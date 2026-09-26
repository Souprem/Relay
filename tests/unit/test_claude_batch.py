from decimal import Decimal

import pytest

from relay.cases.policies import load_policy
from relay.decisions.base import DecisionId, PreparingProvider
from relay.decisions.claude import request_params
from relay.decisions.claude_batch import POLL_INTERVAL_S, BatchError, ClaudeBatchProvider
from relay.evaluation.runner import run_dataset
from relay.traces.store import TraceStore
from tests.claude_fakes import (
    FakeBatches,
    SleepRecorder,
    answers,
    connection_error,
    errored,
    expired,
    message,
    status_error,
    succeeded,
)
from tests.factories import make_case, make_case_input

POLICY = load_policy("immunara-v0.1")
A, B = make_case_input("A"), make_case_input("B")


def provider(batches, **kwargs):
    sleep = SleepRecorder()
    return ClaudeBatchProvider(batches, sleep=sleep, **kwargs), sleep


def test_the_batch_provider_implements_the_prepare_hook():
    assert isinstance(provider(FakeBatches([]))[0], PreparingProvider)


def test_requests_use_the_case_id_as_custom_id_and_the_sync_params():
    batch_provider, _ = provider(FakeBatches([]))
    requests = batch_provider.requests([A, B])
    assert [r["custom_id"] for r in requests] == ["A", "B"]
    assert requests[0]["params"] == request_params(A, POLICY)


def test_duplicate_or_invalid_custom_ids_are_rejected():
    batch_provider, _ = provider(FakeBatches([]))
    with pytest.raises(BatchError, match="duplicate"):
        batch_provider.requests([A, make_case_input("A")])
    with pytest.raises(BatchError, match="not valid"):
        batch_provider.requests([make_case_input("bad id!")])


async def test_prepare_submits_once_polls_until_ended_and_keys_results_by_custom_id():
    low = message(answers(diagnosis_support={"p_yes": 0.1}))
    batches = FakeBatches(
        [succeeded("B", low), succeeded("A")],  # out of order on purpose
        statuses=("in_progress", "in_progress", "ended"),
    )
    submitted = []
    batch_provider, sleep = provider(batches, on_submitted=submitted.append)
    await batch_provider.prepare([A, B])
    assert [[r["custom_id"] for r in call] for call in batches.created] == [["A", "B"]]
    assert submitted == ["msgbatch_test"] and batch_provider.batch_id == "msgbatch_test"
    assert sleep.delays == [POLL_INTERVAL_S, POLL_INTERVAL_S]
    assert batches.retrieved == ["msgbatch_test", "msgbatch_test"]
    a, b = await batch_provider.decide(A), await batch_provider.decide(B)
    assert a.get(DecisionId.DIAGNOSIS_SUPPORT).p_yes == 0.97
    assert b.get(DecisionId.DIAGNOSIS_SUPPORT).p_yes == 0.1


async def test_batch_bundles_have_no_latency_and_the_batch_price():
    batch_provider, _ = provider(FakeBatches([succeeded("A")], statuses=("ended",)))
    await batch_provider.prepare([A])
    bundle = await batch_provider.decide(A)
    assert bundle.error is None
    assert bundle.latency_ms is None
    assert bundle.derivations["execution"]["mode"] == "batch"
    assert bundle.estimated_cost_usd == Decimal("0.01095")  # half of the sync $0.0219


async def test_errored_expired_and_missing_results_become_error_bundles():
    C = make_case_input("C")
    batch_provider, _ = provider(
        FakeBatches([errored("A"), expired("B")], statuses=("ended",), requests=3)
    )
    await batch_provider.prepare([A, B, C])
    a, b, c = [await batch_provider.decide(x) for x in (A, B, C)]
    assert a.error == "batch errored: api_error: overloaded"
    assert b.error == "batch expired: no reply for this case"
    assert c.error == "batch: no result for this case"
    for bundle in (a, b, c):
        assert bundle.decisions == [] and bundle.latency_ms is None
        assert bundle.derivations["execution"]["mode"] == "batch"


