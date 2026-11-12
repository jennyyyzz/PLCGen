# -*- coding: utf-8 -*-
"""轻量 ST 解释器（离线仿真执行）

用途：没有 CODESYS / 没有软 PLC 时，也能把 ST 代码按扫描周期跑起来，
给测试用例一个真实的功能性反馈（不是假数据）。

支持子集
  - 声明：VAR ... END_VAR，类型 BOOL / INT / DINT / REAL（其余按数值处理）
  - 语句：赋值 `:=`、IF / ELSIF / ELSE / END_IF、FOR ... TO ... BY ... DO ... END_FOR
  - 表达式：AND OR XOR NOT MOD、比较 = <> < > <= >=、+ - * / 、括号、TRUE/FALSE、数字
  - 字面量：进制字面量 16#8001 / 2#1010_1011 / 8#17 / 10#12（下划线分隔可用），
    类型前缀 INT#16#80 / DINT#-5 / BOOL#1 / BOOL#TRUE，时间 T#5S / TIME#500MS
  - 定时器：TON / TOF / TP（声明 + `t(IN:=.., PT:=T#5S);` 调用 + `t.Q` / `t.ET` 成员），
    时基为扫描周期累加的虚拟时钟，与 hold_ms 配合可测长延时
  - 数组：`a : ARRAY[0..9] OF BOOL;` 声明 + `a[i] := x;` / `x := a[i];` 下标读写
    （元素须为标量类型；结构体数组元素的下标访问不支持）
  - 字符串：STRING 字面量 `'abc'`（单引号转义写 `''`）、STRING 下标读取
    （1 基，越界返回 0），以及 Standard Library 的 LEN / LEFT / RIGHT / MID /
    CONCAT / INSERT / DELETE / REPLACE / FIND；TRIM / UPPER / LOWER 为
    仿真额外支持（CODESYS 中不属于 Standard，使用时需另引 StringUtils）
  - 函数：类型转换 X_TO_Y（如 TIME_TO_UDINT）与 ABS / MIN / MAX / LIMIT / SEL

不支持（遇到会明确抛 Unsupported，绝不静默当成通过）
  CASE / FOR / WHILE / REPEAT / 结构体成员访问 / 自定义 FB 的调用（仅内置定时器）

明确边界：这是逻辑预演，**不能替代 CODESYS 编译与运行**。
它能回答「这段逻辑按用例走一遍对不对」，不能回答「代码能不能编译」。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from st_lint import strip_comments, collect_declarations, Report, split_pou  # noqa


class Unsupported(Exception):
    pass


class BreakLoop(Exception):
    pass


class ContinueLoop(Exception):
    pass


TOKEN_RE = re.compile(
    r"(?P<str>'(?:[^']|'')*')"
    r"|(?P<typed>[A-Za-z_]\w*#[A-Za-z0-9_.#+-]+)"
    r"|(?P<based>\d{1,2}#[0-9A-Fa-f_]+)"
    r"|(?P<num>\d+\.\d+|\d+)"
    r"|(?P<id>[A-Za-z_]\w*)"
    r"|(?P<op>:=|<>|<=|>=|=|<|>|\+|-|\*|/|\(|\)|;|\.[A-Za-z_]\w*|\[|\]|,)"
)

TYPED_LITERAL = re.compile(r"[A-Za-z_]\w*#\S+")

BOOL_TYPES = {"BOOL"}
STRING_TYPES = {"STRING", "WSTRING"}
NUM_TYPES = {"INT", "DINT", "SINT", "UINT", "UDINT", "REAL", "LREAL",
             "BYTE", "WORD", "DWORD", "TIME"}

SUPPORTED_BASES = {2, 8, 10, 16}
_BASED_RE = re.compile(r"^(\d{1,2})#([0-9A-Fa-f_]+)$")

# 时间字面量 T#5S / TIME#500MS -> 毫秒数（内部统一用 ms 数值表示 TIME）
DUR_RE = re.compile(r"(\d+(?:\.\d+)?)(us|ns|ms|s|m|h|d)", re.I)
DUR_UNITS = {"us": 0.001, "ns": 0.000001, "ms": 1.0, "s": 1000.0,
             "m": 60000.0, "h": 3600000.0, "d": 86400000.0}


def _duration_ms(body: str):
    total = 0.0
    matched = 0
    consumed = 0
    for m in DUR_RE.finditer(body):
        matched += 1
        consumed += len(m.group(0))
        total += float(m.group(1)) * DUR_UNITS[m.group(2).lower()]
    # 全串都要被时长单元覆盖，防止把普通数字误判成时间
    if not matched or consumed != len(body.replace(" ", "")):
        return None
    return int(total) if total == int(total) else total


def _based_value(body: str):
    """`16#8001` / `2#1010_10` -> int；不是进制字面量返回 None。"""
    m = _BASED_RE.match(body)
    if not m:
        return None
    base = int(m.group(1))
    digits = m.group(2).replace("_", "")
    if base not in SUPPORTED_BASES or not digits:
        raise Unsupported("不支持的进制字面量 %s（仅支持 2# 8# 10# 16#）" % body)
    return int(digits, base)


def decode_string(text: str) -> str:
    """ST 字符串字面量 `'a''b'` -> a'b（单引号用两个单引号转义）。"""
    body = text.strip()
    if len(body) < 2 or not body.startswith("'") or not body.endswith("'"):
        raise Unsupported("无法解析的字符串字面量 %s" % text)
    return body[1:-1].replace("''", "'")


