"""relay run / eval / generate, and the offline analyses sweep / report / compare / replay /
regression."""

import asyncio
import contextlib
import os
import sys
from collections.abc import Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import anthropic
import typer
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from pydantic import ValidationError
from typesafe_sdk import AsyncTypeSafeClient

from relay.cases.loader import CaseLoadError, load_case, load_dataset
from relay.cases.models import PriorAuthCase
from relay.cases.policies import AuthorizationPolicy, latest_policy_for, load_policy
from relay.decisions.base import DecisionProvider
from relay.decisions.claude import ClaudeProvider, Mode
from relay.decisions.claude_batch import ClaudeBatchProvider
from relay.decisions.claude_prompt import CLAUDE_QUESTION_SETS
from relay.decisions.ground_truth import GroundTruthProvider
from relay.decisions.jev import JevProvider
from relay.decisions.questions import DEFAULT_QUESTION_SET_VERSION, Q_V0_2, QUESTION_SET_VERSIONS
from relay.decisions.rules_baseline import RulesBaselineProvider
from relay.evaluation.artifacts import write_eval_bundle
from relay.evaluation.budget import (
    DEFAULT_BUDGET_USD,
    DEFAULT_LEDGER,
    BudgetExceeded,
    SpendEntry,
    SpendLedger,
    attach_batch,
    check_budget,
    find_batch,
    load_ledger,
    project_cost,
    reserve,
    settle,
    write_ledger,
)
from relay.evaluation.calibration import calibrate_run
from relay.evaluation.compare import compare_runs
from relay.evaluation.confusion import confusion_matrices
from relay.evaluation.frontier import DEFAULT_CEILING, frontier_csv, run_sweep
from relay.evaluation.metrics import EvalError, run_identity, score_run
from relay.evaluation.regression import RegressionResult
from relay.evaluation.regression_run import (
    CandidateSpec,
    RegressionInputError,
    RegressionRequest,
    load_gates,
    run_regression,
    write_outputs,
)
from relay.evaluation.runner import (
    RunConfigError,
    run_dataset,
    sample_cases,
    validate_run_config,
)
from relay.evaluation.tracediff import (
    REPRODUCE_LABEL,
    candidate_trace_label,
    diff_case,
    live_label,
    original_label,
    policy_replay_label,
    replay_exit_code,
    replay_thresholds,
    replay_trace,
)
from relay.generation.generator import generate_dataset, verify_dataset
from relay.generation.manifest import MANIFEST_DIR, dataset_hash, read_manifest, write_manifest
from relay.reporting import (
    CLAUDE_NOTE,
    DISCLAIMER,
    GROUNDTRUTH_NOTE,
    RULES_NOTE,
    GateRow,
    describe_selection,
    render_comparison,
    render_eval_summary,
    render_frontier_table,
    render_gate_summary,
    render_regression,
    render_run_report,
    render_run_table,
    render_trace_diff,
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
    claude = "claude"


class ClaudeMode(StrEnum):
    sync = "sync"
    batch = "batch"


CLAUDE_TIMEOUT_S = 300.0


@dataclass(frozen=True)
class ClaudeRun:
    """Settings that only the claude provider takes: mode, budget guard, batch re-attachment."""

    mode: Mode
    budget_usd: Decimal
    ledger: Path
    batch_id: str | None = None


@dataclass(frozen=True)
class QuestionSets:
    """The question sets a provider accepts for --questions, and the one it runs by default."""

    allowed: tuple[str, ...]
    default: str


# Providers that take --questions. A provider missing here has no question set, and an explicit
# --questions for it is a usage error rather than a silently ignored flag.
PROVIDER_QUESTION_SETS: dict[ProviderName, QuestionSets] = {
    ProviderName.jev: QuestionSets(QUESTION_SET_VERSIONS, DEFAULT_QUESTION_SET_VERSION),
    ProviderName.claude: QuestionSets(CLAUDE_QUESTION_SETS, Q_V0_2),
}


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
    str | None,
    typer.Option(
        help="Question set, for providers that have one ("
        + "; ".join(
            f"{name.value}: {', '.join(sets.allowed)}, default {sets.default}"
            for name, sets in PROVIDER_QUESTION_SETS.items()
        )
        + "). An error with any other provider."
    ),
]

# The environment variable each provider needs, or None if it needs no key. One entry per provider.
PROVIDER_KEYS: dict[ProviderName, str | None] = {
    ProviderName.jev: "TYPESAFE_API_KEY",
    ProviderName.groundtruth: None,
    ProviderName.rules: None,
    ProviderName.claude: "ANTHROPIC_API_KEY",
}
PROVIDER_NOTES: dict[ProviderName, str] = {
    ProviderName.groundtruth: GROUNDTRUTH_NOTE,
    ProviderName.rules: RULES_NOTE,
    ProviderName.claude: CLAUDE_NOTE,
}

Limit = Annotated[
    int | None,
    typer.Option(
        min=1, help="Use a deterministic subsample of this many cases (needs --sample-seed)."
    ),
]
SampleSeed = Annotated[int | None, typer.Option(min=0, help="Seed for the --limit subsample.")]

