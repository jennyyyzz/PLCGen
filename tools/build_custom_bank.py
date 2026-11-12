"""Build the Custom Question Bank, LTL specs, test cases and reference ST."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from custom_defs import QUESTIONS

ROOT = Path(__file__).resolve().parent.parent
CUSTOM_BANK = ROOT / "codesys_service" / "bank" / "custom"
CASES = CUSTOM_BANK / "cases"
ST = CUSTOM_BANK / "st"
SPECS = ROOT / "specs" / "custom"
DATA = ROOT / "data"
DOCS = ROOT / "docs"

SOURCE = {
    "source_type": "independent_conception",
    "source_reference": "Original scenario created for this project; no external question text was copied.",
    "synthesis_process": (
        "Derived from standard industrial PLC control patterns (IEC 61131-3, "
        "safety interlocks, conveyor sequencing, batching and flame-proving "
        "sequences). The I/O list, timing and acceptance behaviour were written "
        "specifically for this assignment."
    ),
    "manual_modifications": (
        "Reduced to a single function block with deterministic scan-cycle "
        "behaviour; no vendor-specific libraries or hardware dependencies."
    ),
    "review_process": (
        "Internal design review against PLC realism: deterministic I/O, safe fail state, "
        "bounded timers, no unbounded loops, and testable behaviour at a 20 ms "
        "scan. Independent peer review is pending."
    ),
}


def interface_rows(q):
    rows = ["| Direction | Variable/Field | Data Type | Description |",
            "| --- | --- | --- | --- |"]
    for name, direction, typ, desc in q["interface"]:
        rows.append(f"| {direction.capitalize()} | `{name}` | `{typ}` | {desc} |")
    return "\n".join(rows)


def question_markdown(q):
    req = textwrap.dedent(q["requirements"]).strip()
    return (
        f"# {q['title']}\n\n"
        f"- **Difficulty:** {q['difficulty'].capitalize()} ({q['difficulty']})\n"
        f"- **POU:** `{q['pou']}`\n"
        f"- **Primary axis:** `{q['axis']}`\n\n"
        f"## Requirements\n\n{req}\n\n"
        f"## Interface Definition\n\n{interface_rows(q)}\n"
    )


def task_record(q):
    return {
        "id": q["id"],
        "pou": q["pou"],
        "title": q["title"],
        "difficulty": q["difficulty"],
        "primary_axis": q["axis"],
        "diversity_tags": q["tags"],
        "rationale": q["rationale"],
        "source": SOURCE,
        "interface": [
            {"name": n, "dir": d, "type": t, "desc": desc}
            for n, d, t, desc in q["interface"]
        ],
        "en": question_markdown(q),
    }


def spec_record(q):
    return {
        "task_id": q["id"],
        "title": q["title"],
        "pou": q["pou"],
        "abstraction": (
            "Discrete-time LTL over scan-cycle states. Numeric conditions are "
            "derived atoms; timer conditions use internal atoms mapped to the "
            "TON/TOF .Q flag of the reference implementation."
        ),
        "assumptions": [
            "The PLC scan is periodic (20 ms in the test cases).",
            "Inputs change only at scan boundaries.",
            "A timer atom becomes true after its configured delay has elapsed.",
            "The reference implementation is used only to validate the specification; it is not shown to the coding agent.",
        ],
        "atoms": [
            {"id": a, "kind": kind, "expression": expr, "meaning": meaning}
            for a, kind, expr, meaning in q["atoms"]
        ],
        "properties": [
            {"id": pid, "name": name, "formula": formula, "rationale": why}
            for pid, name, formula, why in q["specs"]
        ],
    }


def case_record(q):
    return {
        "task_id": q["id"],
        "title": q["title"],
        "pou": q["pou"],
        "scan_ms": 20,
        "primary_axis": q["axis"],
        "interface": [
            {"name": n, "dir": d, "type": t, "desc": desc}
            for n, d, t, desc in q["interface"]
        ],
        "cases": q["cases"],
    }


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    for d in (CASES, ST, SPECS, DATA, DOCS):
        d.mkdir(parents=True, exist_ok=True)

    grouped = {"easy": [], "medium": [], "hard": []}
    manifest_tasks = []

    for q in QUESTIONS:
        grouped[q["difficulty"]].append(task_record(q))
        write_json(SPECS / f"{q['id']}.ltl.json", spec_record(q))
        write_json(CASES / f"{q['id']}.testcase.json", case_record(q))
        (ST / f"{q['pou']}.st").write_text(q["st"].strip() + "\n", encoding="utf-8")
        manifest_tasks.append({
            "id": q["id"],
            "pou": q["pou"],
            "title": q["title"],
            "difficulty": q["difficulty"],
            "primary_axis": q["axis"],
            "question": f"data/custom_questions.json#{q['id']}",
            "spec": f"specs/custom/{q['id']}.ltl.json",
            "test_case": f"codesys_service/bank/custom/cases/{q['id']}.testcase.json",
            "reference_st": f"codesys_service/bank/custom/st/{q['pou']}.st",
        })

    write_json(DATA / "custom_questions.json", grouped)
    write_json(DATA / "custom_manifest.json", {
        "version": "1.0",
        "naming": {
            "public": "FB_Q01-FB_Q20",
            "custom": "FB_C01-FB_C12",
        },
        "tasks": manifest_tasks,
    })

    # Dataset record
    rec = [
        "# Custom Question Bank dataset record",
        "",
        "This document records the source, adaptation, rationality and diversity of the 12 custom questions.",
        "",
        "## Naming",
        "",
        "- Public questions: `FB_Q01`-`FB_Q20` (provided public question bank).",
        "- Custom questions: `FB_C01`-`FB_C12` (this dataset).",
        "- `FB` = Function Block (IEC 61131-3 POU); `Q` = public question bank; `C` = custom.",
        "",
        "## Source and adaptation",
        "",
        "All 12 questions are original scenarios written for this project. No external question text was copied. "
        "Each scenario is a synthesis of common industrial PLC patterns and was manually reduced to a single "
        "function block with deterministic scan-cycle behaviour.",
        "",
        "| ID | Title | Difficulty | Primary axis | Source type |",
        "| --- | --- | --- | --- | --- |",
    ]
    for q in QUESTIONS:
        rec.append(f"| {q['id']} | {q['title']} | {q['difficulty']} | {q['axis']} | independent conception |")

    rec += [
        "",
        "## Rationality of the questions",
        "",
        "| ID | Why the scenario is realistic |",
        "| --- | --- |",
    ]
    for q in QUESTIONS:
        rec.append(f"| {q['id']} | {q['rationale']} |")

    rec += [
        "",
        "## Diversity measurement",
        "",
        "| Axis | Questions | Count |",
        "| --- | --- | --- |",
    ]
    for axis in ("sorting_filtering", "cyclic_timing", "safety_logic"):
        ids = [q["id"] for q in QUESTIONS if q["axis"] == axis]
        rec.append(f"| {axis} | {', '.join(ids)} | {len(ids)} |")
    rec += [
        "",
        "Difficulty distribution:",
        "",
        "| Difficulty | Questions | Count |",
        "| --- | --- | --- |",
    ]
    for diff in ("easy", "medium", "hard"):
        ids = [q["id"] for q in QUESTIONS if q["difficulty"] == diff]
        rec.append(f"| {diff} | {', '.join(ids)} | {len(ids)} |")
    rec += [
        "",
        "Additional diversity: edge detection, timers, counters, analog thresholds, state machines, "
        "safety interlocks, jam detection and flame proving. The public bank mainly covers state machines "
        "and alarm/debounce logic, so this set deliberately emphasises sorting/filtering, cyclic timing "
        "and safety logic.",
        "",
        "## Review process",
        "",
        "Each question was checked for: deterministic I/O; a safe fail state; bounded timers; no unbounded "
        "loops; and testability in a 20 ms scan. Independent peer review is still pending.",
    ]
    (DOCS / "custom_dataset_record.md").write_text("\n".join(rec) + "\n", encoding="utf-8")

    # Spec summary
    spec_lines = [
        "# Custom Question Bank LTL specification summary",
        "",
        "Each question has three properties: a safety/invariant property, a response/sequence property and a "
        "recovery/termination property. Atoms are defined in the corresponding JSON file under `specs/custom/`.",
        "",
        "| ID | POU | Properties |",
        "| --- | --- | --- |",
    ]
    for q in QUESTIONS:
        props = "; ".join(f"{pid}: {name}" for pid, name, _, _ in q["specs"])
        spec_lines.append(f"| {q['id']} | `{q['pou']}` | {props} |")
    spec_lines += [
        "",
        "## Abstraction notes",
        "",
        "- LTL is evaluated over discrete scan-cycle states.",
        "- Numeric thresholds are represented as derived atoms (for example `HeightInRange`).",
        "- Timer conditions are represented as internal atoms mapped to the reference implementation's `.Q` flag.",
        "- The reference ST is only a validation artifact and must not be given to the coding agent.",
    ]
    (DOCS / "custom_specs.md").write_text("\n".join(spec_lines) + "\n", encoding="utf-8")

    # Test summary
    test_lines = [
        "# Custom Question Bank test case summary",
        "",
        "Test cases follow the repository format used by `codesys_service/run_tests.py`.",
        "",
        "| ID | POU | Cases | Steps |",
        "| --- | --- | --- | --- |",
    ]
    for q in QUESTIONS:
        steps = sum(len(c["steps"]) for c in q["cases"])
        test_lines.append(f"| {q['id']} | `{q['pou']}` | {len(q['cases'])} | {steps} |")
    test_lines += [
        "",
        "## How to run",
        "",
        "```bash",
        "cd codesys_service",
        "python run_tests.py --case bank/custom/cases/C01.testcase.json --st bank/custom/st/FB_C01.st --backend dry",
        "python run_tests.py --case bank/custom/cases/C01.testcase.json --st bank/custom/st/FB_C01.st --backend sim",
        "```",
        "",
        "The `dry` backend checks the case structure and cross-checks variable names/types against the ST. "
        "The `sim` backend executes the reference ST scan by scan.",
    ]
    (DOCS / "custom_tests.md").write_text("\n".join(test_lines) + "\n", encoding="utf-8")

    # Specs README
    (SPECS / "README.md").write_text(
        "# Custom Question Bank LTL specs\n\n"
        "One JSON file per question, `C01.ltl.json` ... `C12.ltl.json`.\n\n"
        "Each file contains: `task_id`, `title`, `pou`, `atoms`, `properties` and the abstraction assumptions.\n"
        "Formulas use standard LTL operators: `G`, `F`, `X`, `U`, `∧`, `∨`, `¬`, `→`.\n",
        encoding="utf-8",
    )

    print(f"Built {len(QUESTIONS)} questions")
    print("Wrote data/custom_questions.json and data/custom_manifest.json")
    print("Wrote specs, test cases, reference ST and docs")


if __name__ == "__main__":
    main()
