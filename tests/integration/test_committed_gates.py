"""The committed regression gates (evals/regression/gates.json) pass on the committed traces.

This is the same command CI runs. Gates marked requires_generated are SKIPPED by the command
itself when evals/generated/gen-v0.2-holdout is not on disk (it is git-ignored; CI regenerates
it with `relay generate`).
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from relay.cli import app
from relay.evaluation.regression_run import load_gates, load_waivers

REPO = Path(__file__).resolve().parents[2]
GATES = REPO / "evals" / "regression" / "gates.json"
EXAMPLE_WAIVER = REPO / "evals" / "regression" / "examples" / "waiver-tmp17.json"
GOLD_JEV = "evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz"


def invoke(tmp_path, *args):
    return CliRunner().invoke(app, ["--env-file", str(tmp_path / "missing.env"), *map(str, args)])


def test_the_committed_gates_are_the_spec_s_initial_set():
    names = [g.name for g in load_gates(GATES).gates]
    assert names == [
        "gold-reproduce-groundtruth",
        "gold-reproduce-rules",
        "gold-reproduce-jev",
        "gold-reproduce-claude",
        "smoke-reproduce-jev",
        "gold-jev-vs-claude",
        "holdout-reproduce-jev",
        "holdout-reproduce-rules",
        "holdout-reproduce-claude-150",
    ]


def test_every_committed_gate_points_at_committed_files():
    for spec in load_gates(GATES).gates:
        assert (REPO / spec.baseline).is_file(), spec.name
        if spec.candidate.traces is not None:
            assert (REPO / spec.candidate.traces).is_file(), spec.name
        if spec.requires_generated:
            assert spec.dataset.startswith("evals/generated/"), spec.name
        else:
            assert (REPO / spec.dataset).is_dir(), spec.name


def test_the_committed_gates_pass(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO)  # gate paths are repository-relative
    result = invoke(tmp_path, "regression", "--config", GATES, "--out", tmp_path / "report")
    assert result.exit_code == 0, result.output
    summary = result.output[result.output.index("REGRESSION GATES") :].splitlines()[2:]
    for spec in load_gates(GATES).gates:
        [row] = [line for line in summary if line.split()[0] == spec.name]
        generated = (REPO / spec.dataset).is_dir()
        expected = "SKIPPED" if spec.requires_generated and not generated else "PASS"
        assert row.split()[1] == expected, row
        if expected == "PASS":
            verdict = json.loads((tmp_path / "report" / spec.name / "regression.json").read_text())
            assert verdict["verdict"] == "PASS"


def test_the_example_waiver_is_labelled_as_an_example_and_well_formed():
    [waiver] = load_waivers(EXAMPLE_WAIVER)
    assert waiver.case_id == "GOLD-TMP-17"
    assert waiver.reason.startswith("EXAMPLE ONLY")


@pytest.mark.parametrize("waived", [False, True], ids=["fails", "waived"])
def test_the_readme_gold_demo(tmp_path, monkeypatch, waived):
    monkeypatch.chdir(REPO)
    args = [
        "regression",
        "--dataset",
        "evals/gold",
        "--baseline",
        GOLD_JEV,
        "--candidate-at",
        "0.89",
    ]
    if waived:
        args += ["--waivers", EXAMPLE_WAIVER.relative_to(REPO)]
    result = invoke(tmp_path, *args)
    assert result.exit_code == (0 if waived else 4), result.output
    last = result.output.splitlines()[-1]
    assert last == (
        "REGRESSION GATE: PASS"
        if waived
        else ("REGRESSION GATE: FAIL — 1 newly unsafe case(s) without a waiver: GOLD-TMP-17")
    )
