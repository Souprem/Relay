"""determine_action(..., ablate=...): the Phase 3E gate-ablation switch (spec A1, A2)."""

import pytest

from relay.cases.policies import load_policy
from relay.workflow.engine import ABLATIONS, determine_action
from relay.workflow.outcomes import GateResult, WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1
from tests.factories import make_bundle, make_case_input

POLICY = load_policy("immunara-v0.1")
AUTO = WorkflowAction.AUTO_PROCESS
INFO = WorkflowAction.REQUEST_INFO
REVIEW = WorkflowAction.HUMAN_REVIEW
BOTH = frozenset({"contradiction", "missing_evidence"})


def decide(bundle, ablate=frozenset(), age=40):
    return determine_action(
        make_case_input(age=age), bundle, POLICY, THRESHOLDS_V0_1, ablate=ablate
    )


def gate(outcome, name):
    [result] = [g for g in outcome.gate_path if g.gate == name]
    return result


def test_the_ablatable_gates_are_exactly_contradiction_and_missing_evidence():
    assert ABLATIONS == BOTH


@pytest.mark.parametrize(
    "bundle_kwargs",
    [
        {},
        {"contra": 0.9},
        {"contra": 0.3},
        {"doc": 0.5, "missing": "TREATMENT_HISTORY", "missing_p": 0.8},
        {"missing": "INSURANCE_INFORMATION", "missing_p": 0.8},
        {"step": 0.9},
        {"error": "boom"},
    ],
)
def test_the_default_is_the_unablated_engine(bundle_kwargs):
    bundle = make_bundle(**bundle_kwargs)
    input_ = make_case_input()
    assert determine_action(input_, bundle, POLICY, THRESHOLDS_V0_1) == determine_action(
        input_, bundle, POLICY, THRESHOLDS_V0_1, ablate=frozenset()
    )


def test_an_unknown_ablation_raises():
    with pytest.raises(ValueError, match=r"unknown ablation\(s\) \['age'\]"):
        decide(make_bundle(), ablate=frozenset({"age"}))


def test_contradiction_ablation_turns_a_contradiction_review_into_auto_process():
    bundle = make_bundle(contra=0.9)
    assert decide(bundle).action is REVIEW
    outcome = decide(bundle, frozenset({"contradiction"}))
    assert outcome.action is AUTO
    assert gate(outcome, "contradiction") == GateResult(
        gate="contradiction", fired=False, detail="ABLATED: contradiction gate disabled"
    )
    auto = gate(outcome, "auto_process")
    assert auto.fired
    assert auto.detail.endswith(
        "p_yes(material_contradiction)=0.900, contradiction auto-block ABLATED"
    )
    assert outcome.reasons == [
        "all required judgments are at or above 0.95 (contradiction auto-block ABLATED)"
    ]


def test_contradiction_ablation_also_removes_the_auto_block():
    bundle = make_bundle(contra=0.3)  # below the 0.80 review gate, above the 0.20 auto-block
    unablated = decide(bundle)
    assert (unablated.action, unablated.gate_path[-1].gate) == (REVIEW, "default_review")
    assert decide(bundle, frozenset({"contradiction"})).action is AUTO


def test_contradiction_ablation_still_needs_the_required_judgments():
    outcome = decide(make_bundle(contra=0.9, step=0.9), frozenset({"contradiction"}))
    assert (outcome.action, outcome.gate_path[-1].gate) == (REVIEW, "default_review")
    assert outcome.reasons == ["step_therapy p_yes=0.900 is below the 0.95 autonomous-action bar"]


def test_missing_evidence_ablation_falls_through_to_the_next_gate():
    bundle = make_bundle(missing="INSURANCE_INFORMATION", missing_p=0.8)
    assert decide(bundle).action is INFO
    outcome = decide(bundle, frozenset({"missing_evidence"}))
    assert (outcome.action, outcome.gate_path[-1].gate) == (AUTO, "auto_process")
    assert gate(outcome, "missing_evidence") == GateResult(
        gate="missing_evidence", fired=False, detail="ABLATED: missing_evidence gate disabled"
    )
    lower = decide(
        make_bundle(missing="DIAGNOSIS", missing_p=0.8, diag=0.9), frozenset({"missing_evidence"})
    )
    assert (lower.action, lower.gate_path[-1].gate) == (REVIEW, "default_review")


def test_missing_evidence_ablation_keeps_the_documentation_gate():
    bundle = make_bundle(doc=0.5, missing="TREATMENT_HISTORY", missing_p=0.8)
    outcome = decide(bundle, frozenset({"missing_evidence"}))
    assert (outcome.action, outcome.gate_path[-1].gate) == (INFO, "documentation")


def test_missing_evidence_ablation_leaves_contradiction_detection_alone():
    outcome = decide(make_bundle(contra=0.9), frozenset({"missing_evidence"}))
    assert (outcome.action, outcome.gate_path[-1].gate) == (REVIEW, "contradiction")


def test_both_ablations_list_both_gates_as_ablated():
    bundle = make_bundle(contra=0.9, missing="INSURANCE_INFORMATION", missing_p=0.8)
    outcome = decide(bundle, BOTH)
    assert outcome.action is AUTO
    assert [g.gate for g in outcome.gate_path] == [
        "provider",
        "age",
        "contradiction",
        "documentation",
        "missing_evidence",
        "auto_process",
    ]
    assert [g.detail for g in outcome.gate_path if g.detail.startswith("ABLATED")] == [
        "ABLATED: contradiction gate disabled",
        "ABLATED: missing_evidence gate disabled",
    ]


def test_the_earlier_gates_still_fire_before_an_ablated_gate_is_reached():
    assert decide(make_bundle(contra=0.9), BOTH, age=16).gate_path[-1].gate == "age"
    outcome = decide(make_bundle(error="boom"), BOTH)
    assert [g.gate for g in outcome.gate_path] == ["provider"]
