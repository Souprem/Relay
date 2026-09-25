"""relay run / eval / generate, and the offline analyses sweep / report / compare."""

import asyncio
import os
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from typesafe_sdk import AsyncTypeSafeClient

from relay.cases.loader import CaseLoadError, load_dataset
from relay.cases.models import PriorAuthCase
from relay.decisions.base import DecisionProvider
from relay.decisions.ground_truth import GroundTruthProvider
from relay.decisions.jev import JevProvider
from relay.decisions.questions import DEFAULT_QUESTION_SET_VERSION, Q_V0_1, Q_V0_2
from relay.decisions.rules_baseline import RulesBaselineProvider
from relay.evaluation.artifacts import write_eval_bundle
from relay.evaluation.calibration import calibrate_run
from relay.evaluation.compare import compare_runs
from relay.evaluation.confusion import confusion_matrices
from relay.evaluation.frontier import DEFAULT_CEILING, frontier_csv, run_sweep
from relay.evaluation.metrics import EvalError, run_identity, score_run
from relay.evaluation.runner import RunConfigError, run_dataset, validate_run_config
from relay.generation.generator import generate_dataset, verify_dataset
from relay.generation.manifest import MANIFEST_DIR, dataset_hash, read_manifest, write_manifest
from relay.reporting import (
    DISCLAIMER,
    GROUNDTRUTH_NOTE,
    RULES_NOTE,
    describe_selection,
    render_comparison,
    render_eval_summary,
    render_frontier_table,
    render_run_report,
    render_run_table,
)
from relay.traces.models import RunManifest, WorkflowTrace
from relay.traces.store import TraceStore, current_git_sha, new_run_id, read_traces

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help=f"Relay: confidence-aware workflow engine. {DISCLAIMER}",
)


class ProviderName(StrEnum):
    jev = "jev"
    groundtruth = "groundtruth"
    rules = "rules"


class QuestionSet(StrEnum):
    q_v0_1 = Q_V0_1
    q_v0_2 = Q_V0_2


Dataset = Annotated[
    Path,
    typer.Option(exists=True, file_okay=False, dir_okay=True, help="Directory of case folders."),
]
Provider = Annotated[ProviderName, typer.Option(help="Decision provider.")]
Policy = Annotated[str, typer.Option(help="Policy/threshold version.")]
Concurrency = Annotated[int, typer.Option(min=1, help="Cases decided at once.")]
TracesDir = Annotated[Path, typer.Option(help="Where trace files are written.")]
ReportsDir = Annotated[Path, typer.Option(help="Where Markdown reports are written.")]
Questions = Annotated[
    QuestionSet | None,
    typer.Option(
        help=f"Jev question set (default {DEFAULT_QUESTION_SET_VERSION}). Only valid with "
        "--provider jev."
    ),
]
DEFAULT_QUESTIONS = QuestionSet(DEFAULT_QUESTION_SET_VERSION)

# The environment variable each provider needs, or None if it needs no key. One entry per provider.
PROVIDER_KEYS: dict[ProviderName, str | None] = {
    ProviderName.jev: "TYPESAFE_API_KEY",
    ProviderName.groundtruth: None,
    ProviderName.rules: None,
}
# Providers that accept --questions; the others reject an explicit --questions.
QUESTION_SET_PROVIDERS: frozenset[ProviderName] = frozenset({ProviderName.jev})
PROVIDER_NOTES: dict[ProviderName, str] = {
    ProviderName.groundtruth: GROUNDTRUTH_NOTE,
    ProviderName.rules: RULES_NOTE,
}

TraceFile = Annotated[
    Path, typer.Option(exists=True, dir_okay=False, help="Trace file (.jsonl or .jsonl.gz).")
]
Ceiling = Annotated[
    float, typer.Option(min=0.0, max=1.0, help="Maximum unsafe automation rate for selection.")
]
At = Annotated[
    float | None,
    typer.Option(min=0.0, max=1.0, help="Also report this auto_process threshold (e.g. from dev)."),
]


@app.callback()
def main(
    env_file: Annotated[Path, typer.Option(help="dotenv file with provider API keys.")] = Path(
        ".env"
    ),
) -> None:
    load_dotenv(env_file, override=False)


def _fail(message: str) -> typer.Exit:
    typer.echo(f"error: {message}", err=True)
    return typer.Exit(code=2)


def _load_cases(dataset: Path) -> list[PriorAuthCase]:
    try:
        return load_dataset(dataset)
    except CaseLoadError as error:
        raise _fail(str(error)) from error


