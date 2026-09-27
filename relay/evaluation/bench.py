"""relay bench: does adding narrow decisions cost latency? (handoff experiment 4)

For each sampled case and each size k, one TypeSafe System One request carries the first k
questions of a fixed ordering of q-v0.3's 19 (QUESTION_IDS_V0_3); size 20 adds one padding
question, a duplicate of diagnosis_support under another id (disclosed in every output). The
installed typesafe-sdk sends all of a call's questions in one HTTP request and returns no
per-question timing, so the bench measures per-call wall latency around that one request. Calls
run one at a time (never concurrently), case by case, so no call's latency includes another's.
Decisions are not scored: a partial question set cannot form a bundle.

I1: within a case, the sizes are rotated (a Latin-square offset derived deterministically from the
sample seed and the case's index) rather than always run in the same order, so no one size is
always the first call of a case (which would always pay connection warm-up) or always the last
(which would always benefit from any server-side prefix or state cache). Each call's `position`
(its 0-based index within its case) is recorded, so the confound can be checked directly. This
does not change the call count (still cases × len(sizes)) or the pre-run estimate.
"""

import math
import time
from collections.abc import Callable, Sequence
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from typesafe_sdk import TypeSafeError

from relay.cases.models import CaseInput
from relay.cases.policies import AuthorizationPolicy, load_policy
from relay.decisions.jev import (
    CLIENT_VERSION,
    JEV_MODEL,
    PRICE_PER_INPUT_TOKEN_USD,
    SystemOneClient,
    build_state,
)
from relay.decisions.questions import Q_V0_3, QUESTION_IDS_V0_3, build_questions, candidate_years

PADDING_SOURCE = "diagnosis_support"
PADDING_QUESTION = "diagnosis_support_padding"
MAX_SIZE = len(QUESTION_IDS_V0_3) + 1  # 20: the 19 q-v0.3 questions plus the padding question
DEFAULT_SIZES: tuple[int, ...] = (1, 5, 10, 20)
BATCHING_NOTE = (
    "Each call is one system_one request carrying all k questions for one case "
    f"({CLIENT_VERSION}); the client does not split a request."
)
PER_QUESTION_NOTE = (
    f"Not measured: {CLIENT_VERSION} returns no per-question timing (one HTTP request per call)."
)
PADDING_NOTE = (
    f"Size {MAX_SIZE} is q-v0.3's {len(QUESTION_IDS_V0_3)} questions plus {PADDING_QUESTION!r}, "
    f"a duplicate of {PADDING_SOURCE!r} under another id (controlled padding)."
)


def bench_question_ids(size: int) -> tuple[str, ...]:
    """The first `size` ids of the fixed ordering; 20 appends the padding question."""
    if not 1 <= size <= MAX_SIZE:
        raise ValueError(f"size must be between 1 and {MAX_SIZE}, got {size}")
    if size == MAX_SIZE:
        return (*QUESTION_IDS_V0_3, PADDING_QUESTION)
    return QUESTION_IDS_V0_3[:size]


def bench_questions(policy: AuthorizationPolicy, years: Sequence[str], size: int) -> dict[str, Any]:
    full = build_questions(policy, years, Q_V0_3)
    full[PADDING_QUESTION] = full[PADDING_SOURCE]
    return {qid: full[qid] for qid in bench_question_ids(size)}


def rotate_sizes(sizes: Sequence[int], seed: int, case_index: int) -> tuple[int, ...]:
    """`sizes` rotated by (seed + case_index) mod len(sizes) (I1): a Latin-square offset, so
    across enough cases each size lands in each call position equally often instead of always
    at the same position."""
    ordered = tuple(sizes)
    n = len(ordered)
    if n == 0:
        return ordered
    offset = (seed + case_index) % n
    return ordered[offset:] + ordered[:offset]


