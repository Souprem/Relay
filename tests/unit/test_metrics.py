from decimal import Decimal

import pytest

from relay.cases.models import MissingEvidence
from relay.evaluation.metrics import EvalError, EvalSummary, percentile, score_run
from relay.workflow.outcomes import WorkflowAction
from tests.factories import make_bundle, make_case, make_trace, make_truth

AUTO = WorkflowAction.AUTO_PROCESS
REVIEW = WorkflowAction.HUMAN_REVIEW
INFO = WorkflowAction.REQUEST_INFO
INCOMPLETE = make_truth(
    documentation_complete=False, missing_evidence=MissingEvidence.TREATMENT_HISTORY
)


def test_percentile_nearest_rank():
    values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert percentile(values, 50) == 50
    assert percentile(values, 95) == 100
    assert percentile([7], 95) == 7
    assert percentile([], 50) is None


def test_unsafe_automation_rate_counts_autos_that_should_not_be_automated():
    cases = [
        make_case("A"),  # expected AUTO
        make_case("B"),  # expected AUTO
        make_case("C", truth=make_truth(contradiction_present=True)),  # expected REVIEW
        make_case("D", truth=INCOMPLETE),  # expected REQUEST_INFO
        make_case("E"),  # expected AUTO
    ]
    traces = [
        make_trace(cases[0], action=AUTO),
        make_trace(cases[1], action=AUTO),
        make_trace(cases[2], action=AUTO),  # unsafe
        make_trace(cases[3], action=AUTO),  # unsafe
        make_trace(cases[4], action=REVIEW),  # safe but unnecessary escalation
    ]
    summary = score_run(traces, cases)
    assert summary.n_cases == 5
    assert summary.auto_process_count == 4
    assert summary.unsafe_automation_count == 2
    assert summary.unsafe_automation_rate == pytest.approx(0.5)
    assert summary.automation_rate == pytest.approx(0.8)
    assert summary.correct_actions == 2
    assert summary.correct_action_rate == pytest.approx(0.4)
    assert summary.human_escalation_rate == pytest.approx(0.2)
    assert [c.unsafe_automation for c in summary.cases] == [False, False, True, True, False]


def test_unsafe_automation_rate_unavailable_without_autos():
    case = make_case("A", truth=make_truth(contradiction_present=True))
    summary = score_run([make_trace(case, action=REVIEW)], [case])
    assert summary.auto_process_count == 0
    assert summary.unsafe_automation_rate is None


def test_per_question_accuracy_uses_half_threshold_and_top_choice():
    case = make_case("A", truth=make_truth(step_therapy_satisfied=False))
    bundle = make_bundle("A", step=0.4, contra=0.6, missing="NONE")
    summary = score_run([make_trace(case, bundle)], [case])
    acc = summary.per_question_accuracy
    assert acc["step_therapy"] == 1.0  # 0.4 < 0.5 -> NO, truth NO
    assert acc["material_contradiction"] == 0.0  # 0.6 -> YES, truth NO
    assert acc["missing_evidence"] == 1.0
    assert acc["diagnosis_support"] == 1.0


def test_invalid_outputs_are_counted_and_excluded_from_question_accuracy():
    case = make_case("A")
    summary = score_run([make_trace(case, make_bundle("A", error="boom"))], [case])
    assert summary.invalid_outputs == 1
    assert summary.cases[0].invalid_output is True
    assert summary.per_question_accuracy["diagnosis_support"] is None


def test_latency_and_cost():
    cases = [make_case(f"T-{i}") for i in range(3)]
    traces = [
        make_trace(c, make_bundle(c.input.id, latency_ms=ms, cost=Decimal("0.0001")))
        for c, ms in zip(cases, [100, 300, 200], strict=True)
    ]
    summary = score_run(traces, cases)
    assert (summary.latency_p50_ms, summary.latency_p95_ms) == (200, 300)
    assert summary.latency_low_sample is True
    assert summary.total_cost_usd == Decimal("0.0003")
    assert summary.cost_per_case_usd == Decimal("0.0001")


def test_cost_unavailable_when_any_case_lacks_cost():
    cases = [make_case("A"), make_case("B")]
    traces = [make_trace(cases[0]), make_trace(cases[1], make_bundle("B", cost=None))]
    summary = score_run(traces, cases)
    assert summary.total_cost_usd is None and summary.cost_per_case_usd is None


def test_hash_mismatch_is_an_error():
    case = make_case("A")
    trace = make_trace(case).model_copy(update={"case_content_hash": "sha256:stale"})
    with pytest.raises(EvalError, match="hash"):
        score_run([trace], [case])


def test_unknown_case_is_an_error():
    with pytest.raises(EvalError, match="Z"):
        score_run([make_trace(make_case("Z"))], [make_case("A")])


def test_empty_traces_is_an_error():
    with pytest.raises(EvalError):
        score_run([], [make_case("A")])


def test_multiple_runs_is_an_error():
    case = make_case("A")
    traces = [make_trace(case, run_id="run_one"), make_trace(case, run_id="run_two")]
    with pytest.raises(EvalError, match="multiple runs"):
        score_run(traces, [case])


def test_duplicate_case_id_in_traces_is_an_error():
    case = make_case("A")
    trace = make_trace(case)
    with pytest.raises(EvalError, match="A"):
        score_run([trace, trace], [case])


def test_cases_are_ordered_by_case_id_regardless_of_trace_order():
    cases = [make_case("B"), make_case("C"), make_case("A")]
    traces = [make_trace(cases[0]), make_trace(cases[1]), make_trace(cases[2])]
    summary = score_run(traces, cases)
    assert [c.case_id for c in summary.cases] == ["A", "B", "C"]


def test_question_set_versions_are_sorted_and_distinct():
    """C4: identity of which question set(s) produced a run's traces, for the results record."""
    cases = [make_case("A"), make_case("B")]
    bundle_b = make_bundle("B").model_copy(update={"question_set_version": "q-v0.2"})
    traces = [make_trace(cases[0]), make_trace(cases[1], bundle_b)]
    summary = score_run(traces, cases)
    assert summary.question_set_versions == ["q-test", "q-v0.2"]


def test_question_set_versions_defaults_to_empty_list_for_old_results_json():
    """A pre-C4 results.json has no question_set_versions key; it must still validate."""
    old = score_run([make_trace(make_case("A"))], [make_case("A")]).model_dump(mode="json")
    del old["question_set_versions"]
    summary = EvalSummary.model_validate(old)
    assert summary.question_set_versions == []


def test_incomplete_trace_coverage_is_an_error():
    cases = [make_case("A"), make_case("B"), make_case("C")]
    traces = [make_trace(cases[0])]
    with pytest.raises(EvalError, match="B") as excinfo:
        score_run(traces, cases)
    assert "C" in str(excinfo.value)
