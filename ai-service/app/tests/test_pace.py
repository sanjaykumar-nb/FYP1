"""Pace-based early warning for delay (app.graph.metrics.pace_projections)."""

from datetime import timedelta

import pytest

from app.graph import GraphBuilder, GraphMetrics
from app.graph.metrics import pace_projections
from app.graph.snapshot import MilestoneSnapshot
from app.services.graph_pipeline import recommendation_output_from_graph
from app.tests.factories import NOW, member, snapshot, task, uid

pytestmark = pytest.mark.mvp


def _sprint(elapsed: float, done: int, still_open: int, *, with_start: bool = True, points=3):
    """A 10-day sprint `elapsed` of the way through, with `done` tasks finished."""
    start = NOW - timedelta(days=10 * elapsed)
    sprint = MilestoneSnapshot(
        id=uid("sprint"), name="Sprint 1",
        start_date=start if with_start else None, target_date=start + timedelta(days=10),
    )
    tasks = [task(f"done{i}", status="done", points=points, assignee="dev", milestone_label="sprint")
             for i in range(done)]
    tasks += [task(f"open{i}", status="in_progress", points=points, assignee="dev", milestone_label="sprint")
              for i in range(still_open)]
    return snapshot(members=[member("dev")], milestones=[sprint], tasks=tasks)


def _analyze(snap):
    graph = GraphBuilder().build(snap)
    return graph, GraphMetrics(now=NOW).compute(graph)


def test_behind_pace_raises_delay_before_the_deadline():
    # Halfway through with 2 of 10 tasks done: on this pace 40% gets done, 60% is left open.
    graph, analysis = _analyze(_sprint(elapsed=0.5, done=2, still_open=8))

    finding = next(f for f in analysis.findings if f.metric == "projected_unfinished")
    assert finding.value == pytest.approx(0.6)
    assert finding.severity == "critical"
    assert analysis.risk_scores["delay"] == "critical"
    assert sorted(finding.node_ids) == sorted(f"task:{uid(f'open{i}')}" for i in range(8))
    assert all(graph.has_node(n) for n in finding.node_ids)


def test_on_pace_raises_nothing():
    _, analysis = _analyze(_sprint(elapsed=0.5, done=5, still_open=5))
    assert not [f for f in analysis.findings if f.metric == "projected_unfinished"]
    assert analysis.risk_scores["delay"] == "low"


@pytest.mark.parametrize("elapsed", [0.1, 1.2])
def test_projects_only_inside_the_schedule_window(elapsed):
    # Too early to extrapolate, or past the deadline (where the overdue signal applies).
    graph, _ = _analyze(_sprint(elapsed=elapsed, done=0, still_open=10))
    assert pace_projections(graph, NOW) == []


def test_needs_a_start_date():
    graph, _ = _analyze(_sprint(elapsed=0.5, done=0, still_open=10, with_start=False))
    assert pace_projections(graph, NOW) == []


def test_work_is_weighted_by_points_with_unestimated_tasks_counting_one():
    snap = _sprint(elapsed=0.5, done=0, still_open=0)
    snap.tasks = [
        task("big", status="done", points=8, milestone_label="sprint"),
        task("todo1", status="backlog", points=None, milestone_label="sprint"),
        task("todo2", status="backlog", points=None, milestone_label="sprint"),
    ]
    graph, _ = _analyze(snap)

    (pace,) = pace_projections(graph, NOW)
    assert pace.completed == pytest.approx(0.8)
    assert pace.projected_unfinished == 0.0


def test_behind_pace_recommends_replanning_not_splitting_overdue_work():
    graph, analysis = _analyze(_sprint(elapsed=0.5, done=2, still_open=8))

    recs = recommendation_output_from_graph(analysis, graph).recommendations
    rescope = next(r for r in recs if r.type == "rescope")
    assert rescope.title == "Re-plan before the deadline"
    assert "at this pace" in rescope.description
    assert not any(r.type == "split_task" for r in recs)
