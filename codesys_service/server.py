# -*- coding: utf-8 -*-
"""CODESYS toolchain HTTP service (Part 2 of the course project).

Exposes the three toolchain capabilities (static check / CODESYS compile /
test execution) as an HTTP API, so the rest of the team (Agent framework,
dataset, experiments) can just POST JSON — no CODESYS install, no CLI.

Run (on the machine that has CODESYS installed):
    python server.py                             # default 127.0.0.1:8000
    python server.py --host 0.0.0.0 --port 8000  # LAN-accessible
    python server.py --project templates/template.project

Interactive API docs: http://127.0.0.1:8000/docs

Conventions
  * Request bodies are JSON; ST code is passed as text in "st_code"
    ("st_path" for a host-local file is also supported).
  * Tool failures are NOT HTTP errors: the service returns 200 with the
    outcome in the ok / errors fields, so Agent repair loops stay simple.
    Only malformed requests yield 4xx.
  * CODESYS compilation is serialized with a global lock (batch mode shares
    one POU/project, so concurrent compiles would overwrite each other).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

HERE = Path(__file__).resolve().parent
PY = sys.executable

import client  # noqa: E402  thin client in the same folder; never raises

APP = FastAPI(
    title="PLCGen CODESYS Toolchain Service",
    description=(
        "HTTP wrapper around the CODESYS toolchain: ST static check, "
        "CODESYS compilation, and test-case execution.\n\n"
        "**Conventions**\n\n"
        "- Pass ST source as text in `st_code` (or a host-local path in `st_path`).\n"
        "- Tool failures return HTTP 200 with `ok=false` and details in `errors`; "
        "only malformed requests return 4xx.\n"
        "- `result` values: `PASS` / `COMPILE_FAIL` / `STATIC_FAIL` "
        "(rejected by the static check before compiling) / `TEST_FAIL` / `NOT_RUN`.\n"
        "- Test backends: `dry` (structure check), `sim` (offline simulation), "
        "`ads` (real PLC runtime)."
    ),
    version="1.0.0",
)

# Global configuration (overridable via command-line flags)
CFG: dict[str, Any] = {
    "project": str(HERE / "templates" / "template.project"),
    "profile": None,          # None = let codesys_compile.py auto-detect
}

# CODESYS compile lock: batch mode shares one POU, concurrent runs would clash
_COMPILE_LOCK = threading.Lock()

# Request journal (last 200 entries, queryable via /api/jobs)
_JOBS: list[dict] = []
_JOBS_LOCK = threading.Lock()
_JOB_LIMIT = 200

TS_FMT = "%Y-%m-%d %H:%M:%S"

# Access logs with wall-clock timestamps (uvicorn's default has none)
LOG_CONFIG: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(asctime)s | %(levelprefix)s %(message)s",
            "datefmt": TS_FMT,
            "use_colors": None,
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": '%(asctime)s | %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
            "datefmt": TS_FMT,
        },
    },
    "handlers": {
        "default": {"formatter": "default", "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr"},
        "access": {"formatter": "access", "class": "logging.StreamHandler",
                   "stream": "ext://sys.stdout"},
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO",
                           "propagate": False},
    },
}


# ------------------------------------------------------------------ request models

class LintRequest(BaseModel):
    st_code: str | None = Field(None, description="ST source text (or use st_path)")
    st_path: str | None = Field(None, description="Host-local path to an .st file")


class CompileRequest(BaseModel):
    st_code: str | None = Field(None, description="ST source text (or use st_path)")
    st_path: str | None = Field(None, description="Host-local path to an .st file")
    pou: str | None = Field(
        None,
        description="POU name; omit to use the name declared in the ST code. "
                    "PROGRAM / FUNCTION_BLOCK / FUNCTION are all supported.")
    backend: str = Field("auto", description="auto / codesys / lint")
    project: str | None = Field(None, description="Template project path (default: service config)")
    timeout: int = Field(900, ge=10, le=3600, description="Compile timeout in seconds")


class TestRequest(BaseModel):
    st_code: str | None = Field(None, description="ST source text (required for sim/ads)")
    st_path: str | None = Field(None, description="Host-local path to an .st file")
    cases: dict | list | None = Field(
        None, description="Test case JSON (object or array; or use case_path)")
    case_path: str | None = Field(None, description="Host-local test case file/directory path")
    backend: str = Field("dry", description="dry (structure check) / sim (offline) / ads (real PLC)")
    ams: str | None = Field(None, description="ads backend: AMS NetId, e.g. 127.0.0.1.1.1")
    port: int | None = Field(None, description="ads backend: port, e.g. 851")


class PipelineRequest(BaseModel):
    """lint -> compile -> (optional) tests, stopping at the first failure."""
    st_code: str | None = Field(None, description="ST source text (or use st_path)")
    st_path: str | None = Field(None, description="Host-local path to an .st file")
    cases: dict | list | None = Field(None, description="Test case JSON (optional)")
    case_path: str | None = Field(None, description="Host-local test case path (optional)")
    pou: str | None = Field(
        None,
        description="POU name; omit to use the name declared in the ST code. "
                    "PROGRAM / FUNCTION_BLOCK / FUNCTION are all supported.")
    compile_backend: str = Field("auto", description="auto / codesys / lint")
    test_backend: str = Field("sim", description="dry / sim / ads (only used when cases are provided)")
    project: str | None = Field(None, description="Template project path (default: service config)")
    timeout: int = Field(900, ge=10, le=3600, description="Compile timeout in seconds")
    ams: str | None = Field(None, description="ads backend: AMS NetId")
    port: int | None = Field(None, description="ads backend: port")


# ------------------------------------------------------------------ helpers

def _new_job(endpoint: str, brief: dict) -> str:
    jid = uuid.uuid4().hex[:12]
    with _JOBS_LOCK:
        _JOBS.append({"id": jid, "endpoint": endpoint, "brief": brief,
                      "started": time.time(),
                      "started_at": time.strftime(TS_FMT, time.localtime()),
                      "finished": None, "finished_at": None,
                      "ok": None, "duration_ms": None})
        del _JOBS[:-_JOB_LIMIT]
    return jid


def _finish_job(jid: str, ok: bool, ms: float):
    with _JOBS_LOCK:
        for j in _JOBS:
            if j["id"] == jid:
                j.update(finished=time.time(),
                         finished_at=time.strftime(TS_FMT, time.localtime()),
                         ok=ok, duration_ms=round(ms))
                return


def _materialize_st(req) -> tuple[str, bool]:
    """Resolve st_code / st_path to a real file. Returns (path, is_temp)."""
    if req.st_code:
        f = HERE / "out" / "http" / f"req_{uuid.uuid4().hex[:10]}.st"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(req.st_code, encoding="utf-8")
        return str(f), True
    if req.st_path:
        p = Path(req.st_path)
        if not p.is_file():
            raise HTTPException(404, f"st_path not found: {req.st_path}")
        return str(p), False
    raise HTTPException(400, "provide either st_code or st_path")


def _materialize_cases(req) -> tuple[str | None, bool]:
    if req.cases is not None:
        f = HERE / "out" / "http" / f"req_{uuid.uuid4().hex[:10]}.testcase.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(req.cases, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        return str(f), True
    if req.case_path:
        p = Path(req.case_path)
        if not (p.is_file() or p.is_dir()):
            raise HTTPException(404, f"case_path not found: {req.case_path}")
        return str(p), False
    return None, False


def _cleanup(path: str | None, tmp: bool):
    if path and tmp:
        Path(path).unlink(missing_ok=True)


def _run_tests_cli(case: str, st: str | None, backend: str,
                   ams: str | None, port: int | None) -> dict:
    """Run the test CLI with --ams/--port (client.run_cases does not pass them)."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "tests.json"
        cmd = [PY, str(HERE / "run_tests.py"), "--case", case,
               "--backend", backend, "--out", str(out)]
        if st:
            cmd += ["--st", st]
        if ams:
            cmd += ["--ams", ams]
        if port:
            cmd += ["--port", str(port)]
        try:
            import os as _os
            env = dict(_os.environ)
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                               encoding="utf-8", errors="replace", env=env)
        except subprocess.TimeoutExpired:
            return {"total": 0, "pass": 0, "pass_rate": 0.0,
                    "results": [], "fatal": "test timeout after 600s"}
        try:
            return json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            return {"total": 0, "pass": 0, "pass_rate": 0.0, "results": [],
                    "fatal": "no result file",
                    "raw_stdout": p.stdout[-1500:], "raw_stderr": p.stderr[-1500:]}


