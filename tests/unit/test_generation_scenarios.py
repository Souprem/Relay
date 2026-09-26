from random import Random

import pytest

from relay.generation.facts import DIFFICULTIES
from relay.generation.scenarios import AS_OF_MAX, AS_OF_MIN, PROFILES, sample_facts

SEEDS = range(400)
WIDE_SEEDS = range(1000)


def sample(seed, difficulty, **overrides):
    return sample_facts(Random(seed), case_id=f"S-{seed}", difficulty=difficulty, **overrides)


def all_facts(difficulty, **overrides):
    return [sample(seed, difficulty, **overrides) for seed in SEEDS]


def actual_days(f):
    return ((f.mtx_end or f.as_of_date) - f.mtx_start).days


def profile_courses(facts):
    """Courses drawn from the profile's duration sampler (dates_conflict redraws its own)."""
    return [f for f in facts if f.mtx_status == "taken" and f.contradiction != "dates_conflict"]


def test_profiles_cover_every_difficulty():
    assert tuple(PROFILES) == DIFFICULTIES == ("easy", "medium", "hard", "adversarial")


def test_same_random_state_gives_equal_facts():
    assert sample(7, "hard") == sample(7, "hard")
    assert sample(7, "hard") != sample(8, "hard")


def test_unknown_difficulty_is_rejected_with_allowed_values():
    with pytest.raises(ValueError, match="adversarial"):
        sample(0, "extreme")


def test_probability_overrides_are_validated():
    with pytest.raises(ValueError, match="note_noise"):
        sample(0, "easy", note_noise=1.5)
    with pytest.raises(ValueError, match="missing_data_probability"):
        sample(0, "easy", missing_data_probability=-0.1)


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_invariants_hold_for_every_difficulty(difficulty):
    for f in all_facts(difficulty):
        assert AS_OF_MIN <= f.as_of_date <= AS_OF_MAX
        assert f.note_date <= f.as_of_date
        taken = f.mtx_status == "taken"
        assert (f.mtx_start is not None) is taken
        assert (f.start_precision is not None) is taken
        assert (f.end_precision is None) is (f.mtx_end is None)
        if taken and f.mtx_end is not None:
            assert f.mtx_start < f.mtx_end <= f.note_date
        if not taken:
            assert f.mtx_outcome == "not_stated" and not f.split_across_documents
        if f.contradiction is not None:
            assert taken and f.medication_history and not f.split_across_documents
            assert f.start_precision == "day" and f.end_precision in ("day", None)
        assert (f.history_start is not None) is (f.contradiction == "dates_conflict")
        if f.history_start is not None:
            end = f.mtx_end or f.as_of_date
            assert 42 <= (end - f.mtx_start).days <= 70
            assert 42 <= (f.mtx_start - f.history_start).days <= 70
            assert f.diagnosis_year <= f.history_start.year
        if taken and f.mtx_end is None:
            assert f.note_date == f.as_of_date
        if f.split_across_documents:
            assert f.medication_history
        if f.mtx_status == "undocumented":
            assert not f.medication_history
        assert (f.stale_note_date is not None) is f.stale_note
        if f.stale_note and f.mtx_start is not None:
            assert f.stale_note_date < min(f.mtx_start, f.history_start or f.mtx_start)
        assert f.noise == PROFILES[difficulty].note_noise


def test_easy_cases_are_clean():
    for f in all_facts("easy"):
        assert f.start_precision in ("day", None) and f.end_precision in ("day", None)
        assert not f.split_across_documents and not f.medication_history
        assert f.contradiction is None and f.mtx_status in ("taken", "undocumented")
        assert not (f.injection or f.relative_distractor or f.stale_note or f.other_dmards)
        assert f.age >= 25


@pytest.mark.parametrize("difficulty", ["easy", "medium"])
def test_easy_and_medium_durations_are_clearly_short_or_clearly_long(difficulty):
    days = [actual_days(f) for f in profile_courses(all_facts(difficulty))]
    assert days and all(28 <= d <= 56 or 112 <= d <= 210 for d in days)


def test_hard_durations_straddle_twelve_weeks_and_ages_include_minors():
    facts = all_facts("hard")
    days = [actual_days(f) for f in profile_courses(facts)]
    assert days and all(56 <= d <= 105 for d in days)  # 8 * 7 = 56, 15 * 7 = 105
    assert min(days) < 84 <= max(days)
    ages = [f.age for f in facts]
    assert all(16 <= a <= 19 or 25 <= a <= 78 for a in ages)
    assert any(a < 18 for a in ages)
    assert any(f.contradiction for f in facts)


def test_adversarial_cases_have_at_least_one_adversarial_feature():
    for f in all_facts("adversarial"):
        other_dmard_instead = f.mtx_status == "never" and bool(f.other_dmards)
        assert f.relative_distractor or f.injection or f.stale_note or other_dmard_instead
        if f.mtx_status == "relative_only":
            assert f.relative_distractor


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_no_profile_produces_yearless_dates(difficulty):
    # gen-v0.2: yearless dates are out of scope (the year is usually inferable and the rule is not
    # stated to readers). The labeller still handles hand-built no_year facts.
    assert "no_year" not in PROFILES[difficulty].precisions
    for seed in WIDE_SEEDS:
        f = sample(seed, difficulty, missing_data_probability=1.0)
        assert "no_year" not in (f.start_precision, f.end_precision), seed
    for seed in WIDE_SEEDS:
        f = sample(seed, difficulty)
        assert "no_year" not in (f.start_precision, f.end_precision), seed


def test_ongoing_courses_are_noted_on_the_as_of_date():
    ongoing = [
        f
        for d in DIFFICULTIES
        for f in all_facts(d)
        if f.mtx_status == "taken" and f.mtx_end is None
    ]
    assert ongoing and all(f.note_date == f.as_of_date for f in ongoing)
    ended = [f for f in all_facts("medium") if f.mtx_end is not None]
    assert any(f.note_date < f.as_of_date for f in ended)


def test_zero_probabilities_remove_gaps_and_contradictions():
    for difficulty in DIFFICULTIES:
        for f in all_facts(difficulty, missing_data_probability=0.0, contradiction_probability=0.0):
            assert f.diagnosis_status == "established" and f.member_id is not None
            assert f.mtx_status != "undocumented" and f.contradiction is None


def test_missing_data_probability_one_always_leaves_a_gap():
    for f in all_facts("hard", missing_data_probability=1.0):
        gap = (
            f.diagnosis_status != "established"
            or f.member_id is None
            or f.mtx_status == "undocumented"
        )
        assert gap, f


def test_note_noise_override_is_recorded():
    assert sample(0, "easy", note_noise=0.9).noise == 0.9
