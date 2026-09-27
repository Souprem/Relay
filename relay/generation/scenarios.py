"""Difficulty profiles and sampling of CaseFacts from a seeded Random.

Every random draw happens in a fixed order, so the same Random state always yields the same facts.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from random import Random

from relay.generation.facts import (
    DIFFICULTIES,
    GEN_V0_2,
    GEN_V0_3,
    GENERATOR_VERSIONS,
    CaseFacts,
    ContradictionKind,
    DiagnosisStatus,
    Difficulty,
    InterruptionReason,
    InterruptionVariant,
    MtxOutcome,
    MtxStatus,
    Precision,
)

AS_OF_MIN = date(2026, 6, 1)
AS_OF_MAX = date(2026, 12, 15)
STATES: tuple[str, ...] = ("CA", "FL", "GA", "IL", "MA", "MI", "NC", "NY", "OH", "PA", "TX", "WA")
# (payer, plan, member-id prefix): the three fictional plans used by the v0.1 smoke cases.
PLANS: tuple[tuple[str, str, str], ...] = (
    ("ExampleHealth", "ExampleHealth Gold", "EXH"),
    ("CivicCare", "CivicCare Plus", "CCP"),
    ("Northstar", "Northstar Choice", "NSC"),
)
OTHER_DMARDS: tuple[str, ...] = (
    "hydroxychloroquine 200 mg twice daily",
    "sulfasalazine 1000 mg twice daily",
    "leflunomide 20 mg daily",
)
IRRELEVANT_MEDS: tuple[str, ...] = (
    "CETIRIZINE 10 MG PO DAILY",
    "IBUPROFEN 400 MG PO AS NEEDED",
    "LISINOPRIL 10 MG PO DAILY",
    "ATORVASTATIN 20 MG PO NIGHTLY",
    "OMEPRAZOLE 20 MG PO DAILY",
    "VITAMIN D3 1000 IU PO DAILY",
)
ADVERSARIAL_FEATURES: tuple[str, ...] = ("other_dmard", "relative", "injection", "stale_note")
CONTRADICTION_KINDS: tuple[ContradictionKind, ...] = ("history_vs_note", "dates_conflict")
# dates_conflict: the note's course is 6-10 weeks (under 12 on its own) and the medication history
# starts a further 6-10 weeks earlier (at least 12 weeks on its own), same stop date.
CONFLICT_NOTE_DAYS = (42, 70)
CONFLICT_EXTRA_DAYS = (42, 70)
OUTCOMES_ENDED: tuple[MtxOutcome, ...] = ("inadequate_response", "intolerance", "not_stated")
OUTCOME_WEIGHTS_ENDED: tuple[float, ...] = (0.6, 0.25, 0.15)
OUTCOMES_ONGOING: tuple[MtxOutcome, ...] = ("inadequate_response", "not_stated")
OUTCOME_WEIGHTS_ONGOING: tuple[float, ...] = (0.8, 0.2)

# gen-v0.3 (Phase 3D). About 20% of taken-methotrexate courses are interrupted: eligible courses
# (taken, no contradiction) are interrupted with INTERRUPTED_PROBABILITY; the audit checks the
# share over all taken courses against 20% +/- 5 pp. Variants are equally likely.
INTERRUPTED_PROBABILITY = 0.24
INTERRUPTION_VARIANTS: tuple[InterruptionVariant, ...] = ("a", "b", "c")
INTERRUPTION_REASONS: tuple[InterruptionReason, ...] = ("infection", "surgery", "travel", "lab")
HOLD_DAYS = (14, 56)  # the gap between the pause and the restart
# Segment lengths in days, (first, second), per variant. Short segments stay at least 7 days
# under the 84-day minimum and long ones 14 days over it, so no segment is a near miss;
# pattern (a)'s total span (first + hold + second) always reaches 84.
SEGMENT_DAYS: dict[InterruptionVariant, tuple[tuple[int, int], tuple[int, int]]] = {
    "a": ((42, 77), (28, 77)),
    "b": ((21, 70), (98, 180)),
    "c": ((98, 180), (21, 70)),
}
# About 25% of taken courses ended more than 365 days before as_of. Only ended courses can be
# old, and ongoing courses are 20% of taken ones, so an ended course is moved back with
# probability 0.25 / 0.8. Its final end then lands 380-720 days before as_of.
OLD_COURSE_PROBABILITY = 0.3125
OLD_COURSE_GAP_DAYS = (380, 720)


@dataclass(frozen=True)
class DifficultyProfile:
    precisions: tuple[Precision, ...]
    precision_weights: tuple[float, ...]
    split_probability: float
    medication_history_probability: float
    contradiction_probability: float
    missing_data_probability: float
    note_noise: float
    near_miss: bool
    boundary_age_probability: float
    co_dmard_probability: float
    adversarial: bool


PROFILES: dict[Difficulty, DifficultyProfile] = {
    "easy": DifficultyProfile(
        precisions=("day",),
        precision_weights=(1.0,),
        split_probability=0.0,
        medication_history_probability=0.0,
        contradiction_probability=0.0,
        missing_data_probability=0.25,
        note_noise=0.0,
        near_miss=False,
        boundary_age_probability=0.0,
        co_dmard_probability=0.0,
        adversarial=False,
    ),
    "medium": DifficultyProfile(
        precisions=("day", "month"),
        precision_weights=(0.5, 0.5),
        split_probability=0.6,
        medication_history_probability=0.5,
        contradiction_probability=0.05,
        missing_data_probability=0.30,
        note_noise=0.3,
        near_miss=False,
        boundary_age_probability=0.0,
        co_dmard_probability=0.2,
        adversarial=False,
    ),
    "hard": DifficultyProfile(
        precisions=("day", "month"),
        precision_weights=(0.45, 0.55),
        split_probability=0.6,
        medication_history_probability=0.5,
        contradiction_probability=0.35,
        missing_data_probability=0.30,
        note_noise=0.5,
        near_miss=True,
        boundary_age_probability=0.25,
        co_dmard_probability=0.2,
        adversarial=False,
    ),
    "adversarial": DifficultyProfile(
        precisions=("day", "month"),
        precision_weights=(0.55, 0.45),
        split_probability=0.5,
        medication_history_probability=0.5,
        contradiction_probability=0.15,
        missing_data_probability=0.30,
        note_noise=0.7,
        near_miss=False,
        boundary_age_probability=0.0,
        co_dmard_probability=0.0,
        adversarial=True,
    ),
}


def _check_probability(name: str, value: float) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1, got {value}")
    return value


def _days(rng: Random, low: int, high: int) -> timedelta:
    return timedelta(days=rng.randint(low, high))


def sample_facts(
    rng: Random,
    *,
    case_id: str,
    difficulty: Difficulty,
    contradiction_probability: float | None = None,
    missing_data_probability: float | None = None,
    note_noise: float | None = None,
    generator_version: str = GEN_V0_2,
) -> CaseFacts:
    if generator_version not in GENERATOR_VERSIONS:
        raise ValueError(
            f"unknown generator version {generator_version!r}; allowed: {list(GENERATOR_VERSIONS)}"
        )
    if difficulty not in PROFILES:
        raise ValueError(f"unknown difficulty {difficulty!r}; allowed: {list(DIFFICULTIES)}")
    profile = PROFILES[difficulty]
    p_contradiction = _check_probability(
        "contradiction_probability",
        profile.contradiction_probability
        if contradiction_probability is None
        else contradiction_probability,
    )
    p_missing = _check_probability(
        "missing_data_probability",
        profile.missing_data_probability
        if missing_data_probability is None
        else missing_data_probability,
    )
    noise = _check_probability(
        "note_noise", profile.note_noise if note_noise is None else note_noise
    )

    # 1. Identity and structured fields.
    as_of = AS_OF_MIN + _days(rng, 0, (AS_OF_MAX - AS_OF_MIN).days)
    note_date = as_of - _days(rng, 0, 10)
    if rng.random() < profile.boundary_age_probability:
        age = rng.randint(16, 19)
    else:
        age = rng.randint(25, 78)
    state = rng.choice(STATES)
    payer, plan, prefix = rng.choice(PLANS)
    member_id: str | None = f"{prefix}-{rng.randint(100000, 999999)}"

    # 2. Treatment timeline (always sampled; kept only if methotrexate was taken).
    if profile.near_miss:
        duration = _days(rng, 56, 105)  # 8-15 weeks, straddling the 12-week line
    elif rng.random() < 0.7:
        duration = _days(rng, 112, 210)  # 16-30 weeks: clearly sufficient at day precision
    else:
        duration = _days(rng, 28, 56)  # 4-8 weeks: clearly short
    ongoing = rng.random() < 0.2
    mtx_end: date | None = None if ongoing else note_date - _days(rng, 7, 90)
    start = (mtx_end or as_of) - duration
    mtx_start: date | None = start
    start_precision: Precision | None = rng.choices(profile.precisions, profile.precision_weights)[
        0
    ]
    end_precision: Precision | None = (
        None if ongoing else rng.choices(profile.precisions, profile.precision_weights)[0]
    )
    if ongoing:
        mtx_outcome: MtxOutcome = rng.choices(OUTCOMES_ONGOING, OUTCOME_WEIGHTS_ONGOING)[0]
    else:
        mtx_outcome = rng.choices(OUTCOMES_ENDED, OUTCOME_WEIGHTS_ENDED)[0]
    diagnosis_status: DiagnosisStatus = "established"
    diagnosis_year = start.year - rng.randint(0, 4)
    mtx_status: MtxStatus = "taken"
    split = rng.random() < profile.split_probability
    medication_history = split or rng.random() < profile.medication_history_probability
    irrelevant_meds = tuple(rng.sample(IRRELEVANT_MEDS, rng.randint(1, 3)))
    other_dmards: tuple[str, ...] = ()
    if rng.random() < profile.co_dmard_probability:
        other_dmards = (rng.choice(OTHER_DMARDS),)

    # 3. Adversarial features (at least one on adversarial cases).
    injection = relative_distractor = stale_note = False
    if profile.adversarial:
        features = rng.sample(ADVERSARIAL_FEATURES, rng.choice((1, 1, 2)))
        if "other_dmard" in features:
            mtx_status = "never"
            other_dmards = (rng.choice(OTHER_DMARDS),)
        if "relative" in features:
            relative_distractor = True
            if mtx_status == "taken" and rng.random() < 0.5:
                mtx_status = "relative_only"
        injection = "injection" in features
        stale_note = "stale_note" in features

    # 4. Documentation gap. (Yearless dates are out of scope from gen-v0.2: see facts.py.)
    if rng.random() < p_missing:
        gaps = ["diagnosis", "member_id"]
        if mtx_status == "taken":
            gaps.append("treatment_history")
        gap = rng.choice(gaps)
        if gap == "diagnosis":
            diagnosis_status = rng.choice(("pending", "absent"))
        elif gap == "member_id":
            member_id = None
        else:
            mtx_status = "undocumented"

    # 5. Contradiction (needs a documented methotrexate course with full dates).
    contradiction: ContradictionKind | None = None
    history_start: date | None = None
    if mtx_status == "taken" and rng.random() < p_contradiction:
        contradiction = rng.choice(CONTRADICTION_KINDS)
        start_precision = "day"
        end_precision = None if ongoing else "day"
        split = False
        medication_history = True
        if contradiction == "dates_conflict":
            mtx_start = (mtx_end or as_of) - _days(rng, *CONFLICT_NOTE_DAYS)
            history_start = mtx_start - _days(rng, *CONFLICT_EXTRA_DAYS)
            diagnosis_year = min(diagnosis_year, history_start.year)

    # 5b. gen-v0.3 only: interrupted courses, then old courses. gen-v0.2 draws nothing here, so
    # its facts (and every later draw) are unchanged.
    mtx_segments: tuple[tuple[date, date | None], ...] | None = None
    variant: InterruptionVariant | None = None
    reason: InterruptionReason | None = None
    if generator_version == GEN_V0_3 and mtx_status == "taken":
        if contradiction is None and rng.random() < INTERRUPTED_PROBABILITY:
            variant = rng.choice(INTERRUPTION_VARIANTS)
            reason = rng.choice(INTERRUPTION_REASONS)
            (first_low, first_high), (second_low, second_high) = SEGMENT_DAYS[variant]
            first = rng.randint(first_low, first_high)
            hold = rng.randint(*HOLD_DAYS)
            second = rng.randint(second_low, second_high)
            restart = (mtx_end or as_of) - timedelta(days=second)
            pause = restart - timedelta(days=hold)
            mtx_start = pause - timedelta(days=first)
            mtx_segments = ((mtx_start, pause), (restart, mtx_end))
            start_precision = "day"
            end_precision = None if ongoing else "day"
            split = False
        if mtx_end is not None and rng.random() < OLD_COURSE_PROBABILITY:
            shift = timedelta(days=rng.randint(*OLD_COURSE_GAP_DAYS) - (as_of - mtx_end).days)
            mtx_end -= shift
            assert mtx_start is not None
            mtx_start -= shift
            if history_start is not None:
                history_start -= shift
            if mtx_segments is not None:
                (s1, p1), (r2, e2) = mtx_segments
                assert e2 is not None
                mtx_segments = ((s1 - shift, p1 - shift), (r2 - shift, e2 - shift))
        assert mtx_start is not None
        diagnosis_year = min(diagnosis_year, (history_start or mtx_start).year)

    # 6. Normalize fields that only apply to a documented methotrexate course.
    if mtx_status != "taken":
        mtx_start = mtx_end = None
        start_precision = end_precision = None
        mtx_outcome = "not_stated"
        split = False
    if mtx_status == "undocumented":
        medication_history = False
    if mtx_status == "taken" and mtx_end is None:
        note_date = as_of  # "continues today" is dated at the as-of date the length counts to
    stale_note_date: date | None = None
    if stale_note:
        anchor = history_start or mtx_start or (as_of - timedelta(days=210))
        stale_note_date = anchor - _days(rng, 14, 90)

    return CaseFacts(
        case_id=case_id,
        difficulty=difficulty,
        as_of_date=as_of,
        note_date=note_date,
        age=age,
        state=state,
        payer=payer,
        plan=plan,
        member_id=member_id,
        diagnosis_status=diagnosis_status,
        diagnosis_year=diagnosis_year,
        mtx_status=mtx_status,
        mtx_start=mtx_start,
        mtx_end=mtx_end,
        start_precision=start_precision,
        end_precision=end_precision,
        split_across_documents=split,
        medication_history=medication_history,
        mtx_outcome=mtx_outcome,
        other_dmards=other_dmards,
        irrelevant_meds=irrelevant_meds,
        contradiction=contradiction,
        history_start=history_start,
        injection=injection,
        relative_distractor=relative_distractor,
        stale_note=stale_note,
        stale_note_date=stale_note_date,
        noise=noise,
        generator_version=generator_version,
        mtx_segments=mtx_segments,
        interruption_variant=variant,
        interruption_reason=reason,
    )
