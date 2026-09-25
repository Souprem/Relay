from pathlib import Path

import pytest

from relay.cases.loader import load_case
from relay.cases.policies import load_policy
from relay.decisions.claude import RETRY_DELAY_S, ClaudeProvider, request_params
from relay.workflow.engine import bundle_problem
from tests.claude_fakes import (
    FakeMessages,
    SleepRecorder,
    connection_error,
    message,
    status_error,
)

REPO = Path(__file__).resolve().parents[2]
AUTO01 = load_case(REPO / "evals" / "smoke" / "AUTO-01")


async def decide(*outcomes):
    messages, sleep = FakeMessages(*outcomes), SleepRecorder()
    bundle = await ClaudeProvider(messages, sleep=sleep).decide(AUTO01.input)
    return bundle, messages, sleep


async def test_decide_sends_the_request_params_and_measures_latency():
    bundle, messages, sleep = await decide(message())
    assert messages.calls == [request_params(AUTO01.input, load_policy("immunara-v0.1"))]
    assert bundle_problem(bundle) is None
    assert isinstance(bundle.latency_ms, int) and bundle.latency_ms >= 0
    assert bundle.derivations["execution"]["mode"] == "sync"
    assert sleep.delays == []


@pytest.mark.parametrize("first", [status_error(500), status_error(429), connection_error()])
async def test_a_retryable_error_gets_one_more_attempt(first):
    bundle, messages, sleep = await decide(first, message())
    assert bundle.error is None
    assert len(messages.calls) == 2
    assert sleep.delays == [RETRY_DELAY_S]


@pytest.mark.parametrize(
    "error, name",
    [
        (status_error(429), "RateLimitError"),
        (status_error(500), "InternalServerError"),
        (connection_error(), "APIConnectionError"),
    ],
)
async def test_a_retryable_error_twice_becomes_an_error_bundle(error, name):
    bundle, messages, _ = await decide(error, error)
    assert bundle.decisions == []
    assert bundle.error.startswith(f"{name}: ")
    assert len(messages.calls) == 2
    assert isinstance(bundle.latency_ms, int)


async def test_a_client_error_is_final_at_once():
    bundle, messages, sleep = await decide(status_error(400))
    assert bundle.error.startswith("BadRequestError: ")
    assert len(messages.calls) == 1 and sleep.delays == []


async def test_a_non_anthropic_exception_propagates():
    with pytest.raises(ValueError, match="bug"):
        await decide(ValueError("bug"))


async def test_a_refusal_reply_becomes_an_error_bundle():
    bundle, _, _ = await decide(message(stop_reason="refusal"))
    assert bundle.error.startswith("refusal")
    assert bundle.derivations["stop_reason"] == "refusal"


def test_unknown_question_set_is_rejected_at_construction():
    with pytest.raises(ValueError, match="q-v0.1"):
        ClaudeProvider(FakeMessages(message()), question_set="q-v0.1")
