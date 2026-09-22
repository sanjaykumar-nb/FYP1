"""Analyse the Phase 1 user study (docs/user-study/PROTOCOL.md, section 8).

Reads the two result sheets and reports, evidence vs baseline:
- H1 accuracy: tasks correct per participant, exact Wilcoxon signed-rank; per task, exact McNemar
- H2 time: total seconds on T1-T4 per participant, the same test, plus the median paired
  difference with a bootstrap 95% interval
- H3 usability: SUS mean with a 95% interval, against the benchmark of 68
- RQ4: share agreeing (4 or 5) with each explanation item, and T5 answers

Effect sizes are matched-pairs rank-biserial r. Standard library only.

Run:
    python -m eval.user_study_analysis ../docs/user-study/results_tasks.csv ../docs/user-study/results_questionnaires.csv
Writes eval/user_study_result.json.
"""

from __future__ import annotations

import csv
import itertools
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(__file__).parent / "user_study_result.json"
SUS_BENCHMARK = 68.0
SCORED_TASKS = ("T1", "T2", "T3", "T4")
EXPLANATION_ITEMS = [f"E{i}" for i in range(1, 8)]


def sus_score(answers: list[int]) -> float:
    """Brooke's scoring: odd items score (answer - 1), even items (5 - answer); the sum x 2.5."""
    if len(answers) != 10 or any(not 1 <= a <= 5 for a in answers):
        raise ValueError("SUS needs ten answers from 1 to 5")
    return 2.5 * sum((a - 1) if i % 2 == 0 else (5 - a) for i, a in enumerate(answers))


def wilcoxon_exact(differences: list[float]) -> dict:
    """Two-sided exact Wilcoxon signed-rank test (zeros dropped, ties given average ranks)."""
    d = [x for x in differences if x != 0]
    n = len(d)
    if n == 0:
        return {"n": 0, "w_plus": 0.0, "p_value": 1.0, "rank_biserial_r": 0.0}
    order = sorted(range(n), key=lambda i: abs(d[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(d[order[j + 1]]) == abs(d[order[i]]):
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    w_plus = sum(r for r, x in zip(ranks, d) if x > 0)
    total = n * (n + 1) / 2
    observed = min(w_plus, total - w_plus)
    # Every assignment of signs to the ranks is equally likely under the null.
    extreme = sum(1 for signs in itertools.product((0, 1), repeat=n)
                  if min(s := sum(r for r, b in zip(ranks, signs) if b), total - s) <= observed + 1e-9)
    return {"n": n, "w_plus": w_plus, "p_value": round(min(1.0, extreme / 2 ** n), 4),
            "rank_biserial_r": round((w_plus - (total - w_plus)) / total, 3)}


def mcnemar_exact(evidence_only: int, baseline_only: int) -> float:
    """Two-sided exact McNemar p-value from the discordant pairs."""
    n = evidence_only + baseline_only
    if n == 0:
        return 1.0
    k = min(evidence_only, baseline_only)
    return round(min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n), 4)


def bootstrap_median_ci(values: list[float], draws: int = 5000, seed: int = 7) -> list[float]:
    rng = random.Random(seed)
    medians = sorted(statistics.median(rng.choices(values, k=len(values))) for _ in range(draws))
    return [round(medians[int(0.025 * draws)], 1), round(medians[int(0.975 * draws) - 1], 1)]


def t_interval(values: list[float]) -> list[float]:
    """95% interval for a mean (t distribution; critical values for small samples)."""
    t95 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23,
           11: 2.20, 12: 2.18, 13: 2.16, 14: 2.14, 15: 2.13, 19: 2.09, 24: 2.06, 29: 2.05}
    n = len(values)
    if n < 2:
        return [values[0], values[0]] if values else []
    df = n - 1
    t = t95.get(df) or t95[max(k for k in t95 if k <= df)]
    half = t * statistics.stdev(values) / math.sqrt(n)
    mean = statistics.mean(values)
    return [round(mean - half, 1), round(mean + half, 1)]


def analyse(task_rows: list[dict], questionnaire_rows: list[dict]) -> dict:
    per: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(dict))
    for r in task_rows:
        if r["task"] in SCORED_TASKS and r.get("correct") not in ("", None):
            per[r["participant"]][r["condition"]][r["task"]] = r
    both = [p for p, c in per.items() if "evidence" in c and "baseline" in c]

    def score(p: str, cond: str) -> int:
        return sum(int(r["correct"]) for r in per[p][cond].values())

    def seconds(p: str, cond: str) -> float:
        return sum(float(r["seconds"]) for r in per[p][cond].values())

    acc = {c: [score(p, c) for p in both] for c in ("evidence", "baseline")}
    secs = {c: [seconds(p, c) for p in both] for c in ("evidence", "baseline")}
    time_diff = [e - b for e, b in zip(secs["evidence"], secs["baseline"])]
    by_task = {}
    for task in SCORED_TASKS:
        pairs = [(int(per[p]["evidence"][task]["correct"]), int(per[p]["baseline"][task]["correct"]))
                 for p in both if task in per[p]["evidence"] and task in per[p]["baseline"]]
        if pairs:
            by_task[task] = {"n": len(pairs), "evidence_correct": sum(e for e, _ in pairs),
                             "baseline_correct": sum(b for _, b in pairs),
                             "mcnemar_p": mcnemar_exact(sum(e > b for e, b in pairs), sum(b > e for e, b in pairs))}

    sus = [sus_score([int(q[f"S{i}"]) for i in range(1, 11)]) for q in questionnaire_rows if q.get("S1")]
    explanation = {}
    for item in EXPLANATION_ITEMS:
        answers = [int(q[item]) for q in questionnaire_rows if q.get(item)]
        if answers:
            explanation[item] = {"n": len(answers), "median": statistics.median(answers),
                                 "agree_share": round(sum(a >= 4 for a in answers) / len(answers), 3)}
    count = lambda key: dict(sorted(Counter(q[key] for q in questionnaire_rows if q.get(key)).items()))  # noqa: E731

    return {
        "participants_with_both_conditions": len(both),
        "h1_accuracy": {"evidence_mean_correct": round(statistics.mean(acc["evidence"]), 2) if both else None,
                        "baseline_mean_correct": round(statistics.mean(acc["baseline"]), 2) if both else None,
                        "wilcoxon": wilcoxon_exact([e - b for e, b in zip(acc["evidence"], acc["baseline"])]),
                        "by_task": by_task},
        "h2_time": {"evidence_median_s": statistics.median(secs["evidence"]) if both else None,
                    "baseline_median_s": statistics.median(secs["baseline"]) if both else None,
                    "median_paired_difference_s": statistics.median(time_diff) if both else None,
                    "difference_ci95": bootstrap_median_ci(time_diff) if both else None,
                    "wilcoxon": wilcoxon_exact(time_diff)},
        "h3_sus": {"n": len(sus), "mean": round(statistics.mean(sus), 1) if sus else None,
                   "ci95": t_interval(sus) if sus else None, "benchmark": SUS_BENCHMARK},
        "rq4_explanation_items": explanation,
        "preference": count("preference"),
        "t5_apply": count("t5_apply"),
    }


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    read = lambda p: list(csv.DictReader(open(p, newline="", encoding="utf-8")))  # noqa: E731
    result = analyse(read(sys.argv[1]), read(sys.argv[2]))
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
