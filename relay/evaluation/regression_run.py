"""Running one regression gate: load the runs, build the candidate, diff, judge, write artifacts.

Offline only (spec G1): a candidate is an existing trace file or a policy replay of the
baseline's stored decisions, so nothing here builds a network client or needs a key. Every
problem with the inputs raises RegressionInputError, which the CLI maps to exit 2.
"""

import gzip
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from relay.cases.loader import CaseLoadError, load_dataset
from relay.cases.models import PriorAuthCase
from relay.cases.policies import latest_policy_for, load_policy
from relay.evaluation.metrics import EvalError
from relay.evaluation.regression import RegressionResult, Waiver, WaiverFile, build_result
from relay.evaluation.runner import sample_cases
from relay.evaluation.tracediff import (
    REPRODUCE_LABEL,
    candidate_trace_label,
    diff_runs,
    original_label,
    policy_replay_label,
    replay_run,
)
from relay.generation.manifest import dataset_hash, read_manifest
from relay.traces.models import RunManifest, WorkflowTrace
from relay.traces.store import read_traces

CANDIDATE_TRACES = "candidate.jsonl.gz"
CANDIDATE_MANIFEST = "candidate.manifest.json"
BASELINE_TRACES = "baseline.jsonl.gz"
BASELINE_MANIFEST = "baseline.manifest.json"


class RegressionInputError(ValueError):
    """The gate cannot run on these inputs (a usage or input error: exit 2)."""


class CandidateSpec(BaseModel):
    """Where the candidate comes from (spec G2). Exactly one of traces / policy / latest_policy /
    reproduce, or `at` alone (a policy replay of the baseline under its own policy at `at`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    traces: str | None = None
    policy: str | None = None
    latest_policy: bool = False
    at: float | None = None
    reproduce: bool = False

    @property
    def is_policy_replay(self) -> bool:
        return self.traces is None and not self.reproduce

    @property
    def redecided(self) -> bool:
        """True when the candidate's decisions were replayed rather than read as recorded: any
        policy replay always re-decides; a candidate trace file only when --candidate-at re-runs
        it. Used wherever a re-decided candidate needs its own written trace file."""
        return self.is_policy_replay or (self.traces is not None and self.at is not None)


class GateSpec(BaseModel):
    """One entry of evals/regression/gates.json. Paths are relative to the working directory
    (run from the repository root, as for `relay generate`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    dataset: str
    baseline: str
    candidate: CandidateSpec
    baseline_at: float | None = None
    max_regressed: int | None = Field(default=None, ge=0)
    waivers: str | None = None
    requires_generated: bool = False


class GatesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gates: list[GateSpec]


@dataclass(frozen=True)
class RegressionRequest:
    dataset: Path
    baseline: Path
    candidate: CandidateSpec
    baseline_at: float | None = None
    waivers: Path | None = None
    max_regressed: int | None = None
    gate: str | None = None

    @classmethod
    def from_gate(cls, spec: GateSpec) -> "RegressionRequest":
        return cls(
            dataset=Path(spec.dataset),
            baseline=Path(spec.baseline),
            candidate=spec.candidate,
            baseline_at=spec.baseline_at,
            waivers=None if spec.waivers is None else Path(spec.waivers),
            max_regressed=spec.max_regressed,
            gate=spec.name,
        )


@dataclass(frozen=True)
class RegressionRun:
    result: RegressionResult
    baseline: list[WorkflowTrace]  # after --baseline-at, if given
    candidate: list[WorkflowTrace]
    source_manifest: RunManifest | None  # the baseline's run manifest, if found
    dataset: Path


def validate_request(candidate: CandidateSpec, baseline_at: float | None) -> None:
    """The candidate-source rules of spec G2; RegressionInputError on a violation."""
    sources = [
        name
        for name, used in (
            ("--candidate-traces", candidate.traces is not None),
            ("--candidate-policy", candidate.policy is not None),
            ("--candidate-latest-policy", candidate.latest_policy),
            ("--reproduce", candidate.reproduce),
        )
        if used
    ]
    if len(sources) > 1:
        raise RegressionInputError("choose one candidate source, not " + " and ".join(sources))
    if candidate.reproduce and (candidate.at is not None or baseline_at is not None):
        raise RegressionInputError(
            "--reproduce replays the baseline as recorded; it cannot be combined with "
            "--candidate-at or --baseline-at"
        )
    if not sources and candidate.at is None:
        raise RegressionInputError(
            "no candidate: give --candidate-traces, --candidate-policy, "
            "--candidate-latest-policy, --candidate-at or --reproduce"
        )
    for flag, value in (("--candidate-at", candidate.at), ("--baseline-at", baseline_at)):
        if value is not None and not 0.0 < value <= 1.0:
            raise RegressionInputError(f"{flag} must be in (0, 1], got {value:g}")


def find_run_manifest(trace_file: Path) -> RunManifest | None:
    """The run manifest beside a trace file: <stem>.manifest.json (fresh runs, regression
    candidates) or run-manifest.json (committed baselines). None if neither exists."""
    stem = trace_file.name.removesuffix(".gz").removesuffix(".jsonl")
    for path in (
        trace_file.parent / f"{stem}.manifest.json",
        trace_file.parent / "run-manifest.json",
    ):
        if path.exists():
            try:
                return RunManifest.model_validate_json(path.read_text(encoding="utf-8"))
            except (ValidationError, OSError) as error:
                raise RegressionInputError(f"{path}: {error}") from error
    return None


def load_waivers(path: Path) -> list[Waiver]:
    try:
        return WaiverFile.model_validate_json(path.read_text(encoding="utf-8")).waivers
    except (ValidationError, OSError) as error:
        raise RegressionInputError(f"{path}: malformed waiver file: {error}") from error


def load_gates(path: Path) -> GatesConfig:
    try:
        config = GatesConfig.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValidationError, OSError) as error:
        raise RegressionInputError(f"{path}: malformed gates file: {error}") from error
    names = [g.name for g in config.gates]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise RegressionInputError(f"{path}: duplicate gate names {duplicates}")
    known = set(names)
    for spec in config.gates:
        try:
            validate_request(spec.candidate, spec.baseline_at)
        except RegressionInputError as error:
            raise RegressionInputError(f"{path}: gate {spec.name}: {error}") from error
        if spec.waivers is not None:
            # M2: a waiver scoped to neither "*" nor a real gate name fails closed (applies_to
            # never matches it), but silently — reject the typo instead of letting it hide.
            unknown = sorted(
                {
                    w.gate
                    for w in load_waivers(Path(spec.waivers))
                    if w.gate != "*" and w.gate not in known
                }
            )
            if unknown:
                raise RegressionInputError(
                    f"{path}: gate {spec.name}: waiver file {spec.waivers} scopes waiver(s) to "
                    f"unknown gate(s) {unknown}"
                )
    return config


