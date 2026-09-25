"""Shared builders for tests. Every value here is synthetic."""

from datetime import date
from decimal import Decimal

from relay.cases.models import (
    CaseInput,
    Document,
    GroundTruth,
    Insurance,
    MedicationRequest,
    MissingEvidence,
    Patient,
    PriorAuthCase,
)
from relay.decisions.base import Decision, DecisionBundle, DecisionId


def make_case_input(
    case_id: str = "T-01",
    *,
    age: int = 40,
    member_id: str | None = "M-0001",
    documents: tuple[Document, ...] | None = None,
    as_of: date = date(2026, 9, 15),
) -> CaseInput:
    return CaseInput(
        id=case_id,
        dataset_id="test",
        as_of_date=as_of,
        patient=Patient(age=age, state="MA"),
        medication=MedicationRequest(name="Immunara", indication="rheumatoid arthritis"),
        insurance=Insurance(payer="ExampleHealth", plan="ExampleHealth Gold", member_id=member_id),
        documents=documents
        or (Document(id="physician_note", kind="physician_note", text="Synthetic note."),),
        policy_id="immunara-v0.1",
    )


def make_truth(**overrides: object) -> GroundTruth:
    values: dict[str, object] = {
        "diagnosis_supported": True,
        "step_therapy_satisfied": True,
        "documentation_complete": True,
        "contradiction_present": False,
        "missing_evidence": MissingEvidence.NONE,
    }
    values.update(overrides)
    return GroundTruth.model_validate(values)


def make_case(
    case_id: str = "T-01", *, truth: GroundTruth | None = None, age: int = 40
) -> PriorAuthCase:
    return PriorAuthCase(
        input=make_case_input(case_id, age=age), ground_truth=truth or make_truth()
    )


def make_bundle(
    case_id: str = "T-01",
    *,
    diag: float = 0.99,
    step: float = 0.99,
    doc: float = 0.99,
    contra: float = 0.01,
    missing: str = "NONE",
    missing_p: float = 0.9,
    error: str | None = None,
    latency_ms: int = 100,
    cost: Decimal | None = Decimal("0.00001"),
    provider: str = "test",
) -> DecisionBundle:
    decisions = (
        []
        if error
        else [
            Decision.yes_no(DecisionId.DIAGNOSIS_SUPPORT, diag, provider),
            Decision.yes_no(DecisionId.STEP_THERAPY, step, provider),
            Decision.yes_no(DecisionId.DOCUMENTATION_COMPLETE, doc, provider),
            Decision.yes_no(DecisionId.MATERIAL_CONTRADICTION, contra, provider),
            Decision.choice(
                DecisionId.MISSING_EVIDENCE, missing, {missing: missing_p}, provider, missing_p
            ),
        ]
    )
    return DecisionBundle(
        case_id=case_id,
        decisions=decisions,
        provider=provider,
        provider_version="test-v1",
        question_set_version="q-test",
        question_set_hash="sha256:test",
        latency_ms=latency_ms,
        input_tokens=100,
        estimated_cost_usd=cost,
        error=error,
    )
