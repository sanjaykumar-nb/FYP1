"""Build ProjectSnapshot objects (project x sprint) from the loaded TAWOS SQLite DB.

Ground truth for delay: TAWOS carries no `due_date` on Issue at all (confirmed
against TAWOS_schema.sql), so the label comes from what the data does have —
whether each issue was resolved by the end of its assigned sprint. A sprint
counts as "delayed" when at least SPRINT_DELAY_THRESHOLD of its issues were
not resolved in time (30% — the same bar used elsewhere in this codebase for
"this is a real problem, not noise", e.g. SILENT_RATIO_MEDIUM).

Point-in-time reconstruction matters here. Every issue in a years-old dataset
is long since resolved by the time this dump was taken, so a task's *current*
status can't be used directly — that would leak the future into a snapshot
that's supposed to represent "as of sprint end". Each task's `status` and
`due_date` are reconstructed as they would have looked at sprint end:
resolved-by-then -> done; not yet resolved-by-then -> still open, with
due_date set to the sprint's end (its implicit deadline), which is what lets
GraphMetrics' existing overdue-ratio signal — built for due_date, not sprint
membership — apply to this data unmodified. GraphMetrics itself must then be
run with `now=sprint_end`, not wall-clock time, or every historical sprint
would trivially read as 100% overdue.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from app.graph.snapshot import (
    CommentSnapshot,
    DependencySnapshot,
    MemberSnapshot,
    MilestoneSnapshot,
    ProjectSnapshot,
    TaskSnapshot,
)

DB_PATH = Path(__file__).parent / "tawos.db"
_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-0000000000aa")

SPRINT_DELAY_THRESHOLD = 0.30
MIN_ISSUES_PER_SPRINT = 15

# Verified against the real data's issue_link name/direction distribution
# (inspect_link_names, run before this was finalized) — the initial guess of
# {"Depend", "Block", "Blocker"} only matched ~2k of ~18.6k real dependency
# links; TAWOS's actual naming spreads the same relationship across several
# near-synonyms (plural/singular, "Dependency" as its own name).
BLOCKING_LINK_NAMES = {
    "Depends", "Depend", "Dependency",
    "Blocks", "Block", "Blocker", "Blockers", "Blocked",
    "Required",
}


@dataclass
class SprintCase:
    project_key: str
    sprint_jira_id: int
    sprint_end: str
    n_issues: int
    unresolved_fraction: float
    label_delayed: bool
    snapshot: ProjectSnapshot
    as_of: Optional[str] = None  # when the snapshot was taken: sprint end, or the checkpoint


def _uuid_for(label: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, label)


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "")[:19])


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"{DB_PATH} not found — run `python -m eval.datasets.tawos_load` first")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def inspect_link_names(conn: sqlite3.Connection) -> list[tuple]:
    """What dependency-like link names actually exist in this dump — run once
    to confirm BLOCKING_LINK_NAMES before trusting the dependency mapping."""
    return conn.execute(
        "SELECT name, direction, COUNT(*) FROM issue_link GROUP BY name, direction ORDER BY 3 DESC"
    ).fetchall()


def _map_status(raw: Optional[str]) -> str:
    if not raw:
        return "backlog"
    r = raw.lower()
    if "progress" in r or "review" in r:
        return "in_progress"
    if "block" in r:
        return "blocked"
    return "backlog"


def _map_priority(raw: Optional[str]) -> str:
    if not raw:
        return "medium"
    r = raw.lower()
    if "block" in r or "critical" in r or "highest" in r:
        return "critical"
    if "high" in r or "major" in r:
        return "high"
    if "low" in r or "minor" in r or "trivial" in r:
        return "low"
    return "medium"


def _eligible_sprints(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT s.id, s.jira_id, s.project_id, s.start_date, s.end_date, s.complete_date, p.project_key,
               COUNT(i.id) as n_issues
        FROM sprint s
        JOIN project p ON p.id = s.project_id
        JOIN issue i ON i.sprint_id = s.id
        WHERE s.state = 'CLOSED' AND (s.end_date IS NOT NULL OR s.complete_date IS NOT NULL)
        GROUP BY s.id
        HAVING n_issues >= ?
        """,
        (MIN_ISSUES_PER_SPRINT,),
    ).fetchall()


def velocity_history(conn: sqlite3.Connection, sprint_row: sqlite3.Row, window: int = 6) -> list[float]:
    """Story points the project completed in each sprint that had ended before this
    one started, oldest first — all its tracker could have known at sprint start.

    A sprint's completed points are those of its issues resolved by its end. (TAWOS
    files an issue under its last sprint, so work carried over counts where it finished.)
    """
    if not sprint_row["start_date"]:
        return []
    rows = conn.execute(
        """
        SELECT COALESCE(s.end_date, s.complete_date) AS ended,
               COALESCE(SUM(CASE WHEN i.resolution_date <= COALESCE(s.end_date, s.complete_date)
                            THEN i.story_point END), 0) AS done_points
        FROM sprint s
        JOIN issue i ON i.sprint_id = s.id
        WHERE s.project_id = ? AND s.id != ? AND s.state = 'CLOSED'
          AND COALESCE(s.end_date, s.complete_date) <= ?
        GROUP BY s.id
        ORDER BY ended DESC, s.id DESC
        LIMIT ?
        """,
        (sprint_row["project_id"], sprint_row["id"], sprint_row["start_date"], window),
    ).fetchall()
    return [float(r["done_points"]) for r in reversed(rows)]


