"""The core site data: index.json, runs.json, runs/<RUN_ID>.json, cases.json, cases/<ID>.json.

Runs on the committed gold and smoke sets are re-scored from their traces with the existing
evaluation code (run_sweep, calibrate_run, replay_run, diff_case). Runs on the git-ignored
generated sets come from their committed report bundles (summary.json, calibration.json,
frontier.csv written by `relay report`), so no generated dataset is needed.
"""

import csv
import io
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from relay.cases.models import PriorAuthCase
from relay.cases.policies import load_policy
from relay.decisions.base import Decision, DecisionId
from relay.evaluation.calibration import RunCalibration, calibrate_run
from relay.evaluation.frontier import (
    DEFAULT_CEILING,
    FrontierPoint,
    SweepResult,
    run_sweep,
    select_operating_point,
)
from relay.evaluation.labels import expected_action
from relay.evaluation.metrics import EvalError, RunIdentity, run_identity
from relay.evaluation.tracediff import CROSSINGS, GATE_ORDER, THRESHOLD_NAMES, classify, diff_case
from relay.reporting import DISCLAIMER
from relay.site.common import (
    ExportContext,
    ExportError,
    LoadedRun,
    load_cases,
    load_run,
    point_at,
    point_rates,
    read_json,
    read_run_traces,
    trace_for,
    write_json,
)
from relay.site.findings import build_findings, build_hero
from relay.site.questions import questions_compare, questions_page
from relay.site.registry import (
    DATASETS,
    DIFFS,
    EASY_CASE,
    HARD_CASE,
    HEADLINE,
    RUNS,
    DiffSpec,
    RunSpec,
    dataset_spec,
)
from relay.traces.models import WorkflowTrace
from relay.workflow.thresholds import load_thresholds

SCHEMA_VERSION = 1
CATEGORY_LABELS: dict[str, str] = {
    "STR": "Straightforward",
    "MIS": "Missing information",
    "CON": "Conflicting evidence",
    "TMP": "Temporal reasoning",
    "TRK": "Tricky or ambiguous",
    "SMOKE": "Smoke",
}
CLAUDE_SPEND = "evals/baselines/claude-spend.json"
JEV_SPEND = "evals/baselines/jev-spend-3d.json"


def category_of(case_id: str) -> str:
    """GOLD-STR-01 -> STR; every other id (the smoke set) -> SMOKE."""
    parts = case_id.split("-")
    if len(parts) == 3 and parts[0] == "GOLD" and parts[1] in CATEGORY_LABELS:
        return parts[1]
    return "SMOKE"


# ---- runs ---------------------------------------------------------------------------------


def _run_payload(
    spec: RunSpec,
    identity: RunIdentity,
    sweep: SweepResult,
    calibration: RunCalibration,
    recorded_auto: float,
) -> dict[str, Any]:
    at = sweep.at_point
    assert at is not None
    return {
        "run_id": spec.run_id,
        "dataset": spec.dataset,
        "provider": spec.provider,
        "label": spec.label,
        "slug": spec.slug,
        "question_set": spec.question_set,
        "questions_page": questions_page(spec.question_set),
        "note": spec.note,
        "n": at.n,
        "operating_point": {
            "auto_process": at.auto_threshold,
            "recorded": recorded_auto,
            "source": spec.operating_point_source,
        },
        "metrics": point_rates(at),
        "frontier": {
            "points": [p.model_dump(mode="json") for p in sweep.points],
            "flat": sweep.frontier_flat,
            "ceiling": sweep.ceiling,
            "ceiling_binding": sweep.ceiling_binding,
            # The run's own in-sample selection: a diagnostic, never an operating point.
            "in_sample_selected": None if sweep.selected is None else sweep.selected.auto_threshold,
        },
        "calibration": calibration.model_dump(mode="json"),
        "identity": identity.model_dump(mode="json"),
    }


def _threshold(spec: RunSpec, recorded_auto: float) -> float:
    return recorded_auto if spec.operating_point is None else spec.operating_point


