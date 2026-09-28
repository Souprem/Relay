import pytest
from typesafe_sdk import Choice, Noul

from relay.cases.models import Document
from relay.cases.policies import load_policy
from relay.decisions.questions import (
    DEFAULT_QUESTION_SET_VERSION,
    INTERRUPTION_QUESTION_IDS,
    QUESTION_IDS,
    QUESTION_IDS_V0_3,
    QUESTION_SET_VERSIONS,
    build_questions,
    candidate_years,
    question_ids,
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


# Pinned before Phase 2B: the committed smoke-v0.1 baseline traces carry exactly this hash.
Q_V0_1_HASH = "sha256:b395531673a539ec02c1e66bb03d5952b8608eba15f041939549ece2617ac77a"
NEVER_TOOK = "never took methotrexate"


def test_known_versions_and_default():
    assert QUESTION_SET_VERSIONS == ("q-v0.1", "q-v0.2", "q-v0.3")
    # Adopted by the dev-only rule (spec §6); see evals/baselines/gen-v0.2-dev/adoption.txt.
    assert DEFAULT_QUESTION_SET_VERSION == "q-v0.2"


def test_q_v0_1_hash_is_unchanged_from_before_phase_2b():
    assert question_set_hash(POLICY, "q-v0.1") == Q_V0_1_HASH


def test_q_v0_2_hash_differs_from_q_v0_1():
    assert question_set_hash(POLICY, "q-v0.2") != question_set_hash(POLICY, "q-v0.1")
    assert question_set_hash(POLICY, "q-v0.2").startswith("sha256:")


def test_q_v0_2_treatment_history_option_counts_never_taken_as_documented():
    option = build_questions(POLICY, ["2026"], "q-v0.2")["missing_evidence"].criteria[
        "TREATMENT_HISTORY"
    ]
    assert option == (
        "The records do not say whether or when the patient took methotrexate. A record "
        "stating that the patient never took methotrexate counts as documented treatment history."
    )


def test_q_v0_2_documentation_criterion_adds_the_never_taken_clause():
    v1 = build_questions(POLICY, ["2026"], "q-v0.1")["documentation_complete"].criteria
    v2 = build_questions(POLICY, ["2026"], "q-v0.2")["documentation_complete"].criteria
    assert v2["true"] == v1["true"].removesuffix(".") + (
        " (a statement that the patient never took methotrexate counts as treatment history)."
    )
    assert v2["false"] == v1["false"]
    assert NEVER_TOOK not in v1["true"]


def test_q_v0_2_changes_nothing_else():
    v1 = build_questions(POLICY, ["2019", "2026"], "q-v0.1")
    v2 = build_questions(POLICY, ["2019", "2026"], "q-v0.2")
    assert tuple(v2) == QUESTION_IDS
    changed = {qid for qid in QUESTION_IDS if v1[qid].model_dump() != v2[qid].model_dump()}
    assert changed == {"documentation_complete", "missing_evidence"}
    v1_options = dict(v1["missing_evidence"].criteria)
    v2_options = dict(v2["missing_evidence"].criteria)
    del v1_options["TREATMENT_HISTORY"], v2_options["TREATMENT_HISTORY"]
    assert v1_options == v2_options


def test_unknown_question_set_is_rejected():
    with pytest.raises(ValueError, match="q-v9"):
        build_questions(POLICY, ["2026"], "q-v9")
    with pytest.raises(ValueError, match="q-v9"):
        question_set_hash(POLICY, "q-v9")


# ---- Phase 3D: q-v0.3 (interrupted courses) ----

# The committed gold-v0.1 and gen-v0.2 q-v0.2 Jev traces carry exactly this hash.
Q_V0_2_HASH = "sha256:89717c795a2dfea7efe30e038fb483c6d4ed72d343bfbfcefeabfc6483d7a4aa"


def test_q_v0_2_hash_is_unchanged_by_q_v0_3():
    assert question_set_hash(POLICY, "q-v0.2") == Q_V0_2_HASH
    assert question_set_hash(POLICY, "q-v0.1") == Q_V0_1_HASH


def test_q_v0_3_has_nineteen_questions_in_a_fixed_order():
    questions = build_questions(POLICY, ["2026"], "q-v0.3")
    assert tuple(questions) == QUESTION_IDS_V0_3 == QUESTION_IDS + INTERRUPTION_QUESTION_IDS
    assert len(questions) == 19
    assert question_ids("q-v0.3") == QUESTION_IDS_V0_3
    assert question_ids("q-v0.2") == question_ids("q-v0.1") == QUESTION_IDS
    assert isinstance(questions["mtx_interrupted"], Noul)
    assert all(isinstance(questions[q], Choice) for q in INTERRUPTION_QUESTION_IDS[1:])


def test_question_ids_rejects_an_unknown_set():
    with pytest.raises(ValueError, match="unknown question set 'q-v9'"):
        question_ids("q-v9")


def test_q_v0_3_keeps_every_q_v0_2_question_except_the_first_and_last_time_wording():
    v2 = build_questions(POLICY, ["2025", "2026"], "q-v0.2")
    v3 = build_questions(POLICY, ["2025", "2026"], "q-v0.3")
    reworded = {
        "mtx_start_month",
        "mtx_start_day",
        "mtx_start_year",
        "mtx_end_status",
        "mtx_end_month",
        "mtx_end_day",
        "mtx_end_year",
    }
    for qid in QUESTION_IDS:
        if qid in reworded:
            assert v3[qid].criteria == v2[qid].criteria, qid
            assert v3[qid].instructions != v2[qid].instructions, qid
        else:
            assert v3[qid] == v2[qid], qid
    first = " (the first time, if it was restarted)"
    last = " (the last time, if it was restarted)"
    for qid in ("mtx_start_month", "mtx_start_day", "mtx_start_year"):
        assert v3[qid].instructions == v2[qid].instructions.replace(
            "taking methotrexate?", f"taking methotrexate{first}?"
        )
    for qid in ("mtx_end_month", "mtx_end_day", "mtx_end_year"):
        assert v3[qid].instructions == v2[qid].instructions.replace(
            "taking methotrexate?", f"taking methotrexate{last}?"
        )
    assert v3["mtx_end_status"].instructions == (
        f"What is the status of the patient's own methotrexate treatment (not a relative's){last}?"
    )


def test_q_v0_3_interruption_questions():
    q = build_questions(POLICY, ["2025", "2026"], "q-v0.3")
    assert q["mtx_interrupted"].instructions == (
        "Do the documents describe the patient's own methotrexate being held, paused or stopped "
        "and later restarted?"
    )
    criteria = q["mtx_interrupted"].criteria
    assert "resumed or restarted" in criteria["true"]
    assert "one continuous course" in criteria["false"] and "relative" in criteria["false"]
    assert q["mtx_pause_month"].instructions == (
        "In which month did the patient (not a relative or other person) first stop taking "
        "methotrexate before restarting it (a hold or pause counts as a stop)? Answer 'none' if "
        "the documents do not state the month, or if the course was never stopped and restarted."
    )
    assert q["mtx_restart_day"].instructions == (
        "On which day of the month (1-31) did the patient (not a relative or other person) "
        "restart taking methotrexate after a hold, pause or stop? Answer 'none' if the day is not "
        "stated, for example when only a month is given, or if the course was never stopped and "
        "restarted."
    )
    assert list(q["mtx_restart_year"].criteria) == ["2025", "2026", "none"]
    assert len(q["mtx_pause_day"].criteria) == 32
    assert "never held, paused or stopped" in q["mtx_pause_month"].criteria["none"]


def test_q_v0_3_hash_is_new_and_the_same_under_either_immunara_policy():
    v3 = question_set_hash(POLICY, "q-v0.3")
    assert v3 not in (Q_V0_1_HASH, Q_V0_2_HASH)
    assert question_set_hash(load_policy("immunara-v0.2"), "q-v0.3") == v3
    assert question_set_hash(load_policy("immunara-v0.2"), "q-v0.2") == Q_V0_2_HASH