def decode_literal(text: str):
    """把 ST 字面量转成 Python 值。

    支持：基于进制的数字字面量（16#8001、2#1010_1011、8#17、10#12）、
    数值类型前缀（INT#16#80、DINT#-5、REAL#3.14）、BOOL 前缀（BOOL#1、BOOL#TRUE）。
    其余（TIME#5s 等）抛 Unsupported。
    """
    s = text.strip()
    prefix = None
    m = re.match(r"^([A-Za-z_]\w*)#", s)
    if m:
        prefix = m.group(1).upper()
        s = s[m.end():]

    if prefix in ("T", "TIME", "LTIME"):
        # 时间字面量：T#5S / TIME#1M30S / T#500MS -> 毫秒数
        v = _duration_ms(s)
        if v is not None:
            return v
        raise Unsupported("无法解析的时间字面量 %s" % text)

    if prefix == "BOOL":
        u = s.upper()
        if u in ("1", "TRUE"):
            return True
        if u in ("0", "FALSE"):
            return False
        raise Unsupported("不支持的 BOOL 字面量 %s" % text)

    if prefix in NUM_TYPES:
        sign = 1
        if s.startswith("-"):
            sign, s = -1, s[1:]
        v = _based_value(s)
        if v is None:
            try:
                v = float(s) if ("." in s or prefix in ("REAL", "LREAL")) else int(s)
            except ValueError:
                raise Unsupported("不支持的类型化字面量 %s" % text)
        return sign * v

    if prefix is not None:
        raise Unsupported("不支持的类型化字面量 %s（当前仅支持数值/BOOL 前缀）" % text)

    v = _based_value(s)
    if v is not None:
        return v
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        raise Unsupported("无法解析的字面量 %s" % text)


def tokenize(text: str):
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in " \t\r\n":
            i += 1
            continue
        m = TOKEN_RE.match(text, i)
        if not m:
            raise Unsupported("无法识别的字符 %r（位置 %d）" % (ch, i))
        kind = m.lastgroup
        val = m.group(0)
        tokens.append((kind, val))
        i = m.end()
    return tokens


