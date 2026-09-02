"""Extract every GraphMetrics finding as a feature, per tuning-set sprint.

Purpose: see which of the six risk types actually carry signal for sprint
delay before blindly combining all of them into a composite — with only 717
tuning samples, including uninformative features just adds overfitting risk
for no benefit.
"""

from __future__ import annotations

import statistics
from datetime import timedelta

from app.graph import GraphBuilder, GraphMetrics
from eval.datasets.tawos_score import _parse_dt
from eval.datasets.tawos_tune import _tuning_cases

# One feature per (risk_type, metric) pair GraphMetrics can ever emit.
FEATURE_KEYS = [
    ("dependency", "cycle_count"),
    ("dependency", "critical_path_share"),
    ("dependency", "betweenness_centrality"),
    ("knowledge", "sole_owner_ratio"),
    ("knowledge", "articulation_person_count"),
    ("workload", "workload_skew"),
    ("workload", "idle_member_ratio"),
    ("delay", "overdue_ratio"),
    ("delay", "blocked_ratio"),
    ("coordination", "cluster_ratio"),
    ("coordination", "isolated_member_count"),
    ("silent_member", "silent_ratio"),
]


def extract_features(analysis) -> dict[str, float]:
    values = {f"{rt}:{m}": 0.0 for rt, m in FEATURE_KEYS}
    for f in analysis.findings:
        key = f"{f.risk_type}:{f.metric}"
        if key in values:
            values[key] = f.value
    return values


def build_dataset():
    cases = _tuning_cases()
    labels, feature_rows = [], []
    for c in cases:
        graph = GraphBuilder().build(c.snapshot)
        eval_time = _parse_dt(c.sprint_end) + timedelta(days=1)
        analysis = GraphMetrics(now=eval_time).compute(graph)
        feature_rows.append(extract_features(analysis))
        labels.append(c.label_delayed)
    return labels, feature_rows


def point_biserial(labels: list[bool], values: list[float]) -> float:
    """Correlation between a binary label and a continuous feature —
    Pearson's r applied directly to the 0/1-coded label."""
    y = [1.0 if l else 0.0 for l in labels]
    n = len(y)
    mean_y, mean_x = sum(y) / n, sum(values) / n
    cov = sum((yi - mean_y) * (xi - mean_x) for yi, xi in zip(y, values))
    var_y = sum((yi - mean_y) ** 2 for yi in y)
    var_x = sum((xi - mean_x) ** 2 for xi in values)
    if var_y == 0 or var_x == 0:
        return 0.0
    return cov / (var_y * var_x) ** 0.5


def main():
    labels, rows = build_dataset()
    print(f"n={len(labels)} sprints, positive_rate={sum(labels)/len(labels):.3f}\n")

    print(f"{'feature':32} {'nonzero%':>9} {'corr_w_label':>13}")
    for key, _ in [(f"{rt}:{m}", None) for rt, m in FEATURE_KEYS]:
        values = [row[key] for row in rows]
        nonzero_pct = sum(1 for v in values if v != 0) / len(values) * 100
        corr = point_biserial(labels, values)
        print(f"{key:32} {nonzero_pct:8.1f}% {corr:13.4f}")


if __name__ == "__main__":
    main()
