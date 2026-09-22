"""Measure how fast the main Phase 1 features respond, end to end over HTTP.

Imports the real Mesos sprint into the running stack, then times each feature's
request: sign-in, the workspace, the board, a task's discussion, dependencies,
sprints, team, the dashboard, a create-edit-move-delete cycle on a task, the
analysis history, and a full analysis (backend + AI service, no LLM key).
Each is warmed up twice, then timed; reports p50 / p95 / max in milliseconds.

Run with the backend (8000) and AI service (8001) up:
    python -m app.scripts.measure_latency [--api URL] [--runs 30]
Writes ai-service/eval/phase1_api_latency_result.json.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

import httpx

from app.scripts.import_real_sprint import DEFAULT_API, PASSWORD, import_sprint

FIXTURE = Path(__file__).parent / "fixtures" / "mesos_sprint_74.json"
OUT = Path(__file__).resolve().parents[3] / "ai-service" / "eval" / "phase1_api_latency_result.json"
ANALYSIS_RUNS = 10


def summary(samples: list[float]) -> dict:
    ordered = sorted(samples)
    at = lambda q: ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]  # noqa: E731
    return {"n": len(samples), "p50_ms": round(statistics.median(samples), 1),
            "p95_ms": round(at(0.95), 1), "max_ms": round(max(samples), 1)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default=DEFAULT_API)
    ap.add_argument("--runs", type=int, default=30)
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")

    project = import_sprint(FIXTURE, args.api)
    pid = project["project_id"]
    timings: dict[str, list[float]] = {}

    with httpx.Client(base_url=f"{args.api}/api/v1", timeout=180) as http:
        def timed(name: str, method: str, url: str, runs: int, expect: int = 200, **kwargs):
            response = None
            for i in range(runs + 2):
                started = time.perf_counter()
                response = http.request(method, url, **kwargs)
                elapsed = (time.perf_counter() - started) * 1000
                if response.status_code != expect:
                    sys.exit(f"{name}: {method} {url} -> {response.status_code} {response.text[:200]}")
                if i >= 2:  # the first two warm up connections and caches
                    timings.setdefault(name, []).append(elapsed)
            return response

        login = timed("sign in", "POST", "/auth/login", args.runs,
                      data={"username": project["email"], "password": PASSWORD})
        http.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

        timed("workspace (project list)", "GET", "/projects", args.runs)
        timed("project", "GET", f"/projects/{pid}", args.runs)
        board = timed("task board (30 tasks)", "GET", f"/projects/{pid}/tasks", args.runs, params={"page_size": 100})
        timed("dependencies", "GET", f"/projects/{pid}/dependencies", args.runs)
        timed("sprints", "GET", f"/projects/{pid}/milestones", args.runs)
        timed("team", "GET", f"/projects/{pid}/members", args.runs, params={"page_size": 100})
        timed("dashboard", "GET", f"/analytics/projects/{pid}/dashboard", args.runs)
        task_id = board.json()["items"][0]["id"]
        timed("task discussion", "GET", f"/projects/{pid}/tasks/{task_id}/comments", args.runs)

        # Write path: create, edit, move and delete a task, each timed.
        for _ in range(args.runs + 2):
            for name, method, suffix, body, expect in (
                ("create task", "POST", "", {"title": "Latency probe", "status": "planned"}, 201),
            ):
                started = time.perf_counter()
                created = http.post(f"/projects/{pid}/tasks", json=body)
                timings.setdefault(name, []).append((time.perf_counter() - started) * 1000)
                if created.status_code != expect:
                    sys.exit(f"create task -> {created.status_code} {created.text[:200]}")
            probe = created.json()["id"]
            for name, method, suffix, body, expect in (
                ("edit task", "PATCH", "", {"priority": "high"}, 200),
                ("move task", "PATCH", "/move", {"status": "in_progress", "position": 0}, 200),
                ("delete task", "DELETE", "", None, 204),
            ):
                started = time.perf_counter()
                response = http.request(method, f"/projects/{pid}/tasks/{probe}{suffix}", json=body)
                timings.setdefault(name, []).append((time.perf_counter() - started) * 1000)
                if response.status_code != expect:
                    sys.exit(f"{name} -> {response.status_code} {response.text[:200]}")
        for name in ("create task", "edit task", "move task", "delete task"):
            timings[name] = timings[name][2:]  # drop the warm-up rounds

        timed("run analysis (backend + AI service)", "POST", f"/analytics/projects/{pid}/analyze", ANALYSIS_RUNS)
        timed("analysis history", "GET", f"/analytics/projects/{pid}/agent-runs", args.runs)

    result = {
        "method": __doc__.strip().splitlines()[0],
        "environment": {"api": args.api, "machine": platform.platform(), "python": platform.python_version(),
                        "project": "Apache Mesos sprint 74 (30 tasks, 13 people)"},
        "endpoints": {name: summary(samples) for name, samples in timings.items()},
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    width = max(len(n) for n in timings)
    for name, s in result["endpoints"].items():
        print(f"  {name:{width}}  p50 {s['p50_ms']:7.1f} ms   p95 {s['p95_ms']:7.1f} ms   (n={s['n']})")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
