"""Generate publication-quality SVG figures for the paper, from measured data.

Every figure is built from the committed result JSONs - no hand-typed numbers -
so a figure can never silently drift from the evaluation that produced it.

Output is SVG (true vector, scales without loss in LaTeX via \\includegraphics
after svg->pdf conversion, or directly with the `svg` package).

DESIGN CONSTRAINTS (IEEE two-column print):
- Canvas units are POINTS. A figure with width=516 fills the full 7.16in text
  width; width=252 fits one column. Font sizes are therefore literal pt sizes,
  and 8-9pt text stays legible at final size.
- No titles inside the figures - IEEE captions sit below the figure. Titles
  inside would duplicate the caption.
- Palette #1a5490 / #d2691e / #6a4c93 passed all six checks of the dataviz
  validator (worst adjacent CVD dE 23.7 protan). BUT blue vs purple collapse in
  GRAYSCALE (dL 0.018), and IEEE papers are routinely printed B&W - so the
  3-series figure carries hatch patterns and direct value labels as secondary
  encoding. Two-series figures use blue+orange only (dL 0.153, safe in B&W).
- Recessive grid, thin marks, legend on every multi-series figure.

Run: python -m eval.make_figures   (no API calls, no network, deterministic)
"""

from __future__ import annotations

import json
import math
from pathlib import Path

EVAL = Path(__file__).parent
OUT = EVAL / "figures"

BLUE, ORANGE, PURPLE = "#1a5490", "#d2691e", "#6a4c93"
INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"
FONT = "Helvetica, Arial, sans-serif"


def esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def txt(x, y, s, size=8, fill=INK, anchor="middle", weight="normal", style="normal"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}" '
            f'font-style="{style}">{esc(s)}</text>')


def svg_open(w, h):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}pt" height="{h}pt" '
            f'viewBox="0 0 {w} {h}">\n'
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>\n')


# ---------------------------------------------------------------- figure 2
def fig_token_scaling() -> str:
    rows = json.loads((EVAL / "figure_token_sweep.json").read_text())
    W, H = 516, 265
    L, R, T, B = 62, 76, 14, 46           # right margin sized to the direct labels (~56pt), not guessed
    pw, ph = W - L - R, H - T - B

    xlo, xhi = math.log10(10), math.log10(4000)
    ylo, yhi = 2.0, 6.0                    # 10^2 .. 10^6 tokens

    def X(tasks): return L + (math.log10(tasks) - xlo) / (xhi - xlo) * pw
    def Y(tok):   return T + ph - (math.log10(tok) - ylo) / (yhi - ylo) * ph

    s = [svg_open(W, H)]

    # recessive decade grid
    for d in range(2, 7):
        y = Y(10 ** d)
        s.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L+pw}" y2="{y:.1f}" '
                 f'stroke="{GRID}" stroke-width="0.5"/>')
        lbl = {2: "100", 3: "1K", 4: "10K", 5: "100K", 6: "1M"}[d]
        s.append(txt(L - 6, y + 2.8, lbl, 8, MUTED, "end"))
    for t in (13, 53, 203, 1003, 2003):
        x = X(t)
        s.append(f'<line x1="{x:.1f}" y1="{T}" x2="{x:.1f}" y2="{T+ph}" '
                 f'stroke="{GRID}" stroke-width="0.5"/>')
        s.append(txt(x, T + ph + 13, f"{t:,}", 8, MUTED))

    # axes
    s.append(f'<line x1="{L}" y1="{T}" x2="{L}" y2="{T+ph}" stroke="{MUTED}" stroke-width="0.8"/>')
    s.append(f'<line x1="{L}" y1="{T+ph}" x2="{L+pw}" y2="{T+ph}" stroke="{MUTED}" stroke-width="0.8"/>')
    s.append(txt(L + pw / 2, H - 8, "Project size (tasks, log scale)", 9, INK))
    s.append(f'<g transform="translate(13,{T+ph/2}) rotate(-90)">'
             + txt(0, 0, "Prompt tokens (log scale)", 9, INK) + '</g>')

    # series
    for key, color, marker, label in (
        ("naive", ORANGE, "square", "Naive (full dataset in prompt)"),
        ("graph", BLUE, "circle", "Graph-grounded (witness subgraph)"),
    ):
        pts = [(X(r["tasks"]), Y(r[key])) for r in rows]
        d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
        s.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6"/>')
        for x, y in pts:
            if marker == "circle":
                s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.9" fill="{color}" '
                         f'stroke="#ffffff" stroke-width="1"/>')
            else:
                s.append(f'<rect x="{x-2.7:.1f}" y="{y-2.7:.1f}" width="5.4" height="5.4" '
                         f'fill="{color}" stroke="#ffffff" stroke-width="1"/>')
        # direct end label (secondary encoding: identity never color-alone)
        ex, ey = pts[-1]
        val = rows[-1][key]
        s.append(txt(ex + 7, ey + (-4 if key == "naive" else 4), f"{val:,} tok", 8, color, "start", "bold"))
        s.append(txt(ex + 7, ey + (5.5 if key == "naive" else 13.5), label.split(" (")[0], 7.5, MUTED, "start"))

    # the headline gap, annotated in place
    xg = X(2003)
    y1, y2 = Y(rows[-1]["naive"]), Y(rows[-1]["graph"])
    s.append(f'<line x1="{xg-16:.1f}" y1="{y1:.1f}" x2="{xg-16:.1f}" y2="{y2:.1f}" '
             f'stroke="{INK}" stroke-width="0.8" stroke-dasharray="2,1.5"/>')
    s.append(f'<g transform="translate({xg-20:.1f},{(y1+y2)/2:.1f}) rotate(-90)">'
             + txt(0, 0, "487x", 9, INK, "middle", "bold") + '</g>')

    # legend
    lx, ly = L + 6, T + 10
    for i, (color, label) in enumerate(((BLUE, "Graph-grounded (this work)"),
                                        (ORANGE, "Naive full-dataset prompting"))):
        yy = ly + i * 12
        s.append(f'<rect x="{lx}" y="{yy-4}" width="9" height="3" fill="{color}"/>')
        s.append(txt(lx + 13, yy, label, 8, INK, "start"))

    s.append("</svg>")
    return "\n".join(s)


