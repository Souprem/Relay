"""The regression gate's verdict, waivers and result model (pure; no files)."""

import pytest
from pydantic import ValidationError

from relay.evaluation.intervals import clopper_pearson
from relay.evaluation.regression import (
    Waiver,
    WaiverFile,
    build_result,
    evaluate_gate,
    rate,
)
from relay.evaluation.tracediff import diff_case, diff_runs, replay_run
from relay.workflow.outcomes import WorkflowAction
from tests.factories import make_bundle, make_case, make_trace, make_truth

AUTO = WorkflowAction.AUTO_PROCESS
REVIEW = WorkflowAction.HUMAN_REVIEW


def base_diff():
    case = make_case("T-01")
    trace = make_trace(case)
    return diff_case(trace, trace, case, original_label="b", candidate_label="c")


BASE = base_diff()


def synthetic(
    case_id, *, change="unchanged", newly_unsafe=False, identical=True, unsafe_both=False
):
    """A TraceDiff with only the fields the verdict reads set."""
    return BASE.model_copy(
        update={
            "case_id": case_id,
            "change": change,
            "newly_unsafe": newly_unsafe,
            "unsafe_resolved": False,
            "unsafe_both": unsafe_both,
            "identical": identical,
        }
    )


def waiver(case_id, gate="*", **overrides):
    values = {
        "case_id": case_id,
        "gate": gate,
        "reason": "accepted after review",
        "approved_by": "reviewer",
        "date": "2026-09-26",
    }
    values.update(overrides)
    return Waiver.model_validate(values)


def gate(diffs, *, reproduce=False, waivers=(), name=None, max_regressed=None):
    return evaluate_gate(
        diffs, reproduce=reproduce, waivers=list(waivers), gate=name, max_regressed=max_regressed
    )


# ---- the verdict ----


def test_no_differences_pass_with_exit_0():
    outcome = gate([synthetic("A"), synthetic("B")])
    assert (outcome.verdict, outcome.exit_code, outcome.failures) == ("PASS", 0, [])


def test_a_newly_unsafe_case_fails_with_exit_4_and_is_named():
    outcome = gate([synthetic("A"), synthetic("B", change="regressed", newly_unsafe=True)])
    assert (outcome.verdict, outcome.exit_code) == ("FAIL", 4)
    assert outcome.failures == ["1 newly unsafe case(s) without a waiver: B"]
    assert [d.case_id for d in outcome.newly_unsafe] == ["B"]


def test_a_waiver_covers_its_newly_unsafe_case():
    diffs = [synthetic("B", change="regressed", newly_unsafe=True)]
    outcome = gate(diffs, waivers=[waiver("B")])
    assert (outcome.verdict, outcome.exit_code) == ("PASS", 0)
    assert [(d.case_id, w.case_id) for d, w in outcome.waived] == [("B", "B")]
    assert outcome.newly_unsafe == [] and outcome.stale_waivers == []


def test_a_waiver_applies_to_its_own_gate_or_to_every_gate():
    diffs = [synthetic("B", change="regressed", newly_unsafe=True)]
    assert gate(diffs, waivers=[waiver("B", gate="g1")], name="g1").verdict == "PASS"
    other = gate(diffs, waivers=[waiver("B", gate="g2")], name="g1")
    assert other.verdict == "FAIL"
    assert other.stale_waivers == []  # a waiver for another gate is out of scope, not stale
    assert gate(diffs, waivers=[waiver("B", gate="g2")], name=None).verdict == "FAIL"


def test_a_waiver_matching_no_newly_unsafe_case_is_stale_but_not_a_failure():
    outcome = gate([synthetic("A")], waivers=[waiver("GONE")])
    assert (outcome.verdict, outcome.exit_code) == ("PASS", 0)
    assert [w.case_id for w in outcome.stale_waivers] == ["GONE"]


