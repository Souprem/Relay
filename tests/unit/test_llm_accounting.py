"""Refusals, prompt-cache reads and partial missing-evidence distributions in eval output."""

import pytest

from relay.evaluation.calibration import calibrate_run, is_partial
from relay.evaluation.compare import compare_runs
from relay.evaluation.metrics import EvalSummary, score_run
from relay.reporting import render_calibration_markdown, render_comparison, render_eval_summary
from tests.factories import make_bundle, make_case, make_trace

USAGE_A = {"input_tokens": 1000, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 3000}
USAGE_B = {"input_tokens": 1000, "cache_creation_input_tokens": 1000, "cache_read_input_tokens": 0}


def claude_like_run():
    cases = [make_case("A"), make_case("B"), make_case("C")]
    bundles = [
        make_bundle("A", derivations={"stop_reason": "end_turn", "usage": USAGE_A}),
        make_bundle("B", error="refusal: Claude declined", derivations={"stop_reason": "refusal"}),
        make_bundle("C", derivations={"stop_reason": "end_turn", "usage": USAGE_B}),
    ]
    return cases, [make_trace(c, b) for c, b in zip(cases, bundles, strict=True)]


def test_refusals_are_counted_from_the_recorded_stop_reason():
    cases, traces = claude_like_run()
    summary = score_run(traces, cases)
    assert summary.refusals == 1
    assert "Refusals" in render_eval_summary(summary)


def test_runs_without_stop_reasons_report_no_refusal_row():
    cases = [make_case("A")]
    summary = score_run([make_trace(cases[0])], cases)
    assert summary.refusals is None and summary.cache_read_share is None
    text = render_eval_summary(summary)
    assert "Refusals" not in text and "Prompt cache reads" not in text


def test_cache_read_share_is_cached_over_all_prompt_tokens():
    cases, traces = claude_like_run()
    summary = score_run(traces, cases)
    # 3000 cached of 1000 + 3000 + 1000 + 1000 prompt tokens
    assert summary.cache_read_share == pytest.approx(0.5)
    assert "Prompt cache reads        50.0% of prompt tokens" in render_eval_summary(summary)


def test_old_results_json_without_the_accounting_fields_still_validates():
    cases, traces = claude_like_run()
    old = score_run(traces, cases).model_dump(mode="json")
    del old["refusals"], old["cache_read_share"]
    summary = EvalSummary.model_validate(old)
    assert (summary.refusals, summary.cache_read_share) == (None, None)


def test_partial_means_probability_mass_on_no_label():
    labels = ("X", "Y")
    assert is_partial({"X": 0.9}, labels)
    assert not is_partial({"X": 1.0}, labels)
    assert not is_partial({"X": 0.4, "Y": 0.6}, labels)


def test_partial_missing_evidence_distributions_are_counted_and_reported():
    cases = [make_case("A"), make_case("B")]
    traces = [
        make_trace(cases[0], make_bundle("A", missing_p=0.9)),
        make_trace(cases[1], make_bundle("B", missing_p=1.0)),
    ]
    calibration = calibrate_run(traces, cases)
    assert calibration.partial_choice_distributions == 1
    text = "\n".join(render_calibration_markdown(calibration))
    assert "Partial missing_evidence distributions" in text and ": 1 of 2." in text


def test_compare_shows_refusals_cache_reads_and_partial_distributions():
    cases, claude = claude_like_run()
    other = [make_trace(c, make_bundle(c.input.id), run_id="run_o") for c in cases]
    text = render_comparison(compare_runs([("claude", claude), ("other", other)], cases))
    for row in ("Refusals", "Prompt cache reads", "Partial missing_evidence distributions"):
        assert row in text
    assert "50.0% of prompt tokens" in text