class Parser:
    def __init__(self, tokens):
        self.t = tokens
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def next(self):
        tok = self.peek()
        self.i += 1
        return tok

    def accept_kw(self, kw):
        k, v = self.peek()
        if k == "id" and v.upper() == kw:
            self.i += 1
            return True
        return False

    def expect_kw(self, kw):
        if not self.accept_kw(kw):
            k, v = self.peek()
            raise Unsupported("期望 %s，实际是 %s" % (kw, v))

    def expect_op(self, op):
        k, v = self.peek()
        if k == "op" and v == op:
            self.i += 1
            return
        raise Unsupported("期望 %r，实际是 %r" % (op, v))

    # -------------------------------------------------- 语句
    def parse_program(self):
        stmts = []
        while self.peek()[0] is not None:
            s = self.parse_statement()
            if s is not None:
                stmts.append(s)
        return stmts

    def parse_statement(self):
        k, v = self.peek()
        if k == "op" and v == ";":
            self.i += 1
            return None
        if k == "id":
            up = v.upper()
            if up == "IF":
                return self.parse_if()
            if up == "FOR":
                return self.parse_for()
            if up == "EXIT":
                self.i += 1
                if self.peek() == ("op", ";"):
                    self.i += 1
                return ("exit",)
            if up == "CONTINUE":
                self.i += 1
                if self.peek() == ("op", ";"):
                    self.i += 1
                return ("continue",)
            if up == "RETURN":
                self.i += 1
                if self.peek() == ("op", ";"):
                    self.i += 1
                return ("return",)
            if up in ("CASE", "WHILE", "REPEAT"):
                raise Unsupported("不支持的控制语句 %s（当前解释器只支持 IF）" % up)
        return self.parse_assign()

    def parse_assign(self):
        k, v = self.peek()
        if k != "id":
            raise Unsupported("语句应以变量名开头，实际是 %r" % (v,))
        name = v.upper()
        self.i += 1
        k2, v2 = self.peek()

        # FB 调用语句：t(IN := x, PT := T#5S);（内置定时器 TON/TOF/TP）
        if k2 == "op" and v2 == "(":
            self.i += 1
            args = []
            if self.peek() != ("op", ")"):
                while True:
                    pk, pv = self.next()
                    if pk != "id":
                        raise Unsupported("调用参数应以参数名开头，实际是 %r" % (pv,))
                    pname = pv.upper()
                    self.expect_op(":=")
                    val = self.parse_expr()
                    args.append((pname, val))
                    if self.peek() == ("op", ","):
                        self.i += 1
                        continue
                    break
            self.expect_op(")")
            if self.peek() == ("op", ";"):
                self.i += 1
            return ("fbcall", name, args)

        # 数组元素赋值：a[i] := x;  /  结构体数组字段赋值：a[i].f := x;
        if k2 == "op" and v2 == "[":
            self.i += 1
            idx = self.parse_expr()
            self.expect_op("]")
            pk, pv = self.peek()
            if pk == "op" and pv.startswith(".") and len(pv) > 1:
                self.i += 1
                field = pv[1:].upper()
                self.expect_op(":=")
                expr = self.parse_expr()
                if self.peek() == ("op", ";"):
                    self.i += 1
                return ("assign_idx_field", name, idx, field, expr)
            self.expect_op(":=")
            expr = self.parse_expr()
            if self.peek() == ("op", ";"):
                self.i += 1
            return ("assign_idx", name, idx, expr)

        # 结构体字段赋值：s.f := x;
        if k2 == "op" and v2.startswith(".") and len(v2) > 1:
            self.i += 1
            field = v2[1:].upper()
            self.expect_op(":=")
            expr = self.parse_expr()
            if self.peek() == ("op", ";"):
                self.i += 1
            return ("assign_field", name, field, expr)

        self.expect_op(":=")
        expr = self.parse_expr()
        if self.peek() == ("op", ";"):
            self.i += 1
        return ("assign", name, expr)

    def parse_if(self):
        self.expect_kw("IF")
        branches = []
        cond = self.parse_expr()
        self.expect_kw("THEN")
        body = self.parse_block({"ELSIF", "ELSE", "END_IF"})
        branches.append((cond, body))
        while self.accept_kw("ELSIF"):
            cond = self.parse_expr()
            self.expect_kw("THEN")
            body = self.parse_block({"ELSIF", "ELSE", "END_IF"})
            branches.append((cond, body))
        else_body = []
        if self.accept_kw("ELSE"):
            else_body = self.parse_block({"END_IF"})
        self.expect_kw("END_IF")
        if self.peek() == ("op", ";"):
            self.i += 1
        return ("if", branches, else_body)

    def parse_block(self, stop_kws):
        stmts = []
        while True:
            k, v = self.peek()
            if k is None:
                raise Unsupported("IF 结构缺少结束标记")
            if k == "id" and v.upper() in stop_kws:
                return stmts
            s = self.parse_statement()
            if s is not None:
                stmts.append(s)

    def parse_for(self):
        self.expect_kw("FOR")
        k, v = self.next()
        if k != "id":
            raise Unsupported("FOR 循环变量应为标识符，实际是 %r" % (v,))
        var = v.upper()
        self.expect_op(":=")
        start = self.parse_expr()
        self.expect_kw("TO")
        end = self.parse_expr()
        step = ("lit", 1)
        if self.accept_kw("BY"):
            step = self.parse_expr()
        self.expect_kw("DO")
        body = self.parse_block({"END_FOR"})
        self.expect_kw("END_FOR")
        if self.peek() == ("op", ";"):
            self.i += 1
        return ("for", var, start, end, step, body)

    # -------------------------------------------------- 表达式
    def parse_expr(self):
        return self.parse_or()

    def parse_or(self):
        node = self.parse_xor()
        while True:
            k, v = self.peek()
            if k == "id" and v.upper() == "OR":
                self.i += 1
                node = ("bin", "OR", node, self.parse_xor())
            else:
                return node

    def parse_xor(self):
        node = self.parse_and()
        while True:
            k, v = self.peek()
            if k == "id" and v.upper() == "XOR":
                self.i += 1
                node = ("bin", "XOR", node, self.parse_and())
            else:
                return node

    def parse_and(self):
        node = self.parse_cmp()
        while True:
            k, v = self.peek()
            if k == "id" and v.upper() == "AND":
                self.i += 1
                node = ("bin", "AND", node, self.parse_cmp())
            else:
                return node

    def parse_cmp(self):
        node = self.parse_add()
        while True:
            k, v = self.peek()
            if k == "op" and v in ("=", "<>", "<", ">", "<=", ">="):
                self.i += 1
                node = ("bin", v, node, self.parse_add())
            else:
                return node

    def parse_add(self):
        node = self.parse_mul()
        while True:
            k, v = self.peek()
            if k == "op" and v in ("+", "-"):
                self.i += 1
                node = ("bin", v, node, self.parse_mul())
            else:
                return node

    def parse_mul(self):
        node = self.parse_unary()
        while True:
            k, v = self.peek()
            if (k == "op" and v in ("*", "/")) or (k == "id" and v.upper() == "MOD"):
                self.i += 1
                node = ("bin", v.upper(), node, self.parse_unary())
            else:
                return node

    def parse_unary(self):
        k, v = self.peek()
        if k == "id" and v.upper() == "NOT":
            self.i += 1
            return ("not", self.parse_unary())
        if k == "op" and v == "-":
            self.i += 1
            return ("neg", self.parse_unary())
        return self.parse_primary()

    def parse_primary(self):
        k, v = self.next()
        if k == "num":
            return ("lit", float(v) if "." in v else int(v))
        if k == "str":
            return ("lit", decode_string(v))
        if k in ("based", "typed"):
            return ("lit", decode_literal(v))
        if k == "id":
            up = v.upper()
            if up == "TRUE":
                return ("lit", True)
            if up == "FALSE":
                return ("lit", False)
            if up in ("AND", "OR", "NOT", "THEN", "ELSE", "ELSIF"):
                raise Unsupported("表达式里出现非法关键字 %s" % up)
            pk, pv = self.peek()
            # 函数调用：TIME_TO_UDINT(x)、ABS(x) 等
            if pk == "op" and pv == "(":
                self.i += 1
                args = []
                if self.peek() != ("op", ")"):
                    args.append(self.parse_expr())
                    while self.peek() == ("op", ","):
                        self.i += 1
                        args.append(self.parse_expr())
                self.expect_op(")")
                return ("call", up, args)
            # 数组元素读取：a[i]  /  结构体数组字段读取：a[i].f
            if pk == "op" and pv == "[":
                self.i += 1
                idx = self.parse_expr()
                self.expect_op("]")
                nk, nv = self.peek()
                if nk == "op" and nv.startswith(".") and len(nv) > 1:
                    self.i += 1
                    return ("index_field", up, idx, nv[1:].upper())
                return ("index", up, idx)
            # 定时器成员：t.Q / t.ET（tokenizer 把 .Q 合成一个 op token）
            if pk == "op" and pv.startswith(".") and len(pv) > 1:
                self.i += 1
                return ("member", up, pv[1:].upper())
            return ("var", up)
        if k == "op" and v == "(":
            node = self.parse_expr()
            self.expect_op(")")
            return node
        raise Unsupported("无法解析的表达式片段 %r" % (v,))


