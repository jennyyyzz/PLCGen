# -*- coding: utf-8 -*-
"""轻量 ST 解释器（离线仿真执行）

用途：没有 CODESYS / 没有软 PLC 时，也能把 ST 代码按扫描周期跑起来，
给测试用例一个真实的功能性反馈（不是假数据）。

支持子集
  - 声明：VAR ... END_VAR，类型 BOOL / INT / DINT / REAL（其余按数值处理）
  - 语句：赋值 `:=`、IF / ELSIF / ELSE / END_IF
  - 表达式：AND OR XOR NOT MOD、比较 = <> < > <= >=、+ - * / 、括号、TRUE/FALSE、数字

不支持（遇到会明确抛 Unsupported，绝不静默当成通过）
  CASE / FOR / WHILE / REPEAT / 定时器(ton 等) / 数组 / 结构体 / 功能块调用

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


TOKEN_RE = re.compile(
    r"(?P<num>\d+\.\d+|\d+)"
    r"|(?P<id>[A-Za-z_]\w*)"
    r"|(?P<op>:=|<>|<=|>=|=|<|>|\+|-|\*|/|\(|\)|;|\.[A-Za-z_]|\[|\]|,)"
)

TYPED_LITERAL = re.compile(r"[A-Za-z_]\w*#\S+")

BOOL_TYPES = {"BOOL"}
NUM_TYPES = {"INT", "DINT", "SINT", "UINT", "UDINT", "REAL", "LREAL",
             "BYTE", "WORD", "DWORD", "TIME"}


def tokenize(text: str):
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in " \t\r\n":
            i += 1
            continue
        m = TYPED_LITERAL.match(text, i)
        if m:
            raise Unsupported("不支持类型化字面量 %s" % m.group(0))
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
            if up == "RETURN":
                self.i += 1
                if self.peek() == ("op", ";"):
                    self.i += 1
                return ("return",)
            if up in ("CASE", "FOR", "WHILE", "REPEAT", "EXIT", "CONTINUE"):
                raise Unsupported("不支持的控制语句 %s（当前解释器只支持 IF）" % up)
        return self.parse_assign()

    def parse_assign(self):
        k, v = self.peek()
        if k != "id":
            raise Unsupported("语句应以变量名开头，实际是 %r" % (v,))
        name = v.upper()
        self.i += 1
        if self.peek() == ("op", "["):
            raise Unsupported("不支持数组下标")
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
        if k == "id":
            up = v.upper()
            if up == "TRUE":
                return ("lit", True)
            if up == "FALSE":
                return ("lit", False)
            if up in ("AND", "OR", "NOT", "THEN", "ELSE", "ELSIF"):
                raise Unsupported("表达式里出现非法关键字 %s" % up)
            return ("var", up)
        if k == "op" and v == "(":
            node = self.parse_expr()
            self.expect_op(")")
            return node
        raise Unsupported("无法解析的表达式片段 %r" % (v,))


# ------------------------------------------------------------------ 执行

def _to_bool(v):
    if isinstance(v, bool):
        return v
    return bool(v)


def _num(v):
    if isinstance(v, bool):
        return 1 if v else 0
    return v


def eval_expr(node, env):
    kind = node[0]
    if kind == "lit":
        return node[1]
    if kind == "var":
        if node[1] not in env:
            raise Unsupported("读取了未声明的变量 %s" % node[1])
        return env[node[1]]
    if kind == "not":
        return not _to_bool(eval_expr(node[1], env))
    if kind == "neg":
        return -_num(eval_expr(node[1], env))
    if kind == "bin":
        op = node[1]
        a = eval_expr(node[2], env)
        b = eval_expr(node[3], env)
        if op == "AND":
            return _to_bool(a) and _to_bool(b)
        if op == "OR":
            return _to_bool(a) or _to_bool(b)
        if op == "XOR":
            return _to_bool(a) != _to_bool(b)
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
            return _num(a) / _num(b) if b != 0 else 0
        if op == "MOD":
            return _num(a) % _num(b) if b != 0 else 0
    raise Unsupported("不支持的表达式节点 %r" % (node,))


def exec_stmts(stmts, env):
    for s in stmts:
        kind = s[0]
        if kind == "assign":
            env[s[1]] = eval_expr(s[2], env)
        elif kind == "if":
            _, branches, else_body = s
            for cond, body in branches:
                if _to_bool(eval_expr(cond, env)):
                    exec_stmts(body, env)
                    break
            else:
                exec_stmts(else_body, env)
        elif kind == "return":
            return


class Program:
    """一个可执行 POU：reset() 回到上电初值，scan() 跑一个周期。"""

    def __init__(self, st_text: str):
        text = strip_comments(st_text)
        self.decls, _types = collect_declarations(text, Report("<st_sim>"))
        _decl, body = split_pou(text)
        if not body.strip():
            body = text
        tokens = tokenize(body)
        self.ast = Parser(tokens).parse_program()
        self.env = {}
        self.reset()

    def var_type(self, name: str) -> str:
        item = self.decls.get(name.upper())
        return (item[2] if item else "BOOL").split("(")[0].strip().upper()

    def default(self, name: str):
        t = self.var_type(name)
        if t in BOOL_TYPES:
            return False
        if t in NUM_TYPES:
            return 0.0 if t in ("REAL", "LREAL") else 0
        return False

    def reset(self):
        self.env = {k: self.default(k) for k in self.decls}

    def write(self, name: str, value):
        self.env[name.upper()] = value

    def read(self, name: str):
        return self.env.get(name.upper(), self.default(name))

    def scan(self):
        exec_stmts(self.ast, self.env)
