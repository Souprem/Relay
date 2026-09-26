"""Per-decision confusion matrices. Rows are the ground truth, columns the prediction."""

from collections.abc import Sequence

from pydantic import BaseModel

from relay.cases.models import PriorAuthCase
from relay.decisions.base import DecisionId
from relay.evaluation.calibration import MISSING_EVIDENCE_LABELS
from relay.evaluation.metrics import paired_cases, truth_flag
from relay.traces.models import WorkflowTrace
from relay.workflow.engine import bundle_problem

YES_NO_LABELS: tuple[str, ...] = ("yes", "no")


class ConfusionMatrix(BaseModel):
    decision: str
    labels: list[str]
    counts: list[list[int]]  # counts[truth_index][predicted_index]
    n: int
    invalid_excluded: int

    def count(self, truth: str, predicted: str) -> int:
        return self.counts[self.labels.index(truth)][self.labels.index(predicted)]


def _yes_no(flag: bool) -> str:
    return "yes" if flag else "no"


def confusion_matrices(
    traces: Sequence[WorkflowTrace], cases: Sequence[PriorAuthCase]
) -> dict[str, ConfusionMatrix]:
    labels = {
        q: list(MISSING_EVIDENCE_LABELS if q == DecisionId.MISSING_EVIDENCE else YES_NO_LABELS)
        for q in DecisionId
    }
    counts = {q: [[0] * len(labels[q]) for _ in labels[q]] for q in DecisionId}
    invalid = 0
    for trace, case in paired_cases(traces, cases):
        if bundle_problem(trace.decisions) is not None:
            invalid += 1
            continue
        for decision in trace.decisions.decisions:
            q = decision.question_id
            if q == DecisionId.MISSING_EVIDENCE:
                assert decision.answer is not None
                truth, predicted = case.ground_truth.missing_evidence.value, decision.answer
            else:
                assert decision.p_yes is not None
                truth = _yes_no(truth_flag(case.ground_truth, q))
                predicted = _yes_no(decision.p_yes >= 0.5)
            counts[q][labels[q].index(truth)][labels[q].index(predicted)] += 1
    return {
        q.value: ConfusionMatrix(
            decision=q.value,
            labels=labels[q],
            counts=counts[q],
            n=sum(map(sum, counts[q])),
            invalid_excluded=invalid,
        )
        for q in DecisionId
    }
