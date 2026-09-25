"""Combine two Claude batch runs on gen-v0.2-dev into one 400-case trace file.

Context (Task 13, Phase 2D): the first dev batch (msgbatch_01SpuLJxsxtaXJ8W2YPps8Tf) was
cancelled by the controller after a local polling crash and a long stall; Anthropic had already
processed it as succeeded=378, canceled=22 by the time it was cancelled. Re-attaching (run
run_20260925T190719Z_d65789) collected those 378 real bundles for free, plus 22 error bundles
(`decisions.error` set, e.g. "batch canceled: no result returned") for the canceled cases. Those
22 case ids were re-run as a second batch on a one-off dataset directory containing only their
case folders (run_20260925T190826Z_b1c45c), succeeding on all 22.

This script combines the two into a single trace file covering all 400 gen-v0.2-dev cases, with
one shared run id, so `relay eval/sweep/report/compare --traces ...` can score it as an ordinary
run. Provenance (the two source run ids and batch ids) is recorded in an extra `source_runs` key
in the manifest; `RunManifest` does not set `extra="forbid"`, so tooling that loads the manifest
through the model ignores the extra key, and it stays in the committed JSON for a human reader.

Usage:
    uv run python scripts/combine_claude_dev.py \
        --dataset evals/generated/gen-v0.2-dev \
        --primary traces/run_20260925T190719Z_d65789.jsonl \
        --canceled-rerun traces/run_20260925T190826Z_b1c45c.jsonl \
        --traces-dir traces

Prints the new run id and the path to the combined trace + manifest files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from relay.cases.loader import load_dataset
from relay.traces.models import RunManifest
from relay.traces.store import current_git_sha, new_run_id, read_traces


def combine(
    dataset_dir: Path, primary_path: Path, canceled_rerun_path: Path, traces_dir: Path
) -> tuple[str, Path, Path]:
    dataset = load_dataset(dataset_dir)
    all_case_ids = {case.input.id for case in dataset}

    primary_traces = read_traces(primary_path)
    rerun_traces = read_traces(canceled_rerun_path)

    primary_run_ids = {t.run_id for t in primary_traces}
    rerun_run_ids = {t.run_id for t in rerun_traces}
    if len(primary_run_ids) != 1:
        raise SystemExit(f"primary trace file has multiple run ids: {sorted(primary_run_ids)}")
    if len(rerun_run_ids) != 1:
        raise SystemExit(f"canceled-rerun trace file has multiple run ids: {sorted(rerun_run_ids)}")
    primary_run_id = primary_run_ids.pop()
    rerun_run_id = rerun_run_ids.pop()

    good_primary = [t for t in primary_traces if t.decisions.error is None]
    errored_primary = [t for t in primary_traces if t.decisions.error is not None]
    bad_rerun = [t for t in rerun_traces if t.decisions.error is not None]
    if bad_rerun:
        raise SystemExit(
            f"canceled-rerun trace file still has errors for: {[t.case_id for t in bad_rerun]}"
        )

    errored_ids = {t.case_id for t in errored_primary}
    rerun_ids = {t.case_id for t in rerun_traces}
    if errored_ids != rerun_ids:
        raise SystemExit(
            "canceled-rerun does not exactly cover the primary run's error cases: "
            f"errored={sorted(errored_ids)} rerun={sorted(rerun_ids)}"
        )

    combined = good_primary + rerun_traces
    combined_ids = [t.case_id for t in combined]
    duplicates = sorted({cid for cid in combined_ids if combined_ids.count(cid) > 1})
    if duplicates:
        raise SystemExit(f"duplicate case ids after combining: {duplicates}")
    missing = sorted(all_case_ids - set(combined_ids))
    if missing:
        raise SystemExit(f"combined traces are missing cases: {missing}")
    extra = sorted(set(combined_ids) - all_case_ids)
    if extra:
        raise SystemExit(f"combined traces reference cases outside the dataset: {extra}")

    for trace, case in ((t, next(c for c in dataset if c.input.id == t.case_id)) for t in combined):
        if trace.case_content_hash != case.input.content_hash():
            raise SystemExit(f"{trace.case_id}: case content hash changed since the run")

    combined_run_id = new_run_id()
    rewritten = [trace.model_copy(update={"run_id": combined_run_id}) for trace in combined]

    traces_dir.mkdir(parents=True, exist_ok=True)
    trace_path = traces_dir / f"{combined_run_id}.jsonl"
    with trace_path.open("x", encoding="utf-8") as handle:
        for trace in rewritten:
            handle.write(trace.model_dump_json() + "\n")

    manifest = RunManifest(
        run_id=combined_run_id,
        created_at=max(t.timestamp for t in rewritten),
        dataset_id=dataset[0].input.dataset_id,
        dataset_path=str(dataset_dir),
        provider="claude",
        policy_version=rewritten[0].policy_version,
        question_set_version=rewritten[0].question_set_version,
        case_count=len(rewritten),
        trace_file=str(trace_path),
        relay_git_sha=current_git_sha(),
        sample_limit=None,
        sample_seed=None,
    )
    manifest_dict = json.loads(manifest.model_dump_json(indent=2))
    manifest_dict["source_runs"] = [
        {
            "run_id": primary_run_id,
            "role": "primary batch (collected after controller cancellation)",
            "batch_id": "msgbatch_01SpuLJxsxtaXJ8W2YPps8Tf",
            "cases_used": len(good_primary),
            "cases_dropped_as_canceled": len(errored_primary),
        },
        {
            "run_id": rerun_run_id,
            "role": "re-run of the 22 canceled case ids",
            "batch_id": "msgbatch_012TiAgwjfKK8DGZKdvhv5Hm",
            "cases_used": len(rerun_traces),
        },
    ]
    manifest_path = trace_path.with_suffix(".manifest.json")
    with manifest_path.open("x", encoding="utf-8") as handle:
        json.dump(manifest_dict, handle, indent=2)
        handle.write("\n")

    return combined_run_id, trace_path, manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--canceled-rerun", type=Path, required=True)
    parser.add_argument("--traces-dir", type=Path, default=Path("traces"))
    args = parser.parse_args()

    run_id, trace_path, manifest_path = combine(
        args.dataset, args.primary, args.canceled_rerun, args.traces_dir
    )
    print(f"combined run id: {run_id}")
    print(f"traces: {trace_path}")
    print(f"manifest: {manifest_path}")


if __name__ == "__main__":
    main()
