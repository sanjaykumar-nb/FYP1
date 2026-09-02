"""Threshold-boundary sensitivity analysis — a harder test than eval/run_eval.py.

run_eval.py's detection scenarios are deliberately unambiguous (injected
magnitude sits clearly above or below threshold), so 100% precision/recall
there is the expected result of correct code, not evidence of anything
subtle. This script instead sweeps the injected magnitude FINELY across each
threshold and asks: does the detector actually flip exactly where the
documented constant says it should?

This can fail in ways run_eval.py structurally cannot: an off-by-one in the
comparison operator, a threshold applied to the wrong denominator, or —
expected and reported here, not hidden — quantization from small integer
team sizes meaning the exact threshold ratio is sometimes unreachable.
"""

from __future__ import annotations

from app.graph import GraphBuilder, GraphMetrics
from app.graph.metrics import OVERDUE_RATIO_MEDIUM, SILENT_RATIO_MEDIUM, WORKLOAD_SKEW_MEDIUM
from app.tests.factories import comment, member, snapshot, task


def _severity_at(metric_name: str, findings) -> str:
    for f in findings:
        if f.metric == metric_name:
            return f.severity
    return "absent"


def sweep_overdue_ratio(team_size: int = 5, n_tasks: int = 100, step: int = 2):
    members = [member(f"d{i}") for i in range(team_size)]
    rows = []
    for n_overdue in range(0, n_tasks + 1, step):
        tasks = [
            task(f"t{i}", assignee=f"d{i % team_size}", status="in_progress",
                 due_in_days=-5 if i < n_overdue else 30)
            for i in range(n_tasks)
        ]
        graph = GraphBuilder().build(snapshot(members=members, tasks=tasks))
        analysis = GraphMetrics().compute(graph)
        ratio = n_overdue / n_tasks
        severity = _severity_at("overdue_ratio", analysis.findings)
        rows.append({"ratio": round(ratio, 3), "severity": severity})
    return rows


def sweep_workload_skew(team_size: int = 5, base_points: int = 2, base_tasks_per_person: int = 10):
    members = [member(f"d{i}") for i in range(team_size)]
    rows = []
    for extra in range(0, 61, 3):
        tasks = []
        for i in range(team_size):
            for j in range(base_tasks_per_person):
                tasks.append(task(f"t{i}_{j}", assignee=f"d{i}", points=base_points, status="in_progress"))
        # Pile `extra` points onto d0 specifically, in addition to its base load.
        if extra:
            tasks.append(task("heavy", assignee="d0", points=extra, status="in_progress"))
        graph = GraphBuilder().build(snapshot(members=members, tasks=tasks))
        analysis = GraphMetrics().compute(graph)
        skew_finding = next((f for f in analysis.findings if f.metric == "workload_skew"), None)
        rows.append({
            "extra_points_on_d0": extra,
            "measured_skew": skew_finding.value if skew_finding else None,
            "severity": skew_finding.severity if skew_finding else "absent",
        })
    return rows


def sweep_silent_ratio(team_size: int = 10, n_tasks_per_person: int = 3):
    members = [member(f"d{i}") for i in range(team_size)]
    rows = []
    for n_silent in range(0, team_size + 1):
        tasks, comments = [], []
        for i in range(team_size):
            for j in range(n_tasks_per_person):
                t = task(f"t{i}_{j}", assignee=f"d{i}", status="in_progress")
                tasks.append(t)
                if i >= n_silent:  # first n_silent people never comment
                    comments.append(comment(f"t{i}_{j}", f"d{i}"))
        graph = GraphBuilder().build(snapshot(members=members, tasks=tasks, comments=comments))
        analysis = GraphMetrics().compute(graph)
        ratio = n_silent / team_size
        severity = _severity_at("silent_ratio", analysis.findings)
        rows.append({"n_silent": n_silent, "team_size": team_size, "ratio": round(ratio, 3), "severity": severity})
    return rows


def find_transition(rows: list[dict], key: str, severity_key: str = "severity") -> tuple[float | None, float | None]:
    """Returns (last_value_below_threshold, first_value_at_or_above) by scanning
    for the first low->medium+ transition."""
    prev = None
    for row in rows:
        is_flagged = row[severity_key] not in ("low", "absent")
        if is_flagged and prev is not None and not prev["flagged"]:
            return prev["value"], row[key]
        prev = {"value": row[key], "flagged": is_flagged}
    return None, None


def main():
    print("=== overdue_ratio (documented threshold: %.2f) ===" % OVERDUE_RATIO_MEDIUM)
    rows = sweep_overdue_ratio()
    below, at = find_transition(rows, "ratio")
    print(f"observed transition: {below} -> {at}  (severity flips low/absent -> medium here)")
    for r in rows:
        if abs(r["ratio"] - OVERDUE_RATIO_MEDIUM) <= 0.06:
            print(" ", r)

    print("\n=== workload_skew (documented threshold: %.2f) ===" % WORKLOAD_SKEW_MEDIUM)
    rows = sweep_workload_skew()
    for r in rows:
        if r["measured_skew"] is not None and abs(r["measured_skew"] - WORKLOAD_SKEW_MEDIUM) <= 0.15:
            print(" ", r)
    below, at = find_transition(rows, "extra_points_on_d0")
    print(f"observed transition at extra_points_on_d0: {below} -> {at}")

    print("\n=== silent_ratio (documented threshold: %.2f) ===" % SILENT_RATIO_MEDIUM)
    rows = sweep_silent_ratio()
    for r in rows:
        print(" ", r)
    below, at = find_transition(rows, "ratio")
    print(f"observed transition: {below} -> {at}")


if __name__ == "__main__":
    main()