ModeOption = Annotated[
    ClaudeMode | None,
    typer.Option(
        "--mode", help="claude only: sync (default; latency measured) or batch (half price)."
    ),
]
BudgetUsd = Annotated[
    float | None,
    typer.Option(
        min=0.0,
        help=f"claude only: refuse to start if ledger spend + projected cost exceeds this "
        f"(default {DEFAULT_BUDGET_USD}).",
    ),
]
LedgerOption = Annotated[
    Path | None, typer.Option(help=f"claude only: spend ledger (default {DEFAULT_LEDGER}).")
]
BatchId = Annotated[
    str | None,
    typer.Option(help="claude --mode batch only: re-attach to this submitted Message Batch."),
]

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


def _apply_limit(
    cases: list[PriorAuthCase], limit: int | None, seed: int | None
) -> tuple[list[PriorAuthCase], tuple[int, int] | None]:
    """The cases to use and the (limit, seed) subsample, if one was requested."""
    if limit is None and seed is None:
        return cases, None
    if limit is None or seed is None:
        raise _fail("--limit and --sample-seed must be given together")
    return sample_cases(cases, limit, seed), (limit, seed)


def _read_trace_file(path: Path) -> list[WorkflowTrace]:
    try:
        return read_traces(path)
    except (ValueError, KeyError, OSError) as error:
        raise _fail(f"{path}: {error}") from error


def _resolve_questions(provider: ProviderName, questions: str | None) -> str | None:
    """The question set to run with: the provider's default, or None if it has no question set.

    An explicit --questions must be one the provider allows; for a provider without a question
    set it is a usage error.
    """
    sets = PROVIDER_QUESTION_SETS.get(provider)
    if sets is None:
        if questions is not None:
            names = ", ".join(p.value for p in PROVIDER_QUESTION_SETS)
            raise _fail(
                f"--questions does not apply to --provider {provider.value}: the "
                f"{provider.value} provider has no question set (providers with one: {names})"
            )
        return None
    if questions is None:
        return sets.default
    if questions not in sets.allowed:
        raise _fail(
            f"--questions {questions!r} is not available for --provider {provider.value}; "
            f"choose one of: {', '.join(sets.allowed)}"
        )
    return questions


def _resolve_claude(
    provider: ProviderName,
    mode: ClaudeMode | None = None,
    budget_usd: float | None = None,
    ledger: Path | None = None,
    batch_id: str | None = None,
) -> ClaudeRun | None:
    """Claude run settings with defaults filled in, or None for other providers.

    Claude-only flags given with another provider are a usage error, not silently ignored.
    """
    if provider is not ProviderName.claude:
        flags = {
            "--mode": mode,
            "--budget-usd": budget_usd,
            "--ledger": ledger,
            "--batch-id": batch_id,
        }
        given = [flag for flag, value in flags.items() if value is not None]
        if given:
            raise _fail(f"{', '.join(given)} applies only to --provider claude")
        return None
    resolved: Mode = "sync" if mode is None else mode.value
    if batch_id is not None and resolved != "batch":
        raise _fail("--batch-id needs --mode batch")
    return ClaudeRun(
        mode=resolved,
        budget_usd=DEFAULT_BUDGET_USD if budget_usd is None else Decimal(str(budget_usd)),
        ledger=DEFAULT_LEDGER if ledger is None else ledger,
        batch_id=batch_id,
    )


def _load_ledger(claude: ClaudeRun) -> SpendLedger:
    try:
        return load_ledger(claude.ledger)
    except (ValidationError, OSError) as error:
        raise _fail(f"{claude.ledger}: {error}") from error


def _find_settled_batch_cost_entry(ledger: SpendLedger, batch_id: str) -> SpendEntry | None:
    """Among every entry that ever carried this batch id, the one that actually holds its real,
    non-zero cost (M1). find_batch returns the *first* match, which after a normal re-attach is
    the superseded $0 entry (its cost moved to a later run's entry) -- not the one worth citing
    when refusing a repeat re-attach.
    """
    candidates = [
        e
        for e in ledger.entries
        if e.batch_id == batch_id and e.status == "settled" and e.cost_usd > 0
    ]
    return candidates[-1] if candidates else None


def _find_orphan_reservation(ledger: SpendLedger, dataset_id: str, cases: int) -> SpendEntry | None:
    """The leftover reservation from an ambiguous create() failure (C2/I2): a still-"reserved"
    batch entry with no batch id yet, for this run's dataset and case count.

    Returned only when there is exactly one candidate. With zero or more than one, binding
    automatically would be guessing which run's money a newly-discovered batch id actually
    belongs to, so the caller falls back to a fresh (but still budget-check-free) reservation
    instead.
    """
    candidates = [
        e
        for e in ledger.entries
        if e.status == "reserved"
        and e.mode == "batch"
        and e.batch_id is None
        and e.dataset_id == dataset_id
        and e.cases == cases
    ]
    return candidates[0] if len(candidates) == 1 else None


