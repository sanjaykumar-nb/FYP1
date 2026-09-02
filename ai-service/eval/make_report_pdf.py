"""Build the complete project report as a PDF, with the figures embedded as VECTOR.

Every metric in this document is read from the committed result JSONs at build
time - nothing is hand-typed - so the PDF cannot drift from the evaluation that
produced it. Re-run after any eval change and the report updates itself.

Run: python -m eval.make_report_pdf     (from ai-service/; offline, deterministic)
Out: PROJECT_REPORT.pdf at the repository root.
"""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle)
from svglib.svglib import svg2rlg

EVAL = Path(__file__).parent
FIGS = EVAL / "figures"
OUT = EVAL.parent.parent / "PROJECT_REPORT.pdf"

BLUE = colors.HexColor("#1a5490")
ORANGE = colors.HexColor("#d2691e")
INK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#5c5c5c")
RULE = colors.HexColor("#d0d7de")
BAND = colors.HexColor("#eef3f8")
ZEBRA = colors.HexColor("#f7f9fb")

PAGE_W, PAGE_H = A4
MARGIN = 42
CONTENT_W = PAGE_W - 2 * MARGIN            # 511pt on A4

# ---------------------------------------------------------------- data
D = {
    "run": json.loads((EVAL / "last_run_report.json").read_text()),
    "tok": json.loads((EVAL / "figure_token_sweep.json").read_text()),
    "all987": json.loads((EVAL / "datasets" / "tawos_score_result.json").read_text()),
    "hold": json.loads((EVAL / "datasets" / "tawos_holdout_result.json").read_text()),
    "abl": json.loads((EVAL / "ablation_result.json").read_text()),
    "live": json.loads((EVAL / "live_llm_result_v3.json").read_text()),
}

# ---------------------------------------------------------------- styles
_ss = getSampleStyleSheet()
S = {
    "title": ParagraphStyle("t", parent=_ss["Title"], fontName="Helvetica-Bold",
                            fontSize=23, leading=28, textColor=BLUE, spaceAfter=4),
    "sub": ParagraphStyle("sub", parent=_ss["Normal"], fontName="Helvetica",
                          fontSize=11.5, leading=15, textColor=MUTED, alignment=TA_CENTER),
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=14.5, leading=18,
                         textColor=BLUE, spaceBefore=16, spaceAfter=7),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11, leading=14,
                         textColor=INK, spaceBefore=11, spaceAfter=5),
    "body": ParagraphStyle("b", fontName="Times-Roman", fontSize=9.6, leading=13.4,
                           textColor=INK, alignment=TA_JUSTIFY, spaceAfter=6),
    "bullet": ParagraphStyle("bu", fontName="Times-Roman", fontSize=9.6, leading=13.2,
                             textColor=INK, leftIndent=13, bulletIndent=3, spaceAfter=3),
    "cell": ParagraphStyle("c", fontName="Helvetica", fontSize=7.9, leading=10, textColor=INK),
    "cellb": ParagraphStyle("cb", fontName="Helvetica-Bold", fontSize=7.9, leading=10, textColor=INK),
    "hdr": ParagraphStyle("hd", fontName="Helvetica-Bold", fontSize=7.9, leading=10,
                          textColor=colors.white),
    "cap": ParagraphStyle("cap", fontName="Helvetica", fontSize=8.2, leading=11,
                          textColor=MUTED, alignment=TA_CENTER, spaceBefore=5, spaceAfter=10),
    "callout": ParagraphStyle("co", fontName="Times-Italic", fontSize=9.6, leading=13.4,
                              textColor=INK, leftIndent=9, rightIndent=9, spaceAfter=6),
    "note": ParagraphStyle("n", fontName="Helvetica", fontSize=8.3, leading=11.2,
                           textColor=MUTED, spaceAfter=6),
}


def P(t, s="body"):
    return Paragraph(t, S[s])


