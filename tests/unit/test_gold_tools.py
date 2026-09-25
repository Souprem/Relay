import json

import pytest

from tests.factories import make_case, make_truth
from tests.gold_support import ALL_IDS, GUIDE_PATH, REPO, rules_section
from tests.gold_tools import (
    blind_ids,
    compute_agreement,
    export_blind_packet,
    import_second_pass,
    per_category_rows,
)


def _record(**overrides):
    record = {
        "diagnosis_supported": True,
        "step_therapy_satisfied": True,
        "documentation_complete": True,
        "contradiction_present": False,
        "missing_evidence": "NONE",
        "rationale": "physician_note establishes RA and a 20-week course.",
    }
    record.update(overrides)
    return record


def test_blind_ids_are_a_stable_shuffled_permutation():
    mapping = blind_ids()
    assert mapping == blind_ids()
    assert sorted(mapping) == sorted(ALL_IDS)
    assert sorted(mapping.values()) == [f"CASE-{n:03d}" for n in range(1, 101)]
    first_twenty = [gold for gold, blind in mapping.items() if blind <= "CASE-020"]
    assert len({gold.split("-")[1] for gold in first_twenty}) > 1  # categories are mixed


def test_import_maps_blind_ids_back_and_rejects_bad_records():
    expected = ["GOLD-STR-01", "GOLD-CON-01"]
    mapping = blind_ids()
    blind = {"reviewer": "blind-second-pass", "labels": {mapping[g]: _record() for g in expected}}
    imported = import_second_pass(blind, expected)
    assert list(imported["labels"]) == ["GOLD-CON-01", "GOLD-STR-01"]
    assert imported["labels"]["GOLD-STR-01"]["blind_id"] == mapping["GOLD-STR-01"]

    inconsistent = {
        "labels": {
            mapping["GOLD-STR-01"]: _record(documentation_complete=False),
            mapping["GOLD-CON-01"]: _record(),
        }
    }
    with pytest.raises(ValueError, match="inconsistent"):
        import_second_pass(inconsistent, expected)
    with pytest.raises(ValueError, match="missing"):
        import_second_pass({"labels": {mapping["GOLD-STR-01"]: _record()}}, expected)
    unused_label = {"labels": {mapping[g]: _record() for g in expected}}
    unused_label["labels"][mapping["GOLD-CON-01"]] = _record(
        missing_evidence="DOSAGE", documentation_complete=False
    )
    with pytest.raises(ValueError, match="missing_evidence"):
        import_second_pass(unused_label, expected)


def test_compute_agreement_counts_facts_and_derived_actions():
    auto_case = make_case("T-01")  # all facts true, NONE -> AUTO_PROCESS
    review_case = make_case("T-02", truth=make_truth(step_therapy_satisfied=False))
    second = {
        "labels": {
            "T-01": _record(),
            "T-02": _record(),  # says step therapy is satisfied -> AUTO_PROCESS
        }
    }
    result = compute_agreement([auto_case, review_case], second)
    assert result["n"] == 2
    assert result["per_fact"]["step_therapy_satisfied"] == {"agree": 1, "n": 2, "rate": 0.5}
    assert result["per_fact"]["diagnosis_supported"] == {"agree": 2, "n": 2, "rate": 1.0}
    assert result["all_five"] == {"agree": 1, "n": 2, "rate": 0.5}
    assert result["action"] == {"agree": 1, "n": 2, "rate": 0.5}
    assert result["disagreements"] == [
        {"case_id": "T-02", "fact": "step_therapy_satisfied", "first": False, "second": True}
    ]
    assert result["action_disagreements"] == [
        {"case_id": "T-02", "first": "HUMAN_REVIEW", "second": "AUTO_PROCESS"}
    ]


def test_export_contains_only_label_free_inputs(tmp_path):
    out = tmp_path / "blind"
    ids = export_blind_packet(out)
    assert ids == [f"CASE-{n:03d}" for n in range(1, 101)]
    case_dirs = sorted(p.name for p in (out / "cases").iterdir())
    assert case_dirs == ids
    assert not list(out.rglob("ground_truth.json"))
    for case_dir in (out / "cases").iterdir():
        raw = json.loads((case_dir / "case.json").read_text())
        assert raw["id"] == case_dir.name
        assert "GOLD-" not in (case_dir / "case.json").read_text()
    rules = (out / "RULES.md").read_text()
    assert rules.strip() == rules_section(GUIDE_PATH.read_text())
    assert "GOLD-" not in rules
    template = json.loads((out / "second_pass.template.json").read_text())
    assert sorted(template["labels"]) == ids
    assert sorted(p.name for p in out.iterdir()) == [
        "RULES.md",
        "cases",
        "second_pass.template.json",
    ]
    with pytest.raises(ValueError, match="inside the repository"):
        export_blind_packet(REPO / "evals" / "blind-should-not-exist")
    assert not (REPO / "evals" / "blind-should-not-exist").exists()


def test_per_category_rows_group_scored_cases_by_prefix():
    def scored(case_id, action, expected, unsafe=False, invalid=False):
        return {
            "case_id": case_id,
            "expected_action": expected,
            "action": action,
            "correct": action == expected,
            "unsafe_automation": unsafe,
            "invalid_output": invalid,
        }

    results = {
        "cases": [
            scored("GOLD-STR-01", "AUTO_PROCESS", "AUTO_PROCESS"),
            scored("GOLD-CON-01", "AUTO_PROCESS", "HUMAN_REVIEW", unsafe=True),
            scored("GOLD-TMP-01", "HUMAN_REVIEW", "HUMAN_REVIEW", invalid=True),
        ]
    }
    rows = {r["category"]: r for r in per_category_rows(results)}
    assert list(rows) == ["STR", "MIS", "CON", "TMP", "TRK", "ALL"]
    assert rows["STR"] == {
        "category": "STR",
        "n": 1,
        "correct": 1,
        "auto": 1,
        "unsafe": 0,
        "request_info": 0,
        "review": 0,
        "invalid": 0,
    }
    assert rows["CON"]["unsafe"] == 1 and rows["CON"]["correct"] == 0
    assert rows["MIS"]["n"] == 0
    assert rows["ALL"] == {
        "category": "ALL",
        "n": 3,
        "correct": 2,
        "auto": 2,
        "unsafe": 1,
        "request_info": 0,
        "review": 1,
        "invalid": 1,
    }
