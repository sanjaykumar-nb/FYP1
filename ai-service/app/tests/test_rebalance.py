"""Suggested reassignments for workload findings (app.graph.actions)."""

import pytest

from app.graph.actions import MAX_MOVES, plan_rebalance
from app.graph.metrics import open_point_loads
from app.services.graph_pipeline import build_graph, recommendation_output_from_graph
from app.tests.factories import healthy_project, member, milestone, snapshot, task, uid

pytestmark = pytest.mark.mvp


def _skewed():
    """busy carries 10 open points, steady 2, idle none: skew 2.5 (high)."""
    members = [member(name) for name in ("busy", "steady", "idle")]
    tasks = [
        task("b0", status="done", points=8, assignee="busy", milestone_label="m"),
        task("b1", status="in_progress", points=5, assignee="busy", milestone_label="m"),
        task("b2", status="planned", points=3, assignee="busy", milestone_label="m"),
        task("b3", status="planned", points=2, assignee="busy", milestone_label="m"),
        task("s1", status="in_progress", points=2, assignee="steady", milestone_label="m"),
    ]
    return snapshot(members=members, milestones=[milestone("m")], tasks=tasks)


def test_moves_work_off_the_busiest_person_until_load_skew_is_low():
    graph, analysis = build_graph(_skewed())
    assert analysis.risk_scores["workload"] == "high"

    plan = plan_rebalance(graph)

    assert [(m.task_id, m.from_person, m.to_person) for m in plan.moves] == [
        (f"task:{uid('b1')}", f"person:{uid('busy')}", f"person:{uid('idle')}")
    ]
    assert (plan.peak_before, plan.peak_after) == (10, 5)
    assert (plan.severity_before, plan.severity_after) == ("high", "low")


def test_plan_names_real_nodes_and_never_raises_the_peak():
    members = [member(name) for name in ("busy", "a", "b", "c")]
    tasks = [task(f"x{i}", status="in_progress", points=3, assignee="busy") for i in range(6)]
    tasks += [task("a1", points=1, assignee="a"), task("b1", points=1, assignee="b")]
    graph, _ = build_graph(snapshot(members=members, tasks=tasks))

    plan = plan_rebalance(graph)

    assert 1 <= len(plan.moves) <= MAX_MOVES
    load, _ = open_point_loads(graph)
    for move in plan.moves:
        assert all(graph.has_node(n) for n in (move.task_id, move.from_person, move.to_person))
        peak = max(load.values())
        load[move.from_person] -= move.points
        load[move.to_person] += move.points
        assert max(load.values()) <= peak
    assert max(load.values()) == plan.peak_after < plan.peak_before


def test_balanced_project_needs_no_moves():
    graph, _ = build_graph(healthy_project(12))
    assert plan_rebalance(graph) is None


def test_finding_and_plan_agree_on_the_load():
    graph, analysis = build_graph(_skewed())
    skew = next(f for f in analysis.findings if f.metric == "workload_skew")
    assert f"carries {plan_rebalance(graph).peak_before} open points" in skew.title


def test_workload_recommendation_carries_the_moves():
    graph, analysis = build_graph(_skewed())
    recs = recommendation_output_from_graph(analysis, graph).recommendations

    workload = next(r for r in recs if r.type == "redistribute")
    assert [(a.kind, a.task_id) for a in workload.actions] == [("reassign", f"task:{uid('b1')}")]
    assert "from 10 to 5 points" in workload.expected_effect
    assert "high → low" in workload.expected_effect
    assert all(not r.actions for r in recs if r.type != "redistribute")


def test_effect_quotes_the_same_team_mean_as_the_finding():
    # 13 people carrying 50 points: a mean of 3.846, which must read 3.8 in both places.
    names = ["busy"] + [f"m{i}" for i in range(1, 13)]
    tasks = [task(f"busy{i}", status="in_progress", points=3, assignee="busy") for i in range(3)]
    tasks += [task(f"m{i}t", status="in_progress", points=5, assignee=f"m{i}") for i in range(1, 9)]
    tasks.append(task("m9t", status="in_progress", points=1, assignee="m9"))
    graph, analysis = build_graph(snapshot(members=[member(n) for n in names], tasks=tasks))

    skew = next(f for f in analysis.findings if f.metric == "workload_skew")
    workload = next(
        r for r in recommendation_output_from_graph(analysis, graph).recommendations if r.type == "redistribute"
    )
    assert "team mean of 3.8" in skew.title
    assert "team mean of 3.8" in workload.expected_effect