def bullets(items, style="bullet"):
    return [Paragraph(t, S[style], bulletText="•") for t in items]


def tbl(rows, widths, header=True, align_right=None, zebra=True):
    """rows[0] is the header. widths are fractions of CONTENT_W."""
    cw = [w * CONTENT_W for w in widths]
    data = []
    for r_i, row in enumerate(rows):
        out = []
        for c_i, cell in enumerate(row):
            if r_i == 0 and header:
                out.append(Paragraph(str(cell), S["hdr"]))
            else:
                bold = str(cell).startswith("**") and str(cell).endswith("**")
                txt = str(cell).strip("*")
                st = S["cellb"] if bold else S["cell"]
                if align_right and c_i in align_right:
                    st = ParagraphStyle(f"r{r_i}{c_i}", parent=st, alignment=2)
                out.append(Paragraph(txt, st))
        data.append(out)

    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, RULE),
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), BLUE),
                  ("TOPPADDING", (0, 0), (-1, 0), 4.5),
                  ("BOTTOMPADDING", (0, 0), (-1, 0), 4.5)]
        if zebra:
            for i in range(2, len(rows), 2):
                style.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    t = Table(data, colWidths=cw, repeatRows=1 if header else 0, hAlign="LEFT")
    t.setStyle(TableStyle(style))
    # A short table that splits across a page boundary leaves an orphaned row
    # under a repeated header, which reads as a stray fragment. Keep small
    # tables whole; long ones must still be allowed to break.
    if len(rows) <= 8:
        return KeepTogether(t)
    return t


def figure(svg_name, caption, max_w=None):
    d = svg2rlg(str(FIGS / svg_name))
    target = max_w or CONTENT_W
    sc = target / d.width
    d.width, d.height = d.width * sc, d.height * sc
    d.scale(sc, sc)
    d.hAlign = "CENTER"
    return KeepTogether([Spacer(1, 4), d, P(caption, "cap")])


def callout(text, accent=None):
    accent = accent or BLUE
    p = Paragraph(text, S["callout"])
    t = Table([[p]], colWidths=[CONTENT_W], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BAND),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, accent),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return KeepTogether([t, Spacer(1, 7)])


# ---------------------------------------------------------------- page furniture
def _chrome(canvas, doc, first=False):
    canvas.saveState()
    if not first:
        canvas.setFont("Helvetica", 7.3)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, PAGE_H - 26, "TeamSync AI - Project Report")
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 26,
                               "Graph-Grounded Multi-Agent Project Intelligence")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, PAGE_H - 31, PAGE_W - MARGIN, PAGE_H - 31)
    canvas.setFont("Helvetica", 7.6)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(PAGE_W / 2, 22, str(doc.page))
    canvas.restoreState()


def on_first(c, d): _chrome(c, d, first=True)
def on_later(c, d): _chrome(c, d, first=False)


def main() -> None:
    from eval.report_content import build_story
    from eval.report_content2 import build_story2

    doc = BaseDocTemplate(str(OUT), pagesize=A4,
                          leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=MARGIN, bottomMargin=MARGIN + 8,
                          title="TeamSync AI - Project Report",
                          author="TeamSync AI",
                          subject="Graph-Grounded Multi-Agent Project Intelligence")

    first_frame = Frame(MARGIN, MARGIN + 8, CONTENT_W,
                        PAGE_H - 2 * MARGIN - 8, id="first")
    later_frame = Frame(MARGIN, MARGIN + 8, CONTENT_W,
                        PAGE_H - 2 * MARGIN - 22, id="later")
    doc.addPageTemplates([
        PageTemplate(id="first", frames=[first_frame], onPage=on_first),
        PageTemplate(id="later", frames=[later_frame], onPage=on_later),
    ])

    story, data = build_story()
    story += build_story2(data)
    doc.build(story)
    size = OUT.stat().st_size
    print(f"wrote {OUT}  ({size:,} bytes)")


if __name__ == "__main__":
    main()
