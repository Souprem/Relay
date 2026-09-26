import re
from datetime import date
from random import Random

from relay.generation.dates import MONTH_NAMES
from relay.generation.facts import DIFFICULTIES
from relay.generation.render import (
    FILLER_SENTENCES,
    INJECTION_LINES,
    MEMBER_ID_MISSING,
    NEVER_TAKEN,
    RELATIVES,
    SYNTHETIC_PREFIX,
    UNDOCUMENTED,
    render_documents,
)
from relay.generation.scenarios import sample_facts
from tests.factories import make_facts

NOT_TAKEN = {"mtx_start": None, "mtx_end": None, "start_precision": None, "end_precision": None}
FOUR_DIGITS = re.compile(r"\b\d{4}\b")
MONTH_THEN_DAY = re.compile(r"\b(" + "|".join(MONTH_NAMES) + r")\s+\d{1,2}(?!\d)")


def docs(facts, seed=0):
    return {d.id: d for d in render_documents(facts, Random(seed))}


def note(facts, seed=0):
    return docs(facts, seed)["physician_note"].text


def treatment_paragraph(text):
    # Paragraphs: header + opening, [family history], treatment, plan.
    paragraphs = text.split("\n\n")
    return paragraphs[-2]


def test_every_document_is_marked_synthetic_and_note_is_last():
    for seed in range(400):
        rng = Random(seed)
        facts = sample_facts(rng, case_id="R", difficulty=DIFFICULTIES[seed % 4])
        documents = render_documents(facts, rng)
        assert all(d.text.startswith(SYNTHETIC_PREFIX) for d in documents)
        assert all(d.text.endswith("\n") for d in documents)
        assert documents[-1].id == "physician_note"
        assert len({d.id for d in documents}) == len(documents)


def test_rendering_is_deterministic_for_a_random_state():
    facts = make_facts(noise=0.7, relative_distractor=True, medication_history=True)
    assert render_documents(facts, Random(3)) == render_documents(facts, Random(3))


def test_clean_case_has_only_a_physician_note_with_both_dates():
    documents = docs(make_facts())
    assert list(documents) == ["physician_note"]
    text = documents["physician_note"].text
    assert "2026-01-12" in text or "January 12, 2026" in text
    assert "2026-06-01" in text or "June 1, 2026" in text
    assert "rheumatoid arthritis" in text
    assert "Immunara" in text


def test_injection_case_fax_cover_contains_an_injection_line():
    cover = docs(make_facts(injection=True))["fax_cover"].text
    assert any(line in cover for line in INJECTION_LINES)
    assert "Member ID: EXH-100001" in cover


def test_missing_member_id_gets_a_fax_cover_saying_so():
    cover = docs(make_facts(member_id=None))["fax_cover"].text
    assert f"Member ID: {MEMBER_ID_MISSING}" in cover
    assert not any(line in cover for line in INJECTION_LINES)


def test_relative_distractor_note_mentions_the_relative():
    text = note(make_facts(relative_distractor=True))
    assert "Family history" in text
    assert any(relative in text for relative in RELATIVES)


def test_no_year_dates_render_without_a_year():
    for seed in range(30):
        facts = make_facts(start_precision="no_year", end_precision="no_year")
        paragraph = treatment_paragraph(note(facts, seed))
        assert FOUR_DIGITS.search(paragraph) is None, paragraph
        assert "January" in paragraph and "June" in paragraph


def test_month_precision_dates_have_no_day_number():
    for seed in range(30):
        facts = make_facts(start_precision="month", end_precision="month")
        paragraph = treatment_paragraph(note(facts, seed))
        assert MONTH_THEN_DAY.search(paragraph) is None, paragraph
        assert "2026-01-12" not in paragraph and "2026" in paragraph