def _dataset_hash(dataset: Path, cases: Sequence[PriorAuthCase]) -> str | None:
    """The committed manifest hash for a generated dataset (<dataset>/../manifests/<id>.json),
    checked against the cases on disk; None when there is no manifest."""
    path = dataset.parent / "manifests" / f"{cases[0].input.dataset_id}.json"
    if not path.exists():
        return None
    try:
        manifest = read_manifest(path)
    except (ValueError, OSError) as error:
        raise RegressionInputError(f"{path}: {error}") from error
    if manifest.dataset_hash != dataset_hash(cases):
        raise RegressionInputError(f"{dataset} does not match its manifest {path}")
    return manifest.dataset_hash


def _read(path: Path) -> list[WorkflowTrace]:
    try:
        traces = read_traces(path)
    except (ValueError, KeyError, OSError) as error:
        raise RegressionInputError(f"{path}: {error}") from error
    if not traces:
        raise RegressionInputError(f"{path}: no traces")
    return traces


def _load_cases(dataset: Path) -> list[PriorAuthCase]:
    try:
        cases = load_dataset(dataset)
    except CaseLoadError as error:
        raise RegressionInputError(str(error)) from error
    if not cases:
        raise RegressionInputError(f"{dataset}: no cases")
    return cases


def _candidate(
    request: RegressionRequest, baseline: list[WorkflowTrace], cases: list[PriorAuthCase]
) -> tuple[list[WorkflowTrace], str]:
    spec = request.candidate
    if spec.reproduce:
        return replay_run(baseline, cases, policy_id=None, auto_process=None), REPRODUCE_LABEL
    if spec.traces is not None:
        recorded = _read(Path(spec.traces))
        label = candidate_trace_label(recorded[0])
        if not spec.redecided:
            return recorded, label
        replayed = replay_run(recorded, cases, policy_id=None, auto_process=spec.at)
        return replayed, f"{label} · re-decided at auto_process={spec.at:g}"
    if spec.latest_policy:
        try:
            target = latest_policy_for(baseline[0].policy_id)
        except KeyError as error:
            raise RegressionInputError(str(error.args[0])) from error
    else:
        target = spec.policy or baseline[0].policy_id
    replayed = replay_run(baseline, cases, policy_id=target, auto_process=spec.at)
    return replayed, policy_replay_label(load_policy(target), replayed[0].thresholds, spec.at)


def replay_command_for(request: RegressionRequest, out: Path | None) -> Callable[[str], str | None]:
    """A `relay replay` command that reproduces one case's diff, or None when it would need
    files that exist only with --out (a re-decided baseline or candidate)."""
    spec = request.candidate
    if request.baseline_at is None:
        traces: Path | None = request.baseline
    else:
        traces = None if out is None else out / BASELINE_TRACES
    if spec.reproduce:
        extra: str | None = ""
    elif spec.traces is not None and not spec.redecided:
        extra = f" --candidate-traces {spec.traces}"
    elif spec.is_policy_replay and request.baseline_at is None:
        extra = (
            (f" --policy {spec.policy}" if spec.policy else "")
            + (" --latest-policy" if spec.latest_policy else "")
            + (f" --at {spec.at:g}" if spec.at is not None else "")
        )
    else:
        extra = None if out is None else f" --candidate-traces {out / CANDIDATE_TRACES}"
    if traces is None or extra is None:
        return lambda _case_id: None
    return lambda case_id: (
        f"relay replay {case_id} --traces {traces} --dataset {request.dataset}{extra}"
    )


