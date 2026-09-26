"""The trace diff core: decision deltas, the crossed-threshold table, gates and classification."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from relay.cases.policies import load_policy
from relay.decisions.base import DecisionId
from relay.evaluation.runner import policy_text_hash
from relay.evaluation.tracediff import (
    CROSSINGS,
    EXIT_ENGINE_DRIFT,
    EXIT_NEWLY_UNSAFE,
    REPRODUCE_LABEL,
    THRESHOLD_NAMES,
    TraceDiff,
    candidate_trace_label,
    classify,
    diff_traces,
    live_label,
    original_label,
    policy_replay_label,
    replay_exit_code,
)
from relay.traces.models import WorkflowTrace
from relay.workflow.engine import determine_action
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1
from tests.factories import make_bundle, make_case

POLICY = load_policy("immunara-v0.1")
POLICY_V2 = POLICY.model_copy(update={"id": "immunara-v0.2", "version": "v0.2"})
CURRENT = policy_text_hash(POLICY)
T = THRESHOLDS_V0_1
CASE = make_case("T-01")
AUTO = WorkflowAction.AUTO_PROCESS
INFO = WorkflowAction.REQUEST_INFO
REVIEW = WorkflowAction.HUMAN_REVIEW
DIAG = DecisionId.DIAGNOSIS_SUPPORT
STEP = DecisionId.STEP_THERAPY
DOC = DecisionId.DOCUMENTATION_COMPLETE
CONTRA = DecisionId.MATERIAL_CONTRADICTION
MISSING = DecisionId.MISSING_EVIDENCE


def trace_for(
    bundle=None,
    *,
    thresholds=T,
    policy=POLICY,
    run_id="run_a",
    text_hash: str | None = "use-policy",
) -> WorkflowTrace:
    """A trace whose action, reasons and gate path come from the real engine."""
    bundle = bundle or make_bundle("T-01")
    outcome = determine_action(CASE.input, bundle, policy, thresholds)
    return WorkflowTrace(
        trace_id=f"tr_{run_id}",
        run_id=run_id,
        timestamp=datetime(2026, 9, 26, tzinfo=UTC),
        case_id="T-01",
        case_content_hash=CASE.input.content_hash(),
        dataset_id="test",
        provider=bundle.provider,
        provider_version=bundle.provider_version,
        question_set_version=bundle.question_set_version,
        question_set_hash=bundle.question_set_hash,
        policy_id=policy.id,
        policy_version=policy.version,
        policy_text_hash=policy_text_hash(policy) if text_hash == "use-policy" else text_hash,
        thresholds=thresholds,
        decisions=bundle,
        action=outcome.action,
        decision_reasons=outcome.reasons,
        gate_path=outcome.gate_path,
        relay_git_sha="abc123",
    )


def diff(
    original,
    candidate,
    *,
    expected_original=REVIEW,
    expected_candidate=REVIEW,
    current_hash: str | None = CURRENT,
):
    return diff_traces(
        original,
        candidate,
        expected_original=expected_original,
        expected_candidate=expected_candidate,
        original_label="orig",
        candidate_label="cand",
        current_policy_text_hash=current_hash,
    )


def row(d, question_id):
    return next(x for x in d.decisions if x.question_id == question_id)


def gate_fired(trace, gate):
    """True/False for a gate the engine reached, None if it never got there."""
    return next((g.fired for g in trace.gate_path if g.gate == gate), None)


# ---- the crossed-threshold table against the engine ----

# For each gated (decision, threshold) row: make_bundle kwargs putting that one decision just on
# the comparison's True side and just on its False side of threshold t. Every other decision
# stays at make_bundle's defaults, which pass every gate (AUTO_PROCESS).
ENGINE_CASES = {
    (DIAG, "auto_process"): lambda t: ({"diag": t + 0.01}, {"diag": t - 0.01}),
    (STEP, "auto_process"): lambda t: ({"step": t + 0.01}, {"step": t - 0.01}),
    (DOC, "auto_process"): lambda t: ({"doc": t + 0.01}, {"doc": t - 0.01}),
    (CONTRA, "contradiction_review"): lambda t: ({"contra": t + 0.01}, {"contra": t - 0.01}),
    (CONTRA, "contradiction_auto_block"): lambda t: (
        {"contra": t + 0.01},
        {"contra": t - 0.01},
    ),
    (DOC, "documentation_request_info"): lambda t: ({"doc": t + 0.01}, {"doc": t - 0.01}),
    (MISSING, "missing_evidence_request_info"): lambda t: (
        {"missing": "DOSAGE", "missing_p": t + 0.01},
        {"missing": "DOSAGE", "missing_p": t - 0.01},
    ),
}


def test_every_threshold_has_at_least_one_crossing_row():
    assert {name for _, name in CROSSINGS} == set(THRESHOLD_NAMES)
    assert set(THRESHOLD_NAMES) == {
        "auto_process",
        "contradiction_review",
        "contradiction_auto_block",
        "documentation_request_info",
        "missing_evidence_request_info",
    }


def test_every_gated_row_is_checked_against_the_engine():
    assert set(ENGINE_CASES) == {key for key, c in CROSSINGS.items() if c.gate is not None}


@pytest.mark.parametrize("key", list(ENGINE_CASES), ids=lambda k: f"{k[0]}-{k[1]}")
def test_crossing_a_threshold_flips_the_engine_gate_and_is_named(key):
    question_id, name = key
    true_side, false_side = ENGINE_CASES[key](getattr(T, name))
    a = trace_for(make_bundle("T-01", **true_side))
    b = trace_for(make_bundle("T-01", **false_side))
    gate = CROSSINGS[key].gate
    assert gate_fired(a, gate) is not None and gate_fired(b, gate) is not None
    assert gate_fired(a, gate) != gate_fired(b, gate)
    d = diff(a, b)
    assert row(d, question_id).crossed == [name]
    assert all(x.crossed == [] for x in d.decisions if x.question_id != question_id)


@pytest.mark.parametrize("key", list(ENGINE_CASES), ids=lambda k: f"{k[0]}-{k[1]}")
def test_a_move_that_stays_on_one_side_flips_nothing(key):
    question_id, name = key
    t = getattr(T, name)
    near, _ = ENGINE_CASES[key](t)
    far, _ = ENGINE_CASES[key](t + 0.01)
    a = trace_for(make_bundle("T-01", **near))
    b = trace_for(make_bundle("T-01", **far))
    gate = CROSSINGS[key].gate
    assert gate_fired(a, gate) == gate_fired(b, gate)
    assert all(x.crossed == [] for x in diff(a, b).decisions)


def test_reported_only_rows_are_named_but_do_not_move_the_engine():
    # material_contradiction vs auto_process compares 1 - p_yes: 0.96 vs 0.94 crosses 0.95,
    # but the engine only compares contradiction with contradiction_review/auto_block.
    a = trace_for(make_bundle("T-01", contra=0.04))
    b = trace_for(make_bundle("T-01", contra=0.06))
    assert (a.action, b.action) == (AUTO, AUTO)
    assert row(diff(a, b), CONTRA).crossed == ["auto_process"]
    # missing_evidence vs auto_process compares p(NONE).
    c = trace_for(make_bundle("T-01", missing="NONE", missing_p=0.96))
    e = trace_for(make_bundle("T-01", missing="NONE", missing_p=0.90))
    assert (c.action, e.action) == (AUTO, AUTO)
    assert row(diff(c, e), MISSING).crossed == ["auto_process"]


def test_a_pure_threshold_change_shows_as_crossed():
    bundle = make_bundle("T-01", step=0.93)
    a = trace_for(bundle)
    b = trace_for(bundle, thresholds=T.model_copy(update={"auto_process": 0.9}))
    d = diff(a, b)
    assert row(d, STEP).crossed == ["auto_process"]
    assert row(d, STEP).delta == 0.0
    assert row(d, DIAG).crossed == []
    assert d.thresholds == {"auto_process": (0.95, 0.9)}
    assert (d.action_original, d.action_candidate) == (REVIEW, AUTO)


# ---- decision deltas ----


def test_yes_no_delta_and_rendering():
    a = trace_for(make_bundle("T-01", step=0.93))
    b = trace_for(make_bundle("T-01", step=0.55))
    r = row(diff(a, b), STEP)
    assert (r.kind, r.original, r.candidate) == ("yes_no", "p_yes=0.930", "p_yes=0.550")
    assert r.delta == pytest.approx(-0.38)
    assert r.answer_changed is False


def test_yes_no_answer_changes_when_p_yes_crosses_one_half():
    a = trace_for(make_bundle("T-01", diag=0.6))
    b = trace_for(make_bundle("T-01", diag=0.4))
    assert row(diff(a, b), DIAG).answer_changed is True


def test_choice_delta_tracks_the_original_answers_probability():
    a = trace_for(make_bundle("T-01", missing="NONE", missing_p=0.9))
    b = trace_for(make_bundle("T-01", missing="DOSAGE", missing_p=0.8))
    r = row(diff(a, b), MISSING)
    assert (r.kind, r.original, r.candidate) == ("choice", "NONE (0.90)", "DOSAGE (0.80)")
    assert r.answer_changed is True
    assert r.delta == pytest.approx(-0.9)  # candidate gives NONE no probability at all


def test_a_decision_missing_on_one_side():
    a = trace_for(make_bundle("T-01"))
    b = trace_for(make_bundle("T-01", error="boom"))
    r = row(diff(a, b), STEP)
    assert (r.kind, r.original, r.candidate) == ("yes_no", "p_yes=0.990", "missing")
    assert (r.answer_changed, r.delta, r.crossed) == (True, None, [])


def test_a_decision_missing_on_both_sides():
    a = trace_for(make_bundle("T-01", error="boom"))
    b = trace_for(make_bundle("T-01", error="bang"))
    r = row(diff(a, b), MISSING)
    assert (r.kind, r.original, r.candidate) == (None, "missing", "missing")
    assert (r.answer_changed, r.delta, r.crossed) == (False, None, [])


def test_deltas_cover_all_five_decisions_in_order():
    d = diff(trace_for(), trace_for())
    assert [x.question_id for x in d.decisions] == list(DecisionId)


# ---- gates ----


def test_gate_rows_are_the_union_of_both_paths_in_engine_order():
    a = trace_for(make_bundle("T-01"))  # AUTO_PROCESS
    b = trace_for(make_bundle("T-01", contra=0.9))  # contradiction fires
    rows = {g.gate: g for g in diff(a, b).gates}
    assert list(rows) == [
        "provider",
        "age",
        "contradiction",
        "documentation",
        "missing_evidence",
        "auto_process",
    ]
    assert (rows["contradiction"].original, rows["contradiction"].candidate) == (
        "passed",
        "FIRED",
    )
    assert (rows["auto_process"].original, rows["auto_process"].candidate) == (
        "FIRED",
        "not reached",
    )
    assert rows["auto_process"].detail_candidate is None
    assert rows["contradiction"].detail_candidate.startswith("p_yes(material_contradiction)=0.900")


def test_default_review_appears_when_either_path_reaches_it():
    a = trace_for(make_bundle("T-01"))
    b = trace_for(make_bundle("T-01", step=0.5))
    rows = {g.gate: g for g in diff(a, b).gates}
    assert (rows["default_review"].original, rows["default_review"].candidate) == (
        "not reached",
        "FIRED",
    )


# ---- classification ----


def test_classify():
    assert classify(REVIEW, REVIEW) == "correct"
    assert classify(INFO, REVIEW) == "wrong-safe"
    assert classify(REVIEW, AUTO) == "wrong-safe"
    assert classify(AUTO, REVIEW) == "UNSAFE"


# (original action, candidate action) with expected HUMAN_REVIEW on both sides:
# REVIEW is correct, INFO is wrong-safe, AUTO is UNSAFE.
MATRIX = [
    (REVIEW, REVIEW, "unchanged", False, False),
    (REVIEW, INFO, "regressed", False, False),
    (REVIEW, AUTO, "regressed", True, False),
    (INFO, REVIEW, "improved", False, False),
    (INFO, INFO, "unchanged", False, False),
    (INFO, AUTO, "changed-both-wrong", True, False),
    (AUTO, REVIEW, "improved", False, True),
    (AUTO, INFO, "changed-both-wrong", False, True),
    (AUTO, AUTO, "unchanged", False, False),
]


@pytest.mark.parametrize("action_o,action_c,change,newly,resolved", MATRIX)
def test_change_classification_matrix(action_o, action_c, change, newly, resolved):
    base = trace_for()
    d = diff(
        base.model_copy(update={"action": action_o}),
        base.model_copy(update={"action": action_c}),
    )
    assert (d.change, d.newly_unsafe, d.unsafe_resolved) == (change, newly, resolved)


def test_two_different_wrong_safe_actions_are_changed_both_wrong():
    base = trace_for()
    d = diff(
        base.model_copy(update={"action": INFO}),
        base.model_copy(update={"action": REVIEW}),
        expected_original=AUTO,
        expected_candidate=AUTO,
    )
    assert (d.change, d.newly_unsafe) == ("changed-both-wrong", False)


def test_each_side_is_judged_against_its_own_expected_action():
    base = trace_for()
    d = diff(
        base.model_copy(update={"action": REVIEW}),
        base.model_copy(update={"action": AUTO}),
        expected_original=REVIEW,
        expected_candidate=AUTO,
    )
    assert (d.change, d.newly_unsafe, d.unsafe_resolved) == ("unchanged", False, False)
    assert (d.expected_original, d.expected_candidate) == (REVIEW, AUTO)


# ---- identical, policy and policy text ----


def test_identical_ignores_latency_cost_and_tokens():
    a = trace_for(make_bundle("T-01", latency_ms=100, cost=Decimal("0.00001")))
    slow = make_bundle("T-01", latency_ms=900, cost=Decimal("0.5"))
    b = trace_for(slow.model_copy(update={"input_tokens": 5}), run_id="run_b")
    assert diff(a, b).identical is True


def test_identical_is_false_when_anything_else_differs():
    a = trace_for(make_bundle("T-01"))
    assert diff(a, trace_for(make_bundle("T-01", derivations={"x": 1}))).identical is False
    assert diff(a, a.model_copy(update={"decision_reasons": ["other"]})).identical is False
    assert diff(a, a.model_copy(update={"gate_path": a.gate_path[:-1]})).identical is False
    assert diff(a, a.model_copy(update={"action": REVIEW})).identical is False


def test_policy_is_reported_only_when_it_differs():
    a = trace_for()
    assert diff(a, trace_for()).policy is None
    b = trace_for(policy=POLICY_V2)
    assert diff(a, b).policy == ("immunara-v0.1 v0.1", "immunara-v0.2 v0.2")


def test_policy_text_change_against_the_current_text_of_the_original_policy():
    current = CURRENT
    same = diff(trace_for(), trace_for(), current_hash=current)
    assert same.policy_text_changed is False
    old = trace_for(text_hash="sha256:" + "0" * 64)
    changed = diff(old, trace_for(), current_hash=current)
    assert changed.policy_text_changed is True
    assert changed.policy_text_hash_original == "sha256:" + "0" * 64
    assert changed.policy_text_hash_current == current
    unrecorded = diff(trace_for(text_hash=None), trace_for(), current_hash=current)
    assert unrecorded.policy_text_changed is None


def test_traces_of_different_cases_cannot_be_diffed():
    a = trace_for()
    with pytest.raises(ValueError, match="different cases"):
        diff(a, a.model_copy(update={"case_id": "T-02"}))


def test_diff_round_trips_through_json():
    d = diff(trace_for(), trace_for(thresholds=T.model_copy(update={"auto_process": 0.9})))
    assert TraceDiff.model_validate_json(d.model_dump_json()) == d


# ---- exit codes and labels ----


def test_replay_exit_codes():
    same = diff(trace_for(), trace_for())
    assert replay_exit_code(same, reproduce=True) == 0
    drift = same.model_copy(update={"identical": False})
    assert replay_exit_code(drift, reproduce=True) == EXIT_ENGINE_DRIFT == 3
    assert replay_exit_code(drift, reproduce=False) == 0
    unsafe = same.model_copy(update={"newly_unsafe": True})
    assert replay_exit_code(unsafe, reproduce=False) == EXIT_NEWLY_UNSAFE == 4
    both = drift.model_copy(update={"newly_unsafe": True})
    assert replay_exit_code(both, reproduce=True) == 4


def test_labels():
    t = trace_for(run_id="run_20260925T170857Z_b95be9")
    assert original_label(t) == (
        "run_20260925T170857Z_b95be9 · test q-test · policy immunara-v0.1 (v0.1) · "
        "thresholds auto_process=0.95"
    )
    assert REPRODUCE_LABEL == "reproduce: stored decisions, current engine, original policy"
    assert policy_replay_label(POLICY, None) == (
        "policy replay: STORED DECISIONS under policy immunara-v0.1 (v0.1) — judgments were "
        "made against the original policy's questions"
    )
    assert policy_replay_label(POLICY_V2, 0.89) == (
        "policy replay: STORED DECISIONS under policy immunara-v0.2 (v0.2), auto_process=0.89 "
        "— judgments were made against the original policy's questions"
    )
    assert candidate_trace_label(t) == "candidate trace run_20260925T170857Z_b95be9 · test q-test"
    assert live_label(t) == ("live run run_20260925T170857Z_b95be9 · test q-test on frozen inputs")
