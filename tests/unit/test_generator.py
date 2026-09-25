import hashlib
import json
from pathlib import Path

import pytest

from relay.cases.loader import load_case, load_dataset
from relay.cases.policies import load_policy
from relay.evaluation.labels import expected_action
from relay.generation.facts import DIFFICULTIES, GENERATOR_VERSION
from relay.generation.generator import (
    generate_case,
    generate_dataset,
    verify_dataset,
    write_case,
)
from relay.generation.manifest import (
    DatasetManifest,
    dataset_hash,
    read_manifest,
    write_manifest,
)
from relay.generation.render import SYNTHETIC_PREFIX
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1

POLICY = load_policy("immunara-v0.1")


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_generate_case_is_deterministic():
    assert generate_case(42, "hard") == generate_case(42, "hard")
    assert generate_case(42, "hard") != generate_case(43, "hard")


def test_generate_case_structured_fields():
    case = generate_case(42, "easy")
    assert case.input.id == "GEN-00000042"
    assert case.input.dataset_id == "gen-adhoc"
    assert case.input.policy_id == "immunara-v0.1"
    assert (case.input.medication.name, case.input.medication.indication) == (
        "Immunara",
        "rheumatoid arthritis",
    )
    assert case.ground_truth.notes.startswith(f"{GENERATOR_VERSION} easy:")
    assert generate_case(42, "easy", dataset_id="custom").input.dataset_id == "custom"


def test_unknown_difficulty_and_policy_version_are_rejected():
    with pytest.raises(ValueError, match="allowed"):
        generate_case(1, "extreme")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="v0.1"):
        generate_case(1, "easy", policy_version="v9")


def test_written_case_round_trips_through_the_real_loader(tmp_path):
    case = generate_case(5, "adversarial")
    case_dir = write_case(case, tmp_path)
    assert case_dir == tmp_path / "GEN-00000005"
    assert load_case(case_dir) == case
    raw = json.loads((case_dir / "case.json").read_text())
    assert [d["file"] for d in raw["documents"]] == [f"{d.id}.txt" for d in case.input.documents]


def test_consistency_sweep_over_two_thousand_seeds(tmp_path):
    actions = set()
    for seed in range(2000):
        case = generate_case(seed, DIFFICULTIES[seed % 4])
        loaded = load_case(write_case(case, tmp_path))
        assert loaded == case
        assert all(d.text.startswith(SYNTHETIC_PREFIX) for d in loaded.input.documents)
        actions.add(expected_action(loaded, POLICY, THRESHOLDS_V0_1))
    assert actions == set(WorkflowAction)


def test_same_arguments_give_byte_identical_datasets(tmp_path):
    first = generate_dataset(24, 9, "gen-test", tmp_path / "a")
    second = generate_dataset(24, 9, "gen-test", tmp_path / "b")
    assert first == second
    assert tree_digest(tmp_path / "a") == tree_digest(tmp_path / "b")
    other = generate_dataset(24, 10, "gen-test", tmp_path / "c")
    assert other.dataset_hash != first.dataset_hash


def test_dev_sized_dataset_distribution(tmp_path):
    manifest = generate_dataset(400, 1, "gen-v0.1-dev", tmp_path / "dev")
    assert manifest.count == 400
    assert manifest.difficulty_counts == {d: 100 for d in sorted(DIFFICULTIES)}
    assert set(manifest.expected_action_counts) == {a.value for a in WorkflowAction}
    for action, n in manifest.expected_action_counts.items():
        assert n >= 60, (action, n)  # at least 15% of 400
    assert set(manifest.missing_evidence_counts) == {
        "DIAGNOSIS",
        "TREATMENT_HISTORY",
        "INSURANCE_INFORMATION",
        "NONE",
    }
    assert sum(manifest.missing_evidence_counts.values()) == 400
    cases = load_dataset(tmp_path / "dev")
    assert [c.input.id for c in cases][:2] == ["GEN-01000000", "GEN-01000001"]
    assert {c.input.dataset_id for c in cases} == {"gen-v0.1-dev"}


def test_manifest_hash_matches_files_and_has_no_timestamp(tmp_path):
    manifest = generate_dataset(12, 4, "gen-test", tmp_path / "ds")
    assert manifest.dataset_hash == dataset_hash(load_dataset(tmp_path / "ds"))
    assert manifest.dataset_hash.startswith("sha256:")
    assert set(DatasetManifest.model_fields) == {
        "dataset_id",
        "generator_version",
        "seed",
        "count",
        "difficulty_counts",
        "expected_action_counts",
        "missing_evidence_counts",
        "dataset_hash",
    }
    path = tmp_path / "manifests" / "gen-test.json"
    write_manifest(manifest, path)
    assert read_manifest(path) == manifest
    assert path.read_text().endswith("}\n")


def test_dataset_hash_ignores_case_order(tmp_path):
    generate_dataset(6, 4, "gen-test", tmp_path / "ds")
    cases = load_dataset(tmp_path / "ds")
    assert dataset_hash(cases) == dataset_hash(list(reversed(cases)))


def test_non_empty_output_directory_is_refused(tmp_path):
    out = tmp_path / "ds"
    out.mkdir()
    (out / "keep.txt").write_text("x")
    with pytest.raises(FileExistsError, match="not empty"):
        generate_dataset(4, 1, "gen-test", out)


def test_existing_empty_output_directory_is_allowed(tmp_path):
    out = tmp_path / "ds"
    out.mkdir()
    assert generate_dataset(4, 1, "gen-test", out).count == 4


def test_zero_count_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="count"):
        generate_dataset(0, 1, "gen-test", tmp_path / "ds")


def test_verify_passes_on_fresh_generation(tmp_path):
    manifest = generate_dataset(8, 3, "gen-test", tmp_path / "ds")
    assert verify_dataset(manifest, tmp_path / "ds") == []
    assert verify_dataset(manifest) == []
    assert verify_dataset(manifest, tmp_path / "missing") == []


def test_verify_detects_an_edited_document(tmp_path):
    manifest = generate_dataset(8, 3, "gen-test", tmp_path / "ds")
    note = tmp_path / "ds" / "GEN-03000000" / "documents" / "physician_note.txt"
    note.write_text(note.read_text() + "Edited.\n")
    [problem] = verify_dataset(manifest, tmp_path / "ds")
    assert "files on disk" in problem


def test_verify_detects_a_tampered_manifest(tmp_path):
    manifest = generate_dataset(8, 3, "gen-test", tmp_path / "ds")
    tampered = manifest.model_copy(update={"dataset_hash": "sha256:0"})
    problems = verify_dataset(tampered)
    assert len(problems) == 1 and "does not match the manifest" in problems[0]


def test_verify_rejects_a_different_generator_version(tmp_path):
    manifest = generate_dataset(4, 3, "gen-test", tmp_path / "ds")
    old = manifest.model_copy(update={"generator_version": "gen-v0.0"})
    [problem] = verify_dataset(old)
    assert "gen-v0.0" in problem and GENERATOR_VERSION in problem
