"""Ablation in traces, manifests, replay, diffs and labels (Phase 3E spec A3)."""

import json

from relay.cases.policies import load_policy
from relay.evaluation.runner import policy_text_hash
from relay.evaluation.tracediff import (
    candidate_trace_label,
    diff_traces,
    original_label,
    replay_run,
    replay_trace,
)
from relay.reporting import ablation_line, render_trace_diff
from relay.traces.models import RunManifest, WorkflowTrace
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1
from tests.factories import make_bundle, make_case, make_trace

POLICY = load_policy("immunara-v0.1")
CURRENT = policy_text_hash(POLICY)
CASE = make_case("T-01")
AUTO = WorkflowAction.AUTO_PROCESS
REVIEW = WorkflowAction.HUMAN_REVIEW


def ablated(trace, names=("contradiction",)):
    """`trace` re-decided with `names` ablated, the way relay ablate builds it."""
    marked = trace.model_copy(update={"ablation": list(names)})
    return replay_trace(marked, CASE, policy=POLICY, thresholds=trace.thresholds, git_sha="x")


def diff(a, b):
    return diff_traces(
        a,
        b,
        expected_original=REVIEW,
        expected_candidate=REVIEW,
        original_label="o",
        candidate_label="c",
        current_policy_text_hash=CURRENT,
    )


def test_a_trace_or_manifest_without_the_key_loads_as_not_ablated():
    trace = make_trace(CASE)
    raw = json.loads(trace.model_dump_json())
    del raw["ablation"]
    assert WorkflowTrace.model_validate(raw).ablation is None
    manifest = {
        "run_id": "run_x",
        "created_at": "2026-09-27T00:00:00Z",
        "dataset_id": "test",
        "dataset_path": "evals/smoke",
        "provider": "jev",
        "policy_version": "v0.1",
        "case_count": 1,
        "trace_file": "t.jsonl",
        "relay_git_sha": None,
    }
    assert RunManifest.model_validate(manifest).ablation is None
    assert RunManifest.model_validate(manifest | {"ablation": ["contradiction"]}).ablation == [
        "contradiction"
    ]


def test_replay_re_applies_the_trace_s_ablation_so_an_ablated_trace_reproduces():
    original = make_trace(CASE, make_bundle("T-01", contra=0.9))
    assert original.action is REVIEW
    once = ablated(original)
    assert (once.action, once.ablation) == (AUTO, ["contradiction"])
    again = replay_trace(once, CASE, policy=POLICY, thresholds=once.thresholds, git_sha="x")
    assert again.ablation == ["contradiction"]
    assert (again.action, again.decision_reasons, again.gate_path) == (
        once.action,
        once.decision_reasons,
        once.gate_path,
    )
    assert diff(once, again).identical


def test_replay_run_carries_ablation_through():
    original = make_trace(CASE, make_bundle("T-01", contra=0.9))
    [once] = replay_run(
        [original.model_copy(update={"ablation": ["contradiction"]})],
        [CASE],
        policy_id=None,
        auto_process=None,
    )
    assert (once.action, once.ablation) == (AUTO, ["contradiction"])


def test_diffs_record_each_side_s_ablation():
    original = make_trace(CASE, make_bundle("T-01", contra=0.9))
    candidate = ablated(original, ("contradiction", "missing_evidence"))
    d = diff(original, candidate)
    assert (d.ablation_original, d.ablation_candidate) == (
        None,
        ["contradiction", "missing_evidence"],
    )
    assert not d.identical


def test_the_ablation_line_appears_only_when_a_side_is_ablated():
    original = make_trace(CASE, make_bundle("T-01", contra=0.9))
    candidate = ablated(original, ("contradiction", "missing_evidence"))
    assert ablation_line(diff(original, original)) is None
    assert "ABLATION" not in render_trace_diff(diff(original, original))
    assert ablation_line(diff(original, candidate)) == (
        "ABLATION: none → contradiction+missing_evidence"
    )
    assert ablation_line(diff(candidate, candidate)) == (
        "ABLATION: contradiction+missing_evidence (both sides)"
    )
    text = render_trace_diff(diff(original, candidate), all_gates=True)
    assert "\nABLATION: none → contradiction+missing_evidence\n" in text
    assert "ABLATED: contradiction gate disabled" in text


def test_labels_name_the_ablation():
    plain = make_trace(CASE)
    abl = plain.model_copy(update={"ablation": ["contradiction", "missing_evidence"]})
    assert "ablate" not in original_label(plain)
    assert "ablate" not in candidate_trace_label(plain)
    assert original_label(abl).endswith("auto_process=0.95 · ablate=contradiction+missing_evidence")
    assert candidate_trace_label(abl) == (
        "candidate trace run_test · test q-test · ablate=contradiction+missing_evidence"
    )


def test_thresholds_are_untouched_by_ablation():
    original = make_trace(CASE, make_bundle("T-01", contra=0.9))
    assert ablated(original).thresholds == THRESHOLDS_V0_1