# ------------------------------------------------------------------ endpoints

@APP.get("/", tags=["meta"], summary="Service landing page")
def index() -> dict:
    """Landing page so that opening the base URL in a browser makes sense."""
    return {
        "service": APP.title,
        "version": APP.version,
        "docs": "/docs",
        "health": "/health",
        "endpoints": ["/api/lint", "/api/compile", "/api/tests",
                      "/api/pipeline", "/api/jobs"],
        "hint": "POST JSON to the endpoints above; see /docs for live examples.",
    }


@APP.get("/health", tags=["meta"])
def health() -> dict:
    """Health check: version, template project availability, current config."""
    project = Path(CFG["project"])
    return {
        "status": "ok",
        "service": APP.title,
        "version": APP.version,
        "time": time.strftime(TS_FMT, time.localtime()),
        "config": {
            "project": CFG["project"],
            "project_exists": project.is_file(),
            "profile": CFG["profile"] or "<auto-detect>",
        },
        "jobs_total": len(_JOBS),
    }


@APP.get("/api/jobs", tags=["meta"])
def jobs() -> dict:
    """Recent requests (id / endpoint / start time / duration / outcome)."""
    with _JOBS_LOCK:
        return {"count": len(_JOBS), "jobs": list(reversed(_JOBS))}


