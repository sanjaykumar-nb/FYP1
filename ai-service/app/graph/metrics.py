"""Deterministic risk computation over the project knowledge graph.

Every one of the six risk types is a graph property, not an LLM inference. The
LLM's job downstream is to *explain* these findings, never to produce the
numbers. That gives reproducible scores (identical input => identical output)
and costs zero tokens.

Thresholds are module-level constants so they are auditable and tunable in one
place — they are part of the method, not hidden in the code.
"""

from __future__ import annotations

import statistics
from datetime import date, datetime, timezone
from typing import Optional

import networkx as nx
from pydantic import BaseModel, Field

from app.graph.builder import (
    ASSIGNED_TO,
    COMMENTED_ON,
    COMPONENT,
    KNOWS,
    MILESTONE,
    PART_OF,
    PERSON,
    TASK,
    ProjectGraph,
)

RISK_TYPES = (
    "delay",
    "coordination",
    "workload",
    "dependency",
    "knowledge",
    "silent_member",
)

LEVELS = ("low", "medium", "high", "critical")
_LEVEL_RANK = {lvl: i for i, lvl in enumerate(LEVELS)}

# --- thresholds ----------------------------------------------------------
OVERDUE_RATIO_MEDIUM = 0.10
OVERDUE_RATIO_HIGH = 0.25
OVERDUE_RATIO_CRITICAL = 0.40

BLOCKED_RATIO_MEDIUM = 0.10
BLOCKED_RATIO_HIGH = 0.20

# A milestone's pace is extrapolated only once this share of its schedule has
# passed; earlier, one slow first day would read as a failing sprint. Projected
# unfinished work is graded with the OVERDUE_RATIO_* cut-offs, so the pace signal
# adds no thresholds of its own.
PACE_MIN_ELAPSED = 0.25

# Ratio of the busiest person's points to the team mean.
WORKLOAD_SKEW_MEDIUM = 1.5
WORKLOAD_SKEW_HIGH = 2.0
WORKLOAD_SKEW_CRITICAL = 3.0

# Fraction of the open-task graph sitting on the single longest blocking chain.
CRITICAL_PATH_SHARE_MEDIUM = 0.25
CRITICAL_PATH_SHARE_HIGH = 0.40

# A person is a knowledge SPOF when they are the sole owner of a component
# holding at least this many tasks.
SPOF_MIN_COMPONENT_TASKS = 2

# Fraction of assigned members who never comment.
SILENT_RATIO_MEDIUM = 0.30
SILENT_RATIO_HIGH = 0.50


def _level_from(value: float, medium: float, high: float,
                critical: Optional[float] = None) -> str:
    if critical is not None and value >= critical:
        return "critical"
    if value >= high:
        return "high"
    if value >= medium:
        return "medium"
    return "low"


def max_level(levels) -> str:
    levels = [l for l in levels if l in _LEVEL_RANK]
    if not levels:
        return "low"
    return max(levels, key=lambda l: _LEVEL_RANK[l])


def open_point_loads(graph: ProjectGraph) -> tuple[dict[str, int], list[tuple[str, str, int]]]:
    """Open-work load per person: points of their unfinished tasks, each counting at least 1.

    Returns every person's load (zero included) and the open assignments behind
    it as (person, task, weight). The workload finding and the rebalancing plan
    (app.graph.actions) both use this, so they always agree on who carries what.
    """
    open_tasks = {n for n, a in graph.task_attrs().items() if not a.get("is_done")}
    load = {p: 0 for p in graph.nodes_of(PERSON)}
    assignments: list[tuple[str, str, int]] = []
    for person, task, points in graph.assignment_pairs():
        if task in open_tasks:
            weight = max(points, 1)
            load[person] = load.get(person, 0) + weight
            assignments.append((person, task, weight))
    return load, assignments


class Finding(BaseModel):
    """One computed risk observation plus the graph nodes that witness it."""

    risk_type: str
    severity: str
    title: str
    metric: str
    value: float
    node_ids: list[str] = Field(default_factory=list)

    def __str__(self) -> str:  # compact, for prompt rendering
        return f"[{self.risk_type}/{self.severity}] {self.title} ({self.metric}={self.value:g})"


class GraphAnalysis(BaseModel):
    risk_scores: dict[str, str] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    overall_risk_level: str = "low"
    stats: dict = Field(default_factory=dict)

    def findings_for(self, *risk_types: str) -> list[Finding]:
        wanted = set(risk_types)
        return [f for f in self.findings if f.risk_type in wanted]


