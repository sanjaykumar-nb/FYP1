"""Concrete fixes for workload findings.

"Redistribute workload" leaves a manager to work out what to move, and to whom.
This proposes the moves themselves, computed on the same graph and the same
open-point loads as the finding (metrics.open_point_loads), so every task and
person it names is a real node and its projected effect is judged by the same
thresholds as the risk score.
"""

from __future__ import annotations

import statistics
from typing import Optional

from pydantic import BaseModel

from app.graph.builder import KNOWS, TOUCHES, ProjectGraph
from app.graph.metrics import (
    WORKLOAD_SKEW_CRITICAL,
    WORKLOAD_SKEW_HIGH,
    WORKLOAD_SKEW_MEDIUM,
    _level_from,
    open_point_loads,
)

MAX_MOVES = 3
NOT_STARTED = frozenset({"backlog", "planned"})


class Reassignment(BaseModel):
    task_id: str
    from_person: str
    to_person: str
    points: int  # what the task counts toward load (unestimated tasks count as 1)


class RebalancePlan(BaseModel):
    moves: list[Reassignment]
    mean: float
    peak_before: int
    peak_after: int
    severity_before: str
    severity_after: str


def _skew_severity(peak: float, mean: float) -> str:
    return _level_from(peak / mean, WORKLOAD_SKEW_MEDIUM, WORKLOAD_SKEW_HIGH, WORKLOAD_SKEW_CRITICAL)


def plan_rebalance(graph: ProjectGraph, max_moves: int = MAX_MOVES) -> Optional[RebalancePlan]:
    """Greedy: take open work off the busiest person until load skew is low.

    Each move hands one of the busiest person's open tasks to the teammate that
    leaves the pair most even — ties going to the less-loaded teammate, then to
    one who already knows the task's component, then to work not yet started.
    A move must strictly lighten the busiest person. Returns None when load skew
    is already low or no move helps.

    Remaining ties go by task title and person name, not node id. Ids are minted
    by the database, so two imports of the same sprint get different ones; ordering
    by them made the same project get different (equally good) suggestions each
    time it was loaded. Titles and names are what the user reads, and they stay put.
    """
    load, assignments = open_point_loads(graph)
    if len(load) < 2 or not any(load.values()):
        return None
    mean = statistics.mean(load.values())
    peak_before = max(load.values())
    severity_before = _skew_severity(peak_before, mean)
    if severity_before == "low":
        return None

    owner = {task: person for person, task, _ in assignments}
    weight = {task: w for _, task, w in assignments}
    status = {n: a.get("status") for n, a in graph.task_attrs().items()}
    knows = set(graph.edges_of_kind(KNOWS))
    components: dict[str, set[str]] = {}
    for task, comp in graph.edges_of_kind(TOUCHES):
        components.setdefault(task, set()).add(comp)

    def label(node: str) -> tuple[str, str]:
        attrs = graph.attrs(node)
        return (attrs.get("title") or attrs.get("name") or "", node)

    moves: list[Reassignment] = []
    while len(moves) < max_moves:
        busiest = max(sorted(load, key=label), key=lambda p: load[p])
        if _skew_severity(load[busiest], mean) == "low":
            break

        best = None
        for task in sorted((t for t, p in owner.items() if p == busiest), key=label):
            w = weight[task]
            for receiver in sorted(load, key=label):
                if receiver == busiest:
                    continue
                pair_peak = max(load[busiest] - w, load[receiver] + w)
                if pair_peak >= load[busiest]:
                    continue
                familiar = any((receiver, c) in knows for c in components.get(task, ()))
                key = (pair_peak, load[receiver], not familiar,
                       status.get(task) not in NOT_STARTED, label(task), label(receiver))
                if best is None or key < best[0]:
                    best = (key, task, receiver)
        if best is None:
            break

        _, task, receiver = best
        load[busiest] -= weight[task]
        load[receiver] += weight[task]
        owner[task] = receiver
        moves.append(Reassignment(task_id=task, from_person=busiest, to_person=receiver, points=weight[task]))

    if not moves:
        return None
    peak_after = max(load.values())
    return RebalancePlan(
        moves=moves,
        # Unrounded: callers format it the way the finding does, so both quote the same mean.
        mean=mean,
        peak_before=peak_before,
        peak_after=peak_after,
        severity_before=severity_before,
        severity_after=_skew_severity(peak_after, mean),
    )
