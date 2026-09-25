"""Gold-set data and checks for gold-v0.1 (Phase 2E). Evaluation-only: relay/ never imports this.

INTENDED is the machine-readable copy of the per-id scenario table in
evals/gold/AUTHORING_GUIDE.md section 7. test_gold_dataset.py keeps the two identical.
"""

import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import NamedTuple

from relay.cases.loader import CaseLoadError, load_case, load_dataset
from relay.cases.models import (
    CaseInput,
    Document,
    GroundTruth,
    Insurance,
    MedicationRequest,
    MissingEvidence,
    Patient,
    PriorAuthCase,
)
from relay.cases.policies import load_policy
from relay.evaluation.labels import expected_action
from relay.workflow.thresholds import THRESHOLDS_V0_1

REPO = Path(__file__).resolve().parents[1]
GOLD_DIR = REPO / "evals" / "gold"
GUIDE_PATH = GOLD_DIR / "AUTHORING_GUIDE.md"
DATASET_ID = "gold-v0.1"
POLICY_ID = "immunara-v0.1"
CATEGORIES: tuple[str, ...] = ("STR", "MIS", "CON", "TMP", "TRK")
STYLES: tuple[str, ...] = ("SOAP", "LTR", "BUL", "NAR")
FACTS: tuple[str, ...] = (
    "diagnosis_supported",
    "step_therapy_satisfied",
    "documentation_complete",
    "contradiction_present",
    "missing_evidence",
)
ALLOWED_MISSING: tuple[str, ...] = (
    "DIAGNOSIS",
    "TREATMENT_HISTORY",
    "INSURANCE_INFORMATION",
    "NONE",
)
ALL_IDS: tuple[str, ...] = tuple(f"GOLD-{c}-{i:02d}" for c in CATEGORIES for i in range(1, 21))
CASE_ID_RE = re.compile(r"^GOLD-(STR|MIS|CON|TMP|TRK)-(0[1-9]|1[0-9]|20)$")
SYNTHETIC_PREFIX = "SYNTHETIC RECORD - "
RULES_BEGIN = "<!-- RULES:BEGIN -->"
RULES_END = "<!-- RULES:END -->"
TOP_LEVEL_FILES = frozenset(
    {"AUTHORING_GUIDE.md", "README.md", "ADJUDICATION.md", "second_pass.json", "agreement.json"}
)
AS_OF_MIN, AS_OF_MAX = date(2026, 6, 1), date(2026, 12, 15)
AGE_MIN, AGE_MAX = 19, 85
PLANS: dict[str, tuple[str, str]] = {
    "ExampleHealth": ("ExampleHealth Gold", "EXH"),
    "Northstar": ("Northstar Choice", "NSC"),
    "CivicCare": ("CivicCare Plus", "CCP"),
}
DOCUMENT_ID_RE = re.compile(
    r"^(physician_note|clinic_note|progress_note|consult_note|referral_letter|problem_list"
    r"|medication_history|outside_records|pharmacy_fills|lab_report|fax_cover|insurance_card"
    r"|intake_form)(_[23])?$"
)
# Checked case-insensitively in every document: label leaks and evaluation vocabulary.
FORBIDDEN_ANY_CASE: tuple[str, ...] = (
    "ground_truth",
    "ground truth",
    "expected_action",
    "expected action",
    "stale",
    "distractor",
    "contradict",
    "inconsisten",
    "discrepan",
    "adjudicat",
    "second pass",
    "scenario",
    "label",
    "step therapy",
    "step-therapy",
    "documentation complete",
    "missing evidence",
    "missing_evidence",
    "auto_process",
    "request_info",
    "human_review",
)
# Checked case-sensitively: case ids and the dataset id ("ExampleHealth Gold" stays allowed).
FORBIDDEN_EXACT_CASE: tuple[str, ...] = ("GOLD-", "gold-v0")
US_FORMAT_NOTE = "MM/DD/YYYY"
MONTHS = "(?:January|February|March|April|May|June|July|August|September|October|November|December)"
DATE_PATTERNS: dict[str, re.Pattern[str]] = {
    "iso": re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    "us": re.compile(r"\b\d{2}/\d{2}/\d{4}\b"),
    "long": re.compile(rf"\b{MONTHS} \d{{1,2}}, \d{{4}}\b"),
    "month_only": re.compile(rf"\b{MONTHS} \d{{4}}\b"),
    "relative": re.compile(
        rf"\b(?:weeks?|months?) (?:ago|before|prior to|earlier)\b|\bthis {MONTHS}\b|\blast month\b",
        re.IGNORECASE,
    ),
}
SOAP_HEADINGS: tuple[str, ...] = ("Subjective:", "Objective:", "Assessment:", "Plan:")
LETTER_CLOSINGS: tuple[str, ...] = ("Sincerely,", "Kind regards,", "With regards,", "Best regards,")
CATEGORY_KIND_FLOORS: dict[str, int] = {
    "medication_history": 4,
    "fax_cover": 2,
    "lab_report": 2,
    "insurance_card": 1,
}
CATEGORY_DATE_FLOORS: dict[str, int] = {"iso": 5, "long": 3, "month_only": 2}
SET_KIND_FLOORS: dict[str, int] = {"physician_note": 100} | {
    kind: 5 * n for kind, n in CATEGORY_KIND_FLOORS.items()
}
SET_DATE_FLOORS: dict[str, int] = {fmt: 5 * n for fmt, n in CATEGORY_DATE_FLOORS.items()} | {
    "us": 4,
    "relative": 3,
}
MAX_CASES_PER_SENTENCE = 2
SENTENCE_END = re.compile(r"[.!?](?=\s+[A-Z(]|\s*$)")


