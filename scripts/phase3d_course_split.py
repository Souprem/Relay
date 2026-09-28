"""Phase 3D q-v0.3 course-category split for step_therapy accuracy (offline, no provider calls).

Tags each case in a committed gen-v0.3 dataset as interrupted, old-course or other by reading its
committed `ground_truth.json` `notes` field (written by `relay/generation/labels.py` at generation
time): `"interrupted ("` marks an interrupted-and-restarted course, and `"ended Nd before as-of"`
with N > 365 marks an old course. No dataset regeneration and no random draw is needed; the tags
come entirely from files already on disk. It then reports `step_therapy` accuracy (prediction =
`p_yes >= 0.5` vs `ground_truth.step_therapy_satisfied`) per tag, for two committed trace files
over the same dataset.

uv run python -m scripts.phase3d_course_split DATASET_DIR BASELINE_TRACES BASELINE_LABEL CANDIDATE_TRACES CANDIDATE_LABEL

Example (offline, matches the README's "Where the interrupted-course accuracy comes from"):
uv run python -m scripts.phase3d_course_split \\
    evals/generated/gen-v0.3-holdout \\
    evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz q-v0.2 \\
    evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz q-v0.3
"""

import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

INTERRUPTED_RE = re.compile(r"interrupted \(")
OLD_COURSE_RE = re.compile(r"ended (\d+)d before as-of")
OLD_COURSE_DAYS = 365


def tag_case(notes: str) -> str:
    """Tag a case from its committed ground_truth.json `notes` field."""
    if INTERRUPTED_RE.search(notes):
        return "interrupted"
    match = OLD_COURSE_RE.search(notes)
    if match and int(match.group(1)) > OLD_COURSE_DAYS:
        return "old_course"
    return "other"


def tag_dataset(dataset_dir: Path) -> dict[str, str]:
    tags: dict[str, str] = {}
    for case_dir in sorted(dataset_dir.iterdir()):
        gt_path = case_dir / "ground_truth.json"
        if not gt_path.is_file():
            continue
        notes = json.loads(gt_path.read_text(encoding="utf-8"))["notes"]
        tags[case_dir.name] = tag_case(notes)
    return tags


def load_ground_truth(dataset_dir: Path, case_id: str) -> dict[str, Any]:
    return json.loads((dataset_dir / case_id / "ground_truth.json").read_text(encoding="utf-8"))


def load_traces(path: Path) -> dict[str, dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    out: dict[str, dict[str, Any]] = {}
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            out[record["case_id"]] = record
    return out


def step_therapy_p_yes(record: dict[str, Any]) -> float | None:
    for decision in record["decisions"]["decisions"]:
        if decision["question_id"] == "step_therapy":
            return decision["p_yes"]
    return None


def accuracy_by_tag(
    dataset_dir: Path, tags: dict[str, str], traces: dict[str, dict[str, Any]]
) -> dict[str, tuple[int, int]]:
    correct: Counter[str] = Counter()
    total: Counter[str] = Counter()
    for case_id, tag in tags.items():
        record = traces.get(case_id)
        if record is None:
            continue
        truth = load_ground_truth(dataset_dir, case_id)["step_therapy_satisfied"]
        p_yes = step_therapy_p_yes(record)
        predicted = p_yes is not None and p_yes >= 0.5
        total[tag] += 1
        correct[tag] += int(predicted == truth)
    return {tag: (correct[tag], total[tag]) for tag in total}


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(__doc__, file=sys.stderr)
        return 2
    dataset_dir = Path(argv[0])
    baseline_traces, baseline_label = Path(argv[1]), argv[2]
    candidate_traces, candidate_label = Path(argv[3]), argv[4]

    tags = tag_dataset(dataset_dir)
    counts = Counter(tags.values())
    print(
        f"{dataset_dir.name} (n={len(tags)}): "
        + ", ".join(f"{tag} {counts[tag]}" for tag in ("interrupted", "old_course", "other"))
    )

    results: dict[str, dict[str, tuple[int, int]]] = {}
    for label, path in ((baseline_label, baseline_traces), (candidate_label, candidate_traces)):
        results[label] = accuracy_by_tag(dataset_dir, tags, load_traces(path))

    for tag in ("interrupted", "old_course", "other"):
        parts = []
        for label in (baseline_label, candidate_label):
            correct, total = results[label].get(tag, (0, 0))
            rate = correct / total if total else float("nan")
            parts.append(f"{label} {correct}/{total} = {rate:.4f}")
        print(f"  {tag:12s} " + "   ".join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
