import json

from typer.testing import CliRunner

from relay.cli import app

runner = CliRunner()


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--env-file", str(tmp_path / "missing.env"), *args])


def generate(tmp_path, count=8, seed=3, dataset_id="gen-test"):
    return invoke(
        tmp_path,
        "generate",
        "--count",
        str(count),
        "--seed",
        str(seed),
        "--dataset-id",
        dataset_id,
        "--out",
        str(tmp_path / dataset_id),
        "--manifests-dir",
        str(tmp_path / "manifests"),
    )


def verify(tmp_path, dataset_id="gen-test", *extra):
    return invoke(
        tmp_path,
        "generate",
        "--verify",
        str(tmp_path / "manifests" / f"{dataset_id}.json"),
        "--out",
        str(tmp_path / dataset_id),
        *extra,
    )


def test_generate_writes_cases_and_manifest(tmp_path):
    result = generate(tmp_path)
    assert result.exit_code == 0, result.output
    case_dirs = sorted(p.name for p in (tmp_path / "gen-test").iterdir())
    assert case_dirs == [f"GEN-0300000{i}" for i in range(8)]
    manifest = json.loads((tmp_path / "manifests" / "gen-test.json").read_text())
    assert (manifest["dataset_id"], manifest["seed"], manifest["count"]) == ("gen-test", 3, 8)
    assert manifest["generator_version"] == "gen-v0.1"
    assert manifest["dataset_hash"] in result.output


def test_verify_passes_on_a_fresh_generation(tmp_path):
    generate(tmp_path)
    result = verify(tmp_path)
    assert result.exit_code == 0, result.output
    assert result.output.startswith("OK:")


def test_verify_fails_after_a_document_is_edited(tmp_path):
    generate(tmp_path)
    note = tmp_path / "gen-test" / "GEN-03000001" / "documents" / "physician_note.txt"
    note.write_text(note.read_text().replace("Immunara", "Immunara today"))
    result = verify(tmp_path)
    assert result.exit_code == 2
    assert "MISMATCH" in result.output and "files on disk" in result.output


def test_non_empty_out_is_refused_with_the_path(tmp_path):
    generate(tmp_path)
    result = generate(tmp_path)
    assert result.exit_code == 2
    assert "gen-test" in result.output and "not empty" in result.output


def test_count_zero_and_negative_seed_are_rejected_by_option_bounds(tmp_path):
    assert generate(tmp_path, count=0).exit_code == 2
    assert generate(tmp_path, seed=-1, dataset_id="neg").exit_code == 2


def test_generate_requires_all_options(tmp_path):
    result = invoke(tmp_path, "generate", "--count", "4", "--out", str(tmp_path / "x"))
    assert result.exit_code == 2
    assert "--seed" in result.output


def test_verify_cannot_be_combined_with_generation_options(tmp_path):
    generate(tmp_path)
    result = verify(tmp_path, "gen-test", "--seed", "4")
    assert result.exit_code == 2
    assert "--verify" in result.output


def test_groundtruth_eval_on_a_generated_dataset_is_perfect(tmp_path):
    assert generate(tmp_path, count=40, seed=3, dataset_id="gen-pipeline").exit_code == 0
    result = invoke(
        tmp_path,
        "eval",
        "--dataset",
        str(tmp_path / "gen-pipeline"),
        "--provider",
        "groundtruth",
        "--traces-dir",
        str(tmp_path / "traces"),
        "--reports-dir",
        str(tmp_path / "reports"),
        "--results-dir",
        str(tmp_path / "results"),
    )
    assert result.exit_code == 0, result.output
    assert "40/40 (100.0%)" in result.output
    results = json.loads(next((tmp_path / "results").glob("*.json")).read_text())
    assert results["correct_action_rate"] == 1.0
    assert results["auto_process_count"] > 0
    assert results["unsafe_automation_rate"] == 0.0


def test_verify_exits_2_with_malformed_manifest_count_zero(tmp_path):
    generate(tmp_path)
    # Overwrite manifest with invalid count (0)
    manifest_path = tmp_path / "manifests" / "gen-test.json"
    manifest_data = json.loads(manifest_path.read_text())
    manifest_data["count"] = 0
    manifest_path.write_text(json.dumps(manifest_data))
    result = verify(tmp_path)
    assert result.exit_code == 2
    assert "error:" in result.output


def test_verify_exits_2_with_invalid_json_manifest(tmp_path):
    (tmp_path / "manifests").mkdir(parents=True, exist_ok=True)
    manifest_path = tmp_path / "manifests" / "bad.json"
    manifest_path.write_text("{ invalid json")
    result = invoke(
        tmp_path,
        "generate",
        "--verify",
        str(manifest_path),
        "--out",
        str(tmp_path / "output"),
    )
    assert result.exit_code == 2
    assert "error:" in result.output
