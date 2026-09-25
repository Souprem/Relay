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


def renderings(d, precision, n=200):
    return {format_date(d, precision, Random(seed)) for seed in range(n)}


def test_day_precision_is_iso_or_long_form():
    assert renderings(FEB_4, "day") == {"2026-02-04", "February 4, 2026"}


def test_month_precision_variants_depend_on_day_of_month():
    # "early" only for days 1-10, "late" only for days 21-31.
    assert renderings(FEB_4, "month") == {
        "February 2026",
        "early February 2026",
        "around February 2026",
    }
    assert renderings(date(2026, 2, 15), "month") == {"February 2026", "around February 2026"}
    assert renderings(date(2026, 2, 25), "month") == {
        "February 2026",
        "late February 2026",
        "around February 2026",
    }


def test_month_precision_never_puts_a_day_number_next_to_the_month():
    for day in range(1, 29):
        for text in renderings(date(2026, 2, day), "month", n=30):
            assert MONTH_THEN_DAY.search(text) is None, text


def test_no_year_precision_has_no_four_digit_year():
    assert renderings(FEB_4, "no_year") == {"February", "early February"}
    for text in renderings(date(2026, 7, 28), "no_year"):
        assert FOUR_DIGITS.search(text) is None, text


def test_unknown_precision_is_rejected():
    with pytest.raises(ValueError, match="precision"):
        format_date(FEB_4, "week", Random(0))  # type: ignore[arg-type]


def test_date_phrase_prepositions():
    for seed in range(50):
        assert date_phrase(FEB_4, "day", Random(seed)).startswith("on ")
        month = date_phrase(FEB_4, "month", Random(seed))
        assert month.startswith("in ") or month.startswith("around "), month
        assert date_phrase(FEB_4, "no_year", Random(seed)).startswith("in ")
        assert date_phrase(FEB_4, "month", Random(seed), since=True).startswith("since ")


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
