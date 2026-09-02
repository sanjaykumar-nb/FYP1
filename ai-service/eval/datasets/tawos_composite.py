"""A composite delay-risk score — logistic regression over GraphMetrics
findings, fit and cross-validated ENTIRELY within the tuning set.

Pure-Python logistic regression (numpy/sklearn are broken in this
environment — DLL load failure — and pulling in a heavy numeric dependency
for a ~700-row offline script would be overkill anyway). Verified against a
trivially-separable synthetic case before being trusted on real data.

Feature selection is not automatic: tawos_features.py showed most of
GraphMetrics' six risk types are structurally dead in a sprint-reconstructed
graph (dependency links span a project's whole history, not one sprint
window, so almost none land inside a single sprint — SPOF, cycles, and
coordination findings are ~0% nonzero here). Only features with real
nonzero coverage and a plausible independent contribution are used;
idle_member_ratio and workload_skew are included despite being partly
redundant with overdue_ratio (both collapse toward the same "how much is
open" fact when little is open) — the regression's own fitted weights and
the CV result reveal how much they add, if anything, rather than assuming.

Model selection (which features, whether this beats overdue_ratio alone) is
decided by CROSS-VALIDATED tuning-set performance only. The held-out set is
touched by nothing in this file.
"""

from __future__ import annotations

import math
import statistics
from datetime import timedelta

from app.graph import GraphBuilder, GraphMetrics
from eval.datasets.tawos_score import _auc, _confusion, _parse_dt
from eval.datasets.tawos_tune import _tuning_cases

FEATURES = ["delay:overdue_ratio", "workload:idle_member_ratio", "workload:workload_skew",
            "dependency:critical_path_share"]


def _sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def _standardize(rows: list[list[float]]) -> tuple[list[list[float]], list[float], list[float]]:
    n, d = len(rows), len(rows[0])
    means = [sum(r[j] for r in rows) / n for j in range(d)]
    stds = [((sum((r[j] - means[j]) ** 2 for r in rows) / n) ** 0.5) or 1.0 for j in range(d)]
    scaled = [[(r[j] - means[j]) / stds[j] for j in range(d)] for r in rows]
    return scaled, means, stds


def fit_logistic(X: list[list[float]], y: list[int], lr: float = 0.3, epochs: int = 3000, l2: float = 0.01) -> list[float]:
    n = len(X)
    d = len(X[0]) + 1  # + bias
    Xb = [[1.0] + row for row in X]
    w = [0.0] * d
    for _ in range(epochs):
        grad = [0.0] * d
        for xi, yi in zip(Xb, y):
            p = _sigmoid(sum(wj * xj for wj, xj in zip(w, xi)))
            err = p - yi
            for j in range(d):
                grad[j] += err * xi[j]
        for j in range(d):
            reg = l2 * w[j] if j > 0 else 0.0  # never regularize the bias
            w[j] -= lr * (grad[j] / n + reg)
    return w


def predict_proba(w: list[float], row: list[float]) -> float:
    xb = [1.0] + row
    return _sigmoid(sum(wj * xj for wj, xj in zip(w, xb)))


def _extract_dataset():
    from eval.datasets.tawos_features import extract_features

    cases = _tuning_cases()
    projects, labels, rows = [], [], []
    for c in cases:
        graph = GraphBuilder().build(c.snapshot)
        eval_time = _parse_dt(c.sprint_end) + timedelta(days=1)
        analysis = GraphMetrics(now=eval_time).compute(graph)
        feats = extract_features(analysis)
        rows.append([feats[k] for k in FEATURES])
        labels.append(1 if c.label_delayed else 0)
        projects.append(c.project_key)
    return projects, labels, rows


def _group_kfold(projects: list[str], k: int = 3, seed: int = 0):
    unique = sorted(set(projects))
    import random
    rng = random.Random(seed)
    rng.shuffle(unique)
    folds = [unique[i::k] for i in range(k)]
    for fold_projects in folds:
        test_idx = [i for i, p in enumerate(projects) if p in fold_projects]
        train_idx = [i for i, p in enumerate(projects) if p not in fold_projects]
        yield train_idx, test_idx


def cross_validate():
    projects, labels, raw_rows = _extract_dataset()

    fold_results = []
    for train_idx, test_idx in _group_kfold(projects, k=3):
        train_rows = [raw_rows[i] for i in train_idx]
        train_y = [labels[i] for i in train_idx]
        train_scaled, means, stds = _standardize(train_rows)
        w = fit_logistic(train_scaled, train_y)

        test_labels, test_preds, test_probs = [], [], []
        for i in test_idx:
            scaled = [(raw_rows[i][j] - means[j]) / stds[j] for j in range(len(FEATURES))]
            p = predict_proba(w, scaled)
            test_labels.append(bool(labels[i]))
            test_preds.append(p >= 0.5)
            test_probs.append(p)

        conf = _confusion(list(zip(test_labels, test_preds)))
        auc = _auc(test_labels, test_probs)
        fold_results.append({**conf, "auc": round(auc, 4), "weights": [round(x, 3) for x in w]})

    return fold_results


def fit_final_model() -> dict:
    """Fit on the ENTIRE tuning set (no held-out data touched) — this is the
    model tawos_holdout_eval.py evaluates exactly once."""
    _, labels, raw_rows = _extract_dataset()
    scaled, means, stds = _standardize(raw_rows)
    w = fit_logistic(scaled, labels)
    return {"features": FEATURES, "weights": w, "means": means, "stds": stds}


def main():
    print(f"features: {FEATURES}\n")
    results = cross_validate()
    for i, r in enumerate(results):
        print(f"fold {i}: n={r['n']} P={r['precision']:.3f} R={r['recall']:.3f} "
              f"F1={r['f1']:.3f} Acc={r['accuracy']:.3f} AUC={r['auc']:.3f}")
        print(f"        weights (bias, {', '.join(FEATURES)}): {r['weights']}")

    mean_f1 = statistics.mean(r["f1"] for r in results)
    mean_auc = statistics.mean(r["auc"] for r in results)
    mean_prec = statistics.mean(r["precision"] for r in results)
    mean_rec = statistics.mean(r["recall"] for r in results)
    print(f"\ncross-validated mean: P={mean_prec:.3f} R={mean_rec:.3f} F1={mean_f1:.3f} AUC={mean_auc:.3f}")
    print("(compare against the single-feature overdue_ratio baseline: F1=0.793)")

    import json
    from pathlib import Path
    final = fit_final_model()
    out = Path(__file__).parent / "tawos_composite_model.json"
    out.write_text(json.dumps(final, indent=2))
    print(f"\nfinal model (fit on full tuning set) saved to {out.name}")
    print(f"weights: {[round(x,3) for x in final['weights']]}")


if __name__ == "__main__":
    main()
