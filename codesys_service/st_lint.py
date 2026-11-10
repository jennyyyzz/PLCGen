# -*- coding: utf-8 -*-
"""ST 代码静态检查（离线，不依赖 CODESYS）

作用：在把 ST 代码丢给 CODESYS 编译之前，先挡掉一批「必然编译不过」的低级错误，
把一个 2~3 分钟的编译轮次压缩成 20 毫秒的本地检查。

检查项
  E001 块结构不配对（IF/END_IF、VAR/END_VAR ...）
  E002 括号不配对
  E003 单引号不配对
  E004 语句位置误用 `=`（应为 `:=`）
  E005 变量重复声明
  W101 标识符未声明
  W102 疑似缺少分号

用法
  python st_lint.py demo/motor_start_stop.st
  python st_lint.py demo/ --json out/lint.json [--strict]

退出码：0 = 无 error（warning 不影响）；1 = 存在 error
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- 词法基础

POU_HEADERS = ("PROGRAM", "FUNCTION_BLOCK", "FUNCTION")

# 开块关键字 -> 对应的闭块关键字
BLOCK_PAIRS = {
    "IF": "END_IF",
    "CASE": "END_CASE",
    "FOR": "END_FOR",
    "WHILE": "END_WHILE",
    "REPEAT": "END_REPEAT",
    "FUNCTION_BLOCK": "END_FUNCTION_BLOCK",
    "FUNCTION": "END_FUNCTION",
    "PROGRAM": "END_PROGRAM",
    "TYPE": "END_TYPE",
    "STRUCT": "END_STRUCT",
    "ACTION": "END_ACTION",
    "METHOD": "END_METHOD",
    "PROPERTY": "END_PROPERTY",
    "INTERFACE": "END_INTERFACE",
    "VAR": "END_VAR",
    "VAR_INPUT": "END_VAR",
    "VAR_OUTPUT": "END_VAR",
    "VAR_IN_OUT": "END_VAR",
    "VAR_GLOBAL": "END_VAR",
    "VAR_TEMP": "END_VAR",
    "VAR_STAT": "END_VAR",
    "VAR_EXTERNAL": "END_VAR",
}
VAR_OPENERS = {k for k in BLOCK_PAIRS if k.startswith("VAR")}
VAR_MODIFIERS = {"CONSTANT", "RETAIN", "NON_RETAIN", "PERSISTENT"}

KEYWORDS = {
    # 语句
    "IF", "THEN", "ELSIF", "ELSE", "END_IF", "CASE", "OF", "END_CASE",
    "FOR", "TO", "BY", "DO", "END_FOR", "WHILE", "END_WHILE",
    "REPEAT", "UNTIL", "END_REPEAT", "EXIT", "CONTINUE", "RETURN", "JMP",
    # 声明
    "VAR", "VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT", "VAR_GLOBAL", "VAR_TEMP",
    "VAR_STAT", "VAR_EXTERNAL", "VAR_CONFIG", "VAR_ACCESS", "END_VAR",
    "PROGRAM", "END_PROGRAM", "FUNCTION", "END_FUNCTION",
    "FUNCTION_BLOCK", "END_FUNCTION_BLOCK", "ACTION", "END_ACTION",
    "METHOD", "END_METHOD", "PROPERTY", "END_PROPERTY",
    "INTERFACE", "END_INTERFACE", "TYPE", "END_TYPE", "STRUCT", "END_STRUCT",
    "ARRAY", "POINTER", "REFERENCE", "AT", "CONSTANT", "RETAIN", "NON_RETAIN",
    "PERSISTENT", "READ_ONLY", "READ_WRITE", "PUBLIC", "PRIVATE", "PROTECTED",
    "EXTENDS", "IMPLEMENTS", "OVERRIDE", "ABSTRACT", "FINAL", "THIS",
    # 运算符 / 字面量
    "AND", "OR", "XOR", "NOT", "MOD", "AND_THEN", "OR_ELSE",
    "TRUE", "FALSE", "NULL",
    # 基本类型
    "BOOL", "BYTE", "WORD", "DWORD", "LWORD", "SINT", "INT", "DINT", "LINT",
    "USINT", "UINT", "UDINT", "ULINT", "REAL", "LREAL", "TIME", "LTIME",
    "DATE", "LDATE", "TOD", "LTOD", "DT", "LDT", "STRING", "WSTRING", "CHAR",
    "WCHAR", "ANY", "ANY_NUM", "ANY_INT", "BIT",
}

# 常见标准库 / 内置功能块与函数（避免误报未声明）
BUILTINS = {
    "TON", "TOF", "TP", "R_TRIG", "F_TRIG", "CTU", "CTD", "CTUD", "SR", "RS",
    "ABS", "SQRT", "LN", "LOG", "EXP", "EXPT", "SIN", "COS", "TAN", "ASIN",
    "ACOS", "ATAN", "ATAN2", "TRUNC", "ROUND", "CEIL", "FLOOR", "MOVE",
    "SEL", "MUX", "LIMIT", "MAX", "MIN", "ADD", "SUB", "MUL", "DIV",
    "SHL", "SHR", "ROL", "ROR", "ADR", "SIZEOF", "LEN", "LEFT", "RIGHT",
    "MID", "CONCAT", "INSERT", "DELETE", "REPLACE", "FIND",
}

IDENT_RE = re.compile(r"[A-Za-z_]\w*")
ADDR_RE = re.compile(r"%[IQM][XBWDL]?\d+(?:\.\d+)*", re.I)
TYPED_LITERAL_RE = re.compile(r"\b[A-Za-z_]\w*#[^\s;,)]*")
DURATION_RE = re.compile(r"\b\d+(?:\.\d+)?(?:ms|us|ns|s|m|h|d)\b", re.I)

# 语句位置出现 `=`（而非 `:=`）——ST 里赋值必须用 `:=`
ASSIGN_MISUSE_RE = re.compile(
    r"^\s*([A-Za-z_]\w*(?:\s*\[[^\]]*\])?(?:\.[A-Za-z_]\w*)*)\s*=(?!=)"
)
# 以这些关键字开头的行本来就是表达式，允许出现 `=`
EXPR_LINE_PREFIXES = ("IF", "ELSIF", "WHILE", "UNTIL", "CASE")
CONTINUATION_TAIL = (";", "THEN", "DO", "ELSE", "OF", ",", "(", ":=",
                     "AND", "OR", "XOR", "+", "-", "*", "/", "&", "[")
CONTINUATION_HEAD = (".", "+", "-", "*", "/", ")", "]", "AND", "OR", "XOR",
                     "THEN", "DO")


def strip_comments(text: str) -> str:
    """去掉 // 行注释与 (* *) 块注释，保留换行以便行号对齐。"""
    out_chars = []
    i = 0
    n = len(text)
    in_block = False
    in_str = False
    while i < n:
        ch = text[i]
        if in_block:
            if text.startswith("*)", i):
                in_block = False
                i += 2
                continue
            out_chars.append("\n" if ch == "\n" else " ")
            i += 1
            continue
        if in_str:
            out_chars.append(ch)
            if ch == "'":
                in_str = False
            i += 1
            continue
        if ch == "'":
            in_str = True
            out_chars.append(ch)
            i += 1
            continue
        if text.startswith("(*", i):
            in_block = True
            out_chars.append("  ")
            i += 2
            continue
        if text.startswith("//", i):
            while i < n and text[i] != "\n":
                out_chars.append(" ")
                i += 1
            continue
        out_chars.append(ch)
        i += 1
    return "".join(out_chars)


