"""relay eval --jev-budget-usd / --jev-ledger: the Phase 3D Jev spend counter (fake client)."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner
from typesafe_sdk import SystemOneResponse

import relay.cli as cli_module
from relay.cli import app
from relay.evaluation.budget import load_ledger, reserve, write_ledger

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
FIXTURE = REPO / "tests" / "fixtures" / "jev" / "auto01_response.json"
runner = CliRunner()


class FakeAsyncClient:
    """Answers every case with the AUTO-01 fixture (1,800 input tokens: $0.0000756 a case)."""

    calls = 0

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def system_one(self, state, questions, *, model=None, **kwargs):
        FakeAsyncClient.calls += 1
        return SystemOneResponse.model_validate(json.loads(FIXTURE.read_text()))


@pytest.fixture
def fake_jev(monkeypatch):
    FakeAsyncClient.calls = 0
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", FakeAsyncClient)
    return FakeAsyncClient


def eval_jev(tmp_path, *extra, provider="jev"):
    return runner.invoke(
        app,
        [
            "--env-file",
            str(tmp_path / "missing.env"),
            "eval",
            "--dataset",
            str(SMOKE),
            "--provider",
            provider,
            "--traces-dir",
            str(tmp_path / "traces"),
            "--reports-dir",
            str(tmp_path / "reports"),
            "--results-dir",
            str(tmp_path / "results"),
            *extra,
        ],
    )


def test_a_counted_run_prints_the_estimate_reserves_and_settles(tmp_path, fake_jev):
    ledger = tmp_path / "jev-spend.json"
    result = eval_jev(tmp_path, "--jev-budget-usd", "1.00", "--jev-ledger", str(ledger))
    assert result.exit_code == 0, result.output
    # 10 smoke cases x 12 questions x $0.000013
    assert "jev estimate: 10 cases × 12 questions ≈ $0.0016" in result.output
    assert "Jev budget: spent $0.0000 of the $1.00 cap" in result.output
    [entry] = load_ledger(ledger).entries
    assert (entry.status, entry.mode, entry.cases, entry.dataset_id) == (
        "settled",
        "sync",
        10,
        "smoke-v0.1",
    )
    assert entry.cost_usd == Decimal("0.000756")  # 10 x 1,800 tokens x $0.042 / 1M
    assert "Jev spend: this run $0.0008; total $0.0008 of the $1.00 cap" in result.output


def test_q_v0_3_estimates_nineteen_questions(tmp_path, fake_jev):
    result = eval_jev(
        tmp_path,
        "--questions",
        "q-v0.3",
        "--jev-budget-usd",
        "1.00",
        "--jev-ledger",
        str(tmp_path / "l.json"),
    )
    # The fake answers only the 12 q-v0.2 questions, so every bundle is malformed; the counter
    # still prints the estimate first and settles what the calls cost.
    assert "jev estimate: 10 cases × 19 questions ≈ $0.0025" in result.output


def test_the_counter_refuses_a_run_over_the_cap_before_any_call(tmp_path, fake_jev):
    ledger = tmp_path / "jev-spend.json"
    earlier = reserve(
        load_ledger(ledger),
        run_id="run_earlier",
        dataset_id="gen-v0.3-dev",
        mode="sync",
        cases=400,
        projected=Decimal("0.9990"),
    )
    write_ledger(ledger, earlier)
    result = eval_jev(tmp_path, "--jev-budget-usd", "1.00", "--jev-ledger", str(ledger))
    assert result.exit_code == 2
    assert "jev estimate: 10 cases × 12 questions ≈ $0.0016" in result.output
    assert (
        "Jev budget exceeded: spent $0.9990 + projected $0.0016 = $1.0006, over the $1.00 budget"
    ) in result.output
    assert fake_jev.calls == 0
    assert len(load_ledger(ledger).entries) == 1
    assert not (tmp_path / "traces").exists() or not list((tmp_path / "traces").iterdir())


def test_the_default_ledger_is_results_jev_spend_3d(tmp_path, fake_jev, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = eval_jev(tmp_path, "--jev-budget-usd", "1.00")
    assert result.exit_code == 0, result.output
    assert (tmp_path / "results" / "jev-spend-3d.json").exists()
    assert not (tmp_path / "results" / "claude-spend.json").exists()


def test_a_failed_run_settles_what_was_written(tmp_path, fake_jev, monkeypatch):
    ledger = tmp_path / "jev-spend.json"

    async def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(cli_module, "run_dataset", boom)
    result = eval_jev(tmp_path, "--jev-budget-usd", "1.00", "--jev-ledger", str(ledger))
    assert result.exit_code != 0
    [entry] = load_ledger(ledger).entries
    assert (entry.status, entry.cost_usd) == ("settled", Decimal("0"))


@pytest.mark.parametrize(
    "extra,provider,message",
    [
        (["--jev-budget-usd", "1"], "rules", "--jev-budget-usd applies only to --provider jev"),
        (["--jev-ledger", "x.json"], "groundtruth", "--jev-ledger applies only to --provider jev"),
        (["--jev-ledger", "x.json"], "jev", "--jev-ledger needs --jev-budget-usd"),
    ],
)
def test_misused_flags_are_exit_2(tmp_path, fake_jev, extra, provider, message):
    result = eval_jev(tmp_path, *extra, provider=provider)
    assert result.exit_code == 2
    assert message in result.output
    assert fake_jev.calls == 0


def test_the_counter_does_not_apply_to_re_scoring(tmp_path, fake_jev):
    assert eval_jev(tmp_path).exit_code == 0
    [trace_file] = (tmp_path / "traces").glob("*.jsonl")
    result = eval_jev(tmp_path, "--traces", str(trace_file), "--jev-budget-usd", "1")
    assert result.exit_code == 2
    assert "need a run, not --traces" in result.output
