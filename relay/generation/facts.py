"""The latent scenario behind one generated case: what happened and how it is documented."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

# GENERATOR_VERSION names the frozen gen-v0.2 manifests and stays the default. gen-v0.3 (Phase 3D)
# adds interrupted courses and old courses; generate with generator_version=GEN_V0_3.
GENERATOR_VERSION = "gen-v0.2"
GEN_V0_2 = GENERATOR_VERSION
GEN_V0_3 = "gen-v0.3"
GENERATOR_VERSIONS: tuple[str, ...] = (GEN_V0_2, GEN_V0_3)

Difficulty = Literal["easy", "medium", "hard", "adversarial"]
DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard", "adversarial")

Precision = Literal["day", "month", "no_year"]
DiagnosisStatus = Literal["established", "pending", "absent"]
MtxStatus = Literal["taken", "never", "undocumented", "relative_only"]
MtxOutcome = Literal["inadequate_response", "intolerance", "not_stated"]
ContradictionKind = Literal["history_vs_note", "dates_conflict"]
# gen-v0.3 interrupted courses (gold guide rule D8): (a) no segment reaches the minimum although
# the total span does (the GOLD-TMP-17 pattern); (b) the later segment qualifies (GOLD-TMP-18);
# (c) the earlier segment qualifies.
InterruptionVariant = Literal["a", "b", "c"]
InterruptionReason = Literal["infection", "surgery", "travel", "lab"]


@dataclass(frozen=True)
class CaseFacts:
    """Everything the renderer and labeller need. Never shown to a decision provider.

    Invariants (enforced by scenarios.sample_facts, relied on by render and labels):
    - mtx_start and start_precision are set exactly when mtx_status == "taken".
    - mtx_end is None when treatment is ongoing (or not taken); end_precision is None then.
    - mtx_outcome is "not_stated" unless mtx_status == "taken".
    - contradiction is set only when mtx_status == "taken"; both dates are then day precision.
    - history_start is set exactly when contradiction == "dates_conflict": the earlier start the
      medication history states. The note states mtx_start (a course under 12 weeks); the history
      start gives at least 12 weeks; both sources share the same stop date.
    - note_date == as_of_date when a methotrexate course is ongoing (mtx_status "taken" and
      mtx_end None), so "continues today" is dated at the day the length is counted to.
    - start_precision and end_precision are never "no_year" from sample_facts (gen-v0.2); the
      value remains valid for hand-built facts.
    - stale_note_date is set exactly when stale_note is true.
    - (gen-v0.3) mtx_segments is set only when mtx_status == "taken" and contradiction is None:
      two (start, end) segments, the second end None when ongoing. Then mtx_start is the first
      start, mtx_end the final end, both precisions are "day", split_across_documents is False,
      and interruption_variant and interruption_reason are set (they are None otherwise).
    """

    case_id: str
    difficulty: Difficulty
    as_of_date: date
    note_date: date
    age: int
    state: str
    payer: str
    plan: str
    member_id: str | None
    diagnosis_status: DiagnosisStatus
    diagnosis_year: int
    mtx_status: MtxStatus
    mtx_start: date | None
    mtx_end: date | None
    start_precision: Precision | None
    end_precision: Precision | None
    split_across_documents: bool
    medication_history: bool
    mtx_outcome: MtxOutcome
    other_dmards: tuple[str, ...]
    irrelevant_meds: tuple[str, ...]
    contradiction: ContradictionKind | None
    history_start: date | None
    injection: bool
    relative_distractor: bool
    stale_note: bool
    stale_note_date: date | None
    noise: float

    # gen-v0.3 only; the defaults are every gen-v0.2 case.
    generator_version: str = GEN_V0_2
    mtx_segments: tuple[tuple[date, date | None], ...] | None = None
    interruption_variant: InterruptionVariant | None = None
    interruption_reason: InterruptionReason | None = None