def _read_trace_file(path: Path) -> list[WorkflowTrace]:
    try:
        return read_traces(path)
    except (ValueError, KeyError, OSError) as error:
        raise _fail(f"{path}: {error}") from error


def _resolve_questions(provider: ProviderName, questions: QuestionSet | None) -> QuestionSet | None:
    """The question set to run with: the default for jev, None for providers without one.

    An explicit --questions for a provider that has no question set is a usage error, not a
    silently ignored flag.
    """
    if provider not in QUESTION_SET_PROVIDERS:
        if questions is not None:
            raise _fail(
                f"--questions applies only to --provider jev; the {provider.value} provider "
                "has no question set"
            )
        return None
    return questions if questions is not None else DEFAULT_QUESTIONS


def _preflight(cases: list[PriorAuthCase], provider: ProviderName, policy: str) -> None:
    try:
        validate_run_config(cases, policy)
    except RunConfigError as error:
        raise _fail(str(error)) from error
    key = PROVIDER_KEYS[provider]
    if key is not None and not os.environ.get(key):
        raise _fail(f"{key} is not set (add it to .env or the environment)")


async def _build_provider(
    provider_name: ProviderName,
    cases: list[PriorAuthCase],
    questions: QuestionSet | None,
    stack: AsyncExitStack,
) -> DecisionProvider:
    """One explicit factory per provider. An unhandled name is a bug, never a silent Jev run."""
    if provider_name is ProviderName.jev:
        if questions is None:
            raise ValueError("the jev provider needs a question set")
        client = await stack.enter_async_context(AsyncTypeSafeClient(timeout=30.0))
        return JevProvider(client, question_set_version=questions.value)
    if provider_name is ProviderName.groundtruth:
        return GroundTruthProvider({c.input.id: c.ground_truth for c in cases})
    if provider_name is ProviderName.rules:
        return RulesBaselineProvider()
    raise ValueError(f"no factory for provider {provider_name!r}")


async def _execute(
    cases: list[PriorAuthCase],
    provider_name: ProviderName,
    policy: str,
    concurrency: int,
    traces_dir: Path,
    dataset: Path,
    questions: QuestionSet | None,
) -> tuple[RunManifest, list[WorkflowTrace]]:
    run_id = new_run_id()
    store = TraceStore.create(traces_dir, run_id)
    git_sha = current_git_sha()
    try:
        async with AsyncExitStack() as stack:
            provider = await _build_provider(provider_name, cases, questions, stack)
            traces = await run_dataset(
                cases,
                provider,
                policy_version=policy,
                store=store,
                run_id=run_id,
                concurrency=concurrency,
                git_sha=git_sha,
            )
    except Exception:
        if store.path.exists() and store.path.stat().st_size == 0:
            store.path.unlink()
        raise
    manifest = RunManifest(
        run_id=run_id,
        created_at=datetime.now(UTC),
        dataset_id=cases[0].input.dataset_id,
        dataset_path=str(dataset),
        provider=provider_name.value,
        policy_version=policy,
        question_set_version=traces[0].question_set_version if traces else None,
        case_count=len(traces),
        trace_file=str(store.path),
        relay_git_sha=git_sha,
    )
    store.write_manifest(manifest)
    return manifest, traces


