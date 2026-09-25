"""Shared builders for tests. Every value here is synthetic."""

from datetime import date

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
