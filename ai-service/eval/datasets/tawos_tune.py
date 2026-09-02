"""Threshold tuning — TUNING SET ONLY.

Sweeps GraphMetrics' OVERDUE_RATIO_MEDIUM against the 717 tuning-split
sprints and reports F1/precision/recall at each candidate value. This never
touches the held-out split — that's the whole point of having one. Whatever
value comes out of this gets evaluated exactly once, on held-out data, by
tawos_holdout_eval.py — not here.

Run: python -m eval.datasets.tawos_tune
"""

from __future__ import annotations

from datetime import timedelta

from app.graph import GraphBuilder, GraphMetrics
from app.graph import metrics as metrics_module
from eval.datasets.tawos_ingest import build_sprint_cases, connect
from eval.datasets.tawos_score import _confusion, _parse_dt
from eval.datasets.tawos_split import load_split


def _tuning_cases():
    split = load_split()
    tuning_projects = set(split["tuning_projects"])
    conn = connect()
    return [c for c in build_sprint_cases(conn) if c.project_key in tuning_projects]


def sweep_overdue_threshold(cases, candidates):
    labels = [c.label_delayed for c in cases]
    results = []

    original = metrics_module.OVERDUE_RATIO_MEDIUM
    try:
        for t in candidates:
            metrics_module.OVERDUE_RATIO_MEDIUM = t
            preds = []
            for c in cases:
                graph = GraphBuilder().build(c.snapshot)
                eval_time = _parse_dt(c.sprint_end) + timedelta(days=1)
                analysis = GraphMetrics(now=eval_time).compute(graph)
                preds.append(analysis.risk_scores.get("delay", "low") != "low")
            conf = _confusion(list(zip(labels, preds)))
            results.append({"threshold": t, **conf})
    finally:
        metrics_module.OVERDUE_RATIO_MEDIUM = original

    return results


def main():
    cases = _tuning_cases()
    print(f"tuning on {len(cases)} sprints from {len(set(c.project_key for c in cases))} projects")

    candidates = [0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
    results = sweep_overdue_threshold(cases, candidates)

    print(f"{'threshold':>10} {'precision':>10} {'recall':>8} {'f1':>8} {'accuracy':>9}")
    for r in results:
        print(f"{r['threshold']:>10.2f} {r['precision']:>10.3f} {r['recall']:>8.3f} {r['f1']:>8.3f} {r['accuracy']:>9.3f}")

    best = max(results, key=lambda r: r["f1"])
    print(f"\nbest F1 on TUNING set: threshold={best['threshold']}, F1={best['f1']:.3f}")
    print("(this number is expected to be optimistic — it's fit to this data; "
          "the honest number comes from evaluating this threshold on held-out data)")


if __name__ == "__main__":
    main()
