"""Audit of RENDERED generated cases: label leaks and label/document consistency.

Generates 2,000 cases (all difficulties, the same draws as generate_case) and checks invariants
on the documents a decision provider would actually see, not only on the latent facts.
"""

import re
from dataclasses import dataclass
from datetime import date
from random import Random

import pytest

from relay.cases.models import Document, GroundTruth
from relay.generation.dates import MONTH_NAMES
from relay.generation.facts import DIFFICULTIES, CaseFacts
from relay.generation.generator import generate_case
from relay.generation.labels import MIN_DAYS, label_case
from relay.generation.render import NEVER_TAKEN, NEVER_TAKEN_OTHER_DMARD, render_documents
from relay.generation.scenarios import sample_facts

SEEDS = range(2000)
ALLOWED_DOCUMENT_IDS = frozenset(
    {"fax_cover", "medication_history", "clinic_note", "physician_note"}
)
FORBIDDEN_SUBSTRINGS = ("stale", "distractor", "contradiction", "ground", "label")

MONTH = "(?:" + "|".join(MONTH_NAMES) + ")"
DAY_DATE = re.compile(rf"\d{{4}}-\d{{2}}-\d{{2}}|{MONTH} \d{{1,2}}, \d{{4}}")
QUALIFIED_MONTH = re.compile(rf"\b(early|late) {MONTH}\b")
# A month name not followed by a day-and-year or a year: a yearless date.
YEARLESS_MONTH = re.compile(rf"\b{MONTH}\b(?! \d{{1,2}}, \d{{4}}| \d{{4}})")
# Text that may directly precede a qualified month, by which bound the date is.
START_CONTEXTS = ("started in ", "weekly in ", "since ", "start ")
END_CONTEXTS = ("stopped in ", "discontinued in ", "end ", "methotrexate in ", "MTX in ")


@dataclass(frozen=True)
class Rendered:
    seed: int
    facts: CaseFacts
    documents: dict[str, Document]
    truth: GroundTruth

    @property
    def note(self) -> str:
        return self.documents["physician_note"].text

    @property
    def treatment_paragraph(self) -> str:
        # Paragraphs: header + opening, [family history], treatment, plan.
        return self.note.split("\n\n")[-2]

    @property
    def history_mtx_line(self) -> str | None:
        history = self.documents.get("medication_history")
        if history is None:
            return None
        lines = [line for line in history.text.splitlines() if line.startswith("METHOTREXATE")]
        return lines[0] if lines else None


def render(seed: int) -> Rendered:
    """Exactly generate_case's draws: sample facts, then render with the same Random."""
    rng = Random(seed)
    facts = sample_facts(rng, case_id=f"GEN-{seed:08d}", difficulty=DIFFICULTIES[seed % 4])
    documents = render_documents(facts, rng)
    return Rendered(seed, facts, {d.id: d for d in documents}, label_case(facts))


@pytest.fixture(scope="module")
def rendered() -> list[Rendered]:
    return [render(seed) for seed in SEEDS]


def parse_day_date(text: str) -> date:
    if text[0].isdigit():
        return date.fromisoformat(text)
    month, day, year = text.replace(",", "").split()
    return date(int(year), MONTH_NAMES.index(month) + 1, int(day))


def template_pattern(template: str) -> re.Pattern[str]:
    """A regex matching any rendering of a template ({field} -> any text)."""
    parts = re.split(r"\{[a-zA-Z]+\}", template)
    return re.compile(".+?".join(re.escape(part) for part in parts))


def test_audit_draws_match_generate_case(rendered):
    for r in rendered[:40]:
        case = generate_case(r.seed, r.facts.difficulty)
        assert {d.id: d for d in case.input.documents} == r.documents
        assert case.ground_truth == r.truth


def test_document_ids_are_neutral(rendered):
    for r in rendered:
        assert set(r.documents) <= ALLOWED_DOCUMENT_IDS, (r.seed, list(r.documents))
        assert not any("stale" in doc_id for doc_id in r.documents), r.seed


def test_no_document_names_a_label_or_scenario(rendered):
    for r in rendered:
        for doc_id, document in r.documents.items():
            lowered = document.text.lower()
            for word in FORBIDDEN_SUBSTRINGS:
                assert word not in lowered, (r.seed, doc_id, word)


