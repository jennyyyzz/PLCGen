# -*- coding: utf-8 -*-
"""给 Agent（第 1 项）调用的薄客户端

把三个 CLI 包成函数，Agent 侧只 import 这个文件即可：

    from client import compile_st, run_cases, lint_text

    r = compile_st("out/st/q01.st", pou="PLC_PRG",
                   project="templates/template.project")
    if r["ok"]:
        ...

所有函数都返回 dict（已解析的 JSON），不会抛异常中断 Agent 循环，
失败信息统一在 r["ok"] / r["errors"] / r["fatal"] 里。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable


def _run(cmd: list[str], timeout: int) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout after %ss" % timeout


def _load(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def lint_text(text: str) -> dict:
    """纯文本静态检查，不落盘。"""
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "inline.st"
        f.write_text(text, encoding="utf-8")
        out = Path(d) / "lint.json"
        _run([PY, str(HERE / "st_lint.py"), str(f), "--json", str(out),
              "--quiet"], 60)
        data = _load(out, {"results": []})
        res = (data.get("results") or [{}])[0]
        return {"ok": res.get("ok", False),
                "errors": res.get("errors", []),
                "warnings": res.get("warnings", [])}


def compile_st(st_path: str, pou: str = "PLC_PRG", project: str | None = None,
               backend: str = "auto", timeout: int = 900,
               profile: str | None = None) -> dict:
    """编译单个 ST 文件，返回结构化结果。"""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "compile.json"
        cmd = [PY, str(HERE / "codesys_compile.py"), "--st", str(st_path),
               "--pou", pou, "--backend", backend, "--out", str(out),
               "--timeout", str(timeout)]
        if project:
            cmd += ["--project", str(project)]
        if profile:
            cmd += ["--profile", profile]
        rc, so, se = _run(cmd, timeout + 60)
        data = _load(out, {"items": [], "summary": {}})
        item = (data.get("items") or [{}])[0]
        return {
            "ok": bool(item.get("ok")),
            "result": item.get("result"),
            "stage": item.get("stage"),
            "errors": item.get("errors", []),
            "warnings": item.get("warnings", []),
            "duration_s": item.get("duration_s", 0),
            "env": data.get("env", {}),
            "raw_stdout": so[-1500:],
            "raw_stderr": se[-1500:],
        }


def compile_dir(st_dir: str, project: str, backend: str = "auto",
                timeout: int = 1800) -> dict:
    """一个 CODESYS 进程编译整个目录，返回含 pass_rate 的汇总。"""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "compile_all.json"
        cmd = [PY, str(HERE / "codesys_compile.py"), "--st", str(st_dir),
               "--project", str(project), "--backend", backend,
               "--out", str(out), "--timeout", str(timeout)]
        _run(cmd, timeout + 120)
        return _load(out, {"summary": {}, "items": []})


def run_cases(case_path: str, st_path: str | None = None,
              backend: str = "dry") -> dict:
    """执行测试用例，返回 pass_rate 与逐用例明细。"""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "tests.json"
        cmd = [PY, str(HERE / "run_tests.py"), "--case", str(case_path),
               "--backend", backend, "--out", str(out)]
        if st_path:
            cmd += ["--st", str(st_path)]
        _run(cmd, 600)
        return _load(out, {"total": 0, "pass": 0, "pass_rate": 0.0,
                           "results": []})


if __name__ == "__main__":
    here = HERE / "demo"
    print(json.dumps(lint_text((here / "motor_start_stop.st")
                               .read_text(encoding="utf-8")),
                     ensure_ascii=False, indent=2))
