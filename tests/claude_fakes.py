"""Fake Anthropic responses and clients for the Claude provider tests. Never touches the network.

Messages are built with the SDK's own models, shaped like real replies: an (empty) adaptive
thinking block first, then the JSON text block.
"""

import copy
import json

import anthropic
import httpx2
from anthropic.types import Message

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
