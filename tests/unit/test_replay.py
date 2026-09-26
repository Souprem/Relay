"""replay_trace / replay_run: stored decisions re-run through today's engine."""

from datetime import UTC, datetime

import pytest

import relay.cases.policies as policies_module
import relay.evaluation.tracediff as tracediff
import relay.workflow.thresholds as thresholds_module
from relay.cases.policies import load_policy
from relay.evaluation.metrics import EvalError
from relay.evaluation.runner import policy_text_hash
from relay.evaluation.tracediff import replay_run, replay_thresholds, replay_trace
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1, override_auto_process
from tests.factories import make_bundle, make_case, make_trace

POLICY = load_policy("immunara-v0.1")
POLICY_V2 = POLICY.model_copy(update={"id": "immunara-v0.2", "version": "v0.2", "text": "v2"})
NOW = datetime(2026, 9, 26, 12, tzinfo=UTC)
THRESHOLDS_V2 = THRESHOLDS_V0_1.model_copy(update={"version": "v0.2", "auto_process": 0.9})


def test_replay_trace_marks_the_new_trace_as_a_simulated_replay():
    case = make_case("T-01")
    original = make_trace(case)
    replayed = replay_trace(
        original, case, policy=POLICY, thresholds=THRESHOLDS_V0_1, now=NOW, git_sha="deadbeef"
    )
    assert replayed.trace_id != original.trace_id
    assert replayed.trace_id.startswith("tr_")
    assert replayed.run_id == "replay-run_test"
    assert replayed.replay_of == original.trace_id
    assert replayed.mode == "simulated"
    assert replayed.timestamp == NOW
    assert replayed.relay_git_sha == "deadbeef"
    assert replayed.policy_text_hash == policy_text_hash(POLICY)
    assert replayed.decisions == original.decisions
    assert (replayed.action, replayed.decision_reasons, replayed.gate_path) == (
        original.action,
        original.decision_reasons,
        original.gate_path,
    )


def test_replay_trace_uses_the_candidate_policy_and_thresholds():
    case = make_case("T-01")
    original = make_trace(case, make_bundle("T-01", step=0.93))
    assert original.action == WorkflowAction.HUMAN_REVIEW
    lower = THRESHOLDS_V0_1.model_copy(update={"auto_process": 0.9})
    replayed = replay_trace(original, case, policy=POLICY_V2, thresholds=lower, git_sha="x")
    assert replayed.action == WorkflowAction.AUTO_PROCESS
    assert (replayed.policy_id, replayed.policy_version) == ("immunara-v0.2", "v0.2")
    assert replayed.policy_text_hash == policy_text_hash(POLICY_V2)
    assert replayed.thresholds.auto_process == 0.9


def test_replay_trace_defaults_git_sha_to_the_current_commit(monkeypatch):
    monkeypatch.setattr(tracediff, "current_git_sha", lambda: "cafef00d")
    case = make_case("T-01")
    replayed = replay_trace(make_trace(case), case, policy=POLICY, thresholds=THRESHOLDS_V0_1)
    assert replayed.relay_git_sha == "cafef00d"


def test_replay_trace_refuses_another_case_or_changed_inputs():
    case = make_case("T-01")
    trace = make_trace(case)
    with pytest.raises(ValueError, match="is not the trace's case"):
        replay_trace(trace, make_case("T-02"), policy=POLICY, thresholds=THRESHOLDS_V0_1)
    older = make_case("T-01", age=41)
    with pytest.raises(ValueError, match="content hash changed"):
        replay_trace(trace, older, policy=POLICY, thresholds=THRESHOLDS_V0_1)


def run_of(*case_ids, run_id="run_a"):
    cases = [make_case(i) for i in case_ids]
    return cases, [make_trace(c, make_bundle(c.input.id, step=0.93), run_id=run_id) for c in cases]


def test_replay_run_shares_one_run_id_and_applies_the_overrides():
    cases, traces = run_of("T-01", "T-02")
    replayed = replay_run(traces, cases, policy_id=None, auto_process=0.9)
    assert [t.case_id for t in replayed] == ["T-01", "T-02"]
    assert {t.run_id for t in replayed} == {"replay-run_a"}
    assert {t.action for t in replayed} == {WorkflowAction.AUTO_PROCESS}
    assert [t.replay_of for t in replayed] == [t.trace_id for t in traces]
    assert len({t.relay_git_sha for t in replayed}) == 1


def test_replay_run_with_no_overrides_keeps_each_traces_policy_and_threshold():
    cases, traces = run_of("T-01")
    [replayed] = replay_run(traces, cases, policy_id=None, auto_process=None)
    assert replayed.thresholds == traces[0].thresholds
    assert replayed.policy_id == traces[0].policy_id
    assert replayed.action == traces[0].action


