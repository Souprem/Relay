from datetime import date

import pytest

from relay.cases.models import MissingEvidence
from relay.cases.policies import load_policy
from relay.evaluation.labels import expected_action
from relay.generation.labels import (
    MIN_DAYS,
    conservative_days,
    days_since_end,
    label_case,
    segment_days,
)
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1
from tests.factories import make_case, make_facts

# make_facts(): as_of 2026-09-15, MTX 2026-01-12 -> 2026-06-01 at day precision, inadequate
# response, diagnosis established, member id present.
NOT_TAKEN = {"mtx_start": None, "mtx_end": None, "start_precision": None, "end_precision": None}


def action_for(facts, age=40):
    case = make_case(truth=label_case(facts), age=age)
    return expected_action(case, load_policy("immunara-v0.1"), THRESHOLDS_V0_1)


def test_min_days_matches_policy():
    assert MIN_DAYS == load_policy("immunara-v0.1").min_weeks * 7 == 84


def test_fully_documented_course_is_auto_process():
    facts = make_facts()
    assert conservative_days(facts) == 140  # Jan 12 -> Jun 1: 19 + 28 + 31 + 30 + 31 + 1
    truth = label_case(facts)
    assert truth.diagnosis_supported and truth.step_therapy_satisfied
    assert truth.documentation_complete and not truth.contradiction_present
    assert truth.missing_evidence is MissingEvidence.NONE
    assert action_for(facts) is WorkflowAction.AUTO_PROCESS


@pytest.mark.parametrize(
    ("start", "end", "days", "satisfied"),
    [
        (date(2026, 3, 2), date(2026, 5, 25), 84, True),  # Mar 2 -> May 25: 29 + 30 + 25
        (date(2026, 3, 2), date(2026, 5, 24), 83, False),
        (date(2026, 6, 1), date(2026, 8, 3), 63, False),  # Jun 1 -> Aug 3: 29 + 31 + 3
    ],
)
def test_day_precision_boundary(start, end, days, satisfied):
    facts = make_facts(mtx_start=start, mtx_end=end)
    assert conservative_days(facts) == days
    assert label_case(facts).step_therapy_satisfied is satisfied


def test_month_precision_start_uses_last_day_of_month():
    # Actual Mar 10 -> Jun 22 is 104 days (21 + 30 + 31 + 22), but "March 2026" only
    # establishes Mar 31 -> Jun 22 = 83 days (30 + 31 + 22).
    day = make_facts(mtx_start=date(2026, 3, 10), mtx_end=date(2026, 6, 22))
    month = make_facts(
        mtx_start=date(2026, 3, 10), mtx_end=date(2026, 6, 22), start_precision="month"
    )
    assert conservative_days(day) == 104 and label_case(day).step_therapy_satisfied
    assert conservative_days(month) == 83 and not label_case(month).step_therapy_satisfied
    assert action_for(month) is WorkflowAction.HUMAN_REVIEW
    # Mar 31 -> Jun 23 = 84 days (30 + 31 + 23): exactly enough.
    edge = make_facts(
        mtx_start=date(2026, 3, 10), mtx_end=date(2026, 6, 23), start_precision="month"
    )
    assert conservative_days(edge) == 84 and label_case(edge).step_therapy_satisfied


def test_month_precision_end_uses_first_day_of_month():
    # "June 2026" end establishes Jun 1. Mar 9 -> Jun 1 = 22 + 30 + 31 + 1 = 84 days.
    ok = make_facts(mtx_start=date(2026, 3, 9), mtx_end=date(2026, 6, 20), end_precision="month")
    short = make_facts(
        mtx_start=date(2026, 3, 10), mtx_end=date(2026, 6, 20), end_precision="month"
    )
    assert conservative_days(ok) == 84 and label_case(ok).step_therapy_satisfied
    assert conservative_days(short) == 83 and not label_case(short).step_therapy_satisfied


def test_month_to_month_matches_step_therapy_module_examples():
    # Feb 2026 -> May 2026: Feb 28 -> May 1 = 31 + 30 + 1 = 62 days (fails).
    # Feb 2026 -> Jul 2026: Feb 28 -> Jul 1 = 31 + 30 + 31 + 30 + 1 = 123 days (passes).
    short = make_facts(
        mtx_start=date(2026, 2, 3),
        mtx_end=date(2026, 5, 20),
        start_precision="month",
        end_precision="month",
    )
    long = make_facts(
        mtx_start=date(2026, 2, 3),
        mtx_end=date(2026, 7, 20),
        start_precision="month",
        end_precision="month",
    )
    assert conservative_days(short) == 62 and not label_case(short).step_therapy_satisfied
    assert conservative_days(long) == 123 and label_case(long).step_therapy_satisfied


