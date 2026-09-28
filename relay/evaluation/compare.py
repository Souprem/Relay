"""Compare runs over the same dataset: metrics side by side, then per-case action differences."""

from collections.abc import Mapping, Sequence
from itertools import combinations

from pydantic import BaseModel

from relay.cases.models import PriorAuthCase
from relay.cases.policies import load_policy
from relay.evaluation.calibration import RunCalibration, calibrate_run
from relay.evaluation.frontier import DEFAULT_CEILING, SweepResult, run_sweep
from relay.evaluation.metrics import (
    EvalError,
    EvalSummary,
    RunIdentity,
    paired_cases,
    run_identity,
    score_run,
)
from relay.traces.models import WorkflowTrace
from relay.workflow.engine import determine_action
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import override_auto_process


class RunColumn(BaseModel):
    label: str
    identity: RunIdentity
    summary: EvalSummary
    calibration: RunCalibration
    sweep: SweepResult
    own_auto_process: float


class CaseDiff(BaseModel):
    case_id: str
    expected: WorkflowAction
    action_a: WorkflowAction
    action_b: WorkflowAction
    new_unsafe: bool  # run b automates unsafely where run a did not
    resolved_unsafe: bool  # run a automated unsafely; run b does not


class PairDiff(BaseModel):
    a: str
    b: str
    diffs: list[CaseDiff]


class Comparison(BaseModel):
    dataset_id: str
    n_cases: int
    threshold_note: str
    runs: list[RunColumn]
    pairs: list[PairDiff]


def _is_unsafe(action: WorkflowAction, expected: WorkflowAction) -> bool:
    return action == WorkflowAction.AUTO_PROCESS and expected != WorkflowAction.AUTO_PROCESS


def _actions_at(
    traces: Sequence[WorkflowTrace], cases: Sequence[PriorAuthCase], auto_process: float
) -> dict[str, WorkflowAction]:
    """Re-run determine_action on every stored bundle with auto_process overridden to `at`.

    Every other threshold keeps its own trace's value, matching the frontier sweep (E5).
    """
    actions = {}
    for trace, case in paired_cases(traces, cases):
        policy = load_policy(trace.policy_id)
        thresholds = override_auto_process(trace.thresholds, auto_process)
        outcome = determine_action(case.input, trace.decisions, policy, thresholds)
        actions[trace.case_id] = outcome.action
    return actions


def _pair(
    a: RunColumn, b: RunColumn, overrides: Mapping[str, Mapping[str, WorkflowAction]]
) -> PairDiff:
    b_cases = {c.case_id: c for c in b.summary.cases}
    a_actions = overrides.get(a.label)
    b_actions = overrides.get(b.label)
    diffs = []
    for ca in a.summary.cases:
        cb = b_cases[ca.case_id]
        action_a = a_actions[ca.case_id] if a_actions is not None else ca.action
        action_b = b_actions[ca.case_id] if b_actions is not None else cb.action
        if action_a == action_b:
            continue
        unsafe_a = _is_unsafe(action_a, ca.expected_action)
        unsafe_b = _is_unsafe(action_b, ca.expected_action)
        diffs.append(
            CaseDiff(
                case_id=ca.case_id,
                expected=ca.expected_action,
                action_a=action_a,
                action_b=action_b,
                new_unsafe=unsafe_b and not unsafe_a,
                resolved_unsafe=unsafe_a and not unsafe_b,
            )
        )
    diffs.sort(key=lambda d: (not d.new_unsafe, not d.resolved_unsafe, d.case_id))
    return PairDiff(a=a.label, b=b.label, diffs=diffs)


def compare_runs(
    runs: Sequence[tuple[str, Sequence[WorkflowTrace]]],
    cases: Sequence[PriorAuthCase],
    *,
    ceiling: float = DEFAULT_CEILING,
    at: float | None = None,
) -> Comparison:
    """Each run must cover exactly the dataset's cases with unchanged case hashes (EvalError).

    Action diffs are computed at `at` (re-running determine_action on stored bundles, other
    thresholds left at each trace's own version) when given, otherwise at each run's own
    thresholds (its traces' stored `action`). `threshold_note` always says which was used.
    """
    if len(runs) < 2:
        raise EvalError("compare needs at least two runs")
    labels = [label for label, _ in runs]
    duplicates = sorted({label for label in labels if labels.count(label) > 1})
    if duplicates:
        raise EvalError(f"duplicate run labels {duplicates}; pass distinct --labels")
    columns = []
    overrides: dict[str, dict[str, WorkflowAction]] = {}
    for label, traces in runs:
        try:
            columns.append(
                RunColumn(
                    label=label,
                    identity=run_identity(traces),
                    summary=score_run(traces, cases),
                    calibration=calibrate_run(traces, cases),
                    sweep=run_sweep(traces, cases, ceiling=ceiling, at=at),
                    own_auto_process=traces[0].thresholds.auto_process,
                )
            )
            if at is not None:
                overrides[label] = _actions_at(traces, cases, at)
        except EvalError as error:
            raise EvalError(f"{label}: {error}") from error
    if at is not None:
        threshold_note = f"at auto_process >= {at} (--at)"
    else:
        threshold_note = (
            "at each run's own thresholds ("
            + ", ".join(f"{c.label} auto_process >= {c.own_auto_process}" for c in columns)
            + ")"
        )
    return Comparison(
        dataset_id=columns[0].summary.dataset_id,
        n_cases=columns[0].summary.n_cases,
        threshold_note=threshold_note,
        runs=columns,
        pairs=[_pair(a, b, overrides) for a, b in combinations(columns, 2)],
    )
