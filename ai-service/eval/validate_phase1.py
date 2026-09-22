"""Validate every Phase 1 agent through the deployed analysis endpoint, on real sprints.

Each of the 987 eligible TAWOS sprints is sent to POST /api/v1/analyze — the same
endpoint and scope the backend calls when a user clicks Run Analysis — twice: as it
stood at sprint end, and as it stood halfway through. The endpoint runs in-process
(ASGI), with no LLM key, which is how the product ships.

What is checked, per agent:

- Coordinator      completes, returns every specialist, valid schema, same answer twice
- Planning /
  Progress /
  Workload         each figure it reports equals an independent recount from the raw sprint
- Risk             scores equal a direct GraphMetrics computation; every citation is a real
                   graph node; delay predictions scored against what the sprint really did
- Recommendation   covers every medium-or-worse risk; each suggested reassignment is applied
                   to the sprint and its predicted effect checked against the recomputed one
- LLM layer        no call ever reaches the network without a key

Historical sprints are shifted in time so that the moment evaluated is "now": the
live pipeline, correctly for live projects, judges risk against the wall clock.
The shift reproduces the evaluation scripts' clocks exactly (sprint end + 1 day;
the checkpoint itself), which the cross-check against their published results confirms.

Run (from ai-service/, needs eval/datasets/tawos.db):
    python -m eval.validate_phase1
Writes eval/phase1_validation_result.json.
"""

from __future__ import annotations

import os

# Validate the product as it ships: no LLM key. ai-service/.env may hold a real one;
# an empty variable overrides it, so nothing here can spend a quota.
os.environ["GROQ_API_KEY"] = ""

import asyncio  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import statistics  # noqa: E402
import time  # noqa: E402
from collections import Counter, defaultdict  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

import httpx  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from app.api.v1.analyze import llm_client  # noqa: E402
from app.graph import GraphBuilder, GraphMetrics  # noqa: E402
from app.graph.actions import _skew_severity  # noqa: E402
from app.graph.metrics import open_point_loads  # noqa: E402
from app.graph.snapshot import ProjectSnapshot  # noqa: E402
from app.llm.client import GroqClient, LLMUnavailable  # noqa: E402
from app.main import app  # noqa: E402
from app.models.agent_base import (  # noqa: E402
    PlanningOutput,
    ProgressOutput,
    RecommendationOutput,
    RiskOutput,
    WorkloadIntelOutput,
)
from eval.datasets.tawos_ingest import build_sprint_cases, connect  # noqa: E402

EVAL = Path(__file__).parent
OUT = EVAL / "phase1_validation_result.json"
SCOPE = ["planning", "progress", "workload"]  # what the backend sends (app/services/ai_client.py)
SPECIALISTS = {
    "planning": PlanningOutput,
    "progress": ProgressOutput,
    "workload": WorkloadIntelOutput,
    "risk": RiskOutput,
    "recommendation": RecommendationOutput,
}
LEVELS = ["low", "medium", "high", "critical"]
EFFECT = re.compile(r"from (\d+) to (\d+) points against a team mean of ([\d.]+) — load skew (\w+) → (\w+)")


# ----------------------------------------------------------------- helpers
def _aware(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", ""))
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def shift(snapshot: ProjectSnapshot, delta: timedelta) -> ProjectSnapshot:
    """Move every timestamp by delta, keeping every interval exactly as it was."""
    s = snapshot.model_copy(deep=True)
    move = lambda v: v + delta if v is not None else None  # noqa: E731
    for m in s.milestones:
        m.start_date, m.target_date = move(m.start_date), move(m.target_date)
    for t in s.tasks:
        t.due_date, t.created_at, t.completed_at = move(t.due_date), move(t.created_at), move(t.completed_at)
    for c in s.comments:
        c.created_at = move(c.created_at)
    s.as_of = move(s.as_of)
    return s


def confusion(pairs: list[tuple[bool, bool]]) -> dict:
    tp = sum(y and p for y, p in pairs)
    fp = sum(not y and p for y, p in pairs)
    fn = sum(y and not p for y, p in pairs)
    tn = sum(not y and not p for y, p in pairs)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"n": len(pairs), "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(precision, 4),
            "recall": round(recall, 4), "f1": round(f1, 4), "accuracy": round((tp + tn) / len(pairs), 4)}


def pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


def rate(ok: int, total: int) -> dict:
    return {"ok": ok, "total": total, "rate": round(ok / total, 4) if total else None}


class LLMCounter:
    """Wraps the LLM client: counts attempts, and how many were refused before any network I/O."""

    def __init__(self) -> None:
        self.attempts = self.refused = 0
        self._original = GroqClient.generate_structured

    def __enter__(self):
        counter = self

        async def counted(client, *args, **kwargs):
            counter.attempts += 1
            try:
                return await counter._original(client, *args, **kwargs)
            except LLMUnavailable:
                counter.refused += 1
                raise

        GroqClient.generate_structured = counted
        return self

    def __exit__(self, *exc):
        GroqClient.generate_structured = self._original


# ------------------------------------------------ independent recounts (not agent code)
def expected_planning_summary(s: ProjectSnapshot) -> str:
    milestones = len(s.milestones)
    covered = sum(1 for m in s.milestones if any(t.milestone_id == m.id for t in s.tasks))
    readiness = covered / milestones if milestones else 0.5
    return f"Planning analysis: {milestones} milestones, {len(s.tasks)} tasks. Sprint readiness: {readiness:.0%}"


def expected_progress(s: ProjectSnapshot) -> tuple[float, set[str]]:
    done = sum(1 for t in s.tasks if t.status == "done")
    blocked = {str(t.id) for t in s.tasks if t.status == "blocked"}
    return round(done / max(len(s.tasks), 1), 3), blocked


def expected_workload(s: ProjectSnapshot) -> tuple[int, set[str], set[str]]:
    loads: dict[str, int] = defaultdict(int)
    for t in s.tasks:
        if t.assignee_id is not None:
            loads[str(t.assignee_id)] += t.story_points or 0
    if not loads:
        return 0, set(), set()
    avg = sum(loads.values()) / len(loads)
    return (len(loads), {u for u, v in loads.items() if v > avg * 1.5},
            {u for u, v in loads.items() if v < avg * 0.5})


# ------------------------------------------------------------------ one run
async def analyze(http: httpx.AsyncClient, snapshot: ProjectSnapshot, eval_time: datetime) -> tuple[dict, float]:
    delta = datetime.now(timezone.utc) - eval_time
    payload = {"project_id": str(snapshot.project_id), "scope": SCOPE, "trigger_type": "validation",
               "snapshot": shift(snapshot, delta).model_dump(mode="json")}
    started = time.perf_counter()
    response = await http.post("/api/v1/analyze", json=payload)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.raise_for_status()
    return response.json(), elapsed_ms


def canonical(result: dict) -> str:
    return json.dumps(result.get("result"), sort_keys=True)


class Tally:
    def __init__(self) -> None:
        self.c: Counter = Counter()
        self.latency: list[tuple[int, float]] = []
        self.delay_pairs: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
        self.rec_by_type: Counter = Counter()
        self.rec_needed_by_type: Counter = Counter()
        self.peak_drops: list[int] = []
        self.failures: list[str] = []

    def check(self, key: str, holds: bool, detail: str = "") -> None:
        self.c[f"{key}.total"] += 1
        if holds:
            self.c[f"{key}.ok"] += 1
        elif len(self.failures) < 40:
            self.failures.append(f"{key}: {detail}"[:300])

    def get(self, key: str) -> dict:
        return rate(self.c[f"{key}.ok"], self.c[f"{key}.total"])