def build_sprint_cases(
    conn: sqlite3.Connection, limit: Optional[int] = None, checkpoint: Optional[float] = None,
    with_velocity: bool = False,
) -> Iterator[SprintCase]:
    """Yield one case per eligible sprint.

    By default each snapshot is taken at sprint end. With `checkpoint` (e.g. 0.5)
    it is taken that far through the sprint's start -> end window instead: only
    issues created by then are in scope, only those resolved by then are done, and
    the sprint becomes a milestone carrying its start and end dates, so the pace
    signal can project it. The label is always the sprint's real outcome at its end.

    `with_velocity` adds the project's velocity before the sprint (velocity_history),
    from which the planning agent estimates capacity. It is off by default so the
    published evaluations' inputs stay exactly as they were.
    """
    sprints = _eligible_sprints(conn)
    if limit:
        sprints = sprints[:limit]

    for sprint_row in sprints:
        sprint_end = sprint_row["end_date"] or sprint_row["complete_date"]
        as_of, milestone_id = sprint_end, None
        if checkpoint is not None:
            start, end = _parse_ts(sprint_row["start_date"]), _parse_ts(sprint_end)
            as_of = (start + (end - start) * checkpoint).strftime("%Y-%m-%d %H:%M:%S")
            milestone_id = _uuid_for(f"sprint:{sprint_row['id']}")

        issues = conn.execute("SELECT * FROM issue WHERE sprint_id = ?", (sprint_row["id"],)).fetchall()
        issue_ids: set[int] = set()

        members_seen: dict[int, MemberSnapshot] = {}
        tasks: list[TaskSnapshot] = []
        n_unresolved_by_end = 0

        for row in issues:
            # The label is always the sprint's real outcome at its end.
            resolved_by_end = bool(row["resolution_date"]) and row["resolution_date"] <= sprint_end
            if not resolved_by_end:
                n_unresolved_by_end += 1

            # Reconstruct state AS OF the snapshot moment — not as of today's dump.
            if checkpoint is not None and row["creation_date"] and row["creation_date"] > as_of:
                continue  # not created yet, so not yet part of the sprint
            resolved_by_as_of = bool(row["resolution_date"]) and row["resolution_date"] <= as_of
            issue_ids.add(row["id"])

            assignee_id, reporter_id = row["assignee_id"], row["reporter_id"]
            for uid in (assignee_id, reporter_id):
                if uid is not None and uid not in members_seen:
                    members_seen[uid] = MemberSnapshot(id=_uuid_for(f"user:{uid}"), full_name=f"user{uid}")

            tasks.append(TaskSnapshot(
                id=_uuid_for(f"issue:{row['id']}"),
                title=row["issue_key"] or f"issue-{row['id']}",
                status="done" if resolved_by_as_of else _map_status(row["status"]),
                priority=_map_priority(row["priority"]),
                story_points=int(row["story_point"]) if row["story_point"] else None,
                assignee_id=_uuid_for(f"user:{assignee_id}") if assignee_id else None,
                reporter_id=_uuid_for(f"user:{reporter_id}") if reporter_id else None,
                milestone_id=milestone_id,
                due_date=sprint_end,  # the sprint's own boundary is the implicit deadline
                created_at=row["creation_date"],
                completed_at=row["resolution_date"] if resolved_by_as_of else None,
            ))

        deps = []
        if issue_ids:
            placeholders = ",".join("?" * len(issue_ids))
            links = conn.execute(
                f"SELECT * FROM issue_link WHERE issue_id IN ({placeholders}) "
                f"AND target_issue_id IN ({placeholders})",
                list(issue_ids) * 2,
            ).fetchall()
            for link in links:
                if link["name"] not in BLOCKING_LINK_NAMES or link["direction"] != "INBOUND":
                    continue  # INBOUND-only avoids double-counting the mirrored OUTBOUND row
                deps.append(DependencySnapshot(
                    blocking_task_id=_uuid_for(f"issue:{link['issue_id']}"),
                    blocked_task_id=_uuid_for(f"issue:{link['target_issue_id']}"),
                ))

        comments = []
        if issue_ids:
            placeholders = ",".join("?" * len(issue_ids))
            for c in conn.execute(f"SELECT * FROM comment WHERE issue_id IN ({placeholders})", list(issue_ids)):
                # Comments made after the snapshot moment didn't exist yet.
                if c["author_id"] is None or not c["creation_date"] or c["creation_date"] > as_of:
                    continue
                comments.append(CommentSnapshot(
                    task_id=_uuid_for(f"issue:{c['issue_id']}"),
                    user_id=_uuid_for(f"user:{c['author_id']}"),
                    created_at=c["creation_date"],
                ))

        unresolved_fraction = n_unresolved_by_end / len(issues)

        yield SprintCase(
            project_key=sprint_row["project_key"],
            sprint_jira_id=sprint_row["jira_id"],
            sprint_end=sprint_end,
            n_issues=len(issues),
            unresolved_fraction=round(unresolved_fraction, 4),
            label_delayed=unresolved_fraction >= SPRINT_DELAY_THRESHOLD,
            as_of=as_of,
            snapshot=ProjectSnapshot(
                project_id=_uuid_for(f"project:{sprint_row['project_id']}:sprint:{sprint_row['id']}"),
                name=f"{sprint_row['project_key']} sprint {sprint_row['jira_id']}",
                members=list(members_seen.values()),
                milestones=[MilestoneSnapshot(
                    id=milestone_id,
                    name=f"{sprint_row['project_key']} sprint {sprint_row['jira_id']}",
                    start_date=sprint_row["start_date"],
                    target_date=sprint_end,
                )] if milestone_id else [],
                tasks=tasks,
                dependencies=deps,
                comments=comments,
                velocity_history=velocity_history(conn, sprint_row) if with_velocity else [],
            ),
        )
