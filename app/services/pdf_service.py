"""
pdf_service.py — StudyLens AI PDF renderer.

Converts structured notes (with markdown in detailed_notes) into a
professional ReportLab PDF.  All markdown syntax is parsed and rendered
properly — no raw `###`, `**`, or backtick fences ever appear in the output.
"""

import logging
import os
import re
from pathlib import Path
from typing import List

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

PDF_OUTPUT_DIR = Path("generated_pdfs")

# ─── Colour palette ───────────────────────────────────────────────────────────
_BRAND_DARK      = colors.HexColor("#1A1A2E")
_BRAND_ACCENT    = colors.HexColor("#0F3460")
_BRAND_HIGHLIGHT = colors.HexColor("#E94560")
_TEXT_PRIMARY    = colors.HexColor("#1A1A2E")
_TEXT_SECONDARY  = colors.HexColor("#555555")
_WHITE           = colors.white
_RULE_COLOR      = colors.HexColor("#D0D7DE")
_CODE_BG         = colors.HexColor("#F6F8FA")
_CODE_BORDER     = colors.HexColor("#D0D7DE")
_CODE_TEXT       = colors.HexColor("#24292F")
_HIGHLIGHT_BG    = colors.HexColor("#FFF8E1")
_HIGHLIGHT_BORDER= colors.HexColor("#F0C040")
_DEF_BG          = colors.HexColor("#F0F4FF")
_DEF_BORDER      = colors.HexColor("#0F3460")


def _build_styles() -> dict:
    styles = {}

    styles["doc_title"] = ParagraphStyle(
        "doc_title", fontName="Helvetica-Bold", fontSize=26,
        textColor=_BRAND_DARK, alignment=TA_CENTER, spaceAfter=4, leading=32,
    )
    styles["doc_subtitle"] = ParagraphStyle(
        "doc_subtitle", fontName="Helvetica", fontSize=11,
        textColor=_TEXT_SECONDARY, alignment=TA_CENTER, spaceAfter=4, leading=16,
    )
    styles["section_heading"] = ParagraphStyle(
        "section_heading", fontName="Helvetica-Bold", fontSize=13,
        textColor=_WHITE, alignment=TA_LEFT,
        spaceBefore=20, spaceAfter=8, leading=18,
        leftIndent=8, rightIndent=8,
        backColor=_BRAND_ACCENT, borderPad=7,
    )
    # Markdown ## heading
    styles["h2"] = ParagraphStyle(
        "h2", fontName="Helvetica-Bold", fontSize=12,
        textColor=_BRAND_ACCENT, alignment=TA_LEFT,
        spaceBefore=14, spaceAfter=4, leading=16,
    )
    # Markdown ### heading
    styles["h3"] = ParagraphStyle(
        "h3", fontName="Helvetica-Bold", fontSize=11,
        textColor=_TEXT_PRIMARY, alignment=TA_LEFT,
        spaceBefore=10, spaceAfter=3, leading=14,
    )
    # Markdown #### heading
    styles["h4"] = ParagraphStyle(
        "h4", fontName="Helvetica-Bold", fontSize=10,
        textColor=_TEXT_SECONDARY, alignment=TA_LEFT,
        spaceBefore=8, spaceAfter=2, leading=13,
    )
    styles["body"] = ParagraphStyle(
        "body", fontName="Helvetica", fontSize=10,
        textColor=_TEXT_PRIMARY, alignment=TA_LEFT,
        leading=16, spaceAfter=5,
    )
    styles["bullet"] = ParagraphStyle(
        "bullet", fontName="Helvetica", fontSize=10,
        textColor=_TEXT_PRIMARY, leading=14,
        spaceAfter=3, leftIndent=18, bulletIndent=6,
        bulletFontName="Helvetica-Bold", bulletFontSize=11,
        bulletColor=_BRAND_HIGHLIGHT,
    )
    styles["numbered"] = ParagraphStyle(
        "numbered", fontName="Helvetica", fontSize=10,
        textColor=_TEXT_PRIMARY, leading=14,
        spaceAfter=3, leftIndent=18,
    )
    styles["blockquote"] = ParagraphStyle(
        "blockquote", fontName="Helvetica-Oblique", fontSize=10,
        textColor=_TEXT_SECONDARY, leading=15,
        spaceAfter=5, leftIndent=20,
        borderWidth=2, borderColor=_BRAND_ACCENT,
        borderPad=6, borderRadius=None,
    )
    styles["code"] = ParagraphStyle(
        "code", fontName="Courier", fontSize=8.5,
        textColor=_CODE_TEXT, alignment=TA_LEFT,
        leading=13, spaceAfter=0,
        leftIndent=0, rightIndent=0,
    )
    styles["code_label"] = ParagraphStyle(
        "code_label", fontName="Courier-Bold", fontSize=8,
        textColor=_TEXT_SECONDARY, alignment=TA_LEFT,
        leading=11, spaceAfter=2,
    )
    styles["def_term"] = ParagraphStyle(
        "def_term", fontName="Helvetica-Bold", fontSize=10,
        textColor=_BRAND_ACCENT, leading=14,
        spaceBefore=8, spaceAfter=1,
    )
    styles["def_body"] = ParagraphStyle(
        "def_body", fontName="Helvetica", fontSize=10,
        textColor=_TEXT_PRIMARY, leading=14,
        leftIndent=12, spaceAfter=4,
    )
    styles["revision_item"] = ParagraphStyle(
        "revision_item", fontName="Helvetica", fontSize=10,
        textColor=_TEXT_PRIMARY, leading=14,
        spaceAfter=4, leftIndent=24,
    )
    styles["takeaway"] = ParagraphStyle(
        "takeaway", fontName="Helvetica", fontSize=10,
        textColor=_TEXT_PRIMARY, leading=15,
        spaceAfter=4, leftIndent=8, rightIndent=8,
        backColor=_HIGHLIGHT_BG,
        borderWidth=1, borderColor=_HIGHLIGHT_BORDER,
        borderPad=6, borderRadius=4,
    )
    return styles


