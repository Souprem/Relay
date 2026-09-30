"""Restore and verify the dashboard's generated datasets, offline, before a strict export.

Run from the repository root with `uv run python -m scripts.prepare_dashboard`.
Committed manifests supply every generation parameter; existing data is verified, never replaced.
"""

from pathlib import Path

from relay.generation.generator import generate_dataset, verify_dataset
from relay.generation.manifest import read_manifest
from relay.site.registry import DATASETS


def prepare_datasets(repo: Path) -> None:
    for dataset in DATASETS:
        if dataset.committed:
            continue
        manifest = read_manifest(repo / "evals/generated/manifests" / f"{dataset.id}.json")
        out = repo / dataset.path
        if not out.exists() or not any(out.iterdir()):
            generated = generate_dataset(
                manifest.count,
                manifest.seed,
                manifest.dataset_id,
                out,
                generator_version=manifest.generator_version,
                policy_version=manifest.policy_version,
            )
            if generated != manifest:
                raise ValueError(f"{dataset.id}: generated dataset differs from committed manifest")
        else:
            problems = verify_dataset(manifest, out)
            if problems:
                raise ValueError(f"{dataset.id}: {'; '.join(problems)}")
        print(f"Verified {dataset.id}: {manifest.count} synthetic cases")


if __name__ == "__main__":
    prepare_datasets(Path.cwd())
