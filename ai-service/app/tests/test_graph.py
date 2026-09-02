"""Knowledge graph core: construction, metrics, and determinism (KG-1..KG-5, REL-2)."""

import pytest

from app.graph import GraphBuilder, GraphMetrics, node_id
from app.graph.builder import BLOCKS, COMPONENT, PERSON, TASK
from app.tests.factories import (
    NOW,
    blocks,
    comment,
    healthy_project,
    member,
    milestone,
    snapshot,
    task,
    uid,
)

pytestmark = pytest.mark.mvp


@pytest.fixture
def builder():
    return GraphBuilder()


@pytest.fixture
def metrics():
    return GraphMetrics(now=NOW)


class TestGraphConstruction:
    """KG-1: the graph faithfully mirrors the snapshot."""

    def test_node_and_edge_counts_match_snapshot(self, builder):
        snap = snapshot(
            members=[member("alice"), member("bob")],
            milestones=[milestone("m1")],
            tasks=[
                task("t1", assignee="alice", milestone_label="m1"),
                task("t2", assignee="bob", milestone_label="m1"),
            ],
            dependencies=[blocks("t1", "t2")],
            comments=[comment("t1", "alice")],
        )
        g = builder.build(snap)

        assert len(g.nodes_of(PERSON)) == 2
        assert len(g.nodes_of(TASK)) == 2
        assert len(g.nodes_of(COMPONENT)) == 1
        assert g.edges_of_kind(BLOCKS) == [(node_id(TASK, uid("t1")), node_id(TASK, uid("t2")))]
        assert g.has_node(node_id(PERSON, uid("alice")))

    def test_dangling_references_are_skipped(self, builder):
        """A task assigned to an unknown user must not invent a person node."""
        snap = snapshot(
            members=[member("alice")],
            tasks=[task("t1", assignee="ghost")],
        )
        g = builder.build(snap)
        assert g.nodes_of(PERSON) == [node_id(PERSON, uid("alice"))]

    def test_empty_snapshot_builds(self, builder, metrics):
        g = builder.build(snapshot())
        analysis = metrics.compute(g)
        assert analysis.overall_risk_level == "low"
        assert analysis.findings == []


class TestCriticalPath:
    """KG-2: longest chain through the BLOCKS DAG."""

    def test_critical_path_matches_hand_computed_chain(self, builder, metrics):
        snap = snapshot(
            members=[member("alice")],
            tasks=[task(f"t{i}", status="backlog", assignee="alice") for i in range(5)],
            # t0 -> t1 -> t2 -> t3 chain; t4 is standalone
            dependencies=[blocks("t0", "t1"), blocks("t1", "t2"), blocks("t2", "t3")],
        )
        g = builder.build(snap)
        path = __import__("networkx").dag_longest_path(g.blocks_digraph())

        assert path == [node_id(TASK, uid(f"t{i}")) for i in range(4)]

        analysis = metrics.compute(g)
        cp = [f for f in analysis.findings if f.metric == "critical_path_share"]
        assert len(cp) == 1
        assert cp[0].value == pytest.approx(4 / 5)


class TestSinglePointOfFailure:
    """KG-3: sole component ownership surfaces as knowledge risk."""

    def test_sole_owner_of_component_is_flagged(self, builder, metrics):
        snap = snapshot(
            members=[member("alice"), member("bob")],
            milestones=[milestone("payments"), milestone("ui")],
            tasks=[
                # Only alice ever touches payments.
                task("p1", assignee="alice", milestone_label="payments"),
                task("p2", assignee="alice", milestone_label="payments"),
                # ui is shared.
                task("u1", assignee="alice", milestone_label="ui"),
                task("u2", assignee="bob", milestone_label="ui"),
            ],
        )
        analysis = metrics.compute(builder.build(snap))

        spof = [f for f in analysis.findings if f.metric == "sole_owner_ratio"]
        assert len(spof) == 1
        assert node_id(PERSON, uid("alice")) in spof[0].node_ids
        assert node_id(COMPONENT, uid("payments")) in spof[0].node_ids
        assert analysis.risk_scores["knowledge"] != "low"

    def test_fully_shared_ownership_is_not_flagged(self, builder, metrics):
        analysis = metrics.compute(builder.build(healthy_project()))
        assert analysis.risk_scores["knowledge"] == "low"


