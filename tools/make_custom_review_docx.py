#!/usr/bin/env python3
"""Generate the readable Word summary for the Custom Question Bank."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from custom_defs import QUESTIONS  # noqa: E402

OUT = ROOT / "PLCGen_Custom_Question_Bank_Review.docx"
VAL = json.loads((ROOT / "results" / "custom" / "validation.json").read_text(encoding="utf-8"))
TASKS = {t["id"]: t for t in VAL["tasks"]}


def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = h
        for p in hdr[i].paragraphs:
            for r in p.runs:
                r.bold = True
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = str(value)
    if widths:
        for row in table.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = w
    return table


def heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    return h


def bullet(doc, text):
    doc.add_paragraph(text, style="List Bullet")


def code(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.name = "Courier New"
    run.font.size = Pt(9)
    return p


def main():
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    title = doc.add_heading("PLCGen — Custom Question Bank (C01–C12)", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run("Resumen del trabajo, validación y puntos para la siguiente iteración")
    r.italic = True
    r.font.size = Pt(11)
    doc.add_paragraph("Custom Question Bank dataset, LTL specifications and test cases — internal review copy.").alignment = WD_ALIGN_PARAGRAPH.CENTER

    heading(doc, "1. Resumen ejecutivo")
    doc.add_paragraph(
        "He creado una primera versión completa del banco de preguntas propio: 12 escenarios originales, "
        "tres especificaciones LTL por pregunta, un test case ejecutable por pregunta y una implementación "
        "ST de referencia para validar los tests. Todo está alineado con el formato que ya usa el repositorio "
        "PLCGen y con el naming acordado con la parte experimental."
    )
    add_table(doc, ["Elemento", "Resultado"], [
        ["Preguntas propias", "12 (3 easy, 5 medium, 4 hard)"],
        ["Ejes de diversidad", "sorting/filtering, cyclic timing, safety logic (4 preguntas por eje)"],
        ["Especificaciones LTL", "36 propiedades (3 por pregunta)"],
        ["Test cases", "28 casos, todos en formato del repo"],
        ["ST de referencia", "12/12 lint PASS"],
        ["Validación dry", "12/12 archivos válidos"],
        ["Validación sim", "28/28 casos PASS"],
        ["Naming", "C01–C12 / FB_C01–FB_C12; público: FB_Q01–FB_Q20"],
    ], widths=None)

    heading(doc, "2. Nomenclatura")
    doc.add_paragraph(
        "El prefijo FB significa Function Block (el tipo de POU de IEC 61131-3 que genera el agente). "
        "La letra Q identifica el banco público y la letra C las preguntas custom (C01–C12). "
        "Así, FB_C07 se lee: Function Block, pregunta propia 07."
    )
    add_table(doc, ["Elemento", "Patrón", "Ejemplo"], [
        ["Preguntas públicas", "FB_Q01 … FB_Q20", "FB_Q07"],
        ["Preguntas propias", "FB_C01 … FB_C12", "FB_C07"],
        ["Archivo de test", "Cxx.testcase.json", "C07.testcase.json"],
        ["Archivo de spec", "Cxx.ltl.json", "C07.ltl.json"],
    ])

    heading(doc, "3. Qué contiene el banco")
    doc.add_paragraph("La entrega está organizada en cinco bloques:")
    add_table(doc, ["Bloque", "Ruta", "Contenido"], [
        ["Dataset", "data/custom_questions.json", "12 preguntas con id, POU, dificultad, metadatos, interfaz y enunciado en Markdown."],
        ["Manifest", "data/custom_manifest.json", "Mapa id → POU → spec → test → ST de referencia para integrarlo con el runner experimental."],
        ["LTL", "specs/custom/Cxx.ltl.json", "Átomos, supuestos y 3 propiedades por pregunta."],
        ["Tests", "codesys_service/bank/custom/cases/", "28 casos en el formato de run_tests.py (dry/sim)."],
        ["ST referencia", "codesys_service/bank/custom/st/", "12 implementaciones usadas solo para validar los tests."],
        ["Documentación", "docs/", "Registro de fuente/adaptación, specs, tests y resultados. El Word es solo un resumen interno."],
        ["Informe LaTeX", "report/", "Sección y apéndice para el informe final, más un PDF de preview."],
        ["Validador", "tools/validate_custom_bank.py", "Comprueba IDs, interfaces, specs, tests y manifest."],
    ])
    doc.add_paragraph(
        "Nota importante: el ST de referencia no se le debe pasar al agente durante los experimentos. "
        "Está separado del dataset y solo sirve para comprobar que los tests son ejecutables y coherentes."
    )

    heading(doc, "4. Las 12 preguntas")
    rows = []
    for q in QUESTIONS:
        inputs = sum(1 for v in q["interface"] if v[1] == "input")
        outputs = sum(1 for v in q["interface"] if v[1] == "output")
        rows.append([q["id"], q["title"], q["difficulty"], q["axis"], f"{inputs} / {outputs}",
                     len(q["specs"]), len(q["cases"])])
    add_table(doc, ["ID", "Título", "Dificultad", "Eje principal", "I/O", "Props", "Tests"], rows)

    heading(doc, "5. Diversidad")
    add_table(doc, ["Eje", "Preguntas", "Nº"], [
        ["Sorting / filtering", "C01, C07, C09, C11", "4"],
        ["Cyclic timing", "C03, C04, C05, C08", "4"],
        ["Safety logic", "C02, C06, C10, C12", "4"],
    ])
    add_table(doc, ["Dificultad", "Preguntas", "Nº"], [
        ["Easy", "C01, C02, C03", "3"],
        ["Medium", "C04, C05, C06, C07, C08", "5"],
        ["Hard", "C09, C10, C11, C12", "4"],
    ])
    doc.add_paragraph(
        "El banco público se centra sobre todo en máquinas de estados y alarmas/debounce. "
        "Este set refuerza a propósito sorting/filtering, cyclic timing y safety logic, que era la "
        "petición de la parte experimental."
    )

    heading(doc, "6. Detalle por pregunta")
    for q in QUESTIONS:
        heading(doc, f"{q['id']} — {q['title']}", level=2)
        p = doc.add_paragraph()
        p.add_run("Dificultad: ").bold = True
        p.add_run(f"{q['difficulty']}   ")
        p.add_run("Eje: ").bold = True
        p.add_run(q["axis"])
        doc.add_paragraph(q["rationale"])
        inputs = ", ".join(f"{v[0]}" for v in q["interface"] if v[1] == "input")
        outputs = ", ".join(f"{v[0]}" for v in q["interface"] if v[1] == "output")
        doc.add_paragraph(f"Entradas: {inputs}.")
        doc.add_paragraph(f"Salidas: {outputs}.")
        doc.add_paragraph("Propiedades LTL:")
        add_table(doc, ["ID", "Nombre", "Fórmula"], [
            [pid, name, formula] for pid, name, formula, _ in q["specs"]
        ])
        doc.add_paragraph("Test cases:")
        for c in q["cases"]:
            status = ""
            detail = TASKS.get(q["id"], {})
            for tc in detail.get("cases_detail", []):
                if tc.get("id") == c["id"]:
                    status = f" — {tc.get('result')}"
            bullet(doc, f"{c['id']}: {c['name']} ({len(c['steps'])} pasos){status}")

    heading(doc, "7. Validación ejecutada")
    doc.add_paragraph(
        "La validación se ha ejecutado en local con el toolchain del repo, sin CODESYS: "
        "st_lint.py para el análisis estático y run_tests.py con backend dry y sim. "
        "El backend sim ejecuta la lógica ST scan a scan."
    )
    val_rows = []
    for q in QUESTIONS:
        t = TASKS[q["id"]]
        val_rows.append([q["id"], q["pou"], "VALID" if t["dry_valid"] else "INVALID",
                         f"{t['cases_passed']}/{t['cases']}"])
    add_table(doc, ["ID", "POU", "Dry", "Sim"], val_rows)
    doc.add_paragraph(
        f"Resultado global: lint 12/12 PASS, dry 12/12 VALID, sim {VAL['totals']['passed']}/"
        f"{VAL['totals']['cases']} PASS. El detalle está en docs/custom_validation_results.md."
    )
    doc.add_paragraph(
        "Limitación: esto valida la lógica contra la ST de referencia, no contra CODESYS real. "
        "La compilación CODESYS queda pendiente de la parte 2/experimentos."
    )

    heading(doc, "8. Cómo ejecutar la validación")
    code(doc, "cd custom_question_bank\npython3 tools/validate_custom_bank.py\npython3 tools/run_custom_validation.py")
    doc.add_paragraph("Para probar una pregunta concreta:")
    code(doc,
         "cd custom_question_bank/codesys_service\n"
         "python3 run_tests.py --case bank/custom/cases/C07.testcase.json \\\n"
         "  --st bank/custom/st/FB_C07.st --backend dry\n"
         "python3 run_tests.py --case bank/custom/cases/C07.testcase.json \\\n"
         "  --st bank/custom/st/FB_C07.st --backend sim")

    heading(doc, "8.1 Informe final en LaTeX")
    doc.add_paragraph(
        "El grupo acordó escribir el informe en archivos .tex y unificarlos después. "
        "La sección de este dataset está preparada como fragmento, sin preámbulo ni paquetes, "
        "para incluirla con \\input{}."
    )
    bullet(doc, "Cuerpo: report/custom_question_bank.tex.")
    bullet(doc, "Apéndice con las 36 fórmulas: report/custom_ltl_appendix.tex.")
    bullet(doc, "Instrucciones: report/README.md.")
    bullet(doc, "PDF de preview: report/PLCGen_Custom_Question_Bank.pdf.")
    bullet(doc, "Este Word es solo un resumen interno: no se incluye en el ZIP ni se sube a Git.")

    heading(doc, "9. Integración con la parte experimental")
    bullet(doc, "Entregar el archivo data/custom_manifest.json al runner experimental: contiene el mapa completo de las 12 tareas.")
    bullet(doc, "El naming está alineado: público FB_Q01–FB_Q20; propio FB_C01–FB_C12.")
    bullet(doc, "Los tests están en el mismo formato que los públicos, así que run_tests.py los acepta sin cambios.")
    bullet(doc, "Los test cases de las preguntas propias están incluidos en este dataset; la evaluación experimental los ejecuta.")
    bullet(doc, "Para el informe, la sección Dataset puede usar docs/custom_dataset_record.md y la tabla de diversidad de este documento.")

    heading(doc, "10. Limitaciones y siguientes pasos")
    bullet(doc, "Revisión por pares: el dataset todavía no ha sido revisado de forma independiente; conviene una pasada de 30 min.")
    bullet(doc, "CODESYS real: falta compilar las 12 preguntas en CODESYS y adjuntar el resultado a la tabla de validación.")
    bullet(doc, "Verificación formal: las specs están escritas, pero aún no se han pasado por PLCverif ni por un model checker.")
    bullet(doc, "Cobertura: C11 tiene un solo caso; se puede añadir un caso de reset a mitad de capa y otro de pallet lleno.")
    bullet(doc, "Ambigüedad: revisar si alguna regla de prioridad (por ejemplo, Stop vs. EmergencyStop) debe quedar explícita en el enunciado.")
    bullet(doc, "Si el tiempo aprieta, priorizar la revisión de C01–C08 y dejar C09–C12 como hard opcionales.")

    heading(doc, "11. Checklist para revisar al llegar")
    for text in [
        "Abrir data/custom_questions.json y comprobar que las 12 preguntas se leen bien y que los nombres de variables son los que espera el runner experimental.",
        "Revisar las 36 fórmulas en specs/custom/ y decidir si alguna prioridad debe expresarse de otra forma.",
        "Abrir 2–3 test cases y comprobar que el comportamiento esperado coincide con lo que se quiere evaluar.",
        "Ejecutar python3 tools/run_custom_validation.py y verificar que sigue en 28/28.",
        "Decidir si se añaden más casos a C11 o si se cambia algún escenario antes de congelar esta versión.",
    ]:
        bullet(doc, text)

    heading(doc, "12. Archivos generados")
    code(doc,
         "data/custom_questions.json\n"
         "data/custom_manifest.json\n"
         "specs/custom/C01.ltl.json ... C12.ltl.json\n"
         "specs/custom/README.md\n"
         "codesys_service/bank/custom/cases/C01.testcase.json ... C12.testcase.json\n"
         "codesys_service/bank/custom/st/FB_C01.st ... FB_C12.st\n"
         "docs/custom_dataset_record.md\n"
         "docs/custom_specs.md\n"
         "docs/custom_tests.md\n"
         "docs/custom_validation_results.md\n"
         "report/custom_question_bank.tex\n"
         "report/custom_ltl_appendix.tex\n"
         "report/PLCGen_Custom_Question_Bank.pdf\n"
         "report/README.md\n"
         "tools/validate_custom_bank.py\n"
         "tools/run_custom_validation.py\n"
         "results/custom/validation.json")

    footer = doc.sections[0].footer.paragraphs[0]
    footer.text = "PLCGen Custom Question Bank — internal review copy"
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
