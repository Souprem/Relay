"""Rules-only baseline provider: explicit textual and structured cues -> the five decisions.

Deterministic and network-free. Every probability is 1.0 (explicit cue for yes), 0.0 (explicit
cue for no) or 0.5 (abstain): the rules are a transparent floor, not a calibrated model. They read
`CaseInput` only (structured fields and document text), never ground truth. Rule definitions are
in the pattern tables and helpers in this module.

Scoping: documents are split into lines. A line that mentions a relative is excluded from every
patient rule, and fax-cover lines are used only for the member-ID check, so injected fax text can
never count as clinical evidence.
"""

import hashlib
import json
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from relay.cases.models import CaseInput, MissingEvidence
from relay.cases.policies import AuthorizationPolicy, load_policy
from relay.decisions.base import Decision, DecisionBundle, DecisionId
from relay.decisions.date_parse import ISO_DATE, LONG_DATE, find_day_dates

PROVIDER_NAME = "rules"
RULES_VERSION = "rules-v0.1"
YES, NO, ABSTAIN = 1.0, 0.0, 0.5
MAX_MATCH_CHARS = 200

# Every pattern the rules use. question_set_hash is the SHA-256 of this table as sorted JSON, so
# any wording change produces a new hash. All patterns are matched case-insensitively.
PATTERNS: dict[str, str] = {
    "mtx": r"\b(methotrexate|mtx)\b",
    "relative": (
        r"\b(mother|father|sister|brother|aunt|uncle|grandmother|grandfather|family history)\b"
    ),
    "member_id_missing": r"member id[^.;\n]*?(not provided|not on file|missing)",
    "ra": r"rheumatoid arthritis",
    "dx_keyword": r"\b(diagnos\w*|established|seropositive|seronegative)\b",
    "dx_negator": r"(pending|suspected|not yet established|differential|rule out|workup|undiagnosed)",
    "mtx_never": r"(never (tried|taken|took|received)|has not (taken|tried|received)|not taken)",
    "date_role": (
        r"\b(?:(?P<start>start|started|began|initiated|since|from)"
        r"|(?P<stop>stop|stopped|discontinued|ended|end|until))\b"
    ),
    "to_before_date": r"\bto\s+$",
    "mtx_ongoing": r"(continues|still taking|currently taking|remains on|ongoing|\bactive\b)",
    "records_unavailable": (
        r"(records? (were )?not available|unsure which medications|history (is )?unknown)"
    ),
    "mtx_response": (
        r"(inadequate response|did not improve|no improvement|not improve|persistent"
        r"|intoleran|side effect|nausea|contraindicat)"
    ),
    "iso_date": ISO_DATE,
    "long_date": LONG_DATE,
}
_RE: dict[str, re.Pattern[str]] = {
    name: re.compile(pattern, re.IGNORECASE) for name, pattern in PATTERNS.items()
}


def rules_hash() -> str:
    blob = json.dumps(PATTERNS, sort_keys=True)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Line:
    document_id: str
    kind: str
    number: int  # 1-based line number within the document
    text: str

    @property
    def is_fax(self) -> bool:
        return self.kind == "fax_cover"

    @property
    def is_patient(self) -> bool:
        """Usable for patient rules: not a fax-cover line and not about a relative."""
        return not self.is_fax and _RE["relative"].search(self.text) is None

    @property
    def is_patient_mtx(self) -> bool:
        return self.is_patient and _RE["mtx"].search(self.text) is not None

    def search(self, pattern: str) -> re.Match[str] | None:
        return _RE[pattern].search(self.text)


def split_lines(case: CaseInput) -> list[Line]:
    return [
        Line(doc.id, doc.kind, number, text)
        for doc in case.documents
        for number, text in enumerate(doc.text.splitlines(), start=1)
    ]


@dataclass(frozen=True)
class Fired:
    """One rule firing: which rule, where, and the text that triggered it."""

    rule: str
    document_id: str | None
    line: int | None
    match: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "document_id": self.document_id,
            "line": self.line,
            "match": self.match[:MAX_MATCH_CHARS],
        }


def _fire(rule: str, line: Line, text: str | None = None) -> Fired:
    return Fired(rule, line.document_id, line.number, (text or line.text).strip())


def member_missing(case: CaseInput, lines: Sequence[Line]) -> list[Fired]:
    fired: list[Fired] = []
    if case.insurance.member_id is None:
        fired.append(Fired("member_missing", None, None, "insurance.member_id is None"))
    for line in lines:
        if line.is_fax and (match := line.search("member_id_missing")):
            fired.append(_fire("member_missing", line, match.group(0)))
    return fired


