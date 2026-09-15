"""Early warning: can the delay signal predict a sprint's outcome before it ends?

The end-of-sprint evaluation (tawos_score, tawos_holdout_eval) runs after the
deadline, where "any issue unfinished" already implies the label, so recall 1.0
there is structural. This asks the question that matters in a live project:
part-way through a sprint, knowing only what had happened by then, does the pace
signal (app.graph.metrics.pace_projections) flag the sprints that will end delayed?

Pre-declared before any result was seen; nothing here is tuned:
- checkpoints: 50% and 75% of each sprint's start -> end window
- prediction: GraphMetrics(now=checkpoint).risk_scores["delay"] != "low" (primary)
  and in {"high", "critical"} (secondary)
- ranking score for AUC: projected unfinished share at the deadline
- scope at a checkpoint: issues created by then; done = resolved by then
- label: unchanged (>= 30% of the sprint's issues unresolved at sprint end)

Baselines: flag every sprint; the share of issues still open at the checkpoint
(AUC only). Paired tests on the held-out split: exact McNemar, and a cluster
bootstrap by project of the F1 difference. The end-of-sprint rule is also compared,
paired, with the tuned composite model and with flagging every sprint.

Run: python -m eval.datasets.tawos_midsprint_eval
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from datetime import timedelta
from math import comb
from pathlib import Path

from app.graph import GraphBuilder, GraphMetrics
from app.graph.metrics import pace_projections
from eval.datasets.tawos_composite import predict_proba
from eval.datasets.tawos_features import extract_features
from eval.datasets.tawos_ingest import build_sprint_cases, connect
from eval.datasets.tawos_score import _auc, _confusion, _parse_dt
from eval.datasets.tawos_split import load_split

CHECKPOINTS = (0.5, 0.75)
N_BOOTSTRAP = 2000
SEED = 20260915
MODEL_PATH = Path(__file__).parent / "tawos_composite_model.json"
OUT_PATH = Path(__file__).parent / "tawos_midsprint_result.json"


def _rates(pairs: list[tuple[bool, bool]]) -> dict:
    m = _confusion(pairs)
    negatives = m["fp"] + m["tn"]
    m["specificity"] = round(m["tn"] / negatives, 4) if negatives else 1.0
    m["flag_rate"] = round((m["tp"] + m["fp"]) / m["n"], 4) if m["n"] else 0.0
    return m


def mcnemar_exact(labels: list[bool], a: list[bool], b: list[bool]) -> dict:
    """Two-sided exact McNemar test on which of two paired predictors is right."""
    a_only = sum(1 for y, pa, pb in zip(labels, a, b) if pa == y and pb != y)
    b_only = sum(1 for y, pa, pb in zip(labels, a, b) if pb == y and pa != y)
    n = a_only + b_only
    if n == 0:
        return {"a_right_b_wrong": 0, "b_right_a_wrong": 0, "p_value": 1.0}
    tail = sum(comb(n, i) for i in range(min(a_only, b_only) + 1))
    return {"a_right_b_wrong": a_only, "b_right_a_wrong": b_only,
            "p_value": round(min(1.0, 2 * tail / 2 ** n), 6)}


def paired_bootstrap_f1(rows: list[dict], a: str, b: str, rng: random.Random) -> dict:
    """Resample projects with replacement (sprints within a project are correlated)
    and recompute the F1 difference a - b on the same resampled sprints."""
    by_project: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_project[r["project"]].append(r)
    projects = sorted(by_project)

    def f1(sample: list[dict], key: str) -> float:
        return _confusion([(r["label"], r[key]) for r in sample])["f1"]

    diffs = []
    for _ in range(N_BOOTSTRAP):
        sample = [r for p in (rng.choice(projects) for _ in projects) for r in by_project[p]]
        diffs.append(f1(sample, a) - f1(sample, b))
    diffs.sort()
    return {
        "f1_difference": round(f1(rows, a) - f1(rows, b), 4),
        "ci_95": [round(diffs[int(0.025 * N_BOOTSTRAP)], 4), round(diffs[int(0.975 * N_BOOTSTRAP) - 1], 4)],
        "share_of_resamples_a_better": round(sum(d > 0 for d in diffs) / N_BOOTSTRAP, 4),
    }


def paired(rows: list[dict], a: str, b: str, rng: random.Random) -> dict:
    labels = [r["label"] for r in rows]
    return {
        "mcnemar": mcnemar_exact(labels, [r[a] for r in rows], [r[b] for r in rows]),
        "bootstrap": paired_bootstrap_f1(rows, a, b, rng),
    }


def checkpoint_rows(conn, checkpoint: float, holdout: set[str]) -> list[dict]:
    rows = []
    for case in build_sprint_cases(conn, checkpoint=checkpoint):
        graph = GraphBuilder().build(case.snapshot)
        now = _parse_dt(case.as_of)
        delay = GraphMetrics(now=now).compute(graph).risk_scores.get("delay", "low")
        paces = pace_projections(graph, now)
        tasks = case.snapshot.tasks
        rows.append({
            "project": case.project_key,
            "holdout": case.project_key in holdout,
            "label": case.label_delayed,
            "rule": delay != "low",
            "rule_high": delay in ("high", "critical"),
            "flag_all": True,
            "projected_unfinished": paces[0].projected_unfinished if paces else 0.0,
            "open_share": sum(1 for t in tasks if t.status != "done") / len(tasks) if tasks else 0.0,
            "in_scope": len(tasks),
        })
    return rows


def summarize(rows: list[dict]) -> dict:
    labels = [r["label"] for r in rows]
    return {
        "n_sprints": len(rows),
        "n_projects": len({r["project"] for r in rows}),
        "positive_rate": round(sum(labels) / len(rows), 4),
        "sprints_with_nothing_in_scope_yet": sum(1 for r in rows if r["in_scope"] == 0),
        "pace_rule": _rates([(r["label"], r["rule"]) for r in rows]),
        "pace_rule_high_or_worse": _rates([(r["label"], r["rule_high"]) for r in rows]),
        "flag_every_sprint": _rates([(r["label"], True) for r in rows]),
        "auc_projected_unfinished": round(_auc(labels, [r["projected_unfinished"] for r in rows]), 4),
        "auc_open_share_baseline": round(_auc(labels, [r["open_share"] for r in rows]), 4),
    }


def end_of_sprint_rows(conn, holdout: set[str], model: dict) -> list[dict]:
    rows = []
    for case in build_sprint_cases(conn):
        if case.project_key not in holdout:
            continue
        graph = GraphBuilder().build(case.snapshot)
        analysis = GraphMetrics(now=_parse_dt(case.sprint_end) + timedelta(days=1)).compute(graph)
        feats = extract_features(analysis)
        scaled = [(feats[k] - model["means"][j]) / model["stds"][j] for j, k in enumerate(model["features"])]
        rows.append({
            "project": case.project_key,
            "label": case.label_delayed,
            "rule": analysis.risk_scores.get("delay", "low") != "low",
            "composite": predict_proba(model["weights"], scaled) >= 0.5,
            "flag_all": True,
        })
    return rows


def _line(name: str, m: dict) -> str:
    return (f"  {name:26} P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} "
            f"acc={m['accuracy']:.3f} spec={m['specificity']:.3f} flags={m['flag_rate']:.1%}")


def main():
    split = load_split()
    holdout = set(split["holdout_projects"])
    model = json.loads(MODEL_PATH.read_text())
    conn = connect()
    rng = random.Random(SEED)
    result: dict = {
        "pre_registered": {
            "checkpoints": list(CHECKPOINTS),
            "primary_prediction": "delay risk != low at the checkpoint",
            "secondary_prediction": "delay risk high or critical at the checkpoint",
            "auc_score": "projected unfinished share at the deadline",
            "pace_min_elapsed": 0.25,
            "severity_cutoffs": "OVERDUE_RATIO_* (0.10 / 0.25 / 0.40), reused unchanged",
        },
        "checkpoints": {},
    }

    for checkpoint in CHECKPOINTS:
        rows = checkpoint_rows(conn, checkpoint, holdout)
        held = [r for r in rows if r["holdout"]]
        label = f"{int(checkpoint * 100)}%"
        result["checkpoints"][label] = {
            "all": summarize(rows),
            "tuning": summarize([r for r in rows if not r["holdout"]]),
            "holdout": summarize(held),
            "holdout_paired_pace_rule_vs_flag_every_sprint": paired(held, "rule", "flag_all", rng),
        }
        h = result["checkpoints"][label]["holdout"]
        p = result["checkpoints"][label]["holdout_paired_pace_rule_vs_flag_every_sprint"]
        print(f"\n=== checkpoint {label} — held-out ({h['n_sprints']} sprints, {h['n_projects']} projects)")
        print(_line("pace rule (risk != low)", h["pace_rule"]))
        print(_line("pace rule (high+)", h["pace_rule_high_or_worse"]))
        print(_line("flag every sprint", h["flag_every_sprint"]))
        print(f"  AUC projected_unfinished={h['auc_projected_unfinished']:.3f}  "
              f"open-share baseline={h['auc_open_share_baseline']:.3f}")
        print(f"  paired vs flag-every-sprint: McNemar p={p['mcnemar']['p_value']}  "
              f"F1 diff={p['bootstrap']['f1_difference']} CI {p['bootstrap']['ci_95']}")

    end_rows = end_of_sprint_rows(conn, holdout, model)
    result["end_of_sprint_holdout"] = {
        "rule": _rates([(r["label"], r["rule"]) for r in end_rows]),
        "composite": _rates([(r["label"], r["composite"]) for r in end_rows]),
        "flag_every_sprint": _rates([(r["label"], True) for r in end_rows]),
        "paired_rule_vs_composite": paired(end_rows, "rule", "composite", rng),
        "paired_rule_vs_flag_every_sprint": paired(end_rows, "rule", "flag_all", rng),
    }
    e = result["end_of_sprint_holdout"]
    print(f"\n=== end of sprint — held-out ({len(end_rows)} sprints)")
    for name in ("rule", "composite", "flag_every_sprint"):
        print(_line(name, e[name]))
    for name in ("paired_rule_vs_composite", "paired_rule_vs_flag_every_sprint"):
        print(f"  {name}: McNemar p={e[name]['mcnemar']['p_value']}  "
              f"F1 diff={e[name]['bootstrap']['f1_difference']} CI {e[name]['bootstrap']['ci_95']}")

    OUT_PATH.write_text(json.dumps(result, indent=2))
    print(f"\nwrote {OUT_PATH.name}")


if __name__ == "__main__":
    main()