def test_ongoing_treatment_counts_to_as_of_date():
    # "since March 2026" -> Mar 31 -> Sep 15 = 30 + 31 + 30 + 31 + 31 + 15 = 168 days.
    ongoing = make_facts(
        mtx_start=date(2026, 3, 5), mtx_end=None, end_precision=None, start_precision="month"
    )
    assert conservative_days(ongoing) == 168 and label_case(ongoing).step_therapy_satisfied
    # Jun 23 -> Sep 15 = 7 + 31 + 31 + 15 = 84 days; Jun 24 -> Sep 15 = 83 days.
    edge = make_facts(mtx_start=date(2026, 6, 23), mtx_end=None, end_precision=None)
    late = make_facts(mtx_start=date(2026, 6, 24), mtx_end=None, end_precision=None)
    assert conservative_days(edge) == 84 and label_case(edge).step_therapy_satisfied
    assert conservative_days(late) == 83 and not label_case(late).step_therapy_satisfied


@pytest.mark.parametrize("field", ["start_precision", "end_precision"])
def test_date_without_year_establishes_nothing_and_requests_history(field):
    facts = make_facts(**{field: "no_year"})
    truth = label_case(facts)
    assert conservative_days(facts) is None
    assert not truth.step_therapy_satisfied
    assert truth.missing_evidence is MissingEvidence.TREATMENT_HISTORY
    assert not truth.documentation_complete
    assert action_for(facts) is WorkflowAction.REQUEST_INFO


def test_contradiction_overrides_a_sufficient_duration():
    facts = make_facts(contradiction="history_vs_note", medication_history=True)
    truth = label_case(facts)
    assert conservative_days(facts) == 140
    assert truth.contradiction_present and not truth.step_therapy_satisfied
    assert truth.missing_evidence is MissingEvidence.NONE and truth.documentation_complete
    assert action_for(facts) is WorkflowAction.HUMAN_REVIEW


def dates_conflict_facts(**overrides):
    # Note: 2026-04-06 -> 2026-06-01 (56 days). History: starts 2026-02-09 (112 days).
    values = {
        "contradiction": "dates_conflict",
        "medication_history": True,
        "mtx_start": date(2026, 4, 6),
        "history_start": date(2026, 2, 9),
    }
    values.update(overrides)
    return make_facts(**values)


def test_dates_conflict_is_a_contradiction_that_fails_step_therapy():
    facts = dates_conflict_facts()
    truth = label_case(facts)
    assert conservative_days(facts) == 56 < MIN_DAYS
    assert truth.contradiction_present and not truth.step_therapy_satisfied
    assert truth.missing_evidence is MissingEvidence.NONE and truth.documentation_complete
    assert action_for(facts) is WorkflowAction.HUMAN_REVIEW
    assert "note 56d, history 112d" in truth.notes


def test_notes_do_not_mention_an_other_dmard_that_is_not_rendered():
    dmard = ("sulfasalazine 1000 mg twice daily",)
    undocumented = make_facts(
        mtx_status="undocumented", mtx_outcome="not_stated", other_dmards=dmard, **NOT_TAKEN
    )
    assert "DMARD" not in label_case(undocumented).notes
    for rendered in (
        make_facts(other_dmards=dmard),
        make_facts(mtx_status="never", mtx_outcome="not_stated", other_dmards=dmard, **NOT_TAKEN),
        make_facts(contradiction="history_vs_note", medication_history=True, other_dmards=dmard),
    ):
        assert "other DMARD sulfasalazine" in label_case(rendered).notes


def test_notes_omit_the_outcome_a_history_vs_note_note_does_not_render():
    notes = label_case(make_facts(contradiction="history_vs_note", medication_history=True)).notes
    assert "inadequate_response" not in notes
    assert "inadequate_response" in label_case(make_facts()).notes
    assert "inadequate_response" in label_case(dates_conflict_facts()).notes


def test_near_miss_flag_is_only_for_near_miss_courses():
    assert "near-miss" in label_case(make_facts(difficulty="hard")).notes
    assert "near-miss" not in label_case(dates_conflict_facts(difficulty="hard")).notes


def test_contradiction_case_does_not_request_history_for_a_yearless_date():
    facts = make_facts(
        contradiction="history_vs_note", medication_history=True, start_precision="no_year"
    )
    assert label_case(facts).missing_evidence is MissingEvidence.NONE


