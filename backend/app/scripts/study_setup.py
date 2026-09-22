"""Set up the Phase 1 user study (docs/user-study/PROTOCOL.md) and write its answer key.

Imports two real sprints from different projects, each as it stood halfway through,
each twice: once analysed (the "evidence" condition, the analysis panel is filled)
and once not (the "baseline" condition, only the board, sprints, team and dashboard
charts). Every project's organization gets a read-only viewer account for the
participant, who can then look at everything and change nothing, nor run an analysis.

The answer key is computed from the board itself (tasks, points, assignees, blocking
links), not from the analysis, so a wrong analysis would show up as wrong answers in
the evidence condition rather than hiding in the key. What the analysis said is listed
beside it for the facilitator.

Run it on the day of the sessions (the sprints are replayed at "now"), with the
backend and AI service up and no LLM key:
    python -m app.scripts.study_setup [--api URL] [--key PATH]
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

from app.scripts.import_real_sprint import DEFAULT_API, PASSWORD, import_sprint

FIXTURES = Path(__file__).parent / "fixtures"
SPRINTS = {
    "A": ("Apache Mesos, sprint 74", FIXTURES / "mesos_sprint_74.json"),
    "B": ("LSST Data Management, sprint 305", FIXTURES / "dm_sprint_305.json"),
}
HALFWAY = 0.5
VIEWER_PASSWORD = "study-session-2026"
KEY = Path(__file__).resolve().parents[3] / "docs" / "user-study" / "ANSWER_KEY.md"


def check(response: httpx.Response) -> dict | list:
    if response.status_code >= 400:
        sys.exit(f"{response.request.method} {response.request.url} -> {response.status_code} {response.text[:300]}")
    return response.json() if response.content else {}


def add_viewer(http: httpx.Client, pm_email: str, pid: str, label: str) -> str:
    """A read-only account in the project's organization, for the participant."""
    pm = {"Authorization": "Bearer " + check(http.post("/auth/login", data={"username": pm_email,
                                                                              "password": PASSWORD}))["access_token"]}
    org_id = check(http.get("/auth/me", headers=pm))["organization_id"]
    email = f"participant-{label.lower()}-{time.strftime('%m%d%H%M%S')}@example.com"
    check(http.post(f"/organizations/{org_id}/members", headers=pm, json={
        "email": email, "password": VIEWER_PASSWORD, "full_name": "Study participant", "role": "viewer"}))
    viewer = {"Authorization": "Bearer " + check(http.post("/auth/login", data={"username": email,
                                                                                  "password": VIEWER_PASSWORD}))["access_token"]}
    check(http.get(f"/projects/{pid}", headers=viewer))  # the participant can open it...
    blocked = http.post(f"/analytics/projects/{pid}/analyze", headers=viewer)
    if blocked.status_code != 403:  # ...and cannot run an analysis
        sys.exit(f"viewer could run an analysis on {label}: {blocked.status_code}")
    return email


def board_facts(http: httpx.Client, pm_email: str, pid: str) -> dict:
    """Everything the answer key needs, read from the board as a participant would see it."""
    pm = {"Authorization": "Bearer " + check(http.post("/auth/login", data={"username": pm_email,
                                                                              "password": PASSWORD}))["access_token"]}
    tasks = check(http.get(f"/projects/{pid}/tasks", headers=pm, params={"page_size": 100}))["items"]
    members = check(http.get(f"/projects/{pid}/members", headers=pm, params={"page_size": 100}))
    members = members["items"] if isinstance(members, dict) else members
    deps = check(http.get(f"/projects/{pid}/dependencies", headers=pm))
    deps = deps["items"] if isinstance(deps, dict) else deps
    name = {m["id"]: m.get("full_name") or m["email"] for m in members}
    by_id = {t["id"]: t for t in tasks}
    key = lambda t: t["title"].split(":", 1)[0]  # noqa: E731  "DM-7801: ..." -> "DM-7801"
    is_open = lambda t: t["status"] != "done"  # noqa: E731

    # Two fair readings of "open work": the points shown on the board, and the analysis's
    # rule that every unfinished task counts at least 1 (unestimated work is still work).
    open_points: dict[str, int] = defaultdict(int)
    open_counted: dict[str, int] = defaultdict(int)
    open_tasks: dict[str, list] = defaultdict(list)
    for t in tasks:
        if is_open(t) and t.get("assignee_id"):
            open_points[t["assignee_id"]] += t.get("story_points") or 0
            open_counted[t["assignee_id"]] += max(t.get("story_points") or 0, 1)
            open_tasks[t["assignee_id"]].append(t)
    loads = sorted(open_points.items(), key=lambda kv: (-kv[1], name.get(kv[0], kv[0])))
    peak_id, peak = loads[0] if loads else (None, 0)
    rule_id = max(open_counted, key=lambda u: (open_counted[u], name.get(u, u)), default=None)
    accepted = [peak_id] + ([rule_id] if rule_id not in (None, peak_id) else [])
    blocking: dict[str, list[str]] = defaultdict(list)
    for d in deps:
        blocker, blocked = by_id.get(d["blocking_task_id"]), by_id.get(d["blocked_task_id"])
        if blocker and blocked and is_open(blocker) and is_open(blocked):
            blocking[key(blocker)].append(key(blocked))
    done = [t for t in tasks if not is_open(t)]
    points = sum(t.get("story_points") or 0 for t in tasks)
    return {
        "tasks": len(tasks), "done": len(done),
        "done_share_tasks": round(100 * len(done) / max(len(tasks), 1)),
        "done_share_points": round(100 * sum(t.get("story_points") or 0 for t in done) / max(points, 1)),
        "loads": [(name.get(uid, uid), pts, open_counted[uid]) for uid, pts in loads],
        "accepted": [(name.get(u, u), open_points[u], open_counted[u]) for u in accepted],
        "open_tasks": {name.get(u, u): [(key(t), t.get("story_points"), t["title"].split(":", 1)[-1].strip().strip('"'))
                                        for t in sorted(open_tasks[u], key=lambda t: -(t.get("story_points") or 0))]
                       for u in accepted},
        "blocking": sorted(blocking.items(), key=lambda kv: (-len(kv[1]), kv[0])),
        "key_of": {t["id"]: key(t) for t in tasks}, "name_of": name,
    }


