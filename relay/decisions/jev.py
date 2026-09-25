"""Jev decision provider: one TypeSafe System One call per case, 12 typed questions.

Jev answers narrow questions; this adapter turns the answers into the five decisions the policy
engine consumes. step_therapy is composed in code from date-part answers (see step_therapy.py).
"""

import math
import time
from collections.abc import Callable, Mapping
from decimal import Decimal
from importlib.metadata import version
from typing import Any, Protocol

from pydantic import ValidationError
from typesafe_sdk import ChoiceAnswer, NoulAnswer, SystemOneResponse, TypeSafeError

from relay.cases.models import CaseInput, MissingEvidence
from relay.cases.policies import AuthorizationPolicy, load_policy
from relay.decisions.base import Decision, DecisionBundle, DecisionId
from relay.decisions.questions import (
    QUESTION_SET_VERSION,
    build_questions,
    candidate_years,
    question_set_hash,
)
from relay.decisions.step_therapy import DateParts, p_duration_at_least

JEV_MODEL = "jev-1.13.0"
PRICE_PER_INPUT_TOKEN_USD = Decimal("0.042") / Decimal(1_000_000)
PROVIDER_NAME = "jev"
CLIENT_VERSION = f"typesafe-sdk=={version('typesafe-sdk')}"


class SystemOneClient(Protocol):
    async def system_one(
        self, state: Any, questions: Mapping[str, Any], *, model: str | None = None
    ) -> SystemOneResponse: ...


class _MalformedResponse(Exception):
    pass


def build_state(case: CaseInput, policy: AuthorizationPolicy) -> dict[str, Any]:
    return {
        "policy": policy.text,
        "request": {
            "as_of_date": case.as_of_date.isoformat(),
            "patient": case.patient.model_dump(mode="json"),
            "medication": case.medication.model_dump(mode="json"),
            "insurance": case.insurance.model_dump(mode="json"),
        },
        "documents": {doc.id: {"kind": doc.kind, "text": doc.text} for doc in case.documents},
    }


def _noul(response: SystemOneResponse, qid: str) -> float:
    answer = response.answers.get(qid)
    if not isinstance(answer, NoulAnswer):
        raise _MalformedResponse(f"{qid}: expected noul answer, got {type(answer).__name__}")
    value = answer.noul
    if not (math.isfinite(value) and 0.0 <= value <= 1.0):
        raise _MalformedResponse(f"{qid}: noul {value!r} is not a finite value in [0, 1]")
    return value


def _choice(response: SystemOneResponse, qid: str) -> ChoiceAnswer:
    answer = response.answers.get(qid)
    if not isinstance(answer, ChoiceAnswer):
        raise _MalformedResponse(f"{qid}: expected choice answer, got {type(answer).__name__}")
    for label, probability in answer.probabilities.items():
        if not (math.isfinite(probability) and 0.0 <= probability <= 1.0):
            raise _MalformedResponse(
                f"{qid}: probability for {label!r} is {probability!r}, not a finite value in [0, 1]"
            )
    return answer


def _date_parts(response: SystemOneResponse, prefix: str) -> DateParts:
    return DateParts(
        month=_choice(response, f"{prefix}_month").probabilities,
        day=_choice(response, f"{prefix}_day").probabilities,
        year=_choice(response, f"{prefix}_year").probabilities,
    )


def _to_decisions(
    response: SystemOneResponse, case: CaseInput, policy: AuthorizationPolicy
) -> tuple[list[Decision], dict[str, Any]]:
    missing = _choice(response, "missing_evidence")
    if missing.choice not in {m.value for m in MissingEvidence}:
        raise _MalformedResponse(f"missing_evidence: unknown label {missing.choice!r}")
    duration = p_duration_at_least(
        start=_date_parts(response, "mtx_start"),
        end_status=_choice(response, "mtx_end_status").probabilities,
        end=_date_parts(response, "mtx_end"),
        as_of=case.as_of_date,
        min_days=policy.min_weeks * 7,
    )
    p_inadequate = _noul(response, "mtx_inadequate_response")
    p_step = duration.p_duration * p_inadequate
    decisions = [
        Decision.yes_no(
            DecisionId.DIAGNOSIS_SUPPORT, _noul(response, "diagnosis_support"), PROVIDER_NAME
        ),
        Decision.yes_no(DecisionId.STEP_THERAPY, p_step, PROVIDER_NAME),
        Decision.yes_no(
            DecisionId.DOCUMENTATION_COMPLETE,
            _noul(response, "documentation_complete"),
            PROVIDER_NAME,
        ),
        Decision.yes_no(
            DecisionId.MATERIAL_CONTRADICTION,
            _noul(response, "material_contradiction"),
            PROVIDER_NAME,
        ),
        Decision.choice(
            DecisionId.MISSING_EVIDENCE,
            missing.choice,
            missing.probabilities,
            PROVIDER_NAME,
            missing.confidence,
        ),
    ]
    derivations = {
        "step_therapy": {
            **duration.to_dict(),
            "p_inadequate_response": p_inadequate,
            "p_yes": p_step,
        }
    }
    return decisions, derivations


class JevProvider:
    name = PROVIDER_NAME

    def __init__(
        self,
        client: SystemOneClient,
        *,
        model: str = JEV_MODEL,
        policy_loader: Callable[[str], AuthorizationPolicy] = load_policy,
    ) -> None:
        self._client = client
        self._model = model
        self._policy_loader = policy_loader

    async def decide(self, case: CaseInput) -> DecisionBundle:
        policy = self._policy_loader(case.policy_id)
        questions = build_questions(policy, candidate_years(case))
        base: dict[str, Any] = {
            "case_id": case.id,
            "provider": self.name,
            "question_set_version": QUESTION_SET_VERSION,
            "question_set_hash": question_set_hash(policy),
            "client_version": CLIENT_VERSION,
        }
        started = time.perf_counter()
        try:
            response = await self._client.system_one(
                state=build_state(case, policy), questions=questions, model=self._model
            )
        except TypeSafeError as error:
            return DecisionBundle(
                **base,
                provider_version=self._model,
                latency_ms=round((time.perf_counter() - started) * 1000),
                error=f"{type(error).__name__}: {error}",
            )
        latency_ms = round((time.perf_counter() - started) * 1000)
        tokens = response.usage.input_tokens
        common: dict[str, Any] = {
            **base,
            "provider_version": response.model,
            "latency_ms": latency_ms,
            "input_tokens": tokens,
            "estimated_cost_usd": PRICE_PER_INPUT_TOKEN_USD * tokens
            if tokens is not None
            else None,
            "raw_answers": {k: a.model_dump(mode="json") for k, a in response.answers.items()},
        }
        try:
            decisions, derivations = _to_decisions(response, case, policy)
        except (_MalformedResponse, ValidationError) as error:
            return DecisionBundle(**common, error=f"malformed response: {error}")
        return DecisionBundle(**common, decisions=decisions, derivations=derivations)
