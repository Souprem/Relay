"""Automation/safety frontier: sweep the auto_process threshold over stored decision bundles.

Only auto_process varies; every other threshold stays at the run's version. The engine is re-run
on each trace's stored bundle, so a sweep makes no provider calls. Expected actions come from
ground truth at probability 1.0/0.0, which makes them independent of auto_process.
"""

from collections.abc import Sequence

from pydantic import BaseModel, computed_field

from relay.cases.models import PriorAuthCase
from relay.cases.policies import load_policy
from relay.evaluation.labels import expected_action
from relay.evaluation.metrics import paired_cases
from relay.traces.models import WorkflowTrace
from relay.workflow.engine import determine_action
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import override_auto_process

SWEEP_POINTS: tuple[float, ...] = tuple(round(0.50 + i / 100, 2) for i in range(50))
DEFAULT_CEILING = 0.01


class FrontierPoint(BaseModel):
    auto_threshold: float
    n: int
    auto: int
    request_info: int
    human_review: int
    unsafe: int
    correct: int
    automation_rate: float
    uar: float | None  # unsafe / auto; None when nothing was automated
    human_review_rate: float
    correct_action_rate: float


def sweep(
    traces: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
    *,
    points: Sequence[float] | None = None,
) -> list[FrontierPoint]:
    thresholds_to_try = SWEEP_POINTS if points is None else tuple(points)
    rows = []
    for trace, case in paired_cases(traces, cases):
        policy = load_policy(trace.policy_id)
        rows.append((trace, case, policy, expected_action(case, policy, trace.thresholds)))
    frontier: list[FrontierPoint] = []
    for t in thresholds_to_try:
        auto = info = review = unsafe = correct = 0
        for trace, case, policy, expected in rows:
            thresholds = override_auto_process(trace.thresholds, t)
            action = determine_action(case.input, trace.decisions, policy, thresholds).action
            auto += action == WorkflowAction.AUTO_PROCESS
            info += action == WorkflowAction.REQUEST_INFO
            review += action == WorkflowAction.HUMAN_REVIEW
            unsafe += action == WorkflowAction.AUTO_PROCESS and expected != action
            correct += action == expected
        n = len(rows)
        frontier.append(
            FrontierPoint(
                auto_threshold=t,
                n=n,
                auto=auto,
                request_info=info,
                human_review=review,
                unsafe=unsafe,
                correct=correct,
                automation_rate=auto / n,
                uar=unsafe / auto if auto else None,
                human_review_rate=review / n,
                correct_action_rate=correct / n,
            )
        )
    return frontier


def evaluate_threshold(
    traces: Sequence[WorkflowTrace], cases: Sequence[PriorAuthCase], threshold: float
) -> FrontierPoint:
    """The frontier point for one auto_process threshold (for example a --at value)."""
    return sweep(traces, cases, points=[threshold])[0]


def select_operating_point(
    points: Sequence[FrontierPoint], ceiling: float = DEFAULT_CEILING
) -> FrontierPoint | None:
    """Maximum automation among points with >= 1 AUTO_PROCESS and UAR <= ceiling.

    Ties go to the higher (more conservative) threshold. Returns None when no point qualifies;
    never fabricates one.
    """
    qualifying = [p for p in points if p.auto >= 1 and p.uar is not None and p.uar <= ceiling]
    if not qualifying:
        return None
    return max(qualifying, key=lambda p: (p.automation_rate, p.auto_threshold))


SELECTION_RULE = (
    "maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe "
    "automation rate <= the ceiling; ties go to the higher threshold"
)
FRONTIER_FIELDS: tuple[str, ...] = tuple(FrontierPoint.model_fields)


class SweepResult(BaseModel):
    run_id: str
    dataset_id: str
    provider: str
    question_set_version: str
    ceiling: float
    selection_rule: str = SELECTION_RULE
    selected: FrontierPoint | None
    at_point: FrontierPoint | None
    points: list[FrontierPoint]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def frontier_flat(self) -> bool:
        """True when every swept point has identical auto/unsafe/correct counts.

        A flat frontier means the threshold has no effect on this dataset over the swept range:
        automation, safety and correctness are all determined by something other than
        auto_process (for example, certain 0.0/1.0 probabilities).
        """
        shapes = {(p.auto, p.unsafe, p.correct) for p in self.points}
        return len(shapes) <= 1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ceiling_binding(self) -> bool:
        """True when at least one point with >= 1 AUTO_PROCESS has UAR above the ceiling.

        When this is False, the ceiling never excludes an automated point on this run, so the
        selection rule is really picking the automation-plateau tie-break, not trading off safety.
        """
        return any(p.auto >= 1 and p.uar is not None and p.uar > self.ceiling for p in self.points)


def run_sweep(
    traces: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
    *,
    ceiling: float = DEFAULT_CEILING,
    at: float | None = None,
) -> SweepResult:
    points = sweep(traces, cases)
    return SweepResult(
        run_id=traces[0].run_id,
        dataset_id=traces[0].dataset_id,
        provider=traces[0].provider,
        question_set_version=traces[0].question_set_version,
        ceiling=ceiling,
        selected=select_operating_point(points, ceiling),
        at_point=None if at is None else evaluate_threshold(traces, cases, at),
        points=points,
    )


def frontier_csv(points: Sequence[FrontierPoint]) -> str:
    lines = [",".join(FRONTIER_FIELDS)]
    for point in points:
        values = point.model_dump()
        lines.append(",".join("" if values[f] is None else str(values[f]) for f in FRONTIER_FIELDS))
    return "\n".join(lines) + "\n"
