"""render_trace_diff: the terminal output of `relay replay`."""

import re

from relay.cases.policies import load_policy
from relay.evaluation.runner import policy_text_hash
from relay.evaluation.tracediff import diff_traces, replay_trace
from relay.reporting import DRIFT_LINE, REPRODUCED_LINE, render_trace_diff, replay_summary
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1
from tests.factories import make_bundle, make_case, make_trace

POLICY = load_policy("immunara-v0.1")
CURRENT = policy_text_hash(POLICY)
CASE = make_case("T-01")
AUTO = WorkflowAction.AUTO_PROCESS
INFO = WorkflowAction.REQUEST_INFO
REVIEW = WorkflowAction.HUMAN_REVIEW


def original(**bundle_kwargs):
    trace = make_trace(CASE, make_bundle("T-01", **bundle_kwargs))
    return trace.model_copy(update={"policy_text_hash": CURRENT})


def diff(a, b, *, expected=(REVIEW, REVIEW), current=CURRENT):
    return diff_traces(
        a,
        b,
        expected_original=expected[0],
        expected_candidate=expected[1],
        original_label="run_test · test q-test · policy immunara-v0.1 (v0.1) · thresholds "
        "auto_process=0.95",
        candidate_label="reproduce: stored decisions, current engine, original policy",
        current_policy_text_hash=current,
    )


def at(trace, auto_process):
    thresholds = THRESHOLDS_V0_1.model_copy(update={"auto_process": auto_process})
    return replay_trace(trace, CASE, policy=POLICY, thresholds=thresholds, git_sha="x")


def test_header_labels_both_sides_and_the_expected_action():
    a = original()
    text = render_trace_diff(diff(a, a, expected=(AUTO, AUTO)))
    lines = text.splitlines()
    assert lines[0] == "Relay replay — T-01"
    assert lines[1] == (
        "ORIGINAL run_test · test q-test · policy immunara-v0.1 (v0.1) · thresholds "
        "auto_process=0.95"
    )
    assert lines[2] == "CANDIDATE reproduce: stored decisions, current engine, original policy"
    assert "EXPECTED (evaluation-only): AUTO_PROCESS" in lines


def test_reproduce_verdict_is_printed_in_the_header_and_last():
    a = original()
    same = render_trace_diff(diff(a, a, expected=(AUTO, AUTO)), reproduce=True)
    assert same.splitlines()[3] == REPRODUCED_LINE
    assert same.splitlines()[-1] == REPRODUCED_LINE
    drifted = diff(a, a.model_copy(update={"decision_reasons": ["new"]}), expected=(AUTO, AUTO))
    text = render_trace_diff(drifted, reproduce=True)
    assert text.splitlines()[3] == DRIFT_LINE
    assert text.splitlines()[-1] == DRIFT_LINE
    assert REPRODUCED_LINE not in render_trace_diff(diff(a, a, expected=(AUTO, AUTO)))


def test_reproduce_mode_still_shows_newly_unsafe():  # Minor 7
    """Reproduce mode (drift verdict) and NEWLY UNSAFE are independent signals -- the drift
    verdict compares the stored vs. re-run decision, while NEWLY UNSAFE compares each side's
    action to its own expected action. A renderer test should pin that both show up together
    and in the documented order: the ACTION CHANGED/UNCHANGED (NEWLY UNSAFE) summary line,
    then DRIFT_LINE as the very last line, so a later refactor cannot silently drop either."""
    a = original()
    drifted = diff(
        a,
        a.model_copy(update={"decision_reasons": ["new"]}),
        expected=(AUTO, REVIEW),
    )
    assert drifted.newly_unsafe
    text = render_trace_diff(drifted, reproduce=True)
    lines = text.splitlines()
    assert lines[3] == DRIFT_LINE
    assert lines[-1] == DRIFT_LINE
    summary_line = next(
        line
        for line in lines
        if line.startswith("ACTION CHANGED") or line.startswith("ACTION UNCHANGED")
    )
    assert summary_line == "ACTION UNCHANGED: AUTO_PROCESS (NEWLY UNSAFE)"
    assert lines.index(summary_line) < lines.index(DRIFT_LINE, lines.index(summary_line) + 1)


