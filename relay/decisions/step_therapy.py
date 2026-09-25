"""Compose P(treatment duration >= N days) from Jev's date-part answers.

Jev reads date parts; code does all date arithmetic (Jev is unreliable at date comparison).
Month-only dates become ranges and duration is measured conservatively: latest possible start to
earliest possible end. Any unknown part ("none", invalid date, end not stated) contributes no
probability mass toward "satisfied". Date parts are treated as independent -- an approximation
that Phase 2 calibration must test.
"""

import calendar
from collections.abc import Mapping
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_days": self.min_days,
            "p_duration": round(self.p_duration, 6),
            "start_candidates": [c.to_dict() for c in self.start_candidates],
            "end_candidates": [c.to_dict() for c in self.end_candidates],
        }


def p_duration_at_least(
    *,
    start: DateParts,
    end_status: Mapping[str, float],
    end: DateParts,
    as_of: date,
    min_days: int,
) -> DurationResult:
    starts = date_candidates(start)
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
    p = sum(
        s.probability * e.probability
        for s in starts
        for e in ends
        if (e.earliest - s.latest).days >= min_days
    )
    return DurationResult(
        p_duration=min(p, 1.0),
        min_days=min_days,
        start_candidates=tuple(starts),
        end_candidates=tuple(ends),
    )
