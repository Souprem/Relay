"""relay regression, offline: smoke runs from the groundtruth and rules providers and the
committed gold traces. Never builds a network client."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import relay.cli as cli_module
import relay.evaluation.tracediff as tracediff
from relay.cli import app
from relay.evaluation.regression import RegressionResult

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
GOLD = REPO / "evals" / "gold"
GOLD_RUNS = REPO / "evals" / "baselines" / "gold-v0.1"
GOLD_JEV = GOLD_RUNS / "run_20260925T170857Z_b95be9" / "traces.jsonl.gz"
GOLD_CLAUDE = GOLD_RUNS / "run_20260926T011730Z_f1852f" / "traces.jsonl.gz"
runner = CliRunner()


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--env-file", str(tmp_path / "missing.env"), *map(str, args)])


def regression(tmp_path, *args):
    return invoke(tmp_path, "regression", *args)


@pytest.fixture(scope="module")
def smoke_runs(tmp_path_factory):
    root = tmp_path_factory.mktemp("regression-cli")
    files = {}
    for provider in ("groundtruth", "rules"):
        result = invoke(
            root,
            "run",
            "--dataset",
            SMOKE,
            "--provider",
            provider,
            "--traces-dir",
            root / provider / "traces",
            "--reports-dir",
            root / provider / "reports",
        )
        assert result.exit_code == 0, result.output
        [files[provider]] = (root / provider / "traces").glob("*.jsonl")
    return files


def waiver_file(tmp_path, case_id="GOLD-TMP-17", gate="*"):
    path = tmp_path / "waivers.json"
    waiver = {
        "case_id": case_id,
        "gate": gate,
        "reason": "accepted after review",
        "approved_by": "reviewer",
        "date": "2026-09-26",
    }
    path.write_text(json.dumps({"waivers": [waiver]}), encoding="utf-8")
    return path


GOLD_DEMO = ["--dataset", GOLD, "--baseline", GOLD_JEV, "--candidate-at", "0.89"]


# ---- the gold demonstration ----


def test_the_gold_demo_fails_with_exit_4_and_names_gold_tmp_17(tmp_path):
    result = regression(tmp_path, *GOLD_DEMO)
    assert result.exit_code == 4, result.output
    lines = result.output.splitlines()
    assert "NEWLY UNSAFE (1)" in lines
    assert "  GOLD-TMP-17  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS" in lines
    assert (
        f"      replay: relay replay GOLD-TMP-17 --traces {GOLD_JEV} --dataset {GOLD} --at 0.89"
        in lines
    )
    assert lines[-1] == (
        "REGRESSION GATE: FAIL — 1 newly unsafe case(s) without a waiver: GOLD-TMP-17"
    )


def test_the_gold_demo_passes_with_a_waiver(tmp_path):
    result = regression(tmp_path, *GOLD_DEMO, "--waivers", waiver_file(tmp_path))
    assert result.exit_code == 0, result.output
    assert "WAIVED NEWLY UNSAFE (1) — reviewed, not failures" in result.output
    assert result.output.splitlines()[-1] == "REGRESSION GATE: PASS"


def test_a_stale_waiver_is_a_warning_not_a_failure(tmp_path):
    result = regression(
        tmp_path,
        "--dataset",
        GOLD,
        "--baseline",
        GOLD_JEV,
        "--reproduce",
        "--waivers",
        waiver_file(tmp_path),
    )
    assert result.exit_code == 0, result.output
    assert "STALE WAIVERS (1) — warning: no newly unsafe case" in result.output


def test_claude_versus_jev_on_gold_at_each_operating_point_passes(tmp_path):
    result = regression(
        tmp_path,
        "--dataset",
        GOLD,
        "--baseline",
        GOLD_JEV,
        "--baseline-at",
        "0.89",
        "--candidate-traces",
        GOLD_CLAUDE,
        "--candidate-at",
        "0.55",
    )
    assert result.exit_code == 0, result.output
    assert (
        "CHANGES: improved 3 · unchanged 96 · regressed 1 · changed-both-wrong 0" in result.output
    )
    assert "NEWLY UNSAFE" not in result.output


def test_max_regressed(tmp_path):
    over = regression(
        tmp_path, *GOLD_DEMO, "--waivers", waiver_file(tmp_path), "--max-regressed", "0"
    )
    assert over.exit_code == 4, over.output
    assert over.output.splitlines()[-1] == (
        "REGRESSION GATE: FAIL — 1 regressed case(s), more than --max-regressed 0"
    )
    ok = regression(
        tmp_path, *GOLD_DEMO, "--waivers", waiver_file(tmp_path), "--max-regressed", "1"
    )
    assert ok.exit_code == 0, ok.output


# ---- smoke runs ----


def test_candidate_traces_on_smoke(tmp_path, smoke_runs):
    result = regression(
        tmp_path,
        "--dataset",
        SMOKE,
        "--baseline",
        smoke_runs["groundtruth"],
        "--candidate-traces",
        smoke_runs["rules"],
    )
    assert result.exit_code == 0, result.output
    assert "REGRESSED (1)" in result.output
    assert "  AUTO-03  expected AUTO_PROCESS  AUTO_PROCESS → REQUEST_INFO" in result.output
    assert f"--candidate-traces {smoke_runs['rules']}" in result.output


def test_reproduce_passes_and_engine_drift_exits_3(tmp_path, smoke_runs, monkeypatch):
    args = ["--dataset", SMOKE, "--baseline", smoke_runs["groundtruth"], "--reproduce"]
    ok = regression(tmp_path, *args)
    assert ok.exit_code == 0, ok.output
    real = tracediff.determine_action

    def drifted(case, bundle, policy, thresholds):
        outcome = real(case, bundle, policy, thresholds)
        if case.id != "AUTO-01":
            return outcome
        return outcome.model_copy(update={"reasons": [*outcome.reasons, "a new reason"]})

    monkeypatch.setattr(tracediff, "determine_action", drifted)
    drift = regression(tmp_path, *args)
    assert drift.exit_code == 3, drift.output
    assert "ENGINE DRIFT (1)" in drift.output
    assert drift.output.splitlines()[-1] == (
        "REGRESSION GATE: FAIL — ENGINE DRIFT: 1 case(s) not reproduced: AUTO-01"
    )


def test_json_prints_only_the_result(tmp_path):
    result = regression(tmp_path, *GOLD_DEMO, "--json")
    assert result.exit_code == 4
    parsed = RegressionResult.model_validate_json(result.stdout)
    assert [e.case_id for e in parsed.newly_unsafe] == ["GOLD-TMP-17"]
    assert parsed.verdict == "FAIL"


def test_out_writes_artifacts_that_relay_eval_can_read(tmp_path, smoke_runs):
    out = tmp_path / "report"
    result = regression(
        tmp_path,
        "--dataset",
        SMOKE,
        "--baseline",
        smoke_runs["rules"],
        "--candidate-at",
        "0.5",
        "--out",
        out,
    )
    assert result.exit_code == 0, result.output
    assert (out / "regression.md").read_text(encoding="utf-8") == result.output
    assert json.loads((out / "regression.json").read_text())["dataset_id"] == "smoke-v0.1"
    manifest = json.loads((out / "candidate.manifest.json").read_text())
    assert (manifest["mode"], manifest["source_run_id"]) == ("simulated", smoke_runs["rules"].stem)
    rescored = invoke(
        tmp_path,
        "eval",
        "--dataset",
        SMOKE,
        "--traces",
        out / "candidate.jsonl.gz",
        "--results-dir",
        tmp_path / "results",
    )
    assert rescored.exit_code == 0, rescored.output
    assert "policy v0.1 · dataset smoke-v0.1 · n=10" in rescored.output


# ---- usage errors ----


@pytest.mark.parametrize(
    "flags,message",
    [
        (["--reproduce", "--candidate-at", "0.9"], "cannot be combined"),
        (["--reproduce", "--baseline-at", "0.9"], "cannot be combined"),
        (["--candidate-traces", "BASE", "--candidate-policy", "p"], "choose one candidate source"),
        (["--candidate-policy", "p", "--candidate-latest-policy"], "choose one candidate source"),
        ([], "no candidate"),
        (["--candidate-at", "0"], "--candidate-at must be in (0, 1]"),
        (["--candidate-at", "1.5"], "--candidate-at must be in (0, 1]"),
        (["--reproduce", "--gate", "g"], "--gate needs --config"),
    ],
)
def test_bad_flag_combinations_are_exit_2(tmp_path, smoke_runs, flags, message):
    flags = [str(smoke_runs["rules"]) if f == "BASE" else f for f in flags]
    result = regression(
        tmp_path, "--dataset", SMOKE, "--baseline", smoke_runs["groundtruth"], *flags
    )
    assert result.exit_code == 2, result.output
    assert message in result.output


def test_dataset_and_baseline_are_required_without_config(tmp_path):
    result = regression(tmp_path, "--reproduce")
    assert result.exit_code == 2
    assert "give --dataset and --baseline, or --config" in result.output


def test_a_malformed_waiver_file_is_exit_2(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"waivers": [{"case_id": "GOLD-TMP-17", "gate": "*"}]}')
    result = regression(tmp_path, *GOLD_DEMO, "--waivers", bad)
    assert result.exit_code == 2
    assert "malformed waiver file" in result.output


class NoNetworkClient:
    def __init__(self, *args, **kwargs):
        raise AssertionError("regression constructed a network client")


def test_regression_needs_no_key_and_builds_no_client(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", NoNetworkClient)
    monkeypatch.setattr(cli_module, "AsyncAnthropic", NoNetworkClient)
    assert regression(tmp_path, *GOLD_DEMO).exit_code == 4


# ---- config mode ----


def gates_file(tmp_path, *gates):
    path = tmp_path / "gates.json"
    path.write_text(json.dumps({"gates": list(gates)}), encoding="utf-8")
    return path


def gate(name, baseline, candidate, dataset=SMOKE, **extra):
    return {
        "name": name,
        "dataset": str(dataset),
        "baseline": str(baseline),
        "candidate": candidate,
        **extra,
    }


@pytest.fixture
def three_gates(tmp_path, smoke_runs):
    return gates_file(
        tmp_path,
        gate("smoke-reproduce", smoke_runs["rules"], {"reproduce": True}),
        gate("gold-demo", GOLD_JEV, {"at": 0.89}, dataset=GOLD),
        gate(
            "not-generated",
            smoke_runs["rules"],
            {"reproduce": True},
            dataset=tmp_path / "evals" / "generated" / "nope",
            requires_generated=True,
        ),
    )


def test_config_runs_every_gate_and_exits_with_the_highest_code(tmp_path, three_gates):
    result = regression(tmp_path, "--config", three_gates)
    assert result.exit_code == 4, result.output
    assert "Relay regression — gate smoke-reproduce · dataset smoke-v0.1 · n=10" in result.output
    assert "Relay regression — gate gold-demo · dataset gold-v0.1 · n=100" in result.output
    assert "gate not-generated: SKIPPED (dataset not generated; run relay generate" in result.output
    summary = result.output[result.output.index("REGRESSION GATES") :]
    assert "smoke-reproduce" in summary and "gold-demo" in summary and "SKIPPED" in summary


def test_config_gate_filter(tmp_path, three_gates):
    result = regression(tmp_path, "--config", three_gates, "--gate", "smoke-reproduce")
    assert result.exit_code == 0, result.output
    assert "gold-demo" not in result.output
    unknown = regression(tmp_path, "--config", three_gates, "--gate", "nope")
    assert unknown.exit_code == 2
    assert "no gate named nope" in unknown.output


def test_config_out_writes_one_directory_per_gate_and_a_summary(tmp_path, three_gates):
    out = tmp_path / "regression-report"
    regression(tmp_path, "--config", three_gates, "--out", out)
    assert (out / "smoke-reproduce" / "regression.json").exists()
    assert (out / "gold-demo" / "candidate.jsonl.gz").exists()
    assert not (out / "not-generated").exists()
    assert (out / "summary.md").read_text().startswith("REGRESSION GATES")


def test_a_gate_with_bad_inputs_is_an_error_row_and_the_rest_still_run(tmp_path, smoke_runs):
    path = gates_file(
        tmp_path,
        gate("broken", tmp_path / "missing.jsonl", {"reproduce": True}),
        gate("fine", smoke_runs["rules"], {"reproduce": True}),
    )
    result = regression(tmp_path, "--config", path)
    assert result.exit_code == 2
    assert "Relay regression — gate fine · dataset smoke-v0.1" in result.output
    assert "gate broken: ERROR:" in result.output


def test_config_rejects_single_run_flags(tmp_path, three_gates):
    result = regression(tmp_path, "--config", three_gates, "--dataset", SMOKE)
    assert result.exit_code == 2
    assert "--dataset cannot be combined with --config" in result.output