def committed_run_payload(loaded: LoadedRun, cases: Sequence[PriorAuthCase]) -> dict[str, Any]:
    spec, traces = loaded.spec, loaded.recorded
    recorded_auto = traces[0].thresholds.auto_process
    try:
        sweep = run_sweep(
            traces, cases, ceiling=DEFAULT_CEILING, at=_threshold(spec, recorded_auto)
        )
        calibration = calibrate_run(traces, cases)
    except EvalError as error:
        raise ExportError(f"{spec.run_id}: {error}") from error
    return _run_payload(spec, run_identity(traces), sweep, calibration, recorded_auto)


def frontier_points(text: str) -> list[FrontierPoint]:
    """frontier.csv (relay.evaluation.frontier.frontier_csv) back into FrontierPoints."""
    rows = csv.DictReader(io.StringIO(text))
    return [
        FrontierPoint.model_validate({k: (None if v == "" else v) for k, v in row.items()})
        for row in rows
    ]


def bundle_run_payload(repo: Path, spec: RunSpec) -> dict[str, Any]:
    """A generated-dataset run from its committed report bundle."""
    run_dir = repo / spec.run_dir
    report = run_dir / "report"
    manifest = read_json(run_dir / "run-manifest.json")
    summary = read_json(report / "summary.json")
    try:
        identity = RunIdentity.model_validate(summary["identity"])
        calibration = RunCalibration.model_validate_json(
            (report / "calibration.json").read_text(encoding="utf-8")
        )
        points = frontier_points((report / "frontier.csv").read_text(encoding="utf-8"))
    except (OSError, KeyError, ValueError, ValidationError) as error:
        raise ExportError(f"missing run: {spec.run_dir}: {error}") from error
    if identity.run_id != spec.run_id or manifest.get("run_id") != spec.run_id:
        raise ExportError(f"{spec.run_dir}: run id does not match {spec.run_id}")
    if len(identity.thresholds_versions) != 1:
        raise ExportError(f"{spec.run_id}: expected one thresholds version")
    try:
        recorded_auto = load_thresholds(identity.thresholds_versions[0]).auto_process
    except KeyError as error:
        raise ExportError(f"{spec.run_id}: {error.args[0]}") from error
    sweep = SweepResult(
        run_id=identity.run_id,
        dataset_id=identity.dataset_id,
        provider=identity.provider,
        question_set_version=",".join(identity.question_set_versions),
        ceiling=DEFAULT_CEILING,
        selected=select_operating_point(points, DEFAULT_CEILING),
        at_point=point_at(points, _threshold(spec, recorded_auto)),
        points=points,
    )
    return _run_payload(spec, identity, sweep, calibration, recorded_auto)


