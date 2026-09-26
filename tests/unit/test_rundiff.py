"""diff_case / diff_runs: the run-level diff helpers every replay, regression and shadow caller
shares (F2), so that pairing and expected actions are derived in exactly one place."""

import pytest

import relay.cases.policies as policies_module
import relay.evaluation.tracediff as tracediff
from relay.cases.policies import load_policy
from relay.evaluation.labels import expected_action
from relay.evaluation.metrics import EvalError
from relay.evaluation.runner import policy_text_hash
from relay.evaluation.tracediff import diff_case, diff_runs, diff_traces, replay_trace
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1, override_auto_process
from tests.factories import make_bundle, make_case, make_trace

POLICY = load_policy("immunara-v0.1")


def register_strict_v0_2(monkeypatch):
    """A second registered policy that differs where it matters: min_age 50, so a 40-year-old's
    expected action is HUMAN_REVIEW under it and AUTO_PROCESS under immunara-v0.1."""
    spec = dict(policies_module._POLICIES["immunara-v0.1"], version="v0.2", min_age=50)
    monkeypatch.setitem(policies_module._POLICIES, "immunara-v0.2", spec)
    return load_policy("immunara-v0.2")


def run_of(*case_ids, run_id="run_a", step=0.93):
    cases = [make_case(i) for i in case_ids]
    traces = [make_trace(c, make_bundle(c.input.id, step=step), run_id=run_id) for c in cases]
    return cases, traces


def at(traces, cases, auto_process, policy=POLICY):
    thresholds = override_auto_process(THRESHOLDS_V0_1, auto_process)
    return [
        replay_trace(t, c, policy=policy, thresholds=thresholds, git_sha="x")
        for t, c in zip(traces, cases, strict=True)
    ]


def test_diff_case_matches_a_hand_built_diff_traces():
    [case], [original] = run_of("T-01")
    [candidate] = at([original], [case], 0.9)
    by_hand = diff_traces(
        original,
        candidate,
        expected_original=expected_action(case, POLICY, original.thresholds),
        expected_candidate=expected_action(case, POLICY, candidate.thresholds),
        original_label="o",
        candidate_label="c",
        current_policy_text_hash=policy_text_hash(POLICY),
    )
    assert diff_case(original, candidate, case, original_label="o", candidate_label="c") == by_hand
    assert by_hand.newly_unsafe is False and by_hand.change == "improved"


def test_diff_case_judges_each_side_under_its_own_policy(monkeypatch):
    strict = register_strict_v0_2(monkeypatch)
    [case], [original] = run_of("T-01", step=0.99)
    [candidate] = at([original], [case], 0.95, policy=strict)
    d = diff_case(original, candidate, case, original_label="o", candidate_label="c")
    assert (d.expected_original, d.expected_candidate) == (
        WorkflowAction.AUTO_PROCESS,
        WorkflowAction.HUMAN_REVIEW,
    )
    assert d.policy == ("immunara-v0.1 v0.1", "immunara-v0.2 v0.2")
    assert d.policy_text_hash_current == policy_text_hash(POLICY)


def test_diff_case_uses_the_policy_cache(monkeypatch):
    def no_load(policy_id):
        raise AssertionError(f"loaded {policy_id} despite the cache")

    monkeypatch.setattr(tracediff, "load_policy", no_load)
    [case], [original] = run_of("T-01")
    d = diff_case(
        original,
        original,
        case,
        original_label="o",
        candidate_label="c",
        policies={POLICY.id: POLICY},
    )
    assert d.identical


def test_diff_runs_diffs_every_case_in_trace_order_and_loads_each_policy_once(monkeypatch):
    loaded = []
    real = tracediff.load_policy

    def counting(policy_id):
        loaded.append(policy_id)
        return real(policy_id)

    monkeypatch.setattr(tracediff, "load_policy", counting)
    cases, originals = run_of("T-02", "T-01", "T-03")
    candidates = list(reversed(at(originals, cases, 0.9)))
    diffs = diff_runs(originals, candidates, cases, original_label="o", candidate_label="c")
    assert [d.case_id for d in diffs] == ["T-02", "T-01", "T-03"]
    assert {d.action_candidate for d in diffs} == {WorkflowAction.AUTO_PROCESS}
    assert {(d.original_label, d.candidate_label) for d in diffs} == {("o", "c")}
    assert loaded == ["immunara-v0.1"]


def test_diff_runs_names_missing_and_extra_case_ids():
    cases, originals = run_of("T-01", "T-02")
    _, others = run_of("T-01", "T-03", run_id="run_b")
    with pytest.raises(EvalError, match=r"missing \['T-02'\], extra \['T-03'\]"):
        diff_runs(originals, others, cases, original_label="o", candidate_label="c")


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda c: [c[0], c[1].model_copy(update={"run_id": "run_z"})], "multiple runs"),
        (
            lambda c: [c[0], c[1].model_copy(update={"case_content_hash": "sha256:x"})],
            "hash changed",
        ),
    ],
)
def test_diff_runs_applies_paired_cases_to_the_candidate_run(mutate, message):
    cases, originals = run_of("T-01", "T-02")
    candidates = mutate(at(originals, cases, 0.9))
    with pytest.raises(EvalError, match=message):
        diff_runs(originals, candidates, cases, original_label="o", candidate_label="c")


def test_diff_runs_needs_every_dataset_case():
    cases, originals = run_of("T-01", "T-02")
    with pytest.raises(EvalError, match="do not cover every case"):
        diff_runs(
            originals[:1],
            at(originals, cases, 0.9)[:1],
            cases,
            original_label="o",
            candidate_label="c",
        )


def test_diff_runs_turns_an_unknown_policy_into_an_eval_error():
    cases, originals = run_of("T-01")
    ghost = [originals[0].model_copy(update={"policy_id": "nope-v1"})]
    with pytest.raises(EvalError, match="unknown policy 'nope-v1'"):
        diff_runs(originals, ghost, cases, original_label="o", candidate_label="c")
