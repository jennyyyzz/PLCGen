#!/usr/bin/env python3
"""Run lint, dry and sim validation for the custom assets and write a report."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICE = ROOT / "codesys_service"
CASES = SERVICE / "bank" / "custom" / "cases"
ST = SERVICE / "bank" / "custom" / "st"
OUT = ROOT / "results" / "custom"
DATA = ROOT / "data"


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = json.loads((DATA / "custom_manifest.json").read_text(encoding="utf-8"))["tasks"]

    lint = run([sys.executable, "st_lint.py", "bank/custom/st/"], SERVICE)
    (OUT / "lint.txt").write_text(lint.stdout + lint.stderr, encoding="utf-8")

    report = {
        "lint": {"returncode": lint.returncode, "passed": lint.returncode == 0},
        "tasks": [],
        "totals": {"cases": 0, "passed": 0},
    }

    for task in tasks:
        qid = task["id"]
        case = CASES / f"{qid}.testcase.json"
        st = ST / f"{task['pou']}.st"
        dry_out = OUT / f"{qid}.dry.json"
        sim_out = OUT / f"{qid}.sim.json"
        dry = run([sys.executable, "run_tests.py", "--case", str(case), "--st", str(st),
                   "--backend", "dry", "--out", str(dry_out)], SERVICE)
        sim = run([sys.executable, "run_tests.py", "--case", str(case), "--st", str(st),
                   "--backend", "sim", "--out", str(sim_out)], SERVICE)
        dry_json = json.loads(dry_out.read_text(encoding="utf-8")) if dry_out.is_file() else {}
        sim_json = json.loads(sim_out.read_text(encoding="utf-8")) if sim_out.is_file() else {}
        cases = sim_json.get("total", 0)
        passed = sim_json.get("pass", 0)
        report["tasks"].append({
            "id": qid,
            "pou": task["pou"],
            "title": task["title"],
            "dry_returncode": dry.returncode,
            "dry_valid": dry_json.get("valid", False) if "valid" in dry_json else dry.returncode == 0,
            "sim_returncode": sim.returncode,
            "cases": cases,
            "cases_passed": passed,
            "cases_detail": [
                {"id": c.get("id"), "name": c.get("name"), "result": c.get("result")}
                for c in (sim_json.get("results") or [{}])[0].get("cases", [])
                if "results" in sim_json
            ],
        })
        report["totals"]["cases"] += cases
        report["totals"]["passed"] += passed

    report["totals"]["all_sim_pass"] = report["totals"]["cases"] == report["totals"]["passed"]
    report["dry_all_valid"] = all(t["dry_valid"] for t in report["tasks"])
    (OUT / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Custom Question Bank validation results",
        "",
        f"- Lint: {'PASS' if report['lint']['passed'] else 'FAIL'} (12 reference ST files)",
        f"- Dry structure checks: {'PASS' if report['dry_all_valid'] else 'FAIL'} (12/12 test-case files)",
        f"- Sim execution: {report['totals']['passed']}/{report['totals']['cases']} test cases passed",
        "",
        "| ID | POU | Dry | Sim cases |",
        "| --- | --- | --- | --- |",
    ]
    for t in report["tasks"]:
        lines.append(f"| {t['id']} | `{t['pou']}` | {'VALID' if t['dry_valid'] else 'INVALID'} | {t['cases_passed']}/{t['cases']} |")
    (ROOT / "docs" / "custom_validation_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if report["lint"]["passed"] and report["dry_all_valid"] and report["totals"]["all_sim_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
