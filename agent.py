import json

from autogen_agentchat.agents import AssistantAgent
from autogen_core import CancellationToken

from tools import compile_code


class PLCHarness:
    def __init__(self, generator, max_repairs):
        self.generator = generator
        self.max_repairs = max_repairs

    async def run(self, task):
        await self.generator.on_reset(CancellationToken())
        code = ""
        feedback = None
        history = []
        prompt_tokens = 0
        completion_tokens = 0
        success = False
        reason = "max_attempts_reached"
        previous_codes = set()
        for i in range(self.max_repairs + 1):
            if i == 0:
                prompt = task
            else:
                prompt = (
                    "The previous ST code FAILED compilation.\n"
                    "You must fix the following compiler errors:\n"
                    f"{feedback}\n\n"
                    "Review your previous implementation carefully. "
                    "Correct the errors while preserving the task requirements. "
                    "Return the COMPLETE corrected ST code, not an explanation."
                )
            generation = await self.generator.run(task=prompt)
            p, c = token_usage(generation.messages)
            prompt_tokens += p
            completion_tokens += c
            print(f"\n--- Task generation, attempt {i + 1} ---")
            print("Stop reason:", generation.stop_reason)

            for message in generation.messages:
                print("Message type:", type(message).__name__)
                print("Content:", repr(message.content)[:500])
                print("Token usage:", getattr(message, "models_usage", None))

            code = str(generation.messages[-1].content).strip()
            print("Code length:", len(code))
            if not code or code in previous_codes:
                reason = "empty_or_repeated_code"
                break
            previous_codes.add(code)
            result = json.loads(compile_code(code))
            history.append({
                "attempt": i + 1,
                "compiled": result["success"],
                "errors": result["errors"],
                "stage": result.get("stage"),
                "result": result.get("result")
            })
            if result.get("tool_error"):
                reason = "compile_tool_error"
                break
            if result["success"]:
                success = True
                reason = "compiled"
                break
            feedback = "\n".join(str(error) for error in result["errors"])
            if not feedback:
                reason = "missing_compiler_feedback"
                break
        return {
            "success": success,
            "reason": reason,
            "code": code,
            "attempts": len(history),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "history": history
        }


def build_team(model_client):
    generator = AssistantAgent(
        "CodeGeneratorAgent",
        model_client=model_client,
        description="Generates ST code",
        system_message=(
            "You are the ST Code Generator Agent and you are a PLC "
            "programmer. Generate complete ST code compatible with "
            "CODESYS. Follow the requirements exactly. If compilation "
            "feedback is provided, repair the code while preserving the "
            "intended behavior. Return ONLY the complete ST program. "
            "Do not include Markdown, explanations, or commentary. "
            "Keep the solution concise and avoid unnecessary complexity."
            )
    )
    return generator

def token_usage(messages):
    prompt_tokens = 0
    completion_tokens = 0
    for message in messages:
        usage = getattr(message, "models_usage", None)
        if usage is not None:
            prompt_tokens += usage.prompt_tokens
            completion_tokens += usage.completion_tokens
    return prompt_tokens, completion_tokens