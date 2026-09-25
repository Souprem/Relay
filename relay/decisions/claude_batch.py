"""Claude batch mode (2D spec L7): the Message Batches API at half the sync price.

prepare(), the run_dataset hook, builds one request per case with custom_id = case id, submits
them as one batch (or re-attaches to a batch submitted earlier), polls until the batch has ended,
and converts every result with the same parser as sync mode. Results are keyed by custom_id,
never by position. decide() then returns the stored bundle. Batch bundles have no latency.
"""

import asyncio
import re
from collections.abc import AsyncIterable, Awaitable, Callable, Sequence
from typing import Protocol

from anthropic.types.messages import MessageBatch, MessageBatchIndividualResponse
from anthropic.types.messages.batch_create_params import Request

from relay.cases.models import CaseInput
from relay.cases.policies import AuthorizationPolicy, load_policy
from relay.decisions.base import DecisionBundle
from relay.decisions.claude import (
    PROVIDER_NAME,
    bundle_from_message,
    error_bundle,
    request_params,
)
from relay.decisions.claude_prompt import claude_question_set_version
from relay.decisions.questions import Q_V0_2

POLL_INTERVAL_S = 60.0
_CUSTOM_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class BatchError(Exception):
    """The batch cannot be matched to this run's cases."""


class BatchesClient(Protocol):
    """The part of anthropic.AsyncAnthropic().messages.batches the batch provider uses."""

    async def create(self, *, requests: Sequence[Request]) -> MessageBatch: ...

    async def retrieve(self, message_batch_id: str) -> MessageBatch: ...

    async def results(
        self, message_batch_id: str
    ) -> AsyncIterable[MessageBatchIndividualResponse]: ...


def _request_total(batch: MessageBatch) -> int:
    counts = batch.request_counts
    return counts.processing + counts.succeeded + counts.errored + counts.canceled + counts.expired


class ClaudeBatchProvider:
    name = PROVIDER_NAME

    def __init__(
        self,
        batches: BatchesClient,
        *,
        question_set: str = Q_V0_2,
        policy_loader: Callable[[str], AuthorizationPolicy] = load_policy,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        poll_interval_s: float = POLL_INTERVAL_S,
        batch_id: str | None = None,
        on_submitted: Callable[[str], None] | None = None,
    ) -> None:
        claude_question_set_version(question_set)
        self._batches = batches
        self._question_set = question_set
        self._policy_loader = policy_loader
        self._sleep = sleep
        self._poll_interval_s = poll_interval_s
        self._on_submitted = on_submitted
        self._bundles: dict[str, DecisionBundle] = {}
        self.batch_id = batch_id

    def requests(self, cases: Sequence[CaseInput]) -> list[Request]:
        ids = [case.id for case in cases]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise BatchError(f"duplicate case ids {duplicates}; custom_id must be unique")
        invalid = [i for i in ids if not _CUSTOM_ID.match(i)]
        if invalid:
            raise BatchError(f"case ids {invalid} are not valid batch custom_ids")
        return [
            Request(
                custom_id=case.id,
                params=request_params(
                    case, self._policy_loader(case.policy_id), self._question_set
                ),
            )
            for case in cases
        ]

    async def prepare(self, cases: Sequence[CaseInput]) -> None:
        requests = self.requests(cases)
        if self.batch_id is None:
            batch = await self._batches.create(requests=requests)
            self.batch_id = batch.id
            if self._on_submitted is not None:
                self._on_submitted(batch.id)
        else:
            batch = await self._batches.retrieve(self.batch_id)
        if _request_total(batch) != len(cases):
            raise BatchError(
                f"batch {batch.id} has {_request_total(batch)} requests but this run has "
                f"{len(cases)} cases"
            )
        while batch.processing_status != "ended":
            await self._sleep(self._poll_interval_s)
            batch = await self._batches.retrieve(batch.id)
        by_id = {case.id: case for case in cases}
        bundles: dict[str, DecisionBundle] = {}
        async for item in await self._batches.results(batch.id):
            case = by_id.get(item.custom_id)
            if case is None:
                raise BatchError(
                    f"batch {batch.id} has a result for unknown case {item.custom_id!r}"
                )
            if item.custom_id in bundles:
                raise BatchError(f"batch {batch.id} has two results for case {item.custom_id!r}")
            bundles[item.custom_id] = self._bundle(item, case)
        self._bundles = bundles

    def _bundle(self, item: MessageBatchIndividualResponse, case: CaseInput) -> DecisionBundle:
        policy = self._policy_loader(case.policy_id)
        result = item.result
        if result.type == "succeeded":
            return bundle_from_message(
                result.message, case, policy, mode="batch", question_set=self._question_set
            )
        if result.type == "errored":
            detail = result.error.error
            error = f"batch errored: {detail.type}: {detail.message}"
        else:
            error = f"batch {result.type}: no reply for this case"
        return error_bundle(case.id, policy, error, mode="batch", question_set=self._question_set)

    async def decide(self, case: CaseInput) -> DecisionBundle:
        bundle = self._bundles.get(case.id)
        if bundle is None:
            policy = self._policy_loader(case.policy_id)
            return error_bundle(
                case.id,
                policy,
                "batch: no result for this case",
                mode="batch",
                question_set=self._question_set,
            )
        return bundle
