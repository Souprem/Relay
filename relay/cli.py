"""relay run / relay eval / relay generate."""

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
from relay.evaluation.metrics import EvalError, score_run
from relay.evaluation.runner import RunConfigError, run_dataset, validate_run_config
from relay.generation.generator import generate_dataset, verify_dataset
from relay.generation.manifest import MANIFEST_DIR, read_manifest, write_manifest
from relay.reporting import (
    DISCLAIMER,
    GROUNDTRUTH_NOTE,
    render_eval_summary,
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


Dataset = Annotated[
    Path,
    typer.Option(exists=True, file_okay=False, dir_okay=True, help="Directory of case folders."),
]
Provider = Annotated[ProviderName, typer.Option(help="Decision provider.")]
Policy = Annotated[str, typer.Option(help="Policy/threshold version.")]
Concurrency = Annotated[int, typer.Option(min=1, help="Cases decided at once.")]
TracesDir = Annotated[Path, typer.Option(help="Where trace files are written.")]
ReportsDir = Annotated[Path, typer.Option(help="Where Markdown reports are written.")]


@app.callback()
def main(
    env_file: Annotated[Path, typer.Option(help="dotenv file with TYPESAFE_API_KEY.")] = Path(
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


def _preflight(cases: list[PriorAuthCase], provider: ProviderName, policy: str) -> None:
    try:
        validate_run_config(cases, policy)
    except RunConfigError as error:
        raise _fail(str(error)) from error
    if provider is ProviderName.jev and not os.environ.get("TYPESAFE_API_KEY"):
        raise _fail("TYPESAFE_API_KEY is not set (add it to .env or the environment)")


async def _execute(
    cases: list[PriorAuthCase],
    provider_name: ProviderName,
    policy: str,
    concurrency: int,
    traces_dir: Path,
    dataset: Path,
) -> tuple[RunManifest, list[WorkflowTrace]]:
    run_id = new_run_id()
    store = TraceStore.create(traces_dir, run_id)
    git_sha = current_git_sha()
    try:
        async with AsyncExitStack() as stack:
            provider: DecisionProvider
            if provider_name is ProviderName.groundtruth:
                provider = GroundTruthProvider({c.input.id: c.ground_truth for c in cases})
            else:
                client = await stack.enter_async_context(AsyncTypeSafeClient(timeout=30.0))
                provider = JevProvider(client)
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
) -> list[WorkflowTrace]:
    _preflight(cases, provider, policy)
    if provider is ProviderName.groundtruth:
        typer.echo(f"NOTE: {GROUNDTRUTH_NOTE}")
    manifest, traces = asyncio.run(
        _execute(cases, provider, policy, concurrency, traces_dir, dataset)
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
) -> None:
    """Decide every case in DATASET; write traces and a Markdown report."""
    cases = _load_cases(dataset)
    _run_and_report(cases, provider, policy, concurrency, traces_dir, reports_dir, dataset)


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
) -> None:
    """Run (or re-score) DATASET and print action-level and decision-level metrics."""
    cases = _load_cases(dataset)
    if traces is None:
        trace_list = _run_and_report(
            cases, provider, policy, concurrency, traces_dir, reports_dir, dataset
        )
    else:
        try:
            trace_list = read_traces(traces)
        except (ValueError, KeyError) as error:
            raise _fail(str(error)) from error
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
        Path, typer.Option(help="Where the dataset manifest is written.")
    ] = MANIFEST_DIR,
) -> None:
    """Generate a seeded synthetic dataset, or verify one against its manifest."""
    if verify is not None:
        if count is not None or seed is not None or dataset_id is not None:
            raise _fail("--verify cannot be combined with --count, --seed or --dataset-id")
        try:
            manifest = read_manifest(verify)
        except ValueError as error:
            raise _fail(f"{verify}: {error}") from error
        problems = verify_dataset(manifest, out)
        if problems:
            for problem in problems:
                typer.echo(f"MISMATCH: {problem}", err=True)
            raise typer.Exit(code=2)
        checked = str(out) if out is not None and out.exists() else "not checked"
        typer.echo(
            f"OK: {manifest.dataset_id} regenerates to {manifest.dataset_hash} "
            f"(files on disk: {checked})"
        )
        return
    if out is None or count is None or seed is None or dataset_id is None:
        raise _fail("generating requires --out, --count, --seed and --dataset-id")
    try:
        manifest = generate_dataset(count, seed, dataset_id, out)
    except (FileExistsError, ValueError) as error:
        raise _fail(str(error)) from error
    manifest_path = manifests_dir / f"{dataset_id}.json"
    write_manifest(manifest, manifest_path)
    typer.echo(f"Generated {manifest.count} cases in {out}")
    typer.echo(f"Manifest: {manifest_path}")
    typer.echo(f"Dataset hash: {manifest.dataset_hash}")
    typer.echo(
        "Expected actions: "
        + ", ".join(f"{k} {v}" for k, v in manifest.expected_action_counts.items())
    )
