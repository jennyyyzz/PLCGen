# PLCGen

## Quick Start

Python 3.11 or higher is required.

### 1. Create a Virtual Environment and Install Dependencies

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS or Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure the LLM API

Copy `.env.example` to `.env` and add your own DMXAPI API key.

The `.env` file is excluded from Git to prevent accidental exposure of API credentials.

**Default configuration:**

```dotenv
DMX_API_KEY=your_dmxapi_key
LLM_BASE_URL=https://www.dmxapi.cn/v1

MODEL_A=deepseek-v4-pro-0813
MODEL_B=qwen3-coder-flash

LLM_MAX_TOKENS=1800
LLM_TEMPERATURE=0.2
```

### 3. CODESYS Toolchain HTTP Service

The `codesys_service/` directory contains the toolchain provided by Part 2:
offline ST lint, CODESYS compilation, and test-case execution (dry / sim / ads backends),
exposed as an HTTP API so the Agent framework and other parts can simply POST JSON.

**Users of the service** (everyone): see `codesys_service/README.md` for the full
API reference and usage examples. Once the service host is running, just:

```python
import httpx
r = httpx.post("http://<service-host>:8000/api/pipeline", json={
    "st_code": st_code, "cases": case_json, "test_backend": "sim",
}, timeout=600).json()
```

Interactive API docs are available at `http://<service-host>:8000/docs`.

**Service host** (the machine with CODESYS installed):

```bash
pip install -r requirements.txt        # includes fastapi / uvicorn
python codesys_service/serve_public.py # one-click: local service + free public URL
```

`serve_public.py` starts the service and a cloudflared quick tunnel, then prints a
public `https://...trycloudflare.com` URL (needs the single-file
[cloudflared](https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe)
binary, no account required; see `codesys_service/README.md` section 4). For LAN-only
use instead: `python codesys_service/server.py --host 0.0.0.0`.

`codesys_service/selftest.py` runs the whole toolchain end-to-end for verification.

### 4. Run the Coding Agent

Once the Agent's command-line interface is implemented, you will be able to run PLC code-generation tasks using either model.

```bash
python main.py ...
```

The Agent will generate ST code, invoke the CODESYS compiler, and attempt to repair compilation errors according to the configured retry limit.