def split_pou(text: str):
    """拆出 (声明段, 实现段)。声明段含 PROGRAM/FUNCTION_BLOCK 头与所有 VAR 块。"""
    lines = text.split("\n")
    header_idx = None
    for i, raw in enumerate(lines):
        s = raw.strip().upper()
        if any(s.startswith(k) for k in POU_HEADERS):
            header_idx = i
            break
    if header_idx is None:
        return "", text

    var_depth = 0
    body_idx = None
    seen_var = False
    for i in range(header_idx + 1, len(lines)):
        s = lines[i].strip()
        if not s:
            continue
        su = s.upper()
        first = su.split()[0].rstrip(";(")
        if first in VAR_OPENERS:
            var_depth += 1
            seen_var = True
            continue
        if first == "END_VAR":
            var_depth = max(0, var_depth - 1)
            continue
        if var_depth > 0:
            continue
        if seen_var and first not in VAR_OPENERS:
            body_idx = i
            break
        if not seen_var:
            body_idx = i
            break

    if body_idx is None:
        body_idx = len(lines)
    return "\n".join(lines[header_idx:body_idx]), "\n".join(lines[body_idx:])


# ---------------------------------------------------------------- 检查实现

class Report:
    def __init__(self, path: str):
        self.path = path
        self.errors = []
        self.warnings = []

    def err(self, line, code, msg, col=1):
        self.errors.append({"line": line, "col": col, "code": code, "message": msg})

    def warn(self, line, code, msg, col=1):
        self.warnings.append({"line": line, "col": col, "code": code, "message": msg})

    def to_dict(self):
        return {
            "file": self.path,
            "ok": not self.errors,
            "errors": sorted(self.errors, key=lambda d: (d["line"], d["code"])),
            "warnings": sorted(self.warnings, key=lambda d: (d["line"], d["code"])),
        }


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def check_quotes(text: str, rep: Report):
    for i, line in enumerate(text.split("\n"), start=1):
        if line.count("'") % 2:
            rep.err(i, "E003", "单引号数量为奇数，字符串未闭合")


