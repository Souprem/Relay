"""run_regression over real committed traces and fresh offline smoke runs (no network)."""

import gzip
import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from relay.cli import app
from relay.evaluation.regression_run import (
    CandidateSpec,
    RegressionInputError,
    RegressionRequest,
    find_run_manifest,
    load_gates,
    load_waivers,
    replay_command_for,
    run_regression,
    validate_request,
    write_outputs,
)
from relay.traces.store import read_traces
from relay.workflow.outcomes import WorkflowAction

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
GOLD = REPO / "evals" / "gold"
GOLD_RUNS = REPO / "evals" / "baselines" / "gold-v0.1"
GOLD_JEV = GOLD_RUNS / "run_20260925T170857Z_b95be9" / "traces.jsonl.gz"
GOLD_CLAUDE = GOLD_RUNS / "run_20260926T011730Z_f1852f" / "traces.jsonl.gz"


def smoke_run(root: Path, provider: str, *extra: str) -> Path:
    result = CliRunner().invoke(
        app,
        [
            "--env-file",
            str(root / "missing.env"),
            "run",
            "--dataset",
            str(SMOKE),
            "--provider",
            provider,
            "--traces-dir",
            str(root / provider / "traces"),
            "--reports-dir",
            str(root / provider / "reports"),
            *extra,
        ],
    )
    assert result.exit_code == 0, result.output
    [path] = (root / provider / "traces").glob("*.jsonl")
    return path


@pytest.fixture(scope="module")
def smoke(tmp_path_factory):
    root = tmp_path_factory.mktemp("regression-smoke")
    return {p: smoke_run(root, p) for p in ("groundtruth", "rules")}


# ---- request validation (spec G2) ----


@pytest.mark.parametrize(
    "candidate,baseline_at,message",
    [
        (CandidateSpec(traces="t", policy="p"), None, "choose one candidate source"),
        (CandidateSpec(policy="p", latest_policy=True), None, "choose one candidate source"),
        (CandidateSpec(traces="t", reproduce=True), None, "choose one candidate source"),
        (CandidateSpec(reproduce=True, at=0.9), None, "cannot be combined"),
        (CandidateSpec(reproduce=True), 0.9, "cannot be combined"),
        (CandidateSpec(), None, "no candidate"),
        (CandidateSpec(at=0.0), None, "--candidate-at must be in (0, 1]"),
        (CandidateSpec(at=1.5), None, "--candidate-at must be in (0, 1]"),
        (CandidateSpec(at=0.9), -0.1, "--baseline-at must be in (0, 1]"),
    ],
)
def test_invalid_candidate_sources_are_input_errors(candidate, baseline_at, message):
    with pytest.raises(RegressionInputError, match=re.escape(message)):
        validate_request(candidate, baseline_at)


@pytest.mark.parametrize(
    "candidate",
    [
        CandidateSpec(traces="t"),
        CandidateSpec(traces="t", at=0.5),
        CandidateSpec(policy="p", at=0.5),
        CandidateSpec(latest_policy=True),
        CandidateSpec(at=1.0),
        CandidateSpec(reproduce=True),
    ],
)
def test_valid_candidate_sources(candidate):
    validate_request(candidate, None)


# ---- run manifests and sampling ----


def test_run_manifests_are_found_for_every_trace_file_layout(smoke, tmp_path):
    assert find_run_manifest(GOLD_JEV).run_id == "run_20260925T170857Z_b95be9"
    assert find_run_manifest(smoke["rules"]).run_id == smoke["rules"].stem
    assert find_run_manifest(tmp_path / "loose.jsonl") is None


def test_a_mismatched_run_manifest_is_an_input_error(smoke, tmp_path):
    """M9: a run-manifest.json beside a trace file is otherwise trusted without checking it
    actually describes that trace file, which would subsample against the wrong manifest."""
    trace = smoke["rules"]
    manifest_path = trace.with_suffix(".manifest.json")
    mismatched = tmp_path / trace.name
    mismatched.write_bytes(trace.read_bytes())
    bad_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bad_manifest["run_id"] = "not-the-real-run-id"
    (tmp_path / manifest_path.name).write_text(json.dumps(bad_manifest), encoding="utf-8")
    with pytest.raises(RegressionInputError, match="does not match"):
        run_regression(
            RegressionRequest(dataset=SMOKE, baseline=mismatched, candidate=CandidateSpec(at=0.9))
        )


