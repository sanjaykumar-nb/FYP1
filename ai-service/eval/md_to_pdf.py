"""Render a Markdown document to a well-structured PDF.

Written for this project's reference documents (IEEE_PAPER_REPORT.md,
PROJECT_RESEARCH_DOSSIER.md), which are heavy on tables, nested lists, fenced
code, and mathematical/typographic Unicode.

Two things this handles that a naive converter does not:

1. UNICODE. ReportLab's built-in Type1 fonts use WinAnsi encoding, which has no
   glyph for the arrows, set operators, Greek letters and box-drawing characters
   these documents use throughout (-> x >= k D <-> o . etc.). Rendering with
   them silently produces black boxes. Real Unicode TTFs are registered instead,
   and anything still unmappable is transliterated rather than dropped.

2. MERMAID. Fenced ```mermaid blocks are diagram source, not code - printing the
   source verbatim in a PDF is noise. Where a caller supplies a figure mapping,
   the block is replaced by the corresponding pre-rendered SVG (vector); with no
   mapping it degrades to a labelled placeholder rather than raw source.

Usage:
    python -m eval.md_to_pdf INPUT.md OUTPUT.pdf ["Cover Title"]
"""

from __future__ import annotations

import html
import os
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak,
                                PageTemplate, Paragraph, Preformatted, Spacer, Table,
                                TableStyle)
from svglib.svglib import svg2rlg

# ---------------------------------------------------------------- fonts
_WF = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "Fonts"
_FONTS = {
    "Body": "times.ttf", "Body-B": "timesbd.ttf", "Body-I": "timesi.ttf",
    "Head": "arialbd.ttf", "Sans": "arial.ttf", "Sans-I": "ariali.ttf",
    "Mono": "consola.ttf",
}
BODY = HEAD = SANS = MONO = None


def _register_fonts():
    """Register Unicode TTFs; fall back to Type1 only if the system has none."""
    global BODY, HEAD, SANS, MONO
    try:
        for name, fn in _FONTS.items():
            pdfmetrics.registerFont(TTFont(name, str(_WF / fn)))
        pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-B",
                                      italic="Body-I", boldItalic="Body-B")
        BODY, HEAD, SANS, MONO = "Body", "Head", "Sans", "Mono"
    except Exception:
        BODY, HEAD, SANS, MONO = "Times-Roman", "Helvetica-Bold", "Helvetica", "Courier"


# Characters with no glyph even in the registered TTFs, or that simply read
# better transliterated in print.
_TRANSLIT = {
    "\u2500": "-", "\u2502": "|", "\u250c": "+", "\u2510": "+", "\u2514": "+",
    "\u2518": "+", "\u251c": "+", "\u2524": "+", "\u252c": "+", "\u2534": "+",
    "\u253c": "+", "\u25b6": ">", "\u25bc": "v", "\u2b1b": "#",
    # Verified absent from both Arial and Times: rendering these without a
    # mapping emits .notdef (a black box / NUL in extracted text).
    "\u2218": "o",   # RING OPERATOR (function composition) - "f o g" is the
                     # conventional ASCII rendering
}

BLUE = colors.HexColor("#1a5490")
INK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#5c5c5c")
RULE = colors.HexColor("#d0d7de")
BAND = colors.HexColor("#eef3f8")
ZEBRA = colors.HexColor("#f7f9fb")
CODEBG = colors.HexColor("#f4f6f8")

PAGE_W, PAGE_H = A4
MARGIN = 44
CONTENT_W = PAGE_W - 2 * MARGIN


def _clean(t: str) -> str:
    for k, v in _TRANSLIT.items():
        t = t.replace(k, v)
    return t


def inline(t: str) -> str:
    """Markdown inline -> ReportLab mini-HTML. Order matters: escape first, so
    that user text containing < or & cannot inject markup."""
    t = _clean(t)
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", lambda m: f'<font face="{MONO}" size="8.2">{m.group(1)}</font>', t)
    t = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*([^*\n]+?)\*(?![\w*])", r"<i>\1</i>", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)          # links -> plain text
    return t


_HEADING_STYLES = {"h1", "h2", "h3"}


