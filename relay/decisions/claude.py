"""Claude baseline (2D): one structured-output Messages API request per case.

Claude answers the same 12 questions as Jev in one JSON object (claude_prompt.py). This module
builds the request, parses the reply into an AnswerSet, and lets composition.py build the same
five decisions, so the judgment source is the only difference from Jev.

Refusal fallbacks are deliberately NOT enabled (2D spec L6): the Batches API rejects the
`fallbacks` parameter, and a silent switch to another model would change what this baseline
measures. A refusal or a truncated reply becomes an error bundle, which the engine routes to
HUMAN_REVIEW.
"""

import asyncio
import json
import math
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from decimal import Decimal
from importlib.metadata import version
from typing import Any, Literal, Protocol

import anthropic
from anthropic.types import Message, Usage
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from pydantic import ValidationError

from relay.cases.models import CaseInput
from relay.cases.policies import AuthorizationPolicy, load_policy
from relay.decisions.base import DecisionBundle
from relay.decisions.claude_prompt import (
    case_schema,
    claude_question_set_hash,
    claude_question_set_version,
    render_system_prompt,
    user_message,
)
from relay.decisions.composition import (
    CHOICE_QUESTIONS,
    MISSING_EVIDENCE_LABELS,
    YES_NO_QUESTIONS,
    AnswerSet,
    ChoiceResult,
    MalformedAnswers,
    compose_decisions,
    single_answer_distribution,
)
from relay.decisions.questions import Q_V0_2, QUESTION_IDS

CLAUDE_MODEL = "claude-opus-5"
PROVIDER_NAME = "claude"
EFFORT = "low"
MAX_TOKENS = 4096
CLIENT_VERSION = f"anthropic=={version('anthropic')}"
# List prices in USD per 1M tokens (claude-api skill, shared/models.md and
# shared/prompt-caching.md), as of PRICES_AS_OF. Cache writes use the 5-minute TTL.
PRICES_AS_OF = "2026-09-25"
INPUT_USD_PER_MTOK = Decimal("5.00")
OUTPUT_USD_PER_MTOK = Decimal("25.00")
CACHE_WRITE_MULTIPLIER = Decimal("1.25")
CACHE_READ_MULTIPLIER = Decimal("0.1")
BATCH_DISCOUNT = Decimal("0.5")
# The six missing-evidence probabilities are normalized in code, but a set that sums far from 1
# means the model did not give a distribution, so it is rejected instead.
MISSING_EVIDENCE_SUM_TOLERANCE = 0.1
Mode = Literal["sync", "batch"]
# The SDK already retries 429, >= 500 and connection errors twice (max_retries=2); the provider
# adds one more attempt after this pause before giving up on a case (2D spec L10).
RETRY_DELAY_S = 5.0


class ClaudeResponseError(Exception):
    """Claude's JSON reply cannot be turned into an AnswerSet."""


def request_params(
    case: CaseInput, policy: AuthorizationPolicy, question_set: str = Q_V0_2
) -> MessageCreateParamsNonStreaming:
    """One request. No `thinking` parameter: Opus 5 runs adaptive thinking by default (L2)."""
    return MessageCreateParamsNonStreaming(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": render_system_prompt(policy, question_set),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message(case, policy)}],
        output_config={
            "effort": EFFORT,
            "format": {"type": "json_schema", "schema": case_schema(case, policy, question_set)},
        },
    )


def usage_counts(usage: Usage) -> dict[str, int]:
    return {
        "input_tokens": usage.input_tokens or 0,
        "cache_creation_input_tokens": usage.cache_creation_input_tokens or 0,
        "cache_read_input_tokens": usage.cache_read_input_tokens or 0,
        "output_tokens": usage.output_tokens or 0,
    }


def estimate_cost_usd(counts: Mapping[str, int], mode: Mode) -> Decimal:
    per_input = INPUT_USD_PER_MTOK / Decimal(1_000_000)
    cost = (
        counts["input_tokens"] * per_input
        + counts["cache_creation_input_tokens"] * per_input * CACHE_WRITE_MULTIPLIER
        + counts["cache_read_input_tokens"] * per_input * CACHE_READ_MULTIPLIER
        + counts["output_tokens"] * OUTPUT_USD_PER_MTOK / Decimal(1_000_000)
    )
    return cost * BATCH_DISCOUNT if mode == "batch" else cost