@APP.post("/api/lint", tags=["toolchain"])
def api_lint(req: LintRequest) -> dict:
    """Static check of ST source (milliseconds, no CODESYS needed).

    Call this first to catch low-level errors (unclosed blocks, misuse of '=',
    duplicate declarations). Saves a whole compile round.
    """
    jid = _new_job("/api/lint", {"st_code_len": len(req.st_code or "")})
    t0 = time.time()
    st, tmp = _materialize_st(req)
    try:
        text = req.st_code if req.st_code else Path(st).read_text(encoding="utf-8")
        r = client.lint_text(text)
        r["st_source"] = st
        _finish_job(jid, r.get("ok", False), (time.time() - t0) * 1000)
        return r
    finally:
        _cleanup(st, tmp)


@APP.post("/api/compile", tags=["toolchain"])
def api_compile(req: CompileRequest) -> dict:
    """Compile ST code with CODESYS (backend=auto degrades to a static check
    when CODESYS is unavailable).

    Returns ok / result / errors / duration_s. The errors array can be pasted
    straight into the next Agent repair prompt.
    """
    jid = _new_job("/api/compile", {"pou": req.pou, "backend": req.backend})
    t0 = time.time()
    st, tmp = _materialize_st(req)
    try:
        with _COMPILE_LOCK:
            r = client.compile_st(
                st, pou=req.pou,
                project=req.project or CFG["project"],
                backend=req.backend, timeout=req.timeout,
                profile=CFG["profile"],
            )
        r["st_source"] = st
        _finish_job(jid, r.get("ok", False), (time.time() - t0) * 1000)
        return r
    finally:
        _cleanup(st, tmp)


@APP.post("/api/tests", tags=["toolchain"])
def api_tests(req: TestRequest) -> dict:
    """Execute test cases.

    - dry: structure validation only (variables declared in the ST, types match)
    - sim: offline simulation, executes the ST logic scan-cycle by scan-cycle
    - ads: real CODESYS Control Win runtime (needs ams / port)

    Cases go in the `cases` field or via `case_path`.
    """
    jid = _new_job("/api/tests", {"backend": req.backend})
    t0 = time.time()
    st, tmp_st = _materialize_st(req)
    case, tmp_case = _materialize_cases(req)
    try:
        if case is None:
            raise HTTPException(400, "provide either cases or case_path")
        if req.backend in ("sim", "ads"):
            r = _run_tests_cli(case, st, req.backend, req.ams, req.port)
        else:
            r = client.run_cases(case, st, backend="dry")
        r.pop("_file", None)
        _finish_job(jid, r.get("pass_rate", 0.0) >= 1.0, (time.time() - t0) * 1000)
        return r
    finally:
        _cleanup(st, tmp_st)
        _cleanup(case, tmp_case)


