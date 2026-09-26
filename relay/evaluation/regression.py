"""The regression gate: result model, waivers and verdict (Phase 3B spec §3, G4-G6).

Pure: no file or network I/O. relay.evaluation.regression_run loads the runs, builds the
candidate and calls build_result; relay.reporting renders the result.

The verdict is FAIL when (a) a newly unsafe case has no waiver, (b) max_regressed is set and more
cases regressed than that, or (c) in reproduce mode any case is not identical. Exit codes: 0 PASS,
4 for (a)/(b), 3 for (c); the highest applicable code wins. Waivers cover newly unsafe cases only.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from relay.cases.models import PriorAuthCase
from relay.evaluation.calibration import calibrate_run
from relay.evaluation.intervals import clopper_pearson
from relay.evaluation.metrics import RunIdentity, run_identity, score_run
from relay.evaluation.tracediff import EXIT_ENGINE_DRIFT, EXIT_NEWLY_UNSAFE, TraceDiff
from relay.traces.models import WorkflowTrace
from relay.workflow.outcomes import WorkflowAction

CHANGE_ORDER: tuple[str, ...] = ("improved", "unchanged", "regressed", "changed-both-wrong")
LISTED_IDS = 10  # case ids spelled out in one failure sentence before "and N more"

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Waiver(BaseModel):
    """A reviewed decision to accept one newly unsafe case in one gate ("*" for every gate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: NonEmpty
    gate: NonEmpty
    reason: NonEmpty
    approved_by: NonEmpty
    date: NonEmpty

    @field_validator("date")
    @classmethod
    def _iso_date(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("date must be YYYY-MM-DD")
        date.fromisoformat(value)  # rejects 2026-13-40
        return value

    def applies_to(self, gate: str | None) -> bool:
        return self.gate == "*" or self.gate == gate


class WaiverFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    waivers: list[Waiver]


class Interval(BaseModel):
    low: float
    high: float


class Rate(BaseModel):
    count: int
    n: int
    rate: float | None  # None when n == 0
    ci95: Interval | None  # Clopper-Pearson; None when n == 0


class SideMetrics(BaseModel):
    label: str
    identity: RunIdentity
    n: int
    correct: Rate
    automation: Rate
    request_info: Rate
    human_review: Rate
    uar: Rate  # unsafe / AUTO_PROCESS count
    invalid_outputs: int


class CalibrationDelta(BaseModel):
    decision: str
    brier_baseline: float | None
    brier_candidate: float | None
    brier_delta: float | None
    ece_baseline: float | None
    ece_candidate: float | None
    ece_delta: float | None


class CaseEntry(BaseModel):
    case_id: str
    expected: WorkflowAction  # under the baseline's policy and thresholds
    expected_candidate: WorkflowAction | None  # only when it differs from `expected`
    action_baseline: WorkflowAction
    action_candidate: WorkflowAction
    answer_changed: list[str]  # decision ids whose answer flipped
    crossed_gated: dict[str, list[str]]  # decision id -> gated thresholds crossed
    replay_command: str | None


class WaivedCase(BaseModel):
    entry: CaseEntry
    waiver: Waiver


class RegressionResult(BaseModel):
    gate: str | None
    reproduce: bool
    dataset_id: str
    n: int
    baseline: SideMetrics
    candidate: SideMetrics
    calibration: list[CalibrationDelta]
    change_counts: dict[str, int]  # CHANGE_ORDER keys
    not_identical: int
    newly_unsafe: list[CaseEntry]  # without a waiver
    waived: list[WaivedCase]
    unsafe_resolved: list[CaseEntry]
    regressed: list[CaseEntry]
    improved: list[CaseEntry]
    drifted: list[CaseEntry]  # reproduce mode only: cases that are not identical
    stale_waivers: list[Waiver]
    max_regressed: int | None
    verdict: Literal["PASS", "FAIL"]
    failures: list[str]
    exit_code: int


@dataclass(frozen=True)
class GateOutcome:
    newly_unsafe: list[TraceDiff]  # without a waiver
    waived: list[tuple[TraceDiff, Waiver]]
    stale_waivers: list[Waiver]
    regressed: list[TraceDiff]
    drifted: list[TraceDiff]
    failures: list[str]
    exit_code: int

    @property
    def verdict(self) -> Literal["PASS", "FAIL"]:
        return "FAIL" if self.failures else "PASS"


def _ids(case_ids: Sequence[str]) -> str:
    shown = ", ".join(case_ids[:LISTED_IDS])
    more = len(case_ids) - LISTED_IDS
    return shown if more <= 0 else f"{shown} and {more} more"


def evaluate_gate(
    diffs: Sequence[TraceDiff],
    *,
    reproduce: bool,
    waivers: Sequence[Waiver],
    gate: str | None,
    max_regressed: int | None,
) -> GateOutcome:
    """The verdict over labelled diffs. Only waivers that apply to `gate` are considered; one of
    those matching no newly unsafe case is stale (a warning, never a failure)."""
    if any(d.change is None for d in diffs):
        raise ValueError("the regression gate needs labelled diffs (expected actions)")
    ordered = sorted(diffs, key=lambda d: d.case_id)
    applicable = [w for w in waivers if w.applies_to(gate)]
    newly_unsafe: list[TraceDiff] = []
    waived: list[tuple[TraceDiff, Waiver]] = []
    for d in (d for d in ordered if d.newly_unsafe):
        waiver = next((w for w in applicable if w.case_id == d.case_id), None)
        if waiver is None:
            newly_unsafe.append(d)
        else:
            waived.append((d, waiver))
    unsafe_ids = {d.case_id for d in ordered if d.newly_unsafe}
    stale = [w for w in applicable if w.case_id not in unsafe_ids]
    regressed = [d for d in ordered if d.change == "regressed"]
    drifted = [d for d in ordered if not d.identical] if reproduce else []

    failures: list[str] = []
    code = 0
    if drifted:
        failures.append(
            f"ENGINE DRIFT: {len(drifted)} case(s) not reproduced: "
            f"{_ids([d.case_id for d in drifted])}"
        )
        code = max(code, EXIT_ENGINE_DRIFT)
    if newly_unsafe:
        failures.append(
            f"{len(newly_unsafe)} newly unsafe case(s) without a waiver: "
            f"{_ids([d.case_id for d in newly_unsafe])}"
        )
        code = max(code, EXIT_NEWLY_UNSAFE)
    if max_regressed is not None and len(regressed) > max_regressed:
        failures.append(
            f"{len(regressed)} regressed case(s), more than --max-regressed {max_regressed}"
        )
        code = max(code, EXIT_NEWLY_UNSAFE)
    return GateOutcome(
        newly_unsafe=newly_unsafe,
        waived=waived,
        stale_waivers=stale,
        regressed=regressed,
        drifted=drifted,
        failures=failures,
        exit_code=code,
    )


def rate(count: int, n: int) -> Rate:
    if n == 0:
        return Rate(count=count, n=n, rate=None, ci95=None)
    low, high = clopper_pearson(count, n)
    return Rate(count=count, n=n, rate=count / n, ci95=Interval(low=low, high=high))


def side_metrics(
    label: str,
    traces: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
    *,
    dataset_hash: str | None,
) -> SideMetrics:
    s = score_run(traces, cases)
    return SideMetrics(
        label=label,
        identity=run_identity(traces, dataset_hash=dataset_hash),
        n=s.n_cases,
        correct=rate(s.correct_actions, s.n_cases),
        automation=rate(s.auto_process_count, s.n_cases),
        request_info=rate(s.request_info_count, s.n_cases),
        human_review=rate(s.human_review_count, s.n_cases),
        uar=rate(s.unsafe_automation_count, s.auto_process_count),
        invalid_outputs=s.invalid_outputs,
    )


def _delta(before: float | None, after: float | None) -> float | None:
    return None if before is None or after is None else after - before


def calibration_deltas(
    baseline: Sequence[WorkflowTrace],
    candidate: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
) -> list[CalibrationDelta]:
    before = calibrate_run(baseline, cases).decisions
    after = calibrate_run(candidate, cases).decisions
    return [
        CalibrationDelta(
            decision=decision,
            brier_baseline=before[decision].brier,
            brier_candidate=after[decision].brier,
            brier_delta=_delta(before[decision].brier, after[decision].brier),
            ece_baseline=before[decision].ece,
            ece_candidate=after[decision].ece,
            ece_delta=_delta(before[decision].ece, after[decision].ece),
        )
        for decision in before
    ]


def case_entry(diff: TraceDiff, replay_command: str | None) -> CaseEntry:
    assert diff.expected_original is not None and diff.expected_candidate is not None
    return CaseEntry(
        case_id=diff.case_id,
        expected=diff.expected_original,
        expected_candidate=(
            None if diff.expected_candidate == diff.expected_original else diff.expected_candidate
        ),
        action_baseline=diff.action_original,
        action_candidate=diff.action_candidate,
        answer_changed=[d.question_id.value for d in diff.decisions if d.answer_changed],
        crossed_gated={
            d.question_id.value: d.crossed_gated for d in diff.decisions if d.crossed_gated
        },
        replay_command=replay_command,
    )


def build_result(
    diffs: Sequence[TraceDiff],
    baseline: Sequence[WorkflowTrace],
    candidate: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
    *,
    baseline_label: str,
    candidate_label: str,
    gate: str | None,
    reproduce: bool,
    waivers: Sequence[Waiver],
    max_regressed: int | None,
    dataset_hash: str | None = None,
    replay_command: Callable[[str], str | None] | None = None,
) -> RegressionResult:
    """The full RegressionResult for one baseline/candidate pair already diffed by diff_runs.

    score_run / calibrate_run pair each side with `cases`, so EvalError propagates for traces
    that do not cover the dataset.
    """
    outcome = evaluate_gate(
        diffs, reproduce=reproduce, waivers=waivers, gate=gate, max_regressed=max_regressed
    )
    command = replay_command or (lambda _case_id: None)

    def entries(selected: Sequence[TraceDiff]) -> list[CaseEntry]:
        return [case_entry(d, command(d.case_id)) for d in selected]

    ordered = sorted(diffs, key=lambda d: d.case_id)
    return RegressionResult(
        gate=gate,
        reproduce=reproduce,
        dataset_id=baseline[0].dataset_id,
        n=len(diffs),
        baseline=side_metrics(baseline_label, baseline, cases, dataset_hash=dataset_hash),
        candidate=side_metrics(candidate_label, candidate, cases, dataset_hash=dataset_hash),
        calibration=calibration_deltas(baseline, candidate, cases),
        change_counts={c: sum(d.change == c for d in diffs) for c in CHANGE_ORDER},
        not_identical=sum(not d.identical for d in diffs),
        newly_unsafe=entries(outcome.newly_unsafe),
        waived=[
            WaivedCase(entry=case_entry(d, command(d.case_id)), waiver=w) for d, w in outcome.waived
        ],
        unsafe_resolved=entries([d for d in ordered if d.unsafe_resolved]),
        regressed=entries(outcome.regressed),
        improved=entries([d for d in ordered if d.change == "improved"]),
        drifted=entries(outcome.drifted),
        stale_waivers=outcome.stale_waivers,
        max_regressed=max_regressed,
        verdict=outcome.verdict,
        failures=outcome.failures,
        exit_code=outcome.exit_code,
    )
