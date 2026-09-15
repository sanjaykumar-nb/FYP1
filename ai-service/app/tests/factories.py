"""Deterministic snapshot factories for graph tests.

UUIDs are derived from a label so failures name a recognisable node rather than
a random id.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.graph.snapshot import (
    CommentSnapshot,
    DependencySnapshot,
    MemberSnapshot,
    MilestoneSnapshot,
    ProjectSnapshot,
    TaskSnapshot,
)

NAMESPACE = uuid.UUID("00000000-0000-0000-0000-0000000000ff")
NOW = datetime(2026, 8, 19, tzinfo=timezone.utc)


def uid(label: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, label)


def member(label: str, role: str = "developer") -> MemberSnapshot:
    return MemberSnapshot(id=uid(label), full_name=label, email=f"{label}@example.com", role=role)


def milestone(label: str, days_out: int = 30) -> MilestoneSnapshot:
    return MilestoneSnapshot(
        id=uid(label), name=label, target_date=NOW + timedelta(days=days_out)
    )


def task(
    label: str,
    status: str = "backlog",
    points: int = 3,
    assignee: Optional[str] = None,
    milestone_label: Optional[str] = None,
    due_in_days: Optional[int] = None,
    priority: str = "medium",
    component: Optional[str] = None,
) -> TaskSnapshot:
    return TaskSnapshot(
        id=uid(label),
        title=label,
        status=status,
        priority=priority,
        story_points=points,
        assignee_id=uid(assignee) if assignee else None,
        milestone_id=uid(milestone_label) if milestone_label else None,
        component=component,
        due_date=NOW + timedelta(days=due_in_days) if due_in_days is not None else None,
    )


def blocks(blocking: str, blocked: str) -> DependencySnapshot:
    return DependencySnapshot(blocking_task_id=uid(blocking), blocked_task_id=uid(blocked))


def comment(task_label: str, user_label: str) -> CommentSnapshot:
    return CommentSnapshot(task_id=uid(task_label), user_id=uid(user_label), created_at=NOW)


def snapshot(**kwargs) -> ProjectSnapshot:
    kwargs.setdefault("project_id", uid("project"))
    kwargs.setdefault("name", "Test Project")
    kwargs.setdefault("as_of", NOW)
    return ProjectSnapshot(**kwargs)


def healthy_project(task_count: int = 12) -> ProjectSnapshot:
    """A well-balanced project: no overdue work, shared ownership, everyone talks."""
    members = [member(f"dev{i}") for i in range(3)]
    milestones = [milestone("alpha"), milestone("beta")]
    tasks, comments = [], []
    for i in range(task_count):
        owner = f"dev{i % 3}"
        ms = "alpha" if i % 2 == 0 else "beta"
        tasks.append(
            task(f"t{i}", status="in_progress" if i % 4 else "done",
                 points=3, assignee=owner, milestone_label=ms, due_in_days=30)
        )
        comments.append(comment(f"t{i}", owner))
        comments.append(comment(f"t{i}", f"dev{(i + 1) % 3}"))
    return snapshot(members=members, milestones=milestones, tasks=tasks, comments=comments)