def validate_run(t: Tally, case, mode: str, body: dict, eval_time: datetime, holdout: set[str]) -> None:
    snap: ProjectSnapshot = case.snapshot
    where = f"{case.project_key}/{case.sprint_jira_id}/{mode}"
    t.check("coordinator.completed", body.get("status") == "completed", where)
    result = body.get("result") or {}
    outputs = result.get("specialist_outputs") or {}

    # -- coordinator: every specialist present, none an error stub, every schema valid
    t.check("coordinator.all_specialists", set(SPECIALISTS) <= set(outputs), f"{where} {sorted(outputs)}")
    for name, model in SPECIALISTS.items():
        out = outputs.get(name) or {}
        t.check(f"{name}.no_error", "agent failed" not in (out.get("summary") or ""), f"{where} {out.get('summary')}")
        try:
            model.model_validate(out)
            t.check(f"{name}.schema_valid", True)
        except ValidationError as exc:
            t.check(f"{name}.schema_valid", False, f"{where} {exc.errors()[:1]}")

    # -- planning / progress / workload against independent recounts
    planning, progress, workload = outputs.get("planning", {}), outputs.get("progress", {}), outputs.get("workload", {})
    t.check("planning.figures_match", planning.get("summary") == expected_planning_summary(snap),
            f"{where} got {planning.get('summary')!r} want {expected_planning_summary(snap)!r}")
    completion, blocked = expected_progress(snap)
    t.check("progress.completion_matches", progress.get("completion_rate") == completion,
            f"{where} got {progress.get('completion_rate')} want {completion}")
    stalled = {w.get("task_id") for w in progress.get("stalled_work") or []}
    t.check("progress.stalled_matches", stalled == blocked, f"{where} got {len(stalled)} want {len(blocked)}")
    members, over, under = expected_workload(snap)
    got_over = {m["user_id"] for m in workload.get("overloaded_members") or []}
    got_under = {m["user_id"] for m in workload.get("underutilized_members") or []}
    summary = workload.get("summary") or ""
    counts_ok = (summary == "No assignments to analyze") if members == 0 else summary.startswith(f"Workload: {members} members,")
    t.check("workload.figures_match", counts_ok and got_over == over and got_under == under,
            f"{where} members {members} over {len(over)}/{len(got_over)} under {len(under)}/{len(got_under)}")

    # -- risk: the endpoint must give exactly what the graph computes directly
    graph = GraphBuilder().build(snap)
    direct = GraphMetrics(now=eval_time).compute(graph)
    risk = outputs.get("risk", {})
    t.check("risk.matches_direct_computation", risk.get("risk_scores") == direct.risk_scores
            and result.get("overall_risk_level") == direct.overall_risk_level,
            f"{where} api {risk.get('risk_scores')} direct {direct.risk_scores}")
    findings = (risk.get("metadata") or {}).get("findings") or []
    for f in findings:
        t.check("risk.findings_cite_evidence", bool(f.get("node_ids")), f"{where} {f.get('title')}")
        for node in f.get("node_ids") or []:
            t.check("risk.citations_resolve", graph.has_node(node), f"{where} {node}")
    for name in SPECIALISTS:
        for ev in (outputs.get(name) or {}).get("evidence") or []:
            if ev.get("reference_id"):
                t.check("evidence.references_resolve", graph.has_node(ev["reference_id"]), f"{where} {ev['reference_id']}")

    predicted = (risk.get("risk_scores") or {}).get("delay", "low") != "low"
    split = "holdout" if case.project_key in holdout else "tuning"
    t.delay_pairs[f"{mode}.all"].append((case.label_delayed, predicted))
    t.delay_pairs[f"{mode}.{split}"].append((case.label_delayed, predicted))

    # -- recommendation: one per medium+ risk type, each grounded in a finding
    recs = result.get("merged_recommendations") or []
    titles = {f.get("title"): f.get("risk_type") for f in findings}
    for rec in recs:
        t.check("recommendation.grounded_in_finding", rec.get("description") in titles, f"{where} {rec.get('title')}")
    covered = {titles.get(rec.get("description")) for rec in recs}
    for rtype, level in (risk.get("risk_scores") or {}).items():
        if LEVELS.index(level) >= 1:
            t.rec_needed_by_type[rtype] += 1
            t.rec_by_type[rtype] += rtype in covered
            t.check("recommendation.covers_medium_plus_risks", rtype in covered, f"{where} {rtype}={level}")

    # -- the suggested reassignments, applied and re-measured
    rebalance = next((r for r in recs if r.get("title") == "Redistribute workload"), None)
    if rebalance is None:
        return
    actions = [a for a in rebalance.get("actions") or [] if a.get("kind") == "reassign"]
    t.c["rebalance.recommendations"] += 1
    if not actions:
        t.c["rebalance.without_moves"] += 1
        return
    t.c["rebalance.with_moves"] += 1
    match = EFFECT.search(rebalance.get("expected_effect") or "")
    t.check("rebalance.effect_stated", match is not None, f"{where} {rebalance.get('expected_effect')}")
    if match is None:
        return
    peak_before, peak_after, _mean, sev_before, sev_after = match.groups()

    loads, _ = open_point_loads(graph)
    mean = statistics.mean(loads.values())
    t.check("rebalance.before_matches_board", max(loads.values()) == int(peak_before), where)
    owner = {str(task.id): str(task.assignee_id) for task in snap.tasks}
    moved = snap.model_copy(deep=True)
    by_id = {str(task.id): task for task in moved.tasks}
    member_ids = {str(m.id) for m in snap.members}
    peaks = [max(loads.values())]
    valid_moves = True
    for a in actions:
        task_id, frm, to = (x.split(":", 1)[1] for x in (a["task_id"], a["from_person"], a["to_person"]))
        valid_moves &= owner.get(task_id) == frm and to in member_ids and task_id in by_id
        if task_id in by_id:
            by_id[task_id].assignee_id = to
            step, _ = open_point_loads(GraphBuilder().build(moved))
            peaks.append(max(step.values()))
    t.check("rebalance.moves_are_valid", valid_moves, where)
    t.check("rebalance.no_move_raises_peak", all(b <= a for a, b in zip(peaks, peaks[1:])), f"{where} {peaks}")
    actual_peak = peaks[-1]
    t.check("rebalance.predicted_peak_holds", actual_peak == int(peak_after), f"{where} {peak_after} vs {actual_peak}")
    t.check("rebalance.predicted_severity_holds", _skew_severity(actual_peak, mean) == sev_after,
            f"{where} {sev_after} vs {_skew_severity(actual_peak, mean)}")
    # Effectiveness, not correctness: with at most three moves, a very uneven team can
    # improve without crossing into a lower band. Reported as a rate, not a pass/fail.
    t.c["rebalance.severity_improved"] += LEVELS.index(sev_after) < LEVELS.index(sev_before)
    t.peak_drops.append(int(peak_before) - actual_peak)
    t.c[f"rebalance.transition.{sev_before}->{sev_after}"] += 1