# ------------------------------------------------------------------ 执行

TIMER_TYPES = {"TON", "TOF", "TP"}
ARRAY_RE = re.compile(
    r"^ARRAY\s*\[\s*(-?\d+)\s*\.\.\s*(-?\d+)\s*\]\s*OF\s+(.+)$", re.I)

# 支持的内置函数：类型转换 X_TO_Y / TO_Y + 通用数值函数
CONV_RE = re.compile(r"^(?:[A-Z0-9]+_)?TO_[A-Z0-9]+$")
INT_TYPES = {"SINT", "INT", "DINT", "USINT", "UINT", "UDINT",
             "BYTE", "WORD", "DWORD", "LWORD", "TIME"}
GENERIC_FUNCS = {"ABS", "MIN", "MAX", "LIMIT", "SEL"}


def _call_func(name, args):
    """内置函数求值（类型转换 + 数值函数 + Standard 字符串函数）。"""
    if name == "LEN":
        return len(_as_str(args[0]))
    if name == "LEFT":
        return _as_str(args[0])[:max(0, _as_int(args[1]))]
    if name == "RIGHT":
        n = max(0, _as_int(args[1]))
        return _as_str(args[0])[-n:] if n else ""
    if name == "MID":  # MID(STR, LEN, POS)，POS 从 1 开始
        s = _as_str(args[0])
        n = max(0, _as_int(args[1]))
        p = max(1, _as_int(args[2]))
        return s[p - 1:p - 1 + n]
    if name == "CONCAT":
        return "".join(_as_str(a) for a in args)
    if name == "INSERT":  # INSERT(STR1, STR2, POS)：插在 POS 之后
        s1, s2 = _as_str(args[0]), _as_str(args[1])
        p = min(len(s1), max(1, _as_int(args[2])))
        return s1[:p] + s2 + s1[p:]
    if name == "DELETE":  # DELETE(STR, LEN, POS)
        s = _as_str(args[0])
        n = max(0, _as_int(args[1]))
        p = max(1, _as_int(args[2]))
        return s[:p - 1] + s[p - 1 + n:]
    if name == "REPLACE":  # REPLACE(STR1, STR2, LEN, POS)
        s1, s2 = _as_str(args[0]), _as_str(args[1])
        n = max(0, _as_int(args[2]))
        p = max(1, _as_int(args[3]))
        return s1[:p - 1] + s2 + s1[p - 1 + n:]
    if name == "FIND":
        pos = _as_str(args[0]).find(_as_str(args[1]))
        return 0 if pos < 0 else pos + 1
    if name in ("TRIM", "UPPER", "LOWER"):
        s = _as_str(args[0])
        return {"TRIM": s.strip, "UPPER": s.upper, "LOWER": s.lower}[name]()
    if name == "ABS":
        return abs(_num(args[0]))
    if name == "MIN":
        return min(_num(a) for a in args)
    if name == "MAX":
        return max(_num(a) for a in args)
    if name == "LIMIT":  # LIMIT(MIN, IN, MAX)
        lo, v, hi = (_num(a) for a in args)
        return max(lo, min(v, hi))
    if name == "SEL":  # SEL(G, IN0, IN1)
        return args[1] if _to_bool(args[0]) else args[2]
    m = re.match(r"^(?:([A-Z0-9]+)_)?TO_([A-Z0-9]+)$", name)
    if m:
        dst = m.group(2)
        v = _num(args[0])
        if dst == "BOOL":
            return _to_bool(v)
        if dst == "TIME":
            return int(v)
        if dst in ("REAL", "LREAL"):
            return float(v)
        return int(v)
    raise Unsupported(
        "不支持的函数 %s（支持类型转换 X_TO_Y、ABS/MIN/MAX/LIMIT/SEL 与 "
        "Standard 字符串函数）" % name)


