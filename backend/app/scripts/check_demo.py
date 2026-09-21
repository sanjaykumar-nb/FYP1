"""Check that the demo still shows what docs/DEMO_SCRIPT.md says it shows.

Replays the real Mesos sprint through the running backend and AI service twice —
at sprint end and halfway through — and walks the video's claims: the verdicts,
the evidence behind them, the suggested moves and their predicted effect, the
effect once applied, and the halfway warning. Prints every claim with what was
seen, and exits non-zero if any of them no longer holds, so a demo that has
drifted fails in CI instead of on camera.

Run with the backend (8000) and AI service (8001) up:
    python -m app.scripts.check_demo [--api http://localhost:8000]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import httpx

from app.scripts.import_real_sprint import DEFAULT_API, PASSWORD, import_sprint

FIXTURE = Path(__file__).parent / "fixtures" / "mesos_sprint_74.json"

FULL_SCORES = {"delay": "critical", "workload": "high", "dependency": "low",
               "knowledge": "low", "coordination": "low", "silent_member": "low"}
# (task key, from, to) — stable across imports since the planner breaks ties by name.
EXPECTED_MOVES = [
    ("MESOS-8383", "Apache Mesos contributor #3409", "Apache Mesos contributor #3415"),
    ("MESOS-8524", "Apache Mesos contributor #3391", "Apache Mesos contributor #3361"),
    ("MESOS-8492", "Apache Mesos contributor #3409", "Apache Mesos contributor #3569"),
]
# Milestone dates are whole days, so how far through the schedule the halfway replay
# reads depends on the hour it is imported: 50% at 00:00 UTC, 57% just before midnight.
PACE = re.compile(r"is (\d+)% through its schedule with (\d+)% of its work done; "
                  r"at this pace (\d+)% will still be open at the deadline")


class Claims:
    def __init__(self) -> None:
        self.failed: list[str] = []

    def expect(self, claim: str, holds: bool, seen: object = "") -> None:
        print(f"  {'ok  ' if holds else 'FAIL'}  {claim}" + (f"  [{seen}]" if seen != "" else ""))
        if not holds:
            self.failed.append(claim)


def outputs(run: dict) -> tuple[dict, list[dict], list[dict]]:
    out = run.get("coordinator_output") or {}
    risk = (out.get("specialist_outputs") or {}).get("risk") or {}
    findings = (risk.get("metadata") or {}).get("findings") or []
    return risk, findings, out.get("merged_recommendations") or []


def raw(node_id: str) -> str:
    return node_id.split(":", 1)[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default=DEFAULT_API)
    api = ap.parse_args().api
    # The findings quote arrows and dashes a Windows console code page cannot encode.
    sys.stdout.reconfigure(errors="replace")
    claims = Claims()

    print("\n== The sprint at its end (shots 0:00 – 3:00) ==")
    full = import_sprint(FIXTURE, api)
    run = full["run"]
    risk, findings, recs = outputs(run)
    titles = [f["title"] for f in findings]

    with httpx.Client(base_url=f"{api}/api/v1", timeout=180) as http:
        token = http.post("/auth/login", data={"username": full["email"], "password": PASSWORD}).json()
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        pid = full["project_id"]
        tasks = http.get(f"/projects/{pid}/tasks", params={"page_size": 100}, headers=headers).json()["items"]
        members = http.get(f"/projects/{pid}/members", params={"page_size": 100}, headers=headers).json()["items"]
        key_of = {t["id"]: t["title"].split(":", 1)[0] for t in tasks}
        name_of = {m["id"]: m["full_name"] for m in members}

        claims.expect("analysis completes", run["status"] == "completed", run["status"])
        claims.expect("overall risk is critical", run["coordinator_output"]["overall_risk_level"] == "critical",
                      run["coordinator_output"]["overall_risk_level"])
        claims.expect("delay critical, workload high, the other four low", risk.get("risk_scores") == FULL_SCORES,
                      risk.get("risk_scores"))
        stats = (risk.get("metadata") or {}).get("graph_stats") or {}
        claims.expect("graph of 45 nodes and 117 links", (stats.get("nodes"), stats.get("edges")) == (45, 117),
                      f"{stats.get('nodes')} nodes, {stats.get('edges')} links")
        claims.expect("finding: 20 of 20 open tasks past due",
                      "20 of 20 open tasks are past their due date" in titles)
        claims.expect("finding: #3409 carries 9 open points vs a team mean of 3.8",
                      "'Apache Mesos contributor #3409' carries 9 open points vs a team mean of 3.8" in titles)
        path = next((f for f in findings if f.get("metric") == "critical_path_share"), None)
        cited = [key_of.get(raw(n)) for n in (path or {}).get("node_ids", [])]
        claims.expect("critical path cites MESOS-5904 then MESOS-5814", cited == ["MESOS-5904", "MESOS-5814"], cited)

        rebalance = next((r for r in recs if r["title"] == "Redistribute workload"), None)
        actions = [a for a in (rebalance or {}).get("actions") or [] if a["kind"] == "reassign"]
        moves = [(key_of.get(raw(a["task_id"])), name_of.get(raw(a["from_person"])), name_of.get(raw(a["to_person"])))
                 for a in actions]
        claims.expect("three suggested moves, the ones DEMO.md lists", moves == EXPECTED_MOVES, moves)
        effect = (rebalance or {}).get("expected_effect") or ""
        claims.expect("predicted: heaviest load 9 -> 6, high -> medium",
                      "from 9 to 6 points" in effect and "high → medium" in effect, effect)

        for a in actions:
            http.patch(f"/projects/{pid}/tasks/{raw(a['task_id'])}", headers=headers,
                       json={"assignee_id": raw(a["to_person"])}).raise_for_status()
        rerun = http.post(f"/analytics/projects/{pid}/analyze", headers=headers).json()
        risk2, findings2, _ = outputs(rerun)
        claims.expect("after applying them: workload is medium", (risk2.get("risk_scores") or {}).get("workload") == "medium",
                      (risk2.get("risk_scores") or {}).get("workload"))
        claims.expect("after applying them: #3481 is heaviest at 6 points",
                      "'Apache Mesos contributor #3481' carries 6 open points vs a team mean of 3.8"
                      in [f["title"] for f in findings2])

    print("\n== The same sprint, halfway through (shot 3:00 – 4:00) ==")
    half = import_sprint(FIXTURE, api, at=0.5)
    risk, findings, recs = outputs(half["run"])
    claims.expect("delay is critical before anything is overdue",
                  (risk.get("risk_scores") or {}).get("delay") == "critical"
                  and not any(f.get("metric") == "overdue_ratio" for f in findings),
                  (risk.get("risk_scores") or {}).get("delay"))
    replan = next((r for r in recs if r["title"] == "Re-plan before the deadline"), None)
    pace = PACE.search((replan or {}).get("description") or "")
    through, done, still_open = (int(g) for g in pace.groups()) if pace else (None, None, None)
    claims.expect("recommends re-planning, 50-57% through with 18% done",
                  pace is not None and 50 <= through <= 57 and done == 18, f"{through}% through, {done}% done")
    claims.expect("projects 63-68% still open (the real sprint ended with 67%)",
                  pace is not None and 63 <= still_open <= 68, f"{still_open}%")

    print()
    if claims.failed:
        print(f"{len(claims.failed)} demo claim(s) no longer hold. Update docs/DEMO_SCRIPT.md and DEMO.md, "
              "or fix what changed.")
        sys.exit(1)
    print("Every claim the demo script makes still holds.")


if __name__ == "__main__":
    main()
