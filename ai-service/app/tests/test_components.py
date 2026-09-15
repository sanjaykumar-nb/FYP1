"""Components: the areas of knowledge the knowledge and coordination risks group work by."""

from datetime import timedelta

import pytest

from app.graph import GraphBuilder, GraphMetrics
from app.graph.builder import COMPONENT, TOUCHES
from app.graph.snapshot import MilestoneSnapshot
from app.tests.factories import NOW, member, milestone, snapshot, task, uid

pytestmark = pytest.mark.mvp


def _sprint() -> MilestoneSnapshot:
    return MilestoneSnapshot(
        id=uid("sprint"), name="Sprint 1",
        start_date=NOW - timedelta(days=3), target_date=NOW + timedelta(days=11),
    )


def _analyze(snap):
    graph = GraphBuilder().build(snap)
    return graph, GraphMetrics(now=NOW).compute(graph)


def test_a_sprint_is_not_a_component():
    team = [member(name) for name in ("alice", "bob", "carol")]
    owners = ["alice", "alice", "bob", "carol"]
    tasks = [task(f"t{i}", assignee=owner, milestone_label="sprint") for i, owner in enumerate(owners)]
    graph, analysis = _analyze(snapshot(members=team, milestones=[_sprint()], tasks=tasks))

    assert graph.nodes_of(COMPONENT) == []
    assert analysis.findings_for("knowledge", "coordination") == []
    assert analysis.risk_scores["knowledge"] == analysis.risk_scores["coordination"] == "low"


def test_an_unscheduled_milestone_still_stands_in_for_a_component():
    graph, _ = _analyze(snapshot(
        members=[member("alice")], milestones=[milestone("area")],
        tasks=[task("t", assignee="alice", milestone_label="area")],
    ))
    assert graph.nodes_of(COMPONENT) == [f"component:{uid('area')}"]


def test_a_named_component_reveals_its_sole_owner_inside_a_sprint():
    tasks = [
        task("p1", assignee="alice", milestone_label="sprint", component="Payments"),
        task("p2", assignee="alice", milestone_label="sprint", component=" payments "),
        task("u1", assignee="alice", milestone_label="sprint", component="UI"),
        task("u2", assignee="bob", milestone_label="sprint", component="UI"),
    ]
    graph, analysis = _analyze(snapshot(
        members=[member("alice"), member("bob")], milestones=[_sprint()], tasks=tasks,
    ))

    # Case and spacing do not split one area into two.
    assert graph.nodes_of(COMPONENT) == ["component:area:payments", "component:area:ui"]
    spof = next(f for f in analysis.findings if f.metric == "sole_owner_ratio")
    assert "component:area:payments" in spof.node_ids
    assert f"person:{uid('alice')}" in spof.node_ids


def test_a_named_component_replaces_the_milestone_fallback():
    graph, _ = _analyze(snapshot(
        members=[member("alice")], milestones=[milestone("area")],
        tasks=[task("t", assignee="alice", milestone_label="area", component="Scheduler")],
    ))
    assert graph.edges_of_kind(TOUCHES) == [(f"task:{uid('t')}", "component:area:scheduler")]


def test_without_components_coordination_gives_no_verdict():
    team = [member(name) for name in ("alice", "bob", "carol")]
    tasks = [task(f"t{i}", assignee=name) for i, name in enumerate(["alice", "bob", "carol"])]
    _, analysis = _analyze(snapshot(members=team, tasks=tasks))

    assert analysis.findings_for("coordination") == []
    assert analysis.risk_scores["coordination"] == "low"


def _core_team_plus(extra_members, extra_tasks):
    team = [member(name) for name in ("alice", "bob", "carol")] + [member(name) for name in extra_members]
    tasks = [task(f"core{i}", assignee=name, component="Core") for i, name in enumerate(["alice", "bob", "carol"])]
    return snapshot(members=team, tasks=tasks + extra_tasks)


def test_people_whose_work_context_is_unknown_are_not_called_isolated():
    # A viewer with no work, and someone whose task names no component.
    snap = _core_team_plus(["viewer", "dave"], [task("loose", assignee="dave")])
    _, analysis = _analyze(snap)

    assert analysis.findings_for("coordination") == []


def test_someone_working_only_in_an_area_nobody_else_touches_is_still_isolated():
    snap = _core_team_plus(["dave"], [task("docs1", assignee="dave", component="Docs")])
    _, analysis = _analyze(snap)

    isolated = next(f for f in analysis.findings if f.metric == "isolated_member_count")
    assert isolated.node_ids == [f"person:{uid('dave')}"]
