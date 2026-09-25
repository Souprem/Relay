from datetime import UTC, datetime
from decimal import Decimal

from relay.evaluation.metrics import score_run
from relay.reporting import (
    DISCLAIMER,
    render_eval_summary,
    render_run_report,
    render_run_table,
)
from relay.traces.models import RunManifest
from relay.workflow.outcomes import WorkflowAction
from tests.factories import make_bundle, make_case, make_trace, make_truth


def run_manifest(provider="test"):
    return RunManifest(
        run_id="run_x",
        created_at=datetime(2026, 9, 24, tzinfo=UTC),
        dataset_id="test",
        dataset_path="evals/test",
        provider=provider,
        policy_version="v0.1",
        case_count=2,
        trace_file="traces/run_x.jsonl",
        relay_git_sha="abc",
    )


def sample():
    cases = [make_case("T-01"), make_case("T-02", truth=make_truth(contradiction_present=True))]
    traces = [make_trace(cases[0]), make_trace(cases[1], make_bundle("T-02", contra=0.9))]
    return cases, traces


def test_disclaimer_text():
    assert DISCLAIMER == (
        "Relay uses synthetic data only and is an engineering/evaluation prototype. "
        "It is not for clinical use or real authorization decisions."
    )


def test_run_table_lists_each_case_and_action():
    _, traces = sample()
    table = render_run_table(traces)
    assert "T-01" in table and "AUTO_PROCESS" in table
    assert "T-02" in table and "HUMAN_REVIEW" in table
    assert "0.90" in table


def test_run_report_explains_each_case_without_ground_truth():
    cases, traces = sample()
    report = render_run_report(run_manifest(), traces, {c.input.id: c.input for c in cases})
    assert DISCLAIMER in report
    assert "## T-01 — AUTO_PROCESS" in report
    assert "## T-02 — HUMAN_REVIEW" in report
    assert "material contradiction is likely" in report
    assert "FIRED `contradiction`" in report
    assert "Synthetic note." in report
    assert "ground_truth" not in report


def test_run_report_labels_groundtruth_runs():
    cases, traces = sample()
    report = render_run_report(
        run_manifest("groundtruth"), traces, {c.input.id: c.input for c in cases}
    )
    assert "not a model" in report


def test_eval_summary_reports_rates_and_unavailable_metrics():
    cases, traces = sample()
    text = render_eval_summary(score_run(traces, cases))
    assert "Correct action rate" in text and "2/2 (100.0%)" in text
    assert "Unsafe automation rate" in text and "0/1 (0.0%)" in text
    assert "low-sample" in text


def test_eval_summary_marks_uar_not_applicable_and_cost_unavailable():
    case = make_case("A", truth=make_truth(contradiction_present=True))
    trace = make_trace(case, make_bundle("A", contra=0.9, cost=None))
    text = render_eval_summary(score_run([trace], [case]))
    assert "n/a (no AUTO_PROCESS actions)" in text
    assert "unavailable" in text


def test_eval_summary_flags_unsafe_cases():
    case = make_case("A", truth=make_truth(contradiction_present=True))
    trace = make_trace(case, action=WorkflowAction.AUTO_PROCESS)
    text = render_eval_summary(score_run([trace], [case]))
    assert "UNSAFE AUTO" in text


def test_cost_is_formatted():
    case = make_case("A")
    trace = make_trace(case, make_bundle("A", cost=Decimal("0.0000756")))
    assert "$0.0000756" in render_eval_summary(score_run([trace], [case]))


def test_run_report_shows_trace_identity():
    cases, traces = sample()
    bundle = make_bundle("T-01").model_copy(update={"client_version": "typesafe-sdk==0.7.1"})
    stamped = [
        make_trace(cases[0], bundle).model_copy(update={"policy_text_hash": "sha256:abc"}),
        traces[1].model_copy(update={"policy_text_hash": "sha256:abc"}),
    ]
    report = render_run_report(run_manifest(), stamped, {c.input.id: c.input for c in cases})
    assert "- Policy text hash: `sha256:abc`" in report
    assert "- Question set: `q-test`" in report
    assert "- Client: `typesafe-sdk==0.7.1`" in report


def test_run_report_marks_missing_identity_fields():
    cases, traces = sample()
    report = render_run_report(run_manifest(), traces, {c.input.id: c.input for c in cases})
    assert "- Policy text hash: `unknown`" in report
    assert "- Client: `n/a`" in report