def _claude_budget_check(claude: ClaudeRun, cases: list[PriorAuthCase]) -> Decimal:
    """The projected cost of this run; exits 2 with the numbers if it would break the budget.

    A --batch-id re-attach never re-checks the cap (C4/I1): re-attaching only ever calls
    retrieve()/results(), never create() (see ClaudeBatchProvider.prepare), so it can never spend
    more than what is already being billed server-side, no matter what the ledger's current spend
    or the budget happens to be. Three cases:
      - The batch id is already in the ledger and still "reserved": nothing further will be
        billed by collecting its results.
      - The batch id is already in the ledger and "settled": refused outright, rather than
        silently projecting $0 and re-processing it into a second settled entry for the same
        money (this is what C4 originally reported: the budget check was skipped, but nothing
        stopped a repeat re-attach from quietly duplicating a real, already-checked cost).
      - The batch id is unknown to the ledger (the operator found it by hand via `batches list`
        after an ambiguous create() failure, per C2): it is bound to the matching orphaned
        reservation left by that failure, if exactly one exists, so nothing new is reserved. If
        none (or more than one) matches, a fresh bookkeeping reservation is made and a warning is
        printed, but the cap still isn't checked.
    """
    ledger = _load_ledger(claude)
    if claude.batch_id is None:
        projected = project_cost(ledger, len(cases), claude.mode)
        try:
            check_budget(ledger, projected, claude.budget_usd)
        except BudgetExceeded as error:
            raise _fail(str(error)) from error
    else:
        found = find_batch(ledger, claude.batch_id)
        if found is not None and found.status == "settled":
            carrier = _find_settled_batch_cost_entry(ledger, claude.batch_id) or found
            raise _fail(
                f"Message Batch {claude.batch_id} is already settled in the ledger (run "
                f"{carrier.run_id}, ${carrier.cost_usd:.4f}); nothing to re-attach. Re-evaluate "
                "its trace file with `relay eval --traces <file>` if you need to re-score it."
            )
        if found is not None:
            projected = Decimal("0")
        else:
            dataset_id = cases[0].input.dataset_id
            orphan = _find_orphan_reservation(ledger, dataset_id, len(cases))
            if orphan is not None:
                write_ledger(claude.ledger, attach_batch(ledger, orphan.run_id, claude.batch_id))
                projected = Decimal("0")
            else:
                projected = project_cost(ledger, len(cases), claude.mode)
                typer.echo(
                    f"warning: Message Batch {claude.batch_id} is not in the ledger, and no "
                    "single orphaned reservation (a reserved batch entry with no batch id, "
                    f"dataset {dataset_id!r}, {len(cases)} cases) was found to attach it to. "
                    f"Reserving ${projected:.4f} for bookkeeping, but not checking the "
                    f"${claude.budget_usd:.2f} budget cap: re-attaching only collects results, "
                    "it never spends anything new.",
                    err=True,
                )
    typer.echo(
        f"Claude budget: spent ${ledger.spent_usd:.4f}, projected ${projected:.4f} for "
        f"{len(cases)} cases ({claude.mode}), budget ${claude.budget_usd:.2f}"
    )
    return projected


def _reserve(
    claude: ClaudeRun, run_id: str, cases: list[PriorAuthCase], projected: Decimal
) -> None:
    ledger = reserve(
        _load_ledger(claude),
        run_id=run_id,
        dataset_id=cases[0].input.dataset_id,
        mode=claude.mode,
        cases=len(cases),
        projected=projected,
    )
    write_ledger(claude.ledger, ledger)


def _record_batch(claude: ClaudeRun, run_id: str, batch_id: str) -> None:
    write_ledger(claude.ledger, attach_batch(_load_ledger(claude), run_id, batch_id))
    typer.echo(
        f"Submitted Message Batch {batch_id}. If this run is interrupted, re-attach with "
        f"--mode batch --batch-id {batch_id} instead of submitting again."
    )


def _partial_traces(store: TraceStore) -> list[WorkflowTrace] | None:
    """Traces already durably written to disk before a run died partway through. Read from the
    file rather than the in-memory list, which is empty until run_dataset returns.

    Parses line-by-line (C6) rather than handing the whole file to read_traces: a crash mid-append
    can leave a torn last line (a partial write, no trailing newline), and that alone must not
    discard the complete lines written before it. Only a bad *last* line is treated as a torn
    write and dropped; a bad line anywhere else means the file is corrupt in some way this
    function doesn't understand, and returns None rather than guessing which lines are real. The
    caller must treat None as "unknown, don't settle" rather than "zero cases completed".

    Reads with errors="replace" (M2): a write cut short mid multi-byte UTF-8 character (trace text
    can contain non-ASCII, e.g. an em dash) would otherwise raise UnicodeDecodeError while reading
    the *whole* file, before line-by-line recovery ever gets a chance to run. Replacing the
    undecodable tail with U+FFFD keeps every complete line decodable; the torn line then simply
    fails JSON parsing and is dropped by the same "bad last line" path as any other torn write.
    """
    if not store.path.exists():
        return []
    try:
        text = store.path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    lines = [line for line in text.splitlines() if line.strip()]
    traces: list[WorkflowTrace] = []
    for i, line in enumerate(lines):
        try:
            traces.append(WorkflowTrace.model_validate_json(line))
        except (ValueError, KeyError):
            if i != len(lines) - 1:
                return None
            break  # a torn last line: drop it, keep everything before it
    return traces