def dx_established(lines: Sequence[Line]) -> list[Fired]:
    return [
        _fire("dx_established", line)
        for line in lines
        if line.kind == "physician_note"
        and line.is_patient
        and line.search("ra")
        and line.search("dx_keyword")
        and not line.search("dx_negator")
    ]


def dx_negated(lines: Sequence[Line], established: Sequence[Fired]) -> list[Fired]:
    """A negator near the diagnosis (same line), or anywhere in a note with no established line."""
    established_docs = {f.document_id for f in established}
    fired: list[Fired] = []
    for line in lines:
        if line.kind != "physician_note" or not line.is_patient or not line.search("dx_negator"):
            continue
        if line.search("ra") or line.document_id not in established_docs:
            fired.append(_fire("dx_negated", line))
    return fired


def diagnosis_p(established: Sequence[Fired], negated: Sequence[Fired]) -> float:
    if established and not negated:
        return YES
    if negated and not established:
        return NO
    return ABSTAIN


def mtx_never(lines: Sequence[Line]) -> list[Fired]:
    return [
        _fire("mtx_never", line, match.group(0))
        for line in lines
        if line.is_patient_mtx and (match := line.search("mtx_never"))
    ]


DateRole = Literal["start", "stop"]


@dataclass(frozen=True)
class DatedMention:
    role: DateRole
    when: date
    fired: Fired


def _date_role(segment: str) -> DateRole | None:
    """The role of a date from the text before it: the nearest start/stop keyword wins."""
    if _RE["to_before_date"].search(segment):
        return "stop"
    matches = list(_RE["date_role"].finditer(segment))
    if not matches:
        return None
    return "start" if matches[-1].group("start") else "stop"


def mtx_dates(lines: Sequence[Line]) -> list[DatedMention]:
    """Day-precision methotrexate start and stop dates on patient lines.

    Each date takes its role from the nearest start/stop keyword between it and the previous date
    on the same line, so "started 2026-01-12 ... discontinued 2026-06-01" yields one start and one
    stop, and "from <date> to <date>" yields a start and a stop. A date with no keyword before it
    is ignored.
    """
    mentions: list[DatedMention] = []
    for line in lines:
        if not line.is_patient_mtx:
            continue
        previous_end = 0
        for when, (start, end) in find_day_dates(line.text):
            segment = line.text[previous_end:start]
            role = _date_role(segment)
            if role is not None:
                text = line.text[previous_end:end]
                mentions.append(DatedMention(role, when, _fire(f"mtx_{role}", line, text)))
            previous_end = end
    return mentions


def mtx_ongoing(lines: Sequence[Line]) -> list[Fired]:
    return [
        _fire("mtx_ongoing", line, match.group(0))
        for line in lines
        if line.is_patient_mtx and (match := line.search("mtx_ongoing"))
    ]


def records_unavailable(lines: Sequence[Line]) -> list[Fired]:
    return [
        _fire("records_unavailable", line, match.group(0))
        for line in lines
        if line.is_patient and (match := line.search("records_unavailable"))
    ]


def mtx_conflicting_starts(mentions: Sequence[DatedMention]) -> list[Fired]:
    starts = sorted({m.when for m in mentions if m.role == "start"})
    if len(starts) < 2:
        return []
    listed = ", ".join(d.isoformat() for d in starts)
    return [Fired("mtx_conflicting_starts", None, None, f"different start dates: {listed}")]


def mtx_response(lines: Sequence[Line]) -> list[Fired]:
    """A response cue on a patient line that is, or is next to, a patient methotrexate line."""
    fired: list[Fired] = []
    for i, line in enumerate(lines):
        if not line.is_patient_mtx:
            continue
        for j in (i - 1, i, i + 1):
            if not 0 <= j < len(lines):
                continue
            other = lines[j]
            if other.document_id != line.document_id or not other.is_patient:
                continue
            if match := other.search("mtx_response"):
                fired.append(_fire("mtx_response", other, match.group(0)))
    return fired


def step_therapy_p(
    *,
    never: bool,
    mentions: Sequence[DatedMention],
    ongoing: bool,
    response: bool,
    as_of: date,
    min_days: int,
) -> tuple[float, dict[str, Any]]:
    """0.0 if never taken or too short; 1.0 if long enough with a response cue; else 0.5.

    With several dates the conservative pair is used: the latest start and the earliest stop.
    With no stop date, an ongoing course ends at as_of.
    """
    starts = [m.when for m in mentions if m.role == "start"]
    stops = [m.when for m in mentions if m.role == "stop"]
    start = max(starts) if starts else None
    end = min(stops) if stops else (as_of if ongoing else None)
    days = (end - start).days if start is not None and end is not None else None
    if never:
        p = NO
    elif days is None:
        p = ABSTAIN
    elif days < min_days:
        p = NO
    elif response:
        p = YES
    else:
        p = ABSTAIN
    duration = {
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "days": days,
        "min_days": min_days,
    }
    return p, duration


