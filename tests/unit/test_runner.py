import asyncio
import hashlib

import pytest

from relay.cases.models import CaseInput, PriorAuthCase
from relay.cases.policies import load_policy
from relay.decisions.ground_truth import GroundTruthProvider
from relay.evaluation.runner import (
    RunConfigError,
    policy_text_hash,
    run_dataset,
    validate_run_config,
)
from relay.traces.store import TraceStore, read_traces
from relay.workflow.outcomes import WorkflowAction
from tests.factories import make_case, make_truth


class SpyProvider:
    name = "spy"

    def __init__(self, cases):
        self._inner = GroundTruthProvider({c.input.id: c.ground_truth for c in cases})
        self.seen_types = []
        self.active = 0
        self.max_active = 0

    async def decide(self, case):
        self.seen_types.append(type(case))
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return await self._inner.decide(case)


def cases():
    return [
        make_case("T-01"),
        make_case("T-02", truth=make_truth(contradiction_present=True)),
        make_case("T-03", age=16),
    ]


async def test_run_dataset_writes_one_trace_per_case_in_order(tmp_path):
    data = cases()
    store = TraceStore.create(tmp_path, "run_t")
    traces = await run_dataset(
        data, SpyProvider(data), policy_version="v0.1", store=store, run_id="run_t", git_sha="abc"
    )
    assert [t.case_id for t in traces] == ["T-01", "T-02", "T-03"]
    assert [t.action for t in traces] == [
        WorkflowAction.AUTO_PROCESS,
        WorkflowAction.HUMAN_REVIEW,
        WorkflowAction.HUMAN_REVIEW,
    ]
    assert sorted(t.case_id for t in read_traces(store.path)) == ["T-01", "T-02", "T-03"]
    first = traces[0]
    assert first.run_id == "run_t" and first.relay_git_sha == "abc"
    assert first.policy_id == "immunara-v0.1" and first.policy_version == "v0.1"
    assert first.case_content_hash == data[0].input.content_hash()
    assert first.gate_path[-1].gate == "auto_process"


async def test_provider_receives_case_input_only(tmp_path):
    data = cases()
    spy = SpyProvider(data)
    await run_dataset(
        data, spy, policy_version="v0.1", store=TraceStore.create(tmp_path, "r"), run_id="r"
    )
    assert spy.seen_types == [CaseInput] * 3
    assert PriorAuthCase not in spy.seen_types


async def test_concurrency_limit_is_respected(tmp_path):
    data = [make_case(f"T-{i:02d}") for i in range(8)]
    spy = SpyProvider(data)
    await run_dataset(
        data,
        spy,
        policy_version="v0.1",
        store=TraceStore.create(tmp_path, "r"),
        run_id="r",
        concurrency=2,
    )
    assert spy.max_active <= 2


def test_validate_run_config_rejects_wrong_policy_version():
    with pytest.raises(RunConfigError, match="v9"):
        validate_run_config(cases(), "v9")


def test_validate_run_config_rejects_unknown_policy():
    bad = make_case("T-01")
    bad = bad.model_copy(update={"input": bad.input.model_copy(update={"policy_id": "nope"})})
    with pytest.raises(RunConfigError, match="nope"):
        validate_run_config([bad], "v0.1")


async def test_bad_config_fails_before_any_provider_call(tmp_path):
    data = cases()
    spy = SpyProvider(data)
    with pytest.raises(RunConfigError):
        await run_dataset(
            data, spy, policy_version="v9", store=TraceStore.create(tmp_path, "r"), run_id="r"
        )
    assert spy.seen_types == []


def test_policy_text_hash_is_sha256_of_the_policy_text():
    policy = load_policy("immunara-v0.1")
    expected = "sha256:" + hashlib.sha256(policy.text.encode("utf-8")).hexdigest()
    assert policy_text_hash(policy) == expected
    # Pinned: editing policies/immunara-v0.1.md without a new policy version breaks this.
    assert expected == "sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80"


async def test_runner_fills_policy_text_hash(tmp_path):
    data = cases()
    store = TraceStore.create(tmp_path, "r")
    traces = await run_dataset(
        data, SpyProvider(data), policy_version="v0.1", store=store, run_id="r"
    )
    expected = policy_text_hash(load_policy("immunara-v0.1"))
    assert {t.policy_text_hash for t in traces} == {expected}
    assert {t.policy_text_hash for t in read_traces(store.path)} == {expected}
