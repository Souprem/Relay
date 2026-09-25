"""Load case directories: case.json + documents/*.txt + ground_truth.json."""

import json
from pathlib import Path

from relay.cases.models import CaseInput, GroundTruth, PriorAuthCase


class CaseLoadError(Exception):
    """A case directory is missing files or contains invalid data."""


def load_case(case_dir: Path) -> PriorAuthCase:
    try:
        raw = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
        documents = []
        for meta in raw.pop("documents"):
            text = (case_dir / "documents" / meta["file"]).read_text(encoding="utf-8")
            documents.append({"id": meta["id"], "kind": meta["kind"], "text": text})
        raw["documents"] = documents
        case_input = CaseInput.model_validate(raw)
        truth = GroundTruth.model_validate_json(
            (case_dir / "ground_truth.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CaseLoadError(f"{case_dir}: {error}") from error
    if case_input.id != case_dir.name:
        raise CaseLoadError(
            f"{case_dir}: case id {case_input.id!r} does not match directory name {case_dir.name!r}"
        )
    return PriorAuthCase(input=case_input, ground_truth=truth)


def load_dataset(dataset_dir: Path) -> list[PriorAuthCase]:
    case_dirs = sorted(p for p in dataset_dir.iterdir() if p.is_dir())
    if not case_dirs:
        raise CaseLoadError(f"{dataset_dir}: no case directories found")
    cases = [load_case(d) for d in case_dirs]
    dataset_ids = {c.input.dataset_id for c in cases}
    if len(dataset_ids) != 1:
        raise CaseLoadError(
            f"{dataset_dir}: cases have mixed dataset_id values {sorted(dataset_ids)}"
        )
    return cases
