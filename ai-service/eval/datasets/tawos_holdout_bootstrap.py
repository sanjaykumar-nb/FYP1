"""Bootstrap confidence intervals for the held-out result.

tawos_holdout_eval.py reports one point estimate (F1 0.712 for the untuned
graph rule) from one fixed split. A point estimate alone invites the fair
question "how stable is that number" — this answers it.

Method: CLUSTER bootstrap by PROJECT, not by sprint. Sprints within the same
project are correlated (shared team conventions, shared codebase health), so
resampling individual sprints would understate the true variance — exactly the
same reasoning that drove the project-level (not sprint-level) train/holdout
split in the first place (see tawos_split.py). Each bootstrap replicate:
resample the 22 held-out projects with replacement, keep every sprint
belonging to a resampled project, recompute the confusion matrix and F1/
precision/recall over the pooled resampled sprints. Repeat 2000 times; report
the 2.5th/97.5th percentiles as a 95% CI.

This resamples PROJECTS, so a replicate can contain a project 0, 1, or several
times — standard cluster bootstrap. The per-sprint predictions themselves are
never recomputed; they are the exact same ones tawos_holdout_eval.py produces
(same model, same frozen threshold), read once and resampled many times.

Run: python -m eval.datasets.tawos_holdout_bootstrap
"""

from __future__ import annotations

import json
import random
import statistics
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from app.graph import GraphBuilder, GraphMetrics
from eval.datasets.tawos_features import extract_features
from eval.datasets.tawos_ingest import build_sprint_cases, connect
from eval.datasets.tawos_score import _parse_dt
from eval.datasets.tawos_split import load_split

N_BOOTSTRAP = 2000
SEED = 12345


def _confusion_f1(pairs: list[tuple[bool, bool]]) -> dict:
    tp = sum(1 for y, p in pairs if y and p)
    fp = sum(1 for y, p in pairs if not y and p)
    fn = sum(1 for y, p in pairs if y and not p)
    tn = sum(1 for y, p in pairs if not y and not p)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / len(pairs) if pairs else 1.0
    return {"precision": precision, "recall": recall, "f1": f1, "accuracy": accuracy}


def _percentile_ci(values: list[float], lo=2.5, hi=97.5) -> tuple[float, float]:
    s = sorted(values)
    n = len(s)

    def pct(p):
        k = (p / 100) * (n - 1)
        f, c = int(k), min(int(k) + 1, n - 1)
        return s[f] + (s[c] - s[f]) * (k - f)

    return pct(lo), pct(hi)


def main() -> None:
    split = load_split()
    holdout_projects = sorted(set(split["holdout_projects"]))
    conn = connect()
    cases = [c for c in build_sprint_cases(conn) if c.project_key in holdout_projects]
    print(f"held-out: {len(cases)} sprints from {len(holdout_projects)} projects")

    # Reproduce the untuned single-signal rule's per-sprint prediction exactly
    # as tawos_holdout_eval.py does (analysis.risk_scores.get("delay","low") !=
    # "low"), and group by project for cluster resampling.
    by_project: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
    for c in cases:
        graph = GraphBuilder().build(c.snapshot)
        eval_time = _parse_dt(c.sprint_end) + timedelta(days=1)
        analysis = GraphMetrics(now=eval_time).compute(graph)
        pred = analysis.risk_scores.get("delay", "low") != "low"
        by_project[c.project_key].append((c.label_delayed, pred))

    point = _confusion_f1([pair for pairs in by_project.values() for pair in pairs])
    print(f"point estimate: precision={point['precision']:.4f} recall={point['recall']:.4f} "
          f"f1={point['f1']:.4f} accuracy={point['accuracy']:.4f}")

    rng = random.Random(SEED)
    boot_f1, boot_prec, boot_rec, boot_acc = [], [], [], []
    for _ in range(N_BOOTSTRAP):
        sampled_projects = [rng.choice(holdout_projects) for _ in range(len(holdout_projects))]
        pooled = [pair for proj in sampled_projects for pair in by_project[proj]]
        m = _confusion_f1(pooled)
        boot_f1.append(m["f1"]); boot_prec.append(m["precision"])
        boot_rec.append(m["recall"]); boot_acc.append(m["accuracy"])

    result = {
        "n_bootstrap": N_BOOTSTRAP,
        "method": "cluster bootstrap by project (resample 22 held-out projects "
                  "with replacement, pool their sprints, recompute confusion matrix)",
        "point_estimate": point,
        "ci_95": {
            "f1": _percentile_ci(boot_f1),
            "precision": _percentile_ci(boot_prec),
            "recall": _percentile_ci(boot_rec),
            "accuracy": _percentile_ci(boot_acc),
        },
        "bootstrap_std": {
            "f1": statistics.pstdev(boot_f1),
            "precision": statistics.pstdev(boot_prec),
            "recall": statistics.pstdev(boot_rec),
            "accuracy": statistics.pstdev(boot_acc),
        },
    }
    print(json.dumps(result, indent=2))

    out = Path(__file__).parent.parent / "tawos_holdout_bootstrap_result.json"
    out.write_text(json.dumps(result, indent=2))
    print(f"\nwritten to {out}")


if __name__ == "__main__":
    main()
