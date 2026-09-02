"""Ablation: does graph-grounding cost DETECTION ACCURACY, or only save tokens?

run_eval.py proves the graph architecture is ~487x cheaper in prompt tokens
than the naive "stringify the dataset into the prompt" approach this project
started from. It does NOT prove the two are equally accurate — and a reviewer
is entitled to ask whether 99.8% fewer tokens bought a quietly worse detector.

This script answers that directly: both architectures are scored on the SAME
synthetic scenarios, against the SAME deterministically-injected ground truth
(eval/scenarios.py), and their precision/recall/F1 are compared head to head.

    graph path — GraphBuilder -> GraphMetrics, deterministic, 0 LLM tokens.
                 Detection is measured exactly as run_eval.py measures it, so
                 the number here is directly comparable to the one already
                 reported.

    naive path — the ORIGINAL pre-graph architecture: the entire project
                 dataset is serialized into the user prompt and a single LLM
                 call is asked which risks are present.

FAIRNESS — this is deliberately stacked in the NAIVE path's favour, so that a
graph win cannot be dismissed as a strawman:

1. Small projects only (sizes 10/20). The naive prompt is O(project size), so
   small projects are where it is most competitive and most affordable — a
   2,000-task project would not fit the budget at all. Testing accuracy, not
   cost, means giving it the sizes it can actually handle.
2. It receives EVERYTHING — tasks, members, milestones, dependencies and
   comments — in one call. That is strictly more context than the real old
   architecture gave any single agent (which fanned partial data across three
   specialists), and strictly more than the graph path's witness subgraph.
3. The prompt is written in good faith: each of the six risk types is defined
   explicitly, so the model is never guessing at the taxonomy.
4. Its response is parsed LENIENTLY (see _extract_risks). A malformed-but-
   readable answer still counts. Schema-compliance is measured separately in
   live_llm_eval.py; penalising it twice here would conflate "can't format
   JSON" with "can't detect risk".

Run: python -m eval.ablation_naive_vs_graph   (needs GROQ_API_KEY; billed calls)
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, asdict
from pathlib import Path

from app.graph import GraphBuilder, GraphMetrics
from app.config import get_settings
from app.llm.client import GroqClient
from eval.scenarios import generate_scenarios

CHECKPOINT_PATH = Path(__file__).parent / "ablation_checkpoint.jsonl"
RESULT_PATH = Path(__file__).parent / "ablation_result.json"

BASE_PACING_SECONDS = 20
BACKOFF_SCHEDULE = [30, 45, 60]

RISK_TYPES = ["dependency", "knowledge", "workload", "delay", "silent_member", "coordination"]

NAIVE_SYSTEM_PROMPT = """You are a project risk analyst. You will be given the complete raw data \
for a software project: its tasks, team members, milestones, task dependencies, and comments.

Identify which of the following six coordination risks are genuinely present:

- "dependency": a circular dependency chain exists between tasks (A blocks B blocks C blocks A), \
or the dependency structure funnels through a single bottleneck task.
- "knowledge": a single point of failure — one person is the sole owner of all work on a \
component/milestone, so their absence would block it entirely.
- "workload": workload is unevenly distributed — one person carries substantially more story \
points of open work than their teammates.
- "delay": a significant share of tasks are overdue (due date already passed while still open).
- "silent_member": a significant share of assigned team members have no comment activity at all, \
suggesting they may be blocked or disengaged.
- "coordination": one or more team members are working in isolation, not sharing any milestone \
or collaboration surface with the rest of the team.

Report only risks the data actually supports. Do not report a risk that is not present — \
false alarms are as costly as misses.

