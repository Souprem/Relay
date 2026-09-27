"""Versioned Jev question sets: 4 Nouls, 1 missing-evidence Choice, 7 date-part Choices.

Question ids are for code and are not sent to the model, so every instruction carries its full
meaning. Yes/no questions are phrased so that a high value means "yes".

q-v0.1 is the v0.1 milestone set. q-v0.2 changes only two criteria so that a record stating that
the patient never took the required drug counts as documented treatment history.

q-v0.3 (Phase 3D) keeps every q-v0.2 question and adds seven for an interrupted course: a Noul
(was the patient's own methotrexate held, paused or stopped and later restarted?) and the date
parts of the first stop (pause) and of the restart. Its start and end questions gain "(the first
time, if it was restarted)" and "(the last time, if it was restarted)": 19 questions.
"""

import hashlib
import json
import re
from collections.abc import Sequence

from typesafe_sdk import Choice, Noul, NoulCriteria

from relay.cases.models import CaseInput
from relay.cases.policies import AuthorizationPolicy
from relay.decisions.step_therapy import MONTHS

Q_V0_1 = "q-v0.1"
Q_V0_2 = "q-v0.2"
Q_V0_3 = "q-v0.3"
QUESTION_SET_VERSIONS: tuple[str, ...] = (Q_V0_1, Q_V0_2, Q_V0_3)
DEFAULT_QUESTION_SET_VERSION = Q_V0_2
QUESTION_IDS: tuple[str, ...] = (
    "diagnosis_support",
    "documentation_complete",
    "material_contradiction",
    "missing_evidence",
    "mtx_start_month",
    "mtx_start_day",
    "mtx_start_year",
    "mtx_end_status",
    "mtx_end_month",
    "mtx_end_day",
    "mtx_end_year",
    "mtx_inadequate_response",
)
INTERRUPTION_QUESTION_IDS: tuple[str, ...] = (
    "mtx_interrupted",
    "mtx_pause_month",
    "mtx_pause_day",
    "mtx_pause_year",
    "mtx_restart_month",
    "mtx_restart_day",
    "mtx_restart_year",
)
QUESTION_IDS_V0_3: tuple[str, ...] = QUESTION_IDS + INTERRUPTION_QUESTION_IDS
_YEAR_PLACEHOLDER = "<case-specific years>"
_YEAR_RE = re.compile(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)")
_ABSENT = "The documents do not state this, or the patient never took the medication."
_NOT_INTERRUPTED = (
    "The documents do not state this, or the patient's course was never held, paused or stopped "
    "and then restarted."
)
_FIRST_TIME = " (the first time, if it was restarted)"
_LAST_TIME = " (the last time, if it was restarted)"


def candidate_years(case: CaseInput) -> list[str]:
    years = {m for doc in case.documents for m in _YEAR_RE.findall(doc.text)}
    years.add(str(case.as_of_date.year))
    return sorted(years)


def _date_part_questions(
    prefix: str,
    event: str,
    drug: str,
    years: Sequence[str],
    *,
    qualifier: str = "",
    none_also: str = "",
    absent: str = _ABSENT,
) -> dict[str, Choice]:
    """Month, day and year questions for one event. `qualifier` follows the drug name,
    `none_also` extends each "Answer 'none' if ..." clause; both are empty up to q-v0.2."""
    who = f"the patient (not a relative or other person) {event} taking {drug}{qualifier}"
    return {
        f"{prefix}_month": Choice(
            instructions=(
                f"In which month did {who}? Answer 'none' if the documents do not state the "
                f"month{none_also}."
            ),
            criteria={m: None for m in MONTHS} | {"none": absent},
        ),
        f"{prefix}_day": Choice(
            instructions=(
                f"On which day of the month (1-31) did {who}? Answer 'none' if the day is not "
                f"stated, for example when only a month is given{none_also}."
            ),
            criteria={str(d): None for d in range(1, 32)} | {"none": absent},
        ),
        f"{prefix}_year": Choice(
            instructions=(
                f"In which year did {who}? Answer 'none' if no year is stated for this "
                f"event{none_also}."
            ),
            criteria={y: None for y in years} | {"none": absent},
        ),
    }


def validate_question_set_version(version: str) -> None:
    if version not in QUESTION_SET_VERSIONS:
        raise ValueError(f"unknown question set {version!r}; known: {list(QUESTION_SET_VERSIONS)}")


def question_ids(version: str) -> tuple[str, ...]:
    """The question ids of a question set, in the order they are sent."""
    validate_question_set_version(version)
    return QUESTION_IDS_V0_3 if version == Q_V0_3 else QUESTION_IDS


def _never_taken_counts(version: str) -> bool:
    """From q-v0.2 on, a record that the patient never took the drug is treatment history."""
    return version in (Q_V0_2, Q_V0_3)


def _documentation_complete_true(drug: str, version: str) -> str:
    text = (
        "The insurance member ID, a clinician note supporting the diagnosis, and the patient's "
        f"treatment history (including whether and when {drug} was taken) are all present"
    )
    if _never_taken_counts(version):
        text += f" (a statement that the patient never took {drug} counts as treatment history)"
    return text + "."


def _treatment_history_option(drug: str, version: str) -> str:
    if _never_taken_counts(version):
        return (
            f"The records do not say whether or when the patient took {drug}. A record stating "
            f"that the patient never took {drug} counts as documented treatment history."
        )
    return f"The patient's {drug} treatment history (dates or outcome) is not documented."