def _run_and_report(
    cases: list[PriorAuthCase],
    provider: ProviderName,
    policy: str,
    concurrency: int,
    traces_dir: Path,
    reports_dir: Path,
    dataset: Path,
    questions: QuestionSet | None,
) -> list[WorkflowTrace]:
    resolved = _resolve_questions(provider, questions)
    _preflight(cases, provider, policy)
    if provider in PROVIDER_NOTES:
        typer.echo(f"NOTE: {PROVIDER_NOTES[provider]}")
    manifest, traces = asyncio.run(
        _execute(cases, provider, policy, concurrency, traces_dir, dataset, resolved)
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{manifest.run_id}.md"
    report_path.write_text(
        render_run_report(manifest, traces, {c.input.id: c.input for c in cases}),
        encoding="utf-8",
    )
    typer.echo(render_run_table(traces))
    typer.echo(f"\nTraces: {manifest.trace_file}\nReport: {report_path}")
    return traces


@app.command()
def run(
    dataset: Dataset,
    provider: Provider = ProviderName.jev,
    policy: Policy = "v0.1",
    concurrency: Concurrency = 4,
    traces_dir: TracesDir = Path("traces"),
    reports_dir: ReportsDir = Path("reports"),
    questions: Questions = None,
) -> None:
    """Decide every case in DATASET; write traces and a Markdown report."""
    cases = _load_cases(dataset)
    _run_and_report(
        cases, provider, policy, concurrency, traces_dir, reports_dir, dataset, questions
    )


@app.command("eval")
def eval_command(
    dataset: Dataset,
    provider: Provider = ProviderName.jev,
    policy: Policy = "v0.1",
    concurrency: Concurrency = 4,
    traces: Annotated[
        Path | None,
        typer.Option(
            exists=True,
            dir_okay=False,
            help="Score this existing trace file instead of running (no provider calls).",
        ),
    ] = None,
    traces_dir: TracesDir = Path("traces"),
    reports_dir: ReportsDir = Path("reports"),
    results_dir: Annotated[Path, typer.Option(help="Where results JSON is written.")] = Path(
        "results"
    ),
    questions: Questions = None,
) -> None:
    """Run (or re-score) DATASET and print action-level and decision-level metrics."""
    cases = _load_cases(dataset)
    if traces is None:
        trace_list = _run_and_report(
            cases, provider, policy, concurrency, traces_dir, reports_dir, dataset, questions
        )
    else:
        trace_list = _read_trace_file(traces)
    try:
        summary = score_run(trace_list, cases)
    except (EvalError, ValueError, KeyError) as error:
        raise _fail(str(error)) from error
    results_dir.mkdir(parents=True, exist_ok=True)
    results_path = results_dir / f"{summary.run_id}.json"
    results_path.write_text(summary.model_dump_json(indent=2) + "\n", encoding="utf-8")
    typer.echo("")
    typer.echo(render_eval_summary(summary))
    typer.echo(f"\nResults: {results_path}")


@app.command("sweep")
def sweep_command(
    dataset: Dataset,
    traces: TraceFile,
    ceiling: Ceiling = DEFAULT_CEILING,
    at: At = None,
    out: Annotated[Path, typer.Option(help="Where the sweep JSON and CSV are written.")] = Path(
        "results"
    ),
) -> None:
    """Sweep the auto_process threshold over stored traces (no provider calls)."""
    cases = _load_cases(dataset)
    trace_list = _read_trace_file(traces)
    try:
        result = run_sweep(trace_list, cases, ceiling=ceiling, at=at)
    except (EvalError, ValueError, KeyError) as error:
        raise _fail(str(error)) from error
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / f"{result.run_id}.sweep.json"
    csv_path = out / f"{result.run_id}.frontier.csv"
    json_path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    csv_path.write_text(frontier_csv(result.points), encoding="utf-8", newline="\n")
    typer.echo(render_frontier_table(result))
    typer.echo(f"\nSweep: {json_path}\nFrontier CSV: {csv_path}")


def _manifest_hash(dataset: Path, cases: list[PriorAuthCase]) -> str | None:
    """The dataset manifest hash if <dataset>/../manifests/<dataset_id>.json exists and matches."""
    dataset_id = cases[0].input.dataset_id
    path = dataset.parent / "manifests" / f"{dataset_id}.json"
    if not path.exists():
        return None
    try:
        manifest = read_manifest(path)
    except (ValueError, OSError) as error:
        raise _fail(f"{path}: {error}") from error
    if manifest.dataset_hash != dataset_hash(cases):
        raise _fail(f"{dataset} does not match its manifest {path} (dataset hash differs)")
    return manifest.dataset_hash


@app.command()
def report(
    dataset: Dataset,
    traces: TraceFile,
    ceiling: Ceiling = DEFAULT_CEILING,
    at: At = None,
    out: Annotated[
        Path | None, typer.Option(help="Bundle directory (default reports/eval-<run_id>/).")
    ] = None,
) -> None:
    """Write the evaluation report bundle for stored traces (no provider calls)."""
    cases = _load_cases(dataset)
    trace_list = _read_trace_file(traces)
    try:
        summary = score_run(trace_list, cases)
        calibration = calibrate_run(trace_list, cases)
        confusion = confusion_matrices(trace_list, cases)
        sweep = run_sweep(trace_list, cases, ceiling=ceiling, at=at)
    except (EvalError, ValueError, KeyError) as error:
        raise _fail(str(error)) from error
    identity = run_identity(trace_list, dataset_hash=_manifest_hash(dataset, cases))
    out_dir = out if out is not None else Path("reports") / f"eval-{summary.run_id}"
    paths = write_eval_bundle(
        out_dir,
        identity=identity,
        summary=summary,
        calibration=calibration,
        confusion=confusion,
        sweep=sweep,
    )
    typer.echo(render_eval_summary(summary, include_cases=False))
    typer.echo("")
    typer.echo(describe_selection(sweep))
    typer.echo(f"\nReport bundle: {out_dir}")
    for path in paths:
        typer.echo(f"  {path.name}")


@app.command()
def compare(
    dataset: Dataset,
    traces: Annotated[
        list[Path],
        typer.Option(
            exists=True, dir_okay=False, help="Trace file; repeat once per run (at least two)."
        ),
    ],
    labels: Annotated[
        str | None, typer.Option(help="Comma-separated run labels, in --traces order.")
    ] = None,
    ceiling: Ceiling = DEFAULT_CEILING,
    at: At = None,
) -> None:
    """Compare runs over the same dataset side by side, with action diffs (no provider calls)."""
    cases = _load_cases(dataset)
    trace_lists = [_read_trace_file(path) for path in traces]
    if labels is None:
        names = [
            t[0].run_id if t else path.stem for t, path in zip(trace_lists, traces, strict=True)
        ]
    else:
        names = [name.strip() for name in labels.split(",")]
        if len(names) != len(trace_lists):
            raise _fail(
                f"--labels has {len(names)} names but {len(trace_lists)} --traces were given"
            )
    try:
        comparison = compare_runs(
            list(zip(names, trace_lists, strict=True)), cases, ceiling=ceiling, at=at
        )
    except (EvalError, ValueError, KeyError) as error:
        raise _fail(str(error)) from error
    typer.echo(render_comparison(comparison))


@app.command()
def generate(
    out: Annotated[
        Path | None, typer.Option(help="Directory the case folders are written to (or checked).")
    ] = None,
    count: Annotated[int | None, typer.Option(min=1, help="Number of cases to generate.")] = None,
    seed: Annotated[int | None, typer.Option(min=0, help="Dataset seed.")] = None,
    dataset_id: Annotated[
        str | None, typer.Option(help="dataset_id written into every case.")
    ] = None,
    verify: Annotated[
        Path | None,
        typer.Option(exists=True, dir_okay=False, help="Manifest to verify instead of generating."),
    ] = None,
    manifests_dir: Annotated[
        Path,
        typer.Option(
            help="Where the dataset manifest is written (a relative path is resolved against "
            "the current directory; run from the repository root)."
        ),
    ] = MANIFEST_DIR,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite an existing manifest for this dataset id.")
    ] = False,
) -> None:
    """Generate a seeded synthetic dataset, or verify one against its manifest."""
    if verify is not None:
        if count is not None or seed is not None or dataset_id is not None:
            raise _fail("--verify cannot be combined with --count, --seed or --dataset-id")
        if out is not None and not out.exists():
            raise _fail(f"--out path does not exist: {out}")
        try:
            manifest = read_manifest(verify)
            problems = verify_dataset(manifest, out)
        except (ValueError, OSError) as error:
            raise _fail(f"{verify}: {error}") from error
        if problems:
            for problem in problems:
                typer.echo(f"MISMATCH: {problem}", err=True)
            raise typer.Exit(code=2)
        checked = str(out) if out is not None else "not checked"
        typer.echo(
            f"OK: {manifest.dataset_id} regenerates to {manifest.dataset_hash} "
            f"(files on disk: {checked})"
        )
        return
    if out is None or count is None or seed is None or dataset_id is None:
        raise _fail("generating requires --out, --count, --seed and --dataset-id")
    manifest_path = manifests_dir / f"{dataset_id}.json"
    if manifest_path.exists() and not force:
        raise _fail(f"manifest {manifest_path} already exists; pass --force to overwrite it")
    try:
        manifest = generate_dataset(count, seed, dataset_id, out)
    except (FileExistsError, ValueError) as error:
        raise _fail(str(error)) from error
    write_manifest(manifest, manifest_path)
    typer.echo(f"Generated {manifest.count} cases in {out}")
    typer.echo(f"Manifest: {manifest_path}")
    typer.echo(f"Dataset hash: {manifest.dataset_hash}")
    typer.echo(
        "Expected actions: "
        + ", ".join(f"{k} {v}" for k, v in manifest.expected_action_counts.items())
    )