async def test_an_unknown_or_repeated_custom_id_is_a_batch_error():
    batch_provider, _ = provider(FakeBatches([succeeded("Z")], statuses=("ended",)))
    with pytest.raises(BatchError, match="unknown case 'Z'"):
        await batch_provider.prepare([A])
    batch_provider, _ = provider(
        FakeBatches([succeeded("A"), succeeded("A")], statuses=("ended",), requests=1)
    )
    with pytest.raises(BatchError, match="two results"):
        await batch_provider.prepare([A])


async def test_a_batch_whose_size_differs_from_the_run_is_refused():
    batch_provider, _ = provider(FakeBatches([succeeded("A")], statuses=("ended",), requests=400))
    with pytest.raises(BatchError, match="400 requests but this run has 1 cases"):
        await batch_provider.prepare([A])


async def test_resuming_an_existing_batch_does_not_submit_again():
    batches = FakeBatches([succeeded("A")], statuses=("ended",))
    batch_provider, _ = provider(batches, batch_id="msgbatch_test")
    await batch_provider.prepare([A])
    assert batches.created == []
    assert batches.retrieved == ["msgbatch_test"]
    assert (await batch_provider.decide(A)).error is None


async def test_run_dataset_traces_batch_results_like_sync_results(tmp_path):
    cases = [make_case("A"), make_case("B")]
    batch_provider, _ = provider(FakeBatches([succeeded("B"), succeeded("A")], statuses=("ended",)))
    store = TraceStore.create(tmp_path, "run_b")
    traces = await run_dataset(
        cases, batch_provider, policy_version="v0.1", store=store, run_id="run_b"
    )
    assert [t.case_id for t in traces] == ["A", "B"]
    assert {t.provider for t in traces} == {"claude"}
    assert {t.question_set_version for t in traces} == {"q-v0.2+claude-prompt-v1"}
    assert all(t.decisions.latency_ms is None for t in traces)


async def test_batch_creation_can_use_a_separate_client_than_polling(tmp_path=None):
    """C2: the caller (the CLI) wires create() to a max_retries=0 client so a submission that
    might have reached the server is never silently retried; retrieve()/results() stay on the
    normal client. Verify the provider actually calls create() on the client it was given for
    that purpose, not the polling one."""
    create_batches = FakeBatches([succeeded("A")], statuses=("ended",))
    poll_batches = FakeBatches([succeeded("A")], statuses=("ended",))
    batch_provider, _ = provider(poll_batches, create_batches=create_batches)
    await batch_provider.prepare([A])
    assert len(create_batches.created) == 1
    assert poll_batches.created == []


async def test_prepare_uses_the_polling_client_by_default_when_none_is_given():
    batches = FakeBatches([succeeded("A")], statuses=("ended",))
    batch_provider, _ = provider(batches)
    await batch_provider.prepare([A])
    assert len(batches.created) == 1


@pytest.mark.parametrize("error", [connection_error(), status_error(500), status_error(429)])
async def test_poll_loop_tolerates_transient_retrieve_errors_and_keeps_polling(error):
    """C5/M3: a dropped connection, a 5xx, or a 429 while polling a multi-hour batch must not
    lose the run; the loop just tries again on the next interval (which is itself a natural
    backoff for a rate limit)."""
    batches = FakeBatches([succeeded("A")], statuses=("in_progress", error, "ended"), requests=1)
    batch_provider, sleep = provider(batches)
    await batch_provider.prepare([A])
    assert (await batch_provider.decide(A)).error is None
    assert batches.retrieved == ["msgbatch_test", "msgbatch_test"]
    assert sleep.delays == [POLL_INTERVAL_S, POLL_INTERVAL_S]


async def test_poll_loop_does_not_tolerate_a_4xx_on_retrieve():
    """A 4xx (e.g. the batch id being wrong) is not transient; it must still raise rather than
    poll forever."""
    batches = FakeBatches(
        [succeeded("A")], statuses=("in_progress", status_error(400), "ended"), requests=1
    )
    batch_provider, _ = provider(batches)
    with pytest.raises(Exception, match="HTTP 400"):
        await batch_provider.prepare([A])
