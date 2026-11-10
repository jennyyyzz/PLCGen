# CODESYS Toolchain HTTP Service — Usage Guide

> Provided by Part 2 (CODESYS Integration & Testing Tools): wraps
> "ST code → static check → CODESYS compile → test execution" behind HTTP endpoints.
> **You do NOT need to install CODESYS or touch any command line — just POST JSON.**
> The service runs on the Windows machine that has CODESYS installed
> (whoever starts it is the host).

## 0. Service Address

The person who starts the service will share the address in the group chat. It is either:

```
http://192.168.x.x:8000        # LAN IP of the host machine
https://xxxx-xxxx-xxxx.trycloudflare.com   # public URL (one-click, see section 4)
```

Verify connectivity first:

```bash
curl http://<service-address>/health
```

If it returns `{"status": "ok", ...}` you are good. You can also open
`http://<service-address>/docs` in a browser for auto-generated interactive
API docs, where every endpoint can be tried out directly on the page.

## 1. Endpoints Overview

| Endpoint        | Method | Purpose                                            | Typical user        |
| --------------- | ------ | -------------------------------------------------- | ------------------- |
| `/`             | GET    | Landing page (JSON list of endpoints, 200 not 404) | Everyone            |
| `/health`       | GET    | Health check / view configuration                  | Everyone            |
| `/api/lint`     | POST   | ST static check (20ms, no CODESYS needed)          | Agent, question writers |
| `/api/compile`  | POST   | Real CODESYS compilation, returns structured errors | Agent           |
| `/api/tests`    | POST   | Execute test cases (dry / sim / ads backends)      | Test-case writers, experiments |
| `/api/pipeline` | POST   | One-shot: lint → compile → test, stops on failure  | Agent main loop     |
| `/api/jobs`     | GET    | Last 200 request records (for troubleshooting)     | Everyone            |

**Common conventions**

- Request bodies are JSON; ST code is passed as **text** in the `st_code` field
  (a `st_path` field for host-local file paths is also supported, but rarely needed).
- Tool failures (compile errors, failed cases) are **NOT** HTTP errors: the service
  still returns 200, with the outcome in the `ok` / `errors` fields of the body.
  Only malformed requests yield 4xx. You don't need try/except to guard compile errors.
- Values of the `result` field: `PASS` / `COMPILE_FAIL` / `STATIC_FAIL`
  (rejected by the static check before compilation) / `TEST_FAIL` / `NOT_RUN`.

## 2. Request/Response Examples per Endpoint

### 2.1 `/api/lint` — Static Check

Call this first to catch low-level errors (unclosed blocks, misuse of `=`,
duplicate declarations, etc.). Results in ~20ms — saves a whole compile round.

**Request**

```json
{
  "st_code": "PROGRAM PLC_PRG\nVAR\n  x : BOOL;\nEND_VAR\nIF x THEN\nEND_IF\n"
}
```

**Response** (`ok=false` on error, messages carry line numbers)

```json
{
  "ok": false,
  "errors": [
    {"line": 6, "col": 1, "code": "E001", "message": "IF not closed (missing END_IF)"}
  ],
  "warnings": [],
  "st_source": "..."
}
```

### 2.2 `/api/compile` — CODESYS Compilation

**Request**

```json
{
  "st_code": "PROGRAM PLC_PRG\n...",
  "pou": "PLC_PRG",
  "backend": "auto",
  "timeout": 900
}
```

- `backend`: `auto` (default — real compile if CODESYS is available on the host,
  otherwise degrades to a static check) / `codesys` / `lint`
- `pou`: defaults to `PLC_PRG`; only pass it if your ST uses a different POU name

**Response**

```json
{
  "ok": true,
  "result": "PASS",
  "stage": "codesys",
  "errors": [],
  "warnings": [],
  "duration_s": 1.8,
  "st_source": "..."
}
```

On failure `errors` is an array whose elements look like
`{"level": "error", "text": "Unknown type: 'NOT_A_TYPE'"}` — you can paste them
straight into the next repair-round prompt. **Note: SP22 compiler messages have
no line numbers**; when repairing, the Agent must locate the issue from the error
text plus a re-read of the code.

### 2.3 `/api/tests` — Execute Test Cases

