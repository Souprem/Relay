"""Seeded generation of synthetic cases and datasets. Same arguments -> byte-identical files."""

import json
import tempfile
from pathlib import Path
from random import Random

from relay.cases.loader import CaseLoadError, load_dataset
from relay.cases.models import CaseInput, Insurance, MedicationRequest, Patient, PriorAuthCase
from relay.cases.policies import load_policy
from relay.generation.facts import DIFFICULTIES, GENERATOR_VERSION, Difficulty
from relay.generation.labels import label_case
from relay.generation.manifest import DatasetManifest, build_manifest, dataset_hash
from relay.generation.render import render_documents
from relay.generation.scenarios import sample_facts
from relay.workflow.thresholds import load_thresholds

POLICY_IDS: dict[str, str] = {"v0.1": "immunara-v0.1"}
SEED_STRIDE = 1_000_000


def generate_case(
    seed: int,
    difficulty: Difficulty,
    contradiction_probability: float | None = None,
    missing_data_probability: float | None = None,
    note_noise: float | None = None,
    policy_version: str = "v0.1",
    dataset_id: str = "gen-adhoc",
) -> PriorAuthCase:
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"unknown difficulty {difficulty!r}; allowed: {list(DIFFICULTIES)}")
    if policy_version not in POLICY_IDS:
        raise ValueError(
            f"unknown policy version {policy_version!r}; allowed: {sorted(POLICY_IDS)}"
        )
    policy = load_policy(POLICY_IDS[policy_version])
    rng = Random(seed)
    facts = sample_facts(
        rng,
        case_id=f"GEN-{seed:08d}",
        difficulty=difficulty,
        contradiction_probability=contradiction_probability,
        missing_data_probability=missing_data_probability,
        note_noise=note_noise,
    )
    documents = render_documents(facts, rng)
    case_input = CaseInput(
        id=facts.case_id,
        dataset_id=dataset_id,
        as_of_date=facts.as_of_date,
        patient=Patient(age=facts.age, state=facts.state),
        medication=MedicationRequest(name=policy.medication, indication=policy.indication),
        insurance=Insurance(payer=facts.payer, plan=facts.plan, member_id=facts.member_id),
        documents=documents,
        policy_id=policy.id,
    )
    return PriorAuthCase(input=case_input, ground_truth=label_case(facts))


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def write_case(case: PriorAuthCase, dataset_dir: Path) -> Path:
    """Write one case in the v0.1 case-directory format and return its directory."""
    case_dir = dataset_dir / case.input.id
    (case_dir / "documents").mkdir(parents=True)
    raw = case.input.model_dump(mode="json")
    raw["documents"] = [
        {"id": d.id, "kind": d.kind, "file": f"{d.id}.txt"} for d in case.input.documents
    ]
    _write(case_dir / "case.json", json.dumps(raw, indent=2) + "\n")
    for document in case.input.documents:
        _write(case_dir / "documents" / f"{document.id}.txt", document.text)
    _write(case_dir / "ground_truth.json", case.ground_truth.model_dump_json(indent=2) + "\n")
    return case_dir


def generate_dataset(count: int, seed: int, dataset_id: str, out_dir: Path) -> DatasetManifest:
    if count < 1:
        raise ValueError(f"count must be at least 1, got {count}")
    if seed < 0:
        raise ValueError(f"seed must be non-negative, got {seed}")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"{out_dir} is not empty; refusing to overwrite")
    out_dir.mkdir(parents=True, exist_ok=True)
    cases: list[PriorAuthCase] = []
    difficulties: list[str] = []
    for i in range(count):
        difficulty = DIFFICULTIES[i % len(DIFFICULTIES)]
        case = generate_case(seed * SEED_STRIDE + i, difficulty, dataset_id=dataset_id)
        write_case(case, out_dir)
        cases.append(case)
        difficulties.append(difficulty)
    return build_manifest(
        dataset_id=dataset_id,
        seed=seed,
        cases=cases,
        difficulties=difficulties,
        thresholds=load_thresholds("v0.1"),
    )


def verify_dataset(manifest: DatasetManifest, out_dir: Path | None = None) -> list[str]:
    """Regenerate from the manifest and compare; also check out_dir on disk if it exists.

    Returns a list of problems; an empty list means the dataset verifies.
    """
    if manifest.generator_version != GENERATOR_VERSION:
        return [
            f"manifest was produced by {manifest.generator_version}, "
            f"but this code is {GENERATOR_VERSION}"
        ]
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        regenerated = generate_dataset(
            manifest.count, manifest.seed, manifest.dataset_id, Path(tmp) / manifest.dataset_id
        )
    if regenerated != manifest:
        problems.append(
            f"regenerated dataset does not match the manifest: dataset_hash "
            f"{regenerated.dataset_hash} vs {manifest.dataset_hash}"
        )
    if out_dir is not None and out_dir.exists():
        try:
            on_disk = dataset_hash(load_dataset(out_dir))
        except CaseLoadError as error:
            problems.append(f"files on disk could not be loaded: {error}")
        else:
            if on_disk != manifest.dataset_hash:
                problems.append(
                    f"files on disk in {out_dir} do not match the manifest: dataset_hash "
                    f"{on_disk} vs {manifest.dataset_hash}"
                )
    return problems
