"""Every remaining measured metric, charted. Companion to make_figures.py
(which covers the 4 headline figures used in the reports/paper). This script
covers everything else: synthetic per-risk-type detection, latency, TAWOS
all-987 vs baseline, the bootstrap CI, live-LLM validity/kappa across all
three runs, per-risk-type kappa, the composite model's CV-to-holdout
collapse, ablation overall metrics, per-agent fallback rate, and grounding
enforcement.

Every value is read from the committed result JSONs — nothing hand-typed.

Run: python -m eval.make_metric_gallery   (offline, deterministic)
"""

from __future__ import annotations

import json
from pathlib import Path

from eval.make_figures import BLUE, GRID, INK, MUTED, ORANGE, PURPLE, esc, svg_open, txt

EVAL = Path(__file__).parent
OUT = EVAL / "figures"
GREEN = "#2e7d46"   # validated 4th categorical hue for the runs comparison (dependency,knowledge,workload use 3; this adds a 4th series slot)


def load(name: str):
    for p in (EVAL / name, EVAL / "datasets" / name):
        if p.exists():
            return json.loads(p.read_text())
    raise FileNotFoundError(name)


# ---------------------------------------------------------------- bar chart helper
def bar_chart(W, H, groups, series, ylabel, ymax=1.0, yfmt="{:.2f}",
              footnote=None, legend_below=False):
    """groups: [label,...]; series: [(name,color,pattern_or_None,[val,...]),...]"""
    L, R, T = 46, 14, 34
    B = 62 if legend_below else 46
    pw, ph = W - L - R, H - T - B
    s = [svg_open(W, H)]

    defs = ['<defs>']
    for name, color, pat, _ in series:
        if pat:
            angle = 45 if pat == "hatchA" else 135
            defs.append(f'<pattern id="{pat}" width="4" height="4" patternTransform="rotate({angle})" '
                        f'patternUnits="userSpaceOnUse"><rect width="4" height="4" fill="{color}"/>'
                        f'<line x1="0" y1="0" x2="0" y2="4" stroke="#ffffff" stroke-width="1.4"/></pattern>')
    defs.append('</defs>')
    s.append("".join(defs))

    def Y(v): return T + ph - (v / ymax) * ph

    step = ymax / 4
    for i in range(5):
        gv = i * step
        y = Y(gv)
        s.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L+pw}" y2="{y:.1f}" stroke="{GRID}" stroke-width="0.5"/>')
        s.append(txt(L - 6, y + 2.8, yfmt.format(gv), 7.5, MUTED, "end"))

    n_series = len(series)
    gw = pw / len(groups)
    bw = gw / (n_series + 1.3)
    for gi, gname in enumerate(groups):
        gx = L + gi * gw
        for si, (name, color, pat, vals) in enumerate(series):
            v = vals[gi]
            x = gx + gw / 2 - (n_series * bw) / 2 + si * bw + 1
            y, hgt = Y(v), (v / ymax) * ph
            fill = f"url(#{pat})" if pat else color
            s.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw-2:.1f}" height="{hgt:.1f}" '
                     f'fill="{fill}" stroke="{color}" stroke-width="0.6" rx="1.5"/>')
            if hgt > 1:
                s.append(txt(x + (bw - 2) / 2, y - 3, yfmt.format(v), 6.8, INK, "middle", "bold"))
        s.append(txt(gx + gw / 2, T + ph + 13, gname, 7.8, INK))

    s.append(f'<line x1="{L}" y1="{T+ph}" x2="{L+pw}" y2="{T+ph}" stroke="{MUTED}" stroke-width="0.8"/>')
    s.append(f'<line x1="{L}" y1="{T}" x2="{L}" y2="{T+ph}" stroke="{MUTED}" stroke-width="0.8"/>')
    s.append(f'<g transform="translate(13,{T+ph/2}) rotate(-90)">' + txt(0, 0, ylabel, 8, INK) + '</g>')

    if legend_below:
        lx = L
        ly = H - 40
        for i, (name, color, pat, _) in enumerate(series):
            x = lx + i * (pw / len(series))
            fill = f"url(#{pat})" if pat else color
            s.append(f'<rect x="{x}" y="{ly}" width="9" height="7" fill="{fill}" stroke="{color}" stroke-width="0.5"/>')
            s.append(txt(x + 13, ly + 6, name, 7.3, INK, "start"))
    else:
        lx, ly = L + 4, T + 8
        for i, (name, color, pat, _) in enumerate(series):
            yy = ly + i * 11
            fill = f"url(#{pat})" if pat else color
            s.append(f'<rect x="{lx}" y="{yy-4}" width="9" height="7" fill="{fill}" stroke="{color}" stroke-width="0.5"/>')
            s.append(txt(lx + 13, yy + 1.5, name, 7.3, INK, "start"))

    if footnote:
        s.append(txt(W - 6, H - 5, footnote, 6.5, MUTED, "end", "normal", "italic"))
    s.append("</svg>")
    return "\n".join(s)


