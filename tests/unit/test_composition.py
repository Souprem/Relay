import pytest

from relay.cases.policies import load_policy
from relay.decisions.base import DecisionId
from relay.decisions.composition import (
    CHOICE_QUESTIONS,
    UNASSIGNED,
    YES_NO_QUESTIONS,
    AnswerSet,
    ChoiceResult,
    MalformedAnswers,
    compose_decisions,
    single_answer_distribution,
)
from relay.decisions.questions import QUESTION_IDS
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