def execution_record(mode: Mode) -> dict[str, Any]:
    """derivations["execution"]: the settings this bundle ran with."""
    return {
        "mode": mode,
        "effort": EFFORT,
        "max_tokens": MAX_TOKENS,
        "model_requested": CLAUDE_MODEL,
    }


def _number(qid: str, field: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ClaudeResponseError(f"{qid}.{field}: expected a number, got {value!r}")
    number = float(value)
    if not (math.isfinite(number) and 0.0 <= number <= 1.0):
        raise ClaudeResponseError(f"{qid}.{field}: {number!r} is not a finite value in [0, 1]")
    return number


def _fields(payload: Mapping[str, Any], qid: str, expected: Sequence[str]) -> Mapping[str, Any]:
    node = payload.get(qid)
    if not isinstance(node, dict) or set(node) != set(expected):
        raise ClaudeResponseError(f"{qid}: expected an object with keys {sorted(expected)}")
    return node


def parse_answers(payload: Any, schema: Mapping[str, Any]) -> tuple[AnswerSet, dict[str, Any]]:
    """Validate Claude's JSON against the question contract and map it into an AnswerSet.

    A choice answer with probability p becomes {answer: p, UNASSIGNED: 1 - p} (L4). The six
    missing-evidence probabilities are normalized to sum to 1; the top label is the answer (ties
    go to the earlier label). Returns the AnswerSet and a record of the normalization.
    """
    if not isinstance(payload, dict):
        raise ClaudeResponseError("the reply is not a JSON object")
    unexpected = sorted(set(payload) - set(QUESTION_IDS))
    if unexpected:
        raise ClaudeResponseError(f"unexpected keys {unexpected}")
    yes_no = {
        qid: _number(qid, "p_yes", _fields(payload, qid, ["p_yes"])["p_yes"])
        for qid in YES_NO_QUESTIONS
    }
    choices: dict[str, ChoiceResult] = {}
    for qid in CHOICE_QUESTIONS:
        if qid == "missing_evidence":
            continue
        node = _fields(payload, qid, ["answer", "probability"])
        options = schema["properties"][qid]["properties"]["answer"]["enum"]
        if node["answer"] not in options:
            raise ClaudeResponseError(f"{qid}: answer {node['answer']!r} is not an option")
        probability = _number(qid, "probability", node["probability"])
        choices[qid] = ChoiceResult(
            node["answer"], single_answer_distribution(node["answer"], probability), probability
        )
    raw = _fields(payload, "missing_evidence", MISSING_EVIDENCE_LABELS)
    values = {label: _number("missing_evidence", label, raw[label]) for label in raw}
    total = sum(values.values())
    if abs(total - 1.0) > MISSING_EVIDENCE_SUM_TOLERANCE:
        raise ClaudeResponseError(
            f"missing_evidence: probabilities sum to {total:.3f}, not 1 "
            f"(tolerance {MISSING_EVIDENCE_SUM_TOLERANCE})"
        )
    probabilities = {label: values[label] / total for label in MISSING_EVIDENCE_LABELS}
    answer = max(MISSING_EVIDENCE_LABELS, key=lambda label: probabilities[label])
    choices["missing_evidence"] = ChoiceResult(answer, probabilities, probabilities[answer])
    return AnswerSet(yes_no=yes_no, choices=choices), {"raw_sum": total}


def _identity(case_id: str, policy: AuthorizationPolicy, question_set: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "provider": PROVIDER_NAME,
        "question_set_version": claude_question_set_version(question_set),
        "question_set_hash": claude_question_set_hash(policy, question_set),
        "client_version": CLIENT_VERSION,
    }


def error_bundle(
    case_id: str,
    policy: AuthorizationPolicy,
    error: str,
    *,
    mode: Mode,
    question_set: str = Q_V0_2,
    latency_ms: int | None = None,
) -> DecisionBundle:
    """A request that produced no message (API error, errored or expired batch entry).

    Such a request is not billed, so its cost is 0 rather than unknown.
    """
    return DecisionBundle(
        **_identity(case_id, policy, question_set),
        provider_version=CLAUDE_MODEL,
        latency_ms=latency_ms,
        input_tokens=0,
        estimated_cost_usd=Decimal("0"),
        derivations={"execution": execution_record(mode)},
        error=error,
    )


def bundle_from_message(
    message: Message,
    case: CaseInput,
    policy: AuthorizationPolicy,
    *,
    mode: Mode,
    question_set: str = Q_V0_2,
    latency_ms: int | None = None,
) -> DecisionBundle:
    counts = usage_counts(message.usage)
    derivations: dict[str, Any] = {
        "execution": execution_record(mode),
        "usage": counts,
        "stop_reason": message.stop_reason,
    }
    common: dict[str, Any] = {
        **_identity(case.id, policy, question_set),
        "provider_version": message.model,
        "latency_ms": latency_ms,
        "input_tokens": counts["input_tokens"]
        + counts["cache_creation_input_tokens"]
        + counts["cache_read_input_tokens"],
        "estimated_cost_usd": estimate_cost_usd(counts, mode),
    }
    if message.stop_reason == "refusal":
        details = message.stop_details
        category = f" (category {details.category})" if details and details.category else ""
        error = f"refusal: Claude declined to answer{category}"
        return DecisionBundle(**common, derivations=derivations, error=error)
    if message.stop_reason == "max_tokens":
        error = f"max_tokens: the reply was cut off at {MAX_TOKENS} output tokens"
        return DecisionBundle(**common, derivations=derivations, error=error)
    if message.stop_reason != "end_turn":
        error = f"unexpected stop_reason {message.stop_reason!r}"
        return DecisionBundle(**common, derivations=derivations, error=error)
    text = next((block.text for block in message.content if block.type == "text"), None)
    if text is None:
        return DecisionBundle(
            **common, derivations=derivations, error="malformed response: no text block"
        )
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        return DecisionBundle(
            **common,
            raw_answers={"text": text},
            derivations=derivations,
            error=f"malformed response: invalid JSON ({error})",
        )
    common["raw_answers"] = payload if isinstance(payload, dict) else {"value": payload}
    try:
        answers, normalization = parse_answers(payload, case_schema(case, policy, question_set))
        decisions, composed = compose_decisions(answers, case, policy, PROVIDER_NAME)
    except (ClaudeResponseError, MalformedAnswers, ValidationError) as error:
        return DecisionBundle(
            **common, derivations=derivations, error=f"malformed response: {error}"
        )
    derivations |= composed
    derivations["missing_evidence"] = normalization
    return DecisionBundle(**common, decisions=decisions, derivations=derivations)


class MessagesClient(Protocol):
    """The part of anthropic.AsyncAnthropic().messages the sync provider uses."""

    async def create(self, **params: Any) -> Message: ...


class ClaudeProvider:
    """Sync mode: one awaited Messages API request per case, latency measured."""

    name = PROVIDER_NAME

    def __init__(
        self,
        messages: MessagesClient,
        *,
        question_set: str = Q_V0_2,
        policy_loader: Callable[[str], AuthorizationPolicy] = load_policy,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        retry_delay_s: float = RETRY_DELAY_S,
    ) -> None:
        claude_question_set_version(question_set)
        self._messages = messages
        self._question_set = question_set
        self._policy_loader = policy_loader
        self._sleep = sleep
        self._retry_delay_s = retry_delay_s

    async def _create(self, params: MessageCreateParamsNonStreaming) -> Message:
        """Most specific error first. Other 4xx errors are final at once; anything that is not
        an Anthropic API error propagates."""
        for attempt in (1, 2):
            try:
                return await self._messages.create(**params)
            except anthropic.RateLimitError:
                if attempt == 2:
                    raise
            except anthropic.APIStatusError as error:
                if error.status_code < 500 or attempt == 2:
                    raise
            except anthropic.APIConnectionError:
                if attempt == 2:
                    raise
            await self._sleep(self._retry_delay_s)
        raise AssertionError("unreachable")

    async def decide(self, case: CaseInput) -> DecisionBundle:
        policy = self._policy_loader(case.policy_id)
        params = request_params(case, policy, self._question_set)
        started = time.perf_counter()
        try:
            message = await self._create(params)
        except (
            anthropic.RateLimitError,
            anthropic.APIStatusError,
            anthropic.APIConnectionError,
        ) as error:
            return error_bundle(
                case.id,
                policy,
                f"{type(error).__name__}: {error}",
                mode="sync",
                question_set=self._question_set,
                latency_ms=round((time.perf_counter() - started) * 1000),
            )
        return bundle_from_message(
            message,
            case,
            policy,
            mode="sync",
            question_set=self._question_set,
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