class Intended(NamedTuple):
    style: str
    dx: bool  # diagnosis_supported
    st: bool  # step_therapy_satisfied
    dc: bool  # documentation_complete
    con: bool  # contradiction_present
    missing: str  # missing_evidence
    action: str  # derived by the engine; stored only as a cross-check


T, F = True, False
AUTO, INFO, REVIEW = "AUTO_PROCESS", "REQUEST_INFO", "HUMAN_REVIEW"
NONE, DX, TH, INS = "NONE", "DIAGNOSIS", "TREATMENT_HISTORY", "INSURANCE_INFORMATION"

# fmt: off
INTENDED: dict[str, Intended] = {
    "GOLD-STR-01": Intended("SOAP", T, T, T, F, NONE, AUTO),
    "GOLD-STR-02": Intended("LTR", T, T, T, F, NONE, AUTO),
    "GOLD-STR-03": Intended("BUL", T, T, T, F, NONE, AUTO),
    "GOLD-STR-04": Intended("NAR", T, T, T, F, NONE, AUTO),
    "GOLD-STR-05": Intended("SOAP", T, T, T, F, NONE, AUTO),
    "GOLD-STR-06": Intended("NAR", T, T, T, F, NONE, AUTO),
    "GOLD-STR-07": Intended("LTR", T, T, T, F, NONE, AUTO),
    "GOLD-STR-08": Intended("BUL", T, T, T, F, NONE, AUTO),
    "GOLD-STR-09": Intended("SOAP", T, T, T, F, NONE, AUTO),
    "GOLD-STR-10": Intended("NAR", T, T, T, F, NONE, AUTO),
    "GOLD-STR-11": Intended("BUL", T, T, F, F, INS, INFO),
    "GOLD-STR-12": Intended("SOAP", T, T, F, F, INS, INFO),
    "GOLD-STR-13": Intended("LTR", T, T, F, F, INS, INFO),
    "GOLD-STR-14": Intended("NAR", T, F, F, F, INS, INFO),
    "GOLD-STR-15": Intended("NAR", T, F, F, F, TH, INFO),
    "GOLD-STR-16": Intended("LTR", T, F, F, F, TH, INFO),
    "GOLD-STR-17": Intended("SOAP", T, F, F, F, TH, INFO),
    "GOLD-STR-18": Intended("BUL", F, F, F, F, DX, INFO),
    "GOLD-STR-19": Intended("LTR", F, T, F, F, DX, INFO),
    "GOLD-STR-20": Intended("BUL", F, F, F, F, DX, INFO),
    "GOLD-MIS-01": Intended("NAR", F, F, F, F, DX, INFO),
    "GOLD-MIS-02": Intended("SOAP", F, F, F, F, DX, INFO),
    "GOLD-MIS-03": Intended("BUL", F, F, F, F, DX, INFO),
    "GOLD-MIS-04": Intended("LTR", F, T, F, F, DX, INFO),
    "GOLD-MIS-05": Intended("NAR", T, F, F, F, TH, INFO),
    "GOLD-MIS-06": Intended("BUL", T, F, F, F, TH, INFO),
    "GOLD-MIS-07": Intended("SOAP", T, F, F, F, TH, INFO),
    "GOLD-MIS-08": Intended("LTR", T, F, F, F, TH, INFO),
    "GOLD-MIS-09": Intended("SOAP", T, F, F, F, TH, INFO),
    "GOLD-MIS-10": Intended("NAR", T, T, F, F, INS, INFO),
    "GOLD-MIS-11": Intended("BUL", T, T, F, F, INS, INFO),
    "GOLD-MIS-12": Intended("LTR", T, T, F, F, INS, INFO),
    "GOLD-MIS-13": Intended("SOAP", T, T, F, F, INS, INFO),
    "GOLD-MIS-14": Intended("NAR", T, F, F, F, INS, INFO),
    "GOLD-MIS-15": Intended("BUL", T, F, F, F, TH, INFO),
    "GOLD-MIS-16": Intended("LTR", F, T, F, F, DX, INFO),
    "GOLD-MIS-17": Intended("NAR", T, T, T, F, NONE, AUTO),
    "GOLD-MIS-18": Intended("SOAP", T, T, T, F, NONE, AUTO),
    "GOLD-MIS-19": Intended("BUL", T, T, T, F, NONE, AUTO),
    "GOLD-MIS-20": Intended("LTR", T, F, T, F, NONE, REVIEW),
    "GOLD-CON-01": Intended("NAR", T, F, T, T, NONE, REVIEW),
    "GOLD-CON-02": Intended("LTR", T, F, T, T, NONE, REVIEW),
    "GOLD-CON-03": Intended("SOAP", T, F, T, T, NONE, REVIEW),
    "GOLD-CON-04": Intended("LTR", T, F, T, T, NONE, REVIEW),
    "GOLD-CON-05": Intended("BUL", F, T, T, T, NONE, REVIEW),
    "GOLD-CON-06": Intended("SOAP", T, F, T, T, NONE, REVIEW),
    "GOLD-CON-07": Intended("NAR", T, F, T, T, NONE, REVIEW),
    "GOLD-CON-08": Intended("BUL", T, F, T, T, NONE, REVIEW),
    "GOLD-CON-09": Intended("LTR", F, F, T, T, NONE, REVIEW),
    "GOLD-CON-10": Intended("SOAP", T, F, T, T, NONE, REVIEW),
    "GOLD-CON-11": Intended("NAR", T, F, T, T, NONE, REVIEW),
    "GOLD-CON-12": Intended("BUL", T, F, F, T, INS, REVIEW),
    "GOLD-CON-13": Intended("SOAP", T, F, T, T, NONE, REVIEW),
    "GOLD-CON-14": Intended("LTR", T, F, T, T, NONE, REVIEW),
    "GOLD-CON-15": Intended("SOAP", T, T, T, F, NONE, AUTO),
    "GOLD-CON-16": Intended("NAR", T, T, T, F, NONE, AUTO),
    "GOLD-CON-17": Intended("BUL", T, T, F, F, INS, INFO),
    "GOLD-CON-18": Intended("LTR", T, T, T, F, NONE, AUTO),
    "GOLD-CON-19": Intended("BUL", T, F, T, F, NONE, REVIEW),
    "GOLD-CON-20": Intended("NAR", T, T, T, F, NONE, AUTO),
    "GOLD-TMP-01": Intended("SOAP", T, T, T, F, NONE, AUTO),
    "GOLD-TMP-02": Intended("NAR", T, F, T, F, NONE, REVIEW),
    "GOLD-TMP-03": Intended("LTR", T, T, T, F, NONE, AUTO),
    "GOLD-TMP-04": Intended("BUL", T, F, T, F, NONE, REVIEW),
    "GOLD-TMP-05": Intended("SOAP", T, F, T, F, NONE, REVIEW),
    "GOLD-TMP-06": Intended("NAR", T, T, T, F, NONE, AUTO),
    "GOLD-TMP-07": Intended("BUL", T, F, T, F, NONE, REVIEW),
    "GOLD-TMP-08": Intended("LTR", T, T, T, F, NONE, AUTO),
    "GOLD-TMP-09": Intended("SOAP", T, F, T, F, NONE, REVIEW),
    "GOLD-TMP-10": Intended("BUL", T, T, T, F, NONE, AUTO),
    "GOLD-TMP-11": Intended("NAR", T, F, T, F, NONE, REVIEW),
    "GOLD-TMP-12": Intended("LTR", T, T, T, F, NONE, AUTO),
    "GOLD-TMP-13": Intended("SOAP", T, F, T, F, NONE, REVIEW),
    "GOLD-TMP-14": Intended("NAR", T, T, T, F, NONE, AUTO),
    "GOLD-TMP-15": Intended("BUL", T, T, T, F, NONE, AUTO),
    "GOLD-TMP-16": Intended("LTR", T, F, F, F, TH, INFO),
    "GOLD-TMP-17": Intended("SOAP", T, F, T, F, NONE, REVIEW),
    "GOLD-TMP-18": Intended("NAR", T, T, T, F, NONE, AUTO),
    "GOLD-TMP-19": Intended("BUL", T, T, T, F, NONE, AUTO),
    "GOLD-TMP-20": Intended("LTR", T, T, T, F, NONE, AUTO),
    "GOLD-TRK-01": Intended("NAR", T, F, T, F, NONE, REVIEW),
    "GOLD-TRK-02": Intended("LTR", T, F, F, F, TH, INFO),
    "GOLD-TRK-03": Intended("SOAP", T, T, T, F, NONE, AUTO),
    "GOLD-TRK-04": Intended("BUL", T, F, T, F, NONE, REVIEW),
    "GOLD-TRK-05": Intended("SOAP", T, F, F, F, TH, INFO),
    "GOLD-TRK-06": Intended("NAR", T, T, T, F, NONE, AUTO),
    "GOLD-TRK-07": Intended("LTR", T, T, T, F, NONE, AUTO),
    "GOLD-TRK-08": Intended("BUL", T, F, T, F, NONE, REVIEW),
    "GOLD-TRK-09": Intended("SOAP", T, F, T, F, NONE, REVIEW),
    "GOLD-TRK-10": Intended("NAR", T, F, T, F, NONE, REVIEW),
    "GOLD-TRK-11": Intended("LTR", T, T, T, F, NONE, AUTO),
    "GOLD-TRK-12": Intended("BUL", T, T, T, F, NONE, REVIEW),
    "GOLD-TRK-13": Intended("SOAP", T, T, T, F, NONE, REVIEW),
    "GOLD-TRK-14": Intended("BUL", T, T, T, F, NONE, AUTO),
    "GOLD-TRK-15": Intended("NAR", T, T, F, F, INS, INFO),
    "GOLD-TRK-16": Intended("LTR", T, T, T, F, NONE, AUTO),
    "GOLD-TRK-17": Intended("SOAP", F, F, F, F, DX, INFO),
    "GOLD-TRK-18": Intended("NAR", F, T, F, F, DX, INFO),
    "GOLD-TRK-19": Intended("BUL", T, F, F, F, TH, INFO),
    "GOLD-TRK-20": Intended("LTR", T, F, T, F, NONE, REVIEW),
}
# fmt: on