def run_regression(request: RegressionRequest, *, out: Path | None = None) -> RegressionRun:
    """One gate, start to finish (writing nothing; see write_outputs)."""
    validate_request(request.candidate, request.baseline_at)
    cases = _load_cases(request.dataset)
    hash_ = _dataset_hash(request.dataset, cases)
    recorded = _read(request.baseline)
    source = find_run_manifest(request.baseline)
    if source is not None and source.run_id != recorded[0].run_id:
        # M9: an untrusted run-manifest.json (e.g. left over from a different run) would
        # otherwise subsample against the wrong manifest with a confusing downstream error.
        raise RegressionInputError(
            f"{request.baseline}: run manifest run_id {source.run_id!r} does not match the "
            f"trace file's run_id {recorded[0].run_id!r}"
        )
    if source is not None and source.sample_limit is not None:
        if source.sample_seed is None:
            raise RegressionInputError(f"{request.baseline}: run manifest has no sample_seed")
        cases = sample_cases(cases, source.sample_limit, source.sample_seed)
    waivers = [] if request.waivers is None else load_waivers(request.waivers)
    try:
        baseline = (
            recorded
            if request.baseline_at is None
            else replay_run(recorded, cases, policy_id=None, auto_process=request.baseline_at)
        )
        candidate, candidate_label = _candidate(request, recorded, cases)
        baseline_label = original_label(baseline[0])
        diffs = diff_runs(
            baseline,
            candidate,
            cases,
            original_label=baseline_label,
            candidate_label=candidate_label,
        )
        result = build_result(
            diffs,
            baseline,
            candidate,
            cases,
            baseline_label=baseline_label,
            candidate_label=candidate_label,
            gate=request.gate,
            reproduce=request.candidate.reproduce,
            waivers=waivers,
            max_regressed=request.max_regressed,
            dataset_hash=hash_,
            replay_command=replay_command_for(request, out),
        )
    except EvalError as error:
        raise RegressionInputError(str(error)) from error
    return RegressionRun(
        result=result,
        baseline=baseline,
        candidate=candidate,
        source_manifest=source,
        dataset=request.dataset,
    )


def _write_traces(path: Path, traces: Sequence[WorkflowTrace]) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for trace in traces:
            handle.write(trace.model_dump_json() + "\n")


def _write_simulated_run(
    source: RunManifest | None,
    dataset: Path,
    traces: Sequence[WorkflowTrace],
    trace_path: Path,
    manifest_path: Path,
) -> None:
    """A simulated run that `relay eval --traces`, `compare` and `replay` can read: gzipped
    traces plus a RunManifest with mode "simulated" and source_run_id (typed fields since 3C),
    and extra keys policy_id and thresholds. `source` is the baseline's run manifest, if found
    (its sample_limit/sample_seed carry over)."""
    _write_traces(trace_path, traces)
    first = traces[0]
    manifest = RunManifest(
        run_id=first.run_id,
        created_at=datetime.now(UTC),
        dataset_id=first.dataset_id,
        dataset_path=str(dataset),
        provider=first.provider,
        policy_version=first.policy_version,
        question_set_version=first.question_set_version,
        case_count=len(traces),
        trace_file=str(trace_path),
        relay_git_sha=first.relay_git_sha,
        sample_limit=None if source is None else source.sample_limit,
        sample_seed=None if source is None else source.sample_seed,
        mode="simulated",
        source_run_id=first.run_id.removeprefix("replay-"),
        ablation=first.ablation,
    )
    data = manifest.model_dump(mode="json") | {
        "policy_id": first.policy_id,
        "thresholds": first.thresholds.model_dump(mode="json"),
    }
    manifest_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_outputs(
    out: Path, run: RegressionRun, request: RegressionRequest, rendered: str
) -> list[Path]:
    """regression.json and regression.md (the terminal text), plus the simulated runs the
    replay commands point at: candidate.* for a replayed candidate, baseline.* after
    --baseline-at. Returns the paths written."""
    out.mkdir(parents=True, exist_ok=True)
    paths = [out / "regression.json", out / "regression.md"]
    paths[0].write_text(run.result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    paths[1].write_text(rendered + "\n", encoding="utf-8")
    spec = request.candidate
    if spec.redecided:
        pair = (out / CANDIDATE_TRACES, out / CANDIDATE_MANIFEST)
        _write_simulated_run(run.source_manifest, run.dataset, run.candidate, *pair)
        paths += pair
    if request.baseline_at is not None:
        pair = (out / BASELINE_TRACES, out / BASELINE_MANIFEST)
        _write_simulated_run(run.source_manifest, run.dataset, run.baseline, *pair)
        paths += pair
    return paths
