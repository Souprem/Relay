from typesafe_sdk import Choice, Noul

from relay.cases.models import Document
from relay.cases.policies import load_policy
from relay.decisions.questions import (
    QUESTION_IDS,
    build_questions,
    candidate_years,
    question_set_hash,
)
from tests.factories import make_case_input

POLICY = load_policy("immunara-v0.1")


def note(text):
    return (Document(id="physician_note", kind="physician_note", text=text),)


def test_exactly_twelve_expected_questions():
    questions = build_questions(POLICY, ["2026"])
    assert tuple(questions) == QUESTION_IDS
    assert len(questions) == 12


def test_question_types():
    questions = build_questions(POLICY, ["2026"])
    nouls = {qid for qid, q in questions.items() if isinstance(q, Noul)}
    choices = {qid for qid, q in questions.items() if isinstance(q, Choice)}
    assert nouls == {
        "diagnosis_support",
        "documentation_complete",
        "material_contradiction",
        "mtx_inadequate_response",
    }
    assert len(choices) == 8


def test_missing_evidence_options():
    options = set(build_questions(POLICY, ["2026"])["missing_evidence"].criteria)
    assert options == {
        "DIAGNOSIS",
        "TREATMENT_HISTORY",
        "LAB_RESULT",
        "DOSAGE",
        "INSURANCE_INFORMATION",
        "NONE",
    }


def test_date_part_questions_offer_none():
    questions = build_questions(POLICY, ["2026"])
    for qid in ("mtx_start_month", "mtx_start_day", "mtx_start_year", "mtx_end_month"):
        assert "none" in questions[qid].criteria, qid
    assert set(questions["mtx_end_status"].criteria) == {"ended", "ongoing", "not_stated"}
    assert len(questions["mtx_start_month"].criteria) == 13
    assert len(questions["mtx_start_day"].criteria) == 32


def test_year_options_come_from_documents_plus_as_of_year():
    case = make_case_input(documents=note("Mother took MTX in 2019. MTX started 2026-02-04."))
    years = candidate_years(case)
    assert years == ["2019", "2026"]
    assert list(build_questions(POLICY, years)["mtx_start_year"].criteria) == [
        "2019",
        "2026",
        "none",
    ]


def test_year_extraction_ignores_non_year_numbers():
    case = make_case_input(documents=note("CDAI 28, 15 mg weekly, member EXH-448213, DAS28 5.4"))
    assert candidate_years(case) == ["2026"]


def test_questions_refer_to_the_patient_not_relatives():
    q = build_questions(POLICY, ["2026"])
    assert "relative" in str(q["mtx_start_month"].instructions).lower()
    assert "relatives" in str(q["mtx_inadequate_response"].criteria).lower()


def test_hash_is_stable_and_independent_of_case_years():
    assert question_set_hash(POLICY) == question_set_hash(POLICY)
    assert question_set_hash(POLICY).startswith("sha256:")


def test_hash_changes_when_wording_changes():
    other = POLICY.model_copy(update={"indication": "psoriatic arthritis"})
    assert question_set_hash(other) != question_set_hash(POLICY)