def _utc(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class PaceProjection(BaseModel):
    """Where a milestone's work will stand at its deadline if the pace so far holds."""

    milestone_id: str
    name: str
    elapsed: float                # share of the start -> deadline window that has passed
    completed: float              # share of the work done (story points, at least 1 per task)
    projected_unfinished: float   # share still open at the deadline on this pace
    open_task_ids: list[str] = Field(default_factory=list)


def pace_projections(graph: ProjectGraph, now: datetime) -> list[PaceProjection]:
    """Linear burn-down extrapolation per milestone: projected completion at the
    deadline = completed / elapsed. Only milestones with a start date and a deadline
    still ahead are projected (PACE_MIN_ELAPSED <= elapsed < 1); once the deadline
    has passed, the overdue signal speaks for their unfinished work."""
    tasks = graph.task_attrs()
    work: dict[str, list[str]] = {}
    for u, v in graph.edges_of_kind(PART_OF):
        task, milestone = (u, v) if graph.attrs(v).get("kind") == MILESTONE else (v, u)
        if task in tasks:
            work.setdefault(milestone, []).append(task)

    now = _utc(now)
    out: list[PaceProjection] = []
    for milestone in graph.nodes_of(MILESTONE):
        attrs = graph.attrs(milestone)
        start, deadline = _utc(attrs.get("start_date")), _utc(attrs.get("target_date"))
        members = sorted(work.get(milestone, []))
        if start is None or deadline is None or deadline <= start or not members:
            continue
        elapsed = (now - start) / (deadline - start)
        if not PACE_MIN_ELAPSED <= elapsed < 1:
            continue
        weight = {t: max(tasks[t].get("points") or 0, 1) for t in members}
        done = sum(w for t, w in weight.items() if tasks[t].get("is_done"))
        completed = done / sum(weight.values())
        out.append(PaceProjection(
            milestone_id=milestone,
            name=attrs.get("name") or milestone,
            elapsed=round(elapsed, 4),
            completed=round(completed, 4),
            projected_unfinished=round(max(0.0, 1 - completed / elapsed), 4),
            open_task_ids=[t for t in members if not tasks[t].get("is_done")],
        ))
    return out


class GraphMetrics:
    """Computes all six risk scores from a ProjectGraph."""

    def __init__(self, now: Optional[datetime] = None):
        self.now = now or datetime.now(timezone.utc)

    def compute(self, graph: ProjectGraph) -> GraphAnalysis:
        findings: list[Finding] = []
        findings += self._delay(graph)
        findings += self._dependency(graph)
        findings += self._workload(graph)
        findings += self._knowledge(graph)
        findings += self._coordination(graph)
        findings += self._silent_members(graph)

        scores = {rt: "low" for rt in RISK_TYPES}
        for f in findings:
            scores[f.risk_type] = max_level([scores[f.risk_type], f.severity])

        findings.sort(key=lambda f: (-_LEVEL_RANK[f.severity], f.risk_type, f.title))

        return GraphAnalysis(
            risk_scores=scores,
            findings=findings,
            overall_risk_level=max_level(scores.values()),
            stats=graph.stats(),
        )

    # -- helpers ----------------------------------------------------------

    def _open_tasks(self, graph: ProjectGraph) -> dict[str, dict]:
        return {n: a for n, a in graph.task_attrs().items() if not a.get("is_done")}

    def _is_overdue(self, attrs: dict) -> bool:
        due = attrs.get("due_date")
        if due is None or attrs.get("is_done"):
            return False
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        return due < self.now

    # -- risk: delay ------------------------------------------------------

    def _delay(self, graph: ProjectGraph) -> list[Finding]:
        tasks = graph.task_attrs()
        if not tasks:
            return []
        open_tasks = self._open_tasks(graph)
        if not open_tasks:
            return []

        overdue = sorted(n for n, a in open_tasks.items() if self._is_overdue(a))
        ratio = len(overdue) / len(open_tasks)
        out: list[Finding] = []
        if overdue:
            out.append(Finding(
                risk_type="delay",
                severity=_level_from(ratio, OVERDUE_RATIO_MEDIUM, OVERDUE_RATIO_HIGH,
                                     OVERDUE_RATIO_CRITICAL),
                title=f"{len(overdue)} of {len(open_tasks)} open tasks are past their due date",
                metric="overdue_ratio",
                value=round(ratio, 3),
                node_ids=overdue[:20],
            ))

        blocked = sorted(n for n, a in open_tasks.items() if a.get("status") == "blocked")
        if blocked:
            b_ratio = len(blocked) / len(open_tasks)
            out.append(Finding(
                risk_type="delay",
                severity=_level_from(b_ratio, BLOCKED_RATIO_MEDIUM, BLOCKED_RATIO_HIGH),
                title=f"{len(blocked)} open tasks are in the blocked state",
                metric="blocked_ratio",
                value=round(b_ratio, 3),
                node_ids=blocked[:20],
            ))

        # Early warning: behind pace before the deadline, while there is still time to act.
        for pace in pace_projections(graph, self.now):
            if pace.projected_unfinished < OVERDUE_RATIO_MEDIUM:
                continue
            out.append(Finding(
                risk_type="delay",
                severity=_level_from(pace.projected_unfinished, OVERDUE_RATIO_MEDIUM,
                                     OVERDUE_RATIO_HIGH, OVERDUE_RATIO_CRITICAL),
                title=(f"'{pace.name}' is {pace.elapsed:.0%} through its schedule with "
                       f"{pace.completed:.0%} of its work done; at this pace "
                       f"{pace.projected_unfinished:.0%} will still be open at the deadline"),
                metric="projected_unfinished",
                value=pace.projected_unfinished,
                node_ids=pace.open_task_ids[:20],
            ))
        return out

    # -- risk: dependency -------------------------------------------------

    def _dependency(self, graph: ProjectGraph) -> list[Finding]:
        dag = graph.blocks_digraph()
        out: list[Finding] = []
        if dag.number_of_edges() == 0:
            return out

        # Circular dependencies are always critical — nothing in the cycle can start.
        cycles = [sorted(c) for c in nx.simple_cycles(dag)]
        if cycles:
            cycles.sort()
            witness = sorted({n for c in cycles for n in c})
            out.append(Finding(
                risk_type="dependency",
                severity="critical",
                title=f"{len(cycles)} circular dependency chain(s) detected",
                metric="cycle_count",
                value=float(len(cycles)),
                node_ids=witness[:20],
            ))
            return out  # centrality is meaningless on a cyclic graph

        open_tasks = self._open_tasks(graph)
        open_dag = dag.subgraph(sorted(open_tasks)).copy()
        if open_dag.number_of_nodes() >= 2 and open_dag.number_of_edges() > 0:
            path = nx.dag_longest_path(open_dag)
            share = len(path) / max(len(open_tasks), 1)
            if len(path) >= 2:
                out.append(Finding(
                    risk_type="dependency",
                    severity=_level_from(share, CRITICAL_PATH_SHARE_MEDIUM,
                                         CRITICAL_PATH_SHARE_HIGH),
                    title=f"Critical path spans {len(path)} chained open tasks",
                    metric="critical_path_share",
                    value=round(share, 3),
                    node_ids=list(path),
                ))

            centrality = nx.betweenness_centrality(open_dag)
            if centrality:
                top, score = max(sorted(centrality.items()), key=lambda kv: kv[1])
                if score > 0:
                    out.append(Finding(
                        risk_type="dependency",
                        severity=_level_from(score, 0.15, 0.30),
                        title=f"'{graph.attrs(top).get('title', top)}' is a dependency bottleneck",
                        metric="betweenness_centrality",
                        value=round(score, 3),
                        node_ids=[top],
                    ))
        return out

    # -- risk: workload ---------------------------------------------------

    def _workload(self, graph: ProjectGraph) -> list[Finding]:
        people = graph.nodes_of(PERSON)
        if len(people) < 2:
            return []

        load, _ = open_point_loads(graph)

        assigned = {p: v for p, v in load.items() if v > 0}
        if not assigned:
            return []

        mean = statistics.mean(load.values())
        if mean <= 0:
            return []

        busiest, busiest_load = max(sorted(load.items()), key=lambda kv: kv[1])
        skew = busiest_load / mean

        out = [Finding(
            risk_type="workload",
            severity=_level_from(skew, WORKLOAD_SKEW_MEDIUM, WORKLOAD_SKEW_HIGH,
                                 WORKLOAD_SKEW_CRITICAL),
            title=(f"'{graph.attrs(busiest).get('name', busiest)}' carries {busiest_load} open "
                   f"points vs a team mean of {mean:.1f}"),
            metric="workload_skew",
            value=round(skew, 3),
            node_ids=[busiest],
        )]

        idle = sorted(p for p, v in load.items() if v == 0)
        if idle and len(idle) < len(people):
            out.append(Finding(
                risk_type="workload",
                severity="medium" if len(idle) / len(people) >= 0.34 else "low",
                title=f"{len(idle)} team member(s) have no open assigned work",
                metric="idle_member_ratio",
                value=round(len(idle) / len(people), 3),
                node_ids=idle[:20],
            ))
        return out

    # -- risk: knowledge (single points of failure) -----------------------

    def _knowledge(self, graph: ProjectGraph) -> list[Finding]:
        out: list[Finding] = []
        pc = graph.person_component_graph()
        if pc.number_of_edges() == 0:
            return out

        # Sole ownership: a component only one person has ever worked in.
        owners: dict[str, list[str]] = {}
        for person, comp in graph.edges_of_kind(KNOWS):
            owners.setdefault(comp, []).append(person)

        task_count: dict[str, int] = {}
        for _task, comp in graph.edges_of_kind("TOUCHES"):
            task_count[comp] = task_count.get(comp, 0) + 1

        spofs: list[tuple[str, str]] = []
        for comp, people in sorted(owners.items()):
            if len(set(people)) == 1 and task_count.get(comp, 0) >= SPOF_MIN_COMPONENT_TASKS:
                spofs.append((people[0], comp))

        if spofs:
            witness = sorted({n for pair in spofs for n in pair})
            names = sorted({graph.attrs(p).get("name", p) for p, _ in spofs})
            ratio = len(spofs) / max(len(owners), 1)
            out.append(Finding(
                risk_type="knowledge",
                severity=_level_from(ratio, 0.20, 0.40, 0.60),
                title=(f"{len(spofs)} component(s) have a single owner: "
                       f"{', '.join(names[:3])}"),
                metric="sole_owner_ratio",
                value=round(ratio, 3),
                node_ids=witness,
            ))

        # Articulation points: removing this person disconnects the knowledge map.
        cut_people = sorted(
            n for n in nx.articulation_points(pc)
            if graph.attrs(n).get("kind") == PERSON
        )
        if cut_people:
            out.append(Finding(
                risk_type="knowledge",
                severity="high" if len(cut_people) > 1 else "medium",
                title=(f"{len(cut_people)} member(s) are articulation points — their "
                       f"departure splits the knowledge map"),
                metric="articulation_person_count",
                value=float(len(cut_people)),
                node_ids=cut_people,
            ))
        return out

    # -- risk: coordination ----------------------------------------------

    def _coordination(self, graph: ProjectGraph) -> list[Finding]:
        # Shared work context is judged through components, so only people with work in
        # at least one component can be judged. Someone with no assigned work, or whose
        # tasks name no component, is not evidence of a silo; idle members are the
        # workload measure's concern. With no component data at all, nobody is judged.
        known = {person for person, _ in graph.edges_of_kind(KNOWS)}
        people = [p for p in graph.nodes_of(PERSON) if p in known]
        if len(people) < 3:
            return []
        collab = graph.collaboration_graph().subgraph(people)

        components = [sorted(c) for c in nx.connected_components(collab)]
        components.sort()
        # Members with no collaboration edge at all are isolated silos of one.
        isolated = sorted(n for n in collab.nodes if collab.degree(n) == 0)

        out: list[Finding] = []
        if len(components) > 1:
            ratio = len(components) / len(people)
            out.append(Finding(
                risk_type="coordination",
                severity=_level_from(ratio, 0.34, 0.50, 0.75),
                title=(f"Team splits into {len(components)} non-collaborating "
                       f"cluster(s) across {len(people)} members"),
                metric="cluster_ratio",
                value=round(ratio, 3),
                node_ids=[c[0] for c in components][:20],
            ))
        if isolated:
            out.append(Finding(
                risk_type="coordination",
                severity="medium" if len(isolated) < len(people) else "high",
                title=f"{len(isolated)} member(s) share no work context with anyone",
                metric="isolated_member_count",
                value=float(len(isolated)),
                node_ids=isolated[:20],
            ))
        return out

    # -- risk: silent member ---------------------------------------------

    def _silent_members(self, graph: ProjectGraph) -> list[Finding]:
        assigned_people = sorted({p for p, _t, _pts in graph.assignment_pairs()})
        if not assigned_people:
            return []

        commenters = {u for u, _v in graph.edges_of_kind(COMMENTED_ON)}
        silent = sorted(p for p in assigned_people if p not in commenters)
        if not silent:
            return []

        ratio = len(silent) / len(assigned_people)
        return [Finding(
            risk_type="silent_member",
            severity=_level_from(ratio, SILENT_RATIO_MEDIUM, SILENT_RATIO_HIGH),
            title=(f"{len(silent)} of {len(assigned_people)} assigned members have "
                   f"posted no comments"),
            metric="silent_ratio",
            value=round(ratio, 3),
            node_ids=silent[:20],
        )]