# ─── Markdown inline parser ───────────────────────────────────────────────────

def _escape_xml(text: str) -> str:
    """Escape characters special to ReportLab's XML parser."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline_md(text: str) -> str:
    """
    Convert inline markdown to ReportLab XML tags.
    Order matters: code spans must be extracted first so we don't
    corrupt backtick contents with other substitutions.
    """
    parts = re.split(r"`([^`\n]+)`", text)
    out = ""
    for i, part in enumerate(parts):
        if i % 2 == 1:
            # Inside backtick — escape XML, wrap in Courier
            safe = _escape_xml(part)
            out += f'<font name="Courier" size="9" color="#6b21a8">{safe}</font>'
        else:
            # Regular text — escape XML then apply markdown
            safe = _escape_xml(part)
            # Bold-italic combined ***text***
            safe = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", safe)
            # Bold **text**
            safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
            # Italic *text*
            safe = re.sub(r"\*(.+?)\*", r"<i>\1</i>", safe)
            # Italic _text_
            safe = re.sub(r"_(.+?)_", r"<i>\1</i>", safe)
            out += safe
    return out


# ─── Code block renderer ──────────────────────────────────────────────────────

def _render_code_block(code_lines: List[str], lang: str, styles: dict) -> list:
    """Render a fenced code block as a styled table (gives it a visible box)."""
    inner_story = []

    # Language label row
    label_text = lang.upper() if lang else "CODE"
    inner_story.append(Paragraph(label_text, styles["code_label"]))

    # Code lines (escape XML, preserve spaces)
    code_paras = []
    for line in code_lines:
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # Replace leading spaces with non-breaking spaces to preserve indentation
        stripped_left = len(safe) - len(safe.lstrip(" "))
        safe = "\u00a0" * stripped_left + safe.lstrip(" ")
        code_paras.append(Paragraph(safe if safe.strip() else "&nbsp;", styles["code"]))

    # Wrap in a table for the background box
    from reportlab.platypus import KeepTogether

    table_data = [[para] for para in code_paras]
    if not table_data:
        return []

    t = Table([[p] for p in code_paras], colWidths=["100%"])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _CODE_BG),
        ("BOX",        (0, 0), (-1, -1), 0.8, _CODE_BORDER),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
    ]))

    return [
        Spacer(1, 0.15 * cm),
        Paragraph(label_text, styles["code_label"]),
        t,
        Spacer(1, 0.15 * cm),
    ]


# ─── Markdown block parser ────────────────────────────────────────────────────

def _parse_markdown(text: str, styles: dict) -> list:
    """
    Parse a markdown string and return a list of ReportLab flowables.
    Handles: headings, bullet lists, numbered lists, code fences,
    blockquotes, horizontal rules, bold/italic/inline-code.
    """
    story = []
    lines = text.split("\n")
    in_code = False
    code_lines: List[str] = []
    code_lang = ""
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # ── Code fence toggle ──────────────────────────────────
        if stripped.startswith("```"):
            if in_code:
                story.extend(_render_code_block(code_lines, code_lang, styles))
                code_lines = []
                code_lang = ""
                in_code = False
            else:
                in_code = True
                code_lang = stripped[3:].strip()
            i += 1
            continue

        if in_code:
            code_lines.append(line)
            i += 1
            continue

        # ── Empty line ─────────────────────────────────────────
        if not stripped:
            story.append(Spacer(1, 0.12 * cm))
            i += 1
            continue

        # ── ATX Headings ───────────────────────────────────────
        if stripped.startswith("#### "):
            story.append(Paragraph(_inline_md(stripped[5:]), styles["h4"]))
        elif stripped.startswith("### "):
            story.append(Paragraph(_inline_md(stripped[4:]), styles["h3"]))
        elif stripped.startswith("## "):
            story.append(Paragraph(_inline_md(stripped[3:]), styles["h2"]))
        elif stripped.startswith("# "):
            # Top-level heading inside detailed_notes → treat as h2
            story.append(Paragraph(_inline_md(stripped[2:]), styles["h2"]))

        # ── Horizontal rule ────────────────────────────────────
        elif re.match(r"^[-*_]{3,}$", stripped):
            story.append(_rule())

        # ── Blockquote ─────────────────────────────────────────
        elif stripped.startswith("> "):
            story.append(Paragraph(_inline_md(stripped[2:]), styles["blockquote"]))

        # ── Unordered list ─────────────────────────────────────
        elif re.match(r"^[-*•]\s", stripped):
            content = re.sub(r"^[-*•]\s+", "", stripped)
            story.append(
                Paragraph(f"•&nbsp;&nbsp;{_inline_md(content)}", styles["bullet"])
            )

        # ── Ordered list ───────────────────────────────────────
        elif re.match(r"^\d+\.\s", stripped):
            num_match = re.match(r"^(\d+)\.\s+(.*)", stripped)
            if num_match:
                num, content = num_match.group(1), num_match.group(2)
                story.append(
                    Paragraph(f"<b>{num}.</b>&nbsp;{_inline_md(content)}", styles["numbered"])
                )

        # ── Regular paragraph ──────────────────────────────────
        else:
            story.append(Paragraph(_inline_md(stripped), styles["body"]))

        i += 1

    # Flush any unclosed code block
    if in_code and code_lines:
        story.extend(_render_code_block(code_lines, code_lang, styles))

    return story


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _rule(width: str = "100%") -> HRFlowable:
    return HRFlowable(
        width=width, thickness=0.5,
        color=_RULE_COLOR, spaceAfter=6, spaceBefore=4,
    )


def _section_heading(text: str, styles: dict) -> Paragraph:
    return Paragraph(f"▸  {text}", styles["section_heading"])


def _bullet_items(items: List[str], styles: dict) -> List[Paragraph]:
    return [
        Paragraph(f"•&nbsp;&nbsp;{_inline_md(item)}", styles["bullet"])
        for item in items
        if item and item.strip()
    ]


# ─── Main generate_pdf ────────────────────────────────────────────────────────

def generate_pdf(notes: dict, output_filename: str) -> str:
    """
    Render a StudyLens AI study-pack dict into a professionally formatted PDF.

    Args:
        notes: dict from llm_service.generate_notes().
               Keys: overview, key_concepts, definitions, detailed_notes,
                     common_mistakes, revision_sheet, key_takeaways.
        output_filename: Filename (without directory path).

    Returns:
        Absolute path to the generated PDF.
    """
    PDF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PDF_OUTPUT_DIR / output_filename

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2.2 * cm, rightMargin=2.2 * cm,
        topMargin=2.5 * cm,  bottomMargin=2.5 * cm,
        title="StudyLens AI Notes",
        author="StudyLens AI",
        subject="Lecture Study Pack",
    )

    styles = _build_styles()
    story = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("StudyLens AI", styles["doc_title"]))
    story.append(Paragraph("Lecture Study Pack", styles["doc_subtitle"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=_BRAND_HIGHLIGHT, spaceAfter=20))

    # ── Overview ──────────────────────────────────────────────────────────────
    overview = notes.get("overview", "").strip()
    if overview:
        story.append(_section_heading("Overview", styles))
        story.append(Spacer(1, 0.15 * cm))
        story.append(Paragraph(_inline_md(overview), styles["body"]))
        story.append(_rule())

    # ── Key Concepts ──────────────────────────────────────────────────────────
    concepts: List[str] = notes.get("key_concepts", [])
    if concepts:
        story.append(_section_heading("Key Concepts", styles))
        story.append(Spacer(1, 0.1 * cm))
        story.extend(_bullet_items(concepts, styles))
        story.append(_rule())

    # ── Definitions ───────────────────────────────────────────────────────────
    definitions: List[dict] = notes.get("definitions", [])
    if definitions:
        story.append(_section_heading("Definitions", styles))
        story.append(Spacer(1, 0.1 * cm))
        for defn in definitions:
            term = str(defn.get("term", "")).strip()
            definition = str(defn.get("definition", "")).strip()
            if term:
                story.append(Paragraph(_inline_md(term), styles["def_term"]))
            if definition:
                story.append(Paragraph(_inline_md(definition), styles["def_body"]))
            story.append(Spacer(1, 0.05 * cm))
        story.append(_rule())

    # ── Detailed Notes (markdown-aware) ───────────────────────────────────────
    detailed_notes = notes.get("detailed_notes", "").strip()
    if detailed_notes:
        story.append(PageBreak())
        story.append(_section_heading("Detailed Notes", styles))
        story.append(Spacer(1, 0.2 * cm))
        story.extend(_parse_markdown(detailed_notes, styles))
        story.append(_rule())

    # ── Common Mistakes ───────────────────────────────────────────────────────
    mistakes: List[str] = notes.get("common_mistakes", [])
    if mistakes:
        story.append(_section_heading("Common Mistakes to Avoid", styles))
        story.append(Spacer(1, 0.1 * cm))
        for m in mistakes:
            if m and m.strip():
                story.append(
                    Paragraph(f"✗&nbsp;&nbsp;{_inline_md(m)}", styles["bullet"])
                )
        story.append(_rule())

    # ── Revision Sheet (checklist) ────────────────────────────────────────────
    revision: List[str] = notes.get("revision_sheet", [])
    if revision:
        story.append(PageBreak())
        story.append(_section_heading("Revision Sheet", styles))
        story.append(Spacer(1, 0.1 * cm))
        for item in revision:
            if item and item.strip():
                story.append(
                    Paragraph(f"☐&nbsp;&nbsp;{_inline_md(item)}", styles["revision_item"])
                )
        story.append(_rule())

    # ── Key Takeaways (highlighted cards) ────────────────────────────────────
    takeaways: List[str] = notes.get("key_takeaways", [])
    if takeaways:
        story.append(_section_heading("Key Takeaways", styles))
        story.append(Spacer(1, 0.1 * cm))
        for i, item in enumerate(takeaways, 1):
            if item and item.strip():
                story.append(
                    Paragraph(f"<b>{i}.</b>&nbsp;{_inline_md(item)}", styles["takeaway"])
                )
                story.append(Spacer(1, 0.06 * cm))
        story.append(_rule())

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.6 * cm))
    story.append(
        Paragraph(
            "<i>Generated by StudyLens AI — powered by Google Gemini</i>",
            styles["doc_subtitle"],
        )
    )

    try:
        doc.build(story)
        logger.info("PDF generated: %s", output_path.resolve())
    except Exception as exc:
        logger.exception("ReportLab failed to build PDF: %s", exc)
        raise

    return str(output_path.resolve())