def contradiction_p(
    never: Sequence[Fired], mentions: Sequence[DatedMention], conflicting: Sequence[Fired]
) -> float:
    """1.0 only for explicit conflicts: never-taken vs. a dated course elsewhere, or two starts."""
    never_docs = {f.document_id for f in never}
    dated_docs = {m.fired.document_id for m in mentions}
    if (never and dated_docs - never_docs) or conflicting:
        return YES
    return NO


@dataclass(frozen=True)
class RulesResult:
    diagnosis: float
    step_therapy: float
    documentation: float
    contradiction: float
    missing: MissingEvidence
    missing_p: float
    fired: tuple[Fired, ...]
    duration: dict[str, Any]


def evaluate_rules(case: CaseInput, *, min_days: int) -> RulesResult:
    lines = split_lines(case)
    member = member_missing(case, lines)
    established = dx_established(lines)
    negated = dx_negated(lines, established)
    never = mtx_never(lines)
    mentions = mtx_dates(lines)
    ongoing = mtx_ongoing(lines)
    unavailable = records_unavailable(lines)
    conflicting = mtx_conflicting_starts(mentions)
    response = mtx_response(lines)

    diagnosis = diagnosis_p(established, negated)
    step, duration = step_therapy_p(
        never=bool(never),
        mentions=mentions,
        ongoing=bool(ongoing),
        response=bool(response),
        as_of=case.as_of_date,
        min_days=min_days,
    )
    contradiction = contradiction_p(never, mentions, conflicting)

    mtx_mentioned = any(line.is_patient_mtx for line in lines)
    gap: MissingEvidence | None = None
    if diagnosis == NO:
        gap = MissingEvidence.DIAGNOSIS
    elif unavailable or (not mtx_mentioned and not never):
        gap = MissingEvidence.TREATMENT_HISTORY
    elif member:
        gap = MissingEvidence.INSURANCE_INFORMATION
    if gap is not None:
        missing, missing_p, documentation = gap, YES, NO
    elif diagnosis == YES and (step != ABSTAIN or never):
        missing, missing_p, documentation = MissingEvidence.NONE, YES, YES
    else:
        missing, missing_p, documentation = MissingEvidence.NONE, ABSTAIN, ABSTAIN

    fired = (
        *member,
        *established,
        *negated,
        *never,
        *(m.fired for m in mentions),
        *ongoing,
        *unavailable,
        *conflicting,
        *response,
    )
    return RulesResult(
        diagnosis=diagnosis,
        step_therapy=step,
        documentation=documentation,
        contradiction=contradiction,
        missing=missing,
        missing_p=missing_p,
        fired=fired,
        duration=duration,
    )


class RulesBaselineProvider:
    """Deterministic pattern-matching baseline. Needs no key and makes no network calls."""

    name = PROVIDER_NAME

    def __init__(
        self, *, policy_loader: Callable[[str], AuthorizationPolicy] = load_policy
    ) -> None:
        self._policy_loader = policy_loader

    async def decide(self, case: CaseInput) -> DecisionBundle:
        started = time.perf_counter()
        policy = self._policy_loader(case.policy_id)
        result = evaluate_rules(case, min_days=policy.min_weeks * 7)
        decisions = [
            Decision.yes_no(DecisionId.DIAGNOSIS_SUPPORT, result.diagnosis, PROVIDER_NAME),
            Decision.yes_no(DecisionId.STEP_THERAPY, result.step_therapy, PROVIDER_NAME),
            Decision.yes_no(DecisionId.DOCUMENTATION_COMPLETE, result.documentation, PROVIDER_NAME),
            Decision.yes_no(DecisionId.MATERIAL_CONTRADICTION, result.contradiction, PROVIDER_NAME),
            Decision.choice(
                DecisionId.MISSING_EVIDENCE,
                result.missing.value,
                {result.missing.value: result.missing_p},
                PROVIDER_NAME,
                result.missing_p,
            ),
        ]
        return DecisionBundle(
            case_id=case.id,
            decisions=decisions,
            derivations={
                "rules": [f.to_dict() for f in result.fired],
                "duration": result.duration,
            },
            provider=PROVIDER_NAME,
            provider_version=RULES_VERSION,
            question_set_version=RULES_VERSION,
            question_set_hash=rules_hash(),
            latency_ms=round((time.perf_counter() - started) * 1000),
            input_tokens=0,
            estimated_cost_usd=Decimal("0"),
        )
