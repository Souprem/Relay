"""Compose P(treatment duration >= N days) from Jev's date-part answers.

Jev reads date parts; code does all date arithmetic (Jev is unreliable at date comparison).
Month-only dates become ranges and duration is measured conservatively: latest possible start to
earliest possible end. Any unknown part ("none", invalid date, end not stated) contributes no
probability mass toward "satisfied". Date parts are treated as independent -- an approximation
that Phase 2 calibration must test.

A policy with a recency rule (immunara-v0.2's max_days_since_therapy) also needs the qualifying
course to end, conservatively at its earliest possible end, no more than that many days before
as_of (an ongoing course ends at as_of). The rule is applied per (start, end) candidate pair.

q-v0.3 reads an interrupted course as two segments (first start -> pause, restart -> final end);
p_consecutive_at_least composes P(some single segment is long enough) from them.
"""

import calendar
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

MONTHS: tuple[str, ...] = tuple(calendar.month_name[1:])
NONE = "none"
PRUNE_BELOW = 0.01


def prune(dist: Mapping[str, float], floor: float = PRUNE_BELOW) -> dict[str, float]:
    kept = {k: v for k, v in dist.items() if v >= floor}
    total = sum(kept.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in kept.items()}


@dataclass(frozen=True)
class DateParts:
    month: Mapping[str, float]
    day: Mapping[str, float]
    year: Mapping[str, float]


@dataclass(frozen=True)
class DateCandidate:
    earliest: date
    latest: date
    probability: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "earliest": self.earliest.isoformat(),
            "latest": self.latest.isoformat(),
            "probability": round(self.probability, 6),
        }


def date_candidates(parts: DateParts) -> list[DateCandidate]:
    """Known-date candidates only; mass on unknown combinations is dropped."""
    out: list[DateCandidate] = []
    for month, p_month in prune(parts.month).items():
        if month not in MONTHS:
            continue
        month_index = MONTHS.index(month) + 1
        for year, p_year in prune(parts.year).items():
            if not year.isdigit():
                continue
            year_value = int(year)
            for day, p_day in prune(parts.day).items():
                probability = p_month * p_year * p_day
                if day == NONE:
                    last_day = calendar.monthrange(year_value, month_index)[1]
                    out.append(
                        DateCandidate(
                            date(year_value, month_index, 1),
                            date(year_value, month_index, last_day),
                            probability,
                        )
                    )
                    continue
                if not day.isdigit():
                    continue
                try:
                    exact = date(year_value, month_index, int(day))
                except ValueError:
                    continue
                out.append(DateCandidate(exact, exact, probability))
    return out


@dataclass(frozen=True)
class DurationResult:
    p_duration: float
    min_days: int
    start_candidates: tuple[DateCandidate, ...]
    end_candidates: tuple[DateCandidate, ...]
    max_days_since: int | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "min_days": self.min_days,
            "p_duration": round(self.p_duration, 6),
            "start_candidates": [c.to_dict() for c in self.start_candidates],
            "end_candidates": [c.to_dict() for c in self.end_candidates],
        }
        if self.max_days_since is not None:  # absent for a policy without a recency rule
            out["max_days_since_therapy"] = self.max_days_since
        return out


def end_candidates(
    end_status: Mapping[str, float], end: DateParts, as_of: date
) -> list[DateCandidate]:
    """Final-end candidates: stated end dates weighted by P(ended), plus as_of for P(ongoing)."""
    status = prune(end_status)
    p_ended = status.get("ended", 0.0)
    p_ongoing = status.get("ongoing", 0.0)
    ends: list[DateCandidate] = []
    if p_ended:
        ends = [
            DateCandidate(c.earliest, c.latest, c.probability * p_ended)
            for c in date_candidates(end)
        ]
    if p_ongoing:
        ends.append(DateCandidate(as_of, as_of, p_ongoing))
    return ends


def qualifies(
    start: DateCandidate,
    end: DateCandidate,
    *,
    as_of: date,
    min_days: int,
    max_days_since: int | None,
) -> bool:
    """Latest start to earliest end is at least min_days and, under a recency rule, the earliest
    end is no more than max_days_since days before as_of."""
    if (end.earliest - start.latest).days < min_days:
        return False
    return max_days_since is None or (as_of - end.earliest).days <= max_days_since


