import pytest

from relay.evaluation.compare import compare_runs
from relay.evaluation.metrics import EvalError
from relay.reporting import render_comparison
from relay.workflow.outcomes import WorkflowAction
from tests.factories import make_bundle, make_case, make_trace, make_truth

AUTO = WorkflowAction.AUTO_PROCESS
REVIEW = WorkflowAction.HUMAN_REVIEW


def dataset():
    return [
        make_case("V"),  # expected AUTO
        make_case("W"),  # expected AUTO
        make_case("X", truth=make_truth(contradiction_present=True)),  # expected REVIEW
    ]


def baseline(cases, run_id="run_a"):
    """V auto, W auto, X review (contradiction caught): all correct."""
    bundles = [make_bundle("V"), make_bundle("W"), make_bundle("X", contra=0.9)]
    return [make_trace(c, b, run_id=run_id) for c, b in zip(cases, bundles, strict=True)]


def worse(cases, run_id="run_b"):
    """V auto; W review (missed automation); X auto (contradiction missed: unsafe)."""
    bundles = [make_bundle("V"), make_bundle("W", diag=0.9), make_bundle("X")]
    return [make_trace(c, b, run_id=run_id) for c, b in zip(cases, bundles, strict=True)]


def test_identical_runs_have_no_diffs():
    cases = dataset()
    result = compare_runs([("a", baseline(cases)), ("b", baseline(cases, "run_b"))], cases)
    assert [(p.a, p.b) for p in result.pairs] == [("a", "b")]
    assert result.pairs[0].diffs == []
    assert result.dataset_id == "test" and result.n_cases == 3
    assert "No action differences between a and b." in render_comparison(result)


def test_new_unsafe_automation_is_listed_first():
    cases = dataset()
    result = compare_runs([("jev", baseline(cases)), ("rules", worse(cases))], cases)
    [pair] = result.pairs
    assert [d.case_id for d in pair.diffs] == ["X", "W"]  # X is unsafe, so it beats W's id order
    x, w = pair.diffs
    assert (x.expected, x.action_a, x.action_b) == (REVIEW, REVIEW, AUTO)
    assert x.new_unsafe and not x.resolved_unsafe
    assert (w.action_a, w.action_b, w.new_unsafe) == (AUTO, REVIEW, False)
    reverse = compare_runs([("rules", worse(cases)), ("jev", baseline(cases))], cases)
    assert reverse.pairs[0].diffs[0].resolved_unsafe


def test_columns_carry_metrics_calibration_and_frontier_points():
    cases = dataset()
    result = compare_runs([("jev", baseline(cases)), ("rules", worse(cases))], cases, at=0.95)
    jev, rules = result.runs
    assert jev.summary.correct_actions == 3 and rules.summary.unsafe_automation_count == 1
    assert set(jev.calibration.decisions) == {
        "diagnosis_support",
        "step_therapy",
        "documentation_complete",
        "material_contradiction",
        "missing_evidence",
    }
    assert jev.sweep.at_point.auto_threshold == 0.95
    assert jev.sweep.selected is not None  # V and W automate safely up to 0.99
    # rules: X (p 0.99) automates at every threshold, so UAR never reaches the ceiling
    assert rules.sweep.selected is None
    text = render_comparison(result)
    assert "Correct action rate" in text and "3/3 (100.0%)" in text
    assert "Brier / ECE material_contradiction" in text
    assert "At 0.95" in text
    assert "Action differences jev -> rules: 2 cases (1 new unsafe automations)" in text
    assert "NEW UNSAFE AUTO" in text
    assert text.index("  X ") < text.index("  W ")
    assert "at auto_process >= 0.95 (--at)" in text  # C3: always states which threshold is used


def test_render_comparison_states_the_at_threshold_used_for_diffs():
    cases = dataset()
    result = compare_runs([("jev", baseline(cases)), ("rules", worse(cases))], cases, at=0.9)
    text = render_comparison(result)
    assert "at auto_process >= 0.9 (--at)" in text


def test_three_runs_give_every_pair_in_order():
    cases = dataset()
    runs = [("a", baseline(cases)), ("b", worse(cases)), ("c", baseline(cases, "run_c"))]
    result = compare_runs(runs, cases)
    assert [(p.a, p.b) for p in result.pairs] == [("a", "b"), ("a", "c"), ("b", "c")]


def test_coverage_mismatch_is_an_error_naming_the_run():
    cases = dataset()
    with pytest.raises(EvalError, match="rules.*X"):
        compare_runs([("jev", baseline(cases)), ("rules", worse(cases)[:2])], cases)


def test_case_hash_mismatch_is_an_error():
    cases = dataset()
    stale = [t.model_copy(update={"case_content_hash": "sha256:old"}) for t in worse(cases)]
    with pytest.raises(EvalError, match="hash"):
        compare_runs([("jev", baseline(cases)), ("rules", stale)], cases)


def test_diffs_use_each_runs_own_thresholds_by_default():
    """C3: with no --at, diffs come from each run's own stored (v0.1, auto_process=0.95) action."""
    case = make_case("V")  # expected AUTO
    a = [make_trace(case, make_bundle("V", diag=0.90), run_id="run_a")]  # below 0.95: not auto
    b = [make_trace(case, make_bundle("V", diag=0.99), run_id="run_b")]  # at/above 0.95: auto
    result = compare_runs([("a", a), ("b", b)], [case])
    [pair] = result.pairs
    assert len(pair.diffs) == 1
    assert pair.diffs[0].action_b == AUTO and pair.diffs[0].action_a != AUTO
    assert "own thresholds" in result.threshold_note


def test_at_threshold_recomputes_diffs_on_stored_bundles():
    """C3: --at re-runs determine_action on both runs' stored bundles at that auto_process."""
    case = make_case("V")  # expected AUTO
    a = [make_trace(case, make_bundle("V", diag=0.90), run_id="run_a")]
    b = [make_trace(case, make_bundle("V", diag=0.99), run_id="run_b")]
    # At their own thresholds (0.95) this is a diff (see test above); at 0.85 both clear the bar.
    result = compare_runs([("a", a), ("b", b)], [case], at=0.85)
    [pair] = result.pairs
    assert pair.diffs == []
    assert "0.85" in result.threshold_note and "--at" in result.threshold_note
    # 0.95 (--at) matches both runs' own default threshold, so it reproduces the same diff.
    at_own = compare_runs([("a", a), ("b", b)], [case], at=0.95)
    assert len(at_own.pairs[0].diffs) == 1


def test_needs_two_runs_with_distinct_labels():
    cases = dataset()
    with pytest.raises(EvalError, match="at least two"):
        compare_runs([("jev", baseline(cases))], cases)
    with pytest.raises(EvalError, match="duplicate"):
        compare_runs([("x", baseline(cases)), ("x", worse(cases))], cases)
