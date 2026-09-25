"""Case schemas. CaseInput is everything a provider may see; GroundTruth is evaluation-only."""

import hashlib
from datetime import date
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MissingEvidence(StrEnum):
    DIAGNOSIS = "DIAGNOSIS"
    TREATMENT_HISTORY = "TREATMENT_HISTORY"
    LAB_RESULT = "LAB_RESULT"
    DOSAGE = "DOSAGE"
    INSURANCE_INFORMATION = "INSURANCE_INFORMATION"
    NONE = "NONE"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Patient(_Frozen):
    age: int = Field(ge=0, le=120)
    state: str


class MedicationRequest(_Frozen):
    name: str
    indication: str


class Insurance(_Frozen):
    payer: str
    plan: str
    member_id: str | None = None


DocumentKind = Literal[
    "physician_note", "medication_history", "lab_report", "fax_cover", "insurance_card", "other"
]


class Document(_Frozen):
    id: str
    kind: DocumentKind
    text: str


class CaseInput(_Frozen):
    """Everything a DecisionProvider may see. Deliberately has no ground-truth field."""

    id: str
    dataset_id: str
    as_of_date: date
    patient: Patient
    medication: MedicationRequest
    insurance: Insurance
    documents: tuple[Document, ...]
    policy_id: str

    def content_hash(self) -> str:
        canonical = self.model_dump_json()
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class GroundTruth(_Frozen):
    """Author-labelled facts. expected_action is derived from these, never hand-written."""

    diagnosis_supported: bool
    step_therapy_satisfied: bool
    documentation_complete: bool
    contradiction_present: bool
    missing_evidence: MissingEvidence
    notes: str = ""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.missing_evidence != MissingEvidence.NONE and self.documentation_complete:
            raise ValueError(
                "inconsistent ground truth: missing_evidence is set but "
                "documentation_complete is true"
            )
        if not self.documentation_complete and self.missing_evidence == MissingEvidence.NONE:
            raise ValueError(
                "inconsistent ground truth: documentation_complete is false but "
                "missing_evidence is NONE"
            )
        return self


class PriorAuthCase(_Frozen):
    input: CaseInput
    ground_truth: GroundTruth
