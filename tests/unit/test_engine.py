import pytest

from relay.cases.policies import load_policy
from relay.decisions.base import Decision, DecisionBundle, DecisionId
from relay.workflow.engine import determine_action
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1, load_thresholds
from tests.factories import make_bundle, make_case_input

POLICY = load_policy("immunara-v0.1")
AUTO = WorkflowAction.AUTO_PROCESS
INFO = WorkflowAction.REQUEST_INFO
REVIEW = WorkflowAction.HUMAN_REVIEW


def decide(bundle, age=40):
    return determine_action(make_case_input(age=age), bundle, POLICY, THRESHOLDS_V0_1)


def fired_gate(outcome):
    assert outcome.gate_path[-1].fired
    assert all(not g.fired for g in outcome.gate_path[:-1])
    return outcome.gate_path[-1].gate


def test_thresholds_v0_1_values():
    t = load_thresholds("v0.1")
    assert (t.auto_process, t.contradiction_review, t.contradiction_auto_block) == (
        0.95,
        0.80,
        0.20,
    )
    assert (t.documentation_request_info, t.missing_evidence_request_info) == (0.60, 0.70)


def test_unknown_thresholds_version():
    with pytest.raises(KeyError):
        load_thresholds("v9")


def test_all_high_confidence_auto_processes():
    outcome = decide(make_bundle())
    assert outcome.action is AUTO
    assert fired_gate(outcome) == "auto_process"
    assert outcome.reasons


def test_provider_error_routes_to_review():
    outcome = decide(make_bundle(error="TypeSafeRateLimitError: slow down"))
    assert outcome.action is REVIEW
    assert fired_gate(outcome) == "provider"
    assert "provider failure" in outcome.reasons[0]


def test_missing_decision_routes_to_review():
    full = make_bundle()
    partial = full.model_copy(update={"decisions": full.decisions[:4]})
    outcome = decide(partial)
    assert outcome.action is REVIEW
    assert "missing_evidence" in outcome.gate_path[-1].detail


def test_wrong_decision_kind_routes_to_review():
    full = make_bundle()
    bad = [*full.decisions[:4], Decision.yes_no(DecisionId.MISSING_EVIDENCE, 0.5, "test")]
    outcome = decide(full.model_copy(update={"decisions": bad}))
    assert outcome.action is REVIEW
    assert fired_gate(outcome) == "provider"


def test_unknown_missing_evidence_label_routes_to_review():
    outcome = decide(make_bundle(missing="SOMETHING_ELSE", missing_p=0.9))
    assert outcome.action is REVIEW
    assert fired_gate(outcome) == "provider"


def test_duplicate_decisions_route_to_review():
    full = make_bundle()
    outcome = decide(full.model_copy(update={"decisions": [*full.decisions, full.decisions[0]]}))
    assert fired_gate(outcome) == "provider"


def test_under_age_routes_to_review_even_with_perfect_decisions():
    outcome = decide(make_bundle(), age=17)
    assert outcome.action is REVIEW
    assert fired_gate(outcome) == "age"
    assert "17" in outcome.reasons[0]


def test_age_equal_to_minimum_passes():
    assert decide(make_bundle(), age=18).action is AUTO


def test_contradiction_at_threshold_reviews():
    outcome = decide(make_bundle(contra=0.80))
    assert outcome.action is REVIEW
    assert fired_gate(outcome) == "contradiction"


def test_contradiction_just_below_review_threshold_still_blocks_auto():
    outcome = decide(make_bundle(contra=0.79))
    assert outcome.action is REVIEW
    assert fired_gate(outcome) == "default_review"


def test_documentation_below_threshold_requests_info():
    outcome = decide(make_bundle(doc=0.59, missing="TREATMENT_HISTORY", missing_p=0.5))
    assert outcome.action is INFO
    assert fired_gate(outcome) == "documentation"
    assert any("treatment history" in r for r in outcome.reasons)


def test_documentation_at_threshold_does_not_request_info():
    outcome = decide(make_bundle(doc=0.60))
    assert outcome.action is REVIEW
    assert fired_gate(outcome) == "default_review"


def test_confident_missing_evidence_requests_info():
    outcome = decide(make_bundle(missing="INSURANCE_INFORMATION", missing_p=0.70))
    assert outcome.action is INFO
    assert fired_gate(outcome) == "missing_evidence"
    assert "insurance information" in outcome.reasons[0]


def test_unconfident_missing_evidence_does_not_request_info():
    outcome = decide(make_bundle(missing="INSURANCE_INFORMATION", missing_p=0.69))
    assert fired_gate(outcome) == "auto_process"


def test_missing_evidence_none_never_requests_info():
    assert decide(make_bundle(missing="NONE", missing_p=0.99)).action is AUTO


@pytest.mark.parametrize("field", ["diag", "step", "doc"])
def test_each_required_judgment_at_auto_threshold_is_enough(field):
    assert decide(make_bundle(**{field: 0.95})).action is AUTO


@pytest.mark.parametrize("field", ["diag", "step", "doc"])
def test_each_required_judgment_below_auto_threshold_reviews(field):
    outcome = decide(make_bundle(**{field: 0.949}))
    assert outcome.action is REVIEW
    assert fired_gate(outcome) == "default_review"
    assert "0.949" in " ".join(outcome.reasons)


def test_contradiction_at_auto_block_threshold_reviews():
    outcome = decide(make_bundle(contra=0.20))
    assert outcome.action is REVIEW
    assert "contradiction" in " ".join(outcome.reasons)


def test_contradiction_below_auto_block_threshold_allows_auto():
    assert decide(make_bundle(contra=0.19)).action is AUTO


def test_contradiction_outranks_missing_information():
    outcome = decide(make_bundle(contra=0.9, doc=0.1, missing="DIAGNOSIS", missing_p=0.9))
    assert fired_gate(outcome) == "contradiction"


def test_age_outranks_contradiction():
    outcome = decide(make_bundle(contra=0.95), age=16)
    assert fired_gate(outcome) == "age"


def test_provider_error_outranks_age():
    outcome = decide(make_bundle(error="boom"), age=16)
    assert fired_gate(outcome) == "provider"


def test_bundle_accessors():
    bundle = make_bundle()
    assert bundle.get(DecisionId.STEP_THERAPY).p_yes == 0.99
    assert bundle.missing_decisions() == []
    empty = DecisionBundle.model_validate({**bundle.model_dump(), "decisions": []})
    assert empty.missing_decisions() == list(DecisionId)


def test_decision_probability_of_selected_answer():
    assert Decision.yes_no(DecisionId.STEP_THERAPY, 0.2, "t").probability == pytest.approx(0.8)
    choice = Decision.choice(DecisionId.MISSING_EVIDENCE, "NONE", {"NONE": 0.7, "DOSAGE": 0.3}, "t")
    assert choice.probability == pytest.approx(0.7)


@pytest.mark.parametrize("bad_value", [1.5, -0.1, float("nan"), float("inf")])
def test_choice_rejects_out_of_range_or_non_finite_probabilities(bad_value):
    with pytest.raises(ValueError, match="probabilit"):
        Decision.choice(DecisionId.MISSING_EVIDENCE, "NONE", {"NONE": bad_value}, "t")