def test_replay_run_loads_the_named_policy(monkeypatch):
    # F1: a v0.2 target brings v0.2 thresholds, so they must be registered for this replay.
    monkeypatch.setitem(thresholds_module._BY_VERSION, "v0.2", THRESHOLDS_V2)
    loaded = []

    def fake_load(policy_id):
        loaded.append(policy_id)
        return POLICY_V2

    monkeypatch.setattr(tracediff, "load_policy", fake_load)
    cases, traces = run_of("T-01", "T-02")
    replayed = replay_run(traces, cases, policy_id="immunara-v0.2", auto_process=None)
    assert loaded == ["immunara-v0.2"]  # loaded once per run, not once per trace
    assert {t.policy_id for t in replayed} == {"immunara-v0.2"}


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda cases, traces: (cases, traces[:1]), "do not cover every case"),
        (lambda cases, traces: (cases, [traces[0], traces[0]]), "duplicate case ids"),
        (
            lambda cases, traces: (
                cases,
                [traces[0], traces[1].model_copy(update={"run_id": "b"})],
            ),
            "multiple runs",
        ),
        (lambda cases, traces: ([make_case("T-01", age=41), cases[1]], traces), "hash changed"),
    ],
)
def test_replay_run_enforces_paired_cases(mutate, message):
    cases, traces = run_of("T-01", "T-02")
    cases, traces = mutate(cases, traces)
    with pytest.raises(EvalError, match=message):
        replay_run(traces, cases, policy_id=None, auto_process=None)


# ---- F1: thresholds follow the target policy version ----


def register_v0_2(monkeypatch, *, with_thresholds: bool = True):
    """Register a second policy version (reusing the v0.1 text file) and, optionally, its
    thresholds, for the length of one test."""
    spec = dict(policies_module._POLICIES["immunara-v0.1"], version="v0.2")
    monkeypatch.setitem(policies_module._POLICIES, "immunara-v0.2", spec)
    if with_thresholds:
        monkeypatch.setitem(thresholds_module._BY_VERSION, "v0.2", THRESHOLDS_V2)


def test_same_version_keeps_the_traces_own_thresholds_even_when_overridden():
    case = make_case("T-01")
    trace = make_trace(case)
    assert replay_thresholds(trace, POLICY, None) is trace.thresholds
    earlier = trace.model_copy(update={"thresholds": override_auto_process(THRESHOLDS_V0_1, 0.9)})
    assert replay_thresholds(earlier, POLICY, None).version == "v0.1+at0.9"
    assert replay_thresholds(earlier, POLICY, 0.8).version == "v0.1+at0.8"


def test_another_version_brings_its_own_thresholds_then_the_override(monkeypatch):
    register_v0_2(monkeypatch)
    trace = make_trace(make_case("T-01"))
    v2 = load_policy("immunara-v0.2")
    assert replay_thresholds(trace, v2, None) == THRESHOLDS_V2
    at = replay_thresholds(trace, v2, 0.85)
    assert (at.version, at.auto_process) == ("v0.2+at0.85", 0.85)


def test_another_version_without_thresholds_is_an_eval_error(monkeypatch):
    register_v0_2(monkeypatch, with_thresholds=False)
    trace = make_trace(make_case("T-01"))
    with pytest.raises(EvalError, match="unknown thresholds version 'v0.2'"):
        replay_thresholds(trace, load_policy("immunara-v0.2"), None)


def test_replay_run_onto_another_version_uses_that_versions_thresholds(monkeypatch):
    register_v0_2(monkeypatch)
    cases, traces = run_of("T-01", "T-02")  # step=0.93: HUMAN_REVIEW at 0.95, AUTO at 0.9
    replayed = replay_run(traces, cases, policy_id="immunara-v0.2", auto_process=None)
    assert {t.thresholds.version for t in replayed} == {"v0.2"}
    assert {t.action for t in replayed} == {WorkflowAction.AUTO_PROCESS}


def test_replay_run_onto_an_unregistered_version_or_policy_is_an_eval_error(monkeypatch):
    register_v0_2(monkeypatch, with_thresholds=False)
    cases, traces = run_of("T-01")
    with pytest.raises(EvalError, match="unknown thresholds version 'v0.2'"):
        replay_run(traces, cases, policy_id="immunara-v0.2", auto_process=None)
    with pytest.raises(EvalError, match="unknown policy 'nope-v1'"):
        replay_run(traces, cases, policy_id="nope-v1", auto_process=None)


def test_replay_run_labels_an_auto_process_override_in_the_thresholds_version():
    cases, traces = run_of("T-01")
    [replayed] = replay_run(traces, cases, policy_id=None, auto_process=0.9)
    assert replayed.thresholds.version == "v0.1+at0.9"


# ---- Phase 3C: mode and run id for relay run --from-traces ----


def test_replay_trace_takes_a_mode_and_a_run_id():
    case = make_case("T-01")
    original = make_trace(case)
    shadow = replay_trace(
        original,
        case,
        policy=POLICY,
        thresholds=THRESHOLDS_V0_1,
        git_sha="x",
        mode="shadow",
        run_id="run_new",
    )
    assert (shadow.mode, shadow.run_id, shadow.replay_of) == ("shadow", "run_new", "tr_T-01")


def test_replay_run_passes_the_mode_and_run_id_to_every_trace():
    cases, traces = run_of("T-01", "T-02")
    replayed = replay_run(
        traces, cases, policy_id=None, auto_process=0.9, mode="shadow", run_id="run_new"
    )
    assert {(t.mode, t.run_id) for t in replayed} == {("shadow", "run_new")}
    assert [t.replay_of for t in replayed] == [t.trace_id for t in traces]
