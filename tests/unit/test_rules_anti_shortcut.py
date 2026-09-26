"""Anti-shortcut: the rules' contradiction output comes from explicit conflict cues only.

gen-v0.2 has a residual tell: a day-precision, non-split methotrexate line in the medication
history predicts a contradiction about 81% of the time (README, Limitations). A rule keyed on that
presentation would score well for the wrong reason. Each test here fixes the label-determining
facts and the physician note, swaps in medication-history documents that differ only in
presentation (day vs. month precision, split vs. non-split, ISO vs. long-form dates, template
draws), and checks that material_contradiction does not move.
"""

import asyncio
from dataclasses import replace
from datetime import date
from random import Random

import pytest

from relay.cases.models import CaseInput, Insurance, MedicationRequest, Patient
from relay.cases.policies import load_policy
from relay.decisions.base import DecisionId
from relay.decisions.date_parse import find_day_dates
from relay.decisions.rules_baseline import RulesBaselineProvider
from relay.generation.facts import DIFFICULTIES, CaseFacts
from relay.generation.generator import SEED_STRIDE, generate_case
from relay.generation.labels import label_case
from relay.generation.render import render_documents
from tests.factories import make_facts

POLICY = load_policy("immunara-v0.1")
SEEDS = range(8)
PROVIDER = RulesBaselineProvider()

# 2026-01-12 -> 2026-06-01 (140 days), inadequate response, medication history present.
ENDED = make_facts(medication_history=True)
# Ongoing: note_date == as_of_date, as the generator guarantees for ongoing courses.
ONGOING = make_facts(
    medication_history=True, mtx_end=None, end_precision=None, note_date=date(2026, 9, 15)
)
# dates_conflict: the note starts 2026-04-01 (61 days to 2026-06-01), the history 2026-01-12.
DATES_CONFLICT = replace(
    ENDED,
    contradiction="dates_conflict",
    mtx_start=date(2026, 4, 1),
    history_start=date(2026, 1, 12),
)


def build(facts: CaseFacts, seed: int) -> CaseInput:
    """What generate_case builds, but from hand-set facts and a fixed render seed."""
    return CaseInput(
        id=facts.case_id,
        dataset_id="anti-shortcut",
        as_of_date=facts.as_of_date,
        patient=Patient(age=facts.age, state=facts.state),
        medication=MedicationRequest(name=POLICY.medication, indication=POLICY.indication),
        insurance=Insurance(payer=facts.payer, plan=facts.plan, member_id=facts.member_id),
        documents=render_documents(facts, Random(seed)),
        policy_id=POLICY.id,
    )


def with_history_from(case: CaseInput, other: CaseInput) -> CaseInput:
    """`case` with its medication-history document replaced by `other`'s; all else unchanged."""
    [history] = [d for d in other.documents if d.kind == "medication_history"]
    documents = tuple(history if d.kind == "medication_history" else d for d in case.documents)
    return case.model_copy(update={"documents": documents})


def presentations(base: CaseFacts, precisions=("day", "month")) -> list[CaseFacts]:
    ended = base.mtx_end is not None
    return [
        replace(base, start_precision=start, end_precision=end, split_across_documents=split)
        for start in precisions
        for end in (precisions if ended else (None,))
        for split in (False, True)
    ]


def labels(facts: CaseFacts):
    return label_case(facts).model_copy(update={"notes": ""})


def contradiction(case: CaseInput) -> tuple[float, set[str]]:
    bundle = asyncio.run(PROVIDER.decide(case))
    rules = {r["rule"] for r in bundle.derivations["rules"]}
    return bundle.get(DecisionId.MATERIAL_CONTRADICTION).p_yes, rules


def has_tell(case: CaseInput) -> bool:
    """A non-split methotrexate medication-history line with a day-precision date."""
    return any(
        "METHOTREXATE" in line
        and "see most recent clinic note" not in line
        and find_day_dates(line)
        for d in case.documents
        if d.kind == "medication_history"
        for line in d.text.splitlines()
    )


def variants(base: CaseFacts, precisions) -> list[tuple[CaseInput, CaseInput]]:
    """(base case, same case with a re-presented medication history) for every seed pair."""
    facts = presentations(base, precisions)
    assert all(labels(f) == labels(base) for f in facts), "a variant changed the labels"
    pairs = []
    for note_seed in SEEDS:
        original = build(base, note_seed)
        for f in facts:
            for history_seed in SEEDS:
                pairs.append((original, with_history_from(original, build(f, history_seed))))
    return pairs


@pytest.mark.parametrize("base", [ENDED, ONGOING], ids=["ended", "ongoing"])
def test_the_tell_alone_never_produces_a_contradiction(base):
    assert labels(base).contradiction_present is False
    pairs = variants(base, ("day", "month"))
    assert any(has_tell(v) for _, v in pairs) and any(not has_tell(v) for _, v in pairs)
    assert {contradiction(v)[0] for _, v in pairs} == {0.0}


@pytest.mark.parametrize(
    "base,expected_detected",
    [
        (replace(ENDED, contradiction="history_vs_note"), 80),
        (replace(ONGOING, contradiction="history_vs_note"), 96),
        (DATES_CONFLICT, 128),
    ],
    ids=["history_vs_note-ended", "history_vs_note-ongoing", "dates_conflict"],
)
def test_contradictions_do_not_depend_on_how_the_history_line_is_presented(base, expected_detected):
    # Contradiction scenarios carry day-precision dates (a facts.py invariant; spec R4 counts
    # only day-precision dates as cues), so split and date format vary here, not precision.
    #
    # `expected_detected` is the exact, deterministic count out of all 128 (note_seed x split x
    # history_seed) variants: detection here tracks only the fixed physician-note phrasing drawn
    # per note_seed (whether it uses a recognized "never" phrasing or falls outside the pattern,
    # e.g. "never been prescribed"), never the swapped-in history document's split/history_seed
    # presentation, which is exactly the anti-shortcut property this test is checking.
    assert labels(base).contradiction_present is True
    detected = 0
    for original, variant in variants(base, ("day",)):
        p, rules = contradiction(variant)
        assert p == contradiction(original)[0]
        if p == 1.0:
            detected += 1
            assert rules & {"mtx_never", "mtx_conflicting_starts"}
    assert detected == expected_detected


def test_generated_cases_with_the_tell_but_no_contradiction_are_never_flagged():
    flagged_tells = 0
    clean_tells = 0
    for i in range(400):
        case = generate_case(7 * SEED_STRIDE + i, DIFFICULTIES[i % 4])
        if not has_tell(case.input) or case.ground_truth.contradiction_present:
            continue
        clean_tells += 1
        flagged_tells += contradiction(case.input)[0] == 1.0
    assert clean_tells > 0
    assert flagged_tells == 0
