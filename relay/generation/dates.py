"""Render dates at a chosen precision and compute what each rendering conservatively establishes.

Month-only dates are measured from the latest possible start (last day of the month) to the
earliest possible end (first day of the month), matching relay.decisions.step_therapy. A date with
no stated year establishes nothing.
"""

import calendar
from datetime import date
from random import Random

from relay.generation.facts import Precision

MONTH_NAMES: tuple[str, ...] = tuple(calendar.month_name[1:])


def format_date(d: date, precision: Precision, rng: Random) -> str:
    """A bare date string, e.g. '2026-02-04', 'February 4, 2026', 'early February 2026', 'February'."""
    month = MONTH_NAMES[d.month - 1]
    if precision == "day":
        return d.isoformat() if rng.random() < 0.5 else f"{month} {d.day}, {d.year}"
    qualifiers = [""]
    if d.day <= 10:
        qualifiers.append("early ")
    if d.day >= 21:
        qualifiers.append("late ")
    if precision == "month":
        qualifiers.append("around ")
        return f"{rng.choice(qualifiers)}{month} {d.year}"
    if precision == "no_year":
        return f"{rng.choice(qualifiers)}{month}"
    raise ValueError(f"unknown precision {precision!r}")


def date_phrase(d: date, precision: Precision, rng: Random, *, since: bool = False) -> str:
    """A date with its preposition, ready to follow a verb: 'on 2026-02-04', 'in early February 2026'."""
    bare = format_date(d, precision, rng)
    if since:
        return f"since {bare}"
    if precision == "day":
        return f"on {bare}"
    if bare.startswith("around "):
        return bare
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