def test_a_sampled_baseline_is_paired_with_its_sample(tmp_path):
    sampled = smoke_run(tmp_path, "groundtruth", "--limit", "4", "--sample-seed", "3")
    run = run_regression(
        RegressionRequest(dataset=SMOKE, baseline=sampled, candidate=CandidateSpec(reproduce=True))
    )
    assert run.result.n == 4
    assert run.result.verdict == "PASS"


# ---- the gold demonstration and a committed-provider comparison ----


def test_gold_jev_at_its_dev_threshold_is_newly_unsafe_on_gold_tmp_17():
    run = run_regression(
        RegressionRequest(dataset=GOLD, baseline=GOLD_JEV, candidate=CandidateSpec(at=0.89))
    )
    result = run.result
    assert (result.verdict, result.exit_code) == ("FAIL", 4)
    assert [e.case_id for e in result.newly_unsafe] == ["GOLD-TMP-17"]
    assert result.failures == ["1 newly unsafe case(s) without a waiver: GOLD-TMP-17"]
    assert result.newly_unsafe[0].replay_command == (
        f"relay replay GOLD-TMP-17 --traces {GOLD_JEV} --dataset {GOLD} --at 0.89"
    )
    assert result.candidate.identity.thresholds_versions == ["v0.1+at0.89"]


def test_claude_is_not_an_unsafe_regression_versus_jev_on_gold():
    run = run_regression(
        RegressionRequest(
            dataset=GOLD,
            baseline=GOLD_JEV,
            baseline_at=0.89,
            candidate=CandidateSpec(traces=str(GOLD_CLAUDE), at=0.55),
            gate="gold-jev-vs-claude",
        )
    )
    result = run.result
    assert (result.verdict, result.exit_code) == ("PASS", 0)
    assert result.change_counts == {
        "improved": 3,
        "unchanged": 96,
        "regressed": 1,
        "changed-both-wrong": 0,
    }
    assert result.newly_unsafe == [] and result.waived == []
    assert result.baseline.label.startswith("replay-run_20260925T170857Z_b95be9 · jev")
    assert result.candidate.label.endswith("· re-decided at auto_process=0.55")
    # the re-decided baseline exists only with --out, so no replay command without it
    assert result.regressed[0].replay_command is None
    # I1: both Jev at 0.89 and Claude at 0.55 automate GOLD-TMP-17 unsafely, so it is invisible
    # to newly_unsafe (the gate is relative to the baseline) but must show up as still_unsafe.
    assert [e.case_id for e in result.still_unsafe] == ["GOLD-TMP-17"]
    still = result.still_unsafe[0]
    assert (still.action_baseline, still.action_candidate) == (
        WorkflowAction.AUTO_PROCESS,
        WorkflowAction.AUTO_PROCESS,
    )
    assert still.expected == WorkflowAction.HUMAN_REVIEW


def test_a_mismatched_candidate_run_is_an_input_error(smoke, tmp_path):
    *kept, dropped = read_traces(smoke["rules"])
    short = tmp_path / "short.jsonl"
    short.write_text("".join(t.model_dump_json() + "\n" for t in kept), encoding="utf-8")
    with pytest.raises(RegressionInputError, match=re.escape(f"missing ['{dropped.case_id}']")):
        run_regression(
            RegressionRequest(
                dataset=SMOKE,
                baseline=smoke["groundtruth"],
                candidate=CandidateSpec(traces=str(short)),
            )
        )


def test_an_unknown_candidate_policy_is_an_input_error(smoke):
    with pytest.raises(RegressionInputError, match="unknown policy 'nope-v1'"):
        run_regression(
            RegressionRequest(
                dataset=SMOKE, baseline=smoke["rules"], candidate=CandidateSpec(policy="nope-v1")
            )
        )


# ---- replay commands ----