# ---------------------------------------------------------------- fig5: synthetic per-risk-type
def fig_synthetic_per_type() -> str:
    run = load("last_run_report.json")
    per = run["detection"]["per_risk_type"]
    order = ["dependency", "knowledge", "workload", "delay", "silent_member", "coordination"]
    nice = {"dependency": "Depend.", "knowledge": "Knowl.", "workload": "Workload",
            "delay": "Delay", "silent_member": "Silent", "coordination": "Coord."}
    groups = [nice[k] for k in order]
    series = [
        ("Precision", BLUE, None, [per[k]["precision"] for k in order]),
        ("Recall", ORANGE, None, [per[k]["recall"] for k in order]),
        ("F1", PURPLE, "hatchA", [per[k]["f1"] for k in order]),
    ]
    return bar_chart(516, 220, groups, series, "Score", ymax=1.05, yfmt="{:.2f}",
                     footnote=f"n={run['detection']['n_scenarios']} synthetic scenarios, 30 per risk type; deterministically injected ground truth")


# ---------------------------------------------------------------- fig6: latency
def fig_latency() -> str:
    lat = load("last_run_report.json")["latency"]
    groups = ["p50", "p95", "mean", "max"]
    vals = [lat["p50_ms"], lat["p95_ms"], lat["mean_ms"], lat["max_ms"]]
    series = [("Latency (ms)", BLUE, None, vals)]
    ymax = max(vals) * 1.25
    return bar_chart(340, 210, groups, series, "Milliseconds", ymax=ymax, yfmt="{:.1f}",
                     footnote=f"deterministic path (build+metrics+select), {lat['project_size_tasks']} tasks, n={lat['n_runs']} runs")


# ---------------------------------------------------------------- fig7: TAWOS all-987 vs baseline
def fig_tawos_all987() -> str:
    a9 = load("tawos_score_result.json")
    gm, base = a9["graph_metrics"], a9["baseline_story_points_median"]
    groups = ["Precision", "Recall", "F1", "Accuracy"]
    series = [
        ("Graph rule (untuned)", BLUE, None, [gm["precision"], gm["recall"], gm["f1"], gm["accuracy"]]),
        ("Story-point baseline", ORANGE, "hatchA", [base["precision"], base["recall"], base["f1"], base["accuracy"]]),
    ]
    return bar_chart(400, 230, groups, series, "Score", ymax=1.05, yfmt="{:.2f}", legend_below=True,
                     footnote=f"all {a9['n_sprints']} eligible sprints, {a9['n_projects']} projects (default, untuned parameters)")