def _settle_interrupted(
    claude: ClaudeRun,
    run_id: str,
    store: TraceStore,
    batch_id: str | None,
    *,
    ambiguous_submission: bool = False,
) -> None:
    """Account for a run that died mid-flight, without ever under- or over-counting real spend.

    A submitted batch bills server-side whether or not this process is still around to see it, so
    its reservation is never settled here: it stays "reserved" at its projected cost (with the
    batch id attached, submitting it a second time if it isn't already) until a later --batch-id
    re-attach reads the real results and settles the real cost. A sync run has no such hidden
    spend: it is settled at the sum of whatever cases were actually completed and written to disk
    before it died (0 if none were).

    ambiguous_submission (C2) is for a batch create() call that failed with a connection error, a
    timeout, or a 5xx: unlike a clean pre-create failure or a 4xx, the request might have reached
    the server anyway, so there is no batch id to attach, but the reservation still must not
    settle at 0 on a guess. It stays "reserved" until an operator checks by hand.
    """
    if batch_id is not None:
        write_ledger(claude.ledger, attach_batch(_load_ledger(claude), run_id, batch_id))
        typer.echo(
            f"error: Claude run {run_id} was interrupted after submitting Message Batch "
            f"{batch_id}; its reservation stays counted against the budget until it is "
            f"resolved. Re-attach with --mode batch --batch-id {batch_id} to collect results "
            "and settle its actual cost.",
            err=True,
        )
        return
    if ambiguous_submission:
        typer.echo(
            f"error: Claude run {run_id}'s Message Batch submission failed with a connection "
            "error, timeout, or server error; it may or may not have reached Anthropic's "
            "servers. Its reservation stays counted against the budget until this is resolved "
            "by hand: check `batches list` in the Anthropic console for a batch submitted "
            "around this run's start time, then re-attach with --mode batch --batch-id <id> if "
            "you find one.",
            err=True,
        )
        return
    traces = _partial_traces(store)
    if traces is None:
        typer.echo(
            f"error: Claude run {run_id}'s trace file could not be parsed; its reservation "
            "stays counted against the budget until this is resolved by hand.",
            err=True,
        )
        return
    _settle(claude, run_id, traces, None, collected=False)


def _settle(
    claude: ClaudeRun,
    run_id: str,
    traces: list[WorkflowTrace],
    batch_id: str | None,
    *,
    collected: bool,
) -> None:
    """Settle this run at its actual estimated cost.

    `collected` must be True only when this run actually read a batch's results (the normal
    success path in _execute): only then is it safe to zero out an earlier reservation for the
    same batch id, because that batch's cost has genuinely moved to this run's entry. A settle
    reached from a failure/interrupted path must never zero another entry's real, still-uncollected
    reservation on a guess -- that was the C1-new bug, where an interrupted re-attach (no traces,
    but claude.batch_id still set) zeroed the original batch's reservation before its results were
    ever collected.
    """
    actual = sum((t.decisions.estimated_cost_usd or Decimal("0") for t in traces), Decimal("0"))
    ledger = _load_ledger(claude)
    if collected and claude.batch_id is not None:
        earlier = find_batch(ledger, claude.batch_id)
        if earlier is not None and earlier.run_id != run_id and earlier.status == "reserved":
            ledger = settle(ledger, earlier.run_id, Decimal("0"), batch_id=claude.batch_id)
    ledger = settle(ledger, run_id, actual, batch_id=batch_id)
    write_ledger(claude.ledger, ledger)
    typer.echo(
        f"Claude spend: this run ${actual:.4f}; total ${ledger.spent_usd:.4f} of the "
        f"${claude.budget_usd:.2f} budget ({claude.ledger})"
    )


def _is_ambiguous_submission_error(error: BaseException) -> bool:
    """Whether a batch create() failure (C2/I2) might have reached Anthropic's servers anyway.

    A dropped connection or a timeout means the client never saw a response, and a 5xx means the
    server may have processed the request before failing to reply cleanly; either way the batch
    may already exist and be billing. Ctrl-C or task cancellation while the create() call is in
    flight is the same story: uploading a large batch can take seconds, and an interrupt part way
    through leaves exactly the same doubt about whether the request landed (I2). A 4xx (a bad
    request, rejected outright) or anything else is definite: nothing was submitted.
    """
    if isinstance(error, anthropic.APIConnectionError):
        return True
    if isinstance(error, anthropic.APIStatusError):
        return error.status_code >= 500
    if isinstance(error, (KeyboardInterrupt, asyncio.CancelledError)):
        return True
    return False


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
    questions: str | None,
    stack: AsyncExitStack,
    claude: ClaudeRun | None = None,
    on_submitted: Callable[[str], None] | None = None,
) -> DecisionProvider:
    """One explicit factory per provider. An unhandled name is a bug, never a silent Jev run."""
    if provider_name is ProviderName.jev:
        if questions is None:
            raise ValueError("the jev provider needs a question set")
        client = await stack.enter_async_context(AsyncTypeSafeClient(timeout=30.0))
        return JevProvider(client, question_set_version=questions)
    if provider_name is ProviderName.groundtruth:
        return GroundTruthProvider({c.input.id: c.ground_truth for c in cases})
    if provider_name is ProviderName.rules:
        return RulesBaselineProvider()
    if provider_name is ProviderName.claude:
        if questions is None or claude is None:
            raise ValueError("the claude provider needs a question set and Claude run settings")
        client = await stack.enter_async_context(AsyncAnthropic(timeout=CLAUDE_TIMEOUT_S))
        if claude.mode == "batch":
            return ClaudeBatchProvider(
                client.messages.batches,
                question_set=questions,
                batch_id=claude.batch_id,
                on_submitted=on_submitted,
                # max_retries=0 for submission only (C2): a create() that fails with a dropped
                # connection, a timeout, or a 5xx might have reached the server anyway, and an
                # automatic SDK retry could then submit (and bill) a second batch. Polling and
                # reading results stay on the normal-retry client (client.messages.batches),
                # since those are idempotent reads.
                create_batches=client.with_options(max_retries=0).messages.batches,
            )
        return ClaudeProvider(client.messages, question_set=questions)
    raise ValueError(f"no factory for provider {provider_name!r}")


