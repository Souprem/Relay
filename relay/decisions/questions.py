"""Versioned Jev question sets: 4 Nouls, 1 missing-evidence Choice, 7 date-part Choices.

Question ids are for code and are not sent to the model, so every instruction carries its full
meaning. Yes/no questions are phrased so that a high value means "yes".

q-v0.1 is the v0.1 milestone set. q-v0.2 changes only two criteria so that a record stating that
the patient never took the required drug counts as documented treatment history.
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
QUESTION_SET_VERSIONS: tuple[str, ...] = (Q_V0_1, Q_V0_2)
DEFAULT_QUESTION_SET_VERSION = Q_V0_1
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
_YEAR_PLACEHOLDER = "<case-specific years>"
_YEAR_RE = re.compile(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)")
_ABSENT = "The documents do not state this, or the patient never took the medication."


def candidate_years(case: CaseInput) -> list[str]:
    years = {m for doc in case.documents for m in _YEAR_RE.findall(doc.text)}
    years.add(str(case.as_of_date.year))
    return sorted(years)


def _date_part_questions(
    prefix: str, event: str, drug: str, years: Sequence[str]
) -> dict[str, Choice]:
    who = f"the patient (not a relative or other person) {event} taking {drug}"
    return {
        f"{prefix}_month": Choice(
            instructions=(
                f"In which month did {who}? Answer 'none' if the documents do not state the month."
            ),
            criteria={m: None for m in MONTHS} | {"none": _ABSENT},
        ),
        f"{prefix}_day": Choice(
            instructions=(
                f"On which day of the month (1-31) did {who}? Answer 'none' if the day is not "
                "stated, for example when only a month is given."
            ),
            criteria={str(d): None for d in range(1, 32)} | {"none": _ABSENT},
        ),
        f"{prefix}_year": Choice(
            instructions=(
                f"In which year did {who}? Answer 'none' if no year is stated for this event."
            ),
            criteria={y: None for y in years} | {"none": _ABSENT},
        ),
    }


def validate_question_set_version(version: str) -> None:
    if version not in QUESTION_SET_VERSIONS:
        raise ValueError(f"unknown question set {version!r}; known: {list(QUESTION_SET_VERSIONS)}")


def _documentation_complete_true(drug: str, version: str) -> str:
    text = (
        "The insurance member ID, a clinician note supporting the diagnosis, and the patient's "
        f"treatment history (including whether and when {drug} was taken) are all present"
    )
    if version == Q_V0_2:
        text += f" (a statement that the patient never took {drug} counts as treatment history)"
    return text + "."


def _treatment_history_option(drug: str, version: str) -> str:
    if version == Q_V0_2:
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
    questions |= _date_part_questions("mtx_start", "start", drug, years)
    questions["mtx_end_status"] = Choice(
        instructions=(
            f"What is the status of the patient's own {drug} treatment (not a relative's)?"
        ),
        criteria={
            "ended": f"The documents say the patient stopped taking {drug}.",
            "ongoing": f"The documents say the patient is still taking {drug}.",
            "not_stated": f"The documents do not say, or the patient never took {drug}.",
        },
    )
    questions |= _date_part_questions("mtx_end", "stop", drug, years)
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
    return questions


def question_set_hash(
    policy: AuthorizationPolicy, version: str = DEFAULT_QUESTION_SET_VERSION
) -> str:
    questions = build_questions(policy, [_YEAR_PLACEHOLDER], version)
    payload = {qid: q.model_dump(mode="json") for qid, q in questions.items()}
    blob = json.dumps({"version": version, "questions": payload}, sort_keys=True)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()
