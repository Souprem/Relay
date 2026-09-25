"""Run a dataset through a provider and the policy engine, tracing every case."""

import asyncio
import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime

from relay.cases.models import PriorAuthCase
from relay.cases.policies import AuthorizationPolicy, load_policy
from relay.decisions.base import DecisionProvider, PreparingProvider
from relay.traces.models import WorkflowTrace
from relay.traces.store import TraceStore, new_trace_id
from relay.workflow.engine import determine_action
from relay.workflow.thresholds import load_thresholds


class RunConfigError(ValueError):
    """The requested policy version or policies cannot be used for these cases."""


def policy_text_hash(policy: AuthorizationPolicy) -> str:
    return "sha256:" + hashlib.sha256(policy.text.encode("utf-8")).hexdigest()


def validate_run_config(
    cases: Sequence[PriorAuthCase], policy_version: str
) -> dict[str, AuthorizationPolicy]:
    try:
        load_thresholds(policy_version)
    except KeyError as error:
        raise RunConfigError(str(error)) from error
    policies: dict[str, AuthorizationPolicy] = {}
    for case in cases:
        policy_id = case.input.policy_id
        if policy_id not in policies:
            try:
                policies[policy_id] = load_policy(policy_id)
            except KeyError as error:
                raise RunConfigError(f"{case.input.id}: {error}") from error
        policy = policies[policy_id]
        if policy.version != policy_version:
            raise RunConfigError(
                f"{case.input.id}: policy {policy_id} is version {policy.version}, "
                f"but policy version {policy_version} was requested"
            )
    return policies


async def run_dataset(
    cases: Sequence[PriorAuthCase],
    provider: DecisionProvider,
    *,
    policy_version: str,
    store: TraceStore,
    run_id: str,
    concurrency: int = 4,
    git_sha: str | None = None,
) -> list[WorkflowTrace]:
    policies = validate_run_config(cases, policy_version)
    thresholds = load_thresholds(policy_version)
    semaphore = asyncio.Semaphore(concurrency)
    if isinstance(provider, PreparingProvider):
        await provider.prepare([case.input for case in cases])

    async def run_one(case: PriorAuthCase) -> WorkflowTrace:
        policy = policies[case.input.policy_id]
        async with semaphore:
            bundle = await provider.decide(case.input)
        outcome = determine_action(case.input, bundle, policy, thresholds)
        trace = WorkflowTrace(
            trace_id=new_trace_id(),
            run_id=run_id,
            timestamp=datetime.now(UTC),
            case_id=case.input.id,
            case_content_hash=case.input.content_hash(),
            dataset_id=case.input.dataset_id,
            provider=bundle.provider,
            provider_version=bundle.provider_version,
            question_set_version=bundle.question_set_version,
            question_set_hash=bundle.question_set_hash,
            policy_id=policy.id,
            policy_version=policy.version,
            policy_text_hash=policy_text_hash(policy),
            thresholds=thresholds,
            decisions=bundle,
            action=outcome.action,
            decision_reasons=outcome.reasons,
            gate_path=outcome.gate_path,
            mode="evaluate",
            relay_git_sha=git_sha,
        )
        store.append(trace)
        return trace

    return list(await asyncio.gather(*(run_one(c) for c in cases)))
