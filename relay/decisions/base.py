"""Typed judgments returned by decision providers. Providers never return workflow actions."""

import math
from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from relay.cases.models import CaseInput


class DecisionId(StrEnum):
    DIAGNOSIS_SUPPORT = "diagnosis_support"
    STEP_THERAPY = "step_therapy"
    DOCUMENTATION_COMPLETE = "documentation_complete"
    MATERIAL_CONTRADICTION = "material_contradiction"
    MISSING_EVIDENCE = "missing_evidence"


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)

    question_id: DecisionId
    kind: Literal["yes_no", "choice"]
    p_yes: float | None = Field(default=None, ge=0.0, le=1.0)
    answer: str | None = None
    probabilities: dict[str, float] = Field(default_factory=dict)
    confidence: float | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    provider: str

    @field_validator("probabilities")
    @classmethod
    def _validate_probabilities(cls, value: dict[str, float]) -> dict[str, float]:
        for label, probability in value.items():
            if not math.isfinite(probability) or not (0.0 <= probability <= 1.0):
                raise ValueError(
                    f"probability for {label!r} must be finite and within [0, 1], got {probability}"
                )
        return value

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if self.kind == "yes_no" and self.p_yes is None:
            raise ValueError("yes_no decision requires p_yes")
        if self.kind == "choice" and self.answer is None:
            raise ValueError("choice decision requires answer")
        return self

    @property
    def probability(self) -> float:
        """Probability of the selected answer."""
        if self.kind == "yes_no":
            assert self.p_yes is not None
            return max(self.p_yes, 1.0 - self.p_yes)
        assert self.answer is not None
        return self.probabilities.get(self.answer, 0.0)

    @classmethod
    def yes_no(cls, question_id: DecisionId, p_yes: float, provider: str) -> Self:
        return cls(question_id=question_id, kind="yes_no", p_yes=p_yes, provider=provider)

    @classmethod
    def choice(
        cls,
        question_id: DecisionId,
        answer: str,
        probabilities: Mapping[str, float],
        provider: str,
        confidence: float | None = None,
    ) -> Self:
        return cls(
            question_id=question_id,
            kind="choice",
            answer=answer,
            probabilities=dict(probabilities),
            confidence=confidence,
            provider=provider,
        )


class DecisionBundle(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    decisions: list[Decision] = Field(default_factory=list)
    raw_answers: dict[str, Any] = Field(default_factory=dict)
    derivations: dict[str, Any] = Field(default_factory=dict)
    provider: str
    provider_version: str
    question_set_version: str
    question_set_hash: str
    latency_ms: int
    input_tokens: int | None = None
    estimated_cost_usd: Decimal | None = None
    error: str | None = None

    def get(self, question_id: DecisionId) -> Decision | None:
        return next((d for d in self.decisions if d.question_id == question_id), None)

    def missing_decisions(self) -> list[DecisionId]:
        present = {d.question_id for d in self.decisions}
        return [q for q in DecisionId if q not in present]


class DecisionProvider(Protocol):
    name: str

    async def decide(self, case: CaseInput) -> DecisionBundle: ...