def check_parens(text: str, rep: Report):
    stack = []
    for i, ch in enumerate(text):
        if ch == "(":
            stack.append(i)
        elif ch == ")":
            if not stack:
                rep.err(_line_of(text, i), "E002", "多余的右括号 )")
            else:
                stack.pop()
    for pos in stack:
        rep.err(_line_of(text, pos), "E002", "左括号 ( 未闭合")


def check_blocks(text: str, rep: Report):
    stack = []  # (keyword, line)
    tokens = [(m.group(0).upper(), m.start()) for m in IDENT_RE.finditer(text)]
    for idx, (tok, pos) in enumerate(tokens):
        line = _line_of(text, pos)
        # CODESYS 文本化 POU 的 PROGRAM / FUNCTION_BLOCK / FUNCTION 是隐含闭合的，
        # 结尾不写 END_PROGRAM，因此这几个头不参与配对
        if tok in ("PROGRAM", "FUNCTION_BLOCK", "FUNCTION",
                   "ACTION", "METHOD", "PROPERTY", "INTERFACE"):
            continue
        if tok in ("END_PROGRAM", "END_FUNCTION_BLOCK", "END_FUNCTION",
                   "END_ACTION", "END_METHOD", "END_PROPERTY", "END_INTERFACE"):
            continue
        if tok in BLOCK_PAIRS:
            # `VAR CONSTANT` / `VAR RETAIN` 这类修饰词不入栈
            nxt = tokens[idx + 1][0] if idx + 1 < len(tokens) else ""
            if tok == "VAR" and nxt in VAR_MODIFIERS:
                stack.append((tok, line))
                continue
            stack.append((tok, line))
        elif tok.startswith("END_"):
            if not stack:
                rep.err(line, "E001", f"{tok} 没有对应的开块语句")
                continue
            open_tok, open_line = stack.pop()
            expected = BLOCK_PAIRS.get(open_tok)
            if expected != tok:
                rep.err(
                    line, "E001",
                    f"{tok} 与第 {open_line} 行的 {open_tok} 不匹配（应为 {expected}）",
                )
    for open_tok, open_line in stack:
        rep.err(open_line, "E001",
                f"{open_tok} 未闭合（缺少 {BLOCK_PAIRS[open_tok]}）")


DECL_RE = re.compile(
    r"^\s*([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*"
    r"(?:AT\s*%[IQM][XBWDL]?[\d.]+)?\s*:\s*([^;:=]+?)\s*(?::=\s*([^;]+))?;",
    re.I,
)


def collect_declarations(text: str, rep: Report):
    """返回 (已声明名集合, 类型名集合)。"""
    declared = {}
    types = set()
    in_var = False
    in_type = False
    for i, raw in enumerate(text.split("\n"), start=1):
        s = raw.strip()
        if not s:
            continue
        su = s.upper()
        first = su.split()[0].rstrip(";(")
        if first in VAR_OPENERS:
            in_var = True
            continue
        if first == "END_VAR":
            in_var = False
            continue
        if first == "TYPE":
            in_type = True
            continue
        if first == "END_TYPE":
            in_type = False
            continue
        if in_type:
            m = re.match(r"^\s*([A-Za-z_]\w*)\s*:", s)
            if m:
                types.add(m.group(1).upper())
            continue
        if not in_var:
            continue
        m = DECL_RE.match(s)
        if not m:
            continue
        type_txt = m.group(2).strip()
        types.add(type_txt.split("(")[0].strip().upper())
        for name in [x.strip() for x in m.group(1).split(",")]:
            key = name.upper()
            if key in declared:
                rep.err(i, "E005", f"变量 {name} 重复声明（首次在第 {declared[key][1]} 行）")
            else:
                declared[key] = (name, i, type_txt)
    return declared, types


