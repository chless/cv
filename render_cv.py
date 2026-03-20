#!/usr/bin/env python3
"""CV renderer: generates PDF and Word documents from cv_data.yaml.

Styled after a LaTeX academic CV with:
- Serif font (Times), large italic-style name
- Contact info right-aligned at top
- Section headers with thick black bar + bold title
- Two-column date|content layout
- Circle-bullet publications with bold titles, italic venues
- Page numbers (X/Y) at bottom right
"""

import argparse
from pathlib import Path

import yaml
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import black, HexColor
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    BaseDocTemplate,
    PageTemplate,
    Frame,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load_cv(path: str = "cv_data.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# PDF Styles
# ---------------------------------------------------------------------------

PAGE_W, PAGE_H = A4
MARGIN_L = 22 * mm
MARGIN_R = 22 * mm
MARGIN_T = 20 * mm
MARGIN_B = 20 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

DATE_COL_W = 70  # width of the date column in points
BODY_COL_W = CONTENT_W - DATE_COL_W

FONT_SERIF = "Times-Roman"
FONT_SERIF_BOLD = "Times-Bold"
FONT_SERIF_ITALIC = "Times-Italic"
FONT_SERIF_BOLD_ITALIC = "Times-BoldItalic"

BAR_COLOR = black
BAR_WIDTH = 50  # width of the thick bar before section titles
BAR_HEIGHT = 3


def _styles():
    """Build paragraph styles for the CV."""
    s = {}

    s["name"] = ParagraphStyle(
        "name", fontName=FONT_SERIF_ITALIC, fontSize=26, leading=32,
        alignment=TA_LEFT, textColor=black,
    )
    s["contact"] = ParagraphStyle(
        "contact", fontName=FONT_SERIF_ITALIC, fontSize=10, leading=14,
        alignment=TA_RIGHT, textColor=black,
    )
    s["section"] = ParagraphStyle(
        "section", fontName=FONT_SERIF_BOLD, fontSize=14, leading=18,
        spaceBefore=0, spaceAfter=6, textColor=black,
    )
    s["subsection"] = ParagraphStyle(
        "subsection", fontName=FONT_SERIF_BOLD, fontSize=11, leading=15,
        alignment=TA_LEFT, spaceBefore=4, spaceAfter=4, textColor=black,
    )
    s["date"] = ParagraphStyle(
        "date", fontName=FONT_SERIF, fontSize=10, leading=13,
        alignment=TA_RIGHT, textColor=black,
    )
    s["entry_title"] = ParagraphStyle(
        "entry_title", fontName=FONT_SERIF_BOLD, fontSize=10.5, leading=14,
        alignment=TA_LEFT, textColor=black,
    )
    s["entry_body"] = ParagraphStyle(
        "entry_body", fontName=FONT_SERIF, fontSize=10, leading=13,
        alignment=TA_LEFT, textColor=black,
    )
    s["entry_italic"] = ParagraphStyle(
        "entry_italic", fontName=FONT_SERIF_ITALIC, fontSize=10, leading=13,
        alignment=TA_LEFT, textColor=black,
    )
    s["pub_title"] = ParagraphStyle(
        "pub_title", fontName=FONT_SERIF_BOLD, fontSize=10.5, leading=14,
        alignment=TA_JUSTIFY, textColor=black,
    )
    s["pub_body"] = ParagraphStyle(
        "pub_body", fontName=FONT_SERIF, fontSize=10, leading=13,
        alignment=TA_LEFT, textColor=black,
    )
    s["pub_venue"] = ParagraphStyle(
        "pub_venue", fontName=FONT_SERIF_ITALIC, fontSize=10, leading=13,
        alignment=TA_LEFT, textColor=black,
    )
    s["pub_note"] = ParagraphStyle(
        "pub_note", fontName=FONT_SERIF_BOLD, fontSize=10, leading=13,
        alignment=TA_LEFT, textColor=black,
    )
    s["topics_label"] = ParagraphStyle(
        "topics_label", fontName=FONT_SERIF, fontSize=10, leading=13,
        alignment=TA_LEFT, textColor=black,
    )
    return s


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

class SectionBar:
    """A thick black bar drawn inline as a Flowable."""
    def __init__(self, width=BAR_WIDTH, height=BAR_HEIGHT):
        from reportlab.platypus import Flowable
        self.__class__.__bases__ = (Flowable,)
        self._width = width
        self._height = height
        self.width = CONTENT_W
        self.height = height + 20  # includes spacing

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        self.canv.setFillColor(BAR_COLOR)
        # Draw bar at left, vertically centered
        self.canv.rect(0, 8, self._width, self._height, fill=1, stroke=0)


from reportlab.platypus import Flowable
from reportlab.pdfgen import canvas as pdfcanvas


class NumberedCanvas(pdfcanvas.Canvas):
    """Canvas that adds page numbers X/Y on every page."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()  # reset state without emitting the page

    def save(self):
        total = len(self._saved_page_states)
        for i, state in enumerate(self._saved_page_states):
            self.__dict__.update(state)
            self.setFont(FONT_SERIF, 9)
            self.drawRightString(
                PAGE_W - MARGIN_R,
                MARGIN_B - 10,
                f"{i + 1}/{total}",
            )
            pdfcanvas.Canvas.showPage(self)
        pdfcanvas.Canvas.save(self)


class SectionTitle(Flowable):
    """A section title with a thick black bar to its left."""
    def __init__(self, text, style, bar_w=BAR_WIDTH, bar_h=BAR_HEIGHT, gap=8):
        super().__init__()
        self.text = text
        self.style = style
        self.bar_w = bar_w
        self.bar_h = bar_h
        self.gap = gap
        self._para = Paragraph(text, style)

    def wrap(self, availWidth, availHeight):
        pw, ph = self._para.wrap(availWidth - self.bar_w - self.gap, availHeight)
        self.width = availWidth
        self.height = max(ph, self.bar_h) + 6
        self._para_h = ph
        self._para_w = pw
        return self.width, self.height

    def draw(self):
        # Draw thick black bar
        bar_y = (self.height - self.bar_h) / 2
        self.canv.setFillColor(BAR_COLOR)
        self.canv.rect(0, bar_y, self.bar_w, self.bar_h, fill=1, stroke=0)

        # Draw text to the right of bar
        text_x = self.bar_w + self.gap
        text_y = (self.height - self._para_h) / 2
        self._para.drawOn(self.canv, text_x, text_y)


class BulletCircle(Flowable):
    """A circle bullet + paragraph content."""
    def __init__(self, content_flowables, bullet_r=3, indent=16):
        super().__init__()
        self.content = content_flowables  # list of Paragraphs
        self.bullet_r = bullet_r
        self.indent = indent

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        total_h = 0
        self._wrapped = []
        for f in self.content:
            w, h = f.wrap(availWidth - self.indent, availHeight - total_h)
            self._wrapped.append((f, w, h))
            total_h += h
        self.height = total_h
        return self.width, self.height

    def draw(self):
        # Circle bullet at the top-left
        first_h = self._wrapped[0][2] if self._wrapped else 14
        cy = self.height - first_h / 2
        cx = self.indent / 2
        self.canv.setStrokeColor(black)
        self.canv.setLineWidth(0.8)
        self.canv.circle(cx, cy, self.bullet_r, fill=0, stroke=1)

        # Draw content
        y = self.height
        for f, w, h in self._wrapped:
            y -= h
            f.drawOn(self.canv, self.indent, y)


def _make_dated_entry(date_text, content_parts, styles):
    """Create a table row with date on left and content on right."""
    date_para = Paragraph(date_text, styles["date"])

    # content_parts is a list of (text, style_name) tuples
    content = []
    for text, sname in content_parts:
        content.append(Paragraph(text, styles[sname]))

    tbl = Table(
        [[date_para, content]],
        colWidths=[DATE_COL_W, BODY_COL_W],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]),
    )
    return tbl


def _make_dated_table(rows, styles):
    """Create a table with multiple dated entries. Each row is (date, content_parts)."""
    table_data = []
    for date_text, content_parts in rows:
        date_para = Paragraph(date_text, styles["date"])
        content = []
        for text, sname in content_parts:
            content.append(Paragraph(text, styles[sname]))
        table_data.append([date_para, content])

    if not table_data:
        return Spacer(1, 0)

    tbl = Table(
        table_data,
        colWidths=[DATE_COL_W, BODY_COL_W],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]),
    )
    return tbl


def _underline_name(authors: str, name: str) -> str:
    """Underline the CV owner's name in the author string."""
    return authors.replace(name, f"<u>{name}</u>")


# ---------------------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------------------


def render_pdf(cv: dict, output: str = "cv_output.pdf"):
    frame = Frame(MARGIN_L, MARGIN_B, CONTENT_W, PAGE_H - MARGIN_T - MARGIN_B,
                  id="main", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    template = PageTemplate(id="cv", frames=[frame])
    doc = BaseDocTemplate(
        output, pagesize=A4,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T, bottomMargin=MARGIN_B,
    )
    doc.addPageTemplates([template])

    s = _styles()
    story = []

    # === HEADER: Name (left) + Contact (right) ===
    name_para = Paragraph(f"<i>{cv['name']}</i>", s["name"])
    contact_lines = []
    if cv.get("email"):
        contact_lines.append(f"&#9993; {cv['email']}")
    if cv.get("phone"):
        contact_lines.append(f"&#9742; {cv['phone']}")
    if cv.get("website"):
        contact_lines.append(f"&#9758; {cv['website']}")
    if cv.get("github"):
        contact_lines.append(f"&#9672; {cv['github']}")
    contact_para = Paragraph("<br/>".join(contact_lines), s["contact"])

    header_table = Table(
        [[name_para, contact_para]],
        colWidths=[CONTENT_W * 0.55, CONTENT_W * 0.45],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]),
    )
    story.append(header_table)
    story.append(Spacer(1, 10))

    # === EDUCATION ===
    if cv.get("education"):
        story.append(SectionTitle("Education", s["section"]))
        rows = []
        for e in cv["education"]:
            parts = []
            degree_line = f'<b>{e["degree"]},</b> <i>{e["institution"]}</i>'
            if e.get("location"):
                degree_line += f', {e["location"]}'
            parts.append((degree_line, "entry_body"))
            if e.get("major"):
                parts.append((f'Major: {e["major"]}', "entry_body"))
            if e.get("advisor"):
                parts.append((f'Advisor: {e["advisor"]}', "entry_body"))
            rows.append((e["period"].replace("~", "–"), parts))
        story.append(_make_dated_table(rows, s))

    # === RESEARCH INTERESTS ===
    if cv.get("research_interests"):
        story.append(SectionTitle("Research Interests", s["section"]))
        topics = "; ".join(cv["research_interests"]) + "."
        # Use a table for "Topics" label + content
        tbl = Table(
            [[Paragraph("Topics", s["entry_body"]),
              Paragraph(topics, s["entry_body"])]],
            colWidths=[DATE_COL_W, BODY_COL_W],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]),
        )
        story.append(tbl)

    # === PUBLICATIONS ===
    if cv.get("publications"):
        story.append(SectionTitle("Publications", s["section"]))

        owner_name = cv.get("name", "")

        # Group by category if present
        categories = {}
        for p in cv["publications"]:
            cat = p.get("category", "Publications")
            categories.setdefault(cat, []).append(p)

        for cat_name, pubs in categories.items():
            if len(categories) > 1:
                story.append(Paragraph(f"<b>{cat_name}</b>", s["subsection"]))

            for p in pubs:
                parts = []
                parts.append(Paragraph(
                    f'<b>{p["title"]}</b>.',
                    s["pub_title"],
                ))
                authors = _underline_name(p["authors"], owner_name)
                parts.append(Paragraph(authors + ".", s["pub_body"]))
                if p.get("venue"):
                    parts.append(Paragraph(
                        f'<i>{p["venue"]}</i>.',
                        s["pub_venue"],
                    ))
                if p.get("note"):
                    parts.append(Paragraph(
                        f'<b>{p["note"]}</b>',
                        s["pub_note"],
                    ))
                if p.get("link_label"):
                    parts.append(Paragraph(p["link_label"], s["pub_body"]))

                story.append(BulletCircle(parts))
                story.append(Spacer(1, 6))

    # === CONFERENCES (as separate section if present) ===
    if cv.get("conferences"):
        story.append(SectionTitle("Conferences", s["section"]))
        for c in cv["conferences"]:
            parts = []
            parts.append(Paragraph(f'<b>{c["title"]}</b>.', s["pub_title"]))
            if c.get("authors"):
                authors = _underline_name(c["authors"], cv.get("name", ""))
                parts.append(Paragraph(authors + ".", s["pub_body"]))
            if c.get("venue"):
                parts.append(Paragraph(f'<i>{c["venue"]}</i>.', s["pub_venue"]))
            if c.get("note"):
                parts.append(Paragraph(f'<b>{c["note"]}</b>', s["pub_note"]))
            story.append(BulletCircle(parts))
            story.append(Spacer(1, 6))

    # === HONORS AND AWARDS ===
    if cv.get("honors"):
        story.append(SectionTitle("Honors and Awards", s["section"]))
        rows = []
        for h in cv["honors"]:
            parts = []
            title_line = f'<b>{h["title"]}</b>'
            if h.get("organization"):
                title_line += f', <i>{h["organization"]}</i>'
            parts.append((title_line, "entry_body"))
            if h.get("description"):
                parts.append((h["description"], "entry_body"))
            rows.append((str(h.get("year", "")), parts))
        story.append(_make_dated_table(rows, s))

    # === INVITED TALKS ===
    if cv.get("invited_talks"):
        story.append(SectionTitle("Invited Talks", s["section"]))
        rows = []
        for t in cv["invited_talks"]:
            parts = []
            title_line = f'<b>{t["title"]}</b>'
            if t.get("venue"):
                title_line += f', <i>{t["venue"]}</i>'
            parts.append((title_line, "entry_body"))
            if t.get("link_label"):
                parts.append((f'({t["link_label"]})', "entry_body"))
            rows.append((t.get("date", ""), parts))
        story.append(_make_dated_table(rows, s))

    # === WORK EXPERIENCE ===
    if cv.get("work_experience"):
        story.append(SectionTitle("Experience", s["section"]))
        rows = []
        for w in cv["work_experience"]:
            parts = []
            line = f'<b>{w["position"]},</b> <i>{w["organization"]}</i>'
            if w.get("location"):
                line += f', {w["location"]}'
            parts.append((line, "entry_body"))
            if w.get("department"):
                parts.append((w["department"], "entry_body"))
            rows.append((w["period"].replace("~", "–"), parts))
        story.append(_make_dated_table(rows, s))

    # === RESEARCH EXPERIENCE ===
    if cv.get("research_experience"):
        story.append(SectionTitle("Research Experience", s["section"]))
        rows = []
        for r in cv["research_experience"]:
            parts = []
            line = f'<b>{r["position"]},</b> <i>{r["organization"]}</i>'
            if r.get("location"):
                line += f', {r["location"]}'
            parts.append((line, "entry_body"))
            if r.get("advisor"):
                parts.append((f'Advisor: {r["advisor"]}', "entry_body"))
            if r.get("subject"):
                parts.append((f'Subject: {r["subject"]}', "entry_body"))
            rows.append((r["period"].replace("~", "–"), parts))
        story.append(_make_dated_table(rows, s))

    # === ACADEMIC SERVICES ===
    if cv.get("academic_services"):
        story.append(SectionTitle("Academic Services", s["section"]))
        for svc in cv["academic_services"]:
            label = svc.get("role", "")
            detail = svc.get("detail", "")
            tbl = Table(
                [[Paragraph(label, s["entry_body"]),
                  Paragraph(detail, s["entry_body"])]],
                colWidths=[DATE_COL_W + 20, BODY_COL_W - 20],
                style=TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]),
            )
            story.append(tbl)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF saved: {output}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Render CV to PDF")
    parser.add_argument("--data", default="cv_data.yaml", help="Path to CV YAML data")
    parser.add_argument("--output", default="cv_output.pdf", help="PDF output filename")
    args = parser.parse_args()

    cv = load_cv(args.data)
    render_pdf(cv, args.output)


if __name__ == "__main__":
    main()
