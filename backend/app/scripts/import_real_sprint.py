"""Replay a real, historical sprint into a running TeamSync instance.

Everything goes through the public REST API — registration, adding teammates,
creating tasks as their real reporters, posting comments as their real authors,
and triggering analysis — so the result exercises exactly the code path a real
team would, not a database shortcut.

Source data: a TAWOS sprint fixture (see ai-service/eval/datasets/
extract_sprint_fixture.py) — real Jira issues, titles, story points, assignees,
blocking links, and comments from an open-source project.

How the history is replayed faithfully:
  * State is reconstructed AS OF SPRINT END. An issue counts as done only if it
    was resolved by then, and only comments written by then are posted. Using
    today's status would leak outcomes the team could not have known.
  * All timestamps are shifted by one constant so the sprint ends yesterday.
    Every real interval is preserved; the analysis simply sees the sprint the
    day after it closed — the same "now = sprint end + 1 day" used offline.
  * Jira sprints have no per-issue due date (neither does TAWOS), so every task
    is due at sprint end, matching the offline evaluation.
  * TAWOS anonymises people, so contributors appear as "Mesos contributor #id".
  * Jira has no notion of a sprint team, so project members are the people who
    were assigned sprint work; reporters and commenters are organization users.
  * Epics carry roll-up points from their children, so they import without
    points rather than counting as their assignee's personal load.
  * Only "Blocker" links are imported as dependencies: Jira's outward "blocks"
    has an unambiguous direction; other link types do not mean "blocks".

Mid-sprint replay (--at 0.5): the same reconstruction, but as the sprint stood
that far through. Only issues created by then are imported, done means resolved
by then, and the replayed moment is placed at *now*, so the deadline is still
ahead and the pace warning, not the overdue signal, is what can fire.

Run with the backend (and AI service) up:
    cd backend
    python -m app.scripts.import_real_sprint app/scripts/fixtures/mesos_sprint_74.json
    python -m app.scripts.import_real_sprint app/scripts/fixtures/mesos_sprint_74.json --at 0.5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

PASSWORD = "realsprint-2018"
PRIORITY = {"Blocker": "critical", "Critical": "critical", "Major": "high", "Minor": "medium", "Trivial": "low"}
# Current Jira status of an issue that was still open at sprint end, mapped to
# where it most plausibly stood then: never-started stays planned.
OPEN_STATUS = {"Open": "planned", "Accepted": "planned", "Reviewable": "review", "In Progress": "in_progress"}


def parse(ts: str | None) -> datetime | None:
    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) if ts else None


def check(response: httpx.Response) -> dict:
    if response.is_error:
        sys.exit(f"{response.request.method} {response.request.url} -> {response.status_code}: {response.text}")
    return response.json() if response.content else {}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("fixture", type=Path)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--at", type=float, default=None, metavar="FRACTION",
                    help="replay the sprint as it stood this far through (e.g. 0.5) instead of at its end")
    args = ap.parse_args()
    if args.at is not None and not 0 < args.at < 1:
        sys.exit("--at must be between 0 and 1")

    fx = json.loads(args.fixture.read_text(encoding="utf-8"))
    sprint_start, sprint_end = parse(fx["sprint"]["start"]), parse(fx["sprint"]["end"])
    now = datetime.now(timezone.utc)
    if args.at is None:
        # The replayed moment is sprint end, placed at yesterday.
        cutoff, moment = sprint_end, "sprint end"
        shift = (now - timedelta(days=1)) - sprint_end
    else:
        # The replayed moment is part-way through, placed at now: the deadline is still ahead.
        cutoff, moment = sprint_start + (sprint_end - sprint_start) * args.at, f"{args.at:.0%} through the sprint"
        shift = now - cutoff

    def replayed(ts: datetime) -> str:
        return (ts + shift).isoformat()

    # Only what existed by the replayed moment: issues created by then, comments written by then.
    issues = [i for i in fx["issues"] if not i.get("created") or parse(i["created"]) <= cutoff]
    comments = [c for c in fx["comments"] if c["created"] and parse(c["created"]) <= cutoff]
    people = sorted(
        {p for i in issues for p in (i["assignee"], i["reporter"]) if p}
        | {c["author"] for c in comments if c["author"]}
    )
    tag = time.strftime("%m%d%H%M%S")  # keeps emails unique across repeated imports
    project_key = fx["project"]["key"]

    with httpx.Client(base_url=f"{args.api}/api/v1", timeout=180) as http:
        tokens: dict[str, str] = {}

        def auth(email: str) -> dict:
            if email not in tokens:
                login = check(http.post("/auth/login", data={"username": email, "password": PASSWORD}))
                tokens[email] = login["access_token"]
            return {"Authorization": f"Bearer {tokens[email]}"}

        pm_email = f"pm-{tag}@example.com"
        registered = check(http.post("/auth/register", json={
            "email": pm_email, "password": PASSWORD, "full_name": "Sprint PM",
            "organization_name": f"{fx['project']['name']} (real sprint replay)",
        }))
        tokens[pm_email] = registered["access_token"]
        me = check(http.get("/auth/me", headers=auth(pm_email)))
        org_id = me["organization_id"]

        project = check(http.post("/projects", headers=auth(pm_email), json={
            "name": f"{fx['project']['name']} — {fx['sprint']['name']}",
            "key": project_key[:10],
            "description": f"Real sprint replayed from TAWOS. {fx['citation']}",
            "start_date": replayed(sprint_start),
            "target_end_date": replayed(sprint_end),
        }))
        pid = project["id"]
        # Creating a project makes its creator a member. The importer's account
        # is scaffolding, not part of the historical team; left in, it would be
        # analysed as a teammate with no work.
        check(http.delete(f"/projects/{pid}/members/{me['id']}", headers=auth(pm_email)))
        milestone = check(http.post(f"/projects/{pid}/milestones", headers=auth(pm_email), json={
            "name": fx["sprint"]["name"], "start_date": replayed(sprint_start), "target_date": replayed(sprint_end),
        }))

        # Jira records no sprint team, so the delivery team is the people who
        # owned sprint work. Reporters and commenters still get accounts (their
        # comments are posted on the real tasks) but are not project members.
        assignees = {i["assignee"] for i in issues if i["assignee"]}
        emails: dict[int, str] = {}
        user_ids: dict[int, str] = {}
        for person in people:
            email = f"{project_key.lower()}-{tag}-u{person}@example.com"
            user = check(http.post(f"/organizations/{org_id}/members", headers=auth(pm_email), json={
                "email": email, "full_name": f"{fx['project']['name']} contributor #{person}",
                "password": PASSWORD, "role": "developer",
            }))
            if person in assignees:
                check(http.post(f"/projects/{pid}/members", headers=auth(pm_email),
                                json={"user_id": user["id"], "role": "developer"}))
            emails[person], user_ids[person] = email, user["id"]
        print(f"team: {len(assignees)} assignees on the project; "
              f"{len(people) - len(assignees)} reporters/commenters as organization users")

        task_ids: dict[int, str] = {}
        done = 0
        for issue in issues:
            resolved = parse(issue["resolved"])
            status = "done" if resolved and resolved <= cutoff else OPEN_STATUS.get(issue["status"], "in_progress")
            done += status == "done"
            reporter = emails.get(issue["reporter"], pm_email)
            description = (issue.get("description") or "").strip()
            # An epic's points roll up its child issues' estimates; they are not
            # work its assignee does personally, so counting them would inflate
            # that one person's load.
            points = None if issue["type"] == "Epic" else issue["story_points"]
            task = check(http.post(f"/projects/{pid}/tasks", headers=auth(reporter), json={
                "title": f"{issue['key']}: {issue.get('title') or issue['type']}"[:500],
                "description": f"{description}\n\n[{issue['type']} · imported from {issue['key']}]".strip(),
                "status": status,
                "priority": PRIORITY.get(issue["priority"], "medium"),
                "story_points": round(points) if points is not None else None,
                "due_date": replayed(sprint_end),
                "assignee_id": user_ids.get(issue["assignee"]),
                "milestone_id": milestone["id"],
            }))
            task_ids[issue["tawos_id"]] = task["id"]
        print(f"tasks: {len(issues)} ({done} resolved by {moment}, {len(issues) - done} still open)")

        deps = 0
        for link in fx["links"]:
            if link["from"] not in task_ids or link["to"] not in task_ids:
                continue  # one end was not created yet at the replayed moment
            if link["type"] == "Blocker" and link["direction"] == "OUTBOUND":
                blocker, blocked = task_ids[link["from"]], task_ids[link["to"]]
                check(http.post(f"/projects/{pid}/tasks/{blocked}/dependencies", headers=auth(pm_email),
                                json={"blocking_task_id": blocker, "dependency_type": "blocks"}))
                deps += 1
        print(f"dependencies: {deps} real blocking links")

        for c in comments:
            author = emails.get(c["author"])
            if not author or c["issue"] not in task_ids:
                continue
            check(http.post(f"/projects/{pid}/tasks/{task_ids[c['issue']]}/comments", headers=auth(author),
                            json={"content": (c["text"] or "").strip() or "(comment had no plain text)"}))
        print(f"comments: {len(comments)} written by {moment} ({len(fx['comments']) - len(comments)} later ones excluded)")

        run = check(http.post(f"/analytics/projects/{pid}/analyze", headers=auth(pm_email)))
        out = run.get("coordinator_output") or {}
        print(f"\nanalysis {run['status']}: overall risk {out.get('overall_risk_level')}")
        print(out.get("overall_summary", ""))
        risk = (out.get("specialist_outputs") or {}).get("risk", {})
        print("risk scores:", json.dumps(risk.get("risk_scores")))
        for rec in out.get("merged_recommendations") or []:
            print(f"  [{rec['priority']}] {rec['title']} — {rec['description']}")

    print(f"\nSign in at http://localhost:3000 as {pm_email} / {PASSWORD}")


if __name__ == "__main__":
    main()
