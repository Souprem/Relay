"""Gold-set tooling (Phase 2E): blind export, second-pass import and agreement."""

import json
import random
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from relay.cases.models import GroundTruth, PriorAuthCase
from tests.gold_support import (
    ALL_IDS,
    ALLOWED_MISSING,
    FACTS,
    GUIDE_PATH,
    REPO,
    derive_action,
    present_case_dirs,
    rules_section,
)

BLIND_SEED = 20260925


def blind_ids() -> dict[str, str]:
    """gold id -> neutral CASE-### id, in a fixed shuffled order so categories don't show."""
    order = list(ALL_IDS)
    random.Random(BLIND_SEED).shuffle(order)
    return {gold_id: f"CASE-{n:03d}" for n, gold_id in enumerate(order, start=1)}


def export_blind_packet(out_dir: Path) -> list[str]:
    """Copy case.json (with a blind id) and documents/ only, plus RULES.md and a template."""
    root = out_dir.resolve()
    if root == REPO or REPO in root.parents:
        raise ValueError(f"{root} is inside the repository; export outside it")
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"{root} is not empty")
    dirs = present_case_dirs()
    if sorted(d.name for d in dirs) != sorted(ALL_IDS):
        raise ValueError("the gold set is incomplete; the blind export needs all 100 cases")
    mapping = blind_ids()
    (root / "cases").mkdir(parents=True, exist_ok=True)
    for case_dir in dirs:
        dest = root / "cases" / mapping[case_dir.name]
        shutil.copytree(case_dir / "documents", dest / "documents")
        raw = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
        raw["id"] = mapping[case_dir.name]
        (dest / "case.json").write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    rules = rules_section(GUIDE_PATH.read_text(encoding="utf-8"))
    (root / "RULES.md").write_text(rules + "\n", encoding="utf-8")
    blind_sorted = sorted(mapping.values())
    template = {
        "reviewer": "blind-second-pass",
        "labels": {b: {**dict.fromkeys(FACTS), "rationale": ""} for b in blind_sorted},
    }
    (root / "second_pass.template.json").write_text(
        json.dumps(template, indent=2) + "\n", encoding="utf-8"
    )
    return blind_sorted


def _facts(record: Mapping[str, Any]) -> dict[str, Any]:
    return {fact: record[fact] for fact in FACTS}


def import_second_pass(
    blind: Mapping[str, Any], expected: Sequence[str] = ALL_IDS
) -> dict[str, Any]:
    """Validate the reviewer's file and map blind ids back to gold ids."""
    mapping = blind_ids()
    back = {blind_id: gold_id for gold_id, blind_id in mapping.items()}
    labels = blind.get("labels")
    if not isinstance(labels, dict):
        raise ValueError("second pass has no 'labels' object")
    want = {mapping[gold_id] for gold_id in expected}
    if set(labels) != want:
        missing = sorted(want - set(labels))[:5]
        unknown = sorted(set(labels) - want)[:5]
        raise ValueError(f"second pass labels: missing {missing}, unknown {unknown}")
    out: dict[str, Any] = {}
    for blind_id, record in labels.items():
        if not isinstance(record, dict) or set(record) != {*FACTS, "rationale"}:
            raise ValueError(f"{blind_id}: keys must be exactly {list(FACTS)} + rationale")
        for fact in FACTS[:4]:
            if not isinstance(record[fact], bool):
                raise ValueError(f"{blind_id}: {fact} must be true or false")
        if record["missing_evidence"] not in ALLOWED_MISSING:
            raise ValueError(f"{blind_id}: missing_evidence must be one of {ALLOWED_MISSING}")
        if not isinstance(record["rationale"], str) or not record["rationale"].strip():
            raise ValueError(f"{blind_id}: rationale must be a non-empty string")
        try:
            GroundTruth.model_validate(_facts(record))
        except ValueError as error:
            raise ValueError(f"{blind_id}: {error}") from error
        out[back[blind_id]] = {"blind_id": blind_id, **record}
    return {
        "reviewer": blind.get("reviewer", "blind-second-pass"),
        "labels": dict(sorted(out.items())),
    }


def compute_agreement(cases: Sequence[PriorAuthCase], second: Mapping[str, Any]) -> dict[str, Any]:
    """Per-fact, all-five and derived-action agreement of the second pass with ground_truth."""
    labels = second["labels"]
    n = len(cases)
    agree = dict.fromkeys(FACTS, 0)
    all_five = 0
    action_agree = 0
    disagreements: list[dict[str, Any]] = []
    action_disagreements: list[dict[str, Any]] = []
    for case in sorted(cases, key=lambda c: c.input.id):
        case_id = case.input.id
        first = case.ground_truth.model_dump(mode="json")
        record = labels[case_id]
        same = True
        for fact in FACTS:
            if first[fact] == record[fact]:
                agree[fact] += 1
            else:
                same = False
                disagreements.append(
                    {"case_id": case_id, "fact": fact, "first": first[fact], "second": record[fact]}
                )
        all_five += same
        first_action = derive_action(case.input, case.ground_truth)
        second_action = derive_action(case.input, GroundTruth.model_validate(_facts(record)))
        if first_action == second_action:
            action_agree += 1
        else:
            action_disagreements.append(
                {"case_id": case_id, "first": first_action, "second": second_action}
            )

    def block(count: int) -> dict[str, Any]:
        return {"agree": count, "n": n, "rate": round(count / n, 4) if n else None}

    return {
        "n": n,
        "per_fact": {fact: block(agree[fact]) for fact in FACTS},
        "all_five": block(all_five),
        "action": block(action_agree),
        "disagreements": disagreements,
        "action_disagreements": action_disagreements,
    }


def _pct(block: Mapping[str, Any]) -> str:
    if not block["n"]:
        return "n/a"
    return f"{block['agree']}/{block['n']} ({block['agree'] / block['n']:.1%})"


def agreement_markdown(result: Mapping[str, Any]) -> str:
    lines = ["| Fact | Agreement with the first pass |", "|---|---|"]
    lines += [f"| `{fact}` | {_pct(result['per_fact'][fact])} |" for fact in FACTS]
    lines.append(f"| all five facts | {_pct(result['all_five'])} |")
    lines.append(f"| derived action | {_pct(result['action'])} |")
    return "\n".join(lines)
