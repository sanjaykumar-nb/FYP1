"""The risk agent stores every finding with its full witness list, so a UI can
show all the tasks and people a finding rests on (evidence keeps only one)."""

import pytest

from app.services.graph_pipeline import build_graph, risk_output_from_graph
from app.tests.factories import member, snapshot, task, uid

pytestmark = pytest.mark.mvp


def _overdue_and_overloaded():
    members = [member("busy"), member("helper"), member("idle")]
    tasks = [
        task(f"late{i}", status="in_progress", points=5, assignee="busy", due_in_days=-3)
        for i in range(4)
    ]
    tasks.append(task("small", status="in_progress", points=1, assignee="helper", due_in_days=10))
    return snapshot(members=members, tasks=tasks)


def test_findings_carry_every_witness_node():
    graph, analysis = build_graph(_overdue_and_overloaded())
    risk = risk_output_from_graph(analysis)

    findings = risk.metadata["findings"]
    assert findings, "four overdue tasks on one person must produce findings"
    for finding in findings:
        assert set(finding) >= {"risk_type", "severity", "title", "metric", "value", "node_ids"}
        assert all(graph.has_node(nid) for nid in finding["node_ids"]), finding

    delay = next(f for f in findings if f["metric"] == "overdue_ratio")
    assert {f"task:{uid(f'late{i}')}" for i in range(4)} <= set(delay["node_ids"])


def test_evidence_cites_the_first_witness_of_each_finding():
    _, analysis = build_graph(_overdue_and_overloaded())
    risk = risk_output_from_graph(analysis)

    assert [e.reference_id for e in risk.evidence] == [
        f["node_ids"][0] for f in risk.metadata["findings"] if f["node_ids"]
    ]