def bench_rotation_seed(sample: tuple[int, int] | None) -> int:
    """The seed used to rotate each case's size order: --sample-seed if one was given, else 0."""
    return 0 if sample is None else sample[1]


def parse_sizes(text: str) -> tuple[int, ...]:
    """'1,5,10,20' -> (1, 5, 10, 20). ValueError for anything else (empty, duplicate, range)."""
    try:
        sizes = tuple(int(part) for part in text.split(","))
    except ValueError:
        raise ValueError(f"--sizes must be comma-separated integers, got {text!r}") from None
    if len(set(sizes)) != len(sizes):
        raise ValueError(f"--sizes has a duplicate: {text!r}")
    for size in sizes:
        bench_question_ids(size)
    return sizes


class BenchCall(BaseModel):
    case_id: str
    size: int
    position: int  # 0-based: this call's index within its case's (rotated) size order (I1)
    latency_ms: float
    input_tokens: int | None = None
    cost_usd: Decimal | None = None
    error: str | None = None


class BenchSize(BaseModel):
    size: int
    calls: int
    errors: int
    latency_ms_p50: float | None
    latency_ms_p95: float | None
    latency_ms_mean: float | None
    input_tokens_mean: float | None
    cost_per_case_usd: Decimal
    total_cost_usd: Decimal


class BenchResult(BaseModel):
    dataset_id: str
    case_count: int
    sample_limit: int | None
    sample_seed: int | None
    model: str
    client_version: str
    question_set_version: str
    ordering: list[str]
    padding_question: str
    batching: str
    per_question_latency: str
    size_order: str
    sizes: list[BenchSize]
    total_cost_usd: Decimal
    calls: list[BenchCall]


def nearest_rank(values: Sequence[float], q: float) -> float:
    """The nearest-rank percentile: the ceil(q * n)-th smallest value (1-based)."""
    ordered = sorted(values)
    return ordered[max(math.ceil(q * len(ordered)), 1) - 1]


def summarize_size(size: int, calls: Sequence[BenchCall], case_count: int) -> BenchSize:
    """Latency over successful calls; cost over every call that reported tokens."""
    ok = [c for c in calls if c.error is None]
    latencies = [c.latency_ms for c in ok]
    tokens = [c.input_tokens for c in ok if c.input_tokens is not None]
    total = sum((c.cost_usd or Decimal("0") for c in calls), Decimal("0"))
    return BenchSize(
        size=size,
        calls=len(calls),
        errors=len(calls) - len(ok),
        latency_ms_p50=nearest_rank(latencies, 0.50) if latencies else None,
        latency_ms_p95=nearest_rank(latencies, 0.95) if latencies else None,
        latency_ms_mean=sum(latencies) / len(latencies) if latencies else None,
        input_tokens_mean=sum(tokens) / len(tokens) if tokens else None,
        cost_per_case_usd=total / case_count if case_count else Decimal("0"),
        total_cost_usd=total,
    )


async def run_bench(
    cases: Sequence[CaseInput],
    client: SystemOneClient,
    *,
    sizes: Sequence[int],
    sample_seed: int = 0,
    model: str = JEV_MODEL,
    clock: Callable[[], float] = time.perf_counter,
    policy_loader: Callable[[str], AuthorizationPolicy] = load_policy,
    on_call: Callable[[BenchCall], None] | None = None,
) -> list[BenchCall]:
    """One call per (case, size), sequentially. A TypeSafeError or a response missing an asked
    question is recorded as that call's error, and the bench continues.

    Sizes are rotated per case (I1, `rotate_sizes`), offset by `sample_seed` and the case's index,
    so size is not confounded with call position; each call's `position` is recorded.
    """
    calls: list[BenchCall] = []
    for case_index, case in enumerate(cases):
        policy = policy_loader(case.policy_id)
        state = build_state(case, policy)
        years = candidate_years(case)
        order = rotate_sizes(sizes, sample_seed, case_index)
        for position, size in enumerate(order):
            questions = bench_questions(policy, years, size)
            started = clock()
            try:
                response = await client.system_one(state=state, questions=questions, model=model)
            except TypeSafeError as error:
                call = BenchCall(
                    case_id=case.id,
                    size=size,
                    position=position,
                    latency_ms=(clock() - started) * 1000,
                    error=f"{type(error).__name__}: {error}",
                )
            else:
                latency_ms = (clock() - started) * 1000
                tokens = response.usage.input_tokens
                missing = sorted(set(questions) - set(response.answers))
                call = BenchCall(
                    case_id=case.id,
                    size=size,
                    position=position,
                    latency_ms=latency_ms,
                    input_tokens=tokens,
                    cost_usd=None if tokens is None else PRICE_PER_INPUT_TOKEN_USD * tokens,
                    error=f"missing answers: {', '.join(missing)}" if missing else None,
                )
            calls.append(call)
            if on_call is not None:
                on_call(call)
    return calls


