"""Wires the knowledge graph core (app.graph) into the agent pipeline.

This is the module that makes the coordinator "graph-grounded": it turns a
ProjectSnapshot into deterministic risk scores plus per-specialist witness
subgraphs, so agents explain computed findings instead of guessing at raw
data. See app.graph for the underlying graph, metrics, and grounding pieces.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from app.graph import (
    Finding,
    GraphAnalysis,
    GraphBuilder,
    GraphMetrics,
    ProjectGraph,
    ProjectSnapshot,
    SubgraphSelector,
    WitnessSubgraph,
)
from app.graph.actions import plan_rebalance
from app.models.agent_base import (
    AgentRecommendation,
    PlanningInput,
    ProgressInput,
    RecommendationOutput,
    RecommendedAction,
    RiskOutput,
    WorkloadIntelInput,
)

_selector = SubgraphSelector()

# Findings that speak to each specialist's concern. Planning cares about
# dependency structure, Progress about delay, Workload about workload/knowledge
# concentration — this is the fan-out mirror of fallback.py's fan-in mapping.
_PLANNING_RISK_TYPES = ("dependency",)
_PROGRESS_RISK_TYPES = ("delay", "coordination")
_WORKLOAD_RISK_TYPES = ("workload", "knowledge")

_REC_TEMPLATES: dict[str, dict] = {
    "delay": dict(type="split_task", title="Split large or overdue tasks",
                  reasoning="Large or overdue tasks have higher uncertainty and delay risk"),
    "workload": dict(type="redistribute", title="Redistribute workload",
                      reasoning="Uneven workload increases delay and burnout risk"),
    "coordination": dict(type="schedule_meeting", title="Schedule a team sync",
                          reasoning="Disconnected collaboration clusters lead to duplicated work"),
    "dependency": dict(type="reassign", title="Unblock the critical path",
                        reasoning="Dependency concentration creates single points of failure"),
    "knowledge": dict(type="pair_program", title="Pair on single-owner components",
                       reasoning="Sole ownership of a component is a knowledge risk if that person is unavailable"),
    "silent_member": dict(type="check_in", title="Check in with quiet team members",
                           reasoning="Members with no visible communication may be blocked or disengaged"),
}


def build_graph(snapshot: ProjectSnapshot) -> tuple[ProjectGraph, GraphAnalysis]:
    graph = GraphBuilder().build(snapshot)
    analysis = GraphMetrics().compute(graph)
    return graph, analysis


def _snapshot_dict_index(snapshot: ProjectSnapshot) -> tuple[list[dict], list[dict], list[dict]]:
    """Raw dict views the legacy fallback methods still expect."""
    milestones = [m.model_dump() for m in snapshot.milestones]
    tasks = [t.model_dump() for t in snapshot.tasks]
    assignments = [
        {"task_id": str(t.id), "assignee_id": str(t.assignee_id), "story_points": t.story_points or 0}
        for t in snapshot.tasks
        if t.assignee_id is not None
    ]
    return milestones, tasks, assignments


def build_planning_input(
    project_id: UUID, snapshot: ProjectSnapshot, graph: ProjectGraph, analysis: GraphAnalysis
) -> PlanningInput:
    milestones, tasks, _ = _snapshot_dict_index(snapshot)
    findings = analysis.findings_for(*_PLANNING_RISK_TYPES)
    witness = _selector.select(graph, findings)
    return PlanningInput(
        project_id=project_id,
        milestones=milestones,
        tasks=tasks,
        team_capacity={"total_points": snapshot.team_capacity_points} if snapshot.team_capacity_points else {},
        graph_context=witness.render(),
        finding_ids=list(witness.allowed_ids()),
    )


def build_progress_input(
    project_id: UUID, snapshot: ProjectSnapshot, graph: ProjectGraph, analysis: GraphAnalysis
) -> ProgressInput:
    _, tasks, _ = _snapshot_dict_index(snapshot)
    findings = analysis.findings_for(*_PROGRESS_RISK_TYPES)
    witness = _selector.select(graph, findings)
    return ProgressInput(
        project_id=project_id,
        tasks=tasks,
        velocity_history=list(snapshot.velocity_history),
        burndown_data=[],
        graph_context=witness.render(),
        finding_ids=list(witness.allowed_ids()),
    )


def build_workload_input(
    project_id: UUID, snapshot: ProjectSnapshot, graph: ProjectGraph, analysis: GraphAnalysis
) -> WorkloadIntelInput:
    _, _, assignments = _snapshot_dict_index(snapshot)
    findings = analysis.findings_for(*_WORKLOAD_RISK_TYPES)
    witness = _selector.select(graph, findings)
    return WorkloadIntelInput(
        project_id=project_id,
        assignments=assignments,
        story_points={a["task_id"]: a["story_points"] for a in assignments},
        graph_context=witness.render(),
        finding_ids=list(witness.allowed_ids()),
    )


def risk_output_from_graph(analysis: GraphAnalysis) -> RiskOutput:
    """Risk scores are always graph-computed — deterministic, zero tokens.

    An LLM is never in the loop for the *numbers*; it would only ever be
    asked to narrate them, and narration is optional polish, not something
    the score depends on.
    """
    top = analysis.findings[:5]
    summary = (
        f"Overall risk: {analysis.overall_risk_level}. "
        + "; ".join(str(f) for f in top) if top else
        f"Overall risk: {analysis.overall_risk_level}. No significant findings."
    )
    return RiskOutput(
        summary=summary[:500],
        risk_level=analysis.overall_risk_level,
        confidence=0.9 if analysis.findings else 0.6,
        signals=[],
        evidence=[
            {"source": "graph", "reference_id": nid, "excerpt": f.title, "relevance": 0.9}
            for f in top
            for nid in f.node_ids[:1]
        ],
        recommendations=[],
        next_action="Review risk findings and assign owners" if analysis.findings else "No action needed",
        risk_scores=dict(analysis.risk_scores),
        # Evidence carries one citation per finding; the full witness list lives here
        # so a UI can show every task and person behind each finding.
        metadata={
            "graph_stats": analysis.stats,
            "finding_count": len(analysis.findings),
            "findings": [f.model_dump() for f in top],
        },
    )


def recommendation_output_from_graph(
    analysis: GraphAnalysis, graph: Optional[ProjectGraph] = None
) -> RecommendationOutput:
    """One recommendation per risk type at medium+ severity, evidence-grounded
    against real graph node ids by construction (never fabricated). Given the
    graph, the workload recommendation also carries the reassignments that
    would carry it out (app.graph.actions)."""
    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    seen_types: set[str] = set()
    recs: list[AgentRecommendation] = []

    for finding in analysis.findings:
        if severity_rank.get(finding.severity, 0) < 2:
            continue
        if finding.risk_type in seen_types:
            continue
        template = _REC_TEMPLATES.get(finding.risk_type)
        if not template:
            continue
        seen_types.add(finding.risk_type)
        rec = AgentRecommendation(
            type=template["type"],
            title=template["title"],
            description=finding.title,
            reasoning=template["reasoning"],
            priority="high" if finding.severity in ("high", "critical") else "medium",
            confidence=0.75,
        )
        if finding.risk_type == "workload" and graph is not None:
            _attach_rebalance(rec, graph)
        recs.append(rec)

    return RecommendationOutput(
        summary=f"Generated {len(recs)} recommendation(s) from {len(analysis.findings)} graph finding(s)",
        risk_level=analysis.overall_risk_level,
        confidence=0.8 if recs else 0.5,
        signals=[],
        evidence=[],
        recommendations=recs,
        next_action="Review and prioritize recommendations" if recs else "No action needed",
        prioritized_actions=[r.model_dump() for r in recs],
    )


def _attach_rebalance(rec: AgentRecommendation, graph: ProjectGraph) -> None:
    plan = plan_rebalance(graph)
    if plan is None:
        return

    def name(nid: str) -> str:
        attrs = graph.attrs(nid)
        return attrs.get("name") or attrs.get("title") or nid

    rec.actions = [
        RecommendedAction(
            kind="reassign",
            task_id=m.task_id,
            from_person=m.from_person,
            to_person=m.to_person,
            points=m.points,
            summary=f"Move {name(m.task_id)} ({m.points} pts) from {name(m.from_person)} to {name(m.to_person)}",
        )
        for m in plan.moves
    ]
    rec.expected_effect = (
        f"Heaviest open load falls from {plan.peak_before} to {plan.peak_after} points against a "
        f"team mean of {plan.mean:.1f} — load skew {plan.severity_before} → {plan.severity_after}."
    )
