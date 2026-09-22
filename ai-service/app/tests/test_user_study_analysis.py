"""The user study's statistics (eval/user_study_analysis.py), on hand-checked cases."""

import pytest

from eval.user_study_analysis import analyse, mcnemar_exact, sus_score, wilcoxon_exact

pytestmark = pytest.mark.mvp


def test_sus_scoring_matches_brookes_rule():
    assert sus_score([3] * 10) == 50.0
    assert sus_score([5, 1] * 5) == 100.0
    assert sus_score([1, 5] * 5) == 0.0
    with pytest.raises(ValueError):
        sus_score([3] * 9)


def test_wilcoxon_exact_small_samples():
    # Six positive differences: the most extreme of 2^6 sign patterns, two-sided p = 2/64.
    assert wilcoxon_exact([1, 2, 3, 4, 5, 6])["p_value"] == pytest.approx(0.0312, abs=1e-4)
    assert wilcoxon_exact([1, 2, 3, 4, 5, 6])["rank_biserial_r"] == 1.0
    assert wilcoxon_exact([0, 0])["p_value"] == 1.0  # zeros carry no information


def test_mcnemar_exact():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(6, 0) == pytest.approx(0.0312, abs=1e-4)  # 2 / 2^6


def test_analyse_pairs_each_participant_across_conditions():
    tasks = [
        {"participant": p, "condition": c, "task": t, "correct": ok, "seconds": s}
        for p in ("P01", "P02")
        for c, ok, s in (("evidence", "1", "30"), ("baseline", "0", "90"))
        for t in ("T1", "T2", "T3", "T4")
    ]
    sus = {f"S{i}": ("4" if i % 2 else "2") for i in range(1, 11)}
    result = analyse(tasks, [{**sus, "E1": "5", "preference": "with"}, {**sus, "E1": "3", "preference": "with"}])
    assert result["participants_with_both_conditions"] == 2
    assert result["h1_accuracy"]["evidence_mean_correct"] == 4
    assert result["h1_accuracy"]["baseline_mean_correct"] == 0
    assert result["h2_time"]["median_paired_difference_s"] == -240
    assert result["h3_sus"]["mean"] == 75.0
    assert result["rq4_explanation_items"]["E1"]["agree_share"] == 0.5
    assert result["preference"] == {"with": 2}
