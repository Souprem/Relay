import re
from datetime import date
from random import Random

import pytest

from relay.generation.dates import (
    MONTH_NAMES,
    conservative_end,
    conservative_start,
    date_phrase,
    format_date,
)
from tests.factories import make_facts

FEB_4 = date(2026, 2, 4)
MONTH_THEN_DAY = re.compile(r"\b(" + "|".join(MONTH_NAMES) + r")\s+\d{1,2}(?!\d)")
FOUR_DIGITS = re.compile(r"\b\d{4}\b")


def renderings(d, precision, bound="start", n=200):
    return {format_date(d, precision, Random(seed), bound=bound) for seed in range(n)}


def test_day_precision_is_iso_or_long_form():
    assert renderings(FEB_4, "day") == {"2026-02-04", "February 4, 2026"}
    assert renderings(FEB_4, "day", "end") == {"2026-02-04", "February 4, 2026"}


def test_month_start_may_only_be_late_and_month_end_only_early():
    # A start's latest bound is the month end, so only "late" (days 21-31) is consistent with it;
    # an end's earliest bound is the month start, so only "early" (days 1-10). Never "around".
    assert renderings(FEB_4, "month", "start") == {"February 2026"}
    assert renderings(FEB_4, "month", "end") == {"February 2026", "early February 2026"}
    assert renderings(date(2026, 2, 15), "month", "start") == {"February 2026"}
    assert renderings(date(2026, 2, 15), "month", "end") == {"February 2026"}
    assert renderings(date(2026, 2, 25), "month", "start") == {
        "February 2026",
        "late February 2026",
    }
    assert renderings(date(2026, 2, 25), "month", "end") == {"February 2026"}


def test_no_qualifier_contradicts_its_bound_on_any_day():
    for day in range(1, 29):
        for precision in ("month", "no_year"):
            d = date(2026, 2, day)
            starts = renderings(d, precision, "start", n=30)
            ends = renderings(d, precision, "end", n=30)
            assert not any("early" in t or "around" in t for t in starts), starts
            assert not any("late" in t or "around" in t for t in ends), ends


def test_month_precision_never_puts_a_day_number_next_to_the_month():
    for day in range(1, 29):
        for bound in ("start", "end"):
            for text in renderings(date(2026, 2, day), "month", bound, n=30):
                assert MONTH_THEN_DAY.search(text) is None, text


def test_no_year_precision_has_no_four_digit_year():
    assert renderings(FEB_4, "no_year", "end") == {"February", "early February"}
    for text in renderings(date(2026, 7, 28), "no_year"):
        assert FOUR_DIGITS.search(text) is None, text


def test_unknown_precision_and_bound_are_rejected():
    with pytest.raises(ValueError, match="precision"):
        format_date(FEB_4, "week", Random(0), bound="start")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="bound"):
        format_date(FEB_4, "month", Random(0), bound="middle")  # type: ignore[arg-type]


def test_date_phrase_prepositions():
    for seed in range(50):
        assert date_phrase(FEB_4, "day", Random(seed), bound="start").startswith("on ")
        assert date_phrase(FEB_4, "month", Random(seed), bound="end").startswith("in ")
        assert date_phrase(FEB_4, "no_year", Random(seed), bound="end").startswith("in ")
        since = date_phrase(FEB_4, "month", Random(seed), bound="start", since=True)
        assert since.startswith("since ")


@pytest.mark.parametrize(
    ("d", "precision", "start", "end"),
    [
        (FEB_4, "day", FEB_4, FEB_4),
        (FEB_4, "month", date(2026, 2, 28), date(2026, 2, 1)),
        (date(2028, 2, 10), "month", date(2028, 2, 29), date(2028, 2, 1)),  # leap year
        (date(2026, 4, 30), "month", date(2026, 4, 30), date(2026, 4, 1)),
        (FEB_4, "no_year", None, None),
    ],
)
def test_conservative_bounds(d, precision, start, end):
    assert conservative_start(d, precision) == start
    assert conservative_end(d, precision) == end


def test_make_facts_default_is_a_documented_mtx_course():
    facts = make_facts()
    assert (facts.mtx_status, facts.start_precision, facts.end_precision) == ("taken", "day", "day")
    assert make_facts(age=17).age == 17
