"""CaseFacts -> GroundTruth: what the rendered documents establish under policy immunara-v0.1.

Rules are applied in a fixed order (spec section 3.4). The generator never writes an action;
expected actions are derived from these facts by the policy engine.
"""

from relay.cases.models import GroundTruth, MissingEvidence
from relay.generation.dates import conservative_end, conservative_start
from relay.generation.facts import GENERATOR_VERSION, CaseFacts

MIN_DAYS = 84  # immunara-v0.1 requires 12 weeks of methotrexate: 12 * 7 = 84 days
_OUTCOMES_THAT_COUNT = frozenset({"inadequate_response", "intolerance"})


def conservative_days(facts: CaseFacts) -> int | None:
    """Conservative treatment length the documents establish, or None if a date lacks a year."""
    if facts.mtx_status != "taken":
        return None
    assert facts.mtx_start is not None and facts.start_precision is not None
    start = conservative_start(facts.mtx_start, facts.start_precision)
    if facts.mtx_end is None:
        end = facts.as_of_date
    else:
        assert facts.end_precision is not None
        end = conservative_end(facts.mtx_end, facts.end_precision)
    if start is None or end is None:
        return None
    return (end - start).days


def _date_lacks_year(facts: CaseFacts) -> bool:
    return facts.start_precision == "no_year" or (
        facts.mtx_end is not None and facts.end_precision == "no_year"
    )


def _missing_evidence(facts: CaseFacts) -> MissingEvidence:
    if facts.diagnosis_status != "established":
        return MissingEvidence.DIAGNOSIS
    if facts.mtx_status == "undocumented":
        return MissingEvidence.TREATMENT_HISTORY
    if facts.mtx_status == "taken" and facts.contradiction is None and _date_lacks_year(facts):
        return MissingEvidence.TREATMENT_HISTORY
    if facts.member_id is None:
        return MissingEvidence.INSURANCE_INFORMATION
    return MissingEvidence.NONE


def _notes(facts: CaseFacts, days: int | None) -> str:
    head = f"{GENERATOR_VERSION} {facts.difficulty}: mtx {facts.mtx_status}"
    if facts.mtx_status == "taken":
        assert facts.mtx_start is not None
        actual_end = facts.mtx_end or facts.as_of_date
        end_precision = facts.end_precision or "ongoing"
        conservative = "unknown" if days is None else f"{days}d"
        head += (
            f" {(actual_end - facts.mtx_start).days}d actual, {conservative} conservative "
            f"(start {facts.start_precision}, end {end_precision}), {facts.mtx_outcome}"
        )
    flags = [f"diagnosis {facts.diagnosis_status}"]
    if facts.member_id is None:
        flags.append("no member id")
    if facts.contradiction is not None:
        flags.append(f"contradiction {facts.contradiction}")
    if facts.split_across_documents:
        flags.append("split docs")
    if facts.other_dmards:
        flags.append("other DMARD " + ", ".join(facts.other_dmards))
    if facts.relative_distractor:
        flags.append("relative distractor")
    if facts.injection:
        flags.append("injection")
    if facts.stale_note:
        flags.append("stale note")
    if facts.difficulty == "hard" and facts.mtx_status == "taken":
        flags.append("near-miss")
    return head + "; " + ", ".join(flags)


def label_case(facts: CaseFacts) -> GroundTruth:
    days = conservative_days(facts)
    duration_ok = facts.contradiction is None and days is not None and days >= MIN_DAYS
    missing = _missing_evidence(facts)
    return GroundTruth(
        diagnosis_supported=facts.diagnosis_status == "established",
        step_therapy_satisfied=duration_ok and facts.mtx_outcome in _OUTCOMES_THAT_COUNT,
        documentation_complete=missing is MissingEvidence.NONE,
        contradiction_present=facts.contradiction is not None,
        missing_evidence=missing,
        notes=_notes(facts, days),
    )
