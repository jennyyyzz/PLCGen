# -*- coding: utf-8 -*-
"""Mutation testing: can the case suite tell a correct implementation from a broken one?

Each file under codesys_service/bank/mutants/ is a reference implementation with
one realistic defect injected. If the suite still passes against it, the suite
cannot see that error.

Mutant naming is <short>_<change>.st, matching the task's short id (E01, M02).
The full task id is read from the case file.

Usage:
    python run_mutation.py
    python run_mutation.py --task E01
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SERVICE = REPO / "codesys_service"
BANK = SERVICE / "bank"

CASES = BANK / "cases_part4"
MUTANTS = BANK / "mutants"
OUT = HERE / "mutation_results.json"

PASS = re.compile(r"\[PASS")
BAD = re.compile(r"\[FAIL|\[ERROR|\[NOT_RUN")
TALLY = re.compile(r"测试通过：(\d+)/(\d+)")


def task_index():
    """short id -> (full id, case file)"""
    idx = {}
    for p in sorted(CASES.glob("*.testcase.json")):
        try:
            full = json.load(open(p)).get("task_id") or p.stem
        except Exception:
            full = p.stem
        short = full.split("_")[0]
        idx[short] = (full, p)
    return idx


def find_runner():
    env = os.environ.get("CODESYS_SERVICE")
    cands = [Path(env)] if env else []
    cands += [SERVICE, REPO / "service", REPO.parent / "codesys_service"]
    for c in cands:
        if (c / "run_tests.py").is_file():
            return c
    return None


def run(service, case, st):
    r = subprocess.run(
        [sys.executable, "run_tests.py", "--case", str(case),
         "--st", str(st), "--backend", "sim"],
        cwd=service, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    m = TALLY.search(out)
    total = int(m.group(2)) if m else 0
    if not total:
        total = len(PASS.findall(out)) + len(BAD.findall(out))
    return len(BAD.findall(out)), total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default=None, help="short id, e.g. E01")
    args = ap.parse_args()

    service = find_runner()
    if service is None:
        print("run_tests.py not found. Expected at %s" % (SERVICE / "run_tests.py"))
        return 2

    idx = task_index()
    files = sorted(MUTANTS.glob("*.st"))
    if not files:
        print("No mutants in %s" % MUTANTS)
        return 2

    rows = []
    for f in files:
        short = f.stem.split("_")[0]
        if short not in idx:
            print("  skipped %s: no case file for task %s" % (f.name, short))
            continue
        if args.task and short != args.task:
            continue
        full, case = idx[short]
        nbad, total = run(service, case, f)
        rows.append({
            "mutant": f.stem,
            "task": full,
            "short": short,
            "change": f.stem[len(short) + 1:].replace("_", " "),
            "detected": nbad > 0,
            "failing_cases": nbad,
            "total_cases": total,
        })

    if not rows:
        print("Nothing to run.")
        return 2

    rows.sort(key=lambda r: (r["short"], r["mutant"]))
    w = max(len(r["mutant"]) for r in rows)
    print("%-*s  %-20s %6s  %s" % (w, "mutant", "task", "fails", "verdict"))
    print("-" * (w + 46))
    for r in rows:
        v = ("DETECTED (%d/%d)" % (r["failing_cases"], r["total_cases"])
             if r["detected"] else "!!! SURVIVED")
        print("%-*s  %-20s %6d  %s" % (w, r["mutant"], r["task"], r["failing_cases"], v))
    killed = sum(1 for r in rows if r["detected"])
    print("-" * (w + 46))
    print("%d/%d mutants detected" % (killed, len(rows)))

    if not args.task:
        json.dump({"killed": killed, "total": len(rows), "mutants": rows},
                  open(OUT, "w"), ensure_ascii=False, indent=2)
        print("written %s" % OUT.name)
    return 0 if killed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
