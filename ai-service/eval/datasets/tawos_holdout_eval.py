"""THE held-out evaluation. Run this once, report whatever it says.

Everything selected in tawos_tune.py / tawos_tune2.py / tawos_composite.py
was decided using tuning-set data only. This script applies those frozen
decisions to the 22 held-out projects (270 sprints) that no tuning step ever
saw, and reports the result — better or worse.

If this number disappoints, the correct response is to report it, not to go
back and re-tune until it improves: doing that would silently turn the
held-out set into a second tuning set and the number would stop meaning
anything.

Run: python -m eval.datasets.tawos_holdout_eval
"""

from __future__ import annotations

import json
import statistics
from datetime import timedelta
from pathlib import Path

from app.graph import GraphBuilder, GraphMetrics
from eval.datasets.tawos_composite import predict_proba
from eval.datasets.tawos_features import extract_features
from eval.datasets.tawos_ingest import build_sprint_cases, connect
from eval.datasets.tawos_score import _auc, _brier, _confusion, _parse_dt
from eval.datasets.tawos_split import load_split

MODEL_PATH = Path(__file__).parent / "tawos_composite_model.json"


def main():
    model = json.loads(MODEL_PATH.read_text())
    features, weights, means, stds = model["features"], model["weights"], model["means"], model["stds"]

    split = load_split()
    holdout_projects = set(split["holdout_projects"])
    conn = connect()
    cases = [c for c in build_sprint_cases(conn) if c.project_key in holdout_projects]
    print(f"held-out: {len(cases)} sprints from {len(set(c.project_key for c in cases))} projects")

    labels, composite_probs, baseline_preds = [], [], []
    for c in cases:
        graph = GraphBuilder().build(c.snapshot)
        eval_time = _parse_dt(c.sprint_end) + timedelta(days=1)
        analysis = GraphMetrics(now=eval_time).compute(graph)
        feats = extract_features(analysis)

        scaled = [(feats[k] - means[j]) / stds[j] for j, k in enumerate(features)]
        composite_probs.append(predict_proba(weights, scaled))
        labels.append(c.label_delayed)
        # The original, untuned single-signal rule, for direct comparison.
        baseline_preds.append(analysis.risk_scores.get("delay", "low") != "low")

    composite_preds = [p >= 0.5 for p in composite_probs]

    result = {
        "n_sprints": len(cases),
        "n_projects": len(set(c.project_key for c in cases)),
        "label_positive_rate": round(sum(labels) / len(labels), 4),
        "composite_model": {
            **_confusion(list(zip(labels, composite_preds))),
            "auc": round(_auc(labels, composite_probs), 4),
            "brier": round(_brier(labels, composite_probs), 4),
        },
        "original_single_signal": _confusion(list(zip(labels, baseline_preds))),
        "note": "Model and all thresholds were selected on the tuning split only; "
                "this held-out set was evaluated once.",
    }
    print(json.dumps(result, indent=2))

    out = Path(__file__).parent / "tawos_holdout_result.json"
    out.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