async def _execute(
    cases: list[PriorAuthCase],
    provider_name: ProviderName,
    policy: str,
    concurrency: int,
    traces_dir: Path,
    dataset: Path,
    questions: str | None,
    sample: tuple[int, int] | None = None,
    claude: ClaudeRun | None = None,
    projected: Decimal = Decimal("0"),
) -> tuple[RunManifest, list[WorkflowTrace]]:
    run_id = new_run_id()
    store = TraceStore.create(traces_dir, run_id)
    git_sha = current_git_sha()
    on_submitted = None
    if claude is not None:
        _reserve(claude, run_id, cases, projected)

        def on_submitted(batch_id: str) -> None:
            _record_batch(claude, run_id, batch_id)

    provider: DecisionProvider | None = None
    traces: list[WorkflowTrace] = []
    try:
        async with AsyncExitStack() as stack:
            provider = await _build_provider(
                provider_name, cases, questions, stack, claude, on_submitted
            )
            traces = await run_dataset(
                cases,
                provider,
                policy_version=policy,
                store=store,
                run_id=run_id,
                concurrency=concurrency,
                git_sha=git_sha,
            )
    except BaseException as error:
        # Account even for a failed run (API error, batch submission failure, Ctrl-C, ...) so its
        # reservation never leaks: see _settle_interrupted for how a submitted batch differs from
        # a sync run that died partway through.
        if claude is not None:
            # `or claude.batch_id` (C1-new): if the failure happened before `provider` was even
            # assigned (e.g. the crash is inside _build_provider itself, before
            # ClaudeBatchProvider's constructor runs), getattr(provider, ...) is None even for a
            # --batch-id re-attach. Falling back to the CLI's own --batch-id makes sure a dying
            # re-attach is still recognized as "a known batch, stays reserved" rather than "nothing
            # was submitted, settle at 0" -- which would zero out a real, still-uncollected batch.
            batch_id = getattr(provider, "batch_id", None) or claude.batch_id
            ambiguous = (
                claude.mode == "batch"
                and batch_id is None
                and _is_ambiguous_submission_error(error)
            )
            _settle_interrupted(claude, run_id, store, batch_id, ambiguous_submission=ambiguous)
        if store.path.exists() and store.path.stat().st_size == 0:
            store.path.unlink()
        raise
    if claude is not None:
        batch_id = getattr(provider, "batch_id", None) or claude.batch_id
        _settle(claude, run_id, traces, batch_id, collected=True)
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
        sample_limit=None if sample is None else sample[0],
        sample_seed=None if sample is None else sample[1],
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
    questions: str | None,
    sample: tuple[int, int] | None = None,
    claude: ClaudeRun | None = None,
) -> list[WorkflowTrace]:
    resolved = _resolve_questions(provider, questions)
    _preflight(cases, provider, policy)
    projected = _claude_budget_check(claude, cases) if claude is not None else Decimal("0")
    if provider in PROVIDER_NOTES:
        typer.echo(f"NOTE: {PROVIDER_NOTES[provider]}")
    manifest, traces = asyncio.run(
        _execute(
            cases,
            provider,
            policy,
            concurrency,
            traces_dir,
            dataset,
            resolved,
            sample,
            claude,
            projected,
        )
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
    limit: Limit = None,
    sample_seed: SampleSeed = None,
    mode: ModeOption = None,
    budget_usd: BudgetUsd = None,
    ledger: LedgerOption = None,
    batch_id: BatchId = None,
) -> None:
    """Decide every case in DATASET; write traces and a Markdown report."""
    claude = _resolve_claude(provider, mode, budget_usd, ledger, batch_id)
    cases, sample = _apply_limit(_load_cases(dataset), limit, sample_seed)
    _run_and_report(
        cases,
        provider,
        policy,
        concurrency,
        traces_dir,
        reports_dir,
        dataset,
        questions,
        sample,
        claude,
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
    limit: Limit = None,
    sample_seed: SampleSeed = None,
    mode: ModeOption = None,
    budget_usd: BudgetUsd = None,
    ledger: LedgerOption = None,
    batch_id: BatchId = None,
) -> None:
    """Run (or re-score) DATASET and print action-level and decision-level metrics."""
    cases, sample = _apply_limit(_load_cases(dataset), limit, sample_seed)
    if traces is None:
        claude = _resolve_claude(provider, mode, budget_usd, ledger, batch_id)
        trace_list = _run_and_report(
            cases,
            provider,
            policy,
            concurrency,
            traces_dir,
            reports_dir,
            dataset,
            questions,
            sample,
            claude,
        )
    else:
        trace_list = _read_trace_file(traces)
    try:
        summary = score_run(trace_list, cases)
    except (EvalError, ValueError, KeyError) as error:
        raise _fail(str(error)) from error
    results_dir.mkdir(parents=True, exist_ok=True)
    results_path = results_dir / f"{summary.run_id}.json"
    results_path.write_text(summary.model_dump_json() + "\n", encoding="utf-8")
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
    json_path.write_text(result.model_dump_json() + "\n", encoding="utf-8")
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