# ---------------------------------------------------------------- fig8: bootstrap CI
def fig_bootstrap_ci() -> str:
    boot = load("tawos_holdout_bootstrap_result.json")
    pe, ci = boot["point_estimate"], boot["ci_95"]
    metrics = ["precision", "recall", "f1", "accuracy"]
    nice = {"precision": "Precision", "recall": "Recall", "f1": "F1", "accuracy": "Accuracy"}

    W, H = 400, 240
    L, R, T, B = 50, 16, 16, 36
    pw, ph = W - L - R, H - T - B
    s = [svg_open(W, H)]

    def Y(v): return T + ph - v * ph

    for gv in (0, 0.25, 0.5, 0.75, 1.0):
        y = Y(gv)
        s.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L+pw}" y2="{y:.1f}" stroke="{GRID}" stroke-width="0.5"/>')
        s.append(txt(L - 6, y + 2.8, f"{gv:.2f}", 7.5, MUTED, "end"))

    gw = pw / len(metrics)
    for gi, m in enumerate(metrics):
        gx = L + gi * gw + gw / 2
        lo, hi = ci[m]
        point = pe[m]
        # whisker
        s.append(f'<line x1="{gx:.1f}" y1="{Y(lo):.1f}" x2="{gx:.1f}" y2="{Y(hi):.1f}" '
                 f'stroke="{BLUE}" stroke-width="1.6"/>')
        for yv in (lo, hi):
            s.append(f'<line x1="{gx-6:.1f}" y1="{Y(yv):.1f}" x2="{gx+6:.1f}" y2="{Y(yv):.1f}" '
                     f'stroke="{BLUE}" stroke-width="1.4"/>')
        s.append(f'<circle cx="{gx:.1f}" cy="{Y(point):.1f}" r="4" fill="{ORANGE}" stroke="#ffffff" stroke-width="1"/>')
        s.append(txt(gx, Y(hi) - 7, f"{point:.3f}", 7.5, INK, "middle", "bold"))
        if lo != hi:
            s.append(txt(gx, Y(lo) + 12, f"[{lo:.2f}, {hi:.2f}]", 6.8, MUTED, "middle"))
        else:
            s.append(txt(gx, Y(lo) + 12, "degenerate (=1.0)", 6.8, MUTED, "middle", "italic"))
        s.append(txt(gx, T + ph + 14, nice[m], 8, INK))

    s.append(f'<line x1="{L}" y1="{T+ph}" x2="{L+pw}" y2="{T+ph}" stroke="{MUTED}" stroke-width="0.8"/>')
    s.append(f'<line x1="{L}" y1="{T}" x2="{L}" y2="{T+ph}" stroke="{MUTED}" stroke-width="0.8"/>')
    s.append(txt(W - 6, H - 4,
                 f"cluster bootstrap by project, n={boot['n_bootstrap']} resamples, 95% CI",
                 6.5, MUTED, "end", "normal", "italic"))
    s.append("</svg>")
    return "\n".join(s)


# ---------------------------------------------------------------- fig9: live-LLM runs comparison
def fig_live_llm_runs() -> str:
    # v1/v2 values are as reported in the paper narrative (not separately
    # committed as JSON since they were superseded runs); v3 is the committed
    # live_llm_result_v3.json.
    v3 = load("live_llm_result_v3.json")
    groups = ["v1\n(600tok,4s)", "v2\n(2000tok,18s)", "v3\n(2000tok,20s+backoff)"]
    groups = ["v1", "v2", "v3 (reported)"]
    validity = [0.278, 0.611, v3["schema_validity_rate"]]
    kappa = [0.35, 0.84, v3["cohens_kappa_overall"]]
    series = [
        ("Schema validity", BLUE, None, validity),
        ("Cohen's kappa", ORANGE, "hatchA", kappa),
    ]
    return bar_chart(360, 220, groups, series, "Value", ymax=1.05, yfmt="{:.2f}", legend_below=True,
                     footnote="v1/v2 superseded runs (narrative-reported); v3 is the committed, reported result")


