"""build_shadow_report: unlabelled agreement plus the evaluation-only promotion check (pure)."""

import pytest

from relay.cases.models import MissingEvidence
from relay.evaluation.metrics import EvalError
from relay.evaluation.regression import Waiver
from relay.evaluation.shadow import agreement, build_shadow_report, transition_matrix
from relay.evaluation.tracediff import diff_runs
from relay.workflow.outcomes import WorkflowAction
from tests.factories import make_bundle, make_case, make_trace, make_truth

AUTO = WorkflowAction.AUTO_PROCESS
INFO = WorkflowAction.REQUEST_INFO
REVIEW = WorkflowAction.HUMAN_REVIEW

# Expected actions: T-01 and T-02 AUTO_PROCESS, T-03 HUMAN_REVIEW, T-04 REQUEST_INFO.
CASES = [
    make_case("T-01"),
    make_case("T-02"),
    make_case("T-03", truth=make_truth(step_therapy_satisfied=False)),
    make_case(
        "T-04",
        truth=make_truth(
            documentation_complete=False, missing_evidence=MissingEvidence.TREATMENT_HISTORY
        ),
    ),
]
# Bundles that give each action under v0.1 thresholds.
BUNDLES = {AUTO: {}, REVIEW: {"step": 0.5}, INFO: {"doc": 0.3}}


def run(actions: dict[str, WorkflowAction], run_id: str):
    by_id = {c.input.id: c for c in CASES}
    traces = []
    for case_id, action in actions.items():
        t = make_trace(by_id[case_id], make_bundle(case_id, **BUNDLES[action]), run_id=run_id)
        assert t.action == action
        traces.append(t)
    return traces


INCUMBENT = run({"T-01": AUTO, "T-02": REVIEW, "T-03": REVIEW, "T-04": INFO}, "run_inc")
# T-02 newly auto-processed and correct; T-03 newly auto-processed and UNSAFE.
UNSAFE_CANDIDATE = run({"T-01": AUTO, "T-02": AUTO, "T-03": AUTO, "T-04": INFO}, "run_sh")
# T-02 newly auto-processed and correct; T-03 unchanged.
SAFE_CANDIDATE = run({"T-01": AUTO, "T-02": AUTO, "T-03": REVIEW, "T-04": INFO}, "run_sh")


def report(candidate, **kwargs):
    return build_shadow_report(
        INCUMBENT,
        candidate,
        CASES,
        incumbent_label="incumbent",
        candidate_label="candidate",
        **kwargs,
    )


def test_transition_matrix_counts_every_cell():
    diffs = diff_runs(
        INCUMBENT, UNSAFE_CANDIDATE, CASES, original_label="a", candidate_label="b", labelled=False
    )
    assert transition_matrix(diffs) == {
        AUTO: {AUTO: 1, INFO: 0, REVIEW: 0},
        INFO: {AUTO: 0, INFO: 1, REVIEW: 0},
        REVIEW: {AUTO: 2, INFO: 0, REVIEW: 0},
    }


def test_agreement_is_computed_without_ground_truth():
    diffs = diff_runs(
        INCUMBENT, UNSAFE_CANDIDATE, CASES, original_label="a", candidate_label="b", labelled=False
    )
    assert all(d.expected_original is None and d.change is None for d in diffs)
    block = agreement(diffs)
    assert (block.n, block.agreed.count, block.agreed.n, block.agreed.rate) == (4, 2, 4, 0.5)
    assert block.newly_auto == ["T-02", "T-03"]
    assert block.stopped_auto == []


def test_stopped_auto_lists_cases_the_candidate_would_no_longer_automate():
    candidate = run({"T-01": REVIEW, "T-02": REVIEW, "T-03": REVIEW, "T-04": INFO}, "run_sh")
    shadow = report(candidate)
    assert shadow.agreement.stopped_auto == ["T-01"]
    assert shadow.agreement.newly_auto == []


def test_a_newly_unsafe_candidate_is_held():
    shadow = report(UNSAFE_CANDIDATE)
    assert (shadow.decision, shadow.exit_code) == ("HOLD", 4)
    assert [e.case_id for e in shadow.promotion.newly_unsafe] == ["T-03"]
    assert shadow.promotion.failures == ["1 newly unsafe case(s) without a waiver: T-03"]
    assert (shadow.dataset_id, shadow.n) == ("test", 4)
    assert (shadow.incumbent_label, shadow.candidate_label) == ("incumbent", "candidate")


def test_a_safe_candidate_is_promoted():
    shadow = report(SAFE_CANDIDATE)
    assert (shadow.decision, shadow.exit_code) == ("PROMOTE", 0)
    assert shadow.promotion.verdict == "PASS"
    assert [e.case_id for e in shadow.promotion.improved] == ["T-02"]
    assert shadow.agreement.agreed.count == 3


def test_a_waiver_turns_hold_into_promote_and_is_scoped_by_gate_name():
    waiver = Waiver(
        case_id="T-03", gate="rollout", reason="reviewed", approved_by="r", date="2026-09-26"
    )
    assert report(UNSAFE_CANDIDATE, waivers=[waiver]).decision == "HOLD"  # no gate name
    promoted = report(UNSAFE_CANDIDATE, waivers=[waiver], gate_name="rollout")
    assert promoted.decision == "PROMOTE"
    assert [w.entry.case_id for w in promoted.promotion.waived] == ["T-03"]


def test_too_many_regressions_hold():
    candidate = run({"T-01": REVIEW, "T-02": REVIEW, "T-03": REVIEW, "T-04": INFO}, "run_sh")
    assert report(candidate).decision == "PROMOTE"  # a safe regression alone does not hold
    held = report(candidate, max_regressed=0)
    assert (held.decision, held.exit_code) == ("HOLD", 4)
    assert held.promotion.failures == ["1 regressed case(s), more than --max-regressed 0"]


def test_still_unsafe_is_reported_but_never_holds():
    incumbent = run({"T-01": AUTO, "T-02": REVIEW, "T-03": AUTO, "T-04": INFO}, "run_inc")
    candidate = run({"T-01": AUTO, "T-02": REVIEW, "T-03": AUTO, "T-04": INFO}, "run_sh")
    shadow = build_shadow_report(
        incumbent, candidate, CASES, incumbent_label="i", candidate_label="c"
    )
    assert shadow.decision == "PROMOTE"
    assert [e.case_id for e in shadow.promotion.still_unsafe] == ["T-03"]


def test_runs_over_different_cases_are_an_eval_error():
    with pytest.raises(EvalError, match="does not cover the same cases"):
        report(SAFE_CANDIDATE[:3])


def test_the_report_round_trips_as_json():
    shadow = report(UNSAFE_CANDIDATE)
    assert type(shadow).model_validate_json(shadow.model_dump_json()) == shadow


def test_replay_commands_are_attached_to_listed_cases():
    shadow = report(UNSAFE_CANDIDATE, replay_command=lambda case_id: f"relay replay {case_id}")
    assert [e.replay_command for e in shadow.promotion.newly_unsafe] == ["relay replay T-03"]
