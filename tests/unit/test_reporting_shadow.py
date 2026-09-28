"""Rendering for relay run --workflow simulated | shadow: the per-case lines in the handoff's
exact wording, the summaries, and the shadow comparison report."""

from datetime import UTC, datetime

import pytest

from relay.evaluation.shadow import build_shadow_report
from relay.reporting import (
    EVALUATION_ONLY_HEADER,
    promotion_line,
    render_shadow_report,
    shadow_line,
    shadow_trailer,
    simulated_line,
    simulated_summary,
)
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.status import CaseStatus, Transition
from tests.factories import make_bundle, make_case, make_trace, make_truth

AUTO = WorkflowAction.AUTO_PROCESS
INFO = WorkflowAction.REQUEST_INFO
REVIEW = WorkflowAction.HUMAN_REVIEW
BUNDLES = {AUTO: {}, REVIEW: {"step": 0.5}, INFO: {"doc": 0.3}}
NOW = datetime(2026, 9, 26, 12, tzinfo=UTC)


def trace(action, case_id="CASE-3817", run_id="run_s", case=None):
    t = make_trace(
        case or make_case(case_id), make_bundle(case_id, **BUNDLES[action]), run_id=run_id
    )
    assert t.action == action
    return t


def transition(action, to):
    return Transition(
        from_status=CaseStatus.RECEIVED, to=to, action=action, trace_id="tr", run_id="run_a", at=NOW
    )


@pytest.mark.parametrize(
    "action,expected",
    [
        (AUTO, "SHADOW: Would auto-process CASE-3817; no action was taken."),
        (INFO, "SHADOW: Would request information for CASE-3817; no action was taken."),
        (REVIEW, "SHADOW: Would send CASE-3817 to human review; no action was taken."),
    ],
)
def test_shadow_lines_use_the_handoff_wording(action, expected):
    assert shadow_line(trace(action)) == expected


def test_a_shadow_line_appends_the_current_status_when_state_exists():
    t = trace(AUTO)
    assert shadow_line(t, (CaseStatus.IN_HUMAN_REVIEW, "run_a")) == (
        "SHADOW: Would auto-process CASE-3817; no action was taken. "
        "(current status: IN_HUMAN_REVIEW by run_a)"
    )
    assert shadow_line(t, (CaseStatus.RECEIVED, None)) == (
        "SHADOW: Would auto-process CASE-3817; no action was taken. (current status: RECEIVED)"
    )


def test_the_shadow_trailer():
    assert shadow_trailer("run_s", 100) == (
        "SHADOW RUN run_s: 100 proposals recorded; case state unchanged (verified)."
    )


def test_simulated_line_and_summary():
    t = transition(AUTO, CaseStatus.AUTO_APPROVED)
    assert simulated_line(t, "CASE-3817") == (
        "SIMULATED: CASE-3817 RECEIVED → AUTO_APPROVED (AUTO_PROCESS)"
    )
    transitions = [
        t,
        transition(REVIEW, CaseStatus.IN_HUMAN_REVIEW),
        transition(REVIEW, CaseStatus.IN_HUMAN_REVIEW),
    ]
    assert simulated_summary("run_a", transitions) == (
        "SIMULATED RUN run_a: 3 transitions applied — AUTO_APPROVED 1 · INFO_REQUESTED 0 · "
        "IN_HUMAN_REVIEW 2"
    )


def shadow_report(candidate_t03: WorkflowAction):
    cases = [make_case("T-01"), make_case("T-02", truth=make_truth(step_therapy_satisfied=False))]
    incumbent = [
        trace(AUTO, "T-01", "run_inc", cases[0]),
        trace(REVIEW, "T-02", "run_inc", cases[1]),
    ]
    candidate = [
        trace(REVIEW, "T-01", "run_sh", cases[0]),
        trace(candidate_t03, "T-02", "run_sh", cases[1]),
    ]
    return build_shadow_report(
        incumbent, candidate, cases, incumbent_label="jev 0.95", candidate_label="jev 0.89"
    )


def test_render_shadow_report_puts_agreement_first_and_the_promotion_check_last():
    text = render_shadow_report(shadow_report(AUTO))
    lines = text.splitlines()
    assert lines[:8] == [
        "Relay shadow comparison — dataset test · n=2",
        "INCUMBENT jev 0.95",
        "CANDIDATE jev 0.89",
        "",
        "AGREEMENT (unlabelled; what a real shadow deployment sees)",
        "  Action agreement: 0/2 (0.0%)  95% CI [0.0%, 84.2%]",
        "",
        "  INCUMBENT \\ CANDIDATE  AUTO_PROCESS  REQUEST_INFO  HUMAN_REVIEW",
    ]
    assert lines[8:11] == [
        "  AUTO_PROCESS           0             0             1",
        "  REQUEST_INFO           0             0             0",
        "  HUMAN_REVIEW           1             0             0",
    ]
    assert "  Would newly auto-process (1): T-02" in lines
    assert "  Would stop auto-processing (1): T-01" in lines
    header = lines.index(EVALUATION_ONLY_HEADER)
    assert header < lines.index("NEWLY UNSAFE (1)")
    assert lines[header + 1] == "Relay regression — dataset test · n=2"
    assert lines[-3] == "REGRESSION GATE: FAIL — 1 newly unsafe case(s) without a waiver: T-02"
    assert lines[-1] == ("PROMOTION CHECK: HOLD — 1 newly unsafe case(s) without a waiver: T-02")


def test_promotion_line_for_a_promoted_candidate():
    report = shadow_report(REVIEW)
    assert report.decision == "PROMOTE"
    assert promotion_line(report) == "PROMOTION CHECK: PROMOTE"
    text = render_shadow_report(report)
    assert "  Would newly auto-process (0): none" in text.splitlines()
    assert text.splitlines()[-1] == "PROMOTION CHECK: PROMOTE"
