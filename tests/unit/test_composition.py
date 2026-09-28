import pytest

from relay.cases.policies import load_policy
from relay.decisions.base import DecisionId
from relay.decisions.composition import (
    CHOICE_QUESTIONS,
    CHOICE_QUESTIONS_V0_3,
    UNASSIGNED,
    YES_NO_QUESTIONS,
    YES_NO_QUESTIONS_V0_3,
    AnswerSet,
    ChoiceResult,
    MalformedAnswers,
    compose_decisions,
    question_groups,
    single_answer_distribution,
)
from relay.decisions.questions import QUESTION_IDS, QUESTION_IDS_V0_3
from tests.factories import make_case_input

POLICY = load_policy("immunara-v0.1")
CASE = make_case_input()  # as of 2026-09-15; the policy needs 12 weeks (84 days)


def certain(answer):
    return ChoiceResult(answer, {answer: 1.0}, 1.0)


def answers(**overrides):
    """Methotrexate 2026-01-12 -> 2026-06-01 (140 days), inadequate response at 0.9."""
    yes_no = {
        "diagnosis_support": 0.98,
        "documentation_complete": 0.97,
        "material_contradiction": 0.03,
        "mtx_inadequate_response": 0.9,
    }
    choices = {
        "missing_evidence": ChoiceResult("NONE", {"NONE": 0.94, "DIAGNOSIS": 0.06}, 0.94),
        "mtx_start_month": certain("January"),
        "mtx_start_day": certain("12"),
        "mtx_start_year": certain("2026"),
        "mtx_end_status": certain("ended"),
        "mtx_end_month": certain("June"),
        "mtx_end_day": certain("1"),
        "mtx_end_year": certain("2026"),
    }
    for qid, value in overrides.items():
        (yes_no if qid in yes_no else choices)[qid] = value
    return AnswerSet(yes_no=yes_no, choices=choices)


def compose(answer_set):
    return compose_decisions(answer_set, CASE, POLICY, "test-provider")


def test_question_groups_cover_the_twelve_questions():
    assert sorted(YES_NO_QUESTIONS + CHOICE_QUESTIONS) == sorted(QUESTION_IDS)


def test_composes_the_five_decisions_with_step_therapy_in_code():
    decisions, derivations = compose(answers())
    assert [d.question_id for d in decisions] == list(DecisionId)
    by_id = {d.question_id: d for d in decisions}
    assert by_id[DecisionId.DIAGNOSIS_SUPPORT].p_yes == 0.98
    assert by_id[DecisionId.STEP_THERAPY].p_yes == pytest.approx(1.0 * 0.9)
    missing = by_id[DecisionId.MISSING_EVIDENCE]
    assert (missing.answer, missing.probabilities, missing.confidence) == (
        "NONE",
        {"NONE": 0.94, "DIAGNOSIS": 0.06},
        0.94,
    )
    assert {d.provider for d in decisions} == {"test-provider"}
    step = derivations["step_therapy"]
    assert (step["min_days"], step["p_duration"], step["p_inadequate_response"]) == (84, 1.0, 0.9)


def test_single_answer_distribution_keeps_the_leftover_unassigned():
    assert single_answer_distribution("March", 0.9) == pytest.approx(
        {"March": 0.9, UNASSIGNED: 0.1}
    )
    assert single_answer_distribution("March", 1.0) == {"March": 1.0}


def test_leftover_mass_contributes_no_date_candidate():
    """2D spec section 4: start month at 0.9, every other part certain -> p_duration 0.9."""
    start = ChoiceResult("January", single_answer_distribution("January", 0.9), 0.9)
    _, derivations = compose(answers(mtx_start_month=start))
    assert derivations["step_therapy"]["p_duration"] == pytest.approx(0.9)
    # Without the UNASSIGNED share, prune() would renormalize January up to 1.0.
    bare = ChoiceResult("January", {"January": 0.9}, 0.9)
    _, derivations = compose(answers(mtx_start_month=bare))
    assert derivations["step_therapy"]["p_duration"] == pytest.approx(1.0)


@pytest.mark.parametrize("qid", YES_NO_QUESTIONS + CHOICE_QUESTIONS)
def test_a_missing_answer_is_malformed(qid):
    full = answers()
    yes_no = {k: v for k, v in full.yes_no.items() if k != qid}
    choices = {k: v for k, v in full.choices.items() if k != qid}
    with pytest.raises(MalformedAnswers, match=qid):
        compose(AnswerSet(yes_no=yes_no, choices=choices))


def test_out_of_range_values_are_malformed():
    with pytest.raises(MalformedAnswers, match="diagnosis_support"):
        compose(answers(diagnosis_support=1.5))
    with pytest.raises(MalformedAnswers, match="mtx_end_day"):
        compose(answers(mtx_end_day=ChoiceResult("1", {"1": float("nan")})))


def test_missing_evidence_needs_a_known_label_that_has_a_probability():
    with pytest.raises(MalformedAnswers, match="unknown label 'SOMETHING'"):
        compose(answers(missing_evidence=ChoiceResult("SOMETHING", {"SOMETHING": 1.0})))
    with pytest.raises(MalformedAnswers, match="has no probability"):
        compose(answers(missing_evidence=ChoiceResult("NONE", {"DIAGNOSIS": 1.0})))


