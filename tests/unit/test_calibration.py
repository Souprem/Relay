import pytest

from relay.evaluation.calibration import (
    BINARY_EDGES,
    CHOICE_EDGES,
    MISSING_EVIDENCE_LABELS,
    binary_calibration,
    calibrate_run,
    choice_calibration,
)
from relay.evaluation.metrics import EvalError
from tests.factories import make_bundle, make_case, make_trace, make_truth


def bin_counts(report):
    return [b.n for b in report.bins]


def test_bin_edges():
    assert BINARY_EDGES == (0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
    assert CHOICE_EDGES == (0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
    assert MISSING_EVIDENCE_LABELS == (
        "DIAGNOSIS",
        "TREATMENT_HISTORY",
        "LAB_RESULT",
        "DOSAGE",
        "INSURANCE_INFORMATION",
        "NONE",
    )


def test_binary_calibration_hand_computed():
    # p_yes, truth -> confidence, correct?
    #   0.90, True  -> 0.90, yes==True   correct   bin [0.9,1.0]
    #   0.80, False -> 0.80, yes!=False  wrong     bin [0.8,0.9)
    #   0.30, False -> 0.70, no==False   correct   bin [0.7,0.8)
    #   0.55, True  -> 0.55, yes==True   correct   bin [0.5,0.6)
    report = binary_calibration([(0.9, True), (0.8, False), (0.3, False), (0.55, True)])
    assert report.n == 4
    # Brier = (0.1^2 + 0.8^2 + 0.3^2 + 0.45^2) / 4 = (0.01 + 0.64 + 0.09 + 0.2025) / 4 = 0.235625
    assert report.brier == pytest.approx(0.235625)
    # ECE = sum (1/4)|acc - conf| = (|1-0.55| + |1-0.7| + |0-0.8| + |1-0.9|) / 4
    #     = (0.45 + 0.30 + 0.80 + 0.10) / 4 = 1.65 / 4 = 0.4125
    assert report.ece == pytest.approx(0.4125)
    assert bin_counts(report) == [1, 0, 1, 1, 1]
    first, empty, third, fourth, last = report.bins
    assert (first.lower, first.upper) == (0.5, 0.6)
    assert first.mean_confidence == pytest.approx(0.55) and first.accuracy == 1.0
    assert (empty.n, empty.mean_confidence, empty.accuracy) == (0, None, None)
    assert third.mean_confidence == pytest.approx(0.7) and third.accuracy == 1.0
    assert fourth.mean_confidence == pytest.approx(0.8) and fourth.accuracy == 0.0
    assert (last.lower, last.upper) == (0.9, 1.0)
    assert last.mean_confidence == pytest.approx(0.9) and last.accuracy == 1.0


def test_binary_bin_edges_are_half_open_except_the_last():
    # 0.5 -> first bin; 1.0 (and p_yes 0.0, confidence 1.0) -> last bin;
    # p_yes 0.2 -> confidence 0.8 -> [0.8, 0.9); 0.6 -> [0.6, 0.7), not [0.5, 0.6).
    report = binary_calibration([(0.5, True), (1.0, True), (0.0, False), (0.2, False), (0.6, True)])
    assert bin_counts(report) == [1, 1, 0, 1, 2]


def test_empty_input_gives_none_metrics_and_empty_bins():
    for report in (binary_calibration([]), choice_calibration([], MISSING_EVIDENCE_LABELS)):
        assert report.n == 0
        assert report.brier is None and report.ece is None
        assert all(b.n == 0 and b.accuracy is None for b in report.bins)
    assert len(binary_calibration([]).bins) == 5
    assert len(choice_calibration([], ["A"]).bins) == 6


def test_choice_calibration_hand_computed_with_absent_labels():
    labels = ["A", "B", "C"]
    items = [
        # chosen A (p 0.7), truth A: correct; "C" absent -> 0.
        # sum_k = (0.7-1)^2 + (0.2-0)^2 + (0-0)^2 = 0.09 + 0.04 + 0 = 0.13
        ({"A": 0.7, "B": 0.2}, "A", "A"),
        # chosen B (p 0.4), truth A: wrong.
        # sum_k = (0.35-1)^2 + (0.4-0)^2 + (0.25-0)^2 = 0.4225 + 0.16 + 0.0625 = 0.645
        ({"B": 0.4, "A": 0.35, "C": 0.25}, "B", "A"),
    ]
    report = choice_calibration(items, labels)
    assert report.n == 2
    # Brier = (0.13 + 0.645) / 2 = 0.3875
    assert report.brier == pytest.approx(0.3875)
    # bins: 0.4 -> [0.0,0.5) acc 0; 0.7 -> [0.7,0.8) acc 1
    # ECE = (1/2)|0 - 0.4| + (1/2)|1 - 0.7| = 0.2 + 0.15 = 0.35
    assert report.ece == pytest.approx(0.35)
    assert bin_counts(report) == [1, 0, 0, 1, 0, 0]
    assert (report.bins[0].lower, report.bins[0].upper) == (0.0, 0.5)


def test_choice_confidence_is_zero_when_the_answer_has_no_probability():
    report = choice_calibration([({"B": 1.0}, "A", "A")], ["A", "B"])
    # confidence 0.0 -> [0.0, 0.5); Brier = (0-1)^2 + (1-0)^2 = 2.0
    assert bin_counts(report) == [1, 0, 0, 0, 0, 0]
    assert report.brier == pytest.approx(2.0)


def test_confidence_outside_the_bins_is_an_error():
    with pytest.raises(ValueError):
        choice_calibration([({"A": 1.5}, "A", "A")], ["A"])


def test_calibrate_run_scores_every_decision_and_excludes_invalid_bundles():
    cases = [
        make_case("A"),
        make_case("B", truth=make_truth(step_therapy_satisfied=False)),
        make_case("C"),
    ]
    traces = [
        make_trace(cases[0]),  # diag .99, step .99, docs .99, contra .01, NONE p .9
        make_trace(cases[1], make_bundle("B", diag=0.8, step=0.3)),
        make_trace(cases[2], make_bundle("C", error="provider down")),  # invalid
    ]
    result = calibrate_run(traces, cases)
    assert result.invalid_excluded == 1
    assert list(result.decisions) == [
        "diagnosis_support",
        "step_therapy",
        "documentation_complete",
        "material_contradiction",
        "missing_evidence",
    ]
    diag = result.decisions["diagnosis_support"]
    # Brier = ((0.99-1)^2 + (0.8-1)^2) / 2 = (0.0001 + 0.04) / 2 = 0.02005
    assert diag.n == 2 and diag.brier == pytest.approx(0.02005)
    step = result.decisions["step_therapy"]
    # A: 0.99 vs yes -> 0.0001; B: 0.3 vs no -> 0.09. Brier = 0.0901 / 2 = 0.04505
    assert step.brier == pytest.approx(0.04505)
    assert bin_counts(step) == [0, 0, 1, 0, 1]  # confidences 0.7 and 0.99
    missing = result.decisions["missing_evidence"]
    # both NONE with p 0.9, truth NONE: per case (0.9-1)^2 = 0.01 over 6 labels -> Brier 0.01
    # one bin [0.9,1.0]: acc 1.0, conf 0.9 -> ECE 0.1
    assert missing.n == 2
    assert missing.brier == pytest.approx(0.01)
    assert missing.ece == pytest.approx(0.1)


def test_calibrate_run_validates_coverage():
    with pytest.raises(EvalError, match="B"):
        calibrate_run([make_trace(make_case("A"))], [make_case("A"), make_case("B")])
