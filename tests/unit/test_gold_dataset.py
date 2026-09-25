"""gold-v0.1 (Phase 2E): scenario table, per-case rules, category composition, whole-set checks.

Per-case checks run on every authored case directory, so authors get feedback case by case.
Category checks run once a category has any case directory. The whole-set check requires all 100 case directories.
"""

from collections import Counter

import pytest

from relay.cases.loader import load_dataset
from relay.generation.manifest import dataset_hash
from tests.gold_support import (
    ALL_IDS,
    CATEGORIES,
    GOLD_DIR,
    GUIDE_PATH,
    INTENDED,
    RULES_BEGIN,
    RULES_END,
    STYLES,
    case_problems,
    category_problems,
    parse_guide_table,
    present_case_dirs,
    rules_section,
    set_problems,
    stray_entries,
    table_action,
)

PRESENT = present_case_dirs()


def _rows(category):
    return [INTENDED[i] for i in ALL_IDS if i.startswith(f"GOLD-{category}-")]


def test_table_has_exactly_the_100_gold_ids():
    assert tuple(INTENDED) == ALL_IDS


def test_table_composition_matches_spec_q7():
    assert Counter(r.action for r in _rows("STR")) == {"AUTO_PROCESS": 10, "REQUEST_INFO": 10}
    assert sum(r.con for r in _rows("CON")) == 14
    assert not any(r.con for c in ("STR", "MIS", "TMP", "TRK") for r in _rows(c))
    mis = _rows("MIS")
    assert sum(r.missing == "NONE" for r in mis) == 4  # "looks missing but present elsewhere"
    assert {r.missing for r in mis} == {
        "DIAGNOSIS",
        "TREATMENT_HISTORY",
        "INSURANCE_INFORMATION",
        "NONE",
    }
    for category in CATEGORIES:
        assert Counter(r.style for r in _rows(category)) == {s: 5 for s in STYLES}, category


def test_table_actions_follow_from_the_facts_through_the_engine():
    for case_id, row in INTENDED.items():
        assert table_action(case_id) == row.action, case_id


def test_guide_table_is_identical_to_the_code_table():
    assert parse_guide_table(GUIDE_PATH.read_text(encoding="utf-8")) == INTENDED


def test_rules_section_is_marked_once_and_names_no_case():
    text = GUIDE_PATH.read_text(encoding="utf-8")
    assert text.count(RULES_BEGIN) == 1
    assert text.count(RULES_END) == 1
    rules = rules_section(text)
    assert "GOLD-" not in rules  # the blind reviewer receives exactly this section
    assert len(rules) > 2000


def test_gold_dir_has_no_stray_entries():
    assert stray_entries() == []


@pytest.mark.parametrize("case_dir", PRESENT, ids=[d.name for d in PRESENT])
def test_case_follows_the_guide(case_dir):
    assert case_problems(case_dir) == []


@pytest.mark.parametrize("category", CATEGORIES)
def test_category_composition_and_floors(category):
    if not any(d.name.startswith(f"GOLD-{category}-") for d in PRESENT):
        pytest.skip(f"no GOLD-{category}-* case directories authored yet")
    assert category_problems(category) == []


def test_full_gold_set():
    assert set_problems() == []


# Frozen by 2E Task 9. Any edit to a gold case, document or label changes this value. Never edit
# gold-v0.1 in place: publish a new dataset id instead, and never because of provider results.
GOLD_DATASET_HASH = "sha256:3ba49030a21f4d715e56df2b3cb3e0b03f07dbdcb097205be15e5674c8e42679"


def test_gold_v0_1_is_frozen():
    assert dataset_hash(load_dataset(GOLD_DIR)) == GOLD_DATASET_HASH
