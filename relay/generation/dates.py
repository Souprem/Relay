"""Render dates at a chosen precision and compute what each rendering conservatively establishes.

Month-only dates are measured from the latest possible start (last day of the month) to the
earliest possible end (first day of the month), matching relay.decisions.step_therapy. A date with
no stated year establishes nothing (the generator no longer samples yearless dates, but the path is
kept and tested).

Qualifiers never contradict those bounds: a start may be "late <Month>" (its latest bound is still
the month end) and an end may be "early <Month>" (its earliest bound is still the month start).
There is no "around".
"""

import calendar
from datetime import date
from random import Random
from typing import Literal

from relay.generation.facts import Precision

MONTH_NAMES: tuple[str, ...] = tuple(calendar.month_name[1:])

Bound = Literal["start", "end"]


def format_date(d: date, precision: Precision, rng: Random, *, bound: Bound) -> str:
    """A bare date string, e.g. '2026-02-04', 'February 4, 2026', 'late February 2026', 'February'.

    `bound` says whether the date is a treatment start or end: only a start may be "late <Month>"
    (days 21-31) and only an end may be "early <Month>" (days 1-10).
    """
    if bound not in ("start", "end"):
        raise ValueError(f"unknown bound {bound!r}")
    month = MONTH_NAMES[d.month - 1]
    if precision == "day":
        return d.isoformat() if rng.random() < 0.5 else f"{month} {d.day}, {d.year}"
    qualifiers = [""]
    if bound == "start" and d.day >= 21:
        qualifiers.append("late ")
    if bound == "end" and d.day <= 10:
        qualifiers.append("early ")
    if precision == "month":
        return f"{rng.choice(qualifiers)}{month} {d.year}"
    if precision == "no_year":
        return f"{rng.choice(qualifiers)}{month}"
    raise ValueError(f"unknown precision {precision!r}")


def date_phrase(
    d: date, precision: Precision, rng: Random, *, bound: Bound, since: bool = False
) -> str:
    """A date with its preposition, ready to follow a verb: 'on 2026-02-04', 'in late March 2026'."""
    bare = format_date(d, precision, rng, bound=bound)
    if since:
        return f"since {bare}"
    if precision == "day":
        return f"on {bare}"
    return f"in {bare}"


def conservative_start(d: date, precision: Precision) -> date | None:
    if precision == "day":
        return d
    if precision == "month":
        return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])
    return None


def conservative_end(d: date, precision: Precision) -> date | None:
    if precision == "day":
        return d
    if precision == "month":
        return date(d.year, d.month, 1)
    return None
