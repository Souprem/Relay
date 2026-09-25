"""Filter a committed trace file down to a deterministic case-id sample, for an apples-to-apples
holdout comparison under a tight API budget (Task 13, Phase 2D).

Context: the $10 Claude budget only covered a 150-case sample of gen-v0.2-holdout
(--limit 150 --sample-seed 7), not the full 1000. To compare Jev and rules against Claude on
exactly that sample (no new provider calls -- Jev and rules already have committed full-holdout
traces), this script keeps only the sampled case ids from an existing trace file and rewrites
every kept line to share one new run id (relay.evaluation.metrics.paired_cases requires all
traces in a file to come from a single run and to cover every case in the --dataset directory
exactly once, so the run id must be rewritten and the file used together with a dataset directory
that itself contains only the same 150 case folders).

The sample is reproduced with the same call the live Claude run used:
    sample_cases(load_dataset(dataset_dir), limit, seed)

Usage:
    uv run python scripts/filter_traces_by_sample.py \
        --dataset evals/generated/gen-v0.2-holdout \
        --source evals/baselines/gen-v0.2-holdout/run_20260925T075242Z_fd455f/traces.jsonl.gz \
        --limit 150 --sample-seed 7 \
        --out traces/jev-holdout-s150-seed7.jsonl

Prints the new run id and the count of lines written.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from relay.cases.loader import load_dataset
from relay.evaluation.runner import sample_cases
from relay.traces.store import new_run_id, read_traces


def filter_traces(
    dataset_dir: Path, source_path: Path, limit: int, seed: int, out_path: Path
) -> tuple[str, int]:
    dataset = load_dataset(dataset_dir)
    sampled_ids = {c.input.id for c in sample_cases(dataset, limit, seed)}

    traces = read_traces(source_path)
    kept = [t for t in traces if t.case_id in sampled_ids]
    kept_ids = {t.case_id for t in kept}
    missing = sampled_ids - kept_ids
    if missing:
        raise SystemExit(f"source trace file is missing sampled cases: {sorted(missing)}")

    combined_run_id = new_run_id()
    rewritten = [t.model_copy(update={"run_id": combined_run_id}) for t in kept]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("x", encoding="utf-8") as handle:
        for trace in rewritten:
            handle.write(trace.model_dump_json() + "\n")

    return combined_run_id, len(rewritten)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--limit", type=int, required=True)
    parser.add_argument("--sample-seed", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    run_id, count = filter_traces(args.dataset, args.source, args.limit, args.sample_seed, args.out)
    print(f"filtered run id: {run_id}")
    print(f"lines written: {count}")
    print(f"traces: {args.out}")


if __name__ == "__main__":
    main()
