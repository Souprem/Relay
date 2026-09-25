"""C5: a drift guard. Re-score each committed evals/baselines/gen-v0.2-* run offline against its
generated dataset on disk, and assert key metrics still match the committed results.json.

This does not call any provider: it replays the committed traces.jsonl.gz through the current
scoring code. If it ever fails, either the engine/labels changed in a way that reinterprets old
decisions, or a committed baseline was hand-edited — both worth stopping for.

Skips cleanly (not a failure) when the corresponding generated dataset directory is absent, since
`evals/generated/<dataset-id>/` is git-ignored and only exists after `relay generate` has been run
(or the case folders were otherwise materialized) locally.
"""

import json
from pathlib import Path

import pytest

from relay.cases.loader import CaseLoadError, load_dataset
from relay.evaluation.metrics import score_run
from relay.evaluation.runner import sample_cases
from relay.traces.store import read_traces

REPO = Path(__file__).resolve().parents[2]
BASELINES = REPO / "evals" / "baselines"
GENERATED = REPO / "evals" / "generated"

# Every committed gen-v0.2-* run directory: (dataset_id, run_dir).
RUN_DIRS: list[tuple[str, Path]] = sorted(
    (dataset_dir.name, run_dir)
    for dataset_dir in BASELINES.glob("gen-v0.2-*")
    if dataset_dir.is_dir()
    for run_dir in dataset_dir.iterdir()
    if run_dir.is_dir()
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
    dataset_dir = GENERATED / dataset_id
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
