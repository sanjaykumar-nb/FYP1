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
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from app.graph.snapshot import (
    CommentSnapshot,
    DependencySnapshot,
    MemberSnapshot,
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


def _uuid_for(label: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, label)


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
        SELECT s.id, s.jira_id, s.project_id, s.end_date, s.complete_date, p.project_key,
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


def build_sprint_cases(conn: sqlite3.Connection, limit: Optional[int] = None) -> Iterator[SprintCase]:
    sprints = _eligible_sprints(conn)
    if limit:
        sprints = sprints[:limit]

    for sprint_row in sprints:
        sprint_end = sprint_row["end_date"] or sprint_row["complete_date"]

        issues = conn.execute("SELECT * FROM issue WHERE sprint_id = ?", (sprint_row["id"],)).fetchall()
        issue_ids = {row["id"] for row in issues}

        members_seen: dict[int, MemberSnapshot] = {}
        tasks: list[TaskSnapshot] = []
        n_unresolved_by_end = 0

        for row in issues:
            # Reconstruct state AS OF sprint_end — not as of today's dump.
            resolved_by_end = bool(row["resolution_date"]) and row["resolution_date"] <= sprint_end
            if not resolved_by_end:
                n_unresolved_by_end += 1

            assignee_id, reporter_id = row["assignee_id"], row["reporter_id"]
            for uid in (assignee_id, reporter_id):
                if uid is not None and uid not in members_seen:
                    members_seen[uid] = MemberSnapshot(id=_uuid_for(f"user:{uid}"), full_name=f"user{uid}")

            tasks.append(TaskSnapshot(
                id=_uuid_for(f"issue:{row['id']}"),
                title=row["issue_key"] or f"issue-{row['id']}",
                status="done" if resolved_by_end else _map_status(row["status"]),
                priority=_map_priority(row["priority"]),
                story_points=int(row["story_point"]) if row["story_point"] else None,
                assignee_id=_uuid_for(f"user:{assignee_id}") if assignee_id else None,
                reporter_id=_uuid_for(f"user:{reporter_id}") if reporter_id else None,
                due_date=sprint_end,  # the sprint's own boundary is the implicit deadline
                created_at=row["creation_date"],
                completed_at=row["resolution_date"] if resolved_by_end else None,
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
                # Comments made after sprint_end didn't exist yet at that point.
                if c["author_id"] is None or not c["creation_date"] or c["creation_date"] > sprint_end:
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
            snapshot=ProjectSnapshot(
                project_id=_uuid_for(f"project:{sprint_row['project_id']}:sprint:{sprint_row['id']}"),
                name=f"{sprint_row['project_key']} sprint {sprint_row['jira_id']}",
                members=list(members_seen.values()),
                milestones=[],
                tasks=tasks,
                dependencies=deps,
                comments=comments,
            ),
        )