def runs_index(run_payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    datasets = []
    for d in DATASETS:
        runs = []
        for r in (r for r in RUNS if r.dataset == d.id):
            payload = run_payloads[r.run_id]
            runs.append(
                {
                    "run_id": r.run_id,
                    "label": r.label,
                    "slug": r.slug,
                    "provider": r.provider,
                    "question_set": r.question_set,
                    "questions_page": questions_page(r.question_set),
                    "n": payload["n"],
                    "auto_process": payload["operating_point"]["auto_process"],
                    "operating_point_source": r.operating_point_source,
                    "metrics": payload["metrics"],
                }
            )
        datasets.append(
            {
                "id": d.id,
                "label": d.label,
                "description": d.description,
                "committed": d.committed,
                "runs": runs,
            }
        )
    return {"datasets": datasets}


# ---- cases --------------------------------------------------------------------------------


def decision_json(question_id: DecisionId, decision: Decision | None, thresholds: dict[str, float]):
    """One judgment and the thresholds an engine gate compares it with (the tracediff.CROSSINGS
    rows that feed a real gate), in Thresholds field order."""
    ticks = [
        {"name": name, "value": thresholds[name], "gate": crossing.gate}
        for name in THRESHOLD_NAMES
        if (crossing := CROSSINGS.get((question_id, name))) is not None
        and crossing.gate is not None
    ]
    if decision is None:
        return {"id": question_id.value, "kind": None, "ticks": ticks}
    return {
        "id": question_id.value,
        "kind": decision.kind,
        "p_yes": decision.p_yes,
        "answer": decision.answer,
        "probabilities": dict(sorted(decision.probabilities.items())),
        "probability": decision.probability,
        "ticks": ticks,
    }


def gate_rows(trace: WorkflowTrace) -> list[dict[str, Any]]:
    """Every engine gate in order: passed, FIRED, or not reached (after the gate that fired)."""
    by_gate = {g.gate: g for g in trace.gate_path}
    rows = []
    for gate in GATE_ORDER:
        result = by_gate.get(gate)
        if result is None:
            rows.append({"gate": gate, "status": "not reached", "detail": None})
        else:
            status = "FIRED" if result.fired else "passed"
            rows.append({"gate": gate, "status": status, "detail": result.detail})
    return rows


def provider_result(spec: RunSpec, trace: WorkflowTrace, case: PriorAuthCase) -> dict[str, Any]:
    expected = expected_action(case, load_policy(trace.policy_id), trace.thresholds)
    thresholds = trace.thresholds.model_dump(mode="json")
    return {
        "slug": spec.slug,
        "label": spec.label,
        "provider": spec.provider,
        "run_id": spec.run_id,
        "question_set": trace.question_set_version,
        "questions_page": questions_page(trace.question_set_version),
        "policy": f"{trace.policy_id} ({trace.policy_version})",
        "thresholds": thresholds,
        "operating_point_source": spec.operating_point_source,
        "note": spec.note,
        "decisions": [decision_json(q, trace.decisions.get(q), thresholds) for q in DecisionId],
        "gates": gate_rows(trace),
        "action": trace.action.value,
        "reasons": list(trace.decision_reasons),
        "expected": expected.value,
        "verdict": classify(trace.action, expected),
    }


def case_input_json(case: PriorAuthCase) -> dict[str, Any]:
    data = case.input.model_dump(mode="json")
    return {
        "as_of_date": data["as_of_date"],
        "patient": data["patient"],
        "medication": data["medication"],
        "insurance": data["insurance"],
        "policy_id": data["policy_id"],
        "documents": data["documents"],
        "content_hash": case.input.content_hash(),
    }


def diff_json(
    repo: Path, spec: DiffSpec, runs: dict[str, LoadedRun], case: PriorAuthCase
) -> dict[str, Any]:
    """A replay diff (relay replay's TraceDiff) for one of the demonstrated cases."""
    original_run = runs[spec.original]
    original = trace_for(original_run.at_op, spec.case_id)
    if spec.candidate_run is not None:
        candidate = trace_for(runs[spec.candidate_run].at_op, spec.case_id)
    else:
        assert spec.candidate_trace is not None
        candidate = trace_for(read_run_traces(repo / spec.candidate_trace), spec.case_id)
    if candidate.case_content_hash != case.input.content_hash():
        raise ExportError(f"{spec.case_id}: the candidate trace was made on different inputs")
    diff = diff_case(
        original,
        candidate,
        case,
        original_label=f"{original_run.spec.label} @{original.thresholds.auto_process:g}",
        candidate_label=spec.candidate_label,
    )
    assert diff.expected_original is not None and diff.expected_candidate is not None
    return diff.model_dump(mode="json") | {
        "title": spec.title,
        "summary": spec.summary,
        "question_sets": [original.question_set_version, candidate.question_set_version],
        "questions_compare": questions_compare(
            original.question_set_version, candidate.question_set_version
        ),
        "verdict_original": classify(diff.action_original, diff.expected_original),
        "verdict_candidate": classify(diff.action_candidate, diff.expected_candidate),
    }


def export_cases(
    repo: Path, out: Path, ctx: ExportContext
) -> tuple[list[Path], list[dict[str, Any]]]:
    written: list[Path] = []
    rows: list[dict[str, Any]] = []
    all_cases = {c.input.id: c for cases in ctx.dataset_cases.values() for c in cases}
    diffs: dict[str, list[dict[str, Any]]] = {}
    for spec in DIFFS:
        if spec.case_id not in all_cases:
            raise ExportError(f"diff for unknown case {spec.case_id}")
        diffs.setdefault(spec.case_id, []).append(
            diff_json(repo, spec, ctx.loaded_runs, all_cases[spec.case_id])
        )
    for dataset_id, cases in ctx.dataset_cases.items():
        runs = [ctx.loaded_runs[r.run_id] for r in RUNS if r.dataset == dataset_id]
        traces = {run.spec.run_id: {t.case_id: t for t in run.at_op} for run in runs}
        for case in cases:
            case_id = case.input.id
            results = [
                provider_result(run.spec, traces[run.spec.run_id][case_id], case) for run in runs
            ]
            expected = {r["expected"] for r in results}
            if len(expected) != 1:
                raise ExportError(f"{case_id}: the runs disagree on the expected action")
            category = category_of(case_id)
            detail = {
                "id": case_id,
                "dataset": dataset_id,
                "category": category,
                "input": case_input_json(case),
                "ground_truth": case.ground_truth.model_dump(mode="json")
                | {"expected_action": results[0]["expected"]},
                "providers": results,
                "diffs": diffs.get(case_id, []),
            }
            written.append(write_json(out / "cases" / f"{case_id}.json", detail))
            rows.append(
                {
                    "id": case_id,
                    "dataset": dataset_id,
                    "category": category,
                    "expected": results[0]["expected"],
                    "has_diff": case_id in diffs,
                    "results": {
                        r["slug"]: {"action": r["action"], "verdict": r["verdict"]}
                        for r in results
                        if r["provider"] != "groundtruth"
                    },
                }
            )
    index = {
        "categories": CATEGORY_LABELS,
        "datasets": [
            {
                "id": dataset_id,
                "label": dataset_spec(dataset_id).label,
                "providers": [
                    {
                        "slug": r.slug,
                        "label": r.label,
                        "run_id": r.run_id,
                        "auto_process": ctx.run_payloads[r.run_id]["operating_point"][
                            "auto_process"
                        ],
                    }
                    for r in RUNS
                    if r.dataset == dataset_id and r.provider != "groundtruth"
                ],
            }
            for dataset_id in ctx.dataset_cases
        ],
        "cases": rows,
    }
    written.append(write_json(out / "cases.json", index))
    return written, rows


# ---- index --------------------------------------------------------------------------------


def headline_rows(run_payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for run_id, note in HEADLINE:
        payload = run_payloads[run_id]
        metrics = payload["metrics"]
        rows.append(
            {
                "run_id": run_id,
                "dataset": payload["dataset"],
                "n": payload["n"],
                "label": payload["label"],
                "question_set": payload["question_set"],
                "auto_process": payload["operating_point"]["auto_process"],
                "flat": payload["frontier"]["flat"],
                "note": note,
                "correct": metrics["correct"],
                "automation": metrics["automation"],
                "uar": metrics["uar"],
            }
        )
    return rows


def _spend(repo: Path, relative: str) -> str:
    data = read_json(repo / relative)
    if "spent_usd" not in data:
        raise ExportError(f"{relative}: no spent_usd")
    return str(data["spent_usd"])


def export_core(
    repo: Path, out: Path, *, exported_at: str, git_sha: str | None
) -> tuple[list[Path], ExportContext]:
    ctx = ExportContext()
    for dataset in DATASETS:
        specs = [r for r in RUNS if r.dataset == dataset.id]
        if dataset.committed:
            cases = load_cases(repo, dataset)
            ctx.dataset_cases[dataset.id] = cases
            for spec in specs:
                loaded = load_run(repo, spec, cases)
                ctx.loaded_runs[spec.run_id] = loaded
                ctx.run_payloads[spec.run_id] = committed_run_payload(loaded, cases)
        else:
            for spec in specs:
                ctx.run_payloads[spec.run_id] = bundle_run_payload(repo, spec)

    written = [
        write_json(out / "runs" / f"{run_id}.json", payload)
        for run_id, payload in sorted(ctx.run_payloads.items())
    ]
    written.append(write_json(out / "runs.json", runs_index(ctx.run_payloads)))
    case_paths, rows = export_cases(repo, out, ctx)
    written += case_paths
    index = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": exported_at,
        "git_sha": git_sha,
        "disclaimer": DISCLAIMER,
        "hero": build_hero(ctx),
        "headline": headline_rows(ctx.run_payloads),
        "spend": {
            "claude_usd": _spend(repo, CLAUDE_SPEND),
            "jev_3d_usd": _spend(repo, JEV_SPEND),
        },
        "counts": {
            "cases": len(rows),
            "by_dataset": {d: len(c) for d, c in ctx.dataset_cases.items()},
            "runs": len(ctx.run_payloads),
        },
        "entry_cases": {"easy": EASY_CASE, "hard": HARD_CASE},
        "findings": build_findings(repo, ctx),
    }
    written.append(write_json(out / "index.json", index))
    return written, ctx