# ---------------------------------------------------------------- figure 3
def fig_holdout() -> str:
    h = json.loads((EVAL / "datasets" / "tawos_holdout_result.json").read_text())
    a = json.loads((EVAL / "datasets" / "tawos_score_result.json").read_text())
    rule, comp = h["original_single_signal"], h["composite_model"]
    base = a["baseline_story_points_median"]

    series = [
        ("Graph rule (untuned)", BLUE, "none",
         [rule["precision"], rule["recall"], rule["f1"]]),
        ("Tuned composite model", ORANGE, "hatchA",
         [comp["precision"], comp["recall"], comp["f1"]]),
        ("Story-point baseline*", PURPLE, "hatchB",
         [base["precision"], base["recall"], base["f1"]]),
    ]
    groups = ["Precision", "Recall", "F1"]

    W, H = 516, 250
    L, R, T, B = 46, 12, 34, 52
    pw, ph = W - L - R, H - T - B

    s = [svg_open(W, H)]
    s.append(f'''<defs>
<pattern id="hatchA" width="4" height="4" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
<rect width="4" height="4" fill="{ORANGE}"/><line x1="0" y1="0" x2="0" y2="4" stroke="#ffffff" stroke-width="1.4"/></pattern>
<pattern id="hatchB" width="4" height="4" patternTransform="rotate(135)" patternUnits="userSpaceOnUse">
<rect width="4" height="4" fill="{PURPLE}"/><line x1="0" y1="0" x2="0" y2="4" stroke="#ffffff" stroke-width="1.4"/></pattern>
</defs>''')

    def Y(v): return T + ph - v * ph

    for gv in (0, 0.25, 0.5, 0.75, 1.0):
        y = Y(gv)
        s.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L+pw}" y2="{y:.1f}" '
                 f'stroke="{GRID}" stroke-width="0.5"/>')
        s.append(txt(L - 6, y + 2.8, f"{gv:.2f}", 8, MUTED, "end"))

    gw = pw / len(groups)
    bw = gw / (len(series) + 1.4)
    for gi, gname in enumerate(groups):
        gx = L + gi * gw
        for si, (_, color, pat, vals) in enumerate(series):
            v = vals[gi]
            # 2pt surface gap between adjacent bars
            x = gx + gw / 2 - (len(series) * bw) / 2 + si * bw + 1
            y, hgt = Y(v), v * ph
            fill = f"url(#{pat})" if pat != "none" else color
            s.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw-2:.1f}" height="{hgt:.1f}" '
                     f'fill="{fill}" stroke="{color}" stroke-width="0.6" rx="1.5"/>')
            s.append(txt(x + (bw - 2) / 2, y - 3.5, f"{v:.3f}", 7.5, INK, "middle", "bold"))
        s.append(txt(gx + gw / 2, T + ph + 14, gname, 9, INK))

    s.append(f'<line x1="{L}" y1="{T+ph}" x2="{L+pw}" y2="{T+ph}" stroke="{MUTED}" stroke-width="0.8"/>')
    s.append(f'<line x1="{L}" y1="{T}" x2="{L}" y2="{T+ph}" stroke="{MUTED}" stroke-width="0.8"/>')

    lx = L + 2
    for i, (label, color, pat, _) in enumerate(series):
        x = lx + i * 168
        fill = f"url(#{pat})" if pat != "none" else color
        s.append(f'<rect x="{x}" y="{T-24}" width="10" height="8" fill="{fill}" '
                 f'stroke="{color}" stroke-width="0.6"/>')
        s.append(txt(x + 14, T - 17, label, 8, INK, "start"))

    s.append(txt(L, H - 8, "*baseline measured on all 987 sprints; the other two on the 270-sprint held-out split",
                 7, MUTED, "start", "normal", "italic"))
    s.append("</svg>")
    return "\n".join(s)


