"""Shared pieces of the site export: errors, JSON writing, run loading and rate shapes."""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from relay.cases.loader import CaseLoadError, load_dataset
from relay.cases.models import PriorAuthCase
from relay.evaluation.frontier import FrontierPoint
from relay.evaluation.metrics import EvalError, paired_cases
from relay.evaluation.regression import Rate, rate
from relay.evaluation.tracediff import replay_run
from relay.site.registry import DatasetSpec, RunSpec
from relay.traces.models import WorkflowTrace
from relay.traces.store import read_traces


class ExportError(Exception):
    """The export cannot be produced from these inputs (the CLI maps it to exit 2)."""


@dataclass(frozen=True)
class LoadedRun:
    """A registered run on a committed dataset: its traces as recorded and re-decided at its
    operating point (the same list when the operating point is the recorded threshold)."""

    spec: RunSpec
    recorded: list[WorkflowTrace]
    at_op: list[WorkflowTrace]


@dataclass
class ExportContext:
    """What the core export loaded, for the gate and experiment exports to reuse."""

    loaded_runs: dict[str, LoadedRun] = field(default_factory=dict)
    dataset_cases: dict[str, list[PriorAuthCase]] = field(default_factory=dict)
    run_payloads: dict[str, dict[str, Any]] = field(default_factory=dict)


def write_json(path: Path, payload: Any) -> Path:
    """Deterministic JSON: sorted keys, two-space indent, UTF-8, one trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ExportError(f"{path}: {error}") from error


def rate_json(r: Rate) -> dict[str, Any]:
    return r.model_dump(mode="json")


def point_rates(point: FrontierPoint) -> dict[str, dict[str, Any]]:
    """The five headline rates at one frontier point, each with its Clopper-Pearson interval."""
    return {
        "correct": rate_json(rate(point.correct, point.n)),
        "automation": rate_json(rate(point.auto, point.n)),
        "request_info": rate_json(rate(point.request_info, point.n)),
        "human_review": rate_json(rate(point.human_review, point.n)),
        "uar": rate_json(rate(point.unsafe, point.auto)),
    }


def point_at(points: Sequence[FrontierPoint], threshold: float) -> FrontierPoint:
    for point in points:
        if abs(point.auto_threshold - threshold) < 1e-9:
            return point
    raise ExportError(f"no frontier point at auto_process={threshold:g}")


def load_cases(repo: Path, spec: DatasetSpec) -> list[PriorAuthCase]:
    path = repo / spec.path
    if not path.is_dir():
        raise ExportError(f"dataset {spec.id} is missing: {path}")
    try:
        return load_dataset(path)
    except CaseLoadError as error:
        raise ExportError(str(error)) from error


def read_run_traces(path: Path) -> list[WorkflowTrace]:
    if not path.is_file():
        raise ExportError(f"missing run: {path}")
    try:
        traces = read_traces(path)
    except (ValueError, OSError) as error:
        raise ExportError(f"{path}: {error}") from error
    if not traces:
        raise ExportError(f"{path}: no traces")
    return traces


def load_run(repo: Path, spec: RunSpec, cases: Sequence[PriorAuthCase]) -> LoadedRun:
    """A committed-dataset run, checked against the cases (one run, every case, unchanged
    content hashes) and re-decided at its operating point with replay_run."""
    recorded = read_run_traces(repo / spec.run_dir / spec.trace_name)
    if recorded[0].run_id != spec.run_id:
        raise ExportError(f"{spec.run_dir}: run id {recorded[0].run_id}, expected {spec.run_id}")
    try:
        paired_cases(recorded, cases)
        at_op = (
            recorded
            if spec.operating_point is None
            else replay_run(recorded, cases, policy_id=None, auto_process=spec.operating_point)
        )
    except EvalError as error:
        raise ExportError(f"{spec.run_id}: {error}") from error
    return LoadedRun(spec=spec, recorded=recorded, at_op=at_op)


def trace_for(traces: Sequence[WorkflowTrace], case_id: str) -> WorkflowTrace:
    matches = [t for t in traces if t.case_id == case_id]
    if len(matches) != 1:
        raise ExportError(f"expected one trace for {case_id}, found {len(matches)}")
    return matches[0]
