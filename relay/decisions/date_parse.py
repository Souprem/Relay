"""Find day-precision dates in free text: ISO `YYYY-MM-DD` and long form `Month D, YYYY`.

Month-only ("March 2026", "late March 2026") and yearless ("March 4") mentions are deliberately
not dates here, and impossible calendar dates (2026-02-30) are rejected, so callers that need an
exact day can abstain instead of guessing.
"""

import calendar
import re
from datetime import date

MONTH_NAMES: tuple[str, ...] = tuple(calendar.month_name[1:])
ISO_DATE = r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)"
LONG_DATE = r"\b(" + "|".join(MONTH_NAMES) + r")\s+(\d{1,2}),\s*(\d{4})(?!\d)"
_ISO_RE = re.compile(ISO_DATE)
_LONG_RE = re.compile(LONG_DATE, re.IGNORECASE)

Span = tuple[int, int]


def _valid(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def find_day_dates(text: str) -> list[tuple[date, Span]]:
    """Every valid day-precision date in `text` with its (start, end) span, in text order."""
    found: list[tuple[date, Span]] = []
    for match in _ISO_RE.finditer(text):
        parsed = _valid(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if parsed is not None:
            found.append((parsed, match.span()))
    for match in _LONG_RE.finditer(text):
        month = MONTH_NAMES.index(match.group(1).capitalize()) + 1
        parsed = _valid(int(match.group(3)), month, int(match.group(2)))
        if parsed is not None:
            found.append((parsed, match.span()))
    return sorted(found, key=lambda item: item[1])
