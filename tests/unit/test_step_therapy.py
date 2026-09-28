from datetime import date

import pytest

from relay.decisions.step_therapy import (
    DateParts,
    date_candidates,
    p_consecutive_at_least,
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


def test_exactly_eighty_four_days_passes():
    result = duration(parts("January", "1", "2026"), parts("March", "26", "2026"))
    assert result.p_duration == pytest.approx(1.0)  # exactly 84 days


def test_eighty_three_days_fails():
    result = duration(parts("January", "1", "2026"), parts("March", "25", "2026"))
    assert result.p_duration == pytest.approx(0.0)  # 83 days


def test_to_dict_is_json_friendly():
    result = duration(parts("January", "12", "2026"), parts("June", "1", "2026"))
    data = result.to_dict()
    assert data["min_days"] == MIN_DAYS
    assert data["start_candidates"][0] == {
        "earliest": "2026-01-12",
        "latest": "2026-01-12",
        "probability": 1.0,
    }


# ---- Phase 3D: recency (immunara-v0.2) and interrupted courses (q-v0.3) ----

NOT_STATED = DateParts(month={"none": 1.0}, day={"none": 1.0}, year={"none": 1.0})


def consecutive(start, pause, restart, end, *, p_int, status=None, as_of=AS_OF, recency=None):
    return p_consecutive_at_least(
        start=start,
        pause=pause,
        restart=restart,
        end_status=status or certain("ended"),
        end=end,
        p_interrupted=p_int,
        as_of=as_of,
        min_days=MIN_DAYS,
        max_days_since=recency,
    )


def test_recency_none_leaves_the_duration_and_its_derivation_unchanged():
    plain = duration(parts("January", "12", "2026"), parts("June", "1", "2026"))
    assert plain.p_duration == 1.0
    assert plain.max_days_since is None
    assert "max_days_since_therapy" not in plain.to_dict()


def test_recency_drops_a_course_that_ended_more_than_365_days_before_as_of():
    start, end = parts("January", "12", "2025"), parts("June", "1", "2025")  # 140 days
    as_of = date(2026, 6, 2)  # 366 days after the end
    old = p_duration_at_least(
        start=start,
        end_status=certain("ended"),
        end=end,
        as_of=as_of,
        min_days=MIN_DAYS,
        max_days_since=365,
    )
    assert old.p_duration == 0.0
    assert old.to_dict()["max_days_since_therapy"] == 365
    on_the_day = p_duration_at_least(
        start=start,
        end_status=certain("ended"),
        end=end,
        as_of=date(2026, 6, 1),  # exactly 365 days after the end
        min_days=MIN_DAYS,
        max_days_since=365,
    )
    assert on_the_day.p_duration == 1.0


def test_recency_uses_the_earliest_possible_end_of_a_month_only_date():
    # Ended "June 2025": the earliest end is 2025-06-01, 366 days before 2026-06-02.
    result = p_duration_at_least(
        start=parts("January", "12", "2025"),
        end_status=certain("ended"),
        end=parts("June", "none", "2025"),
        as_of=date(2026, 6, 2),
        min_days=MIN_DAYS,
        max_days_since=365,
    )
    assert result.p_duration == 0.0


def test_an_ongoing_course_is_always_recent():
    result = p_duration_at_least(
        start=parts("January", "12", "2024"),
        end_status=certain("ongoing"),
        end=UNKNOWN,
        as_of=AS_OF,
        min_days=MIN_DAYS,
        max_days_since=365,
    )
    assert result.p_duration == 1.0


def test_gold_tmp_17_pattern_neither_segment_reaches_twelve_weeks():
    # 2026-01-05 -> held 2026-02-23 (49 d), restarted 2026-03-23 -> 2026-05-18 (56 d).
    start, end = parts("January", "5", "2026"), parts("May", "18", "2026")
    pause, restart = parts("February", "23", "2026"), parts("March", "23", "2026")
    result = consecutive(start, pause, restart, end, p_int=1.0, as_of=date(2026, 6, 10))
    assert (result.p_continuous, result.p_first_segment, result.p_second_segment) == (
        1.0,
        0.0,
        0.0,
    )
    assert result.p_duration == 0.0
    # Read as one continuous course (the q-v0.2 reading) it would pass: 133 days.
    unread = consecutive(start, pause, restart, end, p_int=0.0, as_of=date(2026, 6, 10))
    assert unread.p_duration == 1.0


def test_gold_tmp_18_pattern_the_later_segment_qualifies():
    # 2025-10-06 -> stopped 2025-11-03 (28 d), restarted 2026-01-12 -> 2026-05-04 (112 d).
    result = consecutive(
        parts("October", "6", "2025"),
        parts("November", "3", "2025"),
        parts("January", "12", "2026"),
        parts("May", "4", "2026"),
        p_int=1.0,
        as_of=date(2026, 6, 15),
    )
    assert (result.p_first_segment, result.p_second_segment) == (0.0, 1.0)
    assert result.p_duration == 1.0


def test_the_earlier_segment_can_qualify_and_an_ongoing_restart_ends_at_as_of():
    result = consecutive(
        parts("January", "5", "2026"),
        parts("May", "4", "2026"),  # 119 days
        parts("August", "31", "2026"),
        UNKNOWN,
        p_int=1.0,
        status=certain("ongoing"),  # restart -> as_of 2026-09-15 = 15 days
    )
    assert (result.p_first_segment, result.p_second_segment) == (1.0, 0.0)
    assert result.p_duration == 1.0


def test_segments_combine_by_inclusion_exclusion_and_mix_by_p_interrupted():
    # Start and pause each certain; restart split 50/50 between a qualifying and a short one.
    result = consecutive(
        parts("January", "5", "2026"),
        DateParts(month={"May": 0.6, "February": 0.4}, day=certain("4"), year=certain("2026")),
        DateParts(month={"March": 0.5, "July": 0.5}, day=certain("1"), year=certain("2026")),
        parts("August", "1", "2026"),
        p_int=0.8,
    )
    # A: Jan 5 -> May 4 (119 d) qualifies, -> Feb 4 (30 d) does not: P(A) = 0.6.
    # B: Mar 1 -> Aug 1 (153 d) qualifies, Jul 1 -> Aug 1 (31 d) does not: P(B) = 0.5.
    assert result.p_first_segment == pytest.approx(0.6)
    assert result.p_second_segment == pytest.approx(0.5)
    assert result.p_either_segment == pytest.approx(0.6 + 0.5 - 0.3)
    assert result.p_continuous == 1.0  # Jan 5 -> Aug 1 = 208 days
    assert result.p_duration == pytest.approx(0.2 * 1.0 + 0.8 * 0.8)


def test_an_interruption_with_unknown_pause_and_restart_contributes_nothing():
    result = consecutive(
        parts("January", "5", "2026"),
        NOT_STATED,
        NOT_STATED,
        parts("August", "1", "2026"),
        p_int=0.3,
    )
    assert (result.p_first_segment, result.p_second_segment) == (0.0, 0.0)
    assert result.p_duration == pytest.approx(0.7)
    assert result.pause_candidates == () and result.restart_candidates == ()


def test_recency_applies_to_each_segment_end():
    # The earlier segment qualifies on length but ended 400 days before as_of; the later one
    # is short. Under a 365-day rule nothing qualifies.
    as_of = date(2026, 9, 15)
    start, pause = parts("January", "5", "2025"), parts("August", "11", "2025")
    restart, end = parts("August", "1", "2026"), parts("September", "1", "2026")
    assert (as_of - date(2025, 8, 11)).days == 400
    loose = consecutive(start, pause, restart, end, p_int=1.0, as_of=as_of)
    strict = consecutive(start, pause, restart, end, p_int=1.0, as_of=as_of, recency=365)
    assert (loose.p_duration, strict.p_duration) == (1.0, 0.0)


def test_segment_derivation_records_every_term():
    result = consecutive(
        parts("January", "5", "2026"),
        parts("February", "23", "2026"),
        parts("March", "23", "2026"),
        parts("May", "18", "2026"),
        p_int=0.9,
        recency=365,
    )
    record = result.to_dict()
    assert set(record) == {
        "min_days",
        "max_days_since_therapy",
        "p_duration",
        "p_interrupted",
        "p_continuous",
        "p_first_segment",
        "p_second_segment",
        "p_either_segment",
        "start_candidates",
        "pause_candidates",
        "restart_candidates",
        "end_candidates",
    }
    assert record["max_days_since_therapy"] == 365
    assert record["p_interrupted"] == 0.9
    assert record["pause_candidates"] == [
        {"earliest": "2026-02-23", "latest": "2026-02-23", "probability": 1.0}
    ]
