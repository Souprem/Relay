"""relay run/eval --provider claude with fake Anthropic clients (no network, no real key)."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

import relay.cli as cli_module
from relay.cases.loader import load_dataset
from relay.cli import app
from relay.evaluation.budget import SpendLedger, load_ledger, reserve, write_ledger
from relay.reporting import CLAUDE_NOTE
from relay.traces.store import read_traces
from tests.claude_fakes import FakeBatches, FakeMessages, message, succeeded
from tests.factories import make_bundle

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
SMOKE_IDS = sorted(c.input.id for c in load_dataset(SMOKE))
runner = CliRunner()


class FakeAnthropic:
    """Stands in for anthropic.AsyncAnthropic; every case gets the same well-formed reply."""

    batches: FakeBatches

    def __init__(self, **kwargs):
        self.messages = FakeMessages(message(), batches=FakeAnthropic.batches)

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