def test_split_documents_put_start_in_history_and_stop_in_note():
    documents = docs(make_facts(split_across_documents=True, medication_history=True))
    history = documents["medication_history"].text
    paragraph = treatment_paragraph(documents["physician_note"].text)
    assert "start 2026-01-12" in history or "start January 12, 2026" in history
    assert "end: see most recent clinic note" in history
    assert "2026-06-01" in paragraph or "June 1, 2026" in paragraph
    assert "2026-01-12" not in paragraph and "January 12, 2026" not in paragraph


def test_ongoing_treatment_is_rendered_as_continuing():
    documents = docs(make_facts(mtx_end=None, end_precision=None, medication_history=True))
    assert "status: active" in documents["medication_history"].text
    assert (
        "continue" in documents["physician_note"].text
        or "remains on" in documents["physician_note"].text
    )


def test_history_vs_note_contradiction_uses_the_never_taken_bank():
    facts = make_facts(contradiction="history_vs_note", medication_history=True)
    for seed in range(20):
        documents = docs(facts, seed)
        assert "METHOTREXATE" in documents["medication_history"].text
        paragraph = treatment_paragraph(documents["physician_note"].text)
        filled = {t.format(mtx=m) for t in NEVER_TAKEN for m in ("methotrexate", "MTX")}
        assert paragraph in filled, paragraph


def test_history_vs_note_contradiction_keeps_the_co_dmard():
    facts = make_facts(
        contradiction="history_vs_note",
        medication_history=True,
        other_dmards=("leflunomide 20 mg daily",),
    )
    paragraph = treatment_paragraph(note(facts))
    assert "leflunomide" in paragraph and "has not taken" in paragraph


def test_dates_conflict_history_starts_earlier_with_the_same_stop():
    facts = make_facts(
        contradiction="dates_conflict",
        medication_history=True,
        mtx_start=date(2026, 4, 6),
        history_start=date(2026, 2, 9),
    )
    documents = docs(facts)
    history = documents["medication_history"].text
    paragraph = treatment_paragraph(documents["physician_note"].text)
    assert "start 2026-02-09" in history or "start February 9, 2026" in history
    assert "2026-04-06" in paragraph or "April 6, 2026" in paragraph
    assert "2026-06-01" in history or "June 1, 2026" in history
    assert "2026-06-01" in paragraph or "June 1, 2026" in paragraph


def test_older_note_plans_methotrexate_under_a_neutral_id():
    documents = docs(make_facts(stale_note=True, stale_note_date=date(2025, 12, 1)))
    assert list(documents) == ["clinic_note", "physician_note"]
    stale = documents["clinic_note"]
    assert stale.kind == "physician_note"
    assert "2025-12-01" in stale.text.splitlines()[0]
    assert "start methotrexate" in stale.text


def test_undocumented_history_has_no_medication_list():
    facts = make_facts(mtx_status="undocumented", mtx_outcome="not_stated", **NOT_TAKEN)
    documents = docs(facts)
    assert "medication_history" not in documents
    assert any(s in documents["physician_note"].text for s in UNDOCUMENTED)


def test_other_dmard_instead_of_methotrexate():
    facts = make_facts(
        mtx_status="never",
        mtx_outcome="not_stated",
        other_dmards=("hydroxychloroquine 200 mg twice daily",),
        medication_history=True,
        **NOT_TAKEN,
    )
    documents = docs(facts)
    assert "has not taken" in documents["physician_note"].text
    assert "hydroxychloroquine" in documents["physician_note"].text
    assert "METHOTREXATE" not in documents["medication_history"].text
    assert "HYDROXYCHLOROQUINE" in documents["medication_history"].text


def test_noise_controls_filler_and_abbreviation():
    quiet = note(make_facts(noise=0.0))
    assert not any(s in quiet for s in FILLER_SENTENCES)
    assert "MTX" not in quiet
    loud = note(make_facts(noise=1.0))
    assert any(s in loud for s in FILLER_SENTENCES)
    abbreviated = [note(make_facts(noise=1.0), seed) for seed in range(40)]
    assert any("MTX" in text for text in abbreviated)
