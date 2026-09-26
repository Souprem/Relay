"""2B/2C ruling 1: latency is optional. Batch runs and label fixtures record None, never 0."""

from datetime import UTC, datetime

from relay.decisions.base import DecisionBundle
from relay.decisions.ground_truth import bundle_from_truth
from relay.evaluation.calibration import calibrate_run
from relay.evaluation.compare import compare_runs
from relay.evaluation.confusion import confusion_matrices
from relay.evaluation.frontier import run_sweep
from relay.evaluation.metrics import EvalSummary, run_identity, score_run
from relay.reporting import (
    render_comparison,
    render_eval_report,
    render_eval_summary,
    render_run_report,
)
from relay.traces.models import RunManifest
from tests.factories import make_bundle, make_case, make_trace, make_truth

BATCH = {"execution": {"mode": "batch"}}


def run(latencies, derivations=None, run_id="run_l"):
    cases = [make_case(f"T-{i}") for i in range(len(latencies))]
    traces = [
        make_trace(
            c, make_bundle(c.input.id, latency_ms=ms, derivations=derivations), run_id=run_id
        )
        for c, ms in zip(cases, latencies, strict=True)
    ]
    return cases, traces


def test_bundle_latency_defaults_to_none_and_old_json_still_loads():
    old = make_bundle().model_dump(mode="json")
    assert DecisionBundle.model_validate(old).latency_ms == 100
    del old["latency_ms"]
    assert DecisionBundle.model_validate(old).latency_ms is None


def test_groundtruth_bundles_record_no_latency():
    assert bundle_from_truth("T-01", make_truth()).latency_ms is None


def test_percentiles_use_only_recorded_latencies():
    cases, traces = run([100, None, 300])
    summary = score_run(traces, cases)
    assert (summary.latency_p50_ms, summary.latency_p95_ms, summary.latency_n) == (100, 300, 2)
    assert [c.latency_ms for c in summary.cases] == [100, None, 300]
    assert "100 ms / 300 ms (measured on 2 of 3 cases)" in render_eval_summary(summary)


def test_batch_run_has_no_latency_and_says_why():
    cases, traces = run([None, None], BATCH)
    summary = score_run(traces, cases)
    assert (summary.latency_p50_ms, summary.latency_p95_ms, summary.latency_n) == (None, None, 0)
    assert summary.execution_modes == ["batch"]
    assert "unavailable (batch)" in render_eval_summary(summary)


def test_missing_latency_outside_batch_mode_is_plain_unavailable():
    cases, traces = run([None])
    text = render_eval_summary(score_run(traces, cases))
    assert "unavailable" in text and "(batch)" not in text


def test_old_results_json_without_the_new_fields_still_validates_and_renders():
    cases, traces = run([100])
    old = score_run(traces, cases).model_dump(mode="json")
    del old["latency_n"], old["execution_modes"]
    summary = EvalSummary.model_validate(old)
    assert (summary.latency_n, summary.execution_modes) == (None, [])
    assert "100 ms / 100 ms  [low-sample: n=1 < 30]" in render_eval_summary(summary)


def test_run_report_says_latency_unavailable():
    cases, traces = run([None], BATCH)
    manifest = RunManifest(
        run_id="run_l",
        created_at=datetime(2026, 9, 25, tzinfo=UTC),
        dataset_id="test",
        dataset_path="evals/test",
        provider="test",
        policy_version="v0.1",
        case_count=1,
        trace_file="traces/run_l.jsonl",
        relay_git_sha=None,
    )
    report = render_run_report(manifest, traces, {c.input.id: c.input for c in cases})
    assert "latency unavailable" in report


def test_eval_report_and_compare_mark_batch_latency_unavailable():
    cases, sync = run([120, 80], run_id="run_s")
    _, batch = run([None, None], BATCH, run_id="run_b")
    report = render_eval_report(
        run_identity(batch),
        score_run(batch, cases),
        calibrate_run(batch, cases),
        confusion_matrices(batch, cases),
        run_sweep(batch, cases),
    )
    assert "- Latency: unavailable (batch)" in report
    text = render_comparison(compare_runs([("sync", sync), ("batch", batch)], cases))
    assert "Latency p50 / p95" in text
    assert "80 / 120 ms" in text and "unavailable (batch)" in text
    assert "Cost per case" in text and "$0.0000100" in text
