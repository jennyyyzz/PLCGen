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

### 3. Configure CODESYS

Install CODESYS Development System and configure the local compilation environment.

The project uses CODESYS to compile generated Structured Text (ST) code and provide compilation feedback to the Agent.

Refer to the CODESYS setup instructions once the compiler interface has been implemented.

### 4. Run the Coding Agent

Once the Agent's command-line interface is implemented, you will be able to run PLC code-generation tasks using either model.

```bash
python main.py ...
```

The Agent will generate ST code, invoke the CODESYS compiler, and attempt to repair compilation errors according to the configured retry limit.
