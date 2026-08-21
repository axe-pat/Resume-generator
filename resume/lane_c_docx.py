#!/usr/bin/env python3
"""Build compact Lane C resume and cover-letter DOCX files from JSON payloads."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt


FONT = "Times New Roman"


def _set_font(run, size: float = 10, *, bold: bool = False, italic: bool = False):
    run.font.name = FONT
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), FONT)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), FONT)
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    return run


def _set_cellless_defaults(doc: Document, size: float = 10):
    style = doc.styles["Normal"]
    style.font.name = FONT
    style._element.rPr.rFonts.set(qn("w:ascii"), FONT)
    style._element.rPr.rFonts.set(qn("w:hAnsi"), FONT)
    style.font.size = Pt(size)
    style.paragraph_format.space_after = Pt(0)
    style.paragraph_format.line_spacing = 1.0


def _add_bottom_border(paragraph):
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = p_pr.find(qn("w:pBdr"))
    if p_bdr is None:
        p_bdr = OxmlElement("w:pBdr")
        p_pr.append(p_bdr)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "000000")
    p_bdr.append(bottom)


def _section_header(doc: Document, text: str):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    _add_bottom_border(p)
    _set_font(p.add_run(text.upper()), 10, bold=True)
    return p


def _header_line(doc: Document, left: str, right: str = "", *, size: float = 10):
    p = doc.add_paragraph()
    p.paragraph_format.tab_stops.add_tab_stop(Inches(7.0), WD_TAB_ALIGNMENT.RIGHT)
    _set_font(p.add_run(left), size, bold=True)
    if right:
        _set_font(p.add_run("\t" + right), size)
    return p


def _subtitle(doc: Document, text: str):
    p = doc.add_paragraph()
    _set_font(p.add_run(text), 10, italic=True)
    return p


def _bullet(doc: Document, text: str):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.first_line_indent = Inches(-0.15)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.0
    _set_font(p.add_run(text), 10)
    return p


def build_resume(data: dict, output: Path):
    doc = Document()
    _set_cellless_defaults(doc, 10)
    sec = doc.sections[0]
    sec.top_margin = Inches(0.48)
    sec.bottom_margin = Inches(0.48)
    sec.left_margin = Inches(0.55)
    sec.right_margin = Inches(0.55)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(1)
    _set_font(p.add_run(data["name"]), 16, bold=True)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    _set_font(p.add_run(data["contact"]), 9.5)

    if data.get("profile"):
        _section_header(doc, "Profile")
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        _set_font(p.add_run(data["profile"]), 10)

    _section_header(doc, "Education")
    for index, row in enumerate(data.get("education", [])):
        if index:
            doc.add_paragraph().paragraph_format.space_after = Pt(0)
        _header_line(doc, row["school"], row.get("date", ""))
        _subtitle(doc, row["degree"])
        for bullet in row.get("bullets", []):
            _bullet(doc, bullet)

    for section in data.get("sections", []):
        _section_header(doc, section["title"])
        for index, entry in enumerate(section.get("entries", [])):
            if index:
                spacer = doc.add_paragraph()
                spacer.paragraph_format.line_spacing = 0.2
                spacer.paragraph_format.space_after = Pt(0)
                _set_font(spacer.add_run(""), 2)
            _header_line(doc, entry["organization"], entry.get("date", ""))
            if entry.get("role"):
                _subtitle(doc, entry["role"])
            for bullet in entry.get("bullets", []):
                _bullet(doc, bullet)

    if data.get("skills"):
        _section_header(doc, "Skills & Additional")
        for label, value in data["skills"]:
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.left_indent = Inches(0.25)
            p.paragraph_format.first_line_indent = Inches(-0.15)
            p.paragraph_format.space_after = Pt(0)
            _set_font(p.add_run(label + ": "), 10, bold=True)
            _set_font(p.add_run(value), 10)

    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)


def build_cover_letter(data: dict, output: Path):
    doc = Document()
    _set_cellless_defaults(doc, 11)
    sec = doc.sections[0]
    sec.top_margin = Inches(0.72)
    sec.bottom_margin = Inches(0.72)
    sec.left_margin = Inches(0.85)
    sec.right_margin = Inches(0.85)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(1)
    _set_font(p.add_run(data["name"]), 16, bold=True)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(10)
    _set_font(p.add_run(data["contact"]), 10)

    for line in [data["date"], *data["address"]]:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        _set_font(p.add_run(line), 11)

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(9)
    p.paragraph_format.space_after = Pt(8)
    _set_font(p.add_run(data["salutation"]), 11)

    for text in data["paragraphs"]:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.line_spacing = 1.08
        _set_font(p.add_run(text), 11)

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(12)
    _set_font(p.add_run(data.get("closing", "Sincerely,")), 11)
    p = doc.add_paragraph()
    _set_font(p.add_run(data["name"]), 11, bold=True)

    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: lane_c_docx.py <payload.json>")
    payload_path = Path(sys.argv[1]).resolve()
    data = json.loads(payload_path.read_text(encoding="utf-8"))
    output = Path(data["output_path"]).expanduser().resolve()
    if data["kind"] == "resume":
        build_resume(data, output)
    elif data["kind"] == "cover_letter":
        build_cover_letter(data, output)
    else:
        raise SystemExit(f"Unknown kind: {data['kind']}")
    print(output)


if __name__ == "__main__":
    main()
