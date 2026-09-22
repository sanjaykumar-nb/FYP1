"""The published synthetic evaluation must keep reproducing, on every push.

These evaluations were only run by hand. Judged against the wall clock, the
synthetic scenarios' due dates drifted into the past as the calendar moved on,
and detection silently fell from F1 1.00 to 0.92 a month after publication.
Running them here pins both the clock and the result.
"""

import pytest

from eval.boundary_eval import find_transition, sweep_overdue_ratio, sweep_silent_ratio, sweep_workload_skew
from eval.run_eval import run_detection_eval

pytestmark = pytest.mark.mvp


def test_synthetic_detection_reproduces_the_published_result():
    report = run_detection_eval()
    overall = report["overall"]
    assert (overall["tp"], overall["fp"], overall["fn"], overall["tn"]) == (90, 0, 0, 90)
    assert all(counts["f1"] == 1.0 for counts in report["per_risk_type"].values())


def test_each_detector_changes_verdict_exactly_at_its_documented_threshold():
    assert find_transition(sweep_overdue_ratio(), "ratio") == (0.08, 0.1)       # threshold 0.10
    assert find_transition(sweep_silent_ratio(), "ratio") == (0.2, 0.3)          # threshold 0.30
    skew = sweep_workload_skew()
    below, above = find_transition(skew, "measured_skew")                       # threshold 1.50
    assert below < 1.5 <= above
