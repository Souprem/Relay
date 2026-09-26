"""relay run --workflow shadow --incumbent: the unlabelled agreement section and the
evaluation-only promotion check (PROMOTE exit 0, HOLD exit 4). Offline: smoke runs made in tmp,
and the committed gold traces used as frozen inputs. State files live under tmp_path only."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from relay.cli import app
from relay.traces.store import read_traces
from relay.workflow.status import state_digest

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
GOLD = REPO / "evals" / "gold"
GOLD_RUNS = REPO / "evals" / "baselines" / "gold-v0.1"
GOLD_JEV = GOLD_RUNS / "run_20260925T170857Z_b95be9" / "traces.jsonl.gz"
GOLD_CLAUDE = GOLD_RUNS / "run_20260926T011730Z_f1852f" / "traces.jsonl.gz"
EXAMPLE_WAIVER = REPO / "evals" / "regression" / "examples" / "waiver-tmp17.json"
runner = CliRunner()


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--env-file", str(tmp_path / "missing.env"), *map(str, args)])


def workflow(tmp_path, dataset, kind, *args):
    return invoke(
        tmp_path,
        "run",
        "--dataset",
        dataset,
        "--workflow",
        kind,
        "--traces-dir",
        tmp_path / "traces",
        "--state",
        tmp_path / "state" / "case-status.json",
        *args,
    )


def trace_file_of(result) -> Path:
    line = next(x for x in result.output.splitlines() if x.startswith("Traces: "))
    return Path(line.removeprefix("Traces: "))


@pytest.fixture(scope="module")
def smoke_runs(tmp_path_factory):
    root = tmp_path_factory.mktemp("shadow-compare-smoke")
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


# ---- smoke: agreement numbers against a hand computation ----


def test_smoke_agreement_matches_a_hand_computation(tmp_path, smoke_runs):
    sim = workflow(tmp_path, SMOKE, "simulated", "--from-traces", smoke_runs["groundtruth"])
    assert sim.exit_code == 0, sim.output
    incumbent_file = trace_file_of(sim)
    digest = state_digest(tmp_path / "state" / "case-status.json")
    result = workflow(
        tmp_path,
        SMOKE,
        "shadow",
        "--from-traces",
        smoke_runs["rules"],
        "--incumbent",
        incumbent_file,
    )
    assert result.exit_code == 0, result.output
    assert state_digest(tmp_path / "state" / "case-status.json") == digest
    before = {t.case_id: t.action.value for t in read_traces(incumbent_file)}
    after = {t.case_id: t.action.value for t in read_traces(trace_file_of(result))}
    agreed = sum(before[c] == after[c] for c in before)
    newly = sorted(c for c in before if after[c] == "AUTO_PROCESS" != before[c])
    stopped = sorted(c for c in before if before[c] == "AUTO_PROCESS" != after[c])
    lines = result.output.splitlines()
    assert any(x.startswith(f"  Action agreement: {agreed}/10 ") for x in lines)
    assert f"  Would newly auto-process ({len(newly)}): {', '.join(newly) or 'none'}" in lines
    assert f"  Would stop auto-processing ({len(stopped)}): {', '.join(stopped) or 'none'}" in lines
    header = "INCUMBENT \\ CANDIDATE"
    row = next(i for i, x in enumerate(lines) if x.strip().startswith(header))
    for offset, action in enumerate(("AUTO_PROCESS", "REQUEST_INFO", "HUMAN_REVIEW"), start=1):
        counts = [
            sum(before[c] == action and after[c] == other for c in before)
            for other in ("AUTO_PROCESS", "REQUEST_INFO", "HUMAN_REVIEW")
        ]
        assert lines[row + offset].split() == [action, *map(str, counts)]
    assert "EVALUATION-ONLY (uses ground truth; not available in a real shadow deployment)" in lines
    assert lines[-1].startswith("PROMOTION CHECK: ")


def test_smoke_hard_coded_agreement(tmp_path, smoke_runs):
    """The same comparison with its numbers pinned, so a silent change in either provider or in
    the agreement arithmetic is caught."""
    sim = workflow(tmp_path, SMOKE, "simulated", "--from-traces", smoke_runs["groundtruth"])
    result = workflow(
        tmp_path,
        SMOKE,
        "shadow",
        "--from-traces",
        smoke_runs["rules"],
        "--incumbent",
        trace_file_of(sim),
    )
    lines = result.output.splitlines()
    assert "  Action agreement: 9/10 (90.0%)  95% CI [55.5%, 99.7%]" in lines
    assert "  Would newly auto-process (0): none" in lines
    assert "  Would stop auto-processing (1): AUTO-03" in lines
    assert (result.exit_code, lines[-1]) == (0, "PROMOTION CHECK: PROMOTE")


# ---- gold: the two README demos ----


def test_gold_claude_at_0_55_shadowing_jev_at_0_89_is_promoted(tmp_path):
    sim = workflow(tmp_path, GOLD, "simulated", "--from-traces", GOLD_JEV, "--at", "0.89")
    assert sim.exit_code == 0, sim.output
    assert "AUTO_APPROVED 29 · INFO_REQUESTED 32 · IN_HUMAN_REVIEW 39" in sim.output
    result = workflow(
        tmp_path,
        GOLD,
        "shadow",
        "--from-traces",
        GOLD_CLAUDE,
        "--at",
        "0.55",
        "--incumbent",
        trace_file_of(sim),
    )
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert "  Action agreement: 96/100 (96.0%)  95% CI [90.1%, 98.9%]" in lines
    assert "  Would newly auto-process (2): GOLD-MIS-17, GOLD-TMP-15" in lines
    assert "  Would stop auto-processing (1): GOLD-TMP-18" in lines
    assert (
        "CHANGES: improved 3 · unchanged 96 · regressed 1 · changed-both-wrong 0 · not identical 100"
        in lines
    )
    assert "STILL UNSAFE (1) — also unsafe in the baseline; not a gate failure" in lines
    assert "NEWLY UNSAFE" not in result.output
    assert lines[-3:] == ["REGRESSION GATE: PASS", "", "PROMOTION CHECK: PROMOTE"]


def test_gold_jev_at_0_89_shadowing_jev_at_0_95_is_held_on_gold_tmp_17(tmp_path):
    sim = workflow(tmp_path, GOLD, "simulated", "--from-traces", GOLD_JEV)
    assert sim.exit_code == 0, sim.output
    incumbent_file = trace_file_of(sim)
    result = workflow(
        tmp_path,
        GOLD,
        "shadow",
        "--from-traces",
        GOLD_JEV,
        "--at",
        "0.89",
        "--incumbent",
        incumbent_file,
    )
    assert result.exit_code == 4, result.output
    lines = result.output.splitlines()
    shadow_file = trace_file_of(result)
    assert (
        "SHADOW: Would auto-process GOLD-TMP-17; no action was taken. (current status: "
        f"IN_HUMAN_REVIEW by {incumbent_file.stem})"
    ) in lines
    assert "NEWLY UNSAFE (1)" in lines
    assert (
        f"      replay: relay replay GOLD-TMP-17 --traces {incumbent_file} --dataset {GOLD} "
        f"--candidate-traces {shadow_file}"
    ) in lines
    assert lines[-1] == (
        "PROMOTION CHECK: HOLD — 1 newly unsafe case(s) without a waiver: GOLD-TMP-17"
    )


def test_an_evaluate_run_can_be_the_incumbent_and_waivers_pass_through(tmp_path):
    base = ["--from-traces", GOLD_JEV, "--at", "0.89", "--incumbent", GOLD_JEV]
    held = workflow(tmp_path, GOLD, "shadow", *base)
    assert held.exit_code == 4, held.output
    assert "INCUMBENT evaluate run_20260925T170857Z_b95be9 · jev q-v0.2" in held.output
    waived = workflow(tmp_path, GOLD, "shadow", *base, "--waivers", EXAMPLE_WAIVER)
    assert waived.exit_code == 0, waived.output
    assert "WAIVED NEWLY UNSAFE (1) — reviewed, not failures" in waived.output
    assert waived.output.splitlines()[-1] == "PROMOTION CHECK: PROMOTE"
    too_many = workflow(
        tmp_path, GOLD, "shadow", *base, "--waivers", EXAMPLE_WAIVER, "--max-regressed", "0"
    )
    assert too_many.exit_code == 4
    assert too_many.output.splitlines()[-1] == (
        "PROMOTION CHECK: HOLD — 1 regressed case(s), more than --max-regressed 0"
    )


def test_out_writes_the_shadow_report(tmp_path):
    out = tmp_path / "report"
    result = workflow(
        tmp_path,
        GOLD,
        "shadow",
        "--from-traces",
        GOLD_JEV,
        "--at",
        "0.89",
        "--incumbent",
        GOLD_JEV,
        "--out",
        out,
    )
    assert result.exit_code == 4, result.output
    assert f"Shadow report: {out / 'shadow.json'}, {out / 'shadow.md'}" in result.output
    report = json.loads((out / "shadow.json").read_text())
    assert (report["decision"], report["exit_code"], report["n"]) == ("HOLD", 4, 100)
    assert report["agreement"]["newly_auto"][:2] == ["GOLD-MIS-19", "GOLD-STR-01"]
    assert report["agreement"]["matrix"]["HUMAN_REVIEW"]["AUTO_PROCESS"] == 11
    assert [e["case_id"] for e in report["promotion"]["newly_unsafe"]] == ["GOLD-TMP-17"]
    markdown = (out / "shadow.md").read_text()
    assert markdown.startswith("Relay shadow comparison — dataset gold-v0.1 · n=100\n")
    assert result.output.endswith(markdown)


# ---- incumbent and flag errors ----


def test_a_shadow_run_cannot_be_the_incumbent(tmp_path, smoke_runs):
    shadow = workflow(tmp_path, SMOKE, "shadow", "--from-traces", smoke_runs["rules"])
    assert shadow.exit_code == 0, shadow.output
    runs_before = sorted((tmp_path / "traces").glob("*.jsonl"))
    result = workflow(
        tmp_path,
        SMOKE,
        "shadow",
        "--from-traces",
        smoke_runs["rules"],
        "--incumbent",
        trace_file_of(shadow),
    )
    assert result.exit_code == 2
    assert "is a shadow run; the incumbent must be a simulated or evaluate run" in result.output
    assert sorted((tmp_path / "traces").glob("*.jsonl")) == runs_before


def test_an_incumbent_on_other_cases_is_refused_before_the_run(tmp_path, smoke_runs):
    result = workflow(
        tmp_path, SMOKE, "shadow", "--from-traces", smoke_runs["rules"], "--incumbent", GOLD_JEV
    )
    assert result.exit_code == 2
    assert f"--incumbent {GOLD_JEV}" in result.output
    assert not (tmp_path / "traces").exists()


@pytest.mark.parametrize(
    "args,message",
    [
        (
            ["--workflow", "simulated", "--from-traces", "{gt}", "--incumbent", "{gt}"],
            "--incumbent applies only to --workflow shadow",
        ),
        (
            ["--workflow", "shadow", "--from-traces", "{gt}", "--out", "o"],
            "--out needs --incumbent",
        ),
        (
            ["--workflow", "shadow", "--from-traces", "{gt}", "--max-regressed", "0"],
            "--max-regressed needs --incumbent",
        ),
        (["--incumbent", "{gt}"], "--incumbent needs --workflow"),
    ],
)
def test_comparison_flag_errors(tmp_path, smoke_runs, args, message):
    args = [a.replace("{gt}", str(smoke_runs["groundtruth"])) for a in args]
    result = invoke(tmp_path, "run", "--dataset", SMOKE, "--traces-dir", tmp_path / "traces", *args)
    assert result.exit_code == 2
    assert message in result.output
    assert not (tmp_path / "traces").exists()
