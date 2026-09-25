import json
from pathlib import Path

from typer.testing import CliRunner

from relay.cli import app

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
CASE_IDS = [
    "ADV-01",
    "ADV-02",
    "AUTO-01",
    "AUTO-02",
    "AUTO-03",
    "REV-01",
    "REV-02",
    "RI-01",
    "RI-02",
    "RI-03",
]
runner = CliRunner()


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--env-file", str(tmp_path / "missing.env"), *args])


def dirs(tmp_path):
    return [
        "--traces-dir",
        str(tmp_path / "traces"),
        "--reports-dir",
        str(tmp_path / "reports"),
    ]


def test_run_groundtruth_writes_traces_manifest_and_report(tmp_path):
    result = invoke(
        tmp_path, "run", "--dataset", str(SMOKE), "--provider", "groundtruth", *dirs(tmp_path)
    )
    assert result.exit_code == 0, result.output
    [trace_file] = (tmp_path / "traces").glob("*.jsonl")
    assert len(trace_file.read_text().splitlines()) == 10
    assert len(list((tmp_path / "traces").glob("*.manifest.json"))) == 1
    report = next((tmp_path / "reports").glob("*.md")).read_text()
    for case_id in CASE_IDS:
        assert f"## {case_id} — " in report
    assert "pipeline validation" in result.output.lower()


def test_eval_groundtruth_is_perfect(tmp_path):
    result = invoke(
        tmp_path,
        "eval",
        "--dataset",
        str(SMOKE),
        "--provider",
        "groundtruth",
        *dirs(tmp_path),
        "--results-dir",
        str(tmp_path / "results"),
    )
    assert result.exit_code == 0, result.output
    assert "10/10 (100.0%)" in result.output
    assert "0/3 (0.0%)" in result.output
    results = json.loads(next((tmp_path / "results").glob("*.json")).read_text())
    assert results["correct_action_rate"] == 1.0
    assert results["unsafe_automation_rate"] == 0.0
    assert results["auto_process_count"] == 3


def test_eval_rescores_existing_traces_without_a_provider_key(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    invoke(tmp_path, "run", "--dataset", str(SMOKE), "--provider", "groundtruth", *dirs(tmp_path))
    [trace_file] = (tmp_path / "traces").glob("*.jsonl")
    result = invoke(
        tmp_path,
        "eval",
        "--dataset",
        str(SMOKE),
        "--provider",
        "jev",
        "--traces",
        str(trace_file),
        "--results-dir",
        str(tmp_path / "results"),
    )
    assert result.exit_code == 0, result.output
    assert "10/10 (100.0%)" in result.output


def test_jev_without_key_fails_fast(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    result = invoke(tmp_path, "run", "--dataset", str(SMOKE), "--provider", "jev", *dirs(tmp_path))
    assert result.exit_code == 2
    assert "TYPESAFE_API_KEY" in result.output
    assert not (tmp_path / "traces").exists()


def test_wrong_policy_version_fails_before_writing_traces(tmp_path):
    result = invoke(
        tmp_path,
        "run",
        "--dataset",
        str(SMOKE),
        "--provider",
        "groundtruth",
        "--policy",
        "v9",
        *dirs(tmp_path),
    )
    assert result.exit_code == 2
    assert "v9" in result.output
    assert not (tmp_path / "traces").exists()


def test_invalid_dataset_fails_with_path(tmp_path):
    bad = tmp_path / "bad"
    (bad / "X-01").mkdir(parents=True)
    result = invoke(tmp_path, "run", "--dataset", str(bad), "--provider", "groundtruth")
    assert result.exit_code == 2
    assert "X-01" in result.output
