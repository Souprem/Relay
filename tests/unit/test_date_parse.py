from datetime import date

from relay.decisions.date_parse import find_day_dates


def dates(text):
    return [d for d, _ in find_day_dates(text)]


def test_iso_and_long_form_dates_are_found_in_text_order():
    text = "Started 2026-01-12 and stopped June 1, 2026; seen September 15,2026."
    assert dates(text) == [date(2026, 1, 12), date(2026, 6, 1), date(2026, 9, 15)]


def test_spans_point_at_the_date_text():
    text = "start 2026-02-04 - end March 3, 2026"
    [(_, first), (_, second)] = find_day_dates(text)
    assert text[first[0] : first[1]] == "2026-02-04"
    assert text[second[0] : second[1]] == "March 3, 2026"


def test_long_form_is_case_insensitive():
    assert dates("STARTED JANUARY 5, 2026") == [date(2026, 1, 5)]


def test_month_only_and_yearless_mentions_are_not_day_dates():
    assert dates("since March 2026, late February 2026, in early June 2026, on March 4") == []


def test_invalid_calendar_dates_are_rejected():
    assert dates("2026-02-30 and February 30, 2026 and 2026-13-01") == []


def test_digits_glued_to_a_date_do_not_count():
    assert dates("ref 12026-01-120 and 2026-01-1234") == []
