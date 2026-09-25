"""Ground-truth provider: a test fixture and pipeline check. Its output is NOT a model result."""

from collections.abc import Mapping
from decimal import Decimal

from relay.cases.models import CaseInput, GroundTruth
from relay.decisions.base import Decision, DecisionBundle, DecisionId

PROVIDER_NAME = "groundtruth"


def _certain(flag: bool) -> float:
    return 1.0 if flag else 0.0


def bundle_from_truth(case_id: str, truth: GroundTruth) -> DecisionBundle:
    missing = truth.missing_evidence.value
    decisions = [
        Decision.yes_no(
            DecisionId.DIAGNOSIS_SUPPORT, _certain(truth.diagnosis_supported), PROVIDER_NAME
        ),
        Decision.yes_no(
            DecisionId.STEP_THERAPY, _certain(truth.step_therapy_satisfied), PROVIDER_NAME
        ),
        Decision.yes_no(
            DecisionId.DOCUMENTATION_COMPLETE, _certain(truth.documentation_complete), PROVIDER_NAME
        ),
        Decision.yes_no(
            DecisionId.MATERIAL_CONTRADICTION, _certain(truth.contradiction_present), PROVIDER_NAME
        ),
        Decision.choice(DecisionId.MISSING_EVIDENCE, missing, {missing: 1.0}, PROVIDER_NAME, 1.0),
    ]
    return DecisionBundle(
        case_id=case_id,
        decisions=decisions,
        provider=PROVIDER_NAME,
        provider_version="groundtruth-v1",
        question_set_version="groundtruth",
        question_set_hash="n/a",
        latency_ms=0,
        input_tokens=0,
        estimated_cost_usd=Decimal("0"),
    )


class GroundTruthProvider:
    """Emits certain judgments from labels. Use only to validate the pipeline or in tests."""

    name = PROVIDER_NAME

    def __init__(self, truths: Mapping[str, GroundTruth]) -> None:
        self._truths = dict(truths)

    async def decide(self, case: CaseInput) -> DecisionBundle:
        return bundle_from_truth(case.id, self._truths[case.id])