def test_replay_commands_need_out_only_for_re_decided_runs(tmp_path):
    def command(candidate, baseline_at=None, out=None):
        request = RegressionRequest(
            dataset=Path("ds"),
            baseline=Path("b.jsonl"),
            candidate=candidate,
            baseline_at=baseline_at,
        )
        return replay_command_for(request, out)("C-1")

    head = "relay replay C-1 --traces b.jsonl --dataset ds"
    assert command(CandidateSpec(reproduce=True)) == head
    assert command(CandidateSpec(traces="c.jsonl")) == f"{head} --candidate-traces c.jsonl"
    assert command(CandidateSpec(policy="p", at=0.9)) == f"{head} --policy p --at 0.9"
    assert command(CandidateSpec(latest_policy=True)) == f"{head} --latest-policy"
    assert command(CandidateSpec(traces="c.jsonl", at=0.5)) is None
    assert command(CandidateSpec(traces="c.jsonl", at=0.5), out=tmp_path) == (
        f"{head} --candidate-traces {tmp_path / 'candidate.jsonl.gz'}"
    )
    assert command(CandidateSpec(at=0.9), baseline_at=0.8) is None
    assert command(CandidateSpec(at=0.9), baseline_at=0.8, out=tmp_path) == (
        f"relay replay C-1 --traces {tmp_path / 'baseline.jsonl.gz'} --dataset ds "
        f"--candidate-traces {tmp_path / 'candidate.jsonl.gz'}"
    )


# ---- artifacts ----


def test_write_outputs_writes_the_result_and_the_simulated_runs(tmp_path):
    request = RegressionRequest(
        dataset=GOLD,
        baseline=GOLD_JEV,
        baseline_at=0.95,
        candidate=CandidateSpec(at=0.89),
    )
    run = run_regression(request, out=tmp_path)
    paths = write_outputs(tmp_path, run, request, "rendered text")
    assert sorted(p.name for p in paths) == [
        "baseline.jsonl.gz",
        "baseline.manifest.json",
        "candidate.jsonl.gz",
        "candidate.manifest.json",
        "regression.json",
        "regression.md",
    ]
    assert (tmp_path / "regression.md").read_text() == "rendered text\n"
    assert json.loads((tmp_path / "regression.json").read_text())["verdict"] == "FAIL"
    candidate = read_traces(tmp_path / "candidate.jsonl.gz")
    assert len(candidate) == 100 and {t.mode for t in candidate} == {"simulated"}
    manifest = json.loads((tmp_path / "candidate.manifest.json").read_text())
    assert manifest["mode"] == "simulated"
    assert manifest["source_run_id"] == "run_20260925T170857Z_b95be9"
    assert manifest["policy_id"] == "immunara-v0.1"
    assert manifest["thresholds"]["version"] == "v0.1+at0.89"
    loaded = find_run_manifest(tmp_path / "candidate.jsonl.gz")
    assert loaded.case_count == 100
    # 3C: mode and source_run_id are typed fields now, so they survive a round-trip (3B M8).
    assert (loaded.mode, loaded.source_run_id) == ("simulated", "run_20260925T170857Z_b95be9")
    with gzip.open(tmp_path / "baseline.jsonl.gz", "rt") as handle:
        assert len(handle.read().splitlines()) == 100


def test_a_reproduce_or_recorded_candidate_writes_no_trace_files(smoke, tmp_path):
    request = RegressionRequest(
        dataset=SMOKE, baseline=smoke["rules"], candidate=CandidateSpec(reproduce=True)
    )
    paths = write_outputs(tmp_path, run_regression(request), request, "x")
    assert sorted(p.name for p in paths) == ["regression.json", "regression.md"]


# ---- waiver and gates files ----


def test_a_malformed_waiver_file_is_an_input_error(tmp_path):
    path = tmp_path / "w.json"
    path.write_text('{"waivers": [{"case_id": "A"}]}')
    with pytest.raises(RegressionInputError, match="malformed waiver file"):
        load_waivers(path)
    path.write_text("not json")
    with pytest.raises(RegressionInputError, match="malformed waiver file"):
        load_waivers(path)


def test_a_gates_file_is_validated(tmp_path):
    path = tmp_path / "gates.json"
    gate = {"name": "g", "dataset": "d", "baseline": "b", "candidate": {"reproduce": True}}
    path.write_text(json.dumps({"gates": [gate]}))
    assert load_gates(path).gates[0].candidate.reproduce is True
    path.write_text(json.dumps({"gates": [gate, gate]}))
    with pytest.raises(RegressionInputError, match="duplicate gate names"):
        load_gates(path)
    bad = dict(gate, candidate={"reproduce": True, "at": 0.9})
    path.write_text(json.dumps({"gates": [bad]}))
    with pytest.raises(RegressionInputError, match="gate g: --reproduce"):
        load_gates(path)
    path.write_text(json.dumps({"gates": [dict(gate, surprise=1)]}))
    with pytest.raises(RegressionInputError, match="malformed gates file"):
        load_gates(path)
