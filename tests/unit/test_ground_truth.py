from decimal import Decimal

from relay.cases.models import MissingEvidence
from relay.cases.policies import load_policy
from relay.decisions.base import DecisionId
from relay.decisions.ground_truth import GroundTruthProvider, bundle_from_truth
from relay.evaluation.labels import expected_action
from relay.workflow.engine import bundle_problem
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1
from tests.factories import make_case, make_truth

POLICY = load_policy("immunara-v0.1")


def label(case):
    return expected_action(case, POLICY, THRESHOLDS_V0_1)


def test_bundle_from_truth_is_well_formed_and_certain():
    truth = make_truth(step_therapy_satisfied=False)
    bundle = bundle_from_truth("T-01", truth)
    assert bundle_problem(bundle) is None
    assert bundle.get(DecisionId.STEP_THERAPY).p_yes == 0.0
    assert bundle.get(DecisionId.DIAGNOSIS_SUPPORT).p_yes == 1.0
    assert bundle.get(DecisionId.MISSING_EVIDENCE).probability == 1.0
    assert bundle.provider == "groundtruth"
    assert bundle.estimated_cost_usd == Decimal("0")


async def test_provider_decides_from_truth_by_case_id():
    case = make_case("T-07", truth=make_truth(contradiction_present=True))
    provider = GroundTruthProvider({"T-07": case.ground_truth})
    bundle = await provider.decide(case.input)
    assert bundle.case_id == "T-07"
    assert bundle.get(DecisionId.MATERIAL_CONTRADICTION).p_yes == 1.0


def test_all_requirements_met_is_auto_process():
    assert label(make_case()) is WorkflowAction.AUTO_PROCESS


def test_contradiction_is_review():
    assert (
        label(make_case(truth=make_truth(contradiction_present=True)))
        is WorkflowAction.HUMAN_REVIEW
    )


def test_incomplete_documentation_is_request_info():
    truth = make_truth(
        documentation_complete=False, missing_evidence=MissingEvidence.TREATMENT_HISTORY
    )
    assert label(make_case(truth=truth)) is WorkflowAction.REQUEST_INFO


def test_failed_requirement_with_complete_documentation_is_review():
    truth = make_truth(step_therapy_satisfied=False)
    assert label(make_case(truth=truth)) is WorkflowAction.HUMAN_REVIEW


def test_under_age_is_review():
    assert label(make_case(age=16)) is WorkflowAction.HUMAN_REVIEW