@APP.post("/api/pipeline", tags=["toolchain"])
def api_pipeline(req: PipelineRequest) -> dict:
    """One-shot: lint -> compile -> tests (optional). Use this in the Agent loop.

    - lint fails   -> stage="lint",    result=STATIC_FAIL (a compile round saved)
    - compile fails-> stage="compile", errors hold the compiler output
    - compile ok   -> if cases are provided, tests run and pass_rate is returned
    """
    jid = _new_job("/api/pipeline",
                   {"pou": req.pou,
                    "compile_backend": req.compile_backend,
                    "test_backend": req.test_backend,
                    "has_cases": req.cases is not None or req.case_path is not None})
    t0 = time.time()
    st, tmp_st = _materialize_st(req)
    case, tmp_case = _materialize_cases(req)
    out: dict = {"st_source": st, "stage": None, "steps": {}}
    ok_all = True
    try:
        # 1) static check
        text = req.st_code if req.st_code else Path(st).read_text(encoding="utf-8")
        lint = client.lint_text(text)
        out["steps"]["lint"] = {"ok": lint["ok"], "errors": lint["errors"],
                                "warnings": lint["warnings"]}
        if not lint["ok"]:
            out.update(ok=False, stage="lint", result="STATIC_FAIL",
                       errors=lint["errors"])
            _finish_job(jid, False, (time.time() - t0) * 1000)
            return out

        # 2) CODESYS compile
        with _COMPILE_LOCK:
            comp = client.compile_st(
                st, pou=req.pou, project=req.project or CFG["project"],
                backend=req.compile_backend, timeout=req.timeout,
                profile=CFG["profile"])
        out["steps"]["compile"] = {"ok": comp["ok"], "result": comp.get("result"),
                                   "pou": comp.get("pou"),
                                   "pou_kind": comp.get("pou_kind"),
                                   "entry": comp.get("entry"),
                                   "errors": comp.get("errors", []),
                                   "duration_s": comp.get("duration_s", 0)}
        out["duration_s"] = comp.get("duration_s", 0)
        if not comp["ok"]:
            out.update(ok=False, stage="compile",
                       result=comp.get("result") or "COMPILE_FAIL",
                       errors=comp.get("errors", []))
            _finish_job(jid, False, (time.time() - t0) * 1000)
            return out

        # 3) tests (optional)
        if case is not None:
            if req.test_backend in ("sim", "ads"):
                tests = _run_tests_cli(case, st, req.test_backend, req.ams, req.port)
            else:
                tests = client.run_cases(case, st, backend="dry")
            tests.pop("_file", None)
            out["steps"]["tests"] = {
                "backend": req.test_backend,
                "total": tests.get("total"), "pass": tests.get("pass"),
                "pass_rate": tests.get("pass_rate"),
                "results": tests.get("results", []),
            }
            out["pass_rate"] = tests.get("pass_rate", 0.0)
            ok_all = tests.get("pass_rate", 0.0) >= 1.0

        out.update(ok=ok_all, stage="done" if case is not None else "compiled",
                   result="PASS" if ok_all else "TEST_FAIL")
        _finish_job(jid, ok_all, (time.time() - t0) * 1000)
        return out
    finally:
        _cleanup(st, tmp_st)
        _cleanup(case, tmp_case)


# ------------------------------------------------------------------ entry point

def main():
    ap = argparse.ArgumentParser(description="CODESYS toolchain HTTP service")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--project", default=None,
                    help="template project path (default: templates/template.project)")
    ap.add_argument("--profile", default=None,
                    help="CODESYS profile name (default: auto-detect)")
    args = ap.parse_args()
    if args.project:
        CFG["project"] = args.project
    if args.profile:
        CFG["profile"] = args.profile

    print(f"[server] toolchain root : {HERE}")
    print(f"[server] template       : {CFG['project']} "
          f"({'EXISTS' if Path(CFG['project']).is_file() else 'MISSING'})")
    print(f"[server] started at     : {time.strftime(TS_FMT)}")
    print(f"[server] listening      : http://{args.host}:{args.port}  (docs: /docs)")
    uvicorn.run(APP, host=args.host, port=args.port, log_level="info",
                log_config=LOG_CONFIG)


if __name__ == "__main__":
    main()