Respond with a single JSON object: {"risks_present": ["<risk name>", ...]}
Use exactly the risk names listed above. An empty list is a valid and expected answer for a \
healthy project."""


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def accuracy(self) -> float:
        n = self.tp + self.fp + self.fn + self.tn
        return (self.tp + self.tn) / n if n else 1.0

    def add(self, label: bool, predicted: bool) -> None:
        if label and predicted:
            self.tp += 1
        elif label and not predicted:
            self.fn += 1
        elif not label and predicted:
            self.fp += 1
        else:
            self.tn += 1

    def report(self) -> dict:
        return asdict(self) | {
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "accuracy": round(self.accuracy, 4),
        }


class BackoffClient(GroqClient):
    """Same real-backoff-on-429 behaviour used by live_llm_eval.py: production's
    own retry has no delay, which is useless against an active rate limit."""

    def __init__(self):
        super().__init__()
        self.errors: list[str] = []

    async def ask_json(self, system_prompt: str, user_prompt: str) -> dict | None:
        import httpx

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": 2000,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        for i in range(len(BACKOFF_SCHEDULE) + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions", json=payload, headers=headers
                    )
                    resp.raise_for_status()
                    return json.loads(resp.json()["choices"][0]["message"]["content"])
            except Exception as e:
                if "429" in str(e) and i < len(BACKOFF_SCHEDULE):
                    await asyncio.sleep(BACKOFF_SCHEDULE[i])
                    continue
                self.errors.append(f"{type(e).__name__}: {e}")
                return None
        return None


def _extract_risks(response: dict | None) -> list[str] | None:
    """Lenient parse — see the FAIRNESS note in the module docstring. Returns
    None only if nothing usable came back at all (which is scored as a failed
    call, not as a wrong answer)."""
    if response is None:
        return None
    candidates = None
    if isinstance(response.get("risks_present"), list):
        candidates = response["risks_present"]
    else:
        # Accept any list-of-strings field, or a dict of {risk: bool}.
        for value in response.values():
            if isinstance(value, list) and all(isinstance(x, str) for x in value):
                candidates = value
                break
        if candidates is None:
            truthy = [k for k, v in response.items() if v is True and k in RISK_TYPES]
            if truthy:
                candidates = truthy
    if candidates is None:
        return None
    # Normalise loose spellings ("silent member", "Silent_Member", "SPOF").
    out = []
    for c in candidates:
        norm = str(c).strip().lower().replace(" ", "_").replace("-", "_")
        if norm in RISK_TYPES:
            out.append(norm)
        elif norm in ("spof", "single_point_of_failure", "knowledge_risk"):
            out.append("knowledge")
        elif norm in ("workload_imbalance", "workload_skew"):
            out.append("workload")
        elif norm in ("silent", "silent_members", "disengagement"):
            out.append("silent_member")
    return out


def _naive_prompt(snapshot) -> str:
    """The original pre-graph approach: the whole dataset, stringified."""
    context = {
        "members": [m.model_dump() for m in snapshot.members],
        "milestones": [m.model_dump() for m in snapshot.milestones],
        "tasks": [t.model_dump() for t in snapshot.tasks],
        "dependencies": [d.model_dump() for d in snapshot.dependencies],
        "comments": [c.model_dump() for c in snapshot.comments],
    }
    return f"Analyze this project data and identify which risks are present:\n{context}"


async def main() -> None:
    settings = get_settings()
    if not settings.GROQ_API_KEY:
        raise SystemExit("GROQ_API_KEY is not set. This script makes real, billed API calls.")

    llm = BackoffClient()

    # Small projects only — the naive path's best case (see FAIRNESS #1).
    scenarios = generate_scenarios(seed=42, per_type=6, sizes=(10, 20))
    print(f"{len(scenarios)} scenarios "
          f"({sum(1 for s in scenarios if s.label)} positive) across {len(RISK_TYPES)} risk types",
          flush=True)

    done: dict[int, dict] = {}
    if CHECKPOINT_PATH.exists():
        for line in CHECKPOINT_PATH.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["i"]] = rec
        print(f"resuming: {len(done)} scenarios already recorded", flush=True)

    fh = open(CHECKPOINT_PATH, "a", buffering=1)
    graph_counts, naive_counts = Counts(), Counts()
    per_type_graph: dict[str, Counts] = {rt: Counts() for rt in RISK_TYPES}
    per_type_naive: dict[str, Counts] = {rt: Counts() for rt in RISK_TYPES}
    graph_tokens, naive_tokens = [], []
    naive_failed_calls = 0
    scored = 0

    start = asyncio.get_event_loop().time()

    for i, sc in enumerate(scenarios):
        # --- graph path: deterministic, no LLM, no rate limit ---
        graph = GraphBuilder().build(sc.snapshot)
        analysis = GraphMetrics().compute(graph)
        graph_pred = any(f.metric == sc.metric and f.severity != "low" for f in analysis.findings)

        from app.graph import SubgraphSelector
        witness = SubgraphSelector().select(graph, analysis.findings)
        graph_prompt_tokens = len(witness.render()) // 4

        naive_user_prompt = _naive_prompt(sc.snapshot)
        naive_prompt_tokens = len(naive_user_prompt) // 4

        # --- naive path: full dataset into one LLM call ---
        if i in done:
            rec = done[i]
            naive_risks = rec["naive_risks"]
        else:
            response = await llm.ask_json(NAIVE_SYSTEM_PROMPT, naive_user_prompt)
            naive_risks = _extract_risks(response)
            rec = {
                "i": i, "risk_type": sc.risk_type, "metric": sc.metric, "label": sc.label,
                "graph_pred": graph_pred, "naive_risks": naive_risks,
                "graph_prompt_tokens": graph_prompt_tokens,
                "naive_prompt_tokens": naive_prompt_tokens,
            }
            fh.write(json.dumps(rec) + "\n")
            await asyncio.sleep(BASE_PACING_SECONDS)

        graph_tokens.append(graph_prompt_tokens)
        naive_tokens.append(naive_prompt_tokens)

        if naive_risks is None:
            # The call itself failed (rate limit / unparseable). Excluded from
            # BOTH scorers so the comparison stays strictly like-for-like.
            naive_failed_calls += 1
        else:
            naive_pred = sc.risk_type in naive_risks
            graph_counts.add(sc.label, graph_pred)
            naive_counts.add(sc.label, naive_pred)
            per_type_graph[sc.risk_type].add(sc.label, graph_pred)
            per_type_naive[sc.risk_type].add(sc.label, naive_pred)
            scored += 1

        elapsed = asyncio.get_event_loop().time() - start
        print(f"[{elapsed:6.0f}s] {i + 1}/{len(scenarios)} {sc.risk_type:14} "
              f"label={str(sc.label):5} graph={str(graph_pred):5} "
              f"naive={naive_risks if naive_risks is not None else 'CALL_FAILED'}", flush=True)

    fh.close()

    result = {
        "model": settings.AI_MODEL,
        "n_scenarios": len(scenarios),
        "n_scored": scored,
        "n_naive_calls_failed": naive_failed_calls,
        "note": "Scenarios where the naive LLM call failed outright (rate limit / "
                "unparseable) are excluded from BOTH scorers, so the comparison is "
                "strictly like-for-like on identical scenarios.",
        "graph_architecture": graph_counts.report(),
        "naive_architecture": naive_counts.report(),
        "per_risk_type": {
            rt: {"graph": per_type_graph[rt].report(), "naive": per_type_naive[rt].report()}
            for rt in RISK_TYPES
        },
        "mean_prompt_tokens": {
            "graph": round(sum(graph_tokens) / len(graph_tokens), 1) if graph_tokens else 0,
            "naive": round(sum(naive_tokens) / len(naive_tokens), 1) if naive_tokens else 0,
        },
        "naive_call_errors": llm.errors,
    }
    print("\n" + json.dumps(result, indent=2))
    RESULT_PATH.write_text(json.dumps(result, indent=2))
    print(f"\nwritten to {RESULT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
