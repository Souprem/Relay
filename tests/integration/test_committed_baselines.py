"""C5: a drift guard. Re-score each committed evals/baselines/gen-v0.2-* run offline against its
generated dataset on disk, and assert key metrics still match the committed results.json.

This does not call any provider: it replays the committed traces.jsonl.gz through the current
scoring code. If it ever fails, either the engine/labels changed in a way that reinterprets old
decisions, or a committed baseline was hand-edited — both worth stopping for.

Skips cleanly (not a failure) when the corresponding generated dataset directory is absent, since
`evals/generated/<dataset-id>/` is git-ignored and only exists after `relay generate` has been run
(or the case folders were otherwise materialized) locally.

Committed gold runs under evals/baselines/gold-v0.1/ are re-scored against the tracked evals/gold.

Phase 3A adds a reproduce guard beside it: every committed gold trace, for all four providers, must
replay through today's engine with the same action, reasons and gate path (`relay replay`'s
REPRODUCED). A failure there is ENGINE DRIFT: the engine now reinterprets stored decisions.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import relay.evaluation.tracediff as tracediff
from relay.cases.loader import CaseLoadError, load_dataset
from relay.cases.policies import load_policy
from relay.cli import app
from relay.evaluation.metrics import score_run
from relay.evaluation.runner import sample_cases
from relay.evaluation.tracediff import (
    REPRODUCE_LABEL,
    diff_case,
    original_label,
    replay_exit_code,
    replay_trace,
)
from relay.reporting import REPRODUCED_LINE
from relay.traces.store import read_traces

REPO = Path(__file__).resolve().parents[2]
BASELINES = REPO / "evals" / "baselines"
GENERATED = REPO / "evals" / "generated"

# Committed datasets whose case folders are tracked (not regenerated).
DATASET_DIRS: dict[str, Path] = {"gold-v0.1": REPO / "evals" / "gold"}

# Every committed gen-v0.2-* / gen-v0.3-* and gold run directory: (dataset_id, run_dir). A
# directory counts when it holds traces.jsonl.gz (a regression --out directory does not).
RUN_DIRS: list[tuple[str, Path]] = sorted(
    (dataset_dir.name, run_dir)
    for dataset_dir in [
        *BASELINES.glob("gen-v0.2-*"),
        *BASELINES.glob("gen-v0.3-*"),
        BASELINES / "gold-v0.1",
    ]
    if dataset_dir.is_dir()
    for run_dir in dataset_dir.iterdir()
    if run_dir.is_dir() and (run_dir / "traces.jsonl.gz").is_file()
)

KEY_METRICS = (
    "correct_actions",
    "auto_process_count",
    "unsafe_automation_count",
    "invalid_outputs",
    "per_question_accuracy",
)


@pytest.mark.parametrize("dataset_id,run_dir", RUN_DIRS, ids=[f"{d}/{r.name}" for d, r in RUN_DIRS])
def test_committed_baseline_rescoring_matches_results_json(dataset_id, run_dir):
    dataset_dir = DATASET_DIRS.get(dataset_id, GENERATED / dataset_id)
    if not dataset_dir.exists():
        pytest.skip(f"{dataset_dir} is not on disk; run `relay generate` to materialize it")
    [trace_path] = run_dir.glob("traces.jsonl.gz")
    results_path = run_dir / "results.json"
    committed = json.loads(results_path.read_text())

    try:
        cases = load_dataset(dataset_dir)
    except CaseLoadError as error:
        pytest.skip(f"{dataset_dir}: {error}")
    manifest = json.loads((run_dir / "run-manifest.json").read_text())
    if manifest.get("sample_limit") is not None:  # a --limit/--sample-seed run (2D latency sample)
        cases = sample_cases(cases, manifest["sample_limit"], manifest["sample_seed"])
    traces = read_traces(trace_path)
    fresh = score_run(traces, cases)

    for field in KEY_METRICS:
        assert getattr(fresh, field) == committed[field], (
            f"{run_dir.name}: {field} drifted from the committed baseline"
        )


# ---- Phase 3A: committed gold traces must still reproduce under today's engine ----

GOLD_TRACE_FILES: list[Path] = sorted((BASELINES / "gold-v0.1").glob("run_*/traces.jsonl.gz"))
GOLD_JEV_TRACES = BASELINES / "gold-v0.1" / "run_20260925T170857Z_b95be9" / "traces.jsonl.gz"


def test_the_gold_reproduce_guard_covers_all_four_providers():
    providers = {read_traces(path)[0].provider for path in GOLD_TRACE_FILES}
    assert providers == {"groundtruth", "rules", "jev", "claude"}


def drifted_cases(trace_path: Path) -> list[str]:
    """Case ids whose committed trace today's engine no longer reproduces (reproduce mode:
    stored decisions, the trace's own policy and thresholds)."""
    cases = {c.input.id: c for c in load_dataset(DATASET_DIRS["gold-v0.1"])}
    drifted = []
    for trace in read_traces(trace_path):
        case = cases[trace.case_id]
        policy = load_policy(trace.policy_id)
        replayed = replay_trace(
            trace, case, policy=policy, thresholds=trace.thresholds, git_sha="guard"
        )
        diff = diff_case(
            trace,
            replayed,
            case,
            original_label=original_label(trace),
            candidate_label=REPRODUCE_LABEL,
            policies={policy.id: policy},
        )
        if replay_exit_code(diff, reproduce=True) != 0:
            drifted.append(trace.case_id)
    return drifted


@pytest.mark.parametrize("trace_path", GOLD_TRACE_FILES, ids=lambda p: p.parent.name)
def test_every_committed_gold_trace_reproduces(trace_path):
    assert len(read_traces(trace_path)) == 100
    drifted = drifted_cases(trace_path)
    assert drifted == [], f"{trace_path.parent.name}: ENGINE DRIFT on {drifted}"


def test_the_reproduce_guard_detects_engine_drift(monkeypatch):
    real = tracediff.determine_action

    def drifted_engine(case, bundle, policy, thresholds):
        outcome = real(case, bundle, policy, thresholds)
        if case.id != "GOLD-TMP-17":
            return outcome
        return outcome.model_copy(update={"reasons": [*outcome.reasons, "a new reason"]})

    monkeypatch.setattr(tracediff, "determine_action", drifted_engine)
    assert drifted_cases(GOLD_JEV_TRACES) == ["GOLD-TMP-17"]


def test_relay_replay_reproduces_a_committed_gzipped_gold_trace(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "--env-file",
            str(tmp_path / "missing.env"),
            "replay",
            "GOLD-TMP-17",
            "--traces",
            str(GOLD_JEV_TRACES),
            "--dataset",
            str(DATASET_DIRS["gold-v0.1"]),
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.output.count(REPRODUCED_LINE) == 2
    assert "ORIGINAL run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1" in (
        result.output
    )
