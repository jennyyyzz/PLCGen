
"""
Tools used by the program.
"""

import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

def compile_code(code: str) -> str:
    """
    CODESYS compilation tool.

    Sends generated ST code to the CODESYS HTTP service and
    returns structured compilation results.
    """
    base_url = os.getenv("CODESYS_API_URL", "").rstrip("/")
    if not base_url:
        return json.dumps({
            "success": False,
            "errors": ["CODESYS_API_URL is not configured."],
            "tool_error": True
        })

    try:
        response = httpx.post(
            f"{base_url}/api/compile",
            json={
                "st_code": code,
                "pou": "PLC_PRG",
                "backend": "codesys",
                "timeout": 900
            },
            timeout=930.0
        )
        response.raise_for_status()
        result = response.json()
        status = result.get("result")
        stage = result.get("stage")
        compilation_success = (
            result.get("ok") is True
            and result.get("result") == "PASS"
            and stage == "codesys"
        )
        valid_outcome = (
            (status in ("PASS", "COMPILE_FAIL") and stage == "codesys")
            or (status == "STATIC_FAIL" and stage == "lint")
        )

        errors = [
            error.get(
                "text",
                error.get("message", str(error))
            ) if isinstance(error, dict) else str(error)
            for error in result.get("errors", [])
        ]

        tool_error = not valid_outcome or bool(result.get("fatal"))

        if tool_error and not errors:
            errors = [
                "Compilation was not completed: "
                + str(result.get("result", stage))
            ]

        return json.dumps({
            "success": compilation_success,
            "errors": errors,
            "tool_error": tool_error,
            "stage": stage,
            "result": result.get("result"),
            "duration_s": result.get("duration_s", 0)
        })

    except (httpx.HTTPError, ValueError) as exc:
        return json.dumps({
            "success": False,
            "errors": [str(exc)],
            "tool_error": True
        })