class MarkdownPDF:
    def __init__(self, figure_map: dict[str, str] | None = None,
                 figures_dir: Path | None = None):
        _register_fonts()
        self.figure_map = figure_map or {}
        self.figures_dir = figures_dir
        self._mermaid_seen = 0
        self.S = {
            "title": ParagraphStyle("t", fontName=HEAD, fontSize=24, leading=29,
                                    textColor=BLUE, alignment=TA_CENTER, spaceAfter=6),
            "sub": ParagraphStyle("s", fontName=SANS, fontSize=11.5, leading=15,
                                  textColor=MUTED, alignment=TA_CENTER),
            # keepWithNext: a heading never sits alone at the foot of a page.
            "h1": ParagraphStyle("h1", fontName=HEAD, fontSize=15, leading=19,
                                 textColor=BLUE, spaceBefore=17, spaceAfter=7, keepWithNext=1),
            "h2": ParagraphStyle("h2", fontName=HEAD, fontSize=11.6, leading=15,
                                 textColor=INK, spaceBefore=12, spaceAfter=5, keepWithNext=1),
            "h3": ParagraphStyle("h3", fontName=HEAD, fontSize=10, leading=13,
                                 textColor=MUTED, spaceBefore=9, spaceAfter=4, keepWithNext=1),
            "body": ParagraphStyle("b", fontName=BODY, fontSize=9.7, leading=13.5,
                                   textColor=INK, alignment=TA_JUSTIFY, spaceAfter=6),
            "li": ParagraphStyle("li", fontName=BODY, fontSize=9.7, leading=13.2,
                                 textColor=INK, leftIndent=14, bulletIndent=4, spaceAfter=3),
            "quote": ParagraphStyle("q", fontName=BODY, fontSize=9.7, leading=13.5,
                                    textColor=INK, leftIndent=10, rightIndent=8, spaceAfter=5),
            "cell": ParagraphStyle("c", fontName=SANS, fontSize=7.9, leading=10, textColor=INK),
            "hdr": ParagraphStyle("hd", fontName=HEAD, fontSize=7.9, leading=10,
                                  textColor=colors.white),
            "cap": ParagraphStyle("cap", fontName=SANS, fontSize=8.2, leading=11,
                                  textColor=MUTED, alignment=TA_CENTER,
                                  spaceBefore=4, spaceAfter=10),
            "toc": ParagraphStyle("toc", fontName=SANS, fontSize=9.4, leading=15,
                                  textColor=INK, leftIndent=8),
        }

    # ---------------------------------------------------------------- blocks
    def _column_widths(self, rows) -> list[float]:
        """Give every column at least its longest word, so no word or number is
        split mid-token (\"Precisio / n\"); share the remaining width by how much
        longer each column's full text is. Only when even the longest words cannot
        fit side by side is every column scaled down."""
        pad = 13  # left + right cell padding, plus slack for bold text
        size = self.S["cell"].fontSize
        mins, prefs = [], []
        for c in range(len(rows[0])):
            word = line = 0.0
            for i, row in enumerate(rows):
                font = HEAD if i == 0 else SANS
                text = _clean(re.sub(r"[*`\[\]]", "", row[c]))
                for w in text.split():
                    word = max(word, pdfmetrics.stringWidth(w, font, size))
                line = max(line, pdfmetrics.stringWidth(text, font, size))
            mins.append(word + pad)
            # Cap prose so one long column cannot squeeze the rest.
            prefs.append(max(word, min(line, CONTENT_W * 0.6)) + pad)

        spare = CONTENT_W - sum(mins)
        if spare <= 0:
            return [m / sum(mins) * CONTENT_W for m in mins]
        want = [p - m for p, m in zip(prefs, mins)]
        if sum(want) <= spare:
            # Every cell fits on one line; spread what is left in proportion to width.
            left = spare - sum(want)
            return [p + left * p / sum(prefs) for p in prefs]
        return [m + spare * w / sum(want) for m, w in zip(mins, want)]

    def _table(self, rows):
        ncol = max(len(r) for r in rows)
        rows = [r + [""] * (ncol - len(r)) for r in rows]
        widths = self._column_widths(rows)

        data = [[Paragraph(inline(c), self.S["hdr" if i == 0 else "cell"])
                 for c in row] for i, row in enumerate(rows)]
        style = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("BACKGROUND", (0, 0), (-1, 0), BLUE),
            ("LINEBELOW", (0, 0), (-1, -2), 0.3, RULE),
            ("BOX", (0, 0), (-1, -1), 0.5, RULE),
        ]
        for i in range(2, len(rows), 2):
            style.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
        t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle(style))
        return t

    def _code(self, lines, lang):
        # Mermaid is diagram source: swap in the pre-rendered vector figure.
        if lang == "mermaid":
            self._mermaid_seen += 1
            key = f"mermaid{self._mermaid_seen}"
            svg = self.figure_map.get(key)
            if svg and self.figures_dir and (self.figures_dir / svg).exists():
                d = svg2rlg(str(self.figures_dir / svg))
                sc = CONTENT_W / d.width
                d.width, d.height = d.width * sc, d.height * sc
                d.scale(sc, sc)
                d.hAlign = "CENTER"
                return KeepTogether([Spacer(1, 4), d,
                                     Paragraph(f"Figure {self._mermaid_seen}", self.S["cap"])])
            return Paragraph(f"[diagram: {key}]", self.S["cap"])

        body = _clean("\n".join(lines)) or " "
        pre = Preformatted(body, ParagraphStyle(
            "code", fontName=MONO, fontSize=7.4, leading=9.4, textColor=INK))
        t = Table([[pre]], colWidths=[CONTENT_W], hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CODEBG),
            ("BOX", (0, 0), (-1, -1), 0.5, RULE),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return KeepTogether([t, Spacer(1, 7)])

    def _quote(self, lines):
        p = Paragraph(inline(" ".join(lines)), self.S["quote"])
        t = Table([[p]], colWidths=[CONTENT_W], hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BAND),
            ("LINEBEFORE", (0, 0), (0, -1), 2.5, BLUE),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        return KeepTogether([t, Spacer(1, 7)])

    # ---------------------------------------------------------------- parse
    def parse(self, md: str):
        lines = md.split("\n")
        story, headings = [], []
        i, para, n = 0, [], len(lines)

        def flush():
            if para:
                story.append(Paragraph(inline(" ".join(para)), self.S["body"]))
                para.clear()

        while i < n:
            ln = lines[i]
            st = ln.strip()

            if st.startswith("```"):
                flush()
                lang = st[3:].strip().lower()
                i += 1
                buf = []
                while i < n and not lines[i].strip().startswith("```"):
                    buf.append(lines[i]); i += 1
                i += 1
                story.append(self._code(buf, lang)); continue

            if not st:
                flush(); i += 1; continue

            if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", st):
                flush()
                story.append(Spacer(1, 3))
                t = Table([[""]], colWidths=[CONTENT_W], rowHeights=[0.6], hAlign="LEFT")
                t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), RULE)]))
                story += [t, Spacer(1, 7)]; i += 1; continue

            m = re.match(r"^(#{1,4})\s+(.*)", st)
            if m:
                flush()
                lvl, txt = len(m.group(1)), m.group(2).strip()
                if lvl == 1:
                    story.append(Paragraph(inline(txt), self.S["h1"]))
                else:
                    key = {2: "h1", 3: "h2", 4: "h3"}[min(lvl, 4)]
                    story.append(Paragraph(inline(txt), self.S[key]))
                    if lvl == 2:
                        headings.append(txt)
                i += 1; continue

            # pipe table: header row followed by a |---| separator
            if st.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|-]+\|?$", lines[i + 1].strip()):
                flush()
                rows = []
                for r in (st, *lines[i + 2:]):
                    rs = r.strip() if isinstance(r, str) else ""
                    if not rs.startswith("|"):
                        break
                    rows.append([c.strip() for c in rs.strip("|").split("|")])
                    if r is not st:
                        i += 1
                i += 2
                table = self._table(rows)
                if len(rows) <= 8:
                    # Small tables never split across pages. A heading directly before one
                    # travels in the same KeepTogether: keepWithNext cannot merge a heading
                    # into a KeepTogether, and nesting KeepTogethers forces a page break
                    # before every one (its wrap reports an effectively infinite height).
                    prev = story[-1] if story else None
                    if isinstance(prev, Paragraph) and prev.style.name in _HEADING_STYLES:
                        story[-1] = KeepTogether([prev, table])
                    else:
                        story.append(KeepTogether(table))
                else:
                    story.append(table)
                story.append(Spacer(1, 8)); continue

            if st.startswith(">"):
                flush()
                buf = []
                while i < n and lines[i].strip().startswith(">"):
                    buf.append(lines[i].strip().lstrip(">").strip()); i += 1
                story.append(self._quote(buf)); continue

            m = re.match(r"^([-*+]|\d+[.)])\s+(.*)", st)
            if m:
                flush()
                indent = len(ln) - len(ln.lstrip())
                bullet = "\u2022" if m.group(1) in "-*+" else m.group(1)
                txt = [m.group(2)]
                i += 1
                while i < n:
                    nx = lines[i]
                    if nx.strip() and not re.match(r"^\s*([-*+]|\d+[.)])\s+", nx) \
                       and (len(nx) - len(nx.lstrip())) > indent:
                        txt.append(nx.strip()); i += 1
                    else:
                        break
                stl = ParagraphStyle(f"li{indent}", parent=self.S["li"],
                                     leftIndent=14 + indent * 8,
                                     bulletIndent=4 + indent * 8)
                story.append(Paragraph(inline(" ".join(txt)), stl, bulletText=bullet))
                continue

            para.append(st); i += 1

        flush()
        return story, headings


