"""Workflow- and decision-level metrics. Unavailable metrics are None, never omitted."""

import math
from collections.abc import Iterable, Sequence
from decimal import Decimal

from pydantic import BaseModel, Field

from relay.cases.models import GroundTruth, PriorAuthCase
from relay.cases.policies import load_policy
from relay.decisions.base import Decision, DecisionBundle, DecisionId
from relay.evaluation.labels import expected_action
from relay.traces.models import WorkflowTrace
from relay.workflow.engine import bundle_problem
from relay.workflow.outcomes import WorkflowAction

LOW_SAMPLE_N = 30
YES_NO_TRUTH = {
    DecisionId.DIAGNOSIS_SUPPORT: "diagnosis_supported",
    DecisionId.STEP_THERAPY: "step_therapy_satisfied",
    DecisionId.DOCUMENTATION_COMPLETE: "documentation_complete",
    DecisionId.MATERIAL_CONTRADICTION: "contradiction_present",
}


class EvalError(Exception):
    """Traces cannot be scored against this dataset."""


class ScoredCase(BaseModel):
    case_id: str
    expected_action: WorkflowAction
    action: WorkflowAction
    correct: bool
    unsafe_automation: bool
    invalid_output: bool
    latency_ms: int | None
    estimated_cost_usd: Decimal | None


class EvalSummary(BaseModel):
    run_id: str
    dataset_id: str
    provider: str
    provider_versions: list[str]
    policy_version: str
    n_cases: int
    question_set_versions: list[str] = Field(default_factory=list)
    correct_actions: int
    auto_process_count: int
    request_info_count: int
    human_review_count: int
    unsafe_automation_count: int
    invalid_outputs: int
    correct_action_rate: float
    automation_rate: float
    request_info_rate: float
    human_escalation_rate: float
    unsafe_automation_rate: float | None
    per_question_accuracy: dict[str, float | None]
    latency_p50_ms: int | None
    latency_p95_ms: int | None
    latency_low_sample: bool
    # Cases with a recorded latency (None in results.json files written before Phase 2D).
    latency_n: int | None = None
    # derivations["execution"]["mode"] values seen in the run, e.g. ["batch"]; [] if none.
    execution_modes: list[str] = Field(default_factory=list)
    # Bundles whose provider stopped with stop_reason "refusal"; None when no bundle in the run
    # records a stop_reason (providers other than Claude, and pre-2D results.json files).
    refusals: int | None = None
    # Share of prompt tokens served from the prompt cache, over bundles that record usage.
    cache_read_share: float | None = None
    total_cost_usd: Decimal | None
    cost_per_case_usd: Decimal | None
    cases: list[ScoredCase]


class RunIdentity(BaseModel):
    """What produced a run: enough to tell whether two reports are comparable."""

    run_id: str
    dataset_id: str
    dataset_hash: str | None
    provider: str
    provider_versions: list[str]
    client_versions: list[str]
    question_set_versions: list[str]
    question_set_hashes: list[str]
    policy_versions: list[str]
    policy_text_hashes: list[str]
    thresholds_versions: list[str]
    relay_git_shas: list[str]


def _present(values: Iterable[str | None]) -> list[str]:
    return sorted({v for v in values if v is not None})


def run_identity(
    traces: Sequence[WorkflowTrace], *, dataset_hash: str | None = None
) -> RunIdentity:
    if not traces:
        raise EvalError("no traces to describe")
    return RunIdentity(
        run_id=traces[0].run_id,
        dataset_id=traces[0].dataset_id,
        dataset_hash=dataset_hash,
        provider=traces[0].provider,
        provider_versions=_present(t.provider_version for t in traces),
        client_versions=_present(t.decisions.client_version for t in traces),
        question_set_versions=_present(t.question_set_version for t in traces),
        question_set_hashes=_present(t.question_set_hash for t in traces),
        policy_versions=_present(t.policy_version for t in traces),
        policy_text_hashes=_present(t.policy_text_hash for t in traces),
        thresholds_versions=_present(t.thresholds.version for t in traces),
        relay_git_shas=_present(t.relay_git_sha for t in traces),
    )


def execution_mode(bundle: DecisionBundle) -> str | None:
    """How the provider ran this case ("sync" or "batch"), if it recorded it."""
    execution = bundle.derivations.get("execution")
    if isinstance(execution, dict) and isinstance(execution.get("mode"), str):
        return execution["mode"]
    return None


def _refusals(traces: Sequence[WorkflowTrace]) -> int | None:
    reasons = [t.decisions.derivations.get("stop_reason") for t in traces]
    if all(reason is None for reason in reasons):
        return None
    return sum(reason == "refusal" for reason in reasons)


def _cache_read_share(traces: Sequence[WorkflowTrace]) -> float | None:
    usages = [t.decisions.derivations.get("usage") for t in traces]
    usages = [u for u in usages if isinstance(u, dict)]
    prompt = sum(
        u.get("input_tokens", 0)
        + u.get("cache_creation_input_tokens", 0)
        + u.get("cache_read_input_tokens", 0)
        for u in usages
    )
    if not prompt:
        return None
    return sum(u.get("cache_read_input_tokens", 0) for u in usages) / prompt


