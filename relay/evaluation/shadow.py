"""Shadow comparison (Phase 3C): a shadow candidate against the incumbent on the same cases.

Pure: no file or network I/O. Two parts, kept apart on purpose:

- Agreement is unlabelled (diff_runs(labelled=False)): what a real shadow deployment can see,
  with no ground truth. Agreement rate, the incumbent x candidate action matrix, and the cases
  the candidate would newly auto-process or would stop auto-processing.
- The promotion check is EVALUATION-ONLY: the 3B regression gate (build_result over labelled
  diffs) with the incumbent as baseline. Gate PASS is PROMOTE (exit 0); gate FAIL is HOLD
  (exit 4). STILL UNSAFE cases are reported by the gate but never cause HOLD.
"""

from collections.abc import Callable, Sequence
from typing import Literal

from pydantic import BaseModel

from relay.cases.models import PriorAuthCase
from relay.evaluation.regression import Rate, RegressionResult, Waiver, build_result, rate
from relay.evaluation.tracediff import EXIT_NEWLY_UNSAFE, TraceDiff, diff_runs
from relay.traces.models import WorkflowTrace
from relay.workflow.outcomes import WorkflowAction

ACTIONS: tuple[WorkflowAction, ...] = tuple(WorkflowAction)


class Agreement(BaseModel):
    n: int
    agreed: Rate  # cases where both runs chose the same action
    # incumbent action -> candidate action -> count; every action appears on both axes.
    matrix: dict[WorkflowAction, dict[WorkflowAction, int]]
    newly_auto: list[str]  # the candidate would auto-process; the incumbent did not
    stopped_auto: list[str]  # the incumbent auto-processed; the candidate would not


class ShadowReport(BaseModel):
    dataset_id: str
    n: int
    incumbent_label: str
    candidate_label: str
    agreement: Agreement
    promotion: RegressionResult
    decision: Literal["PROMOTE", "HOLD"]
    exit_code: int  # 0 PROMOTE, EXIT_NEWLY_UNSAFE (4) HOLD


def transition_matrix(
    diffs: Sequence[TraceDiff],
) -> dict[WorkflowAction, dict[WorkflowAction, int]]:
    """Counts of (incumbent action, candidate action) over the diffs, with every cell present."""
    matrix = {a: dict.fromkeys(ACTIONS, 0) for a in ACTIONS}
    for d in diffs:
        matrix[d.action_original][d.action_candidate] += 1
    return matrix


def agreement(diffs: Sequence[TraceDiff]) -> Agreement:
    ordered = sorted(diffs, key=lambda d: d.case_id)
    auto = WorkflowAction.AUTO_PROCESS
    return Agreement(
        n=len(ordered),
        agreed=rate(sum(d.action_original == d.action_candidate for d in ordered), len(ordered)),
        matrix=transition_matrix(ordered),
        newly_auto=[
            d.case_id for d in ordered if d.action_candidate == auto and d.action_original != auto
        ],
        stopped_auto=[
            d.case_id for d in ordered if d.action_original == auto and d.action_candidate != auto
        ],
    )


def build_shadow_report(
    incumbent: Sequence[WorkflowTrace],
    shadow: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
    *,
    incumbent_label: str,
    candidate_label: str,
    waivers: Sequence[Waiver] = (),
    gate_name: str | None = None,
    max_regressed: int | None = None,
    dataset_hash: str | None = None,
    replay_command: Callable[[str], str | None] | None = None,
) -> ShadowReport:
    """Agreement (unlabelled) plus the evaluation-only promotion check. diff_runs checks both
    runs cover the same cases (EvalError otherwise); `gate_name` scopes the waivers as in 3B, and
    `replay_command` gives each listed case its `relay replay` command."""
    unlabelled = diff_runs(
        incumbent,
        shadow,
        cases,
        original_label=incumbent_label,
        candidate_label=candidate_label,
        labelled=False,
    )
    labelled = diff_runs(
        incumbent,
        shadow,
        cases,
        original_label=incumbent_label,
        candidate_label=candidate_label,
    )
    promotion = build_result(
        labelled,
        incumbent,
        shadow,
        cases,
        baseline_label=incumbent_label,
        candidate_label=candidate_label,
        gate=gate_name,
        reproduce=False,
        waivers=waivers,
        max_regressed=max_regressed,
        dataset_hash=dataset_hash,
        replay_command=replay_command,
    )
    held = promotion.verdict == "FAIL"
    return ShadowReport(
        dataset_id=promotion.dataset_id,
        n=promotion.n,
        incumbent_label=incumbent_label,
        candidate_label=candidate_label,
        agreement=agreement(unlabelled),
        promotion=promotion,
        decision="HOLD" if held else "PROMOTE",
        exit_code=EXIT_NEWLY_UNSAFE if held else 0,
    )
