"""relay run/eval --provider claude with fake Anthropic clients (no network, no real key)."""

import asyncio
import json
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

import relay.cli as cli_module
from relay.cases.loader import load_dataset
from relay.cli import app
from relay.evaluation.budget import (
    SpendLedger,
    attach_batch,
    load_ledger,
    reserve,
    settle,
    write_ledger,
)
from relay.reporting import CLAUDE_NOTE
from relay.traces.store import TraceStore, read_traces
from tests.claude_fakes import (
    FakeBatches,
    FakeMessages,
    connection_error,
    message,
    status_error,
    succeeded,
)
from tests.factories import make_bundle, make_trace

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
SMOKE_IDS = sorted(c.input.id for c in load_dataset(SMOKE))
runner = CliRunner()


class FakeAnthropic:
    """Stands in for anthropic.AsyncAnthropic; every case gets the same well-formed reply."""

    batches: FakeBatches

    def __init__(self, **kwargs):
        self.messages = FakeMessages(message(), batches=FakeAnthropic.batches)

    def with_options(self, **kwargs):
        # The CLI asks for a max_retries=0 client for batch submission (C2); the fake has no
        # retry behavior to vary, so the same instance (and the same shared FakeBatches) serves.
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None


@pytest.fixture
def fake_claude(monkeypatch):
    # Already "ended" at submission, so the provider never sleeps between polls.
    FakeAnthropic.batches = FakeBatches(
        [succeeded(i) for i in reversed(SMOKE_IDS)], statuses=("ended",)
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncAnthropic", FakeAnthropic)
    return FakeAnthropic


def claude_eval(tmp_path, *extra):
    return runner.invoke(
        app,
        [
            "--env-file",
            str(tmp_path / "missing.env"),
            "eval",
            "--dataset",
            str(SMOKE),
            "--provider",
            "claude",
            "--traces-dir",
            str(tmp_path / "traces"),
            "--reports-dir",
            str(tmp_path / "reports"),
            "--results-dir",
            str(tmp_path / "results"),
            "--ledger",
            str(tmp_path / "spend.json"),
            *extra,
        ],
    )


def only_traces(tmp_path):
    [trace_file] = (tmp_path / "traces").glob("*.jsonl")
    return read_traces(trace_file)


def test_claude_without_an_api_key_exits_2_before_writing_traces(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = claude_eval(tmp_path)
    assert result.exit_code == 2
    assert "ANTHROPIC_API_KEY is not set" in result.output
    assert not (tmp_path / "traces").exists()
    assert not (tmp_path / "spend.json").exists()


def test_sync_run_traces_every_case_and_settles_the_ledger(tmp_path, fake_claude):
    result = claude_eval(tmp_path)
    assert result.exit_code == 0, result.output
    assert CLAUDE_NOTE in result.output
    assert "Claude budget: spent $0.0000, projected $2.5000 for 10 cases (sync)" in result.output
    traces = only_traces(tmp_path)
    assert len(traces) == 10
    assert {(t.provider, t.question_set_version) for t in traces} == {
        ("claude", "q-v0.2+claude-prompt-v1")
    }
    assert all(isinstance(t.decisions.latency_ms, int) for t in traces)
    [entry] = load_ledger(tmp_path / "spend.json").entries
    assert (entry.mode, entry.cases, entry.status) == ("sync", 10, "settled")
    assert entry.cost_usd == Decimal("0.2190")  # 10 x $0.0219
    assert "Refusals                  0" in result.output


def test_batch_run_has_no_latency_and_records_the_batch(tmp_path, fake_claude):
    result = claude_eval(tmp_path, "--mode", "batch")
    assert result.exit_code == 0, result.output
    assert "Submitted Message Batch msgbatch_test" in result.output
    assert "unavailable (batch)" in result.output
    assert all(t.decisions.latency_ms is None for t in only_traces(tmp_path))
    [entry] = load_ledger(tmp_path / "spend.json").entries
    assert (entry.mode, entry.status, entry.batch_id) == ("batch", "settled", "msgbatch_test")
    assert entry.cost_usd == Decimal("0.10950")  # 10 x $0.01095
    assert len(fake_claude.batches.created) == 1


def test_a_run_over_budget_exits_2_with_the_numbers_and_writes_nothing(tmp_path, fake_claude):
    result = claude_eval(tmp_path, "--budget-usd", "1")
    assert result.exit_code == 2
    assert (
        "Claude budget exceeded: spent $0.0000 + projected $2.5000 = $2.5000, over the $1.00 "
        "budget" in result.output
    )
    assert not (tmp_path / "traces").exists()
    assert not (tmp_path / "spend.json").exists()


def test_reattaching_to_a_recorded_batch_does_not_submit_or_double_count(tmp_path, fake_claude):
    ledger = reserve(
        SpendLedger(),
        run_id="run_failed",
        dataset_id="smoke-v0.1",
        mode="batch",
        cases=10,
        projected=Decimal("1.25"),
    )
    ledger = ledger.model_copy(
        update={"entries": [ledger.entries[0].model_copy(update={"batch_id": "msgbatch_test"})]}
    )
    write_ledger(tmp_path / "spend.json", ledger)
    result = claude_eval(tmp_path, "--mode", "batch", "--batch-id", "msgbatch_test")
    assert result.exit_code == 0, result.output
    assert "projected $0.0000" in result.output
    assert fake_claude.batches.created == []
    failed, resumed = load_ledger(tmp_path / "spend.json").entries
    assert (failed.status, failed.cost_usd) == ("settled", Decimal("0"))
    assert (resumed.status, resumed.cost_usd) == ("settled", Decimal("0.10950"))


@pytest.mark.parametrize(
    "args, message_text",
    [
        (["--provider", "rules", "--mode", "batch"], "--mode applies only to --provider claude"),
        (["--provider", "rules", "--budget-usd", "5"], "--budget-usd applies only"),
        (["--provider", "claude", "--batch-id", "msgbatch_x"], "--batch-id needs --mode batch"),
        (["--provider", "claude", "--questions", "q-v0.1"], "choose one of: q-v0.2"),
    ],
)
def test_claude_flag_misuse_is_a_usage_error(tmp_path, fake_claude, args, message_text):
    result = runner.invoke(
        app,
        [
            "--env-file",
            str(tmp_path / "missing.env"),
            "run",
            "--dataset",
            str(SMOKE),
            "--traces-dir",
            str(tmp_path / "traces"),
            "--reports-dir",
            str(tmp_path / "reports"),
            *args,
        ],
    )
    assert result.exit_code == 2
    assert message_text in result.output
    assert not (tmp_path / "traces").exists()


def test_the_run_report_labels_claude_runs(tmp_path, fake_claude):
    result = claude_eval(tmp_path)
    assert result.exit_code == 0, result.output
    report = next((tmp_path / "reports").glob("*.md")).read_text()
    assert CLAUDE_NOTE in report
    results = json.loads(next((tmp_path / "results").glob("*.json")).read_text())
    assert results["refusals"] == 0 and results["execution_modes"] == ["sync"]


def test_a_batch_submission_failure_still_settles_the_reservation(tmp_path, fake_claude):
    """A run that dies mid-flight (here: the batch submission call itself raises, before any
    batch id exists) must not leave its reservation stuck at "reserved" forever: nothing was ever
    submitted or billed, so it settles at 0 rather than leaking its full projected cost."""

    async def boom(*, requests):
        raise RuntimeError("simulated batch submission failure")

    fake_claude.batches.create = boom
    result = claude_eval(tmp_path, "--mode", "batch")
    assert result.exit_code != 0
    assert list((tmp_path / "traces").glob("*.jsonl")) == []
    [entry] = load_ledger(tmp_path / "spend.json").entries
    assert entry.status == "settled"
    assert entry.cost_usd == Decimal("0")


def test_a_batch_submission_4xx_still_settles_the_reservation_at_zero(tmp_path, fake_claude):
    """C2: a 4xx from batches.create() is a definite failure -- the API rejected the request
    outright, so nothing was ever submitted or billed, unlike the ambiguous cases below."""

    async def reject(*, requests):
        raise status_error(400)

    fake_claude.batches.create = reject
    result = claude_eval(tmp_path, "--mode", "batch")
    assert result.exit_code != 0
    [entry] = load_ledger(tmp_path / "spend.json").entries
    assert entry.status == "settled"
    assert entry.cost_usd == Decimal("0")


@pytest.mark.parametrize("error", [connection_error(), status_error(500)])
def test_an_ambiguous_batch_submission_failure_keeps_the_reservation_reserved(
    tmp_path, fake_claude, error
):
    """C2: a connection error, timeout, or 5xx from batches.create() might have reached
    Anthropic's servers anyway. Settling at 0 could hide a batch that is already billing, so the
    reservation must stay reserved (there is no batch id to attach) with guidance to check by
    hand, rather than assuming nothing happened."""

    async def maybe_submitted(*, requests):
        raise error

    fake_claude.batches.create = maybe_submitted
    result = claude_eval(tmp_path, "--mode", "batch")
    assert result.exit_code != 0
    assert list((tmp_path / "traces").glob("*.jsonl")) == []
    [entry] = load_ledger(tmp_path / "spend.json").entries
    assert entry.status == "reserved"
    assert entry.cost_usd == Decimal("1.25")  # untouched projected cost
    assert "may or may not have reached" in result.output
    assert "batches list" in result.output


def test_reattaching_to_an_already_settled_batch_is_refused(tmp_path, fake_claude):
    """C4: re-attaching to a batch id that is already fully settled must not silently project $0
    and re-process it -- that would add a second settled entry for the same money, with the
    budget check never having looked at that real cost at all."""
    ledger = reserve(
        SpendLedger(),
        run_id="run_done",
        dataset_id="smoke-v0.1",
        mode="batch",
        cases=10,
        projected=Decimal("1.25"),
    )
    ledger = settle(ledger, "run_done", Decimal("0.10950"), batch_id="msgbatch_test")
    write_ledger(tmp_path / "spend.json", ledger)
    result = claude_eval(tmp_path, "--mode", "batch", "--batch-id", "msgbatch_test")
    assert result.exit_code == 2
    assert "already settled" in result.output
    assert fake_claude.batches.created == []
    [entry] = load_ledger(tmp_path / "spend.json").entries
    assert (entry.status, entry.cost_usd) == ("settled", Decimal("0.10950"))


def test_reattaching_to_an_already_settled_batch_cites_the_entry_that_holds_the_cost(
    tmp_path, fake_claude
):
    """M1: after a normal re-attach, find_batch's *first* match for a batch id is the superseded
    $0 bookkeeping entry, not the one that actually holds the real cost. The refusal message must
    name the entry with the money, not the $0 one, so an operator isn't sent looking at the wrong
    run."""
    ledger = reserve(
        SpendLedger(),
        run_id="run_orig",
        dataset_id="smoke-v0.1",
        mode="batch",
        cases=10,
        projected=Decimal("1.25"),
    )
    ledger = attach_batch(ledger, "run_orig", "msgbatch_test")
    ledger = reserve(
        ledger,
        run_id="run_resume",
        dataset_id="smoke-v0.1",
        mode="batch",
        cases=10,
        projected=Decimal("0"),
    )
    ledger = settle(ledger, "run_orig", Decimal("0"), batch_id="msgbatch_test")
    ledger = settle(ledger, "run_resume", Decimal("0.10950"), batch_id="msgbatch_test")
    write_ledger(tmp_path / "spend.json", ledger)
    result = claude_eval(tmp_path, "--mode", "batch", "--batch-id", "msgbatch_test")
    assert result.exit_code == 2
    assert "run_resume" in result.output
    assert "$0.1095" in result.output
    assert "run_orig" not in result.output


def test_a_known_reattach_skips_the_budget_cap_even_when_already_over_budget(tmp_path, fake_claude):
    """I1/C4: re-attaching to a batch that is already known to the ledger (still reserved) must
    never be blocked by the cap. Collecting its results spends nothing new, no matter how the
    ledger's other spend compares to --budget-usd."""
    ledger = reserve(
        SpendLedger(),
        run_id="run_orig",
        dataset_id="smoke-v0.1",
        mode="batch",
        cases=10,
        projected=Decimal("1.25"),
    )
    ledger = attach_batch(ledger, "run_orig", "msgbatch_test")
    write_ledger(tmp_path / "spend.json", ledger)
    # spent_usd (1.25) already exceeds this budget; a normal budget check would refuse.
    result = claude_eval(
        tmp_path, "--mode", "batch", "--batch-id", "msgbatch_test", "--budget-usd", "1"
    )
    assert result.exit_code == 0, result.output
    assert "projected $0.0000" in result.output
    [orig, resumed] = load_ledger(tmp_path / "spend.json").entries
    assert (orig.status, orig.cost_usd) == ("settled", Decimal("0"))
    assert (resumed.status, resumed.cost_usd) == ("settled", Decimal("0.10950"))


def test_an_unknown_batch_id_binds_to_the_matching_orphan_without_stacking_a_reservation(
    tmp_path, fake_claude
):
    """I1/C4: an operator-supplied --batch-id that the CLI never recorded (found by hand via
    `batches list` after an ambiguous create() failure) must bind to the leftover orphaned
    reservation rather than stacking a brand-new projected reservation on top of it."""
    ledger = reserve(
        SpendLedger(),
        run_id="run_orphan",
        dataset_id="smoke-v0.1",
        mode="batch",
        cases=10,
        projected=Decimal("1.25"),
    )
    write_ledger(tmp_path / "spend.json", ledger)
    result = claude_eval(tmp_path, "--mode", "batch", "--batch-id", "msgbatch_test")
    assert result.exit_code == 0, result.output
    assert "warning" not in result.output
    assert fake_claude.batches.created == []
    entries = load_ledger(tmp_path / "spend.json").entries
    assert len(entries) == 2  # the orphan (zeroed) plus this run (settled at the real cost)
    orphan = next(e for e in entries if e.run_id == "run_orphan")
    assert (orphan.status, orphan.cost_usd, orphan.batch_id) == (
        "settled",
        Decimal("0"),
        "msgbatch_test",
    )
    other = next(e for e in entries if e.run_id != "run_orphan")
    assert (other.status, other.cost_usd, other.batch_id) == (
        "settled",
        Decimal("0.10950"),
        "msgbatch_test",
    )


def test_an_unknown_batch_id_with_no_orphan_match_reserves_fresh_and_skips_the_cap(
    tmp_path, fake_claude
):
    """I1/C4: with no matching orphan to bind to, the CLI falls back to a fresh bookkeeping
    reservation (printing a warning) rather than guessing -- but the cap still isn't checked,
    since re-attaching never calls create() and so never spends anything beyond what the batch
    already cost server-side."""
    result = claude_eval(
        tmp_path, "--mode", "batch", "--batch-id", "msgbatch_test", "--budget-usd", "0"
    )
    assert result.exit_code == 0, result.output
    assert "warning" in result.output and "msgbatch_test" in result.output
    assert fake_claude.batches.created == []
    [entry] = load_ledger(tmp_path / "spend.json").entries
    assert (entry.status, entry.batch_id) == ("settled", "msgbatch_test")


def test_an_interrupted_reattach_before_the_provider_exists_keeps_the_reservation_reserved(
    tmp_path, fake_claude, monkeypatch
):
    """CRITICAL regression (C1-new): a --batch-id re-attach that dies before the provider object
    even exists (e.g. a crash inside _build_provider, before AsyncAnthropic's context manager
    finishes) must not zero the batch's real, still-uncollected reservation. Previously
    getattr(provider, "batch_id", None) resolved to None whenever `provider` was never assigned,
    so the interrupted-run handler wrongly took the "nothing was submitted, settle at 0" branch --
    permanently erasing a real reservation, after which the new settled-batch refusal (C4) then
    blocked any further recovery."""
    ledger = reserve(
        SpendLedger(),
        run_id="run_orig",
        dataset_id="smoke-v0.1",
        mode="batch",
        cases=10,
        projected=Decimal("1.25"),
    )
    ledger = attach_batch(ledger, "run_orig", "msgbatch_test")
    write_ledger(tmp_path / "spend.json", ledger)

    real_build_provider = cli_module._build_provider
    calls = {"n": 0}

    async def flaky_build_provider(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated crash before the provider is assigned")
        return await real_build_provider(*args, **kwargs)

    monkeypatch.setattr(cli_module, "_build_provider", flaky_build_provider)

    result = claude_eval(tmp_path, "--mode", "batch", "--batch-id", "msgbatch_test")
    assert result.exit_code != 0
    # This run's own (known, $0) reservation may also be left "reserved" -- that's harmless. What
    # matters is that the *original* reservation, holding the batch's real projected cost, is
    # untouched rather than zeroed out.
    orig = next(e for e in load_ledger(tmp_path / "spend.json").entries if e.run_id == "run_orig")
    assert (orig.status, orig.cost_usd, orig.batch_id) == (
        "reserved",
        Decimal("1.25"),
        "msgbatch_test",
    )

    result2 = claude_eval(tmp_path, "--mode", "batch", "--batch-id", "msgbatch_test")
    assert result2.exit_code == 0, result2.output
    entries = load_ledger(tmp_path / "spend.json").entries
    settled_with_cost = [
        e
        for e in entries
        if e.batch_id == "msgbatch_test" and e.status == "settled" and e.cost_usd > 0
    ]
    assert len(settled_with_cost) == 1


async def test_a_cancelled_batch_submission_keeps_the_reservation_reserved(tmp_path, monkeypatch):
    """I2: Ctrl-C or task cancellation while batches.create() is in flight must be treated the
    same as a connection error or a 5xx -- the request may have reached the server anyway -- not
    as a definite "nothing was submitted" failure that settles at 0."""
    cases = load_dataset(SMOKE)
    claude = cli_module.ClaudeRun(
        mode="batch", budget_usd=Decimal("60"), ledger=tmp_path / "spend.json"
    )

    class CancelledDuringSubmission:
        name = "claude"
        batch_id = None

        async def prepare(self, cases):
            raise asyncio.CancelledError()

    async def fake_build_provider(*args, **kwargs):
        return CancelledDuringSubmission()

    monkeypatch.setattr(cli_module, "_build_provider", fake_build_provider)
    with pytest.raises(asyncio.CancelledError):
        await cli_module._execute(
            cases,
            cli_module.ProviderName.claude,
            "v0.1",
            1,
            tmp_path / "traces",
            tmp_path / "dataset",
            "q-v0.2",
            None,
            claude,
            Decimal("1.25"),
        )

    [entry] = load_ledger(tmp_path / "spend.json").entries
    assert entry.status == "reserved"
    assert entry.cost_usd == Decimal("1.25")


def test_partial_traces_drops_only_a_torn_last_line(tmp_path):
    """C6: a crash mid-append can leave a torn last line (a partial write, no trailing newline).
    That alone must not discard the complete lines written before it."""
    cases = load_dataset(SMOKE)[:2]
    store = TraceStore.create(tmp_path, "run_torn")
    for case in cases:
        store.append(make_trace(case, make_bundle(case.input.id, provider="claude")))
    with store.path.open("a", encoding="utf-8") as handle:
        handle.write('{"trace_id": "tr_torn", "run_id": "run_torn", "case_id":')  # cut short
    traces = cli_module._partial_traces(store)
    assert traces is not None
    assert [t.case_id for t in traces] == [c.input.id for c in cases]


def test_partial_traces_drops_a_last_line_torn_mid_multibyte_character(tmp_path):
    """M2: a write cut short in the middle of a multi-byte UTF-8 character (trace text can
    contain non-ASCII, e.g. an em dash) must not raise UnicodeDecodeError out of _partial_traces
    -- it's still just a torn last line, and the complete lines before it must still be
    recovered."""
    cases = load_dataset(SMOKE)[:2]
    store = TraceStore.create(tmp_path, "run_torn_utf8")
    for case in cases:
        store.append(make_trace(case, make_bundle(case.input.id, provider="claude")))
    em_dash = "—".encode()  # 3 bytes; write only the first 2 to cut through the character
    with store.path.open("ab") as handle:
        handle.write(b'{"trace_id": "tr_torn", "note": "cut mid-dash ' + em_dash[:2])
    traces = cli_module._partial_traces(store)
    assert traces is not None
    assert [t.case_id for t in traces] == [c.input.id for c in cases]


def test_partial_traces_is_none_when_a_non_last_line_is_corrupt(tmp_path):
    """A bad line that isn't the last one means something worse than a torn write happened; the
    caller must not guess which lines are trustworthy."""
    store = TraceStore.create(tmp_path, "run_corrupt")
    case = load_dataset(SMOKE)[0]
    good_line = make_trace(case, make_bundle(case.input.id, provider="claude")).model_dump_json()
    store.path.write_text("not json at all\n" + good_line + "\n", encoding="utf-8")
    assert cli_module._partial_traces(store) is None


def test_settle_interrupted_keeps_the_reservation_reserved_when_the_trace_file_is_corrupt(
    tmp_path, capsys
):
    """C6: settling a corrupt trace file at 0 (or at whatever partial traces happen to parse)
    could under-count real, already-incurred sync spend. Unknown must not be treated as zero."""
    claude = cli_module.ClaudeRun(
        mode="sync", budget_usd=Decimal("60"), ledger=tmp_path / "spend.json"
    )
    ledger = reserve(
        SpendLedger(),
        run_id="run_corrupt",
        dataset_id="smoke-v0.1",
        mode="sync",
        cases=10,
        projected=Decimal("2.5"),
    )
    write_ledger(claude.ledger, ledger)
    store = TraceStore.create(tmp_path / "traces", "run_corrupt")
    store.path.write_text("not json at all\nnor is this\n", encoding="utf-8")
    cli_module._settle_interrupted(claude, "run_corrupt", store, None)
    [entry] = load_ledger(claude.ledger).entries
    assert (entry.status, entry.cost_usd) == ("reserved", Decimal("2.5"))
    assert "could not be parsed" in capsys.readouterr().err


async def test_a_mid_run_sync_failure_settles_the_cases_actually_completed(tmp_path, monkeypatch):
    """The in-memory `traces` list run_dataset would have returned is empty when it raises
    partway through, but the cases that did complete already made a billable API call and are
    durably written to the trace file. Settling must read the actual cost from disk, not report 0
    spend for work that really happened."""
    cases = load_dataset(SMOKE)
    claude = cli_module.ClaudeRun(
        mode="sync", budget_usd=Decimal("60"), ledger=tmp_path / "spend.json"
    )

    class DyingProvider:
        name = "claude"

        def __init__(self):
            self.calls = 0

        async def decide(self, case_input):
            self.calls += 1
            if self.calls > 3:
                raise RuntimeError("simulated mid-run failure")
            return make_bundle(case_id=case_input.id, provider="claude", cost=Decimal("0.01"))

    async def fake_build_provider(*args, **kwargs):
        return DyingProvider()

    monkeypatch.setattr(cli_module, "_build_provider", fake_build_provider)
    with pytest.raises(RuntimeError, match="simulated mid-run failure"):
        await cli_module._execute(
            cases,
            cli_module.ProviderName.claude,
            "v0.1",
            1,
            tmp_path / "traces",
            tmp_path / "dataset",
            "q-v0.2",
            None,
            claude,
            Decimal("2.5"),
        )

    [entry] = load_ledger(tmp_path / "spend.json").entries
    assert entry.status == "settled"
    assert entry.cost_usd == Decimal("0.03")  # 3 completed cases x $0.01, not 0


def test_a_failure_after_batch_submission_leaves_the_reservation_reserved(tmp_path, fake_claude):
    """Once a batch is submitted, Anthropic bills for it whether or not this process is still
    around to collect the results. If the CLI dies while polling or reading results, settling at
    0 (or at whatever partial traces happen to exist) would hide real, already-incurred spend.
    The reservation must stay "reserved" at its projected cost, with the batch id attached, so a
    later --batch-id re-attach can read the real results and settle the real cost."""

    async def boom(message_batch_id):
        raise RuntimeError("simulated results failure")

    fake_claude.batches.results = boom
    result = claude_eval(tmp_path, "--mode", "batch")
    assert result.exit_code != 0
    assert list((tmp_path / "traces").glob("*.jsonl")) == []
    assert len(fake_claude.batches.created) == 1
    [entry] = load_ledger(tmp_path / "spend.json").entries
    assert entry.status == "reserved"
    assert entry.batch_id == "msgbatch_test"
    assert entry.cost_usd == Decimal("1.25")  # untouched projected cost, not settled
    assert "--batch-id msgbatch_test" in result.output