class TimerInst:
    """TON / TOF / TP 定时器实例（时基为虚拟扫描时钟，单位 ms）。"""

    __slots__ = ("kind", "q", "et", "start", "running", "active", "prev_in")

    def __init__(self, kind):
        self.kind = kind
        self.q = False
        self.et = 0
        self.start = 0
        self.running = False
        self.active = False
        self.prev_in = False

    def call(self, in_, pt, clock, scan=20):
        if self.kind == "TON":
            if in_:
                if not self.running:
                    self.running = True
                    self.start = clock - scan
                el = clock - self.start
                self.et = min(el, pt)
                self.q = el >= pt
            else:
                self.q = False
                self.et = 0
                self.running = False
        elif self.kind == "TOF":
            if in_:
                self.q = True
                self.et = 0
                self.running = False
            else:
                if self.q and not self.running:
                    self.running = True
                    self.start = clock - scan
                if self.running:
                    el = clock - self.start
                    if el >= pt:
                        self.q = False
                        self.et = pt
                        self.running = False
                    else:
                        self.et = el
        elif self.kind == "TP":
            if in_ and not self.prev_in and not self.active:
                self.active = True
                self.start = clock - scan
                self.q = True
                self.et = 0
            if self.active:
                el = clock - self.start
                if el >= pt:
                    self.q = False
                    self.et = pt
                    self.active = False
                else:
                    self.et = el
            self.prev_in = in_


class StructVal:
    """结构体值：按字段名存取（DUT 实例）。"""

    __slots__ = ("fields",)

    def __init__(self, fields):
        self.fields = dict(fields)          # upper-case field name -> default

    def get(self, f):
        if f not in self.fields:
            raise Unsupported("结构体没有字段 %s" % f)
        return self.fields[f]

    def set(self, f, v):
        if f not in self.fields:
            raise Unsupported("结构体没有字段 %s" % f)
        self.fields[f] = v

    def copy(self):
        return StructVal({k: (v.copy() if isinstance(v, StructVal) else v)
                          for k, v in self.fields.items()})


class ArrayVal:
    """数组值：按实际下标存取，越界明确报错。"""

    __slots__ = ("lo", "hi", "default", "data")

    def __init__(self, lo, hi, elem_default):
        self.lo, self.hi = lo, hi
        self.default = elem_default
        # each element needs its own StructVal, otherwise all elements alias one object
        self.data = {i: (elem_default.copy() if isinstance(elem_default, StructVal)
                         else elem_default)
                     for i in range(lo, hi + 1)}

    def get(self, i):
        if i < self.lo or i > self.hi:
            raise Unsupported("数组下标 %d 越界（[%d..%d]）" % (i, self.lo, self.hi))
        return self.data[i]

    def set(self, i, v):
        if i < self.lo or i > self.hi:
            raise Unsupported("数组下标 %d 越界（[%d..%d]）" % (i, self.lo, self.hi))
        self.data[i] = v


def _to_bool(v):
    if isinstance(v, bool):
        return v
    return bool(v)


def _num(v):
    if isinstance(v, bool):
        return 1 if v else 0
    return v


def _as_str(v):
    """把字符串函数实参转成 Python str（标记/数字实参按 ST 的文本形式）。"""
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _as_int(v):
    if isinstance(v, str):
        try:
            return int(float(v.strip()))
        except ValueError:
            raise Unsupported("字符串 %r 不能作为整数参数" % v)
    return int(_num(v))


