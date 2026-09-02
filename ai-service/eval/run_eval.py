"""Zero-label evaluation harness for the knowledge-graph core.

Produces the metrics described in the plan's Part A2 — no external dataset
(that's Phase E1, deferred). Run: `python -m eval.run_eval` from ai-service/.

Four things are measured, each against a different part of the pipeline:

1. Detection accuracy   — GraphMetrics (app/graph/metrics.py): precision/
                           recall/F1 on synthetic scenarios with a known
                           injected anomaly (eval/scenarios.py).
2. Token cost vs size    — SubgraphSelector + WitnessSubgraph (app/graph/
                           subgraph.py): the O(anomalies)-not-O(size) claim.
3. Latency               — GraphBuilder + GraphMetrics + SubgraphSelector,
                           end to end: is the deterministic path fast enough
                           to run synchronously per plan Part B3.
4. Grounding enforcement — app/graph/grounding.py: whether a fabricated
                           evidence reference can ever survive to the caller.

Schema-validity and fallback-vs-LLM agreement (also listed in Part A2) need a
live GROQ_API_KEY and are not measured here — see the report's caveat.
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import asdict, dataclass

from app.graph import GraphBuilder, GraphMetrics, SubgraphSelector
from app.graph.grounding import drop_ungrounded
from eval.scenarios import generate_scenarios


@dataclass
class ConfusionCounts:
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


def run_detection_eval(seed: int = 42, per_type: int = 30) -> dict:
    scenarios = generate_scenarios(seed=seed, per_type=per_type)
    builder = GraphBuilder()
    metrics = GraphMetrics()

    per_risk_type: dict[str, ConfusionCounts] = {}
    overall = ConfusionCounts()
    examples: list[dict] = []

    for sc in scenarios:
        graph = builder.build(sc.snapshot)
        analysis = metrics.compute(graph)
        # "Detected" means the system would act on it: GraphMetrics reports
        # some signals (e.g. workload_skew) unconditionally as informational
        # context even when low, and recommendation_output_from_graph only
        # acts on medium+ severity (see app/services/graph_pipeline.py) — so
        # detection is measured the same way, not by mere Finding presence.
        predicted = any(f.metric == sc.metric and f.severity != "low" for f in analysis.findings)

        counts = per_risk_type.setdefault(sc.risk_type, ConfusionCounts())
        if sc.label and predicted:
            counts.tp += 1; overall.tp += 1
        elif sc.label and not predicted:
            counts.fn += 1; overall.fn += 1
        elif not sc.label and predicted:
            counts.fp += 1; overall.fp += 1
        else:
            counts.tn += 1; overall.tn += 1

        if len(examples) < 12:
            examples.append({
                "risk_type": sc.risk_type, "metric": sc.metric, "label": sc.label,
                "predicted": predicted, "description": sc.description,
            })

    return {
        "n_scenarios": len(scenarios),
        "overall": asdict(overall) | {
            "precision": overall.precision, "recall": overall.recall,
            "f1": overall.f1, "accuracy": overall.accuracy,
        },
        "per_risk_type": {
            rt: asdict(c) | {"precision": c.precision, "recall": c.recall, "f1": c.f1, "accuracy": c.accuracy}
            for rt, c in sorted(per_risk_type.items())
        },
        "examples": examples,
    }


def run_token_eval() -> dict:
    from eval.scenarios import workload_scenario
    import random

    rng = random.Random(7)
    sizes = [10, 50, 200, 1000, 2000]
    rows = []
    for n in sizes:
        sc = workload_scenario(rng, positive=True, size=n)
        graph = GraphBuilder().build(sc.snapshot)
        analysis = GraphMetrics().compute(graph)
        witness = SubgraphSelector().select(graph, analysis.findings_for("workload", "delay", "dependency"))
        rendered = witness.render()
        rows.append({
            "task_count": n + 3,  # workload_scenario adds 3 heavy tasks
            "witness_nodes": len(witness.node_ids),
            "rendered_chars": len(rendered),
            "approx_tokens": len(rendered) // 4,
        })

    baseline_repr_tokens = None
    try:
        # For comparison: what the OLD architecture would have cost — a raw
        # repr() dump of every task, once, for the largest size tested.
        sc = workload_scenario(rng, positive=True, size=sizes[-1])
        raw = f"{[t.model_dump() for t in sc.snapshot.tasks]}"
        baseline_repr_tokens = len(raw) // 4
    except Exception:
        pass

    smallest, largest = rows[0], rows[-1]
    growth_ratio = largest["approx_tokens"] / max(smallest["approx_tokens"], 1)
    size_ratio = largest["task_count"] / smallest["task_count"]

    return {
        "sweep": rows,
        "smallest_to_largest_task_growth": round(size_ratio, 2),
        "smallest_to_largest_token_growth": round(growth_ratio, 3),
        "old_architecture_repr_tokens_at_largest_size": baseline_repr_tokens,
        "new_architecture_tokens_at_largest_size": largest["approx_tokens"],
    }


def run_latency_eval(n_runs: int = 50) -> dict:
    import random
    from eval.scenarios import workload_scenario

    rng = random.Random(11)
    durations_ms = []
    for _ in range(n_runs):
        sc = workload_scenario(rng, positive=True, size=200)
        start = time.perf_counter()
        graph = GraphBuilder().build(sc.snapshot)
        analysis = GraphMetrics().compute(graph)
        SubgraphSelector().select(graph, analysis.findings_for("workload", "delay", "dependency", "knowledge"))
        durations_ms.append((time.perf_counter() - start) * 1000)

    durations_ms.sort()
    return {
        "n_runs": n_runs,
        "project_size_tasks": 203,
        "p50_ms": round(statistics.median(durations_ms), 3),
        "p95_ms": round(durations_ms[int(0.95 * len(durations_ms)) - 1], 3),
        "max_ms": round(max(durations_ms), 3),
        "mean_ms": round(statistics.mean(durations_ms), 3),
    }


def run_grounding_eval(n_trials: int = 200) -> dict:
    import random

    rng = random.Random(3)
    caught = 0
    for i in range(n_trials):
        real_ids = [f"task:{i}-real-{j}" for j in range(rng.randint(0, 3))]
        fake_ids = [f"task:{i}-fabricated-{j}" for j in range(rng.randint(1, 3))]
        payload = {
            "evidence": [
                {"source": "graph", "reference_id": rid, "excerpt": "x", "relevance": 0.9}
                for rid in real_ids + fake_ids
            ]
        }
        cleaned = drop_ungrounded(payload, real_ids)
        surviving_ids = {e["reference_id"] for e in cleaned["evidence"]}
        if surviving_ids.isdisjoint(fake_ids) and surviving_ids == set(real_ids):
            caught += 1

    return {
        "n_trials": n_trials,
        "fabrications_fully_stripped": caught,
        "enforcement_rate": round(caught / n_trials, 4),
    }


def main() -> None:
    report = {
        "detection": run_detection_eval(),
        "tokens": run_token_eval(),
        "latency": run_latency_eval(),
        "grounding": run_grounding_eval(),
        "note": (
            "Schema-validity rate and fallback-vs-LLM agreement (Cohen's kappa) "
            "require a live GROQ_API_KEY and are not measured here."
        ),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
