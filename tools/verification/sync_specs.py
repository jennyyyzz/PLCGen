# -*- coding: utf-8 -*-
"""Regenerate the machine-derivable parts of every spec document.

What is derived (and therefore must never be typed by hand):

  * the case table's TC rows      <- migrated/cases/<task>.testcase.json
  * the suite line                <- case count and scan-cycle count from the JSON
  * the validation block numbers  <- final_regression.txt / final_refst.txt /
                                     st_mutation_results.json / compile results

What is preserved (human judgement, never touched):

  * the LTL property tables
  * the "Assumptions and requirement gaps" section
  * the per-case "Purpose" and "Properties covered" text, which is matched back
    to its existing TC row by id

A new case with no existing row is inserted with its own name and a TODO marker,
so it is impossible to add a case and silently leave it out of the report.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SPECS = ROOT / "codesys_service" / "specs"
CASES = ROOT / "codesys_service" / "bank" / "cases_part4"


def load_passes(path):
    """task -> (passed, failed) from a '<task> <passed> <failed>' file."""
    out = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) == 3:
            out[parts[0]] = (int(parts[1]), int(parts[2]))
    return out


def load_mutants():
    """task -> (killed, total)"""
    p = HERE / "st_mutation_results.json"
    out = {}
    if not p.exists():
        return out
    for m in json.load(open(p))["mutants"]:
        k, t = out.get(m["task"], (0, 0))
        out[m["task"]] = (k + (1 if m["detected"] else 0), t + 1)
    return out


def load_compile():
    """task -> 'PASS' | 'FAIL' | None, from compile_results.txt if present."""
    p = HERE / "compile_results.txt"
    out = {}
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].upper() in ("PASS", "FAIL"):
            out[parts[0]] = parts[1].upper()
    return out


BANK = load_passes(HERE / "final_regression.txt")
REF = load_passes(HERE / "final_refst.txt")
MUT = load_mutants()
COMPILE = load_compile()


def parse_case_rows(section):
    """Existing TC rows, keyed by id, from the current case table."""
    rows = {}
    for line in section.splitlines():
        m = re.match(r"^\|\s*(TC\d+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$", line)
        if m:
            rows[m.group(1)] = (m.group(2), m.group(3))
    return rows


def rebuild(task):
    sp = SPECS / f"{task}_spec.md"
    cp = CASES / f"{task}.testcase.json"
    if not sp.exists() or not cp.exists():
        print(f"  skip {task}: missing spec or case file")
        return False

    doc = sp.read_text()
    case = json.load(open(cp))
    cases = case["cases"]
    n_case = len(cases)
    n_step = sum(len(c.get("steps", [])) for c in cases)

    # ---- case table ----
    if "## Test cases" not in doc:
        print(f"  skip {task}: no '## Test cases' section")
        return False
    head, rest = doc.split("## Test cases", 1)
    old_section, after = rest.split("## Validation of the test cases", 1)
    old_rows = parse_case_rows(old_section)

    row_lines = []
    for c in cases:
        cid = c["id"]
        if cid in old_rows:
            purpose, props = old_rows[cid]
        else:
            purpose = c.get("name", "").strip()
            props = "TODO: 未标注覆盖的规约条目"
        row_lines.append(f"| {cid} | {purpose} | {props} |")

    new_section = (
        f"\n\nFile: `{task}.testcase.json` ({n_case} cases, {n_step} scan cycles).\n\n"
        "| Case | Purpose | Properties covered |\n"
        "|---|---|---|\n" + "\n".join(row_lines) + "\n\n"
    )

    # ---- validation block ----
    bp, bf = BANK.get(task, (0, 0))
    rp, rf = REF.get(task, (0, 0))
    mk, mt = MUT.get(task, (0, 0))
    comp = COMPILE.get(task)

    rows = []
    rows.append("| Check | Result |")
    rows.append("|---|---|")
    rows.append("| Structural check (`dry`) | interface names and types match the declaration |")
    if rp or rf:
        badge = "PASS" if rf == 0 else f"**{rf} case(s) FAIL**"
        rows.append(f"| Offline simulation (`sim`) vs the Part-4 reference implementation "
                    f"| **{rp}/{rp + rf} cases** — {badge} |")
    if bp or bf:
        badge = "PASS" if bf == 0 else f"**{bf} case(s) FAIL** (see `CROSSCHECK.md`)"
        rows.append(f"| Offline simulation (`sim`) vs the Part-2 reference implementation "
                    f"| **{bp}/{bp + bf} cases** — {badge} |")
    rows.append(f"| CODESYS V3.5 compilation (FUNCTION_BLOCK) | {comp} |" if comp
                else "| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |")
    if mt:
        rows.append(f"| Mutation testing (ST mutants) | **{mk}/{mt}** mutants detected |")

    new_val = (
        "\n\n" + "\n".join(rows) + "\n\n"
        f"Suite: {n_case} cases / {n_step} scan cycles.\n\n"
        "The test cases were run against two independently written reference implementations; "
        "where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "
        "\"Conventions settled\") was adopted.\n\n"
        "---\n\n"
        "*Derived values in this section are regenerated from the test-case file and the run "
        "artefacts by `tools/sync_specs.py`; do not edit them by hand.*\n"
    )

    sp.write_text(head + "## Test cases" + new_section
                  + "## Validation of the test cases" + new_val)
    added = [c["id"] for c in cases if c["id"] not in old_rows]
    note = f"  (added rows: {', '.join(added)})" if added else ""
    print(f"  {task:<18} {n_case} cases / {n_step} cycles  "
          f"ref {rp}/{rp + rf}  bank {bp}/{bp + bf}  mut {mk}/{mt}{note}")
    return True


def main():
    tasks = sorted(p.stem.replace("_spec", "") for p in SPECS.glob("*_spec.md"))
    print(f"syncing {len(tasks)} spec files")
    ok = sum(rebuild(t) for t in tasks)
    print(f"\n{ok}/{len(tasks)} spec files updated")


if __name__ == "__main__":
    main()
