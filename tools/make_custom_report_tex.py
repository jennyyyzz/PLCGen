#!/usr/bin/env python3
"""Generate English LaTeX fragments for the Custom Question Bank report section."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "report"
DATA = ROOT / "data"
VAL = json.loads((ROOT / "results" / "custom" / "validation.json").read_text(encoding="utf-8"))
TASKS = json.loads((DATA / "custom_questions.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((DATA / "custom_manifest.json").read_text(encoding="utf-8"))
VAL_BY_ID = {t["id"]: t for t in VAL["tasks"]}

AXIS_LABEL = {
    "sorting_filtering": "Sorting / filtering",
    "cyclic_timing": "Cyclic timing",
    "safety_logic": "Safety logic",
}


def esc(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in str(text))


def path_tex(text: str) -> str:
    return r"\texttt{" + esc(text) + "}"


def formula_tex(formula: str) -> str:
    out = formula
    out = out.replace("∧", r" \wedge ").replace("∨", r" \vee ")
    out = out.replace("¬", r" \neg ").replace("→", r" \rightarrow ")
    out = out.replace("TRUE", r"\mathrm{TRUE}").replace("FALSE", r"\mathrm{FALSE}")
    out = re.sub(r"\b(G|F|X|U|W|R)\b", lambda m: rf"\mathbf{{{m.group(1)}}}", out)
    out = re.sub(r"\s+", " ", out).strip()
    return "$" + out + "$"


def question_rows():
    rows = []
    for diff in ("easy", "medium", "hard"):
        for q in TASKS[diff]:
            n_in = sum(1 for v in q["interface"] if v["dir"] == "input")
            n_out = sum(1 for v in q["interface"] if v["dir"] == "output")
            spec = json.loads((ROOT / "specs" / "custom" / f"{q['id']}.ltl.json").read_text(encoding="utf-8"))
            case = json.loads((ROOT / "codesys_service" / "bank" / "custom" / "cases" / f"{q['id']}.testcase.json").read_text(encoding="utf-8"))
            rows.append((q, n_in, n_out, len(spec["properties"]), len(case["cases"])))
    return rows


def build_body():
    rows = question_rows()
    lines = [
        "% Custom Question Bank dataset section.",
        "% Intended to be included from the main report with \\input{report/custom_question_bank}.",
        "% This fragment deliberately contains no preamble and no package imports.",
        "",
        r"\section{Custom Question Bank}",
        r"\label{sec:custom_question_bank}",
        "",
        r"\subsection{Overview and Naming}",
        "The Custom Question Bank contains 12 original PLC programming tasks. "
        "They are named \\texttt{C01}--\\texttt{C12} and implemented as function blocks "
        "\\texttt{FB\\_C01}--\\texttt{FB\\_C12}. The public question bank uses "
        "\\texttt{FB\\_Q01}--\\texttt{FB\\_Q20}; the \\texttt{C} prefix therefore keeps the "
        "custom blocks separate from the public ones.",
        "",
        "The 12 tasks are deliberately balanced across three axes: sorting/filtering, "
        "cyclic timing and safety logic. The public bank is dominated by state machines "
        "and alarm/debounce behaviour, so these axes add complementary coverage. "
        "Each task is stored in \\texttt{data/custom\\_questions.json} with its interface, "
        "difficulty, rationale, source record, LTL specification and test cases.",
        "",
        r"\begin{table}[htbp]",
        r"\centering",
        r"\small",
        r"\caption{Custom Question Bank at a glance. I/O counts include all function-block inputs and outputs.}",
        r"\label{tab:custom_overview}",
        r"\begin{tabular}{|l|l|p{0.24\textwidth}|l|p{0.14\textwidth}|c|c|c|}",
        r"\hline",
        r"ID & POU & Title & Difficulty & Axis & I/O & Props. & Tests \\",
        r"\hline",
    ]
    for q, n_in, n_out, n_props, n_cases in rows:
        lines.append(
            f"{q['id']} & \\texttt{{{esc(q['pou'])}}} & {esc(q['title'])} & "
            f"{q['difficulty'].capitalize()} & {AXIS_LABEL[q['primary_axis']]} & "
            f"{n_in}/{n_out} & {n_props} & {n_cases} \\\\"
        )
    lines += [
        r"\hline",
        r"\end{tabular}",
        r"\end{table}",
        "",
        r"\subsection{Source and Adaptation Record}",
        "All tasks are original scenarios written for this project; no external question text "
        "was copied. The scenarios were synthesised from standard industrial PLC control "
        "patterns (IEC 61131-3 function blocks, safety interlocks, conveyor sequencing, "
        "batching and flame-proving sequences). The table below records the source type of "
        "each scenario.",
        "",
        r"\begin{table}[htbp]",
        r"\centering",
        r"\small",
        r"\caption{Source record. All 12 scenarios use independent conception.}",
        r"\label{tab:custom_sources}",
        r"\begin{tabular}{|l|p{0.58\textwidth}|p{0.22\textwidth}|}",
        r"\hline",
        r"ID & Scenario & Source type \\",
        r"\hline",
    ]
    for q, *_ in rows:
        lines.append(f"{q['id']} & {esc(q['title'])} & Independent conception \\\\")
    lines += [
        r"\hline",
        r"\end{tabular}",
        r"\end{table}",
        "",
        "The adaptation procedure is common to all tasks. Each scenario was manually reduced "
        "to a single function block with deterministic scan-cycle behaviour, bounded timers "
        "and no vendor-specific libraries. Each task received an internal review against PLC "
        "realism; independent peer review is still pending.",
        "",
        r"\subsection{Rationality of the Scenarios}",
        "Each scenario reflects a recognisable PLC function. The list below records why the "
        "task is realistic and which control problem it exercises.",
        "",
        r"\begin{description}",
    ]
    for q, *_ in rows:
        lines.append(f"\\item[{q['id']} --- {esc(q['title'])}] {esc(q['rationale'])}")
    lines += [
        r"\end{description}",
        "",
        r"\subsection{Diversity Measurement}",
        "Diversity is measured along two dimensions: the primary control axis and the "
        "difficulty level. Each primary axis contains four questions, and the difficulty "
        "distribution is 3 easy, 5 medium and 4 hard.",
        "",
        r"\begin{table}[htbp]",
        r"\centering",
        r"\small",
        r"\caption{Diversity by primary control axis.}",
        r"\label{tab:custom_axes}",
        r"\begin{tabular}{|l|l|c|}",
        r"\hline",
        r"Axis & Questions & Count \\",
        r"\hline",
    ]
    for axis, label in AXIS_LABEL.items():
        ids = [q["id"] for diff in TASKS for q in TASKS[diff] if q["primary_axis"] == axis]
        lines.append(f"{label} & {', '.join(ids)} & {len(ids)} \\\\")
    lines += [
        r"\hline",
        r"\end{tabular}",
        r"\end{table}",
        "",
        r"\begin{table}[htbp]",
        r"\centering",
        r"\small",
        r"\caption{Difficulty distribution.}",
        r"\label{tab:custom_difficulty}",
        r"\begin{tabular}{|l|l|c|}",
        r"\hline",
        r"Difficulty & Questions & Count \\",
        r"\hline",
    ]
    for diff in ("easy", "medium", "hard"):
        ids = [q["id"] for q in TASKS[diff]]
        lines.append(f"{diff.capitalize()} & {', '.join(ids)} & {len(ids)} \\\\")
    lines += [
        r"\hline",
        r"\end{tabular}",
        r"\end{table}",
        "",
        "Additional diversity comes from the required skills: edge detection, timers, "
        "counters, analog thresholds, state machines, safety interlocks, jam detection and "
        "flame proving. The complete per-question tags are stored in the dataset JSON.",
        "",
        r"\subsection{Formal Specifications}",
        "Every question is specified in linear temporal logic (LTL). Each question has "
        "three properties: a safety or invariant property, a response or sequencing property, "
        "and a recovery or termination property. Numeric conditions are represented as "
        "derived atoms, and timer conditions are represented by internal atoms mapped to "
        "the reference implementation's timer output. The full set of 36 formulas is given "
        r"in Appendix~\ref{app:custom_ltl}.",
        "",
        "The specifications assume a periodic scan (20\\,ms in the test cases) and that inputs "
        "change only at scan boundaries. The reference ST implementation is used only to "
        "validate the specifications and test cases; it is not shown to the coding agent.",
        "",
        r"\subsection{Test Cases and Validation}",
        "Test cases follow the repository format used by \\texttt{codesys\\_service/run\\_tests.py}. "
        "Each question has a JSON test-case file with interface declarations and one or more "
        "scenarios. A scenario contains inputs, expected outputs and optional hold times for "
        "timers. The cases cover initialisation, normal operation, priority or edge conditions, "
        "and fault recovery where applicable.",
        "",
        r"\begin{table}[htbp]",
        r"\centering",
        r"\small",
        r"\caption{Test-case coverage and local validation results.}",
        r"\label{tab:custom_validation}",
        r"\begin{tabular}{|l|c|c|c|c|}",
        r"\hline",
        r"ID & Test cases & Steps & Dry check & Sim pass \\",
        r"\hline",
    ]
    for q, *_ in rows:
        case = json.loads((ROOT / "codesys_service" / "bank" / "custom" / "cases" / f"{q['id']}.testcase.json").read_text(encoding="utf-8"))
        steps = sum(len(c["steps"]) for c in case["cases"])
        v = VAL_BY_ID[q["id"]]
        lines.append(
            f"{q['id']} & {len(case['cases'])} & {steps} & "
            f"{'VALID' if v['dry_valid'] else 'INVALID'} & "
            f"{v['cases_passed']}/{v['cases']} \\\\"
        )
    lines += [
        r"\hline",
        r"\end{tabular}",
        r"\end{table}",
        "",
        f"The local validation reports {VAL['totals']['passed']}/{VAL['totals']['cases']} "
        "simulation cases passing, and all 12 reference implementations pass the static "
        "check. The real CODESYS compilation results are reported by the experimental "
        "evaluation. The tests validate functional behaviour against the reference ST; "
        "they do not replace a CODESYS compile in the target environment.",
        "",
    ]
    (REPORT / "custom_question_bank.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_appendix():
    lines = [
        "% Custom Question Bank LTL specification appendix.",
        "% Include after \\appendix, e.g. \\appendix \\input{report/custom_ltl_appendix}.",
        "% This fragment contains no preamble and no package imports.",
        "",
        r"\section{Custom Question Bank LTL Specifications}",
        r"\label{app:custom_ltl}",
        "",
        "This appendix lists the three LTL properties for each custom question. "
        "Atoms, assumptions and machine-readable formulas are stored in "
        r"\texttt{specs/custom/Cxx.ltl.json}. The operators are: $\mathbf{G}$ (always), "
        r"$\mathbf{F}$ (eventually), $\mathbf{X}$ (next scan), $\wedge$ (and), "
        r"$\vee$ (or), $\neg$ (not) and $\rightarrow$ (implies).",
        "",
    ]
    for diff in ("easy", "medium", "hard"):
        for q in TASKS[diff]:
            spec = json.loads((ROOT / "specs" / "custom" / f"{q['id']}.ltl.json").read_text(encoding="utf-8"))
            lines += [
                f"\\subsection*{{{q['id']} --- {esc(q['title'])}}}",
                f"\\noindent POU: \\texttt{{{esc(q['pou'])}}}; file: "
                f"\\texttt{{specs/custom/{q['id']}.ltl.json}}.",
                r"\begin{small}",
                r"\begin{itemize}",
            ]
            for p in spec["properties"]:
                lines.append(
                    f"\\item \\textbf{{{p['id']} --- {esc(p['name'])}}}: "
                    f"{formula_tex(p['formula'])}"
                )
            lines += [r"\end{itemize}", r"\end{small}", ""]
    (REPORT / "custom_ltl_appendix.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_preview():
    lines = [
        r"\documentclass[11pt]{article}",
        r"\usepackage[margin=1in]{geometry}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage{lmodern}",
        r"\usepackage{hyperref}",
        r"\title{PLCGen Custom Question Bank}",
        r"\author{Custom Question Bank dataset section}",
        r"\date{}",
        r"\begin{document}",
        r"\sloppy",
        r"\maketitle",
        r"\tableofcontents",
        r"\newpage",
        r"\input{custom_question_bank}",
        r"\appendix",
        r"\input{custom_ltl_appendix}",
        r"\end{document}",
        "",
    ]
    (REPORT / "custom_report_preview.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    build_body()
    build_appendix()
    build_preview()
    (REPORT / "README.md").write_text(
        "# Report fragments (Custom Question Bank)\n\n"
        "The report is written per person in `.tex` and unified later. These fragments are\n"
        "ready to be included from the main report; they contain no preamble and no\n"
        "`\\usepackage` commands.\n\n"
        "## Include from the main report\n\n"
        "```latex\n"
        "\\input{report/custom_question_bank}\n"
        "...\n"
        "\\appendix\n"
        "\\input{report/custom_ltl_appendix}\n"
        "```\n\n"
        "## Preview PDF\n\n"
        "`custom_report_preview.tex` is a standalone wrapper used only to compile\n"
        "`PLCGen_Custom_Question_Bank.pdf`. Do not include the wrapper in the main report.\n\n"
        "## Notes\n\n"
        "- The fragments use only standard LaTeX (`section`, `tabular`, `itemize`).\n"
        "- No internal group roles or work-division references are included.\n"
        "- The dataset paths are relative to the repository root.\n",
        encoding="utf-8",
    )
    print("Wrote report/custom_question_bank.tex")
    print("Wrote report/custom_ltl_appendix.tex")
    print("Wrote report/custom_report_preview.tex")
    print("Wrote report/README.md")


if __name__ == "__main__":
    main()