def _size_order_note(seed: int) -> str:
    return (
        f"size order rotated per case (offset = (sample seed {seed} + case index) mod "
        "len(sizes), a Latin square), so each size appears equally often in each call position"
    )


def build_bench_result(
    calls: Sequence[BenchCall],
    *,
    dataset_id: str,
    case_count: int,
    sizes: Sequence[int],
    sample: tuple[int, int] | None,
    model: str,
) -> BenchResult:
    per_size = [summarize_size(s, [c for c in calls if c.size == s], case_count) for s in sizes]
    return BenchResult(
        dataset_id=dataset_id,
        case_count=case_count,
        sample_limit=None if sample is None else sample[0],
        sample_seed=None if sample is None else sample[1],
        model=model,
        client_version=CLIENT_VERSION,
        question_set_version=Q_V0_3,
        ordering=list(bench_question_ids(MAX_SIZE)),
        padding_question=PADDING_QUESTION,
        batching=BATCHING_NOTE,
        per_question_latency=PER_QUESTION_NOTE,
        size_order=_size_order_note(bench_rotation_seed(sample)),
        sizes=per_size,
        total_cost_usd=sum((s.total_cost_usd for s in per_size), Decimal("0")),
        calls=list(calls),
    )


def _ms(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0f}"


def render_bench(result: BenchResult) -> str:
    """The Markdown table and notes written to parallelism.md (also printed)."""
    sample = (
        f"--limit {result.sample_limit} --sample-seed {result.sample_seed}"
        if result.sample_limit is not None
        else "every case"
    )
    lines = [
        "# Relay bench: narrow decisions per call vs latency",
        "",
        f"Dataset {result.dataset_id}, {result.case_count} cases ({sample}); model "
        f"{result.model}; {result.question_set_version} ordering.",
        "",
        "| Questions per call | Calls | Errors | p50 latency (ms) | p95 latency (ms) | "
        "Mean latency (ms) | Mean input tokens | Est. cost / case |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in result.sizes:
        tokens = "n/a" if s.input_tokens_mean is None else f"{s.input_tokens_mean:.0f}"
        lines.append(
            f"| {s.size} | {s.calls} | {s.errors} | {_ms(s.latency_ms_p50)} | "
            f"{_ms(s.latency_ms_p95)} | {_ms(s.latency_ms_mean)} | {tokens} | "
            f"${s.cost_per_case_usd:.6f} |"
        )
    lines += [
        "",
        f"Total estimated cost: ${result.total_cost_usd:.4f}",
        "",
        f"- Batching: {result.batching}",
        f"- Per-question latency: {result.per_question_latency}",
        f"- Padding: {PADDING_NOTE}",
        f"- Size order: {result.size_order}.",
        "- Calls ran one at a time; latency is wall time around one request, retries included.",
        "- Latency-only: these runs' decisions are not scored.",
        "- Question ordering: " + ", ".join(result.ordering),
    ]
    return "\n".join(lines) + "\n"