# ---- Phase 3D: the q-v0.3 path, question groups and recency ----

POLICY_V2 = load_policy("immunara-v0.2")


def interrupted_answers(p_int, pause, restart, **overrides):
    """answers() plus q-v0.3's seven: pause and restart are (month, day, year) or None."""
    base = answers(**overrides)
    choices = dict(base.choices)
    for prefix, value in (("mtx_pause", pause), ("mtx_restart", restart)):
        for part, answer in zip(("month", "day", "year"), value or ("none",) * 3, strict=True):
            choices[f"{prefix}_{part}"] = certain(answer)
    return AnswerSet(yes_no=dict(base.yes_no) | {"mtx_interrupted": p_int}, choices=choices)


def compose_v3(answer_set, policy=POLICY):
    return compose_decisions(answer_set, CASE, policy, "test-provider", "q-v0.3")


def step_p(decisions):
    return next(d for d in decisions if d.question_id == DecisionId.STEP_THERAPY).p_yes


def test_question_groups_per_question_set():
    assert question_groups("q-v0.2") == question_groups("q-v0.1")
    assert question_groups("q-v0.2") == (YES_NO_QUESTIONS, CHOICE_QUESTIONS)
    yes_no, choices = question_groups("q-v0.3")
    assert sorted(yes_no + choices) == sorted(QUESTION_IDS_V0_3)
    assert (yes_no, choices) == (YES_NO_QUESTIONS_V0_3, CHOICE_QUESTIONS_V0_3)
    with pytest.raises(ValueError, match="unknown question set"):
        question_groups("q-v9")


def test_q_v0_3_path_reads_an_interruption_where_q_v0_2_cannot():
    # Jan 12 -> held Feb 23 (42 d), restarted Mar 23 -> Jun 1 (70 d): no segment reaches 84.
    answer_set = interrupted_answers(0.95, ("February", "23", "2026"), ("March", "23", "2026"))
    decisions, derivations = compose_v3(answer_set)
    step = derivations["step_therapy"]
    assert (step["p_continuous"], step["p_first_segment"], step["p_second_segment"]) == (
        1.0,
        0.0,
        0.0,
    )
    assert step["p_duration"] == pytest.approx(0.05)
    assert step_p(decisions) == pytest.approx(0.05 * 0.9)
    assert step["p_inadequate_response"] == 0.9
    # The q-v0.2 path ignores the extra answers and reads one 140-day course.
    q2_decisions, _ = compose(answer_set)
    assert step_p(q2_decisions) == pytest.approx(0.9)


def test_q_v0_3_path_equals_q_v0_2_when_certainly_not_interrupted():
    decisions, derivations = compose_v3(interrupted_answers(0.0, None, None))
    assert step_p(decisions) == pytest.approx(step_p(compose(answers())[0]))
    assert derivations["step_therapy"]["pause_candidates"] == []


@pytest.mark.parametrize("qid", YES_NO_QUESTIONS_V0_3 + CHOICE_QUESTIONS_V0_3)
def test_a_missing_q_v0_3_answer_is_malformed(qid):
    full = interrupted_answers(0.1, None, None)
    yes_no = {k: v for k, v in full.yes_no.items() if k != qid}
    choices = {k: v for k, v in full.choices.items() if k != qid}
    with pytest.raises(MalformedAnswers, match=qid):
        compose_v3(AnswerSet(yes_no=yes_no, choices=choices))


def test_an_unknown_question_set_is_rejected():
    with pytest.raises(ValueError, match="unknown question set"):
        compose_decisions(answers(), CASE, POLICY, "test-provider", "q-v9")


def old_course(**overrides):
    """Methotrexate 2025-01-13 -> 2025-06-02 (140 days), ended 470 days before 2026-09-15."""
    return {
        "mtx_start_year": certain("2025"),
        "mtx_start_day": certain("13"),
        "mtx_end_year": certain("2025"),
        "mtx_end_day": certain("2"),
        **overrides,
    }


def test_recency_applies_on_the_q_v0_2_path_under_immunara_v0_2():
    stale, stale_derivations = compose(answers(**old_course()))
    aware, aware_derivations = compose_decisions(
        answers(**old_course()), CASE, POLICY_V2, "test-provider"
    )
    assert step_p(stale) == pytest.approx(0.9)
    assert step_p(aware) == 0.0
    assert "max_days_since_therapy" not in stale_derivations["step_therapy"]
    assert aware_derivations["step_therapy"]["max_days_since_therapy"] == 365


def test_recency_applies_on_the_q_v0_3_path_under_immunara_v0_2():
    answer_set = interrupted_answers(0.02, None, None, **old_course())
    stale, stale_derivations = compose_v3(answer_set)
    aware, _ = compose_v3(answer_set, POLICY_V2)
    assert step_p(stale) == pytest.approx(0.98 * 0.9)
    assert step_p(aware) == 0.0
    assert stale_derivations["step_therapy"]["max_days_since_therapy"] is None
