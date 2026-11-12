#!/usr/bin/env python3
"""Validate the Custom Question Bank, LTL specs and test-case metadata."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SPECS = ROOT / "specs" / "custom"
CASES = ROOT / "codesys_service" / "bank" / "custom" / "cases"
ST = ROOT / "codesys_service" / "bank" / "custom" / "st"

VALID_TYPES = {"BOOL", "INT", "DINT", "REAL", "LREAL", "WORD", "DWORD", "USINT", "UINT", "UDINT"}
LTL_WORDS = {"G", "F", "X", "U", "W", "R", "TRUE", "FALSE"}
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class Validator:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, msg: str):
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    def check_questions(self) -> dict[str, dict]:
        path = DATA / "custom_questions.json"
        if not path.is_file():
            self.err(f"missing {path}")
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        if set(raw) != {"easy", "medium", "hard"}:
            self.err("custom_questions.json must have exactly easy/medium/hard keys")
        tasks = {}
        expected_counts = {"easy": 3, "medium": 5, "hard": 4}
        for diff, items in raw.items():
            if len(items) != expected_counts.get(diff):
                self.err(f"{diff}: expected {expected_counts.get(diff)} questions, got {len(items)}")
            for item in items:
                qid = item.get("id")
                if not qid:
                    self.err(f"{diff}: question without id")
                    continue
                if qid in tasks:
                    self.err(f"duplicate question id {qid}")
                tasks[qid] = item
                for key in ("pou", "title", "difficulty", "primary_axis", "diversity_tags",
                            "rationale", "source", "interface", "en"):
                    if key not in item or not item[key]:
                        self.err(f"{qid}: missing field {key}")
                if item.get("difficulty") != diff:
                    self.err(f"{qid}: difficulty field {item.get('difficulty')} does not match group {diff}")
                if not re.fullmatch(r"C\d{2}", qid):
                    self.err(f"{qid}: id must match Cxx")
                if item.get("pou") != f"FB_{qid}":
                    self.err(f"{qid}: POU must be FB_{qid}")
                names = []
                for v in item.get("interface", []):
                    if set(v) != {"name", "dir", "type", "desc"}:
                        self.err(f"{qid}: interface entry must have name/dir/type/desc")
                        continue
                    if v["dir"] not in ("input", "output"):
                        self.err(f"{qid}/{v['name']}: invalid direction {v['dir']}")
                    if v["type"] not in VALID_TYPES:
                        self.err(f"{qid}/{v['name']}: invalid type {v['type']}")
                    names.append(v["name"])
                if len(names) != len(set(names)):
                    self.err(f"{qid}: duplicate interface names")
        expected_ids = {f"C{i:02d}" for i in range(1, 13)}
        if set(tasks) != expected_ids:
            self.err(f"question IDs mismatch: expected {sorted(expected_ids)}, got {sorted(tasks)}")
        return tasks

    def check_specs(self, tasks: dict[str, dict]):
        for qid, task in sorted(tasks.items()):
            path = SPECS / f"{qid}.ltl.json"
            if not path.is_file():
                self.err(f"{qid}: missing spec {path.name}")
                continue
            spec = json.loads(path.read_text(encoding="utf-8"))
            if spec.get("task_id") != qid:
                self.err(f"{qid}: spec task_id mismatch")
            if spec.get("pou") != task["pou"]:
                self.err(f"{qid}: spec POU mismatch")
            atoms = spec.get("atoms") or []
            atom_ids = [a.get("id") for a in atoms]
            if len(atom_ids) != len(set(atom_ids)):
                self.err(f"{qid}: duplicate atom ids")
            if any(not a.get("id") for a in atoms):
                self.err(f"{qid}: atom without id")
            props = spec.get("properties") or []
            if len(props) < 3:
                self.err(f"{qid}: expected at least 3 LTL properties, got {len(props)}")
            prop_ids = [p.get("id") for p in props]
            if len(prop_ids) != len(set(prop_ids)):
                self.err(f"{qid}: duplicate property ids")
            for p in props:
                formula = p.get("formula", "")
                if not formula:
                    self.err(f"{qid}/{p.get('id')}: empty formula")
                    continue
                if formula.count("(") != formula.count(")"):
                    self.err(f"{qid}/{p.get('id')}: unbalanced parentheses")
                used = set(TOKEN_RE.findall(formula))
                unknown = used - set(atom_ids) - LTL_WORDS
                if unknown:
                    self.err(f"{qid}/{p.get('id')}: unknown symbols in formula: {sorted(unknown)}")
                if not any(op in used for op in ("G", "F", "X", "U", "W", "R")):
                    self.warn(f"{qid}/{p.get('id')}: formula has no temporal operator")

    def check_cases(self, tasks: dict[str, dict]):
        for qid, task in sorted(tasks.items()):
            path = CASES / f"{qid}.testcase.json"
            if not path.is_file():
                self.err(f"{qid}: missing test case {path.name}")
                continue
            case = json.loads(path.read_text(encoding="utf-8"))
            if case.get("task_id") != qid:
                self.err(f"{qid}: test task_id mismatch")
            if case.get("pou") != task["pou"]:
                self.err(f"{qid}: test POU mismatch")
            if case.get("scan_ms") != 20:
                self.err(f"{qid}: scan_ms should be 20")
            q_iface = {v["name"]: (v["dir"], v["type"]) for v in task["interface"]}
            c_iface = {v["name"]: (v["dir"], v["type"]) for v in case.get("interface", [])}
            if q_iface != c_iface:
                self.err(f"{qid}: test interface does not match question interface")
            cases = case.get("cases") or []
            if not cases:
                self.err(f"{qid}: no test cases")
            cids = [c.get("id") for c in cases]
            if len(cids) != len(set(cids)):
                self.err(f"{qid}: duplicate test case ids")
            for c in cases:
                for key in ("id", "name", "coverage", "initial_state", "steps"):
                    if not c.get(key):
                        self.err(f"{qid}/{c.get('id')}: missing {key}")
                for s in c.get("steps", []):
                    if "cycle" not in s:
                        self.err(f"{qid}/{c.get('id')}: step without cycle")
                    for grp in ("inputs", "expect"):
                        for name in (s.get(grp) or {}):
                            if name not in q_iface:
                                self.err(f"{qid}/{c.get('id')}: {grp} variable {name} not in interface")
                    if not s.get("expect"):
                        self.err(f"{qid}/{c.get('id')}: step without expect")

    def check_st(self, tasks: dict[str, dict]):
        for qid, task in sorted(tasks.items()):
            path = ST / f"{task['pou']}.st"
            if not path.is_file():
                self.err(f"{qid}: missing reference ST {path.name}")
                continue
            text = path.read_text(encoding="utf-8")
            for v in task["interface"]:
                pattern = re.compile(rf"\b{re.escape(v['name'])}\s*:\s*{re.escape(v['type'])}\b", re.IGNORECASE)
                if not pattern.search(text):
                    self.err(f"{qid}: {v['name']} : {v['type']} not declared in ST")
            if task["pou"] not in text:
                self.err(f"{qid}: POU {task['pou']} not found in ST")

    def check_manifest(self, tasks: dict[str, dict]):
        path = DATA / "custom_manifest.json"
        if not path.is_file():
            self.err(f"missing {path}")
            return
        manifest = json.loads(path.read_text(encoding="utf-8"))
        entries = {e.get("id"): e for e in manifest.get("tasks", [])}
        if set(entries) != set(tasks):
            self.err("manifest task IDs do not match custom_questions.json")
        for qid, e in sorted(entries.items()):
            for key in ("pou", "spec", "test_case", "reference_st"):
                if not e.get(key):
                    self.err(f"manifest {qid}: missing {key}")
            for key in ("spec", "test_case", "reference_st"):
                rel = e.get(key)
                if rel and not (ROOT / rel).is_file():
                    self.err(f"manifest {qid}: path does not exist: {rel}")


    def check_internal_refs(self):
        role_pattern = re.compile(r"experiment owner|teammate|work division|\bRol\s+[1-5]\b|\brole\s+[1-5]\b", re.IGNORECASE)
        part_pattern = re.compile(r"\bPart\s+[1-5]\b")
        roots = [DATA, SPECS, CASES, ST, ROOT / "docs", ROOT / "report"]
        for root in roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if path.is_dir() or path.suffix not in {".json", ".md", ".tex", ".py"}:
                    continue
                if path.name.endswith(".docx"):
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                if role_pattern.search(text) or part_pattern.search(text):
                    self.err(f"internal role reference in deliverable file: {path.relative_to(ROOT)}")

    def run(self) -> int:
        tasks = self.check_questions()
        if tasks:
            self.check_specs(tasks)
            self.check_cases(tasks)
            self.check_st(tasks)
            self.check_manifest(tasks)
        self.check_internal_refs()
        print(f"Questions : {len(tasks)}")
        print(f"Errors    : {len(self.errors)}")
        print(f"Warnings  : {len(self.warnings)}")
        for w in self.warnings:
            print(f"  WARN  {w}")
        for e in self.errors:
            print(f"  ERROR {e}")
        if not self.errors:
            print("VALIDATION PASSED")
            return 0
        return 1


if __name__ == "__main__":
    sys.exit(Validator().run())