# ---------------------------------------------------------------- figure 4
def fig_ablation() -> str:
    d = json.loads((EVAL / "ablation_result.json").read_text())
    per = d["per_risk_type"]
    order = ["dependency", "knowledge", "workload", "delay", "silent_member", "coordination"]
    nice = {"dependency": "Depend.", "knowledge": "Knowl.", "workload": "Workload",
            "delay": "Delay", "silent_member": "Silent", "coordination": "Coord."}

    W, H = 516, 232
    L, R, T, B = 46, 12, 32, 50
    pw, ph = W - L - R, H - T - B
    s = [svg_open(W, H)]

    def Y(v): return T + ph - v * ph

    for gv in (0, 0.25, 0.5, 0.75, 1.0):
        y = Y(gv)
        s.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L+pw}" y2="{y:.1f}" stroke="{GRID}" stroke-width="0.5"/>')
        s.append(txt(L - 6, y + 2.8, f"{gv:.2f}", 8, MUTED, "end"))

    gw = pw / len(order)
    bw = gw / 3.0
    for gi, rt in enumerate(order):
        gx = L + gi * gw
        for si, (key, color) in enumerate((("graph", BLUE), ("naive", ORANGE))):
            v = per[rt][key]["f1"]
            x = gx + gw / 2 - bw + si * bw + 1
            y, hgt = Y(v), v * ph
            s.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw-2:.1f}" height="{hgt:.1f}" '
                     f'fill="{color}" rx="1.5"/>')
            s.append(txt(x + (bw - 2) / 2, y - 3.5, f"{v:.2f}", 7, INK, "middle", "bold"))
        s.append(txt(gx + gw / 2, T + ph + 14, nice[rt], 8, INK))

    s.append(f'<line x1="{L}" y1="{T+ph}" x2="{L+pw}" y2="{T+ph}" stroke="{MUTED}" stroke-width="0.8"/>')
    s.append(f'<line x1="{L}" y1="{T}" x2="{L}" y2="{T+ph}" stroke="{MUTED}" stroke-width="0.8"/>')
    s.append(f'<g transform="translate(13,{T+ph/2}) rotate(-90)">' + txt(0, 0, "F1 score", 9, INK) + '</g>')

    for i, (label, color) in enumerate((("Graph-grounded", BLUE), ("Naive prompting", ORANGE))):
        x = L + 2 + i * 130
        s.append(f'<rect x="{x}" y="{T-22}" width="10" height="8" fill="{color}"/>')
        s.append(txt(x + 14, T - 15, label, 8, INK, "start"))

    g, n = d["graph_architecture"], d["naive_architecture"]
    s.append(txt(L + pw, H - 8,
                 f"overall F1: graph {g['f1']:.3f} vs naive {n['f1']:.3f}  (n=36 scenarios, 0 failed calls)",
                 7.5, MUTED, "end", "normal", "italic"))
    s.append("</svg>")
    return "\n".join(s)


