"""CaseFacts -> GroundTruth: what the rendered documents establish under a policy.

Rules are applied in a fixed order (spec section 3.4). The generator never writes an action;
expected actions are derived from these facts by the policy engine. The policy defaults to
immunara-v0.1; gen-v0.3 labels each case under its own policy_id, so the same facts can be
labelled under immunara-v0.1 and immunara-v0.2 (which adds a recency rule).

Interrupted courses follow the gold guide's rule D8: each segment is measured on its own and
only a single segment of at least min_weeks * 7 days counts. Under a recency rule, that segment
must also end (an ongoing one ends at as_of) no more than max_days_since_therapy days before
as_of, measured from its conservative end.
"""

from datetime import date

from relay.cases.models import GroundTruth, MissingEvidence
from relay.cases.policies import AuthorizationPolicy, load_policy
from relay.generation.dates import conservative_end, conservative_start
from relay.generation.facts import CaseFacts

MIN_DAYS = 84  # immunara-v0.1 requires 12 weeks of methotrexate: 12 * 7 = 84 days
_OUTCOMES_THAT_COUNT = frozenset({"inadequate_response", "intolerance"})
_DEFAULT_POLICY = "immunara-v0.1"


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


def segment_days(facts: CaseFacts) -> tuple[int, ...]:
    """Each segment's length in days (day precision), an ongoing one counted to as_of."""
    assert facts.mtx_segments is not None
    return tuple(((end or facts.as_of_date) - start).days for start, end in facts.mtx_segments)


def days_since_end(facts: CaseFacts) -> int | None:
    """Days from the course's conservative final end to as_of (0 when ongoing), or None."""
    if facts.mtx_status != "taken":
        return None
    if facts.mtx_end is None:
        return 0
    assert facts.end_precision is not None
    end = conservative_end(facts.mtx_end, facts.end_precision)
    return None if end is None else (facts.as_of_date - end).days


def _qualifying_ends(facts: CaseFacts, min_days: int) -> list[date]:
    """The conservative end (as_of if ongoing) of every course or segment long enough."""
    if facts.mtx_segments is not None:
        return [
            end or facts.as_of_date
            for (start, end), days in zip(facts.mtx_segments, segment_days(facts), strict=True)
            if days >= min_days
        ]
    days = conservative_days(facts)
    if days is None or days < min_days:
        return []
    if facts.mtx_end is None:
        return [facts.as_of_date]
    assert facts.end_precision is not None
    end = conservative_end(facts.mtx_end, facts.end_precision)
    assert end is not None  # conservative_days would be None otherwise
    return [end]


def duration_satisfied(facts: CaseFacts, policy: AuthorizationPolicy) -> bool:
    """A single course or segment is long enough and, under a recency rule, recent enough."""
    if facts.contradiction is not None:
        return False
    limit = policy.max_days_since_therapy
    return any(
        limit is None or (facts.as_of_date - end).days <= limit
        for end in _qualifying_ends(facts, policy.min_weeks * 7)
    )


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
    """A machine-written summary that mentions only what the rendered documents show."""
    head = f"{facts.generator_version} {facts.difficulty}: mtx {facts.mtx_status}"
    if facts.mtx_segments is not None:
        first, second = segment_days(facts)
        head += (
            f" interrupted ({facts.interruption_reason}, pattern {facts.interruption_variant}): "
            f"segments {first}d and {second}d, {facts.mtx_outcome}"
        )
    elif facts.mtx_status == "taken":
        assert facts.mtx_start is not None
        actual_end = facts.mtx_end or facts.as_of_date
        end_precision = facts.end_precision or "ongoing"
        conservative = "unknown" if days is None else f"{days}d"
        if facts.contradiction == "dates_conflict":
            assert facts.history_start is not None
            head += (
                f" note {(actual_end - facts.mtx_start).days}d, "
                f"history {(actual_end - facts.history_start).days}d "
                f"(start day, end {end_precision}), {facts.mtx_outcome}"
            )
        else:
            head += (
                f" {(actual_end - facts.mtx_start).days}d actual, {conservative} conservative "
                f"(start {facts.start_precision}, end {end_precision})"
            )
            # A history_vs_note note denies methotrexate, so no outcome is rendered.
            if facts.contradiction is None:
                head += f", {facts.mtx_outcome}"
    flags = [f"diagnosis {facts.diagnosis_status}"]
    if facts.member_id is None:
        flags.append("no member id")
    if facts.contradiction is not None:
        flags.append(f"contradiction {facts.contradiction}")
    if facts.split_across_documents:
        flags.append("split docs")
    if facts.other_dmards and facts.mtx_status != "undocumented":
        flags.append("other DMARD " + ", ".join(facts.other_dmards))
    if facts.relative_distractor:
        flags.append("relative distractor")
    if facts.injection:
        flags.append("injection")
    if facts.stale_note:
        flags.append("stale note")
    near_miss_course = (
        facts.mtx_status == "taken"
        and facts.contradiction != "dates_conflict"
        and facts.mtx_segments is None
    )
    if facts.difficulty == "hard" and near_miss_course:
        flags.append("near-miss")
    since = days_since_end(facts)
    if facts.generator_version != "gen-v0.2" and since is not None and facts.mtx_end is not None:
        flags.append(f"ended {since}d before as-of")
    return head + "; " + ", ".join(flags)


def label_case(facts: CaseFacts, policy: AuthorizationPolicy | None = None) -> GroundTruth:
    """Ground truth under `policy` (default immunara-v0.1)."""
    policy = policy or load_policy(_DEFAULT_POLICY)
    days = conservative_days(facts)
    missing = _missing_evidence(facts)
    return GroundTruth(
        diagnosis_supported=facts.diagnosis_status == "established",
        step_therapy_satisfied=duration_satisfied(facts, policy)
        and facts.mtx_outcome in _OUTCOMES_THAT_COUNT,
        documentation_complete=missing is MissingEvidence.NONE,
        contradiction_present=facts.contradiction is not None,
        missing_evidence=missing,
        notes=_notes(facts, days),
    )