def p_pairs(
    starts: Sequence[DateCandidate],
    ends: Sequence[DateCandidate],
    *,
    as_of: date,
    min_days: int,
    max_days_since: int | None,
) -> float:
    """P(a start/end pair qualifies), capped at 1.0."""
    p = sum(
        s.probability * e.probability
        for s in starts
        for e in ends
        if qualifies(s, e, as_of=as_of, min_days=min_days, max_days_since=max_days_since)
    )
    return min(p, 1.0)


def p_duration_at_least(
    *,
    start: DateParts,
    end_status: Mapping[str, float],
    end: DateParts,
    as_of: date,
    min_days: int,
    max_days_since: int | None = None,
) -> DurationResult:
    starts = date_candidates(start)
    ends = end_candidates(end_status, end, as_of)
    return DurationResult(
        p_duration=p_pairs(
            starts, ends, as_of=as_of, min_days=min_days, max_days_since=max_days_since
        ),
        min_days=min_days,
        start_candidates=tuple(starts),
        end_candidates=tuple(ends),
        max_days_since=max_days_since,
    )


@dataclass(frozen=True)
class SegmentResult:
    """P(consecutive segment >= min_days) for q-v0.3, with every term of the formula."""

    p_duration: float
    min_days: int
    max_days_since: int | None
    p_interrupted: float
    p_continuous: float
    p_first_segment: float
    p_second_segment: float
    p_either_segment: float
    start_candidates: tuple[DateCandidate, ...]
    pause_candidates: tuple[DateCandidate, ...]
    restart_candidates: tuple[DateCandidate, ...]
    end_candidates: tuple[DateCandidate, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_days": self.min_days,
            "max_days_since_therapy": self.max_days_since,
            "p_duration": round(self.p_duration, 6),
            "p_interrupted": round(self.p_interrupted, 6),
            "p_continuous": round(self.p_continuous, 6),
            "p_first_segment": round(self.p_first_segment, 6),
            "p_second_segment": round(self.p_second_segment, 6),
            "p_either_segment": round(self.p_either_segment, 6),
            "start_candidates": [c.to_dict() for c in self.start_candidates],
            "pause_candidates": [c.to_dict() for c in self.pause_candidates],
            "restart_candidates": [c.to_dict() for c in self.restart_candidates],
            "end_candidates": [c.to_dict() for c in self.end_candidates],
        }


def p_consecutive_at_least(
    *,
    start: DateParts,
    pause: DateParts,
    restart: DateParts,
    end_status: Mapping[str, float],
    end: DateParts,
    p_interrupted: float,
    as_of: date,
    min_days: int,
    max_days_since: int | None = None,
) -> SegmentResult:
    """p = (1 - p_int) * P(first start -> final end qualifies)
    + p_int * P(first start -> pause qualifies OR restart -> final end qualifies).

    The two segment events are combined by inclusion-exclusion, P(A) + P(B) - P(A) * P(B),
    under the same independence approximation as the date parts themselves: A reads only the
    start and pause answers and B only the restart and end answers. An unknown pause or restart
    contributes no candidate, so an interruption with unreadable dates adds nothing.
    """
    starts = date_candidates(start)
    pauses = date_candidates(pause)
    restarts = date_candidates(restart)
    ends = end_candidates(end_status, end, as_of)
    p_continuous = p_pairs(
        starts, ends, as_of=as_of, min_days=min_days, max_days_since=max_days_since
    )
    p_first = p_pairs(starts, pauses, as_of=as_of, min_days=min_days, max_days_since=max_days_since)
    p_second = p_pairs(
        restarts, ends, as_of=as_of, min_days=min_days, max_days_since=max_days_since
    )
    p_either = p_first + p_second - p_first * p_second
    p = (1.0 - p_interrupted) * p_continuous + p_interrupted * p_either
    return SegmentResult(
        p_duration=min(p, 1.0),
        min_days=min_days,
        max_days_since=max_days_since,
        p_interrupted=p_interrupted,
        p_continuous=p_continuous,
        p_first_segment=p_first,
        p_second_segment=p_second,
        p_either_segment=p_either,
        start_candidates=tuple(starts),
        pause_candidates=tuple(pauses),
        restart_candidates=tuple(restarts),
        end_candidates=tuple(ends),
    )
