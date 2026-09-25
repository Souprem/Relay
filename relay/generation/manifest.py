"""Dataset manifests: a small, reproducible record of a generated dataset (no timestamps)."""

import hashlib
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from relay.cases.models import PriorAuthCase
from relay.cases.policies import load_policy
from relay.evaluation.labels import expected_action
from relay.generation.facts import GENERATOR_VERSION
from relay.workflow.thresholds import Thresholds

MANIFEST_DIR = Path("evals/generated/manifests")


class DatasetManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str
    generator_version: str
    seed: int
    count: int
    difficulty_counts: dict[str, int]
    expected_action_counts: dict[str, int]
    missing_evidence_counts: dict[str, int]
    dataset_hash: str


def dataset_hash(cases: Sequence[PriorAuthCase]) -> str:
    entries = sorted(
        f"{c.input.id}:{c.input.content_hash()}:{c.ground_truth.model_dump_json()}" for c in cases
    )
    return "sha256:" + hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()


def _sorted_counts(values: Sequence[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def build_manifest(
    *,
    dataset_id: str,
    seed: int,
    cases: Sequence[PriorAuthCase],
    difficulties: Sequence[str],
    thresholds: Thresholds,
) -> DatasetManifest:
    actions = [expected_action(c, load_policy(c.input.policy_id), thresholds).value for c in cases]
    return DatasetManifest(
        dataset_id=dataset_id,
        generator_version=GENERATOR_VERSION,
        seed=seed,
        count=len(cases),
        difficulty_counts=_sorted_counts(difficulties),
        expected_action_counts=_sorted_counts(actions),
        missing_evidence_counts=_sorted_counts(
            [c.ground_truth.missing_evidence.value for c in cases]
        ),
        dataset_hash=dataset_hash(cases),
    )


def write_manifest(manifest: DatasetManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")


def read_manifest(path: Path) -> DatasetManifest:
    return DatasetManifest.model_validate_json(path.read_text(encoding="utf-8"))
