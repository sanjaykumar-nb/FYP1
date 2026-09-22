"""Load-test the Phase 1 stack: many people using it at once, end to end over HTTP.

Imports the real Mesos sprint into the running stack, then runs three scenarios:

- interactive  closed-loop virtual users at rising concurrency, each repeating a session
               mix: the board, dashboard, project, team, sprints, dependencies, a task's
               discussion, and a create-move-delete cycle on a task. No think time, so
               each level measures the most the stack serves and the latency people see.
- analysis     several people pressing Run analysis at the same time, repeatedly
               (backend + AI service, no LLM key).
- sign-in      a burst of people signing in at the same moment (bcrypt is deliberately slow).

Run with the backend (8000) and AI service (8001) up:
    python -m app.scripts.load_test [--api URL] [--label TEXT] [--quick] [--out FILE]
Writes ai-service/eval/phase1_load_test_result.json by default. Exits 1 if any request
failed (a 5xx, a timeout or a wrong status), since under load that is a defect, not noise.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import random
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

from app.scripts.import_real_sprint import DEFAULT_API, PASSWORD, import_sprint

FIXTURE = Path(__file__).parent / "fixtures" / "mesos_sprint_74.json"
OUT = Path(__file__).resolve().parents[3] / "ai-service" / "eval" / "phase1_load_test_result.json"

FULL = {"interactive": [1, 5, 10, 25, 50, 100], "analysis": [1, 2, 5, 10], "sign_in": [1, 10, 25, 50], "seconds": 20}
QUICK = {"interactive": [1, 10, 25, 50], "analysis": [1, 5], "sign_in": [1, 10, 25], "seconds": 8}

# The session mix: how often a person does each thing. Reading dominates, as it does in use.
MIX = {
    "task board": 30, "dashboard": 15, "project": 10, "team": 8, "sprints": 8,
    "dependencies": 8, "task discussion": 8, "create-move-delete a task": 13,
}


def summary(samples: list[float]) -> dict:
    if not samples:
        return {"n": 0}
    ordered = sorted(samples)
    at = lambda q: ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]  # noqa: E731
    return {"n": len(samples), "p50_ms": round(statistics.median(samples), 1), "p95_ms": round(at(0.95), 1),
            "p99_ms": round(at(0.99), 1), "max_ms": round(max(samples), 1)}


class Recorder:
    def __init__(self) -> None:
        self.samples: dict[str, list[float]] = defaultdict(list)
        self.errors: dict[str, int] = defaultdict(int)
        self.error_examples: list[str] = []

    async def call(self, http: httpx.AsyncClient, name: str, method: str, url: str, expect: int = 200, **kw):
        started = time.perf_counter()
        try:
            response = await http.request(method, url, **kw)
            ok = response.status_code == expect
            detail = f"{response.status_code} {response.text[:120]}"
        except httpx.HTTPError as exc:
            response, ok, detail = None, False, f"{type(exc).__name__}"
        self.samples[name].append((time.perf_counter() - started) * 1000)
        if not ok:
            self.errors[name] += 1
            if len(self.error_examples) < 10:
                self.error_examples.append(f"{name}: {method} {url} -> {detail}")
        return response if ok else None


async def interactive_user(http, rec: Recorder, pid: str, task_ids: list[str], stop_at: float, seed: int) -> None:
    rng = random.Random(seed)
    names, weights = list(MIX), list(MIX.values())
    base = f"/projects/{pid}"
    while time.perf_counter() < stop_at:
        action = rng.choices(names, weights)[0]
        if action == "task board":
            await rec.call(http, action, "GET", f"{base}/tasks", params={"page_size": 100})
        elif action == "dashboard":
            await rec.call(http, action, "GET", f"/analytics/projects/{pid}/dashboard")
        elif action == "project":
            await rec.call(http, action, "GET", base)
        elif action == "team":
            await rec.call(http, action, "GET", f"{base}/members", params={"page_size": 100})
        elif action == "sprints":
            await rec.call(http, action, "GET", f"{base}/milestones")
        elif action == "dependencies":
            await rec.call(http, action, "GET", f"{base}/dependencies")
        elif action == "task discussion":
            await rec.call(http, action, "GET", f"{base}/tasks/{rng.choice(task_ids)}/comments")
        else:
            created = await rec.call(http, "create task", "POST", f"{base}/tasks", 201,
                                     json={"title": "Load probe", "status": "planned"})
            if created is not None:
                probe = created.json()["id"]
                await rec.call(http, "move task", "PATCH", f"{base}/tasks/{probe}/move",
                               json={"status": "in_progress", "position": 0})
                await rec.call(http, "delete task", "DELETE", f"{base}/tasks/{probe}", 204)


async def analysis_user(http, rec: Recorder, pid: str, stop_at: float) -> None:
    while time.perf_counter() < stop_at:
        await rec.call(http, "run analysis", "POST", f"/analytics/projects/{pid}/analyze")


def level_result(rec: Recorder, wall_s: float, **head) -> dict:
    everything = [ms for samples in rec.samples.values() for ms in samples]
    errors = sum(rec.errors.values())
    return {**head, "seconds": round(wall_s, 1), "requests": len(everything),
            "throughput_rps": round(len(everything) / wall_s, 1), **summary(everything),
            "errors": errors, "error_rate": round(errors / max(len(everything), 1), 4),
            "by_request": {name: summary(s) for name, s in sorted(rec.samples.items())},
            "error_examples": rec.error_examples}


async def run(args, plan: dict) -> dict:
    project = import_sprint(FIXTURE, args.api)
    pid = project["project_id"]
    limits = httpx.Limits(max_connections=400, max_keepalive_connections=400)
    async with httpx.AsyncClient(base_url=f"{args.api}/api/v1", timeout=120, limits=limits) as http:
        login = await http.post("/auth/login", data={"username": project["email"], "password": PASSWORD})
        login.raise_for_status()
        http.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        board = await http.get(f"/projects/{pid}/tasks", params={"page_size": 100})
        task_ids = [t["id"] for t in board.json()["items"]]
        result = {"interactive": [], "analysis": [], "sign_in_burst": []}

        # Warm up connections, caches and the AI service before anything is timed.
        await asyncio.gather(*(interactive_user(http, Recorder(), pid, task_ids, time.perf_counter() + 2, i)
                               for i in range(5)))
        await analysis_user(http, Recorder(), pid, time.perf_counter() + 1)

        for users in plan["interactive"]:
            rec, started = Recorder(), time.perf_counter()
            stop_at = started + plan["seconds"]
            await asyncio.gather(*(interactive_user(http, rec, pid, task_ids, stop_at, 1000 * users + i)
                                   for i in range(users)))
            result["interactive"].append(level_result(rec, time.perf_counter() - started, users=users))
            r = result["interactive"][-1]
            print(f"  interactive {users:4} users: {r['throughput_rps']:7.1f} req/s   p50 {r['p50_ms']:7.1f}   "
                  f"p95 {r['p95_ms']:7.1f}   p99 {r['p99_ms']:7.1f} ms   errors {r['errors']}", flush=True)

        for users in plan["analysis"]:
            rec, started = Recorder(), time.perf_counter()
            stop_at = started + plan["seconds"]
            await asyncio.gather(*(analysis_user(http, rec, pid, stop_at) for _ in range(users)))
            r = level_result(rec, time.perf_counter() - started, concurrent=users)
            r["analyses_per_minute"] = round(60 * r["requests"] / r["seconds"], 1)
            result["analysis"].append(r)
            print(f"  analysis    {users:4} at once: {r['analyses_per_minute']:6.1f} /min   p50 {r['p50_ms']:7.1f}   "
                  f"p95 {r['p95_ms']:7.1f} ms   errors {r['errors']}", flush=True)

        for users in plan["sign_in"]:
            rec, started = Recorder(), time.perf_counter()
            async with httpx.AsyncClient(base_url=f"{args.api}/api/v1", timeout=120, limits=limits) as fresh:
                await asyncio.gather(*(rec.call(fresh, "sign in", "POST", "/auth/login",
                                                data={"username": project["email"], "password": PASSWORD})
                                       for _ in range(users)))
            r = level_result(rec, time.perf_counter() - started, simultaneous=users)
            result["sign_in_burst"].append(r)
            print(f"  sign-in     {users:4} at once: all done in {1000 * r['seconds']:7.0f} ms   p50 {r['p50_ms']:7.1f}   "
                  f"max {r['max_ms']:7.1f} ms   errors {r['errors']}", flush=True)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default=DEFAULT_API)
    ap.add_argument("--label", default="SQLite, one uvicorn worker per service, load generator on the same machine")
    ap.add_argument("--quick", action="store_true", help="fewer, shorter levels (CI)")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")

    plan = QUICK if args.quick else FULL
    result = asyncio.run(run(args, plan))
    failed = sum(level["errors"] for scenario in result.values() for level in scenario)
    report = {
        "method": __doc__.strip().splitlines()[0],
        "environment": {"api": args.api, "setup": args.label, "machine": platform.platform(),
                        "processor": platform.processor(), "cpus": os.cpu_count(),
                        "python": platform.python_version(),
                        "project": "Apache Mesos sprint 74 (30 tasks, 13 people)",
                        "seconds_per_level": plan["seconds"], "session_mix_weights": MIX},
        **result,
        "failed_requests": failed,
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nwrote {args.out}  ({failed} failed requests)")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
