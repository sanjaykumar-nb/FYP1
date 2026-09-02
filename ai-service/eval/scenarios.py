"""Synthetic project scenarios with a known, injected ground-truth condition.

No external dataset is used here (that's Phase E1 — Jira/TAWOS, deferred).
This is the zero-label evaluation described in the plan's Part A2: each
scenario is generated so a *specific* graph metric is guaranteed to fire (or
not) by construction, which makes precision/recall computable without any
human labeling. Reuses app.tests.factories rather than re-implementing
snapshot construction.

Each risk type in GraphMetrics aggregates more than one sub-signal (e.g.
"dependency" covers both cycles and critical-path share), so ground truth is
tracked against the specific *metric* a scenario targets, not the coarser
risk-level bucket — otherwise an unrelated sub-signal firing by chance would
look like a false positive.

The anomaly-carrying tasks are always injected deterministically (never left
to chance); only the surrounding "noise" tasks are randomized, so a scenario
instance's label is never ambiguous.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.graph.snapshot import ProjectSnapshot
from app.tests.factories import blocks, comment, member, milestone, snapshot, task


@dataclass
class Scenario:
    risk_type: str
    metric: str
    label: bool  # True = anomaly was injected (positive case)
    snapshot: ProjectSnapshot
    description: str


def _team(n: int, prefix: str = "dev") -> list[str]:
    return [f"{prefix}{i}" for i in range(n)]


def cycle_scenario(rng: random.Random, positive: bool, size: int) -> Scenario:
    team = _team(rng.randint(3, 6))
    members = [member(t) for t in team]
    tasks = [task(f"t{i}", assignee=rng.choice(team), status="in_progress") for i in range(3, size)]
    tasks += [task(f"c{i}", assignee=team[0], status="in_progress") for i in range(3)]
    deps = [blocks("c0", "c1"), blocks("c1", "c2")]
    if positive:
        deps.append(blocks("c2", "c0"))  # closes the loop
    return Scenario(
        "dependency", "cycle_count", positive,
        snapshot(members=members, tasks=tasks, dependencies=deps),
        f"{'cyclic' if positive else 'acyclic'} 3-task chain among {size} tasks",
    )


def spof_scenario(rng: random.Random, positive: bool, size: int) -> Scenario:
    team = _team(rng.randint(3, 6))
    members = [member(t) for t in team]
    milestones = [milestone("comp_a"), milestone("comp_b")]
    # comp_a: sole-owned by dev0 when positive, shared otherwise. Always >=2
    # tasks so it clears SPOF_MIN_COMPONENT_TASKS regardless of `size`.
    tasks = [
        task("a0", assignee="dev0", milestone_label="comp_a", status="in_progress"),
        task("a1", assignee=("dev0" if positive else (team[1] if len(team) > 1 else "dev0")),
             milestone_label="comp_a", status="in_progress"),
    ]
    for i in range(size):
        tasks.append(task(f"b{i}", assignee=rng.choice(team), milestone_label="comp_b", status="in_progress"))
    return Scenario(
        "knowledge", "sole_owner_ratio", positive,
        snapshot(members=members, milestones=milestones, tasks=tasks),
        f"{'sole-owner' if positive else 'shared'} component among {size + 2} tasks",
    )


def workload_scenario(rng: random.Random, positive: bool, size: int) -> Scenario:
    team = _team(rng.randint(3, 6))
    members = [member(t) for t in team]
    tasks = []
    # dev0 carries a block of heavy (13-point) tasks when positive; everyone
    # else gets light, even load either way. Scaled with `size` — a fixed
    # headcount of extra tasks gets diluted to nothing on a large project,
    # same as it would in a real one.
    if positive:
        n_heavy = max(3, size // 6)
        tasks += [task(f"h{i}", assignee="dev0", points=13, status="in_progress") for i in range(n_heavy)]
    for i in range(size):
        owner = team[i % len(team)]  # round-robin: guaranteed even in the negative case
        tasks.append(task(f"t{i}", assignee=owner, points=2, status="in_progress"))
    return Scenario(
        "workload", "workload_skew", positive,
        snapshot(members=members, tasks=tasks),
        f"{'3 heavy tasks on one person' if positive else 'even round-robin'} among {size} tasks",
    )


def delay_scenario(rng: random.Random, positive: bool, size: int) -> Scenario:
    team = _team(rng.randint(3, 6))
    members = [member(t) for t in team]
    tasks = []
    for i in range(size):
        # Half the tasks overdue when positive; none when negative.
        overdue = positive and i % 2 == 0
        due = -rng.randint(1, 20) if overdue else rng.randint(10, 60)
        tasks.append(task(f"t{i}", assignee=rng.choice(team), status="in_progress", due_in_days=due))
    return Scenario(
        "delay", "overdue_ratio", positive,
        snapshot(members=members, tasks=tasks),
        f"{'50%' if positive else '0%'} overdue among {size} tasks",
    )


def silent_member_scenario(rng: random.Random, positive: bool, size: int) -> Scenario:
    team = _team(rng.randint(3, 6))
    members = [member(t) for t in team]
    # SILENT_RATIO_MEDIUM is a threshold on the FRACTION of assigned members
    # who never comment (0.30) — so the silent group must scale with team
    # size, not be a fixed headcount, or a single silent person dilutes below
    # the threshold once the team is larger than ~3.
    n_silent = max(1, (len(team) * 2 + 4) // 5)  # ~40% of the team, rounded
    silent = set(team[:n_silent])

    tasks = [task(f"s{j}", assignee=lbl, status="in_progress") for j, lbl in enumerate(team)]
    tasks += [task(f"t{i}", assignee=team[i % len(team)], status="in_progress") for i in range(size)]
    comments = []
    for t in tasks:
        assignee_label = next(lbl for lbl in team if member(lbl).id == t.assignee_id)
        if positive and assignee_label in silent:
            continue
        comments.append(comment(t.title, assignee_label))
    return Scenario(
        "silent_member", "silent_ratio", positive,
        snapshot(members=members, tasks=tasks, comments=comments),
        f"{f'{len(silent)}/{len(team)} silent' if positive else 'everyone comments'} among {size + len(team)} tasks",
    )


def coordination_scenario(rng: random.Random, positive: bool, size: int) -> Scenario:
    team = _team(max(4, rng.randint(4, 7)))
    members = [member(t) for t in team]
    milestones = [milestone("m1"), milestone("m2")]
    tasks = [task("iso0", assignee="dev0", milestone_label="m1", status="in_progress")]
    if not positive:
        # Deterministically pull EVERY team member into shared work first, so
        # nobody can end up isolated purely by chance not being rng.choice()'d
        # among the `size` random tasks below.
        for j, member_label in enumerate(team):
            tasks.append(task(f"shared{j}", assignee=member_label, milestone_label="m2", status="in_progress"))
    for i in range(size):
        owner = rng.choice(team[1:]) if positive else rng.choice(team)
        tasks.append(task(f"t{i}", assignee=owner, milestone_label="m2", status="in_progress"))
    return Scenario(
        "coordination", "isolated_member_count", positive,
        snapshot(members=members, milestones=milestones, tasks=tasks),
        f"{'isolated silo' if positive else 'shared work'}, {len(team)} people, {size + 1} tasks",
    )


SCENARIO_BUILDERS = {
    "dependency": cycle_scenario,
    "knowledge": spof_scenario,
    "workload": workload_scenario,
    "delay": delay_scenario,
    "silent_member": silent_member_scenario,
    "coordination": coordination_scenario,
}


def generate_scenarios(seed: int = 42, per_type: int = 30, sizes: tuple[int, ...] = (10, 30, 80)) -> list[Scenario]:
    """Balanced positive/negative cases per risk type, across a few project sizes."""
    rng = random.Random(seed)
    out: list[Scenario] = []
    for risk_type, builder in SCENARIO_BUILDERS.items():
        for i in range(per_type):
            positive = i % 2 == 0
            size = sizes[i % len(sizes)]
            out.append(builder(rng, positive, size))
    return out