FIXED_AGE: dict[str, int] = {"GOLD-TRK-11": 18, "GOLD-TRK-12": 17, "GOLD-TRK-13": 17}
FIXED_AS_OF: dict[str, date] = {
    "GOLD-TMP-08": date(2026, 9, 7),
    "GOLD-TMP-09": date(2026, 9, 28),
    "GOLD-TMP-12": date(2026, 9, 10),
    "GOLD-TMP-13": date(2026, 8, 14),
    "GOLD-TMP-15": date(2026, 9, 10),
}
# case.json insurance.member_id is null exactly for these: every INSURANCE_INFORMATION case, two
# precedence cases whose member ID is also missing, and MIS-17 (the ID is only on the card).
MEMBER_ID_NULL: frozenset[str] = frozenset(
    {case_id for case_id, row in INTENDED.items() if row.missing == INS}
    | {"GOLD-MIS-02", "GOLD-MIS-07", "GOLD-MIS-17"}
)
US_DATE_IDS: frozenset[str] = frozenset(
    {"GOLD-STR-05", "GOLD-CON-11", "GOLD-TMP-10", "GOLD-TMP-11"}
)
RELATIVE_DATE_IDS: frozenset[str] = frozenset({"GOLD-TMP-12", "GOLD-TMP-13", "GOLD-TMP-15"})