- `backend` — choose one of:
  - `dry`: structure validation only (checks that variables referenced in the
    cases are declared in the ST and types match). **Run this first whenever you
    finish writing a case file.**
  - `sim`: offline simulation — actually executes the ST logic scan-cycle by
    scan-cycle (no PLC needed on the host)
  - `ads`: connects to a real CODESYS Control Win runtime (requires `ams` / `port`
    parameters, provided by the person hosting the service)
- Test cases are embedded directly in the `cases` field, following the course's
  "Test Case Template and Examples" format.

**Request**

```json
{
  "st_code": "PROGRAM PLC_PRG\n...",
  "cases": {
    "task_id": "motor_start_stop",
    "title": "Motor start/stop control",
    "pou": "PLC_PRG",
    "scan_ms": 20,
    "interface": [
      {"name": "StartBtn", "dir": "input",  "type": "BOOL", "desc": "start button"},
      {"name": "StopBtn",  "dir": "input",  "type": "BOOL", "desc": "stop button"},
      {"name": "EStop",    "dir": "input",  "type": "BOOL", "desc": "emergency stop"},
      {"name": "Motor",    "dir": "output", "type": "BOOL", "desc": "motor output"}
    ],
    "cases": [
      {
        "id": "TC01",
        "name": "Normal start and latched run",
        "coverage": "initialization, normal start, latched run after release",
        "initial_state": "all inputs FALSE, Motor FALSE",
        "steps": [
          {"cycle": 0, "inputs": {"StartBtn": 0, "StopBtn": 0, "EStop": 0},
           "expect": {"Motor": 0}, "check": "stays stopped after init"},
          {"cycle": 1, "inputs": {"StartBtn": 1, "StopBtn": 0, "EStop": 0},
           "expect": {"Motor": 1}, "check": "starts when conditions met"},
          {"cycle": 2, "inputs": {"StartBtn": 0, "StopBtn": 0, "EStop": 0},
           "expect": {"Motor": 1}, "check": "keeps running after release"}
        ]
      }
    ]
  },
  "backend": "sim"
}
```

See `codesys_service/demo/motor_start_stop.testcase.json` in the repo for the
full field reference (can be copied directly as a template).

**Response** (`results` is grouped per case file; each group's `cases` holds the
per-case details; failed steps carry a `diff`)

```json
{
  "backend": "sim",
  "total": 3,
  "pass": 2,
  "pass_rate": 0.6667,
  "results": [
    {
      "task_id": "motor_start_stop",
      "mode": "sim",
      "cases": [
        {"id": "TC01", "name": "Normal start and latched run", "result": "PASS",
         "steps": [{"cycle": 1, "inputs": {"StartBtn": 1, "...": 0},
                    "expect": {"Motor": 1}, "actual": {"Motor": true},
                    "ok": true, "diff": []}]},
        {"id": "TC03", "name": "Emergency stop", "result": "FAIL",
         "steps": [{"cycle": 1, "expect": {"Motor": 0},
                    "actual": {"Motor": true}, "ok": false,
                    "diff": ["Motor: expect 0, actual 1"]}]}
      ]
    }
  ]
}
```

### 2.4 `/api/pipeline` — One-Shot (use this in the Agent main loop)

**Request**

```json
{
  "st_code": "PROGRAM PLC_PRG\n...",
  "cases": { "...same as above..." },
  "compile_backend": "auto",
  "test_backend": "sim"
}
```

**Response**: `stage` tells you which step failed (`lint` / `compile` / `done`),
together with that step's full error details:

```json
{
  "ok": false,
  "stage": "compile",
  "result": "COMPILE_FAIL",
  "errors": [...],
  "steps": {
    "lint": {"ok": true, "errors": [], "warnings": []},
    "compile": {"ok": false, "result": "COMPILE_FAIL", "errors": [...]}
  }
}
```

`cases` is optional (lint + compile only). `pass_rate` is only present when tests ran.

## 3. Python Example (recommended for Agent / experiment scripts)

