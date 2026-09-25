"""Offline analysis commands (sweep, report, compare) on a ground-truth run of generated cases."""

import csv
import json

import pytest
from typer.testing import CliRunner

from relay.cli import app

runner = CliRunner()


def invoke(root, *args):
    return runner.invoke(app, ["--env-file", str(root / "missing.env"), *args])


@pytest.fixture(scope="module")
def gt_run(tmp_path_factory):
    """A 40-case generated dataset (with its manifest) and one ground-truth trace file."""
    root = tmp_path_factory.mktemp("analysis")
    dataset = root / "gen-analysis"
    generated = invoke(
        root,
        "generate",
        "--count",
        "40",
        "--seed",
        "3",
        "--dataset-id",
        "gen-analysis",
        "--out",
        str(dataset),
        "--manifests-dir",
        str(root / "manifests"),
    )
    assert generated.exit_code == 0, generated.output
    ran = invoke(
        root,
        "run",
        "--dataset",
        str(dataset),
        "--provider",
        "groundtruth",
        "--traces-dir",
        str(root / "traces"),
        "--reports-dir",
        str(root / "reports"),
    )
    assert ran.exit_code == 0, ran.output
    [trace_file] = (root / "traces").glob("*.jsonl")
    return root, dataset, trace_file


def test_sweep_on_a_groundtruth_run_selects_the_highest_threshold(gt_run, tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    root, dataset, trace_file = gt_run
    out = tmp_path / "results"
    result = invoke(
        root, "sweep", "--dataset", str(dataset), "--traces", str(trace_file), "--out", str(out)
    )
    assert result.exit_code == 0, result.output
    # Certain probabilities: every threshold gives identical results, so the tie rule picks 0.99.
    assert "Selected operating point: auto_process >= 0.99" in result.output
    [sweep_json] = out.glob("*.sweep.json")
    data = json.loads(sweep_json.read_text())
    assert data["selected"]["auto_threshold"] == 0.99
    assert data["selected"]["unsafe"] == 0
    assert data["at_point"] is None
    assert len(data["points"]) == 50
    assert len({(p["auto"], p["correct"]) for p in data["points"]}) == 1
    [frontier] = out.glob("*.frontier.csv")
    rows = list(csv.DictReader(frontier.open()))
    assert len(rows) == 50 and rows[0]["auto_threshold"] == "0.5"


def test_sweep_reports_the_at_point(gt_run, tmp_path):
    root, dataset, trace_file = gt_run
    out = tmp_path / "results"
    args = ["--dataset", str(dataset), "--traces", str(trace_file), "--out", str(out)]
    result = invoke(root, "sweep", *args, "--at", "0.935")
    assert result.exit_code == 0, result.output
    assert "0.935" in result.output and "--at" in result.output
    data = json.loads(next(out.glob("*.sweep.json")).read_text())
    assert data["at_point"]["auto_threshold"] == 0.935


def test_sweep_with_incomplete_traces_exits_2(gt_run, tmp_path):
    root, dataset, trace_file = gt_run
    partial = tmp_path / "partial.jsonl"
    partial.write_text("\n".join(trace_file.read_text().splitlines()[:10]) + "\n")
    result = invoke(
        root, "sweep", "--dataset", str(dataset), "--traces", str(partial), "--out", str(tmp_path)
    )
    assert result.exit_code == 2
    assert result.output.startswith("error:")
    assert "missing" in result.output


def test_sweep_with_a_corrupt_trace_file_exits_2(gt_run, tmp_path):
    root, dataset, _ = gt_run
    bad = tmp_path / "bad.jsonl"
    bad.write_text("not json\n")
    result = invoke(
        root, "sweep", "--dataset", str(dataset), "--traces", str(bad), "--out", str(tmp_path)
    )
    assert result.exit_code == 2
    assert result.output.startswith("error:")
