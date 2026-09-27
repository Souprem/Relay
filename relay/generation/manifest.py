"""Dataset manifests: a small, reproducible record of a generated dataset (no timestamps)."""

import hashlib
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from relay.cases.models import PriorAuthCase
from relay.cases.policies import load_policy
from relay.evaluation.labels import expected_action
from relay.generation.facts import GEN_V0_2
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
    # Phase 3D: the policy version every case uses (gen-v0.3-shift is v0.2). Written only when it
    # is not v0.1, so the committed gen-v0.2 manifests stay byte-identical.
    policy_version: str = "v0.1"


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
    generator_version: str = GEN_V0_2,
    policy_version: str = "v0.1",
) -> DatasetManifest:
    actions = [expected_action(c, load_policy(c.input.policy_id), thresholds).value for c in cases]
    return DatasetManifest(
        dataset_id=dataset_id,
        generator_version=generator_version,
        seed=seed,
        count=len(cases),
        difficulty_counts=_sorted_counts(difficulties),
        expected_action_counts=_sorted_counts(actions),
        missing_evidence_counts=_sorted_counts(
            [c.ground_truth.missing_evidence.value for c in cases]
        ),
        dataset_hash=dataset_hash(cases),
        policy_version=policy_version,
    )


def write_manifest(manifest: DatasetManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exclude = {"policy_version"} if manifest.policy_version == "v0.1" else None
    text = manifest.model_dump_json(indent=2, exclude=exclude)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def read_manifest(path: Path) -> DatasetManifest:
    return DatasetManifest.model_validate_json(path.read_text(encoding="utf-8"))