def eval_expr(node, env, clock=0, scan=20):
    kind = node[0]
    if kind == "lit":
        return node[1]
    if kind == "var":
        if node[1] not in env:
            raise Unsupported("读取了未声明的变量 %s" % node[1])
        return env[node[1]]
    if kind == "call":
        args = [eval_expr(a, env, clock, scan) for a in node[2]]
        return _call_func(node[1], args)
    if kind == "index":
        if node[1] not in env:
            raise Unsupported("读取了未声明的变量 %s" % node[1])
        arr = env[node[1]]
        idx = int(_num(eval_expr(node[2], env, clock, scan)))
        if isinstance(arr, ArrayVal):
            return arr.get(idx)
        if isinstance(arr, str):
            # CODESYS 的 STRING 下标是 1 基，越界读到 NUL（0）
            return ord(arr[idx - 1]) if 1 <= idx <= len(arr) else 0
        raise Unsupported("%s 不是数组或字符串，不能带下标访问" % node[1])
    if kind == "index_field":
        if node[1] not in env:
            raise Unsupported("读取了未声明的变量 %s" % node[1])
        arr = env[node[1]]
        if not isinstance(arr, ArrayVal):
            raise Unsupported("%s 不是数组，不能带下标访问" % node[1])
        elem = arr.get(int(_num(eval_expr(node[2], env, clock, scan))))
        if not isinstance(elem, StructVal):
            raise Unsupported("%s 的元素不是结构体" % node[1])
        return elem.get(node[3])
    if kind == "member":
        if node[1] not in env:
            raise Unsupported("读取了未声明的变量 %s" % node[1])
        obj = env[node[1]]
        if isinstance(obj, StructVal):
            return obj.get(node[2])
        if isinstance(obj, TimerInst):
            if node[2] == "Q":
                return obj.q
            if node[2] == "ET":
                return obj.et
            raise Unsupported("定时器只支持 .Q / .ET 成员，实际是 .%s" % node[2])
        raise Unsupported("成员访问 %s.%s 仅支持定时器（t.Q / t.ET）"
                          % (node[1], node[2]))
    if kind == "not":
        v = eval_expr(node[1], env, clock, scan)
        if isinstance(v, bool):
            return not v
        return ~_num(v)  # 整数按位取反（ST 语义）
    if kind == "neg":
        return -_num(eval_expr(node[1], env, clock, scan))
    if kind == "bin":
        op = node[1]
        a = eval_expr(node[2], env, clock, scan)
        b = eval_expr(node[3], env, clock, scan)
        if op == "AND":
            # ST 语义：两操作数都是 BOOL 时为逻辑与，否则整数按位与
            if isinstance(a, bool) and isinstance(b, bool):
                return a and b
            return _num(a) & _num(b)
        if op == "OR":
            if isinstance(a, bool) and isinstance(b, bool):
                return a or b
            return _num(a) | _num(b)
        if op == "XOR":
            if isinstance(a, bool) and isinstance(b, bool):
                return a != b
            return _num(a) ^ _num(b)
        if op == "=":
            return _num(a) == _num(b)
        if op == "<>":
            return _num(a) != _num(b)
        if op == "<":
            return _num(a) < _num(b)
        if op == ">":
            return _num(a) > _num(b)
        if op == "<=":
            return _num(a) <= _num(b)
        if op == ">=":
            return _num(a) >= _num(b)
        if op == "+":
            return _num(a) + _num(b)
        if op == "-":
            return _num(a) - _num(b)
        if op == "*":
            return _num(a) * _num(b)
        if op == "/":
            if b == 0:
                return 0
            na, nb = _num(a), _num(b)
            # ST: integer operands use integer division (DWORD/2 truncates).
            if isinstance(na, int) and isinstance(nb, int) and not isinstance(na, bool) \
               and not isinstance(nb, bool):
                q = abs(na) // abs(nb)
                return -q if (na < 0) != (nb < 0) else q
            return na / nb
        if op == "MOD":
            return _num(a) % _num(b) if b != 0 else 0
    raise Unsupported("不支持的表达式节点 %r" % (node,))