@pytest.mark.parametrize(
    ("bank_name", "bank"),
    [("NEVER_TAKEN", NEVER_TAKEN), ("NEVER_TAKEN_OTHER_DMARD", NEVER_TAKEN_OTHER_DMARD)],
)
def test_no_denial_phrase_predicts_a_contradiction(rendered, bank_name, bank):
    for template in bank:
        pattern = template_pattern(template)
        seen = {
            r.truth.contradiction_present for r in rendered if pattern.search(r.treatment_paragraph)
        }
        assert seen == {True, False}, (bank_name, template, seen)


def test_contradiction_notes_mention_the_co_dmard(rendered):
    cases = [
        r for r in rendered if r.facts.contradiction == "history_vs_note" and r.facts.other_dmards
    ]
    assert cases
    for r in cases:
        dmard_name = r.facts.other_dmards[0].split()[0]
        assert dmard_name in r.treatment_paragraph, r.seed


def test_no_around_qualifier_is_rendered(rendered):
    for r in rendered:
        for doc_id, document in r.documents.items():
            assert "around" not in document.text.lower(), (r.seed, doc_id)


def test_start_dates_are_never_early_and_end_dates_never_late(rendered):
    qualified = 0
    for r in rendered:
        for document in r.documents.values():
            for match in QUALIFIED_MONTH.finditer(document.text):
                before = document.text[: match.start()]
                is_start = before.endswith(START_CONTEXTS)
                is_end = before.endswith(END_CONTEXTS)
                assert is_start != is_end, (r.seed, before[-40:], match.group())
                expected = "late" if is_start else "early"
                assert match.group(1) == expected, (r.seed, before[-40:], match.group())
                qualified += 1
    assert qualified > 50


def test_dates_conflicts_are_decision_relevant(rendered):
    conflicts = [r for r in rendered if r.facts.contradiction == "dates_conflict"]
    assert len(conflicts) > 20
    for r in conflicts:
        assert r.truth.contradiction_present and not r.truth.step_therapy_satisfied
        note_dates = [parse_day_date(m) for m in DAY_DATE.findall(r.treatment_paragraph)]
        history_line = r.history_mtx_line
        assert history_line is not None, r.seed
        history_dates = [parse_day_date(m) for m in DAY_DATE.findall(history_line)]
        ongoing = r.facts.mtx_end is None
        assert len(note_dates) == len(history_dates) == (1 if ongoing else 2), r.seed
        note_end = r.facts.as_of_date if ongoing else note_dates[1]
        history_end = r.facts.as_of_date if ongoing else history_dates[1]
        assert note_end == history_end, r.seed
        assert (note_end - note_dates[0]).days < MIN_DAYS, r.seed
        assert (history_end - history_dates[0]).days >= MIN_DAYS, r.seed
        if r.facts.diagnosis_status == "established":
            # The diagnosis year is rendered; no documented start may precede it.
            assert str(r.facts.diagnosis_year) in r.note.splitlines()[1], r.seed
            assert r.facts.diagnosis_year <= history_dates[0].year, r.seed


def test_no_yearless_treatment_dates_are_rendered(rendered):
    for r in rendered:
        assert "no_year" not in (r.facts.start_precision, r.facts.end_precision), r.seed
        texts = [r.treatment_paragraph, r.history_mtx_line or ""]
        for text in texts:
            assert YEARLESS_MONTH.search(text) is None, (r.seed, text)


def test_ongoing_courses_are_noted_on_the_as_of_date(rendered):
    ongoing = [r for r in rendered if r.facts.mtx_status == "taken" and r.facts.mtx_end is None]
    assert ongoing
    for r in ongoing:
        header = r.note.splitlines()[0]
        assert header.endswith(r.facts.as_of_date.isoformat()), (r.seed, header)


def test_older_clinic_note_predates_every_rendered_start(rendered):
    older = [r for r in rendered if "clinic_note" in r.documents and r.facts.mtx_status == "taken"]
    assert older
    for r in older:
        older_date = date.fromisoformat(r.documents["clinic_note"].text.splitlines()[0][-10:])
        starts = [parse_day_date(m) for m in DAY_DATE.findall(r.history_mtx_line or "")]
        starts.append(r.facts.mtx_start)
        assert older_date < min(starts), r.seed