ReplayQuestions = Annotated[
    str | None,
    typer.Option(
        "--questions",
        "--question-set",
        help="Live candidate only: the provider's question set (as for run/eval).",
    ),
]


def _one_trace(path: Path, case_id: str, flag: str) -> WorkflowTrace:
    """The single trace for case_id in a trace file; zero or several is a usage error."""
    matches = [t for t in _read_trace_file(path) if t.case_id == case_id]
    if len(matches) != 1:
        raise _fail(
            f"{flag} {path}: expected exactly one trace for {case_id}, found {len(matches)}"
        )
    return matches[0]


def _frozen_case(dataset: Path, trace: WorkflowTrace) -> PriorAuthCase:
    """The trace's case from the dataset, refused unless its inputs hash to the stored hash."""
    case_dir = dataset / trace.case_id
    if not case_dir.is_dir():
        raise _fail(f"{trace.case_id} is not a case folder in {dataset}")
    try:
        case = load_case(case_dir)
    except CaseLoadError as error:
        raise _fail(str(error)) from error
    actual = case.input.content_hash()
    if actual != trace.case_content_hash:
        raise _fail(
            f"{trace.case_id}: the case inputs changed since run {trace.run_id} (trace "
            f"{trace.case_content_hash}, dataset {actual}); replaying altered inputs is not replay"
        )
    return case


def _policy(policy_id: str) -> AuthorizationPolicy:
    try:
        return load_policy(policy_id)
    except KeyError as error:
        raise _fail(str(error.args[0])) from error


def _live_candidate(
    case: PriorAuthCase,
    original: WorkflowTrace,
    dataset: Path,
    provider: ProviderName,
    questions: str | None,
    mode: ClaudeMode | None,
    budget_usd: float | None,
    ledger: Path | None,
    traces_dir: Path,
    quiet: bool,
) -> WorkflowTrace:
    """A fresh provider call on the frozen input, written as an ordinary one-case run.

    With --json, the run's own messages (budget, notes, spend, run id) go to stderr so stdout
    stays pure JSON.

    Uses `load_thresholds(original.policy_version)` (an ordinary run, via `_execute`/`run_dataset`),
    not `original.thresholds` (Minor 4). This only differs when `original` is itself an overridden
    or replayed trace, in which case the diff will show a thresholds change the user didn't ask for.
    """
    if mode is ClaudeMode.batch:
        raise _fail("replay decides one case; --mode batch is not supported (use --mode sync)")
    claude = _resolve_claude(provider, mode, budget_usd, ledger)
    resolved = _resolve_questions(provider, questions)
    cases = [case]
    _preflight(cases, provider, original.policy_version)
    chatter = contextlib.redirect_stdout(sys.stderr) if quiet else contextlib.nullcontext()
    with chatter:
        projected = _claude_budget_check(claude, cases) if claude is not None else Decimal("0")
        if provider in PROVIDER_NOTES:
            typer.echo(f"NOTE: {PROVIDER_NOTES[provider]}")
        manifest, traces = asyncio.run(
            _execute(
                cases,
                provider,
                original.policy_version,
                1,
                traces_dir,
                dataset,
                resolved,
                None,
                claude,
                projected,
            )
        )
        typer.echo(f"Live candidate run {manifest.run_id}: {manifest.trace_file}")
    return traces[0]


