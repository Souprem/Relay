"""relay bench internals: question prefixes, padding, sequential timing with a fake clock."""

from decimal import Decimal

import pytest
from typesafe_sdk import TypeSafeError

from relay.cases.policies import load_policy
from relay.decisions.questions import QUESTION_IDS_V0_3
from relay.evaluation.bench import (
    MAX_SIZE,
    PADDING_QUESTION,
    BenchCall,
    bench_question_ids,
    bench_questions,
    bench_rotation_seed,
    build_bench_result,
    nearest_rank,
    parse_sizes,
    render_bench,
    rotate_sizes,
    run_bench,
    summarize_size,
)
from tests.factories import make_case_input
from tests.jev_fakes import GenericSystemOneClient

POLICY = load_policy("immunara-v0.1")


class FakeClock:
    """perf_counter stand-in: the fake client advances it by 0.1 s + 0.01 s per question."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance_for(self, questions):
        self.now += 0.1 + 0.01 * len(questions)


def test_sizes_are_prefixes_of_the_q_v0_3_ordering_and_20_adds_the_padding():
    assert bench_question_ids(1) == ("diagnosis_support",)
    assert bench_question_ids(5) == QUESTION_IDS_V0_3[:5]
    assert bench_question_ids(10) == QUESTION_IDS_V0_3[:10]
    assert bench_question_ids(19) == QUESTION_IDS_V0_3
    assert bench_question_ids(20) == (*QUESTION_IDS_V0_3, PADDING_QUESTION)
    assert MAX_SIZE == 20
    for bad in (0, 21):
        with pytest.raises(ValueError, match="between 1 and 20"):
            bench_question_ids(bad)


def test_the_padding_question_duplicates_diagnosis_support():
    questions = bench_questions(POLICY, ["2026"], 20)
    assert len(questions) == 20
    assert questions[PADDING_QUESTION] == questions["diagnosis_support"]


def test_parse_sizes():
    assert parse_sizes("1,5,10,20") == (1, 5, 10, 20)
    for bad, message in (("1,x", "integers"), ("5,5", "duplicate"), ("1,25", "between")):
        with pytest.raises(ValueError, match=message):
            parse_sizes(bad)


def test_nearest_rank_percentiles():
    values = [float(v) for v in range(1, 41)]  # 1..40
    assert nearest_rank(values, 0.50) == 20.0
    assert nearest_rank(values, 0.95) == 38.0
    assert nearest_rank([7.0], 0.95) == 7.0


async def test_run_bench_times_each_call_sequentially_with_one_request_per_size():
    clock = FakeClock()
    client = GenericSystemOneClient(on_call=clock.advance_for)
    cases = [make_case_input("T-01"), make_case_input("T-02")]
    calls = await run_bench(cases, client, sizes=(1, 5, 20), clock=clock)
    # Default sample_seed=0: T-01 (case index 0) keeps the given order; T-02 (index 1) is rotated
    # by one (I1).
    assert [(c.case_id, c.size, c.position) for c in calls] == [
        ("T-01", 1, 0),
        ("T-01", 5, 1),
        ("T-01", 20, 2),
        ("T-02", 5, 0),
        ("T-02", 20, 1),
        ("T-02", 1, 2),
    ]
    assert [len(call["questions"]) for call in client.calls] == [1, 5, 20, 5, 20, 1]
    assert {call["model"] for call in client.calls} == {"jev-1.13.0"}
    assert [round(c.latency_ms, 6) for c in calls[:3]] == [110.0, 150.0, 300.0]
    assert calls[2].input_tokens == 1000 + 50 * 20
    assert calls[2].cost_usd == Decimal("0.042") / Decimal(1_000_000) * 2000
    assert all(c.error is None for c in calls)


def test_rotate_sizes_offsets_by_seed_plus_case_index():
    sizes = (1, 5, 10, 20)
    assert rotate_sizes(sizes, seed=0, case_index=0) == (1, 5, 10, 20)
    assert rotate_sizes(sizes, seed=0, case_index=1) == (5, 10, 20, 1)
    assert rotate_sizes(sizes, seed=1, case_index=2) == (20, 1, 5, 10)
    assert rotate_sizes((), seed=3, case_index=2) == ()


def test_bench_rotation_seed_is_the_sample_seed_or_zero():
    assert bench_rotation_seed(None) == 0
    assert bench_rotation_seed((40, 11)) == 11


async def test_bench_size_order_rotates_so_each_size_hits_each_position_once_across_4_cases():
    """I1: with as many cases as sizes, a Latin-square rotation puts each size in each call
    position exactly once, so size is not confounded with call position (e.g. always first,
    always paying connection warm-up; or always last, always benefiting from any cache)."""
    client = GenericSystemOneClient()
    cases = [make_case_input(f"T-{i:02d}") for i in range(4)]
    sizes = (1, 5, 10, 20)
    calls = await run_bench(cases, client, sizes=sizes, sample_seed=3)
    by_size: dict[int, list[int]] = {size: [] for size in sizes}
    for call in calls:
        by_size[call.size].append(call.position)
    for size in sizes:
        assert sorted(by_size[size]) == [0, 1, 2, 3], (size, by_size[size])


class FlakyClient(GenericSystemOneClient):
    async def system_one(self, state, questions, *, model=None, **kwargs):
        if len(questions) == 5:
            raise TypeSafeError("rate limited")
        response = await super().system_one(state, questions, model=model)
        if len(questions) == 20:  # drop an answer
            answers = dict(response.answers)
            del answers[PADDING_QUESTION]
            return response.model_copy(update={"answers": answers})
        return response


async def test_errors_are_recorded_per_call_and_the_bench_continues():
    calls = await run_bench([make_case_input()], FlakyClient(), sizes=(1, 5, 20))
    assert [c.error for c in calls] == [
        None,
        "TypeSafeError: rate limited",
        f"missing answers: {PADDING_QUESTION}",
    ]
    assert calls[1].cost_usd is None and calls[2].cost_usd is not None


def test_summaries_exclude_errors_from_latency_and_count_all_cost():
    calls = [
        BenchCall(
            case_id="a",
            size=5,
            position=0,
            latency_ms=100.0,
            input_tokens=1000,
            cost_usd=Decimal("1"),
        ),
        BenchCall(
            case_id="b",
            size=5,
            position=1,
            latency_ms=300.0,
            input_tokens=3000,
            cost_usd=Decimal("2"),
        ),
        BenchCall(case_id="c", size=5, position=2, latency_ms=9000.0, error="TypeSafeError: x"),
    ]
    s = summarize_size(5, calls, case_count=3)
    assert (s.calls, s.errors) == (3, 1)
    assert (s.latency_ms_p50, s.latency_ms_p95, s.latency_ms_mean) == (100.0, 300.0, 200.0)
    assert s.input_tokens_mean == 2000.0
    assert (s.total_cost_usd, s.cost_per_case_usd) == (Decimal("3"), Decimal("1"))


async def test_result_and_markdown_disclose_batching_padding_and_sample():
    clock = FakeClock()
    client = GenericSystemOneClient(on_call=clock.advance_for)
    cases = [make_case_input(f"T-{i:02d}") for i in range(4)]
    calls = await run_bench(cases, client, sizes=(1, 20), clock=clock)
    result = build_bench_result(
        calls, dataset_id="gen-test", case_count=4, sizes=(1, 20), sample=(4, 11), model="jev-x"
    )
    assert [s.size for s in result.sizes] == [1, 20]
    assert result.sizes[0].latency_ms_p50 == pytest.approx(110.0)
    assert result.sizes[1].latency_ms_p95 == pytest.approx(300.0)
    assert result.ordering[-1] == PADDING_QUESTION and len(result.ordering) == 20
    text = render_bench(result)
    assert "| 1 | 4 | 0 | 110 | 110 | 110 | 1050 |" in text
    assert "| 20 | 4 | 0 | 300 | 300 | 300 | 2000 |" in text
    assert "--limit 4 --sample-seed 11" in text
    assert "one system_one request carrying all k questions" in text
    assert "returns no per-question timing" in text
    assert "a duplicate of 'diagnosis_support'" in text
    assert "not scored" in text
    assert "Size order: size order rotated per case" in text
    assert "Latin square" in text
