"""Round 2 tuning — individualized per-task due dates (TUNING SET ONLY).

Round 1 (tawos_tune.py) proved OVERDUE_RATIO_MEDIUM sweeping was inert: every
task in a sprint shared one due date (sprint end), so overdue_ratio was
always exactly 0.0 or 1.0. This derives a per-task due date instead — created_at
+ (story_points * days-per-point), with days-per-point computed from resolved
tuning-set tasks only (2.959 days/point; 6.025 days flat for point-less
tasks) — so overdue_ratio becomes continuous, and threshold sweeping can
actually do something.
"""

from __future__ import annotations

import statistics
from datetime import timedelta

from app.graph import GraphBuilder, GraphMetrics
from app.graph import metrics as metrics_module
from eval.datasets.tawos_score import _confusion, _parse_dt, _auc, _brier
from eval.datasets.tawos_tune import _tuning_cases

DAYS_PER_POINT = 2.959
DAYS_NO_POINT = 6.025


def with_individual_due_dates(snapshot):
    new_tasks = []
    for t in snapshot.tasks:
        if t.created_at:
            days = t.story_points * DAYS_PER_POINT if t.story_points else DAYS_NO_POINT
            due = t.created_at + timedelta(days=days)
        else:
            due = t.due_date
        new_tasks.append(t.model_copy(update={"due_date": due}))
    return snapshot.model_copy(update={"tasks": new_tasks})


def main():
    cases = _tuning_cases()
    labels = [c.label_delayed for c in cases]

    # Precompute per-sprint overdue_ratio once at the default threshold — the
    # ratio itself doesn't depend on OVERDUE_RATIO_MEDIUM, only which bucket
    # it lands in does, so we can sweep buckets cheaply without rebuilding graphs.
    ratios = []
    for c in cases:
        snap2 = with_individual_due_dates(c.snapshot)
        g = GraphBuilder().build(snap2)
        et = _parse_dt(c.sprint_end) + timedelta(days=1)
        a = GraphMetrics(now=et).compute(g)
        f = next((f for f in a.findings_for("delay") if f.metric == "overdue_ratio"), None)
        ratios.append(f.value if f else 0.0)

    print(f"overdue_ratio: min={min(ratios):.3f} median={statistics.median(ratios):.3f} max={max(ratios):.3f}")
    print(f"AUC using raw continuous overdue_ratio: {_auc(labels, ratios):.4f}")
    print(f"Brier using raw continuous overdue_ratio: {_brier(labels, ratios):.4f}")
    print()

    print(f"{'threshold':>10} {'precision':>10} {'recall':>8} {'f1':>8} {'accuracy':>9}")
    results = []
    for t in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70]:
        preds = [r >= t for r in ratios]
        conf = _confusion(list(zip(labels, preds)))
        results.append({"threshold": t, **conf})
        print(f"{t:>10.2f} {conf['precision']:>10.3f} {conf['recall']:>8.3f} {conf['f1']:>8.3f} {conf['accuracy']:>9.3f}")

    best = max(results, key=lambda r: r["f1"])
    print(f"\nbest F1 on TUNING set: threshold={best['threshold']}, F1={best['f1']:.3f}, "
          f"precision={best['precision']:.3f}, recall={best['recall']:.3f}")


if __name__ == "__main__":
    main()