def exec_stmts(stmts, env, clock=0, scan=20):
    for s in stmts:
        kind = s[0]
        if kind == "assign":
            val = eval_expr(s[2], env, clock, scan)
            # ST assigns structures by value
            env[s[1]] = val.copy() if isinstance(val, StructVal) else val
        elif kind == "assign_idx":
            if s[1] not in env:
                raise Unsupported("读取了未声明的变量 %s" % s[1])
            arr = env[s[1]]
            if not isinstance(arr, ArrayVal):
                raise Unsupported("%s 不是数组，不能带下标赋值（STRING 下标只读）" % s[1])
            idx = int(_num(eval_expr(s[2], env, clock, scan)))
            val = eval_expr(s[3], env, clock, scan)
            arr.set(idx, val.copy() if isinstance(val, StructVal) else val)
        elif kind == "assign_idx_field":
            if s[1] not in env:
                raise Unsupported("读取了未声明的变量 %s" % s[1])
            arr = env[s[1]]
            if not isinstance(arr, ArrayVal):
                raise Unsupported("%s 不是数组" % s[1])
            elem = arr.get(int(_num(eval_expr(s[2], env, clock, scan))))
            if not isinstance(elem, StructVal):
                raise Unsupported("%s 的元素不是结构体" % s[1])
            elem.set(s[3], eval_expr(s[4], env, clock, scan))
        elif kind == "assign_field":
            if s[1] not in env:
                raise Unsupported("读取了未声明的变量 %s" % s[1])
            obj = env[s[1]]
            if not isinstance(obj, StructVal):
                raise Unsupported("%s 不是结构体" % s[1])
            obj.set(s[2], eval_expr(s[3], env, clock, scan))
        elif kind == "fbcall":
            if s[1] not in env:
                raise Unsupported("调用了未声明的功能块实例 %s" % s[1])
            obj = env[s[1]]
            if not isinstance(obj, TimerInst):
                raise Unsupported(
                    "功能块调用仅支持内置定时器（TON/TOF/TP），%s 不是定时器" % s[1])
            kwargs = {name: eval_expr(e, env, clock, scan) for name, e in s[2]}
            in_ = _to_bool(kwargs.get("IN", obj.prev_in))
            pt = int(_num(kwargs.get("PT", 0)))
            obj.call(in_, pt, clock, scan)
        elif kind == "if":
            _, branches, else_body = s
            for cond, body in branches:
                if _to_bool(eval_expr(cond, env, clock, scan)):
                    exec_stmts(body, env, clock, scan)
                    break
            else:
                exec_stmts(else_body, env, clock, scan)
        elif kind == "for":
            _, var, start, end, step, body = s
            first = int(_num(eval_expr(start, env, clock, scan)))
            last = int(_num(eval_expr(end, env, clock, scan)))
            inc = int(_num(eval_expr(step, env, clock, scan)))
            if inc == 0:
                raise Unsupported("FOR 循环的 BY 步长不能为 0")
            value = first
            guard = 0
            while (value <= last) if inc > 0 else (value >= last):
                env[var] = value
                try:
                    exec_stmts(body, env, clock, scan)
                except ContinueLoop:
                    pass
                except BreakLoop:
                    break
                value += inc
                guard += 1
                if guard > 1000000:
                    raise Unsupported("FOR 循环迭代次数过多（> 1,000,000）")
        elif kind == "exit":
            raise BreakLoop()
        elif kind == "continue":
            raise ContinueLoop()
        elif kind == "return":
            return


POU_TERMINATOR = re.compile(
    r"\b(END_PROGRAM|END_FUNCTION_BLOCK|END_FUNCTION)\b\s*;?\s*$", re.IGNORECASE)


def strip_pou_terminator(text: str) -> str:
    """去掉 POU 结尾的 END_PROGRAM / END_FUNCTION_BLOCK / END_FUNCTION。

    这三个结束标记在 CODESYS 文本化 POU 里可有可无，但解释器不认它们
    （会把 END_FUNCTION_BLOCK 当成变量名去解析赋值语句）。
    """
    return POU_TERMINATOR.sub("", text or "").rstrip()


STRUCT_FIELD_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*:\s*([^;:=]+?)\s*(?::=\s*([^;]+?))?\s*;")


def collect_structs(text: str):
    """解析 TYPE ... STRUCT ... END_STRUCT END_TYPE，返回 {类型名: [(字段, 类型文本)]}。"""
    out = {}
    cur = None
    in_struct = False
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        up = line.upper()
        m = re.match(r"^TYPE\s+([A-Za-z_]\w*)\s*:", line, re.I)
        if m:
            cur = m.group(1).upper()
            out.setdefault(cur, [])
            in_struct = "STRUCT" in up
            continue
        if up.startswith("STRUCT") and cur:
            in_struct = True
            continue
        if up.startswith("END_STRUCT"):
            in_struct = False
            continue
        if up.startswith("END_TYPE"):
            cur, in_struct = None, False
            continue
        if cur and in_struct:
            fm = STRUCT_FIELD_RE.match(line)
            if fm:
                out[cur].append((fm.group(1).upper(), fm.group(2).strip()))
    return out