def build_questions(
    policy: AuthorizationPolicy,
    years: Sequence[str],
    version: str = DEFAULT_QUESTION_SET_VERSION,
) -> dict[str, Noul | Choice]:
    validate_question_set_version(version)
    drug = policy.required_therapy
    indication = policy.indication
    questions: dict[str, Noul | Choice] = {
        "diagnosis_support": Noul(
            instructions=(
                f"Do the clinical documents establish a clinician-documented diagnosis of "
                f"{indication} for this patient, as the policy requires?"
            ),
            criteria=NoulCriteria(
                true=f"A clinician states that the patient has {indication} as an established "
                "diagnosis.",
                false="The diagnosis is absent, only suspected, pending workup, or describes "
                "someone other than the patient.",
            ),
        ),
        "documentation_complete": Noul(
            instructions=(
                "Does this request include every item the policy lists under submission "
                "documentation?"
            ),
            criteria=NoulCriteria(
                true=_documentation_complete_true(drug, version),
                false="At least one required item is missing, unavailable, or marked as not "
                "provided.",
            ),
        ),
        "material_contradiction": Noul(
            instructions=(
                "Do the case documents contain a material contradiction about the patient's "
                "diagnosis or treatment history that affects this authorization?"
            ),
            criteria=NoulCriteria(
                true="Two sources make incompatible claims about the same fact, for example one "
                "record shows a medication was taken while another says it was never tried.",
                false="The sources agree, or differ only in wording, detail, or precision "
                "without conflicting.",
            ),
        ),
        "missing_evidence": Choice(
            instructions=(
                "What is the most important information missing from this request for the "
                "policy decision, if any?"
            ),
            criteria={
                "DIAGNOSIS": f"No established diagnosis of {indication} is documented.",
                "TREATMENT_HISTORY": _treatment_history_option(drug, version),
                "LAB_RESULT": "A lab result that the decision depends on is missing.",
                "DOSAGE": "The requested dose or regimen is missing.",
                "INSURANCE_INFORMATION": "The insurance member ID or plan information is missing.",
                "NONE": "Nothing that the policy requires is missing.",
            },
        ),
    }
    v0_3 = version == Q_V0_3
    questions |= _date_part_questions(
        "mtx_start", "start", drug, years, qualifier=_FIRST_TIME if v0_3 else ""
    )
    questions["mtx_end_status"] = Choice(
        instructions=(
            f"What is the status of the patient's own {drug} treatment (not a relative's)"
            f"{_LAST_TIME if v0_3 else ''}?"
        ),
        criteria={
            "ended": f"The documents say the patient stopped taking {drug}.",
            "ongoing": f"The documents say the patient is still taking {drug}.",
            "not_stated": f"The documents do not say, or the patient never took {drug}.",
        },
    )
    questions |= _date_part_questions(
        "mtx_end", "stop", drug, years, qualifier=_LAST_TIME if v0_3 else ""
    )
    questions["mtx_inadequate_response"] = Noul(
        instructions=(
            f"Is it documented that the patient's own {drug} treatment was ineffective "
            "(inadequate response) or was stopped because of intolerance or a contraindication?"
        ),
        criteria=NoulCriteria(
            true=f"A clinician documents that {drug} did not adequately control this patient's "
            "disease, or that it caused intolerance or is contraindicated for this patient.",
            false="There is no such documentation for this patient; statements about "
            "relatives or other people do not count, and neither does a different medication.",
        ),
    )
    if v0_3:
        questions |= _interruption_questions(drug, years)
    return questions


def _interruption_questions(drug: str, years: Sequence[str]) -> dict[str, Noul | Choice]:
    """q-v0.3's seven additions: was the course interrupted, and when was it stopped and resumed."""
    questions: dict[str, Noul | Choice] = {
        "mtx_interrupted": Noul(
            instructions=(
                f"Do the documents describe the patient's own {drug} being held, paused or "
                "stopped and later restarted?"
            ),
            criteria=NoulCriteria(
                true=f"A clinical record states that the patient's own {drug} was held, paused "
                "or stopped, and that the patient later resumed or restarted it.",
                false=f"The patient took one continuous course, never took {drug}, or the hold "
                "and restart describe a relative or another person.",
            ),
        )
    }
    never_restarted = ", or if the course was never stopped and restarted"
    questions |= _date_part_questions(
        "mtx_pause",
        "first stop",
        drug,
        years,
        qualifier=" before restarting it (a hold or pause counts as a stop)",
        none_also=never_restarted,
        absent=_NOT_INTERRUPTED,
    )
    questions |= _date_part_questions(
        "mtx_restart",
        "restart",
        drug,
        years,
        qualifier=" after a hold, pause or stop",
        none_also=never_restarted,
        absent=_NOT_INTERRUPTED,
    )
    return questions


def question_set_hash(
    policy: AuthorizationPolicy, version: str = DEFAULT_QUESTION_SET_VERSION
) -> str:
    questions = build_questions(policy, [_YEAR_PLACEHOLDER], version)
    payload = {qid: q.model_dump(mode="json") for qid, q in questions.items()}
    blob = json.dumps({"version": version, "questions": payload}, sort_keys=True)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()
