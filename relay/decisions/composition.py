"""Provider-neutral composition: narrow answers -> the five decisions the policy engine reads.

Jev and Claude answer the same questions. Each adapter maps its own response into an AnswerSet;
compose_decisions validates it, composes step therapy from the date parts in code
(step_therapy.py), and builds the decisions. Only the judgment source differs between providers.

The question set selects the step-therapy path: q-v0.1/q-v0.2 (12 answers) compose one course,
first start -> final end; q-v0.3 (19 answers) composes P(some consecutive segment >= N) from the
interruption answers as well. A policy recency rule (immunara-v0.2) applies on both paths.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from relay.cases.models import CaseInput, MissingEvidence
from relay.cases.policies import AuthorizationPolicy
from relay.decisions.base import Decision, DecisionId
from relay.decisions.questions import Q_V0_2, Q_V0_3, validate_question_set_version
from relay.decisions.step_therapy import DateParts, p_consecutive_at_least, p_duration_at_least

YES_NO_QUESTIONS: tuple[str, ...] = (
    "diagnosis_support",
    "documentation_complete",
    "material_contradiction",
    "mtx_inadequate_response",
)
CHOICE_QUESTIONS: tuple[str, ...] = (
    "missing_evidence",
    "mtx_start_month",
    "mtx_start_day",
    "mtx_start_year",
    "mtx_end_status",
    "mtx_end_month",
    "mtx_end_day",
    "mtx_end_year",
)
YES_NO_QUESTIONS_V0_3: tuple[str, ...] = (*YES_NO_QUESTIONS, "mtx_interrupted")
CHOICE_QUESTIONS_V0_3: tuple[str, ...] = (
    *CHOICE_QUESTIONS,
    "mtx_pause_month",
    "mtx_pause_day",
    "mtx_pause_year",
    "mtx_restart_month",
    "mtx_restart_day",
    "mtx_restart_year",
)
MISSING_EVIDENCE_LABELS: tuple[str, ...] = tuple(m.value for m in MissingEvidence)
# Probability mass a provider assigned to no option (2D spec L4). It is not a month, day, year or
# status, so it contributes no date candidate and no label. It only stops prune() from
# renormalizing a stated answer's probability up to 1.0.
UNASSIGNED = "__unassigned__"


class MalformedAnswers(Exception):
    """An AnswerSet is missing an answer or holds an unusable value."""


@dataclass(frozen=True)
class ChoiceResult:
    answer: str
    probabilities: Mapping[str, float]
    confidence: float | None = None


@dataclass(frozen=True)
class AnswerSet:
    """p_yes per yes/no question id, and answer + distribution per choice question id."""

    yes_no: Mapping[str, float]
    choices: Mapping[str, ChoiceResult]


def single_answer_distribution(answer: str, probability: float) -> dict[str, float]:
    """A stated answer with its probability; the leftover 1 - p goes to UNASSIGNED."""
    rest = 1.0 - probability
    return {answer: probability, UNASSIGNED: rest} if rest > 0 else {answer: probability}


def _check(qid: str, label: str, value: float) -> None:
    if not (math.isfinite(value) and 0.0 <= value <= 1.0):
        raise MalformedAnswers(f"{qid}: {label} {value!r} is not a finite value in [0, 1]")


def _p_yes(answers: AnswerSet, qid: str) -> float:
    if qid not in answers.yes_no:
        raise MalformedAnswers(f"{qid}: no yes/no answer")
    value = answers.yes_no[qid]
    _check(qid, "p_yes", value)
    return value


def _choice(answers: AnswerSet, qid: str) -> ChoiceResult:
    if qid not in answers.choices:
        raise MalformedAnswers(f"{qid}: no choice answer")
    result = answers.choices[qid]
    for label, probability in result.probabilities.items():
        _check(qid, f"probability for {label!r}", probability)
    return result


def question_groups(version: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(yes/no question ids, choice question ids) that a question set's AnswerSet must hold."""
    validate_question_set_version(version)
    if version == Q_V0_3:
        return YES_NO_QUESTIONS_V0_3, CHOICE_QUESTIONS_V0_3
    return YES_NO_QUESTIONS, CHOICE_QUESTIONS


def _date_parts(answers: AnswerSet, prefix: str) -> DateParts:
    return DateParts(
        month=_choice(answers, f"{prefix}_month").probabilities,
        day=_choice(answers, f"{prefix}_day").probabilities,
        year=_choice(answers, f"{prefix}_year").probabilities,
    )


def _duration(
    answers: AnswerSet, case: CaseInput, policy: AuthorizationPolicy, version: str
) -> tuple[float, dict[str, Any]]:
    """P(duration requirement met) and its derivation, on the question set's path."""
    common: dict[str, Any] = {
        "start": _date_parts(answers, "mtx_start"),
        "end_status": _choice(answers, "mtx_end_status").probabilities,
        "end": _date_parts(answers, "mtx_end"),
        "as_of": case.as_of_date,
        "min_days": policy.min_weeks * 7,
        "max_days_since": policy.max_days_since_therapy,
    }
    if version == Q_V0_3:
        segments = p_consecutive_at_least(
            pause=_date_parts(answers, "mtx_pause"),
            restart=_date_parts(answers, "mtx_restart"),
            p_interrupted=_p_yes(answers, "mtx_interrupted"),
            **common,
        )
        return segments.p_duration, segments.to_dict()
    duration = p_duration_at_least(**common)
    return duration.p_duration, duration.to_dict()


def compose_decisions(
    answers: AnswerSet,
    case: CaseInput,
    policy: AuthorizationPolicy,
    provider: str,
    question_set_version: str = Q_V0_2,
) -> tuple[list[Decision], dict[str, Any]]:
    """The five decisions plus derivations["step_therapy"]. Raises MalformedAnswers."""
    validate_question_set_version(question_set_version)
    missing = _choice(answers, "missing_evidence")
    if missing.answer not in MISSING_EVIDENCE_LABELS:
        raise MalformedAnswers(f"missing_evidence: unknown label {missing.answer!r}")
    if missing.answer not in missing.probabilities:
        raise MalformedAnswers(f"missing_evidence: answer {missing.answer!r} has no probability")
    p_duration, duration = _duration(answers, case, policy, question_set_version)
    p_inadequate = _p_yes(answers, "mtx_inadequate_response")
    p_step = p_duration * p_inadequate
    decisions = [
        Decision.yes_no(
            DecisionId.DIAGNOSIS_SUPPORT, _p_yes(answers, "diagnosis_support"), provider
        ),
        Decision.yes_no(DecisionId.STEP_THERAPY, p_step, provider),
        Decision.yes_no(
            DecisionId.DOCUMENTATION_COMPLETE, _p_yes(answers, "documentation_complete"), provider
        ),
        Decision.yes_no(
            DecisionId.MATERIAL_CONTRADICTION, _p_yes(answers, "material_contradiction"), provider
        ),
        Decision.choice(
            DecisionId.MISSING_EVIDENCE,
            missing.answer,
            missing.probabilities,
            provider,
            missing.confidence,
        ),
    ]
    derivations = {
        "step_therapy": {
            **duration,
            "p_inadequate_response": p_inadequate,
            "p_yes": p_step,
        }
    }
    return decisions, derivations