@pytest.mark.parametrize("outcome", ["inadequate_response", "intolerance"])
def test_qualifying_outcomes(outcome):
    assert label_case(make_facts(mtx_outcome=outcome)).step_therapy_satisfied


def test_outcome_not_stated_fails_step_therapy_but_is_complete():
    truth = label_case(make_facts(mtx_outcome="not_stated"))
    assert not truth.step_therapy_satisfied and truth.documentation_complete
    assert action_for(make_facts(mtx_outcome="not_stated")) is WorkflowAction.HUMAN_REVIEW


@pytest.mark.parametrize("status", ["never", "relative_only"])
def test_never_and_relative_only_are_documented_history_needing_review(status):
    facts = make_facts(mtx_status=status, mtx_outcome="not_stated", **NOT_TAKEN)
    truth = label_case(facts)
    assert not truth.step_therapy_satisfied
    assert truth.documentation_complete and truth.missing_evidence is MissingEvidence.NONE
    assert action_for(facts) is WorkflowAction.HUMAN_REVIEW


def test_undocumented_history_requests_treatment_history():
    facts = make_facts(mtx_status="undocumented", mtx_outcome="not_stated", **NOT_TAKEN)
    truth = label_case(facts)
    assert truth.missing_evidence is MissingEvidence.TREATMENT_HISTORY
    assert action_for(facts) is WorkflowAction.REQUEST_INFO


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {"diagnosis_status": "pending", "mtx_status": "undocumented", "member_id": None},
            MissingEvidence.DIAGNOSIS,
        ),
        ({"diagnosis_status": "absent"}, MissingEvidence.DIAGNOSIS),
        ({"mtx_status": "undocumented", "member_id": None}, MissingEvidence.TREATMENT_HISTORY),
        ({"start_precision": "no_year", "member_id": None}, MissingEvidence.TREATMENT_HISTORY),
        ({"member_id": None}, MissingEvidence.INSURANCE_INFORMATION),
        ({}, MissingEvidence.NONE),
    ],
)
def test_missing_evidence_precedence(overrides, expected):
    if overrides.get("mtx_status") == "undocumented":
        overrides = {**overrides, "mtx_outcome": "not_stated", **NOT_TAKEN}
    truth = label_case(make_facts(**overrides))
    assert truth.missing_evidence is expected
    assert truth.documentation_complete is (expected is MissingEvidence.NONE)


def test_diagnosis_gap_is_not_supported():
    truth = label_case(make_facts(diagnosis_status="pending"))
    assert not truth.diagnosis_supported
    assert action_for(make_facts(diagnosis_status="pending")) is WorkflowAction.REQUEST_INFO


def test_missing_member_id_requests_info():
    assert action_for(make_facts(member_id=None)) is WorkflowAction.REQUEST_INFO


def test_underage_patient_is_reviewed_even_when_labels_are_clean():
    assert action_for(make_facts(), age=17) is WorkflowAction.HUMAN_REVIEW


def test_notes_summarize_the_scenario():
    notes = label_case(
        make_facts(
            difficulty="hard",
            start_precision="month",
            mtx_start=date(2026, 3, 10),
            mtx_end=date(2026, 6, 22),
        )
    ).notes
    assert notes.startswith("gen-v0.2 hard: mtx taken 104d actual, 83d conservative")
    assert "near-miss" in notes


# ---- Phase 3D: rule D8 (interrupted courses) and immunara-v0.2 recency ----

V1, V2 = load_policy("immunara-v0.1"), load_policy("immunara-v0.2")


def interrupted(first, second, variant, **overrides):
    """A gen-v0.3 interrupted course; `first`/`second` are (start, end) with end None = ongoing."""
    values = {
        "generator_version": "gen-v0.3",
        "mtx_segments": (first, second),
        "mtx_start": first[0],
        "mtx_end": second[1],
        "end_precision": None if second[1] is None else "day",
        "interruption_variant": variant,
        "interruption_reason": "infection",
    }
    return make_facts(**(values | overrides))


