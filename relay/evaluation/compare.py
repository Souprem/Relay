"""Compare runs over the same dataset: metrics side by side, then per-case action differences."""

from collections.abc import Sequence
from itertools import combinations

from pydantic import BaseModel

from relay.cases.models import PriorAuthCase
from relay.evaluation.calibration import RunCalibration, calibrate_run
from relay.evaluation.frontier import DEFAULT_CEILING, SweepResult, run_sweep
from relay.evaluation.metrics import EvalError, EvalSummary, RunIdentity, run_identity, score_run
from relay.traces.models import WorkflowTrace
from relay.workflow.outcomes import WorkflowAction


class RunColumn(BaseModel):
    label: str
    identity: RunIdentity
    summary: EvalSummary
    calibration: RunCalibration
    sweep: SweepResult


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
    runs: list[RunColumn]
    pairs: list[PairDiff]


def _pair(a: RunColumn, b: RunColumn) -> PairDiff:
    b_cases = {c.case_id: c for c in b.summary.cases}
    diffs = []
    for ca in a.summary.cases:
        cb = b_cases[ca.case_id]
        if ca.action == cb.action:
            continue
        diffs.append(
            CaseDiff(
                case_id=ca.case_id,
                expected=ca.expected_action,
                action_a=ca.action,
                action_b=cb.action,
                new_unsafe=cb.unsafe_automation and not ca.unsafe_automation,
                resolved_unsafe=ca.unsafe_automation and not cb.unsafe_automation,
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
    """Each run must cover exactly the dataset's cases with unchanged case hashes (EvalError)."""
    if len(runs) < 2:
        raise EvalError("compare needs at least two runs")
    labels = [label for label, _ in runs]
    duplicates = sorted({label for label in labels if labels.count(label) > 1})
    if duplicates:
        raise EvalError(f"duplicate run labels {duplicates}; pass distinct --labels")
    columns = []
    for label, traces in runs:
        try:
            columns.append(
                RunColumn(
                    label=label,
                    identity=run_identity(traces),
                    summary=score_run(traces, cases),
                    calibration=calibrate_run(traces, cases),
                    sweep=run_sweep(traces, cases, ceiling=ceiling, at=at),
                )
            )
        except EvalError as error:
            raise EvalError(f"{label}: {error}") from error
    return Comparison(
        dataset_id=columns[0].summary.dataset_id,
        n_cases=columns[0].summary.n_cases,
        runs=columns,
        pairs=[_pair(a, b) for a, b in combinations(columns, 2)],
    )
