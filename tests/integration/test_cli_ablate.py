"""relay ablate, offline: smoke runs from the groundtruth provider, a doctored copy with one
provider mistake, and the regression gate over the ablated bundle. Never builds a client."""

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

import relay.cli as cli_module
from relay.cases.loader import load_dataset
from relay.cases.policies import load_policy
from relay.cli import app
from relay.evaluation.tracediff import replay_trace
from relay.traces.models import RunManifest
from relay.traces.store import read_traces
from relay.workflow.outcomes import WorkflowAction
from tests.factories import make_bundle

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
runner = CliRunner()


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--env-file", str(tmp_path / "missing.env"), *map(str, args)])


class NoClient:
    def __init__(self, *args, **kwargs):
        raise AssertionError("relay ablate must not build a network client")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", NoClient)
    monkeypatch.setattr(cli_module, "AsyncAnthropic", NoClient)


@pytest.fixture(scope="module")
def groundtruth_run(tmp_path_factory):
    root = tmp_path_factory.mktemp("ablate-cli")
    result = invoke(
        root,
        "run",
        "--dataset",
        SMOKE,
        "--provider",
        "groundtruth",
        "--traces-dir",
        root / "traces",
        "--reports-dir",
        root / "reports",
    )
    assert result.exit_code == 0, result.output
    [trace_file] = (root / "traces").glob("*.jsonl")
    return trace_file


@pytest.fixture(scope="module")
def mistaken_run(groundtruth_run, tmp_path_factory):
    """The groundtruth run with one provider mistake: ADV-01 (a material contradiction; step
    therapy is NOT satisfied) judged all-high except contradiction p=0.9. Only the contradiction
    gate keeps it from AUTO_PROCESS."""
    root = tmp_path_factory.mktemp("ablate-mistaken")
    cases = {c.input.id: c for c in load_dataset(SMOKE)}
    policy = load_policy("immunara-v0.1")
    traces = []
    for trace in read_traces(groundtruth_run):
        if trace.case_id == "ADV-01":
            doctored = trace.model_copy(update={"decisions": make_bundle("ADV-01", contra=0.9)})
            trace = replay_trace(
                doctored,
                cases["ADV-01"],
                policy=policy,
                thresholds=trace.thresholds,
                git_sha="test",
                mode="evaluate",
                run_id=trace.run_id,
            ).model_copy(update={"replay_of": None})
        traces.append(trace)
    path = root / "mistaken.jsonl"
    path.write_text("".join(t.model_dump_json() + "\n" for t in traces), encoding="utf-8")
    return path


def ablate(tmp_path, traces, disable, name, *extra):
    return invoke(
        tmp_path,
        "ablate",
        "--traces",
        traces,
        "--dataset",
        SMOKE,
        "--disable",
        disable,
        "--out",
        tmp_path / name,
        *extra,
    )


def test_ablate_writes_a_simulated_bundle(tmp_path, groundtruth_run):
    result = ablate(tmp_path, groundtruth_run, "contradiction,missing_evidence", "both")
    assert result.exit_code == 0, result.output
    source = read_traces(groundtruth_run)
    assert (
        f"Ablated run {source[0].run_id} (groundtruth groundtruth): "
        "contradiction+missing_evidence disabled at auto_process=0.95, thresholds v0.1: "
        "action changed on 0 of 10 case(s) versus the same run at the same threshold."
    ) in result.output
    out = read_traces(tmp_path / "both" / "traces.jsonl.gz")
    assert [t.case_id for t in out] == [t.case_id for t in source]
    assert {tuple(t.ablation) for t in out} == {("contradiction", "missing_evidence")}
    assert {t.mode for t in out} == {"simulated"}
    raw = json.loads((tmp_path / "both" / "run-manifest.json").read_text())
    manifest = RunManifest.model_validate(raw)
    assert (manifest.mode, manifest.source_run_id, manifest.ablation) == (
        "simulated",
        source[0].run_id,
        ["contradiction", "missing_evidence"],
    )
    assert (raw["auto_process"], raw["thresholds"]["version"], raw["policy_id"]) == (
        0.95,
        "v0.1",
        "immunara-v0.1",
    )
    assert f"Simulated run: {out[0].run_id}" in result.output


def test_at_applies_the_operating_point(tmp_path, groundtruth_run):
    result = ablate(tmp_path, groundtruth_run, "missing_evidence", "me", "--at", "0.9")
    assert result.exit_code == 0, result.output
    assert "missing_evidence disabled at auto_process=0.9, thresholds v0.1+at0.9" in result.output
    raw = json.loads((tmp_path / "me" / "run-manifest.json").read_text())
    assert (raw["auto_process"], raw["ablation"]) == (0.9, ["missing_evidence"])


