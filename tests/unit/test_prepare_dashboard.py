"""Publishing restores missing data and refuses drift instead of presenting skipped checks."""

import pytest

from relay.generation.generator import generate_dataset
from relay.generation.manifest import write_manifest
from relay.site.registry import DatasetSpec
from scripts import prepare_dashboard


@pytest.fixture
def prepared_repo(tmp_path, monkeypatch):
    dataset = DatasetSpec("test-data", "Test", "evals/generated/test-data", False, "Test")
    monkeypatch.setattr(prepare_dashboard, "DATASETS", (dataset,))
    manifest = generate_dataset(4, 1, dataset.id, tmp_path / "reference")
    write_manifest(manifest, tmp_path / "evals/generated/manifests/test-data.json")
    return tmp_path


def test_missing_data_is_restored_and_existing_data_is_preserved(prepared_repo):
    prepare_dashboard.prepare_datasets(prepared_repo)
    output = prepared_repo / "evals/generated/test-data"
    files = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    assert len(list(output.glob("*/case.json"))) == 4
    prepare_dashboard.prepare_datasets(prepared_repo)
    assert files == {
        p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()
    }


def test_changed_existing_data_blocks_publication(prepared_repo):
    prepare_dashboard.prepare_datasets(prepared_repo)
    document = next((prepared_repo / "evals/generated/test-data").glob("*/documents/*.txt"))
    document.write_text("Changed evidence", encoding="utf-8")
    with pytest.raises(ValueError, match="do not match the manifest"):
        prepare_dashboard.prepare_datasets(prepared_repo)
    assert document.read_text(encoding="utf-8") == "Changed evidence"