def test_regressions_fail_only_above_max_regressed():
    diffs = [synthetic("A", change="regressed"), synthetic("B", change="regressed")]
    assert gate(diffs).verdict == "PASS"
    assert gate(diffs, max_regressed=2).verdict == "PASS"
    over = gate(diffs, max_regressed=1)
    assert (over.verdict, over.exit_code) == ("FAIL", 4)
    assert over.failures == ["2 regressed case(s), more than --max-regressed 1"]


def test_a_waiver_never_covers_a_regression():
    diffs = [synthetic("A", change="regressed")]
    outcome = gate(diffs, waivers=[waiver("A")], max_regressed=0)
    assert outcome.verdict == "FAIL"
    assert [w.case_id for w in outcome.stale_waivers] == ["A"]


def test_reproduce_fails_any_non_identical_case_with_exit_3():
    diffs = [synthetic("A"), synthetic("B", identical=False)]
    outcome = gate(diffs, reproduce=True)
    assert (outcome.verdict, outcome.exit_code) == ("FAIL", 3)
    assert outcome.failures == ["ENGINE DRIFT: 1 case(s) not reproduced: B"]
    assert gate(diffs, reproduce=False).verdict == "PASS"  # only reproduce checks identity


def test_engine_drift_cannot_be_waived_and_the_higher_exit_code_wins():
    drift = synthetic("B", change="regressed", newly_unsafe=True, identical=False)
    waived = gate([drift], reproduce=True, waivers=[waiver("B")])
    assert (waived.verdict, waived.exit_code) == ("FAIL", 3)
    both = gate([drift], reproduce=True)
    assert both.exit_code == 4
    assert len(both.failures) == 2


def test_long_id_lists_are_shortened():
    diffs = [synthetic(f"C{i:02d}", change="regressed", newly_unsafe=True) for i in range(12)]
    [failure] = gate(diffs).failures
    assert failure.endswith("C09 and 2 more")


def test_the_verdict_needs_labelled_diffs():
    with pytest.raises(ValueError, match="labelled"):
        gate([BASE.model_copy(update={"change": None})])


# ---- waivers ----


def test_a_waiver_file_parses():
    parsed = WaiverFile.model_validate({"waivers": [waiver("B").model_dump()]})
    assert parsed.waivers == [waiver("B")]


def test_a_duplicate_waiver_is_rejected():
    """M3: the first one silently winning would be a confusing way to fail closed."""
    with pytest.raises(ValidationError, match="duplicate waiver"):
        WaiverFile.model_validate(
            {"waivers": [waiver("B").model_dump(), waiver("B", reason="different").model_dump()]}
        )
    # same case_id, different gate: not a duplicate
    WaiverFile.model_validate(
        {"waivers": [waiver("B", gate="g1").model_dump(), waiver("B", gate="g2").model_dump()]}
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"reason": ""},
        {"reason": "   "},
        {"approved_by": None},
        {"gate": 3},
        {"date": "26/09/2026"},
        {"date": "2026-13-40"},
        {"extra": "field"},
    ],
)
def test_a_malformed_waiver_is_rejected(overrides):
    with pytest.raises(ValidationError):
        waiver("B", **overrides)


def test_every_waiver_field_is_required():
    values = waiver("B").model_dump()
    for field in values:
        partial = {k: v for k, v in values.items() if k != field}
        with pytest.raises(ValidationError):
            Waiver.model_validate(partial)


# ---- the result model ----


def test_rate_carries_a_clopper_pearson_interval_and_none_for_no_trials():
    r = rate(3, 10)
    assert (r.count, r.n, r.rate) == (3, 10, 0.3)
    assert (r.ci95.low, r.ci95.high) == clopper_pearson(3, 10)
    empty = rate(0, 0)
    assert (empty.rate, empty.ci95) == (None, None)