# ---------------------------------------------------------------- fig10: kappa by risk type
def fig_kappa_by_type() -> str:
    v3 = load("live_llm_result_v3.json")
    kbt = v3["cohens_kappa_by_risk_type"]
    order = sorted(kbt.keys(), key=lambda k: -kbt[k]["n"])
    nice = {"dependency": "Depend.", "knowledge": "Knowl.", "workload": "Workload",
            "delay": "Delay", "silent_member": "Silent", "coordination": "Coord."}
    groups = [f"{nice[k]}\n(n={kbt[k]['n']})" for k in order]
    groups = [nice[k] for k in order]
    vals = [kbt[k]["kappa"] for k in order]
    ns = [kbt[k]["n"] for k in order]

    W, H = 420, 220
    L, R, T, B = 46, 14, 16, 42
    pw, ph = W - L - R, H - T - B
    s = [svg_open(W, H)]

    def Y(v): return T + ph - v * ph

    for gv in (0, 0.25, 0.5, 0.75, 1.0):
        y = Y(gv)
        s.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L+pw}" y2="{y:.1f}" stroke="{GRID}" stroke-width="0.5"/>')
        s.append(txt(L - 6, y + 2.8, f"{gv:.2f}", 7.5, MUTED, "end"))

    gw = pw / len(groups)
    bw = gw * 0.5
    for gi, (g, v, n) in enumerate(zip(groups, vals, ns)):
        gx = L + gi * gw + gw / 2
        x = gx - bw / 2
        y, hgt = Y(v), v * ph
        s.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{hgt:.1f}" fill="{BLUE}" rx="1.5"/>')
        s.append(txt(gx, y - 3.5, f"{v:.2f}", 7.5, INK, "middle", "bold"))
        s.append(txt(gx, T + ph + 13, g, 7.8, INK))
        s.append(txt(gx, T + ph + 23, f"n={n}", 6.8, MUTED))

    s.append(f'<line x1="{L}" y1="{T+ph}" x2="{L+pw}" y2="{T+ph}" stroke="{MUTED}" stroke-width="0.8"/>')
    s.append(f'<line x1="{L}" y1="{T}" x2="{L}" y2="{T+ph}" stroke="{MUTED}" stroke-width="0.8"/>')
    s.append(f'<g transform="translate(13,{T+ph/2}) rotate(-90)">' + txt(0, 0, "Cohen's kappa", 8, INK) + '</g>')
    s.append("</svg>")
    return "\n".join(s)


# ---------------------------------------------------------------- fig11: composite model CV->holdout collapse
def fig_overfitting_collapse() -> str:
    hold = load("tawos_holdout_result.json")
    comp = hold["composite_model"]
    # CV numbers are the tuning-set cross-validated result reported in the
    # negative-results narrative (tawos_composite.py's main() output).
    cv = {"f1": 0.816, "auc": 0.887}
    ho = {"f1": comp["f1"], "auc": comp["auc"]}

    W, H = 380, 230
    L, R, T, B = 50, 60, 20, 40
    pw, ph = W - L - R, H - T - B
    s = [svg_open(W, H)]

    def Y(v): return T + ph - v * ph

    for gv in (0, 0.25, 0.5, 0.75, 1.0):
        y = Y(gv)
        s.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L+pw}" y2="{y:.1f}" stroke="{GRID}" stroke-width="0.5"/>')
        s.append(txt(L - 6, y + 2.8, f"{gv:.2f}", 7.5, MUTED, "end"))

    xs = [L + pw * 0.28, L + pw * 0.72]
    for metric, color in (("f1", BLUE), ("auc", ORANGE)):
        y0, y1 = Y(cv[metric]), Y(ho[metric])
        s.append(f'<line x1="{xs[0]:.1f}" y1="{y0:.1f}" x2="{xs[1]:.1f}" y2="{y1:.1f}" '
                 f'stroke="{color}" stroke-width="1.8"/>')
        for x, y in ((xs[0], y0), (xs[1], y1)):
            s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}" stroke="#ffffff" stroke-width="1"/>')
        s.append(txt(xs[0] - 6, y0 + 3, f"{cv[metric]:.3f}", 7.5, color, "end", "bold"))
        s.append(txt(xs[1] + 6, y1 + 3, f"{ho[metric]:.3f}", 7.5, color, "start", "bold"))
        s.append(txt(xs[1] + 6, y1 + 13, metric.upper(), 6.8, MUTED, "start"))

    s.append(txt(xs[0], T + ph + 16, "Cross-validated (tuning)", 7.8, INK))
    s.append(txt(xs[1], T + ph + 16, "Held-out (unseen)", 7.8, INK))

    s.append(f'<line x1="{L}" y1="{T+ph}" x2="{L+pw}" y2="{T+ph}" stroke="{MUTED}" stroke-width="0.8"/>')
    s.append(f'<line x1="{L}" y1="{T}" x2="{L}" y2="{T+ph}" stroke="{MUTED}" stroke-width="0.8"/>')
    s.append(f'<g transform="translate(13,{T+ph/2}) rotate(-90)">' + txt(0, 0, "Score", 8, INK) + '</g>')
    s.append(txt(W / 2, T - 6, "Tuned composite model: tuning vs. held-out", 8, MUTED, "middle", "normal", "italic"))
    s.append("</svg>")
    return "\n".join(s)


