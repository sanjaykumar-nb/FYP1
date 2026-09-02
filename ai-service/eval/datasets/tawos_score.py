"""Score GraphMetrics against real TAWOS sprint outcomes.

Prediction: GraphMetrics(now=sprint_end).risk_scores["delay"] != "low",
computed on the exact same GraphBuilder/GraphMetrics classes the running
application uses — no separate scoring logic, no shortcuts.
Ground truth: SprintCase.label_delayed (>=30% of the sprint's issues were
not resolved by sprint end — see tawos_ingest.py for why this is the label,
given TAWOS has no due_date field).
Baseline: predict delayed if the sprint's median story points exceeds the
per-sprint-set median (the standard baseline for this kind of task).

Run: python -m eval.datasets.tawos_score
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta, timezone

from app.graph import GraphBuilder, GraphMetrics
from eval.datasets.tawos_ingest import build_sprint_cases, connect, inspect_link_names


def _parse_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", ""))
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _confusion(pairs: list[tuple[bool, bool]]) -> dict:
    tp = sum(1 for y, p in pairs if y and p)
    fp = sum(1 for y, p in pairs if not y and p)
    fn = sum(1 for y, p in pairs if y and not p)
    tn = sum(1 for y, p in pairs if not y and not p)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    acc = (tp + tn) / len(pairs) if pairs else 1.0
    return {"n": len(pairs), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(f1, 4), "accuracy": round(acc, 4)}


def _auc(labels: list[bool], scores: list[float]) -> float:
    """Rank-based AUC-ROC (Mann-Whitney U), no sklearn dependency."""
    pos = [s for y, s in zip(labels, scores) if y]
    neg = [s for y, s in zip(labels, scores) if not y]
    if not pos or not neg:
        return float("nan")
    ranked = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(ranked):
        j = i
        while j + 1 < len(ranked) and scores[ranked[j + 1]] == scores[ranked[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[ranked[k]] = avg_rank
        i = j + 1
    rank_sum_pos = sum(ranks[i] for i, y in enumerate(labels) if y)
    n_pos, n_neg = len(pos), len(neg)
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def _brier(labels: list[bool], probs: list[float]) -> float:
    return sum((p - (1.0 if y else 0.0)) ** 2 for y, p in zip(labels, probs)) / len(labels)


SEVERITY_SCORE = {"low": 0.0, "medium": 0.5, "high": 0.75, "critical": 1.0}


def _continuous_delay_score(analysis) -> float:
    """The severity bucket (low/medium/high/critical -> 0/.5/.75/1), not the
    raw overdue_ratio value. Checked and deliberately NOT using overdue_ratio
    directly: every task in a reconstructed sprint shares one due_date (the
    sprint's own end), so once evaluated after that date, overdue_ratio is
    ~always exactly 1.0 for any sprint with at least one open task — a
    near-binary signal, not a finer-grained one, an artifact of this
    sprint-level reconstruction (real usage has per-task due dates that
    vary). The severity bucket is the honest signal to rank on here."""
    for f in analysis.findings_for("delay"):
        if f.metric == "overdue_ratio":
            return SEVERITY_SCORE.get(f.severity, 0.0)
    return 0.0


def main(limit: int | None = None):
    conn = connect()

    link_names = inspect_link_names(conn)
    print("issue_link name/direction distribution:", file=__import__("sys").stderr)
    for row in link_names[:15]:
        print(" ", tuple(row), file=__import__("sys").stderr)

    cases = list(build_sprint_cases(conn, limit=limit))
    print(f"n sprint cases: {len(cases)}", file=__import__("sys").stderr)

    labels: list[bool] = []
    graph_preds: list[bool] = []
    graph_scores: list[float] = []
    baseline_preds: list[bool] = []

    all_medians = []
    for c in cases:
        points = [t.story_points for t in c.snapshot.tasks if t.story_points]
        all_medians.append(statistics.median(points) if points else 0)
    global_median = statistics.median(all_medians) if all_medians else 0

    for case in cases:
        graph = GraphBuilder().build(case.snapshot)
        # "now" must be strictly after due_date (= sprint_end) for anything to
        # ever register as overdue — evaluating exactly at the deadline itself
        # trivially finds nothing late. One day after sprint close is the
        # natural point to ask "is anything still hanging open."
        eval_time = _parse_dt(case.sprint_end) + timedelta(days=1)
        analysis = GraphMetrics(now=eval_time).compute(graph)
        delay_level = analysis.risk_scores.get("delay", "low")

        labels.append(case.label_delayed)
        graph_preds.append(delay_level != "low")
        graph_scores.append(_continuous_delay_score(analysis))

        sprint_points = [t.story_points for t in case.snapshot.tasks if t.story_points]
        sprint_median = statistics.median(sprint_points) if sprint_points else 0
        baseline_preds.append(sprint_median > global_median)

    by_project: dict[str, list[tuple[bool, bool]]] = {}
    for case, pred in zip(cases, graph_preds):
        by_project.setdefault(case.project_key, []).append((case.label_delayed, pred))
    per_project = {
        k: _confusion(v) for k, v in sorted(by_project.items(), key=lambda kv: -len(kv[1]))
        if len(v) >= 5
    }

    result = {
        "n_sprints": len(cases),
        "n_projects": len(set(c.project_key for c in cases)),
        "label_positive_rate": round(sum(labels) / len(labels), 4) if labels else None,
        "graph_metrics": _confusion(list(zip(labels, graph_preds))),
        "graph_metrics_auc": round(_auc(labels, graph_scores), 4) if labels else None,
        "graph_metrics_brier": round(_brier(labels, graph_scores), 4) if labels else None,
        "baseline_story_points_median": _confusion(list(zip(labels, baseline_preds))),
        "per_project_f1": {k: v["f1"] for k, v in per_project.items()},
        "config": {
            "sprint_delay_threshold": 0.30,
            "min_issues_per_sprint": 15,
            "eval_time_offset_days_after_sprint_end": 1,
        },
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit=lim)