def present_case_dirs() -> list[Path]:
    if not GOLD_DIR.is_dir():
        return []
    return sorted(p for p in GOLD_DIR.iterdir() if p.is_dir() and CASE_ID_RE.match(p.name))


def stray_entries() -> list[str]:
    if not GOLD_DIR.is_dir():
        return ["evals/gold does not exist"]
    out: list[str] = []
    for path in sorted(GOLD_DIR.iterdir()):
        if path.name.startswith("."):
            continue
        if path.is_dir() and not CASE_ID_RE.match(path.name):
            out.append(path.name + "/")
        elif path.is_file() and path.name not in TOP_LEVEL_FILES:
            out.append(path.name)
    return out


def rules_section(guide_text: str) -> str:
    start = guide_text.index(RULES_BEGIN) + len(RULES_BEGIN)
    return guide_text[start : guide_text.index(RULES_END)].strip()


def parse_guide_table(guide_text: str) -> dict[str, Intended]:
    flag = {"T": True, "F": False}
    rows: dict[str, Intended] = {}
    for line in guide_text.splitlines():
        if not line.startswith("| GOLD-"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        case_id, style, _scenario, dx, st, dc, con, missing, action = cells
        rows[case_id] = Intended(style, flag[dx], flag[st], flag[dc], flag[con], missing, action)
    return rows


def derive_action(case_input: CaseInput, truth: GroundTruth) -> str:
    case = PriorAuthCase(input=case_input, ground_truth=truth)
    return expected_action(case, load_policy(POLICY_ID), THRESHOLDS_V0_1).value


def intended_truth(case_id: str) -> GroundTruth:
    row = INTENDED[case_id]
    return GroundTruth(
        diagnosis_supported=row.dx,
        step_therapy_satisfied=row.st,
        documentation_complete=row.dc,
        contradiction_present=row.con,
        missing_evidence=MissingEvidence(row.missing),
    )


def table_action(case_id: str) -> str:
    """The engine's action for the table's facts (age is the only structured field it reads)."""
    stub = CaseInput(
        id=case_id,
        dataset_id=DATASET_ID,
        as_of_date=date(2026, 9, 15),
        patient=Patient(age=FIXED_AGE.get(case_id, 40), state="MA"),
        medication=MedicationRequest(name="Immunara", indication="rheumatoid arthritis"),
        insurance=Insurance(payer="ExampleHealth", plan="ExampleHealth Gold", member_id=None),
        documents=(Document(id="physician_note", kind="physician_note", text=SYNTHETIC_PREFIX),),
        policy_id=POLICY_ID,
    )
    return derive_action(stub, intended_truth(case_id))


def note_style(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    if all(any(line.startswith(h) for line in lines) for h in SOAP_HEADINGS):
        return "SOAP"
    if any(line.startswith("Dear ") for line in lines) and any(
        line.startswith(LETTER_CLOSINGS) for line in lines
    ):
        return "LTR"
    if sum(line.startswith("- ") for line in lines) >= 3:
        return "BUL"
    return "NAR"


def case_styles(case: PriorAuthCase) -> set[str]:
    return {note_style(d.text) for d in case.input.documents if d.kind == "physician_note"}


def date_formats(case: PriorAuthCase) -> set[str]:
    text = "\n".join(d.text for d in case.input.documents)
    return {name for name, pattern in DATE_PATTERNS.items() if pattern.search(text)}


def _long_sentences(text: str) -> set[str]:
    body = text.split("\n", 1)[1] if "\n" in text else ""
    out: set[str] = set()
    for piece in re.split(r"(?<=[.!?])\s+|\n+", body):
        words = re.findall(r"[a-z0-9]+", piece.lower())
        if len(words) >= 8:
            out.add(" ".join(words))
    return out


def repeated_sentences(cases: Iterable[PriorAuthCase]) -> list[str]:
    """Sentences of 8+ words (header lines excluded) used in more than two cases."""
    seen: dict[str, set[str]] = {}
    for case in cases:
        for doc in case.input.documents:
            for sentence in _long_sentences(doc.text):
                seen.setdefault(sentence, set()).add(case.input.id)
    return [
        f"sentence reused in {len(ids)} cases ({', '.join(sorted(ids)[:5])}): {sentence[:90]!r}"
        for sentence, ids in sorted(seen.items())
        if len(ids) > MAX_CASES_PER_SENTENCE
    ]


def _notes_problems(case_id: str, notes: str) -> list[str]:
    problems: list[str] = []
    if not notes.strip():
        problems.append("notes are empty")
    if len(SENTENCE_END.findall(notes.strip())) > 3:
        problems.append("notes have more than 3 sentences")
    if len(notes) > 600:
        problems.append(f"notes are {len(notes)} characters, limit 600")
    if case_id == "GOLD-TMP-16":
        if "year" not in notes.lower():
            problems.append("notes must say why the year cannot be recovered")
    elif case_id.startswith("GOLD-TMP-") and not re.search(r"\b\d+ days\b", notes):
        problems.append("TMP notes must show the day arithmetic (for example '= 84 days')")
    return problems


def case_problems(case_dir: Path) -> list[str]:
    case_id = case_dir.name
    if case_id not in INTENDED:
        return [f"{case_id}: not an id in the scenario table"]
    try:
        case = load_case(case_dir)
    except CaseLoadError as error:
        return [f"{case_id}: does not load: {error}"]
    raw = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    row = INTENDED[case_id]
    inp, truth = case.input, case.ground_truth
    problems: list[str] = []

    listed = {f"documents/{meta['file']}" for meta in raw["documents"]}
    on_disk = {
        p.relative_to(case_dir).as_posix()
        for p in case_dir.rglob("*")
        if p.is_file() and not p.name.startswith(".")
    }
    extra = sorted(on_disk - listed - {"case.json", "ground_truth.json"})
    if extra:
        problems.append(f"files not listed in case.json: {extra}")
    for meta in raw["documents"]:
        if meta["file"] != f"{meta['id']}.txt":
            problems.append(f"document {meta['id']!r} must be stored as {meta['id']}.txt")

    if inp.dataset_id != DATASET_ID:
        problems.append(f"dataset_id {inp.dataset_id!r}, expected {DATASET_ID!r}")
    if inp.policy_id != POLICY_ID:
        problems.append(f"policy_id {inp.policy_id!r}, expected {POLICY_ID!r}")
    if (inp.medication.name, inp.medication.indication) != ("Immunara", "rheumatoid arthritis"):
        problems.append("medication must be Immunara for rheumatoid arthritis")
    want_as_of = FIXED_AS_OF.get(case_id)
    if want_as_of is not None and inp.as_of_date != want_as_of:
        problems.append(f"as_of_date {inp.as_of_date}, the table fixes {want_as_of}")
    if want_as_of is None and not AS_OF_MIN <= inp.as_of_date <= AS_OF_MAX:
        problems.append(f"as_of_date {inp.as_of_date} outside {AS_OF_MIN}..{AS_OF_MAX}")
    want_age = FIXED_AGE.get(case_id)
    if want_age is not None and inp.patient.age != want_age:
        problems.append(f"age {inp.patient.age}, the table fixes {want_age}")
    if want_age is None and not AGE_MIN <= inp.patient.age <= AGE_MAX:
        problems.append(f"age {inp.patient.age} outside {AGE_MIN}..{AGE_MAX}")
    plan = PLANS.get(inp.insurance.payer)
    if plan is None or inp.insurance.plan != plan[0]:
        problems.append(f"payer/plan must be one of {sorted(PLANS)} with its plan name")
    member = inp.insurance.member_id
    if case_id in MEMBER_ID_NULL and member is not None:
        problems.append("insurance.member_id must be null for this case")
    if case_id not in MEMBER_ID_NULL:
        if member is None:
            problems.append("insurance.member_id must be set for this case")
        elif plan is not None and not re.fullmatch(rf"{plan[1]}-\d{{6}}", member):
            problems.append(f"member_id {member!r} must look like {plan[1]}-123456")

    ids = [d.id for d in inp.documents]
    if len(ids) != len(set(ids)):
        problems.append(f"duplicate document ids {ids}")
    if not any(d.kind == "physician_note" for d in inp.documents):
        problems.append("no physician_note-kind document")
    for doc in inp.documents:
        if not DOCUMENT_ID_RE.match(doc.id):
            problems.append(f"document id {doc.id!r} is not in the guide's vocabulary")
        if not doc.text.startswith(SYNTHETIC_PREFIX):
            problems.append(f"{doc.id} does not start with {SYNTHETIC_PREFIX!r}")
        lowered = doc.text.lower()
        problems += [
            f"{doc.id} contains forbidden text {term!r}"
            for term in FORBIDDEN_ANY_CASE
            if term in lowered
        ]
        problems += [
            f"{doc.id} contains forbidden text {term!r}"
            for term in FORBIDDEN_EXACT_CASE
            if term in doc.text
        ]
        if DATE_PATTERNS["us"].search(doc.text) and US_FORMAT_NOTE not in doc.text:
            problems.append(f"{doc.id} has a slash date but does not state {US_FORMAT_NOTE}")
    formats = date_formats(case)
    if case_id in US_DATE_IDS and "us" not in formats:
        problems.append("the table requires a US-format (MM/DD/YYYY) date")
    if case_id in RELATIVE_DATE_IDS and "relative" not in formats:
        problems.append("the table requires a relative date")

    got = (
        truth.diagnosis_supported,
        truth.step_therapy_satisfied,
        truth.documentation_complete,
        truth.contradiction_present,
        truth.missing_evidence.value,
    )
    want = (row.dx, row.st, row.dc, row.con, row.missing)
    if got != want:
        problems.append(f"ground truth {got} differs from the scenario table {want}")
    action = derive_action(inp, truth)
    if action != row.action:
        problems.append(f"derived action {action}, the table says {row.action}")
    styles = case_styles(case)
    if row.style not in styles:
        problems.append(f"no physician_note-kind document has style {row.style} ({sorted(styles)})")
    problems += _notes_problems(case_id, truth.notes)
    return [f"{case_id}: {p}" for p in problems]


def _floor_problems(
    cases: list[PriorAuthCase],
    kind_floors: Mapping[str, int],
    date_floors: Mapping[str, int],
    where: str,
) -> list[str]:
    kinds = Counter(kind for c in cases for kind in {d.kind for d in c.input.documents})
    formats = Counter(fmt for c in cases for fmt in date_formats(c))
    problems = [
        f"{where}: document kind {kind!r} in {kinds[kind]} cases, need at least {n}"
        for kind, n in kind_floors.items()
        if kinds[kind] < n
    ]
    problems += [
        f"{where}: {fmt} dates in {formats[fmt]} cases, need at least {n}"
        for fmt, n in date_floors.items()
        if formats[fmt] < n
    ]
    return problems


def category_problems(category: str) -> list[str]:
    expected = [f"GOLD-{category}-{i:02d}" for i in range(1, 21)]
    dirs = [d for d in present_case_dirs() if d.name.startswith(f"GOLD-{category}-")]
    problems: list[str] = []
    found = [d.name for d in dirs]
    if found != expected:
        missing = sorted(set(expected) - set(found))
        problems.append(f"GOLD-{category}: expected 20 case directories, missing {missing}")
    cases: list[PriorAuthCase] = []
    for case_dir in dirs:
        try:
            cases.append(load_case(case_dir))
        except CaseLoadError as error:
            problems.append(str(error))
    problems += _floor_problems(
        cases, CATEGORY_KIND_FLOORS, CATEGORY_DATE_FLOORS, f"GOLD-{category}"
    )
    actions = Counter(derive_action(c.input, c.ground_truth) for c in cases)
    if category == "STR" and actions != Counter({AUTO: 10, INFO: 10}):
        problems.append(f"GOLD-STR: derived actions {dict(actions)}, need 10 {AUTO} and 10 {INFO}")
    if category == "CON":
        n = sum(c.ground_truth.contradiction_present for c in cases)
        if n != 14:
            problems.append(f"GOLD-CON: {n} cases with contradiction_present, need exactly 14")
    if category == "MIS":
        n = sum(c.ground_truth.missing_evidence is MissingEvidence.NONE for c in cases)
        if n != 4:
            problems.append(f"GOLD-MIS: {n} 'present elsewhere' (NONE) cases, need exactly 4")
    problems += [f"GOLD-{category}: {p}" for p in repeated_sentences(cases)]
    return problems


def set_problems() -> list[str]:
    problems = [f"stray entry in evals/gold: {entry}" for entry in stray_entries()]
    found = tuple(d.name for d in present_case_dirs())
    if sorted(found) != sorted(ALL_IDS):  # directories sort alphabetically, ALL_IDS by category
        missing = sorted(set(ALL_IDS) - set(found))
        problems.append(f"expected the 100 table ids, found {len(found)}; missing {missing[:10]}")
    try:
        cases = load_dataset(GOLD_DIR)
    except CaseLoadError as error:
        return [*problems, f"load_dataset failed: {error}"]
    dataset_ids = {c.input.dataset_id for c in cases}
    if dataset_ids != {DATASET_ID}:
        problems.append(f"dataset ids {sorted(dataset_ids)}, expected only {DATASET_ID}")
    problems += _floor_problems(cases, SET_KIND_FLOORS, SET_DATE_FLOORS, "whole set")
    styles = Counter(style for c in cases for style in case_styles(c))
    problems += [
        f"whole set: style {style} in {styles[style]} cases, need at least 25"
        for style in STYLES
        if styles[style] < 25
    ]
    actions = Counter(derive_action(c.input, c.ground_truth) for c in cases)
    wanted = Counter(row.action for row in INTENDED.values())
    if actions != wanted:
        problems.append(f"whole set: derived actions {dict(actions)}, table {dict(wanted)}")
    problems += [f"whole set: {p}" for p in repeated_sentences(cases)]
    return problems


def _tf(flag: bool) -> str:
    return "T" if flag else "F"


def case_summary(case_dir: Path) -> str:
    row = INTENDED.get(case_dir.name)
    try:
        case = load_case(case_dir)
    except CaseLoadError:
        return f"{case_dir.name}  (does not load)"
    t = case.ground_truth
    action = derive_action(case.input, t)
    return (
        f"{case_dir.name}  action={action} (table {row.action if row else '?'})  "
        f"dx={_tf(t.diagnosis_supported)} st={_tf(t.step_therapy_satisfied)} "
        f"dc={_tf(t.documentation_complete)} con={_tf(t.contradiction_present)} "
        f"missing={t.missing_evidence.value}  styles={','.join(sorted(case_styles(case)))} "
        f"(table {row.style if row else '?'})"
    )
