"""Token-efficiency tests for the graph-grounded pipeline (TOK-1..3).

These are the tests that back the Part F novelty claim: prompt cost is
O(anomalies), not O(project size), and the full JSON Schema never appears in
an outgoing prompt.
"""

import pytest

from app.graph import GraphBuilder, GraphMetrics, SubgraphSelector
from app.llm.client import _compact_schema_hint
from app.models.agent_base import PlanningOutput
from app.tests.factories import (
    blocks,
    comment,
    member,
    milestone,
    snapshot,
    task,
)

pytestmark = pytest.mark.mvp


def _approx_tokens(text: str) -> int:
    # The same rough chars/4 heuristic used to size the original ~62k-token
    # baseline in the plan — good enough to catch a regression by an order
    # of magnitude, which is what these tests guard against.
    return len(text) // 4


def _mixed_project(task_count: int, overloaded_ratio: float = 0.15) -> "snapshot":
    """A project with a fixed number of genuine anomalies, regardless of size,
    so growing task_count should NOT grow the rendered witness subgraph."""
    members = [member(f"dev{i}") for i in range(5)]
    milestones_ = [milestone(f"m{i}") for i in range(3)]
    tasks = []
    n_overloaded_tasks = max(2, int(task_count * overloaded_ratio))
    for i in range(task_count):
        # Pile a fixed share of load onto dev0 (the anomaly); spread the rest
        # evenly so the *ratio* of anomalies stays constant as the project grows.
        owner = "dev0" if i < n_overloaded_tasks else f"dev{1 + (i % 4)}"
        tasks.append(task(
            f"t{i}", assignee=owner, milestone_label=f"m{i % 3}",
            status="in_progress", points=3, due_in_days=30,
        ))
    return snapshot(members=members, milestones=milestones_, tasks=tasks)


class TestPromptSize:
    """TOK-1: a realistic project must render a small prompt."""

    def test_planning_prompt_under_3000_tokens_for_200_tasks(self):
        snap = _mixed_project(200)
        graph = GraphBuilder().build(snap)
        analysis = GraphMetrics().compute(graph)
        witness = SubgraphSelector().select(graph, analysis.findings_for("dependency", "delay", "workload"))

        rendered = witness.render()
        assert _approx_tokens(rendered) < 3000, (
            f"witness subgraph rendered to ~{_approx_tokens(rendered)} tokens "
            f"for a 200-task project — expected well under 3000"
        )


class TestPromptScalesWithAnomaliesNotSize:
    """TOK-2: prompt size tracks anomaly count, not project size."""

    def test_50_vs_2000_tasks_same_anomaly_ratio_stays_within_20pct(self):
        small = _mixed_project(50)
        large = _mixed_project(2000)

        def render_size(snap):
            graph = GraphBuilder().build(snap)
            analysis = GraphMetrics().compute(graph)
            witness = SubgraphSelector().select(
                graph, analysis.findings_for("dependency", "delay", "workload")
            )
            return len(witness.render())

        small_size = render_size(small)
        large_size = render_size(large)

        # Not exactly equal — a bigger anomaly set produces slightly more
        # witness nodes even at a fixed ratio — but nowhere near the ~40x
        # growth in raw task count between the two projects.
        assert small_size > 0
        growth = large_size / small_size
        assert growth < 1.20, (
            f"witness subgraph grew {growth:.2f}x between a 50-task and a "
            f"2000-task project at the same anomaly ratio — expected <1.20x "
            f"(task count grew 40x)"
        )


class TestNoFullSchemaInPrompt:
    """TOK-3: only the compact field:type hint is ever sent — never a full
    JSON Schema dump (guards T1 from regressing back to the ~4.7k-token
    baseline)."""

    def test_compact_hint_omits_json_schema_markers(self):
        schema = PlanningOutput.model_json_schema()
        hint = _compact_schema_hint(schema)

        for marker in ("$defs", '"properties"', '"additionalProperties"', "$ref"):
            assert marker not in hint

        # It must still be useful: every required field name appears.
        for field in schema.get("required", []):
            assert field in hint

    def test_compact_hint_is_far_smaller_than_full_schema(self):
        import json

        schema = PlanningOutput.model_json_schema()
        full = json.dumps(schema, indent=2)
        hint = _compact_schema_hint(schema)

        assert len(hint) < len(full) * 0.25