def test_decisions_table_shows_values_delta_crossed_and_changed_answers():
    a = original(step=0.93, missing="NONE", missing_p=0.9)
    b = at(a, 0.9).model_copy(
        update={"decisions": make_bundle("T-01", step=0.93, missing="DOSAGE", missing_p=0.8)}
    )
    text = render_trace_diff(diff(a, b))
    step = next(line for line in text.splitlines() if "step_therapy" in line)
    assert "p_yes=0.930" in step and "+0.000" in step and step.rstrip().endswith("auto_process")
    missing = next(line for line in text.splitlines() if " missing_evidence " in line)
    assert missing.lstrip().startswith("*")
    assert "NONE (0.90)" in missing and "DOSAGE (0.80)" in missing and "-0.900" in missing
    assert "  (* = answer changed)" in text


def test_changed_thresholds_and_changed_gates_are_listed():
    a = original(step=0.93)
    b = at(a, 0.9)
    text = render_trace_diff(diff(a, b))
    assert "THRESHOLDS CHANGED" in text
    assert "  auto_process  0.95 → 0.9" in text
    assert "GATES (rows whose outcome differs; --all-gates shows every row)" in text
    assert re.search(r"auto_process\s+passed → FIRED", text)
    assert "  default_review    FIRED → not reached" in text
    assert "      original:  min(required p_yes)=0.930, auto at >= 0.95" in text
    assert "  provider " not in text  # unchanged rows are hidden by default


def test_all_gates_shows_every_row():
    a = original(step=0.93)
    text = render_trace_diff(diff(a, at(a, 0.9)), all_gates=True)
    assert "GATES (all rows)" in text
    assert re.search(r"provider\s+passed", text)
    assert "      all five decisions present and well-formed" in text


def test_no_gate_change_says_so():
    a = original()
    text = render_trace_diff(diff(a, a, expected=(AUTO, AUTO)))
    assert "GATES: same outcome at every gate (--all-gates shows every row)" in text
    assert "THRESHOLDS CHANGED" not in text


def test_actions_are_classified_and_the_summary_flags_new_unsafe_automation():
    a = original(step=0.93)
    b = at(a, 0.9)
    text = render_trace_diff(diff(a, b))
    assert "  ORIGINAL  HUMAN_REVIEW (correct)" in text
    assert "  CANDIDATE AUTO_PROCESS (UNSAFE)" in text
    assert "      - step_therapy p_yes=0.930 is below the 0.95 autonomous-action bar" in text
    assert text.splitlines()[-1] == "ACTION CHANGED: HUMAN_REVIEW → AUTO_PROCESS (NEWLY UNSAFE)"


def test_summary_line_variants():
    a = original(step=0.93)
    b = at(a, 0.9)
    assert replay_summary(diff(a, a)) == "ACTION UNCHANGED: HUMAN_REVIEW"
    assert replay_summary(diff(b, a)) == (
        "ACTION CHANGED: AUTO_PROCESS → HUMAN_REVIEW (UNSAFE RESOLVED)"
    )
    assert replay_summary(diff(a, b, expected=(AUTO, AUTO))) == (
        "ACTION CHANGED: HUMAN_REVIEW → AUTO_PROCESS (improved)"
    )
    info = a.model_copy(update={"action": INFO})
    assert replay_summary(diff(a, info)) == (
        "ACTION CHANGED: HUMAN_REVIEW → REQUEST_INFO (regressed)"
    )


def test_expected_actions_that_differ_are_both_printed():
    a = original(step=0.93)
    b = at(a, 0.9)
    text = render_trace_diff(diff(a, b, expected=(REVIEW, AUTO)))
    assert (
        "EXPECTED (evaluation-only) under original thresholds: HUMAN_REVIEW · "
        "under candidate thresholds: AUTO_PROCESS"
    ) in text
    other = b.model_copy(update={"policy_id": "immunara-v0.2", "policy_version": "v0.2"})
    text = render_trace_diff(diff(a, other, expected=(REVIEW, AUTO)))
    assert (
        "EXPECTED (evaluation-only) under immunara-v0.1 v0.1: HUMAN_REVIEW · "
        "under immunara-v0.2 v0.2: AUTO_PROCESS"
    ) in text
    assert "POLICY CHANGED: immunara-v0.1 v0.1 → immunara-v0.2 v0.2" in text


def test_policy_text_lines():
    a = original()
    assert "POLICY TEXT" not in render_trace_diff(diff(a, a))
    old = a.model_copy(update={"policy_text_hash": "sha256:0123456789abcdef"})
    text = render_trace_diff(diff(old, a))
    assert f"POLICY TEXT CHANGED since the original run (01234567 → {CURRENT[7:15]})" in text
    unrecorded = a.model_copy(update={"policy_text_hash": None})
    assert "policy text hash not recorded" in render_trace_diff(diff(unrecorded, a))
