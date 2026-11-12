# -*- coding: utf-8 -*-
"""Run the Part 4 case suite against both reference implementations.

Paths resolve relative to this file, so the script works from any clone. It
expects the layout shipped alongside it:

    <repo>/codesys_service/bank/cases_part4/<task>.testcase.json   Part 4 cases
    <repo>/codesys_service/bank/st_part4/<task>.st                 Part 4 reference
    <repo>/codesys_service/bank/st/<task>.st                       Part 2 reference
    <repo>/codesys_service/run_tests.py                            the harness
    <repo>/tools/verification/                                     this file

The Part 4 case files carry the full task id (E01_Filling) while the Part 2
regression cases under bank/cases/ use the short one (E01). Both existed before
this work, so each set keeps its own convention and nothing had to be renamed.

Usage:
    python run_suite.py                    # both implementations, all tasks
    python run_suite.py --impl part4       # one implementation
    python run_suite.py --task E01_Filling
    python run_suite.py --task E01         # short id also accepted
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent                       # tools/verification -> repo root
SERVICE = REPO / "codesys_service"
BANK = SERVICE / "bank"

CASES = BANK / "cases_part4"
IMPLS = {
    "part4": (BANK / "st_part4", "Part 4 reference"),
    "part2": (BANK / "st", "Part 2 reference"),
}

PASS = re.compile(r"\[PASS")
BAD = re.compile(r"\[FAIL|\[ERROR|\[NOT_RUN")
TALLY = re.compile(r"测试通过：(\d+)/(\d+)")


def find_runner():
    """Locate run_tests.py."""
    env = os.environ.get("CODESYS_SERVICE")
    cands = [Path(env)] if env else []
    cands += [SERVICE, REPO / "service", REPO.parent / "codesys_service"]
    for c in cands:
        if (c / "run_tests.py").is_file():
            return c
    return None


def task_list():
    """[(full_id, case_file)] sorted, plus a lookup accepting the short id too."""
    items = []
    for p in sorted(CASES.glob("*.testcase.json")):
        try:
            full = json.load(open(p)).get("task_id") or p.stem
        except Exception:
            full = p.stem
        items.append((full, p))
    return items


def run_one(service, case, st):
    r = subprocess.run(
        [sys.executable, "run_tests.py", "--case", str(case),
         "--st", str(st), "--backend", "sim"],
        cwd=service, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    m = TALLY.search(out)
    if m:
        return int(m.group(1)), int(m.group(2)), out
    npass = len(PASS.findall(out))
    nbad = len(BAD.findall(out))
    if npass + nbad:
        return npass, npass + nbad, out
    return 0, 0, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--impl", choices=list(IMPLS) + ["all"], default="all")
    ap.add_argument("--task", default=None, help="E01_Filling or E01")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    service = find_runner()
    if service is None:
        print("run_tests.py not found. Expected at %s" % (SERVICE / "run_tests.py"))
        print("Set CODESYS_SERVICE to override.")
        return 2

    items = task_list()
    if not items:
        print("No cases in %s" % CASES)
        return 2

    if args.task:
        sel = [t for t, _ in items
               if t == args.task or t.split("_")[0] == args.task]
        if not sel:
            print("Unknown task %s. Available: %s"
                  % (args.task, " ".join(t for t, _ in items)))
            return 2
        items = [(t, p) for t, p in items if t in sel]

    impls = list(IMPLS) if args.impl == "all" else [args.impl]
    summary = {}

    for impl in impls:
        folder, label = IMPLS[impl]
        total_p = total_n = 0
        failures, missing = [], []

        for task, case in items:
            st = folder / f"{task}.st"
            if not st.is_file():
                missing.append(task)
                continue
            p, n, out = run_one(service, case, st)
            total_p += p
            total_n += n
            if p != n:
                failures.append((task, p, n))
                if args.verbose:
                    for line in out.splitlines():
                        if BAD.search(line) or "预期" in line:
                            print("      " + line.strip())

        print("\n===== %s =====" % label)
        if missing:
            print("  no source for: %s" % " ".join(missing))
        for task, p, n in failures:
            print("  %-18s %d/%d" % (task, p, n))
        if not failures and not missing:
            print("  all cases pass")
        if total_n:
            print("  total %d/%d (%.1f%%)" % (total_p, total_n, 100.0 * total_p / total_n))
        summary[impl] = (total_p, total_n)

    print()
    for impl, (p, n) in summary.items():
        print("%-6s %d/%d" % (impl, p, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