@app.command()
def replay(
    case_id: Annotated[str, typer.Argument(help="The case to replay, e.g. GOLD-TMP-17.")],
    traces: TraceFile,
    dataset: Dataset,
    policy_id: Annotated[
        str | None,
        typer.Option("--policy", help="Policy replay: the stored decisions under this policy id."),
    ] = None,
    latest_policy: Annotated[
        bool,
        typer.Option(
            "--latest-policy",
            help="Policy replay: under the newest registered policy for the same medication.",
        ),
    ] = False,
    at: Annotated[
        float | None,
        typer.Option(min=0.0, max=1.0, help="Policy replay: override the auto_process threshold."),
    ] = None,
    candidate_traces: Annotated[
        Path | None,
        typer.Option(
            exists=True, dir_okay=False, help="Candidate: this case's trace from another run."
        ),
    ] = None,
    provider: Annotated[
        ProviderName | None,
        typer.Option(help="Live candidate: a fresh call to this provider on the frozen inputs."),
    ] = None,
    questions: ReplayQuestions = None,
    mode: ModeOption = None,
    budget_usd: BudgetUsd = None,
    ledger: LedgerOption = None,
    traces_dir: Annotated[
        Path, typer.Option(help="Live candidate only: where its trace file is written.")
    ] = Path("traces"),
    all_gates: Annotated[
        bool, typer.Option("--all-gates", help="Show every gate row, not only changed ones.")
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Print the TraceDiff as JSON and nothing else.")
    ] = False,
) -> None:
    """Replay one stored trace beside a candidate and call out every difference.

    Exit codes: 0 ok; 2 usage/input error; 3 ENGINE DRIFT (reproduce only); 4 NEWLY UNSAFE.
    """
    policy_replay = policy_id is not None or latest_policy or at is not None
    sources = [
        name
        for name, used in (
            ("policy replay (--policy/--latest-policy/--at)", policy_replay),
            ("--candidate-traces", candidate_traces is not None),
            ("--provider", provider is not None),
        )
        if used
    ]
    if len(sources) > 1:
        raise _fail("choose one candidate source, not " + " and ".join(sources))
    if policy_id is not None and latest_policy:
        raise _fail("--policy and --latest-policy are mutually exclusive")
    if at is not None and at <= 0.0:
        raise _fail("--at must be > 0 (auto_process must be > 0)")
    if provider is None:
        live_only = {
            "--questions": questions,
            "--mode": mode,
            "--budget-usd": budget_usd,
            "--ledger": ledger,
        }
        given = [flag for flag, value in live_only.items() if value is not None]
        if given:
            raise _fail(f"{', '.join(given)} applies only to a live candidate (--provider)")

    original = _one_trace(traces, case_id, "--traces")
    case = _frozen_case(dataset, original)
    original_policy = _policy(original.policy_id)
    reproduce = False
    if candidate_traces is not None:
        candidate = _one_trace(candidate_traces, case_id, "--candidate-traces")
        if candidate.case_content_hash != original.case_content_hash:
            raise _fail(
                f"--candidate-traces {candidate_traces}: its {case_id} trace was made on "
                f"different case inputs ({candidate.case_content_hash}, original "
                f"{original.case_content_hash})"
            )
        label = candidate_trace_label(candidate)
    elif provider is not None:
        candidate = _live_candidate(
            case,
            original,
            dataset,
            provider,
            questions,
            mode,
            budget_usd,
            ledger,
            traces_dir,
            json_output,
        )
        label = live_label(candidate)
    elif policy_replay:
        if latest_policy:
            try:
                target_id = latest_policy_for(original.policy_id)
            except KeyError as error:
                raise _fail(str(error.args[0])) from error
        else:
            target_id = policy_id or original.policy_id
        target = _policy(target_id)
        try:
            thresholds = replay_thresholds(original, target, at)
        except EvalError as error:
            raise _fail(str(error)) from error
        candidate = replay_trace(original, case, policy=target, thresholds=thresholds)
        label = policy_replay_label(target, thresholds, at)
        if latest_policy and target_id == original.policy_id:
            label += " (already the trace's policy)"
    else:
        reproduce = True
        candidate = replay_trace(
            original, case, policy=original_policy, thresholds=original.thresholds
        )
        label = REPRODUCE_LABEL
    policies = {original_policy.id: original_policy}
    if candidate.policy_id not in policies:
        policies[candidate.policy_id] = _policy(candidate.policy_id)
    diff = diff_case(
        original,
        candidate,
        case,
        original_label=original_label(original),
        candidate_label=label,
        policies=policies,
    )
    if json_output:
        typer.echo(diff.model_dump_json(indent=2))
    else:
        typer.echo(render_trace_diff(diff, all_gates, reproduce=reproduce))
    code = replay_exit_code(diff, reproduce=reproduce)
    if code:
        raise typer.Exit(code=code)


GatesFile = Annotated[
    Path | None,
    typer.Option(
        "--config",
        exists=True,
        dir_okay=False,
        help="Run every gate in this gates file (e.g. evals/regression/gates.json).",
    ),
]


def _gate_row(name: str, result: RegressionResult) -> GateRow:
    return GateRow(
        name=name,
        verdict=result.verdict,
        newly_unsafe=len(result.newly_unsafe),
        regressed=len(result.regressed),
        exit_code=result.exit_code,
    )


def _run_gate(
    request: RegressionRequest, out: Path | None, show_all: bool
) -> tuple[RegressionResult, str]:
    """Run one gate, write its --out files, return the result and its rendered report."""
    run = run_regression(request, out=out)
    rendered = render_regression(run.result, show_all=show_all)
    if out is not None:
        write_outputs(out, run, request, rendered)
    return run.result, rendered


