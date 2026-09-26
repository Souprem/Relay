"""Write an evaluation report bundle (Markdown, JSON, CSV) that a dashboard can render later."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from relay.evaluation.calibration import RunCalibration
from relay.evaluation.confusion import ConfusionMatrix
from relay.evaluation.frontier import SweepResult, frontier_csv
from relay.evaluation.metrics import EvalSummary, RunIdentity
from relay.reporting import render_eval_report

BUNDLE_FILES: tuple[str, ...] = (
    "summary.json",
    "calibration.json",
    "calibration.csv",
    "frontier.csv",
    "confusion.json",
    "report.md",
)
CALIBRATION_CSV_FIELDS: tuple[str, ...] = (
    "decision",
    "lower",
    "upper",
    "n",
    "mean_confidence",
    "accuracy",
    "gap",
)


def _cell(value: object) -> str:
    return "" if value is None else str(value)


def calibration_csv(calibration: RunCalibration) -> str:
    lines = [",".join(CALIBRATION_CSV_FIELDS)]
    for decision, report in calibration.decisions.items():
        for b in report.bins:
            gap = None
            if b.accuracy is not None and b.mean_confidence is not None:
                gap = b.accuracy - b.mean_confidence
            row = (decision, b.lower, b.upper, b.n, b.mean_confidence, b.accuracy, gap)
            lines.append(",".join(_cell(v) for v in row))
    return "\n".join(lines) + "\n"


def _json(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":")) + "\n"


def write_eval_bundle(
    out_dir: Path,
    *,
    identity: RunIdentity,
    summary: EvalSummary,
    calibration: RunCalibration,
    confusion: Mapping[str, ConfusionMatrix],
    sweep: SweepResult,
) -> list[Path]:
    """Write the six BUNDLE_FILES into out_dir (created if needed); return their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    contents = {
        "summary.json": _json(
            {
                "identity": identity.model_dump(mode="json"),
                # Per-case list omitted here (results.json is the source of truth for it).
                "summary": summary.model_dump(mode="json", exclude={"cases"}),
                "ceiling": sweep.ceiling,
                "selection_rule": sweep.selection_rule,
                "selected": None if sweep.selected is None else sweep.selected.model_dump(),
                "at_point": None if sweep.at_point is None else sweep.at_point.model_dump(),
            }
        ),
        "calibration.json": calibration.model_dump_json() + "\n",
        "calibration.csv": calibration_csv(calibration),
        "frontier.csv": frontier_csv(sweep.points),
        "confusion.json": _json({k: m.model_dump(mode="json") for k, m in confusion.items()}),
        "report.md": render_eval_report(identity, summary, calibration, confusion, sweep),
    }
    paths = []
    for name in BUNDLE_FILES:
        path = out_dir / name
        path.write_text(contents[name], encoding="utf-8", newline="\n")
        paths.append(path)
    return paths