class TestCycleDetection:
    """KG-4: circular dependencies — creatable through the API before this."""

    def test_three_node_cycle_is_detected_as_critical(self, builder, metrics):
        snap = snapshot(
            members=[member("alice")],
            tasks=[task(f"c{i}", assignee="alice") for i in range(3)],
            dependencies=[blocks("c0", "c1"), blocks("c1", "c2"), blocks("c2", "c0")],
        )
        analysis = metrics.compute(builder.build(snap))

        cycles = [f for f in analysis.findings if f.metric == "cycle_count"]
        assert len(cycles) == 1
        assert cycles[0].severity == "critical"
        assert analysis.risk_scores["dependency"] == "critical"
        assert analysis.overall_risk_level == "critical"

    def test_acyclic_graph_reports_no_cycles(self, builder, metrics):
        snap = snapshot(
            members=[member("alice")],
            tasks=[task(f"c{i}", assignee="alice") for i in range(3)],
            dependencies=[blocks("c0", "c1"), blocks("c1", "c2")],
        )
        analysis = metrics.compute(builder.build(snap))
        assert not [f for f in analysis.findings if f.metric == "cycle_count"]


class TestWorkloadSkew:
    """KG-5: weighted degree ranks the overloaded member first."""

    def test_overloaded_member_is_identified(self, builder, metrics):
        snap = snapshot(
            members=[member("alice"), member("bob"), member("carol")],
            tasks=[
                task("t1", assignee="alice", points=13, status="in_progress"),
                task("t2", assignee="alice", points=13, status="in_progress"),
                task("t3", assignee="bob", points=2, status="in_progress"),
                task("t4", assignee="carol", points=2, status="in_progress"),
            ],
        )
        analysis = metrics.compute(builder.build(snap))

        skew = [f for f in analysis.findings if f.metric == "workload_skew"]
        assert len(skew) == 1
        assert skew[0].node_ids == [node_id(PERSON, uid("alice"))]
        assert skew[0].value > 2.0
        assert analysis.risk_scores["workload"] in ("high", "critical")

    def test_completed_work_does_not_count_toward_load(self, builder, metrics):
        snap = snapshot(
            members=[member("alice"), member("bob")],
            tasks=[
                task("t1", assignee="alice", points=50, status="done"),
                task("t2", assignee="alice", points=3, status="in_progress"),
                task("t3", assignee="bob", points=3, status="in_progress"),
            ],
        )
        analysis = metrics.compute(builder.build(snap))
        assert analysis.risk_scores["workload"] == "low"


class TestDelayRisk:
    def test_overdue_tasks_raise_delay_risk(self, builder, metrics):
        snap = snapshot(
            members=[member("alice")],
            tasks=[
                task("late1", assignee="alice", status="in_progress", due_in_days=-10),
                task("late2", assignee="alice", status="backlog", due_in_days=-5),
                task("ok", assignee="alice", status="in_progress", due_in_days=20),
            ],
        )
        analysis = metrics.compute(builder.build(snap))

        overdue = [f for f in analysis.findings if f.metric == "overdue_ratio"]
        assert len(overdue) == 1
        # Metric values are rounded to 3dp for compact prompt rendering.
        assert overdue[0].value == pytest.approx(2 / 3, abs=1e-3)
        assert overdue[0].severity == "critical"

    def test_completed_tasks_are_never_overdue(self, builder, metrics):
        snap = snapshot(
            members=[member("alice")],
            tasks=[task("shipped", assignee="alice", status="done", due_in_days=-30)],
        )
        analysis = metrics.compute(builder.build(snap))
        assert analysis.risk_scores["delay"] == "low"


class TestSilentMembers:
    def test_members_who_never_comment_are_flagged(self, builder, metrics):
        snap = snapshot(
            members=[member("alice"), member("bob")],
            tasks=[task("t1", assignee="alice"), task("t2", assignee="bob")],
            comments=[comment("t1", "alice")],
        )
        analysis = metrics.compute(builder.build(snap))

        silent = [f for f in analysis.findings if f.metric == "silent_ratio"]
        assert len(silent) == 1
        assert silent[0].node_ids == [node_id(PERSON, uid("bob"))]


class TestDeterminism:
    """REL-2: identical input must produce identical scores."""

    def test_repeated_computation_is_identical(self, builder, metrics):
        snap = healthy_project(20)
        first = metrics.compute(builder.build(snap))
        second = metrics.compute(builder.build(snap))

        assert first.risk_scores == second.risk_scores
        assert first.overall_risk_level == second.overall_risk_level
        assert [f.model_dump() for f in first.findings] == [
            f.model_dump() for f in second.findings
        ]

    def test_snapshot_content_hash_is_stable(self):
        assert healthy_project(8).content_hash() == healthy_project(8).content_hash()

    def test_content_hash_changes_when_state_changes(self):
        a = healthy_project(8)
        b = healthy_project(9)
        assert a.content_hash() != b.content_hash()