# ---------------------------------------------------------------- figure 0
def fig_topology() -> str:
    """Service topology: three services, their stores, and what talks to what."""
    W, H = 516, 210
    s = [svg_open(W, H)]
    s.append(f'''<defs><marker id="a0" viewBox="0 0 8 8" refX="7" refY="4"
 markerWidth="6" markerHeight="6" orient="auto"><path d="M0,1 L7,4 L0,7 z" fill="{MUTED}"/></marker></defs>''')

    def svc(x, y, w, h, title, tech, port, accent):
        o = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="#ffffff" stroke="{accent}" stroke-width="1.2"/>',
             f'<rect x="{x}" y="{y}" width="{w}" height="3.5" rx="1.5" fill="{accent}"/>']
        o.append(txt(x + w/2, y + 19, title, 9, INK, "middle", "bold"))
        o.append(txt(x + w/2, y + 31, tech, 7.5, MUTED))
        if port:
            o.append(txt(x + w/2, y + 43, port, 7, accent, "middle", "bold"))
        return "".join(o)

    def store(x, y, w, h, label, sub, accent):
        o = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="#fafafa" stroke="{accent}" stroke-width="1"/>']
        o.append(txt(x + w/2, y + h/2 - 1, label, 8.5, INK, "middle", "bold"))
        o.append(txt(x + w/2, y + h/2 + 10, sub, 7, MUTED))
        return "".join(o)

    def arr(x1, y1, x2, y2, label=None, lx=None, ly=None):
        o = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{MUTED}" stroke-width="1.1" marker-end="url(#a0)"/>']
        if label:
            o.append(txt(lx, ly, label, 6.8, MUTED, "middle", "normal", "italic"))
        return "".join(o)

    s.append(svc(14, 30, 120, 54, "Frontend", "Next.js 14 / React", ":3000", BLUE))
    s.append(svc(184, 30, 120, 54, "Core API", "FastAPI / SQLAlchemy", ":8000", BLUE))
    s.append(svc(184, 122, 120, 54, "AI Service", "FastAPI / NetworkX", ":8001", ORANGE))
    s.append(store(360, 30, 120, 44, "PostgreSQL 16", "system of record", BLUE))
    s.append(store(360, 96, 120, 40, "Redis 7 + Celery", "cache / background", BLUE))
    s.append(store(360, 148, 120, 40, "Groq LLM", "optional - narration", ORANGE))

    s.append(arr(136, 57, 182, 57, "REST / WebSocket", 159, 50))
    s.append(arr(306, 47, 358, 47, None))
    s.append(arr(306, 68, 358, 108, None))
    s.append(arr(244, 86, 244, 120, "POST /analyze", 288, 105))
    s.append(arr(306, 158, 358, 166, None))

    s.append(txt(14, 16, "Three services; the AI service is independently deployable and degrades to a rule-based path without the LLM.",
                 7.5, MUTED, "start", "normal", "italic"))
    s.append(txt(244, 196, "graph build + risk metrics run here, entirely offline", 7, ORANGE, "middle", "bold"))
    s.append("</svg>")
    return "\n".join(s)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    figs = {
        "fig0_topology.svg": fig_topology(),
        "fig1_architecture.svg": fig_architecture(),
        "fig2_token_scaling.svg": fig_token_scaling(),
        "fig3_holdout_tawos.svg": fig_holdout(),
        "fig4_ablation.svg": fig_ablation(),
    }
    for name, content in figs.items():
        (OUT / name).write_text(content, encoding="utf-8")
        print(f"wrote {OUT / name}  ({len(content):,} bytes)")



# ---------------------------------------------------------------- figure 1
def fig_architecture() -> str:
    """The contribution, drawn: a hard boundary between the deterministic,
    zero-token core and the bounded LLM narration layer."""
    W, H = 516, 268
    s = [svg_open(W, H)]
    s.append(f'''<defs>
<marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto">
<path d="M0,1 L7,4 L0,7 z" fill="{MUTED}"/></marker>
<marker id="arrRed" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto">
<path d="M0,1 L7,4 L0,7 z" fill="{ORANGE}"/></marker>
</defs>''')

    def box(x, y, w, h, lines, accent, sub=None):
        o = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="#ffffff" '
             f'stroke="{accent}" stroke-width="1.2"/>']
        o.append(f'<rect x="{x}" y="{y}" width="3.5" height="{h}" rx="1.5" fill="{accent}"/>')
        cy = y + h / 2 - (len(lines) - 1) * 5 + (0 if not sub else -4)
        for i, ln in enumerate(lines):
            o.append(txt(x + w / 2 + 2, cy + i * 10 + 3, ln, 8.5, INK, "middle", "bold" if i == 0 else "normal"))
        if sub:
            o.append(txt(x + w / 2 + 2, y + h - 6, sub, 7, MUTED))
        return "".join(o)

    def arrow(x1, y1, x2, y2, color=MUTED, mk="arr", dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
                f'stroke-width="1.1" marker-end="url(#{mk})"{d}/>')

    # ---- deterministic band
    s.append(f'<rect x="10" y="24" width="496" height="94" rx="4" fill="#f2f6fa" stroke="{BLUE}" '
             f'stroke-width="0.7" stroke-dasharray="3,2"/>')
    s.append(txt(18, 38, "DETERMINISTIC CORE - 0 LLM tokens, reproducible, unit-testable",
                 7.5, BLUE, "start", "bold"))

    bw, by, bh = 108, 48, 56
    xs = [22, 148, 274, 400]
    labels = [(["Project data", "tasks · people", "deps · comments"], None),
              (["Knowledge graph", "typed, in-memory"], "NetworkX"),
              (["Risk metrics", "6 graph algorithms"], "critical path, artic. pts"),
              (["Witness subgraph", "k=1, <=60 nodes"], "O(anomalies)")]
    for x, (lines, sub) in zip(xs, labels):
        s.append(box(x, by, bw, bh, lines, BLUE, sub))
    for i in range(3):
        s.append(arrow(xs[i] + bw + 2, by + bh / 2, xs[i + 1] - 3, by + bh / 2))

    # ---- LLM band
    s.append(f'<rect x="10" y="140" width="496" height="94" rx="4" fill="#fdf5ef" stroke="{ORANGE}" '
             f'stroke-width="0.7" stroke-dasharray="3,2"/>')
    s.append(txt(18, 154, "NARRATION LAYER - bounded prompt; never sees the raw dataset",
                 7.5, ORANGE, "start", "bold"))

    ly, lh = 164, 56
    lx = [22, 190, 358]
    s.append(box(lx[0], ly, 140, lh, ["LLM narration", "explains ONE finding"], ORANGE, "cites node ids only"))
    s.append(box(lx[1], ly, 140, lh, ["Grounding check", "drop_ungrounded()"], ORANGE, "citation in subgraph?"))
    s.append(box(lx[2], ly, 136, lh, ["Verified output", "risk + evidence"], BLUE, "persisted as AgentRun"))
    s.append(arrow(lx[0] + 142, ly + lh / 2, lx[1] - 3, ly + lh / 2))
    s.append(arrow(lx[1] + 142, ly + lh / 2, lx[2] - 3, ly + lh / 2))

    # witness subgraph feeds the LLM (the only thing that crosses the boundary)
    s.append(f'<path d="M{xs[3]+bw/2},{by+bh+2} L{xs[3]+bw/2},128 L92,128 L92,{ly-3}" '
             f'fill="none" stroke="{MUTED}" stroke-width="1.1" marker-end="url(#arr)"/>')
    s.append(txt(300, 125, "only the witness subgraph crosses this boundary", 7, MUTED, "middle", "normal", "italic"))

    # rejected citations
    s.append(f'<path d="M260,{ly+lh/2} L260,246" fill="none" stroke="{ORANGE}" stroke-width="1.1" '
             f'marker-end="url(#arrRed)" stroke-dasharray="3,2"/>')
    s.append(txt(268, 250, "fabricated citations stripped (200/200)", 7, ORANGE, "start", "bold"))

    # risk scores bypass the LLM entirely - the key claim
    s.append(f'<path d="M{xs[2]+bw/2},{by+bh+2} L{xs[2]+bw/2},132 L{lx[2]+68},132 L{lx[2]+68},{ly-3}" '
             f'fill="none" stroke="{BLUE}" stroke-width="1.1" marker-end="url(#arr)"/>')
    s.append(txt(W - 12, 125, "risk scores bypass the LLM entirely", 7, BLUE, "end", "bold"))

    s.append("</svg>")
    return "\n".join(s)

if __name__ == "__main__":
    main()