class Program:
    """一个可执行 POU：reset() 回到上电初值，scan() 跑一个周期。

    scan() 使用虚拟扫描时钟（每周期 +scan_ms），TON/TOF/TP 的定时语义
    基于该时钟，配合 run_tests 的 hold_ms 字段可以仿真长延时。
    """

    SUB_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]\s*$")
    FIELD_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*(?:\[\s*(\d+)\s*\])?\s*\.\s*([A-Za-z_]\w*)\s*$")

    def __init__(self, st_text: str, scan_ms: int = 20):
        text = strip_comments(st_text)
        self.decls, _types = collect_declarations(text, Report("<st_sim>"))
        self.structs = collect_structs(text)
        _decl, body = split_pou(text)
        tokens = tokenize(strip_pou_terminator(body))
        self.ast = Parser(tokens).parse_program()
        self.scan_ms = max(int(scan_ms), 1)
        self.clock = 0
        self.env = {}
        self.reset()

    # -------------------------------------------------- 声明类型工具
    def _decl_type(self, name: str) -> str:
        item = self.decls.get(name.upper())
        return (item[2] if item else "").strip()

    def _elem_default(self, type_txt: str):
        t = type_txt.split("(")[0].strip().upper()
        if t in BOOL_TYPES:
            return False
        if t in STRING_TYPES:
            return ""
        if t in NUM_TYPES:
            return 0.0 if t in ("REAL", "LREAL") else 0
        if t in TIMER_TYPES:
            return 0
        if t in getattr(self, "structs", {}):
            return StructVal({f: self._elem_default(ft) for f, ft in self.structs[t]})
        # 未知类型按数值 0 处理
        return 0

    def _split_sub(self, name: str):
        """`Name[3]` -> (NAME, 3)；无下标 -> (NAME, None)。"""
        m = self.SUB_RE.match(str(name))
        if m:
            return m.group(1).upper(), int(m.group(2))
        return str(name).strip().upper(), None

    def var_type(self, name: str) -> str:
        m = self.FIELD_RE.match(str(name))
        if m:
            base, field = m.group(1).upper(), m.group(3).upper()
            t = self._decl_type(base)
            am = ARRAY_RE.match(t) if t else None
            dut = (am.group(3) if am else t).split("(")[0].strip().upper()
            for f, ft in getattr(self, "structs", {}).get(dut, []):
                if f == field:
                    return ft.split("(")[0].strip().upper()
            return "BOOL"
        base, sub = self._split_sub(name)
        t = self._decl_type(base)
        m = ARRAY_RE.match(t) if t else None
        if sub is not None and m:
            # 数组元素：元素类型
            return m.group(3).split("(")[0].strip().upper()
        return t.split("(")[0].strip().upper() if t else "BOOL"

    def default(self, name: str):
        base, _sub = self._split_sub(name)
        t = self._decl_type(base)
        m = ARRAY_RE.match(t) if t else None
        if m:
            return self._elem_default(m.group(3))
        return self._elem_default(t)

    # -------------------------------------------------- 复位 / 读写
    def reset(self):
        self.clock = 0
        env = {}
        for key, (_name, _line, type_txt, init_txt) in self.decls.items():
            t = type_txt.strip()
            u = t.upper()
            if u in TIMER_TYPES:
                env[key] = TimerInst(u)
                continue
            m = ARRAY_RE.match(t)
            if m:
                lo, hi = int(m.group(1)), int(m.group(2))
                env[key] = ArrayVal(lo, hi, self._elem_default(m.group(3)))
                continue
            env[key] = self._init_value(init_txt, self._elem_default(t))
        self.env = env

    def _init_value(self, expr_text, default):
        """VAR 初始化器 `idx : INT := 1`：常量表达式求值，失败回退默认值。"""
        if not expr_text:
            return default
        try:
            node = Parser(tokenize(expr_text + ";")).parse_expr()
            v = eval_expr(node, {}, 0, self.scan_ms)
            return default if v is None else v
        except Exception:
            return default

    def _resolve_field(self, name):
        """`a[i].f` / `s.f` -> (StructVal, FIELD)；不匹配返回 None。"""
        m = self.FIELD_RE.match(str(name))
        if not m:
            return None
        base, idx, field = m.group(1).upper(), m.group(2), m.group(3).upper()
        obj = self.env.get(base)
        if idx is not None:
            if not isinstance(obj, ArrayVal):
                raise Unsupported("%s 不是数组" % base)
            obj = obj.get(int(idx))
        if not isinstance(obj, StructVal):
            raise Unsupported("%s 不是结构体" % base)
        return obj, field

    def write(self, name: str, value):
        fr = self._resolve_field(name)
        if fr:
            fr[0].set(fr[1], value)
            return
        base, sub = self._split_sub(name)
        if sub is not None:
            arr = self.env.get(base)
            if isinstance(arr, ArrayVal):
                arr.set(sub, value)
                return
            raise Unsupported("%s 不是数组，不能按下标写入" % base)
        self.env[base] = value

    def read(self, name: str):
        fr = self._resolve_field(name)
        if fr:
            return fr[0].get(fr[1])
        base, sub = self._split_sub(name)
        if sub is not None:
            arr = self.env.get(base)
            if isinstance(arr, ArrayVal):
                return arr.get(sub)
            raise Unsupported("%s 不是数组，不能按下标读取" % base)
        v = self.env.get(base)
        return self.default(base) if v is None else v

    def scan(self):
        # 第 k 拍在 k*scan_ms 时刻执行：定时器起点对齐周期边界后，
        # hold_ms == PT 时恰好第 PT/scan 拍翻转，ET 数值精确对齐
        self.clock += self.scan_ms
        try:
            exec_stmts(self.ast, self.env, self.clock, self.scan_ms)
        except (BreakLoop, ContinueLoop):
            raise Unsupported("EXIT / CONTINUE 只能出现在循环体内")
