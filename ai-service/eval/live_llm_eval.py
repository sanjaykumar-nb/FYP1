"""Live-LLM evaluation: requires a real GROQ_API_KEY.

Everything in run_eval.py is deterministic-path only, by design (see its
docstring). This script closes the two metrics that explicitly required a
live key and were previously unmeasured:

1. Schema-validity rate  — does the RAW LLM response (before any Pydantic
   coercion) pass the same schema check the production client applies
   (app/llm/client.py: generate_structured -> validate_against_schema)?
2. Cohen's kappa          — agreement between the LLM narration path's
   risk_level and the deterministic rule-based fallback's risk_level, on the
   IDENTICAL input, for calls where the LLM path actually succeeded (a call
   that itself fell back is excluded — comparing fallback to fallback is
   trivially kappa=1 and would misrepresent agreement).

Uses the REAL production agents (PlanningAgent, ProgressAgent,
WorkloadIntelligenceAgent) and the REAL graph pipeline
(app/services/graph_pipeline.py) driving the same synthetic scenarios
run_eval.py uses (eval/scenarios.py) — nothing here is reimplemented, only
instrumented.

Run: python -m eval.live_llm_eval   (from ai-service/, with GROQ_API_KEY set)

v3 changes from the two earlier runs (v1: 600 tok/4s -> kappa 0.35, n=15;
v2: 2000 tok/18s -> kappa 0.84, n=33), both of which were dominated by
HTTP 429s from this account's real (lower-than-advertised) sustained
throughput:

- Retries a 429 with real backoff (30s, 45s, 60s) INSTEAD OF immediately
  counting it as a fallback outcome. Production's own generate_structured()
  retry (max_retries) fires with no delay, which is useless against a
  still-active rate limit — this eval script's retry loop replaces that
  fast-fail behavior (max_retries=1 is passed through to the production
  client so only genuine, non-429 failures count as one production attempt).
  This is scoped to the eval script only; production behavior is unchanged.
- Wider, balanced sample: per_type=5 across all 6 risk types x 3 agents
  = 90 live calls (vs. 54 previously), enabling a per-risk-type breakdown.
- Reports per-risk-type kappa in addition to the overall figure.

This still makes real, billed network calls, unlike every other script in
eval/ — and at this sample size + backoff, a full run can take 45-90+
minutes depending on how often the rate limit is actually hit.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import uuid4

from app.agents.planning import PlanningAgent
from app.agents.progress import ProgressAgent
from app.agents.workload_intel import WorkloadIntelligenceAgent
from app.config import get_settings
from app.llm.client import GroqClient
from app.llm.fallback import RuleBasedFallback
from app.services.graph_pipeline import (
    build_graph,
    build_planning_input,
    build_progress_input,
    build_workload_input,
)
from eval.scenarios import generate_scenarios

BASE_PACING_SECONDS = 20
BACKOFF_SCHEDULE = [30, 45, 60]  # seconds, on consecutive 429s for the same call
CHECKPOINT_PATH = Path(__file__).parent / "live_llm_checkpoint.jsonl"


class InstrumentedGroqClient(GroqClient):
    """Retries 429s with real backoff (production's own retry has no delay,
    which is useless against a still-active rate limit) and records the
    outcome of every logical call — success, or the genuine terminal error —
    without altering the schema-validation behavior itself."""

    def __init__(self):
        super().__init__()
        self.calls: list[dict] = []

    async def generate_structured(self, *args, **kwargs):
        kwargs.setdefault("max_retries", 1)  # our loop handles pacing, not production's fast-retry
        last_err: Exception | None = None
        attempts_used = 0
        for i in range(len(BACKOFF_SCHEDULE) + 1):
            attempts_used += 1
            try:
                result = await super().generate_structured(*args, **kwargs)
                self.calls.append({"valid": True, "error": None, "attempts": attempts_used})
                return result
            except Exception as e:
                last_err = e
                is_rate_limited = "429" in str(e)
                if is_rate_limited and i < len(BACKOFF_SCHEDULE):
                    await asyncio.sleep(BACKOFF_SCHEDULE[i])
                    continue
                break
        self.calls.append({
            "valid": False,
            "error": f"{type(last_err).__name__}: {last_err}",
            "attempts": attempts_used,
        })
        raise last_err


def _kappa(pairs: list[tuple[str, str]]) -> float:
    """Cohen's kappa, hand-rolled (no sklearn in this environment — see
    eval/datasets/tawos_composite.py for the same constraint elsewhere)."""
    n = len(pairs)
    if n == 0:
        return 1.0
    labels = sorted({a for a, _ in pairs} | {b for _, b in pairs})
    po = sum(1 for a, b in pairs if a == b) / n
    row_marg = {l: sum(1 for a, _ in pairs if a == l) / n for l in labels}
    col_marg = {l: sum(1 for _, b in pairs if b == l) / n for l in labels}
    pe = sum(row_marg[l] * col_marg[l] for l in labels)
    if pe >= 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


async def main() -> None:
    settings = get_settings()
    if not settings.GROQ_API_KEY:
        raise SystemExit(
            "GROQ_API_KEY is not set (checked ai-service/.env). "
            "This script makes real, billed API calls and cannot run without it."
        )

    llm = InstrumentedGroqClient()
    llm.max_tokens = 2000
    fallback = RuleBasedFallback()

    planning_agent = PlanningAgent(llm, fallback)
    progress_agent = ProgressAgent(llm, fallback)
    workload_agent = WorkloadIntelligenceAgent(llm, fallback)

    scenarios = generate_scenarios(seed=42, per_type=5)

    # Resume support: a completed (scenario_index, agent) call survives a
    # killed process (session restart, Monitor timeout, etc.) via a JSONL
    # checkpoint written after every single call, not just at the end.
    done: dict[tuple[int, str], dict] = {}
    if CHECKPOINT_PATH.exists():
        for line in CHECKPOINT_PATH.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            done[(rec["sc_i"], rec["agent"])] = rec
        print(f"resuming from checkpoint: {len(done)} calls already recorded", flush=True)

    agreement_pairs: list[tuple[str, str]] = []
    per_risk_type_pairs: dict[str, list[tuple[str, str]]] = {}
    per_agent_fallback_count: dict[str, int] = {}
    per_agent_total: dict[str, int] = {}
    examples: list[dict] = []
    n_valid = 0
    n_calls = 0

    start = asyncio.get_event_loop().time()
    checkpoint_fh = open(CHECKPOINT_PATH, "a", buffering=1)

    for sc_i, sc in enumerate(scenarios):
        graph, analysis = build_graph(sc.snapshot)
        project_id = uuid4()

        for name, agent, build_input, fallback_method in [
            ("planning", planning_agent, build_planning_input, fallback.planning_analysis),
            ("progress", progress_agent, build_progress_input, fallback.progress_analysis),
            ("workload", workload_agent, build_workload_input, fallback.workload_intel_analysis),
        ]:
            input_data = build_input(project_id, sc.snapshot, graph, analysis)
            fb_output = fallback_method(input_data)

            key = (sc_i, name)
            if key in done:
                rec = done[key]
                used_fallback = rec["used_fallback"]
                llm_risk_level = rec["llm_risk_level"]
            else:
                calls_before = len(llm.calls)
                llm_output = await agent.run(input_data)
                calls_after = len(llm.calls)
                used_fallback = calls_after > calls_before and not llm.calls[-1]["valid"]
                llm_risk_level = llm_output.risk_level
                if used_fallback:
                    print(f"    -> FALLBACK sc_i={sc_i} agent={name} "
                          f"attempts={llm.calls[-1]['attempts']} "
                          f"error={llm.calls[-1]['error']}", flush=True)

                rec = {
                    "sc_i": sc_i, "agent": name, "risk_type": sc.risk_type, "metric": sc.metric,
                    "used_fallback": used_fallback,
                    "llm_risk_level": llm_risk_level,
                    "fallback_risk_level": fb_output.risk_level,
                }
                checkpoint_fh.write(json.dumps(rec) + "\n")
                await asyncio.sleep(BASE_PACING_SECONDS)

            n_calls += 1
            if not used_fallback:
                n_valid += 1
            per_agent_total[name] = per_agent_total.get(name, 0) + 1
            if used_fallback:
                per_agent_fallback_count[name] = per_agent_fallback_count.get(name, 0) + 1
            else:
                pair = (llm_risk_level, fb_output.risk_level)
                agreement_pairs.append(pair)
                per_risk_type_pairs.setdefault(sc.risk_type, []).append(pair)

            if len(examples) < 15:
                examples.append({
                    "agent": name,
                    "scenario": f"{sc.risk_type}:{sc.metric}",
                    "used_fallback": used_fallback,
                    "llm_risk_level": llm_risk_level,
                    "fallback_risk_level": fb_output.risk_level,
                })

        elapsed = asyncio.get_event_loop().time() - start
        print(f"[{elapsed:6.0f}s] scenario {sc_i + 1}/{len(scenarios)} done "
              f"({sc.risk_type}:{sc.metric}) — {n_calls} calls so far, "
              f"{n_valid} valid", flush=True)

    checkpoint_fh.close()

    valid_calls = n_valid
    total_calls = n_calls
    total_fallback = sum(per_agent_fallback_count.values())

    result = {
        "model": settings.AI_MODEL,
        "n_scenarios": len(scenarios),
        "n_agent_calls": total_calls,
        "schema_valid_calls": valid_calls,
        "schema_validity_rate": round(valid_calls / total_calls, 4) if total_calls else None,
        "fallback_rate": round(total_fallback / total_calls, 4) if total_calls else None,
        "per_agent_fallback_count": per_agent_fallback_count,
        "per_agent_total_calls": per_agent_total,
        "n_llm_vs_fallback_comparisons": len(agreement_pairs),
        "cohens_kappa_overall": round(_kappa(agreement_pairs), 4),
        "cohens_kappa_by_risk_type": {
            rt: {"n": len(pairs), "kappa": round(_kappa(pairs), 4)}
            for rt, pairs in sorted(per_risk_type_pairs.items())
        },
        "raw_errors_this_process": [c["error"] for c in llm.calls if not c["valid"]],
        "attempts_histogram_this_process": {
            str(i): sum(1 for c in llm.calls if c["attempts"] == i)
            for i in sorted({c["attempts"] for c in llm.calls})
        } if llm.calls else {},
        "note": "raw_errors/attempts_histogram cover only calls made in this "
                "process invocation; resumed calls from a prior checkpointed "
                "run are folded into the aggregate counts but not these two "
                "diagnostic fields.",
        "examples": examples,
    }
    print(json.dumps(result, indent=2))

    out = Path(__file__).parent / "live_llm_result_v3.json"
    out.write_text(json.dumps(result, indent=2))
    print(f"\nwritten to {out}")


if __name__ == "__main__":
    asyncio.run(main())
