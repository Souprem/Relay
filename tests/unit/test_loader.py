import json
import re

import pytest

from relay.cases.loader import CaseLoadError, load_case, load_dataset

CASE_JSON = {
    "id": "X-01",
    "dataset_id": "tmp",
    "as_of_date": "2026-09-15",
    "patient": {"age": 40, "state": "MA"},
    "medication": {"name": "Immunara", "indication": "rheumatoid arthritis"},
    "insurance": {"payer": "ExampleHealth", "plan": "ExampleHealth Gold", "member_id": "M-1"},
    "policy_id": "immunara-v0.1",
    "documents": [{"id": "physician_note", "kind": "physician_note", "file": "note.txt"}],
}
TRUTH_JSON = {
    "diagnosis_supported": True,
    "step_therapy_satisfied": True,
    "documentation_complete": True,
    "contradiction_present": False,
    "missing_evidence": "NONE",
}


def write_case(root, name="X-01", case=None, truth=None, note="Synthetic note."):
    case_dir = root / name
    (case_dir / "documents").mkdir(parents=True)
    (case_dir / "case.json").write_text(json.dumps(case or {**CASE_JSON, "id": name}))
    (case_dir / "ground_truth.json").write_text(json.dumps(truth or TRUTH_JSON))
    (case_dir / "documents" / "note.txt").write_text(note)
    return case_dir


def test_load_case_reads_documents_from_files(tmp_path):
    case = load_case(write_case(tmp_path, note="MTX started 2026-01-12."))
    assert case.input.id == "X-01"
    assert case.input.documents[0].text == "MTX started 2026-01-12."
    assert case.ground_truth.documentation_complete is True


def test_directory_name_must_match_case_id(tmp_path):
    case_dir = write_case(tmp_path, name="X-02", case={**CASE_JSON, "id": "X-99"})
    with pytest.raises(CaseLoadError, match="X-02"):
        load_case(case_dir)


def test_invalid_json_names_the_case_directory(tmp_path):
    case_dir = write_case(tmp_path)
    (case_dir / "case.json").write_text("{not json")
    with pytest.raises(CaseLoadError, match=re.escape(str(case_dir))):
        load_case(case_dir)


def test_missing_document_file_is_a_load_error(tmp_path):
    case_dir = write_case(tmp_path)
    (case_dir / "documents" / "note.txt").unlink()
    with pytest.raises(CaseLoadError, match="note.txt"):
        load_case(case_dir)


def test_inconsistent_ground_truth_is_a_load_error(tmp_path):
    bad = {**TRUTH_JSON, "missing_evidence": "DIAGNOSIS"}
    with pytest.raises(CaseLoadError, match="inconsistent ground truth"):
        load_case(write_case(tmp_path, truth=bad))


def test_load_dataset_sorted_and_single_dataset_id(tmp_path):
    write_case(tmp_path, name="B-01")
    write_case(tmp_path, name="A-01")
    assert [c.input.id for c in load_dataset(tmp_path)] == ["A-01", "B-01"]


def test_load_dataset_rejects_mixed_dataset_ids(tmp_path):
    write_case(tmp_path, name="A-01")
    write_case(tmp_path, name="B-01", case={**CASE_JSON, "id": "B-01", "dataset_id": "other"})
    with pytest.raises(CaseLoadError, match="dataset_id"):
        load_dataset(tmp_path)


def test_load_dataset_empty_directory(tmp_path):
    with pytest.raises(CaseLoadError, match="no case directories"):
        load_dataset(tmp_path)