def check_undeclared(text: str, declared, types, rep: Report):
    allowed = set(declared) | {k.upper() for k in BUILTINS} | KEYWORDS | types

    # 擦掉字符串 / 地址 / 类型化字面量 / 时间字面量，避免误报
    scan = re.sub(r"'[^']*'", "''", text)
    scan = ADDR_RE.sub(" ", scan)
    scan = TYPED_LITERAL_RE.sub(" ", scan)
    scan = DURATION_RE.sub(" ", scan)
    # POU 头后面的名字（PROGRAM PLC_PRG 里的 PLC_PRG）是块名，不是变量
    scan = re.sub(
        r"(?im)^[ \t]*(?:PROGRAM|FUNCTION_BLOCK|FUNCTION|INTERFACE|ACTION|METHOD|PROPERTY)"
        r"[ \t]+[A-Za-z_]\w*",
        " ",
        scan,
    )

    for m in IDENT_RE.finditer(scan):
        name = m.group(0)
        key = name.upper()
        pos = m.start()
        if key in allowed:
            continue
        if key.startswith("END_"):
            continue
        # 成员访问 xxx.yyy：只看左侧
        before = scan[max(0, pos - 1):pos]
        after = scan[pos + len(name):pos + len(name) + 1]
        if before == "." or after == ".":
            continue
        if re.match(r"^[A-Za-z0-9_]+_TO_[A-Za-z0-9_]+$", key):
            continue
        if re.match(r"^TO_[A-Za-z0-9_]+$", key):
            continue
        rep.warn(_line_of(text, pos), "W101", f"标识符 {name} 未在 VAR 区声明")


def check_assign_misuse(text: str, rep: Report):
    for i, raw in enumerate(text.split("\n"), start=1):
        s = raw.strip()
        if not s or s.startswith("("):
            continue
        if s.upper().split()[0] in EXPR_LINE_PREFIXES:
            continue
        m = ASSIGN_MISUSE_RE.match(raw)
        if m:
            rep.err(i, "E004",
                    f"语句位置的 `=` 不是赋值，ST 赋值应写成 `{m.group(1)} := ...`")


def check_semicolon(text: str, rep: Report):
    lines = text.split("\n")
    for i, raw in enumerate(lines, start=1):
        s = raw.strip()
        if ":=" not in s:
            continue
        if s.endswith(CONTINUATION_TAIL):
            continue
        nxt = ""
        for j in range(i, min(i + 3, len(lines))):
            if lines[j].strip():
                nxt = lines[j].strip()
                break
        if nxt and nxt.upper().split()[0] in CONTINUATION_HEAD:
            continue
        rep.warn(i, "W102", "该语句疑似缺少结尾分号 ;")


def lint_source(text: str, path: str = "<string>", strict: bool = False) -> dict:
    rep = Report(path)
    clean = strip_comments(text)
    check_quotes(clean, rep)
    check_parens(clean, rep)
    check_blocks(clean, rep)
    declared, types = collect_declarations(clean, rep)
    check_undeclared(clean, declared, types, rep)
    check_assign_misuse(clean, rep)
    check_semicolon(clean, rep)

    result = rep.to_dict()
    if strict:
        result["errors"], result["warnings"] = (
            result["errors"] + result["warnings"], [])
        result["ok"] = not result["errors"]
    result["stats"] = {
        "lines": len(text.split("\n")),
        "declared_vars": len(declared),
        "var_names": [v[0] for v in declared.values()],
    }
    return result


# ---------------------------------------------------------------- CLI

def _iter_targets(p: Path):
    if p.is_dir():
        return sorted(p.rglob("*.st"))
    return [p]


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="ST 代码静态检查（离线）")
    ap.add_argument("target", help=".st 文件或目录")
    ap.add_argument("--json", help="把结果写入 JSON 文件")
    ap.add_argument("--strict", action="store_true", help="把 warning 也当作 error")
    ap.add_argument("--quiet", action="store_true", help="只输出汇总")
    args = ap.parse_args(argv)

    files = _iter_targets(Path(args.target))
    if not files:
        print(f"没有找到 .st 文件：{args.target}")
        return 2

    results = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        r = lint_source(text, str(f), strict=args.strict)
        results.append(r)
        if not args.quiet:
            status = "PASS" if r["ok"] else "FAIL"
            print(f"[{status}] {f}  "
                  f"error={len(r['errors'])} warning={len(r['warnings'])}")
            for e in r["errors"]:
                print(f"   E {f.name}:{e['line']}  {e['code']}  {e['message']}")
            for w in r["warnings"]:
                print(f"   W {f.name}:{w['line']}  {w['code']}  {w['message']}")

    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    print(f"\n静态检查：{passed}/{total} 通过"
          f"（{total - passed} 个文件存在 error）")

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {"total": total, "passed": passed,
                   "pass_rate": round(passed / total, 4),
                   "results": results}
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"结果已写入 {out}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