def analysis_view(run: dict, facts: dict) -> dict:
    out = run.get("coordinator_output") or {}
    risk = (out.get("specialist_outputs") or {}).get("risk") or {}
    findings = (risk.get("metadata") or {}).get("findings") or []
    raw = lambda n: n.split(":", 1)[1]  # noqa: E731
    moves = []
    for rec in out.get("merged_recommendations") or []:
        for a in rec.get("actions") or []:
            if a.get("kind") == "reassign":
                moves.append((facts["key_of"].get(raw(a["task_id"]), "?"), facts["name_of"].get(raw(a["from_person"]), "?"),
                              facts["name_of"].get(raw(a["to_person"]), "?")))
    return {"scores": risk.get("risk_scores") or {}, "findings": [f.get("title") for f in findings], "moves": moves}


def write_key(path: Path, sessions: dict) -> None:
    lines = [
        "# User study answer key (facilitator only)",
        "",
        f"Generated by `python -m app.scripts.study_setup` on {time.strftime('%Y-%m-%d %H:%M')}. "
        "Regenerate it whenever the sprints are re-imported. Do not show this to participants.",
        "",
        "Scoring rules are in PROTOCOL.md, section 6. The truth below is read from the board, not the analysis.",
    ]
    for label, s in sessions.items():
        f, a = s["facts"], s["analysis"]
        lines += [
            "", f"## Sprint {label}: {s['title']}", "",
            f"Projects: evidence `{s['evidence_pid']}`, baseline `{s['baseline_pid']}`. "
            f"Participant sign-in: evidence `{s['evidence_viewer']}`, baseline `{s['baseline_viewer']}`, "
            f"password `{VIEWER_PASSWORD}`.", "",
            "**T1, on track?** Correct answer: *no*, with a done share of "
            f"{f['done_share_tasks']}% of tasks ({f['done']} of {f['tasks']}) or {f['done_share_points']}% of points, "
            "accepted within ±10 points, while the sprint is about half over.", "",
            "**T2, most open work:** "
            + (f"**{f['accepted'][0][0]}** with **{f['accepted'][0][1]}** open points (accept ±1)."
               if len(f["accepted"]) == 1 else
               "accept either reading (±1): **{}** with **{}** points shown on the board, or **{}** with **{}** "
               "if each unestimated open task counts as 1 point, as the analysis counts it."
               .format(f["accepted"][0][0], f["accepted"][0][1], f["accepted"][1][0], f["accepted"][1][2]))
            + " Everyone with open work:", "",
            "| Person | Open points on the board | Counting each unestimated task as 1 |", "|---|---|---|",
            *[f"| {n} | {p} | {c} |" for n, p, c in f["loads"]], "",
            "**T3, one move to relieve the person named in T2:** correct if the task is one of theirs below and "
            "the receiver then carries less than that person does now (by the same reading).", "",
            *[line for person, rows in f["open_tasks"].items() for line in (
                f"{person}'s open tasks:", "", "| Task | Points | Title |", "|---|---|---|",
                *[f"| {k} | {p if p is not None else 'none'} | {t[:70]} |" for k, p, t in rows], "")],
            "**T4, open work held up by another open task:** "
            + ("; ".join(f"**{b}** blocks {', '.join(v)}" for b, v in f["blocking"]) if f["blocking"]
               else "none on this board at the halfway point, so T4 is not scored for this sprint") + ".", "",
            "What the analysis said (evidence condition only):", "",
            f"- Risk levels: {', '.join(f'{k} {v}' for k, v in a['scores'].items())}",
            *[f"- Finding: {t}" for t in a["findings"]],
            *[f"- Suggested move: {k} from {src} to {dst}" for k, src, dst in a["moves"]],
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default=DEFAULT_API)
    ap.add_argument("--key", type=Path, default=KEY)
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")

    sessions = {}
    with httpx.Client(base_url=f"{args.api}/api/v1", timeout=180) as http:
        for label, (title, fixture) in SPRINTS.items():
            print(f"\n== Sprint {label}: {title} ==")
            evidence = import_sprint(fixture, args.api, HALFWAY)
            baseline = import_sprint(fixture, args.api, HALFWAY, analyze=False)
            facts = board_facts(http, evidence["email"], evidence["project_id"])
            sessions[label] = {
                "title": title, "facts": facts, "analysis": analysis_view(evidence["run"], facts),
                "evidence_pid": evidence["project_id"], "baseline_pid": baseline["project_id"],
                "evidence_viewer": add_viewer(http, evidence["email"], evidence["project_id"], f"{label}-evidence"),
                "baseline_viewer": add_viewer(http, baseline["email"], baseline["project_id"], f"{label}-baseline"),
            }
    write_key(args.key, sessions)
    print(f"\nwrote {args.key}")
    for label, s in sessions.items():
        print(f"  sprint {label}: evidence {s['evidence_viewer']}   baseline {s['baseline_viewer']}   "
              f"password {VIEWER_PASSWORD}")


if __name__ == "__main__":
    main()
