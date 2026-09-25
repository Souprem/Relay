"""Calibration of stored judgments: reliability bins, Brier score and ECE (pure Python).

Yes/no decisions: confidence = max(p_yes, 1 - p_yes), correct = (p_yes >= 0.5) == truth, five
equal-width bins over [0.5, 1.0]. The missing-evidence choice: confidence = probability of the
chosen answer, correct = answer == truth, the same bins plus [0.0, 0.5). Invalid bundles are
excluded and counted. Metrics with no data are None, never omitted.
"""

from collections.abc import Mapping, Sequence

from pydantic import BaseModel

from relay.cases.models import MissingEvidence, PriorAuthCase
from relay.decisions.base import DecisionId
from relay.evaluation.metrics import paired_cases, truth_flag
from relay.traces.models import WorkflowTrace
from relay.workflow.engine import bundle_problem

BINARY_EDGES: tuple[float, ...] = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
CHOICE_EDGES: tuple[float, ...] = (0.0, *BINARY_EDGES)
MISSING_EVIDENCE_LABELS: tuple[str, ...] = tuple(m.value for m in MissingEvidence)
_ROUND = 12  # float noise such as 0.7000000000000001 must not move a value across a bin edge
PARTIAL_TOLERANCE = 1e-6


def is_partial(probabilities: Mapping[str, float], labels: Sequence[str]) -> bool:
    """True when the distribution leaves some probability mass on no label."""
    return sum(probabilities.get(label, 0.0) for label in labels) < 1.0 - PARTIAL_TOLERANCE


class CalibrationBin(BaseModel):
    lower: float
    upper: float
    n: int
    mean_confidence: float | None
    accuracy: float | None


class CalibrationReport(BaseModel):
    n: int
    brier: float | None
    ece: float | None
    bins: list[CalibrationBin]


class RunCalibration(BaseModel):
    """Per-decision calibration for one run, keyed by decision id."""

    decisions: dict[str, CalibrationReport]
    invalid_excluded: int
    # Missing-evidence distributions whose probabilities sum to less than 1: the Brier score
    # counts the unassigned mass as 0 on every label. (0 in files written before Phase 2D.)
    partial_choice_distributions: int = 0


def _bin_index(confidence: float, edges: Sequence[float]) -> int:
    c = round(confidence, _ROUND)
    if not edges[0] <= c <= edges[-1]:
        raise ValueError(f"confidence {confidence} is outside [{edges[0]}, {edges[-1]}]")
    for i in range(len(edges) - 2):
        if c < edges[i + 1]:
            return i
    return len(edges) - 2  # the last bin is closed: 1.0 belongs to it


def _report(
    confidences: Sequence[float],
    correct: Sequence[bool],
    squared_errors: Sequence[float],
    edges: Sequence[float],
) -> CalibrationReport:
    n = len(confidences)
    members: list[list[int]] = [[] for _ in range(len(edges) - 1)]
    for i, confidence in enumerate(confidences):
        members[_bin_index(confidence, edges)].append(i)
    bins: list[CalibrationBin] = []
    ece = 0.0
    for b, idx in enumerate(members):
        if idx:
            mean_confidence = sum(confidences[i] for i in idx) / len(idx)
            accuracy = sum(correct[i] for i in idx) / len(idx)
            ece += len(idx) / n * abs(accuracy - mean_confidence)
        else:
            mean_confidence = accuracy = None
        bins.append(
            CalibrationBin(
                lower=edges[b],
                upper=edges[b + 1],
                n=len(idx),
                mean_confidence=mean_confidence,
                accuracy=accuracy,
            )
        )
    return CalibrationReport(
        n=n,
        brier=sum(squared_errors) / n if n else None,
        ece=ece if n else None,
        bins=bins,
    )


def binary_calibration(pairs: Sequence[tuple[float, bool]]) -> CalibrationReport:
    """pairs: (p_yes, truth)."""
    return _report(
        confidences=[max(p, 1.0 - p) for p, _ in pairs],
        correct=[(p >= 0.5) == truth for p, truth in pairs],
        squared_errors=[(p - (1.0 if truth else 0.0)) ** 2 for p, truth in pairs],
        edges=BINARY_EDGES,
    )


def choice_calibration(
    items: Sequence[tuple[Mapping[str, float], str, str]], labels: Sequence[str]
) -> CalibrationReport:
    """items: (probabilities, predicted answer, truth). Labels absent from probabilities count 0."""
    return _report(
        confidences=[probs.get(answer, 0.0) for probs, answer, _ in items],
        correct=[answer == truth for _, answer, truth in items],
        squared_errors=[
            sum((probs.get(k, 0.0) - (1.0 if k == truth else 0.0)) ** 2 for k in labels)
            for probs, _, truth in items
        ],
        edges=CHOICE_EDGES,
    )


def calibrate_run(
    traces: Sequence[WorkflowTrace], cases: Sequence[PriorAuthCase]
) -> RunCalibration:
    binary: dict[DecisionId, list[tuple[float, bool]]] = {
        q: [] for q in DecisionId if q != DecisionId.MISSING_EVIDENCE
    }
    choice: list[tuple[Mapping[str, float], str, str]] = []
    invalid = 0
    for trace, case in paired_cases(traces, cases):
        if bundle_problem(trace.decisions) is not None:
            invalid += 1
            continue
        for decision in trace.decisions.decisions:
            if decision.question_id == DecisionId.MISSING_EVIDENCE:
                assert decision.answer is not None
                truth = case.ground_truth.missing_evidence.value
                choice.append((decision.probabilities, decision.answer, truth))
            else:
                assert decision.p_yes is not None
                truth_value = truth_flag(case.ground_truth, decision.question_id)
                binary[decision.question_id].append((decision.p_yes, truth_value))
    reports = {q.value: binary_calibration(pairs) for q, pairs in binary.items()}
    reports[DecisionId.MISSING_EVIDENCE.value] = choice_calibration(choice, MISSING_EVIDENCE_LABELS)
    return RunCalibration(
        decisions={q.value: reports[q.value] for q in DecisionId},
        invalid_excluded=invalid,
        partial_choice_distributions=sum(
            is_partial(probs, MISSING_EVIDENCE_LABELS) for probs, _, _ in choice
        ),
    )