```python
import httpx

BASE = "http://192.168.x.x:8000"   # replace with the shared service address

def check(code: str) -> dict:
    """Generate -> check -> compile -> test, in one call."""
    r = httpx.post(f"{BASE}/api/pipeline", json={
        "st_code": code,
        "cases": CASE_JSON,          # test cases for the current task
        "compile_backend": "auto",
        "test_backend": "sim",
    }, timeout=600)
    return r.json()

# Example Agent repair loop
for round_no in range(1, MAX_ROUNDS + 1):
    result = check(current_code)
    if result["ok"]:
        break
    if result["stage"] == "lint":
        prompt = f"Static check failed: {result['errors']}\nPlease fix."
    elif result["stage"] == "compile":
        prompt = f"CODESYS compile errors: {result['errors']}\nPlease fix."
    else:
        prompt = f"Tests not all passed (pass_rate={result.get('pass_rate')}): {result['steps']['tests']['results']}"
    current_code = llm_fix(prompt, current_code)
```

Quick command-line check (no code needed):

```bash
curl -X POST http://192.168.x.x:8000/api/lint \
     -H "Content-Type: application/json" \
     -d "{\"st_code\": \"PROGRAM PLC_PRG\\nEND_PROGRAM\"}"
```

## 4. Starting the Service (host machine only)

### Option A — one-click public URL (recommended)

```bash
pip install -r requirements.txt
python codesys_service/serve_public.py
```

This starts the local service AND a free [cloudflared](https://github.com/cloudflare/cloudflared/releases)
quick tunnel, then prints a public URL like `https://xxxx-xxxx.trycloudflare.com`
(also written to `codesys_service/out/public_url.txt`). Share that URL with the
team — they can use it from anywhere, no VPN, no LAN, no firewall changes.

Prerequisites for Option A:

1. `cloudflared-windows-amd64.exe` (single file, no install, no account) —
   [download here](https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe)
   (~60MB; if GitHub is slow, prefix the URL with a mirror such as `https://ghproxy.net/`).
   Drop it anywhere the script looks: next to `serve_public.py`, in a `bin/`
   folder beside it, `~/Downloads/`, on your `PATH`, or pass `--cloudflared <path>`.
2. Everything from Option B below (CODESYS, template project).

Caveats (fine for this course, know them anyway):

- The public URL is **random and changes on every restart** — re-share it after restarting.
  A fixed URL would need a free Cloudflare account + named tunnel (small config, optional).
- The host machine must stay awake while the team uses the service.
- The quick tunnel is free and unmetered, but has no SLA.

### Option B — LAN only

On the Windows machine with CODESYS installed (repo root):

```powershell
pip install -r requirements.txt      # includes fastapi / uvicorn
python codesys_service/server.py     # default 127.0.0.1:8000
# LAN-accessible:
python codesys_service/server.py --host 0.0.0.0 --port 8000
```

Prerequisites:

1. CODESYS V3.5 SP22 installed (whole team uses the same version), and the template
   project `codesys_service/templates/template.project` generated (already in the repo);
2. First compile takes ~35s (CODESYS process startup), then 1–2s per task;
3. Allow the port through the Windows firewall (a prompt appears on first start —
   check "Private networks").

## 5. Troubleshooting

| Symptom                                          | Cause / fix                                                        |
| ------------------------------------------------ | ------------------------------------------------------------------ |
| Cannot reach `/health`                           | Service not started, or firewall blocks the port; contact the host |
| Compile spins until timeout                      | CODESYS `--noUI` mode blocked by a license/update popup — host checks the taskbar, closes the popup, retry |
| Compile says `result: PASS` but tests `NOT_RUN`  | The `sim` backend does not support CASE/FOR/timer statements — expected behavior (it never fakes a pass) |
| Want to know why a request was slow              | `GET /api/jobs` shows duration and outcome of the last 200 requests |
| Public URL suddenly unreachable                  | Host machine offline/sleeping, or service was restarted — a new URL was issued; get the fresh one from the host |

## 6. Metrics (for the experiment report)

| Metric                          | Where to get it                                                      |
| ------------------------------- | -------------------------------------------------------------------- |
| First-shot compile pass rate    | Call `/api/compile` once per task; count tasks with `ok=true`         |
| Pass rate after n repairs       | Call again after each Agent repair round; record which round `ok=true` |
| Compile time                    | `duration_s` (CODESYS compile only, excluding project open)           |
| Test pass rate                  | `pass_rate` (in `/api/tests` or `/api/pipeline` responses)            |
| Share caught by the static check| Proportion of tasks with `result=STATIC_FAIL` in `pipeline` responses (worth a separate column in the report) |
