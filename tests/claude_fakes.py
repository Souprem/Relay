"""Fake Anthropic responses and clients for the Claude provider tests. Never touches the network.

Messages are built with the SDK's own models, shaped like real replies: an (empty) adaptive
thinking block first, then the JSON text block.
"""

import copy
import json

import anthropic
import httpx2
from anthropic.types import Message
from anthropic.types.messages import MessageBatch, MessageBatchIndividualResponse

# A plausible reply for evals/smoke/AUTO-01 (methotrexate 2026-01-12 -> 2026-06-01, 140 days).
AUTO01_ANSWERS: dict = {
    "diagnosis_support": {"p_yes": 0.97},
    "documentation_complete": {"p_yes": 0.95},
    "material_contradiction": {"p_yes": 0.04},
    "missing_evidence": {
        "DIAGNOSIS": 0.02,
        "TREATMENT_HISTORY": 0.03,
        "LAB_RESULT": 0.01,
        "DOSAGE": 0.01,
        "INSURANCE_INFORMATION": 0.01,
        "NONE": 0.92,
    },
    "mtx_start_month": {"answer": "January", "probability": 0.9},
    "mtx_start_day": {"answer": "12", "probability": 1.0},
    "mtx_start_year": {"answer": "2026", "probability": 1.0},
    "mtx_end_status": {"answer": "ended", "probability": 1.0},
    "mtx_end_month": {"answer": "June", "probability": 1.0},
    "mtx_end_day": {"answer": "1", "probability": 1.0},
    "mtx_end_year": {"answer": "2026", "probability": 1.0},
    "mtx_inadequate_response": {"p_yes": 0.96},
}
USAGE = {
    "input_tokens": 1200,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 1800,
    "output_tokens": 600,
}


def answers(**overrides) -> dict:
    payload = copy.deepcopy(AUTO01_ANSWERS)
    payload.update(overrides)
    return payload


def message(
    payload=None,
    *,
    text: str | None = None,
    stop_reason: str = "end_turn",
    stop_details: dict | None = None,
    model: str = "claude-opus-5",
    usage: dict | None = None,
) -> Message:
    body = text if text is not None else json.dumps(payload if payload is not None else answers())
    content = [{"type": "thinking", "thinking": "", "signature": "sig"}]
    if stop_reason != "refusal":
        content.append({"type": "text", "text": body})
    return Message.model_validate(
        {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "stop_details": stop_details,
            "usage": usage or USAGE,
        }
    )


_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def status_error(status: int) -> anthropic.APIStatusError:
    """The SDK's typed error for an HTTP status (429 -> RateLimitError, 500 -> InternalServerError)."""
    response = httpx2.Response(status, request=_REQUEST)
    classes = {
        400: anthropic.BadRequestError,
        429: anthropic.RateLimitError,
        500: anthropic.InternalServerError,
    }
    return classes.get(status, anthropic.APIStatusError)(
        f"HTTP {status}", response=response, body=None
    )


def connection_error() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(request=_REQUEST)


def response_validation_error() -> anthropic.APIResponseValidationError:
    """A reply the SDK itself could not parse into its expected shape: not a status error or a
    connection error, but still an anthropic.APIError (C7)."""
    response = httpx2.Response(200, request=_REQUEST)
    return anthropic.APIResponseValidationError(response=response, body=None)


class FakeMessages:
    """Stands in for AsyncAnthropic().messages. create() replays scripted outcomes (a Message or
    an exception to raise) in order; the last one repeats."""

    def __init__(self, *outcomes, batches=None):
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []
        self.batches = batches

    async def create(self, **params):
        self.calls.append(params)
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class SleepRecorder:
    def __init__(self):
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def batch(status: str = "in_progress", *, requests: int = 1, batch_id: str = "msgbatch_test"):
    return MessageBatch.model_validate(
        {
            "id": batch_id,
            "type": "message_batch",
            "processing_status": status,
            "created_at": "2026-09-25T00:00:00Z",
            "expires_at": "2026-09-26T00:00:00Z",
            "request_counts": {
                "processing": requests if status != "ended" else 0,
                "succeeded": requests if status == "ended" else 0,
                "errored": 0,
                "canceled": 0,
                "expired": 0,
            },
        }
    )


def succeeded(custom_id: str, msg: Message | None = None) -> MessageBatchIndividualResponse:
    return MessageBatchIndividualResponse.model_validate(
        {
            "custom_id": custom_id,
            "result": {"type": "succeeded", "message": (msg or message()).model_dump()},
        }
    )


def errored(custom_id: str) -> MessageBatchIndividualResponse:
    return MessageBatchIndividualResponse.model_validate(
        {
            "custom_id": custom_id,
            "result": {
                "type": "errored",
                "error": {"type": "error", "error": {"type": "api_error", "message": "overloaded"}},
            },
        }
    )


def expired(custom_id: str) -> MessageBatchIndividualResponse:
    return MessageBatchIndividualResponse.model_validate(
        {"custom_id": custom_id, "result": {"type": "expired"}}
    )


class FakeBatches:
    """Stands in for AsyncAnthropic().messages.batches. Each create()/retrieve() returns the next
    processing status (the last one repeats); results() yields the scripted items in order."""

    def __init__(self, items, *, statuses=("in_progress", "ended"), requests=None):
        self.items = list(items)
        self.statuses = list(statuses)
        self.requests = len(self.items) if requests is None else requests
        self.created: list[list] = []
        self.retrieved: list[str] = []

    def _next(self):
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        if isinstance(status, BaseException):
            raise status
        return batch(status, requests=self.requests)

    async def create(self, *, requests):
        self.created.append(list(requests))
        return self._next()

    async def retrieve(self, message_batch_id):
        self.retrieved.append(message_batch_id)
        return self._next()

    async def results(self, message_batch_id):
        async def stream():
            for item in self.items:
                yield item

        return stream()
