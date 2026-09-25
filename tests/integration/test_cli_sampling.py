"""relay run/eval --limit N --sample-seed S: a deterministic subsample (2D latency sample)."""

import json
from pathlib import Path

from typer.testing import CliRunner

from relay.cli import app

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
runner = CliRunner()


def eval_smoke(tmp_path, name, *extra):
    out = tmp_path / name
    result = runner.invoke(
        app,
        [
            "--env-file",
            str(tmp_path / "missing.env"),
            "eval",
            "--dataset",
            str(SMOKE),
            "--provider",
            "groundtruth",
            "--traces-dir",
            str(out / "traces"),
            "--reports-dir",
            str(out / "reports"),
            "--results-dir",
            str(out / "results"),
            *extra,
        ],
    )
    return result, out


def case_ids(out):
    results = json.loads(next((out / "results").glob("*.json")).read_text())
    return [c["case_id"] for c in results["cases"]]


def test_limit_and_seed_pick_the_same_cases_every_time(tmp_path):
    first, out1 = eval_smoke(tmp_path, "a", "--limit", "3", "--sample-seed", "7")
    second, out2 = eval_smoke(tmp_path, "b", "--limit", "3", "--sample-seed", "7")
    assert first.exit_code == 0 and second.exit_code == 0, first.output + second.output
    assert case_ids(out1) == case_ids(out2)
    assert len(case_ids(out1)) == 3
    manifest = json.loads(next((out1 / "traces").glob("*.manifest.json")).read_text())
    assert (manifest["case_count"], manifest["sample_limit"], manifest["sample_seed"]) == (3, 3, 7)


def test_a_subsample_run_rescores_only_with_the_same_limit_and_seed(tmp_path):
    result, out = eval_smoke(tmp_path, "a", "--limit", "3", "--sample-seed", "7")
    assert result.exit_code == 0, result.output
    [trace_file] = (out / "traces").glob("*.jsonl")
    same, _ = eval_smoke(
        tmp_path, "b", "--traces", str(trace_file), "--limit", "3", "--sample-seed", "7"
    )
    assert same.exit_code == 0, same.output
    full, _ = eval_smoke(tmp_path, "c", "--traces", str(trace_file))
    assert full.exit_code == 2
    assert "do not cover every case" in full.output


def test_limit_without_a_seed_is_a_usage_error(tmp_path):
    result, out = eval_smoke(tmp_path, "a", "--limit", "3")
    assert result.exit_code == 2
    assert "--limit and --sample-seed must be given together" in result.output
    assert not (out / "traces").exists()


def test_a_full_run_records_no_sample(tmp_path):
    result, out = eval_smoke(tmp_path, "a")
    assert result.exit_code == 0, result.output
    manifest = json.loads(next((out / "traces").glob("*.manifest.json")).read_text())
    assert (manifest["sample_limit"], manifest["sample_seed"]) == (None, None)