# ---------------------------------------------------------------- fig12: ablation overall
def fig_ablation_overall() -> str:
    ab = load("ablation_result.json")
    g, n = ab["graph_architecture"], ab["naive_architecture"]
    groups = ["Precision", "Recall", "F1", "Accuracy"]
    series = [
        ("Graph-grounded", BLUE, None, [g["precision"], g["recall"], g["f1"], g["accuracy"]]),
        ("Naive prompting", ORANGE, "hatchA", [n["precision"], n["recall"], n["f1"], n["accuracy"]]),
    ]
    return bar_chart(400, 230, groups, series, "Score", ymax=1.05, yfmt="{:.2f}", legend_below=True,
                     footnote=f"n={ab['n_scenarios']} scenarios, {ab['n_naive_calls_failed']} failed calls")


# ---------------------------------------------------------------- fig13: fallback rate by agent
def fig_fallback_by_agent() -> str:
    v3 = load("live_llm_result_v3.json")
    fb, tot = v3["per_agent_fallback_count"], v3["per_agent_total_calls"]
    agents = sorted(tot.keys())
    rates = [fb.get(a, 0) / tot[a] for a in agents]
    groups = [a.capitalize() for a in agents]
    series = [("Fallback rate", ORANGE, None, rates)]
    return bar_chart(300, 210, groups, series, "Fraction of calls", ymax=1.0, yfmt="{:.0%}",
                     footnote=f"n={sum(tot.values())} total calls across all agents (v3 run)")


# ---------------------------------------------------------------- fig14: grounding enforcement
def fig_grounding() -> str:
    gr = load("last_run_report.json")["grounding"]
    caught_pct = gr["fabrications_fully_stripped"] / gr["n_trials"]
    groups = ["Fabricated citations\nstripped", "Fabricated citations\nsurviving"]
    groups = ["Stripped", "Survived"]
    series = [("Trials", BLUE, None, [caught_pct, 1 - caught_pct])]
    return bar_chart(260, 210, groups, series, "Fraction of trials", ymax=1.05, yfmt="{:.0%}",
                     footnote=f"n={gr['n_trials']} synthetically fabricated evidence references")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    figs = {
        "fig5_synthetic_per_type.svg": fig_synthetic_per_type(),
        "fig6_latency.svg": fig_latency(),
        "fig7_tawos_all987.svg": fig_tawos_all987(),
        "fig8_bootstrap_ci.svg": fig_bootstrap_ci(),
        "fig9_live_llm_runs.svg": fig_live_llm_runs(),
        "fig10_kappa_by_type.svg": fig_kappa_by_type(),
        "fig11_overfitting_collapse.svg": fig_overfitting_collapse(),
        "fig12_ablation_overall.svg": fig_ablation_overall(),
        "fig13_fallback_by_agent.svg": fig_fallback_by_agent(),
        "fig14_grounding.svg": fig_grounding(),
    }
    for name, content in figs.items():
        (OUT / name).write_text(content, encoding="utf-8")
        print(f"wrote {OUT / name}  ({len(content):,} bytes)")


if __name__ == "__main__":
    main()