def _regression_config(config: Path, names: list[str], out: Path | None, show_all: bool) -> int:
    """Config mode: every gate (or the --gate ones), each report, then a summary. Returns the
    highest exit code. A gate with requires_generated whose dataset is missing is SKIPPED; any
    other input error is that gate's ERROR (exit 2) and the remaining gates still run."""
    try:
        gates = load_gates(config).gates
    except RegressionInputError as error:
        raise _fail(str(error)) from error
    unknown = sorted(set(names) - {g.name for g in gates})
    if unknown:
        raise _fail(f"no gate named {', '.join(unknown)} in {config}")
    selected = [g for g in gates if not names or g.name in names]
    rows: list[GateRow] = []
    for spec in selected:
        if spec.requires_generated and not Path(spec.dataset).is_dir():
            note = f"dataset not generated; run relay generate to create {spec.dataset}"
            typer.echo(f"Relay regression — gate {spec.name}: SKIPPED ({note})\n")
            rows.append(GateRow(spec.name, "SKIPPED", None, None, 0, note=note))
            continue
        gate_out = None if out is None else out / spec.name
        try:
            result, rendered = _run_gate(RegressionRequest.from_gate(spec), gate_out, show_all)
        except RegressionInputError as error:
            typer.echo(f"Relay regression — gate {spec.name}: ERROR: {error}\n", err=True)
            rows.append(GateRow(spec.name, "ERROR", None, None, 2, note=str(error)[:80]))
            continue
        typer.echo(rendered + "\n")
        rows.append(_gate_row(spec.name, result))
    summary = render_gate_summary(rows)
    typer.echo(summary)
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        (out / "summary.md").write_text(summary + "\n", encoding="utf-8")
    return max((r.exit_code for r in rows), default=0)


@app.command()
def regression(
    dataset: Annotated[
        Path | None, typer.Option(file_okay=False, help="Directory of case folders.")
    ] = None,
    baseline: Annotated[
        Path | None, typer.Option(dir_okay=False, help="The accepted baseline's trace file.")
    ] = None,
    candidate_traces: Annotated[
        Path | None, typer.Option(dir_okay=False, help="Candidate: another run's trace file.")
    ] = None,
    candidate_policy: Annotated[
        str | None,
        typer.Option(help="Candidate: the baseline's stored decisions under this policy id."),
    ] = None,
    candidate_latest_policy: Annotated[
        bool,
        typer.Option(
            "--candidate-latest-policy",
            help="Candidate: the stored decisions under the newest policy for the medication.",
        ),
    ] = False,
    candidate_at: Annotated[
        float | None,
        typer.Option(
            help="Candidate auto_process threshold, in (0, 1]. Alone: a policy replay of the "
            "baseline under its own policy at this threshold."
        ),
    ] = None,
    reproduce: Annotated[
        bool,
        typer.Option(
            "--reproduce",
            help="Engine-drift gate: the stored decisions under today's engine; any "
            "difference fails with exit 3.",
        ),
    ] = False,
    baseline_at: Annotated[
        float | None,
        typer.Option(help="Re-decide the baseline at this auto_process threshold, in (0, 1]."),
    ] = None,
    waivers: Annotated[
        Path | None,
        typer.Option(exists=True, dir_okay=False, help="Waiver file for newly unsafe cases."),
    ] = None,
    max_regressed: Annotated[
        int | None, typer.Option(min=0, help="Fail when more cases than this regress.")
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option(help="Write regression.json, regression.md and any replayed runs here."),
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Print the RegressionResult as JSON and nothing else.")
    ] = False,
    show_all: Annotated[
        bool, typer.Option("--all", help="List every regressed case, not only the first 20.")
    ] = False,
    config: GatesFile = None,
    gate: Annotated[
        list[str] | None,
        typer.Option("--gate", help="Config mode: run only this gate (repeatable)."),
    ] = None,
) -> None:
    """Gate a candidate against an accepted baseline on the same frozen dataset (offline).

    Exit codes: 0 PASS; 2 usage/input error; 3 ENGINE DRIFT (--reproduce); 4 FAIL (a newly
    unsafe case without a waiver, or more regressions than --max-regressed).
    """
    if config is not None:
        single = {
            "--dataset": dataset,
            "--baseline": baseline,
            "--candidate-traces": candidate_traces,
            "--candidate-policy": candidate_policy,
            "--candidate-latest-policy": candidate_latest_policy or None,
            "--candidate-at": candidate_at,
            "--reproduce": reproduce or None,
            "--baseline-at": baseline_at,
            "--waivers": waivers,
            "--max-regressed": max_regressed,
            "--json": json_output or None,
        }
        given = [flag for flag, value in single.items() if value is not None]
        if given:
            raise _fail(f"{', '.join(given)} cannot be combined with --config")
        code = _regression_config(config, gate or [], out, show_all)
        if code:
            raise typer.Exit(code=code)
        return
    if gate:
        raise _fail("--gate needs --config")
    if dataset is None or baseline is None:
        raise _fail("give --dataset and --baseline, or --config")
    request = RegressionRequest(
        dataset=dataset,
        baseline=baseline,
        candidate=CandidateSpec(
            traces=None if candidate_traces is None else str(candidate_traces),
            policy=candidate_policy,
            latest_policy=candidate_latest_policy,
            at=candidate_at,
            reproduce=reproduce,
        ),
        baseline_at=baseline_at,
        waivers=waivers,
        max_regressed=max_regressed,
    )
    try:
        result, rendered = _run_gate(request, out, show_all)
    except RegressionInputError as error:
        raise _fail(str(error)) from error
    typer.echo(result.model_dump_json(indent=2) if json_output else rendered)
    if result.exit_code:
        raise typer.Exit(code=result.exit_code)