def build(md_path: Path, out_path: Path, title: str | None = None,
          subtitle: str | None = None, figure_map=None, figures_dir=None):
    conv = MarkdownPDF(figure_map, figures_dir)
    raw = md_path.read_text(encoding="utf-8")

    # The source docs open with an H1 + lede + an inline "Contents:" line; the
    # PDF gets a proper cover and generated TOC instead, so strip them.
    lines = raw.split("\n")
    doc_title = title or next((l[2:].strip() for l in lines if l.startswith("# ")), md_path.stem)
    body = "\n".join(l for l in lines
                     if not l.startswith("# ") and not l.strip().startswith("**Contents:**"))
    body = re.sub(r"\n\[\d+\..*?\)\s*·?", "", body)

    story, headings = conv.parse(body)

    cover = [Spacer(1, 150),
             Paragraph(inline(doc_title), conv.S["title"]),
             Spacer(1, 8)]
    if subtitle:
        cover.append(Paragraph(inline(subtitle), conv.S["sub"]))
    cover.append(Spacer(1, 26))
    if headings:
        cover.append(Paragraph("Contents", conv.S["h2"]))
        for h in headings:
            cover.append(Paragraph(inline(h), conv.S["toc"]))
    cover.append(PageBreak())

    doc = BaseDocTemplate(str(out_path), pagesize=A4,
                          leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=MARGIN, bottomMargin=MARGIN + 6,
                          title=_clean(doc_title).encode("ascii", "replace").decode(),
                          author="TeamSync AI")

    def chrome(canvas, d):
        canvas.saveState()
        if d.page > 1:
            canvas.setFont(SANS, 7.3); canvas.setFillColor(MUTED)
            canvas.drawString(MARGIN, PAGE_H - 27, _clean(doc_title)[:70])
            canvas.setStrokeColor(RULE); canvas.setLineWidth(0.5)
            canvas.line(MARGIN, PAGE_H - 32, PAGE_W - MARGIN, PAGE_H - 32)
        canvas.setFont(SANS, 7.6); canvas.setFillColor(MUTED)
        canvas.drawCentredString(PAGE_W / 2, 22, str(d.page))
        canvas.restoreState()

    frame = Frame(MARGIN, MARGIN + 6, CONTENT_W, PAGE_H - 2 * MARGIN - 20, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=chrome)])
    doc.build(cover + story)
    return out_path


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    title = sys.argv[3] if len(sys.argv) > 3 else None
    figs = Path(__file__).parent / "figures"
    fmap = {"mermaid1": "fig0_topology.svg", "mermaid2": "fig1_architecture.svg"}
    build(src, dst, title, figure_map=fmap, figures_dir=figs)
    print(f"wrote {dst}  ({dst.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