def percentile(values: Sequence[int], pct: float) -> int | None:
    """Nearest-rank percentile."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def _decision_correct(decision: Decision, truth: GroundTruth) -> bool:
    if decision.question_id == DecisionId.MISSING_EVIDENCE:
        return decision.answer == truth.missing_evidence.value
    assert decision.p_yes is not None
    return (decision.p_yes >= 0.5) == truth_flag(truth, decision.question_id)


def truth_flag(truth: GroundTruth, question_id: DecisionId) -> bool:
    """The ground-truth answer to a yes/no decision."""
    return getattr(truth, YES_NO_TRUTH[question_id])


def paired_cases(
    traces: Sequence[WorkflowTrace], cases: Sequence[PriorAuthCase]
) -> list[tuple[WorkflowTrace, PriorAuthCase]]:
    """Match one run's traces to dataset cases, in trace order.

    Raises EvalError unless the traces come from one run, have no duplicate case ids, refer only
    to known cases whose content hash is unchanged, and cover every case in the dataset.
    """
    if not traces:
        raise EvalError("no traces to score")
    run_ids = {t.run_id for t in traces}
    if len(run_ids) != 1:
        raise EvalError(f"traces come from multiple runs: {sorted(run_ids)}")
    trace_case_ids = [t.case_id for t in traces]
    duplicates = sorted({cid for cid in trace_case_ids if trace_case_ids.count(cid) > 1})
    if duplicates:
        raise EvalError(f"duplicate case ids in traces: {duplicates}")
    by_id = {c.input.id: c for c in cases}
    pairs: list[tuple[WorkflowTrace, PriorAuthCase]] = []
    for trace in traces:
        case = by_id.get(trace.case_id)
        if case is None:
            raise EvalError(f"trace for unknown case {trace.case_id}")
        if case.input.content_hash() != trace.case_content_hash:
            raise EvalError(f"{trace.case_id}: case content hash changed since the run")
        pairs.append((trace, case))
    missing = sorted(set(by_id) - set(trace_case_ids))
    if missing:
        raise EvalError(f"traces do not cover every case in the dataset, missing: {missing}")
    return pairs


def score_run(traces: Sequence[WorkflowTrace], cases: Sequence[PriorAuthCase]) -> EvalSummary:
    scored: list[ScoredCase] = []
    hits: dict[DecisionId, list[bool]] = {q: [] for q in DecisionId}
    for trace, case in paired_cases(traces, cases):
        expected = expected_action(case, load_policy(trace.policy_id), trace.thresholds)
        invalid = bundle_problem(trace.decisions) is not None
        scored.append(
            ScoredCase(
                case_id=trace.case_id,
                expected_action=expected,
                action=trace.action,
                correct=trace.action == expected,
                unsafe_automation=(
                    trace.action == WorkflowAction.AUTO_PROCESS
                    and expected != WorkflowAction.AUTO_PROCESS
                ),
                invalid_output=invalid,
                latency_ms=trace.decisions.latency_ms,
                estimated_cost_usd=trace.decisions.estimated_cost_usd,
            )
        )
        if not invalid:
            for decision in trace.decisions.decisions:
                hits[decision.question_id].append(_decision_correct(decision, case.ground_truth))

    n = len(scored)
    autos = sum(c.action == WorkflowAction.AUTO_PROCESS for c in scored)
    infos = sum(c.action == WorkflowAction.REQUEST_INFO for c in scored)
    reviews = sum(c.action == WorkflowAction.HUMAN_REVIEW for c in scored)
    unsafe = sum(c.unsafe_automation for c in scored)
    correct = sum(c.correct for c in scored)
    costs = [c.estimated_cost_usd for c in scored]
    total_cost = None if any(c is None for c in costs) else sum(costs, Decimal("0"))
    latencies = [c.latency_ms for c in scored if c.latency_ms is not None]
    return EvalSummary(
        run_id=traces[0].run_id,
        dataset_id=traces[0].dataset_id,
        provider=traces[0].provider,
        provider_versions=sorted({t.provider_version for t in traces}),
        policy_version=traces[0].policy_version,
        n_cases=n,
        question_set_versions=sorted({t.question_set_version for t in traces}),
        correct_actions=correct,
        auto_process_count=autos,
        request_info_count=infos,
        human_review_count=reviews,
        unsafe_automation_count=unsafe,
        invalid_outputs=sum(c.invalid_output for c in scored),
        correct_action_rate=correct / n,
        automation_rate=autos / n,
        request_info_rate=infos / n,
        human_escalation_rate=reviews / n,
        unsafe_automation_rate=unsafe / autos if autos else None,
        per_question_accuracy={q.value: (sum(h) / len(h) if h else None) for q, h in hits.items()},
        latency_p50_ms=percentile(latencies, 50),
        latency_p95_ms=percentile(latencies, 95),
        latency_low_sample=len(latencies) < LOW_SAMPLE_N,
        latency_n=len(latencies),
        execution_modes=_present(execution_mode(t.decisions) for t in traces),
        refusals=_refusals(traces),
        cache_read_share=_cache_read_share(traces),
        total_cost_usd=total_cost,
        cost_per_case_usd=None if total_cost is None else total_cost / n,
        cases=sorted(scored, key=lambda c: c.case_id),
    )