def test_a_contradiction_ablation_makes_a_newly_unsafe_case_the_gate_reports(
    tmp_path, mistaken_run
):
    result = ablate(tmp_path, mistaken_run, "contradiction", "contra")
    assert result.exit_code == 0, result.output
    assert "action changed on 1 of 10 case(s)" in result.output
    [adv] = [
        t for t in read_traces(tmp_path / "contra" / "traces.jsonl.gz") if t.case_id == "ADV-01"
    ]
    assert adv.action is WorkflowAction.AUTO_PROCESS
    gate = invoke(
        tmp_path,
        "regression",
        "--dataset",
        SMOKE,
        "--baseline",
        mistaken_run,
        "--candidate-traces",
        tmp_path / "contra" / "traces.jsonl.gz",
        "--out",
        tmp_path / "contra",
    )
    assert gate.exit_code == 4, gate.output
    assert "· ablate=contradiction" in gate.output
    assert gate.output.splitlines()[-1] == (
        "REGRESSION GATE: FAIL — 1 newly unsafe case(s) without a waiver: ADV-01"
    )
    verdict = json.loads((tmp_path / "contra" / "regression.json").read_text())
    assert [e["case_id"] for e in verdict["newly_unsafe"]] == ["ADV-01"]


def test_an_ablated_bundle_reproduces(tmp_path, mistaken_run):
    assert ablate(tmp_path, mistaken_run, "contradiction", "contra").exit_code == 0
    trace_file = tmp_path / "contra" / "traces.jsonl.gz"
    gate = invoke(
        tmp_path, "regression", "--dataset", SMOKE, "--baseline", trace_file, "--reproduce"
    )
    assert gate.exit_code == 0, gate.output
    replay = invoke(tmp_path, "replay", "ADV-01", "--traces", trace_file, "--dataset", SMOKE)
    assert replay.exit_code == 0, replay.output
    assert "ABLATION: contradiction (both sides)" in replay.output


def test_a_re_decided_ablated_candidate_keeps_its_ablation(tmp_path, mistaken_run):
    assert ablate(tmp_path, mistaken_run, "contradiction", "contra").exit_code == 0
    gate = invoke(
        tmp_path,
        "regression",
        "--dataset",
        SMOKE,
        "--baseline",
        mistaken_run,
        "--candidate-traces",
        tmp_path / "contra" / "traces.jsonl.gz",
        "--candidate-at",
        "0.9",
        "--out",
        tmp_path / "gate",
    )
    assert gate.exit_code == 4, gate.output
    raw = json.loads((tmp_path / "gate" / "candidate.manifest.json").read_text())
    assert raw["ablation"] == ["contradiction"]


def test_a_sampled_run_is_ablated_on_its_own_sample(tmp_path):
    run = invoke(
        tmp_path,
        "run",
        "--dataset",
        SMOKE,
        "--provider",
        "groundtruth",
        "--limit",
        "5",
        "--sample-seed",
        "7",
        "--traces-dir",
        tmp_path / "traces",
        "--reports-dir",
        tmp_path / "reports",
    )
    assert run.exit_code == 0, run.output
    [trace_file] = (tmp_path / "traces").glob("*.jsonl")
    result = ablate(tmp_path, trace_file, "contradiction", "sampled")
    assert result.exit_code == 0, result.output
    assert "action changed on 0 of 5 case(s)" in result.output
    manifest = RunManifest.model_validate_json(
        (tmp_path / "sampled" / "run-manifest.json").read_text()
    )
    assert (manifest.case_count, manifest.sample_limit, manifest.sample_seed) == (5, 5, 7)


@pytest.mark.parametrize(
    "args,message",
    [
        (["--disable", "age"], "cannot disable ['age']"),
        (["--disable", ""], "give gate names separated by commas"),
        (["--disable", "contradiction", "--at", "0"], "--at must be > 0"),
    ],
)
def test_bad_flags_are_exit_2(tmp_path, groundtruth_run, args, message):
    result = invoke(
        tmp_path,
        "ablate",
        "--traces",
        groundtruth_run,
        "--dataset",
        SMOKE,
        "--out",
        tmp_path / "x",
        *args,
    )
    assert result.exit_code == 2
    assert message in result.output
    assert not (tmp_path / "x").exists()


def test_input_refusals_are_exit_2(tmp_path, groundtruth_run):
    assert ablate(tmp_path, groundtruth_run, "contradiction", "once").exit_code == 0
    again = ablate(tmp_path, groundtruth_run, "contradiction", "once")
    assert again.exit_code == 2 and "is not empty" in again.output
    twice = ablate(tmp_path, tmp_path / "once" / "traces.jsonl.gz", "missing_evidence", "twice")
    assert twice.exit_code == 2 and "is already ablated" in twice.output
    other = tmp_path / "other"
    shutil.copytree(SMOKE / "AUTO-01", other / "AUTO-01")
    partial = invoke(
        tmp_path,
        "ablate",
        "--traces",
        groundtruth_run,
        "--dataset",
        other,
        "--disable",
        "contradiction",
        "--out",
        tmp_path / "partial",
    )
    assert partial.exit_code == 2 and "trace for unknown case" in partial.output