# GOLD-TMP-17 shape: 2026-01-05 -> 2026-02-23 (49 d), held, 2026-03-23 -> 2026-05-18 (56 d).
TMP_17 = interrupted(
    (date(2026, 1, 5), date(2026, 2, 23)), (date(2026, 3, 23), date(2026, 5, 18)), "a"
)
# GOLD-TMP-18 shape: 2025-10-06 -> 2025-11-03 (28 d), 2026-01-12 -> 2026-05-04 (112 d).
TMP_18 = interrupted(
    (date(2025, 10, 6), date(2025, 11, 3)), (date(2026, 1, 12), date(2026, 5, 4)), "b"
)
# Pattern (c): 2026-01-05 -> 2026-05-04 (119 d), 2026-06-01 -> 2026-07-06 (35 d).
EARLIER = interrupted(
    (date(2026, 1, 5), date(2026, 5, 4)), (date(2026, 6, 1), date(2026, 7, 6)), "c"
)


def test_d8_tmp_17_pattern_is_not_satisfied_although_the_span_is_133_days():
    assert segment_days(TMP_17) == (49, 56)
    assert conservative_days(TMP_17) == 133
    assert not label_case(TMP_17).step_therapy_satisfied
    assert action_for(TMP_17) is WorkflowAction.HUMAN_REVIEW


def test_d8_a_single_qualifying_segment_satisfies_either_way_round():
    assert segment_days(TMP_18) == (28, 112)
    assert segment_days(EARLIER) == (119, 35)
    for facts in (TMP_18, EARLIER):
        assert label_case(facts).step_therapy_satisfied
        assert action_for(facts) is WorkflowAction.AUTO_PROCESS


def test_d8_still_needs_a_qualifying_outcome():
    assert not label_case(
        interrupted(TMP_18.mtx_segments[0], TMP_18.mtx_segments[1], "b", mtx_outcome="not_stated")
    ).step_therapy_satisfied


def test_d8_an_ongoing_later_segment_counts_to_as_of():
    facts = interrupted(
        (date(2026, 1, 5), date(2026, 2, 2)), (date(2026, 5, 4), None), "b"
    )  # 28 d, then 2026-05-04 -> 2026-09-15 = 134 d
    assert segment_days(facts) == (28, 134)
    assert label_case(facts).step_therapy_satisfied


def test_interrupted_notes_name_the_segments_and_pattern():
    notes = label_case(TMP_17).notes
    assert notes.startswith("gen-v0.3 easy: mtx taken interrupted (infection, pattern a):")
    assert "segments 49d and 56d, inadequate_response" in notes


def test_v0_1_and_v0_2_labels_agree_for_a_recent_course():
    facts = make_facts()  # ended 2026-06-01, 106 days before 2026-09-15
    assert days_since_end(facts) == 106
    assert label_case(facts, V1) == label_case(facts, V2) == label_case(facts)


def test_recency_fails_a_course_that_ended_more_than_365_days_before_as_of():
    old = make_facts(mtx_start=date(2025, 1, 13), mtx_end=date(2025, 6, 2))  # 140 d
    assert days_since_end(old) == 470
    assert label_case(old, V1).step_therapy_satisfied
    assert not label_case(old, V2).step_therapy_satisfied
    edge = make_facts(mtx_start=date(2025, 4, 1), mtx_end=date(2025, 9, 15))
    assert days_since_end(edge) == 365
    assert label_case(edge, V2).step_therapy_satisfied


def test_recency_uses_the_conservative_end_of_a_month_only_date():
    # "September 2025" ends at the earliest 2025-09-01: 379 days before 2026-09-15.
    facts = make_facts(mtx_start=date(2025, 3, 3), mtx_end=date(2025, 9, 20), end_precision="month")
    assert days_since_end(facts) == 379
    assert label_case(facts, V1).step_therapy_satisfied
    assert not label_case(facts, V2).step_therapy_satisfied


def test_recency_applies_to_the_qualifying_segment_not_the_last_one():
    # The earlier segment qualifies (119 d) but ended 2025-05-04, 499 days before as_of; the
    # later, recent segment is short (35 d).
    facts = interrupted(
        (date(2025, 1, 5), date(2025, 5, 4)), (date(2026, 6, 1), date(2026, 7, 6)), "c"
    )
    assert label_case(facts, V1).step_therapy_satisfied
    assert not label_case(facts, V2).step_therapy_satisfied


def test_an_ongoing_course_is_always_recent():
    facts = make_facts(mtx_start=date(2024, 1, 8), mtx_end=None, end_precision=None)
    assert days_since_end(facts) == 0
    assert label_case(facts, V2).step_therapy_satisfied


def test_gen_v0_3_notes_record_how_long_ago_the_course_ended():
    facts = make_facts(generator_version="gen-v0.3")
    assert label_case(facts).notes.endswith("ended 106d before as-of")
    assert "before as-of" not in label_case(make_facts()).notes  # gen-v0.2 notes unchanged
