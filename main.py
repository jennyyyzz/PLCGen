import asyncio
import json
import time

from common import parse_args, build_model_client, load_settings, make_run_dir, save_run_summary, save_json
from agent import build_team, PLCHarness


def load_tasks() -> list[dict]:
    data = json.load(open("data/tasks.json"))
    tasks = []

    for difficulty, problems in data.items():
        for index, problem in enumerate(problems, start=1):
            tasks.append({
                "id": f"{difficulty}_{index:02d}",
                "difficulty": difficulty,
                "description": problem["en"]
            })

    return tasks

async def main():
    args = parse_args()
    settings = load_settings()
    model_name = settings["models"][args.model]
    print(f"Model option: {args.model}")
    print(f"Model: {model_name}")
    model_client = build_model_client(settings, args.model)
    generator = build_team(model_client)
    harness = PLCHarness(generator, max_repairs=3)
    tasks = load_tasks()
    out_dir = make_run_dir(f"{args.model} - model_name")
    overall_summary = []
    try:
        for task in tasks:
            task_id = task["id"]
            print(f"Running task {task_id} with {model_name}")
            task_dir = out_dir / f"task_{task_id}"
            task_dir.mkdir(parents=True, exist_ok=True)
            start_time = time.perf_counter()
            try:
                result = await harness.run(task=task["description"])
                execution_time = time.perf_counter() - start_time
                (task_dir / "code.st").write_text(result.get("code", ""), encoding="utf-8")
                summary = {
                    "task_id": task_id,
                    "difficulty": task["difficulty"],
                    "model_option": args.model,
                    "model": model_name,
                    "success": result["success"],
                    "reason": result["reason"],
                    "attempts": result.get("attempts"),
                    "execution_time": execution_time,
                    "prompt_tokens":result.get("prompt_tokens", 0),
                    "completion_tokens": result.get("completion_tokens", 0),
                    "history": result.get("history", [])
                }
            except Exception as e:
                execution_time = time.perf_counter() - start_time
                summary = {
                    "task_id": task_id,
                    "difficulty": task["difficulty"],
                    "model_option": args.model,
                    "model": model_name,
                    "success": False,
                    "reason": "execution_error",
                    "error": str(e),
                    "execution_time": execution_time,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                }
            save_json(task_dir / "result.json", summary)
            overall_summary.append(summary)
        total = len(overall_summary)
        succeeded = sum(1 for result in overall_summary if result["success"])
        execution_time = sum(result.get("execution_time", 0) for result in overall_summary)
        prompt_tokens = sum(result.get("prompt_tokens", 0) for result in overall_summary)
        completion_tokens = sum(result.get("completion_tokens", 0) for result in overall_summary)
        save_run_summary(
            out_dir,
            model_option=args.model,
            model=model_name,
            total=total,
            succeeded=succeeded,
            success_rate=((succeeded / total) if total else 0),
            execution_time=execution_time,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            results=overall_summary
        )
        print(f"Total tasks: {total}")
        print(f"Successful tasks: {succeeded}")
        print(f"Success rate: {(succeeded / total * 100 if total else 0):.2f}%")
        print(f"Execution time: {execution_time}")
        print(f"Prompt tokens: {prompt_tokens}")
        print(f"Completion tokens: {completion_tokens}")
        print(f"Total tokens: {(prompt_tokens + completion_tokens)}")
    finally:
        await model_client.close()


if __name__ == "__main__":
    asyncio.run(main())