# ------------------------------------------------------------------ main
async def main() -> None:
    assert not llm_client.configured, "validation must run with no LLM key"
    split = json.loads((EVAL / "datasets" / "tawos_split.json").read_text())
    holdout = set(split["holdout_projects"])
    conn = connect()
    limit = int(os.environ.get("VALIDATE_LIMIT", "0")) or None  # a quick sample; the cross-check needs all
    cases = {"end": list(build_sprint_cases(conn, limit=limit)),
             "mid": list(build_sprint_cases(conn, limit=limit, checkpoint=0.5))}
    clocks = {
        "end": lambda c: _aware(c.sprint_end) + timedelta(days=1),  # as tawos_score / tawos_holdout_eval
        "mid": lambda c: _aware(c.as_of),                          # as tawos_midsprint_eval
    }
    t = Tally()
    first_pass: dict[str, str] = {}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://ai-service", timeout=120) as http:
        with LLMCounter() as llm:
            for mode, batch in cases.items():
                for i, case in enumerate(batch, 1):
                    eval_time = clocks[mode](case)
                    body, ms = await analyze(http, case.snapshot, eval_time)
                    t.latency.append((len(case.snapshot.tasks), ms))
                    validate_run(t, case, mode, body, eval_time, holdout)
                    if mode == "end":
                        first_pass[f"{case.project_key}/{case.sprint_jira_id}"] = canonical(body)
                    if i % 200 == 0:
                        print(f"  {mode}: {i}/{len(batch)}", flush=True)

            # Determinism: the same sprint, analysed again, must give the same answer.
            for case in cases["end"]:
                body, _ = await analyze(http, case.snapshot, clocks["end"](case))
                key = f"{case.project_key}/{case.sprint_jira_id}"
                t.check("coordinator.deterministic", canonical(body) == first_pass[key], key)

    # -- cross-check against the published evaluation results
    published_end = json.loads((EVAL / "datasets" / "tawos_score_result.json").read_text())["graph_metrics"]
    published_mid = json.loads((EVAL / "datasets" / "tawos_midsprint_result.json").read_text())["checkpoints"]["50%"]
    ours_end, ours_mid = confusion(t.delay_pairs["end.all"]), confusion(t.delay_pairs["mid.all"])
    same = lambda a, b: all(a[k] == b[k] for k in ("tp", "fp", "fn", "tn"))  # noqa: E731

    sizes = [n for n, _ in t.latency]
    buckets = {"<25 tasks": (0, 25), "25-49": (25, 50), "50-99": (50, 100), "100+": (100, 10**6)}
    latency = {"all": {"n": len(t.latency), "p50_ms": round(pct([m for _, m in t.latency], 0.5), 1),
                       "p95_ms": round(pct([m for _, m in t.latency], 0.95), 1),
                       "max_ms": round(max(m for _, m in t.latency), 1)}}
    for label, (lo, hi) in buckets.items():
        ms = [m for n, m in t.latency if lo <= n < hi]
        if ms:
            latency[label] = {"n": len(ms), "p50_ms": round(pct(ms, 0.5), 1), "p95_ms": round(pct(ms, 0.95), 1)}

    keys = sorted({k.rsplit(".", 1)[0] for k in t.c if k.endswith(".total")})
    result = {
        "method": __doc__.strip().splitlines()[0],
        "dataset": {"sprints": len(cases["end"]), "runs": len(t.latency) + len(cases["end"]),
                    "tasks_per_sprint": {"median": statistics.median(sizes), "max": max(sizes)},
                    "holdout_projects": len(holdout)},
        "llm": {"key_configured": llm_client.configured, "calls_attempted": llm.attempts,
                "refused_before_network": llm.refused},
        "checks": {k: t.get(k) for k in keys},
        "delay_prediction": {k: confusion(v) for k, v in sorted(t.delay_pairs.items())},
        "cross_check_with_published": {
            "end_of_sprint_all_987": {"published": {k: published_end[k] for k in ("tp", "fp", "fn", "tn")},
                                      "via_api": {k: ours_end[k] for k in ("tp", "fp", "fn", "tn")},
                                      "identical": same(ours_end, published_end)},
            "midsprint_50pct_all": {"published": {k: published_mid["all"]["pace_rule"][k] for k in ("tp", "fp", "fn", "tn")},
                                    "via_api": {k: ours_mid[k] for k in ("tp", "fp", "fn", "tn")},
                                    "identical": same(ours_mid, published_mid["all"]["pace_rule"])},
        },
        "recommendation_coverage_by_risk": {k: rate(t.rec_by_type[k], t.rec_needed_by_type[k])
                                            for k in sorted(t.rec_needed_by_type)},
        "rebalance": {
            "workload_recommendations": t.c["rebalance.recommendations"],
            "with_moves": t.c["rebalance.with_moves"],
            "without_moves": t.c["rebalance.without_moves"],
            "severity_improved": rate(t.c["rebalance.severity_improved"], t.c["rebalance.with_moves"]),
            "peak_drop_points": {"mean": round(statistics.mean(t.peak_drops), 2) if t.peak_drops else None,
                                 "median": statistics.median(t.peak_drops) if t.peak_drops else None},
            "transitions": {k.split(".", 2)[2]: v for k, v in sorted(t.c.items()) if k.startswith("rebalance.transition.")},
        },
        "latency_in_process": latency,
        "failures_sample": t.failures,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n")

    print("\nchecks:")
    for k in keys:
        r = t.get(k)
        print(f"  {'ok  ' if r['ok'] == r['total'] else 'FAIL'}  {k:42} {r['ok']}/{r['total']}")
    print("\ncross-check with published results:",
          {k: v["identical"] for k, v in result["cross_check_with_published"].items()})
    print("llm:", result["llm"])
    print("latency:", latency["all"])
    print(f"\nwrote {OUT.name}")


if __name__ == "__main__":
    asyncio.run(main())