def three_case_run():
    """T-01 expected AUTO_PROCESS, T-02 and T-03 expected HUMAN_REVIEW (step therapy not met);
    every bundle has step_therapy 0.93, so all three are HUMAN_REVIEW at 0.95."""
    cases = [
        make_case("T-01"),
        make_case("T-02", truth=make_truth(step_therapy_satisfied=False)),
        make_case("T-03", truth=make_truth(step_therapy_satisfied=False)),
    ]
    traces = [make_trace(c, make_bundle(c.input.id, step=0.93)) for c in cases]
    return cases, traces


def test_build_result_at_a_lower_threshold():
    cases, baseline = three_case_run()
    candidate = replay_run(baseline, cases, policy_id=None, auto_process=0.9)
    diffs = diff_runs(baseline, candidate, cases, original_label="base", candidate_label="cand")
    result = build_result(
        diffs,
        baseline,
        candidate,
        cases,
        baseline_label="base",
        candidate_label="cand",
        gate="g",
        reproduce=False,
        waivers=[waiver("T-03", reason="reviewed")],
        max_regressed=None,
        dataset_hash="sha256:d",
        replay_command=lambda case_id: f"relay replay {case_id}",
    )
    assert (result.gate, result.dataset_id, result.n) == ("g", "test", 3)
    assert result.change_counts == {
        "improved": 1,
        "unchanged": 0,
        "regressed": 2,
        "changed-both-wrong": 0,
    }
    assert result.not_identical == 3
    assert [e.case_id for e in result.newly_unsafe] == ["T-02"]
    assert [w.entry.case_id for w in result.waived] == ["T-03"]
    assert [e.case_id for e in result.improved] == ["T-01"]
    assert [e.case_id for e in result.regressed] == ["T-02", "T-03"]
    entry = result.newly_unsafe[0]
    assert (entry.expected, entry.expected_candidate) == (REVIEW, None)
    assert (entry.action_baseline, entry.action_candidate) == (REVIEW, AUTO)
    assert entry.answer_changed == []
    assert entry.crossed_gated == {"step_therapy": ["auto_process"]}
    assert entry.replay_command == "relay replay T-02"
    assert (result.verdict, result.exit_code) == ("FAIL", 4)
    assert result.failures == ["1 newly unsafe case(s) without a waiver: T-02"]
    assert result.baseline.automation.count == 0 and result.candidate.automation.count == 3
    assert result.baseline.uar.rate is None
    assert (result.candidate.uar.count, result.candidate.uar.n) == (2, 3)
    assert result.candidate.identity.dataset_hash == "sha256:d"
    assert result.candidate.identity.thresholds_versions == ["v0.1+at0.9"]
    # the same stored decisions on both sides: calibration cannot move
    assert {c.brier_delta for c in result.calibration} == {0.0}
    assert [c.decision for c in result.calibration][0] == "diagnosis_support"
    assert type(result).model_validate_json(result.model_dump_json()) == result


def test_still_unsafe_lists_cases_unsafe_on_both_sides_and_never_fails_the_gate():
    """I1: a case the baseline already automates unsafely is invisible to newly_unsafe (the gate
    is relative to the baseline, per spec G5), so it must be surfaced separately."""
    cases, baseline = three_case_run()
    candidate = replay_run(baseline, cases, policy_id=None, auto_process=0.9)
    diffs = diff_runs(baseline, candidate, cases, original_label="base", candidate_label="cand")
    # T-02 and T-03 are genuinely newly unsafe here (see test_build_result_at_a_lower_threshold);
    # simulate a baseline that was already unsafe on both, so neither is newly unsafe anymore.
    diffs = [
        d.model_copy(update={"newly_unsafe": False, "unsafe_both": True})
        if d.case_id in ("T-02", "T-03")
        else d
        for d in diffs
    ]
    result = build_result(
        diffs,
        baseline,
        candidate,
        cases,
        baseline_label="base",
        candidate_label="cand",
        gate="g",
        reproduce=False,
        waivers=[],
        max_regressed=None,
    )
    assert [e.case_id for e in result.still_unsafe] == ["T-02", "T-03"]
    assert result.newly_unsafe == []
    assert (result.verdict, result.exit_code, result.failures) == ("PASS", 0, [])
