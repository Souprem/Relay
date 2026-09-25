from datetime import date

import pytest

from relay.decisions.step_therapy import (
    DateParts,
    date_candidates,
    p_duration_at_least,
    prune,
)

AS_OF = date(2026, 9, 15)
MIN_DAYS = 84  # 12 weeks
UNKNOWN = DateParts(month={"none": 1.0}, day={"none": 1.0}, year={"none": 1.0})


def certain(value):
    return {value: 1.0}


def parts(month, day, year):
    return DateParts(month=certain(month), day=certain(day), year=certain(year))


def duration(start, end=UNKNOWN, status=None):
    return p_duration_at_least(
        start=start,
        end_status=status or certain("ended"),
        end=end,
        as_of=AS_OF,
        min_days=MIN_DAYS,
    )


def test_prune_drops_small_mass_and_renormalizes():
    assert prune({"a": 0.995, "b": 0.005}) == {"a": pytest.approx(1.0)}
    assert prune({"a": 0.6, "b": 0.3, "c": 0.1}) == {
        "a": pytest.approx(0.6),
        "b": pytest.approx(0.3),
        "c": pytest.approx(0.1),
    }


def test_prune_keeps_values_exactly_at_floor():
    assert set(prune({"a": 0.99, "none": 0.01})) == {"a", "none"}


def test_prune_everything_below_floor_is_empty():
    assert prune({"a": 0.005}) == {}


def test_exact_date_candidate():
    [c] = date_candidates(parts("January", "12", "2026"))
    assert (c.earliest, c.latest, c.probability) == (date(2026, 1, 12), date(2026, 1, 12), 1.0)


def test_month_only_candidate_is_whole_month_range():
    [c] = date_candidates(parts("February", "none", "2026"))
    assert (c.earliest, c.latest) == (date(2026, 2, 1), date(2026, 2, 28))


def test_unknown_parts_and_invalid_dates_produce_no_candidates():
    assert date_candidates(parts("none", "5", "2026")) == []
    assert date_candidates(parts("March", "5", "none")) == []
    assert date_candidates(parts("February", "30", "2026")) == []


def test_exact_dates_twenty_weeks_pass():
    result = duration(parts("January", "12", "2026"), parts("June", "1", "2026"))
    assert result.p_duration == pytest.approx(1.0)  # 140 days


def test_month_only_february_to_july_passes_conservatively():
    result = duration(parts("February", "none", "2026"), parts("July", "none", "2026"))
    assert result.p_duration == pytest.approx(1.0)  # Feb 28 -> Jul 1 = 123 days


def test_month_only_february_to_may_fails_conservatively():
    result = duration(parts("February", "none", "2026"), parts("May", "none", "2026"))
    assert result.p_duration == pytest.approx(0.0)  # Feb 28 -> May 1 = 62 days


def test_nine_weeks_fails():
    result = duration(parts("June", "1", "2026"), parts("August", "3", "2026"))
    assert result.p_duration == pytest.approx(0.0)  # 63 days


def test_ongoing_uses_as_of_date():
    result = duration(parts("March", "none", "2026"), status=certain("ongoing"))
    assert result.p_duration == pytest.approx(1.0)  # Mar 31 -> Sep 15 = 168 days
    assert result.end_candidates[0].earliest == AS_OF


def test_recent_ongoing_start_fails():
    result = duration(parts("August", "1", "2026"), status=certain("ongoing"))
    assert result.p_duration == pytest.approx(0.0)  # 45 days


def test_end_not_stated_contributes_no_mass():
    result = duration(parts("January", "12", "2026"), status=certain("not_stated"))
    assert result.p_duration == 0.0
    assert result.end_candidates == ()


def test_unknown_start_contributes_no_mass():
    result = duration(UNKNOWN, parts("June", "1", "2026"))
    assert result.p_duration == 0.0


def test_hand_computed_mixed_probabilities():
    start = DateParts(month={"January": 0.8, "June": 0.2}, day=certain("5"), year=certain("2026"))
    end = parts("May", "10", "2026")
    status = {"ended": 0.9, "not_stated": 0.1}
    # Jan 5 -> May 10 = 125 days (passes, 0.8); Jun 5 -> May 10 is negative (fails).
    result = duration(start, end, status)
    assert result.p_duration == pytest.approx(0.8 * 0.9)


def test_to_dict_is_json_friendly():
    result = duration(parts("January", "12", "2026"), parts("June", "1", "2026"))
    data = result.to_dict()
    assert data["min_days"] == MIN_DAYS
    assert data["start_candidates"][0] == {
        "earliest": "2026-01-12",
        "latest": "2026-01-12",
        "probability": 1.0,
    }
