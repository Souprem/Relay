"""Deterministic policy engine: judgments + thresholds -> one workflow action with reasons.

Probability is a signal, not a permission slip. Gates run in a fixed order and the first gate
that fires decides the action.
"""

from relay.cases.models import CaseInput, MissingEvidence
from relay.cases.policies import AuthorizationPolicy
from relay.decisions.base import DecisionBundle, DecisionId
from relay.workflow.outcomes import GateResult, PolicyOutcome, WorkflowAction
from relay.workflow.thresholds import Thresholds

_CHOICE_DECISIONS = {DecisionId.MISSING_EVIDENCE}
_MISSING_LABELS = {m.value for m in MissingEvidence}


def bundle_problem(bundle: DecisionBundle) -> str | None:
    """Return why a bundle cannot be trusted by the engine, or None if it is well-formed."""
    if bundle.error:
        return bundle.error
    missing = bundle.missing_decisions()
    if missing:
        return "missing decisions: " + ", ".join(missing)
    if len(bundle.decisions) != len(DecisionId):
        return "duplicate decisions in bundle"
    for decision in bundle.decisions:
        expected = "choice" if decision.question_id in _CHOICE_DECISIONS else "yes_no"
        if decision.kind != expected:
            return f"{decision.question_id} has kind {decision.kind}, expected {expected}"
    missing_evidence = bundle.get(DecisionId.MISSING_EVIDENCE)
    assert missing_evidence is not None
    if missing_evidence.answer not in _MISSING_LABELS:
        return f"missing_evidence answer {missing_evidence.answer!r} is not a known label"
    return None


def _p_yes(bundle: DecisionBundle, question_id: DecisionId) -> float:
    decision = bundle.get(question_id)
    assert decision is not None and decision.p_yes is not None
    return decision.p_yes


def determine_action(
    case: CaseInput,
    bundle: DecisionBundle,
    policy: AuthorizationPolicy,
    thresholds: Thresholds,
) -> PolicyOutcome:
    t = thresholds
    path: list[GateResult] = []

    def passed(gate: str, detail: str) -> None:
        path.append(GateResult(gate=gate, fired=False, detail=detail))

    def fired(gate: str, detail: str, action: WorkflowAction, *reasons: str) -> PolicyOutcome:
        path.append(GateResult(gate=gate, fired=True, detail=detail))
        return PolicyOutcome(action=action, reasons=list(reasons), gate_path=path)

    problem = bundle_problem(bundle)
    if problem is not None:
        return fired(
            "provider", problem, WorkflowAction.HUMAN_REVIEW, f"provider failure: {problem}"
        )
    passed("provider", "all five decisions present and well-formed")

    age, min_age = case.patient.age, policy.min_age
    detail = f"patient.age={age}, policy min_age={min_age}"
    if age < min_age:
        return fired(
            "age",
            detail,
            WorkflowAction.HUMAN_REVIEW,
            f"patient age {age} is below the policy minimum of {min_age}",
        )
    passed("age", detail)

    contra = _p_yes(bundle, DecisionId.MATERIAL_CONTRADICTION)
    detail = f"p_yes(material_contradiction)={contra:.3f}, review at >= {t.contradiction_review}"
    if contra >= t.contradiction_review:
        return fired(
            "contradiction",
            detail,
            WorkflowAction.HUMAN_REVIEW,
            f"a material contradiction is likely (p={contra:.3f})",
        )
    passed("contradiction", detail)

    missing = bundle.get(DecisionId.MISSING_EVIDENCE)
    assert missing is not None and missing.answer is not None
    missing_label = missing.answer.lower().replace("_", " ")
    doc = _p_yes(bundle, DecisionId.DOCUMENTATION_COMPLETE)
    detail = (
        f"p_yes(documentation_complete)={doc:.3f}, "
        f"request info below {t.documentation_request_info}"
    )
    if doc < t.documentation_request_info:
        reasons = [f"documentation is likely incomplete (p_yes={doc:.3f})"]
        if missing.answer != MissingEvidence.NONE:
            reasons.append(f"most likely missing: {missing_label} (p={missing.probability:.3f})")
        return fired("documentation", detail, WorkflowAction.REQUEST_INFO, *reasons)
    passed("documentation", detail)

    detail = (
        f"missing_evidence={missing.answer} (p={missing.probability:.3f}), "
        f"request info at >= {t.missing_evidence_request_info}"
    )
    if (
        missing.answer != MissingEvidence.NONE
        and missing.probability >= t.missing_evidence_request_info
    ):
        return fired(
            "missing_evidence",
            detail,
            WorkflowAction.REQUEST_INFO,
            f"missing {missing_label} (p={missing.probability:.3f})",
        )
    passed("missing_evidence", detail)

    required = {
        "diagnosis_support": _p_yes(bundle, DecisionId.DIAGNOSIS_SUPPORT),
        "step_therapy": _p_yes(bundle, DecisionId.STEP_THERAPY),
        "documentation_complete": doc,
    }
    below = [
        f"{name} p_yes={p:.3f} is below the {t.auto_process} autonomous-action bar"
        for name, p in required.items()
        if p < t.auto_process
    ]
    blocked = contra >= t.contradiction_auto_block
    detail = (
        f"min(required p_yes)={min(required.values()):.3f}, auto at >= {t.auto_process}; "
        f"p_yes(material_contradiction)={contra:.3f}, blocks at >= {t.contradiction_auto_block}"
    )
    if not below and not blocked:
        return fired(
            "auto_process",
            detail,
            WorkflowAction.AUTO_PROCESS,
            f"all required judgments are at or above {t.auto_process} and contradiction "
            f"risk is below {t.contradiction_auto_block}",
        )
    passed("auto_process", detail)

    reasons = list(below)
    if blocked:
        reasons.append(
            f"contradiction risk p={contra:.3f} blocks autonomous processing "
            f"(>= {t.contradiction_auto_block})"
        )
    return fired(
        "default_review",
        "case does not meet the autonomous-action bar",
        WorkflowAction.HUMAN_REVIEW,
        *reasons,
    )
