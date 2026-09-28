"""relay budget show / release on temporary ledgers only; results/claude-spend.json is never
read or written here."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from typer.testing import CliRunner

from relay.cli import app
from relay.evaluation.budget import (
    SpendLedger,
    attach_batch,
    load_ledger,
    reserve,
    settle,
    write_ledger,
)

NOW = datetime(2026, 9, 25, tzinfo=UTC)


@pytest.fixture
def ledger(tmp_path):
    ledger = SpendLedger()
    for run_id, mode, projected in (
        ("run_smoke", "sync", "0.30"),
        ("run_stuck", "batch", "1.50"),
        ("run_batched", "batch", "2.00"),
    ):
        ledger = reserve(
            ledger,
            run_id=run_id,
            dataset_id="gen-v0.2-dev",
            mode=mode,
            cases=10,
            projected=Decimal(projected),
            now=NOW,
        )
    ledger = settle(ledger, "run_smoke", Decimal("0.25"), now=NOW)
    ledger = attach_batch(ledger, "run_batched", "msgbatch_test")
    path = tmp_path / "spend.json"
    write_ledger(path, ledger)
    return path


def budget(tmp_path, *args):
    return CliRunner().invoke(
        app, ["--env-file", str(tmp_path / "missing.env"), "budget", *map(str, args)]
    )


def test_show_lists_entries_and_totals(tmp_path, ledger):
    result = budget(tmp_path, "show", "--ledger", ledger)
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0] == f"Claude spend ledger — {ledger}"
    assert any(line.startswith("run_batched") and "msgbatch_test" in line for line in lines)
    assert lines[-1] == (
        "Settled $0.2500 · reserved $3.5000 · total $3.7500 of the $10.00 default budget"
    )


def test_show_on_a_missing_ledger_is_empty(tmp_path):
    result = budget(tmp_path, "show", "--ledger", tmp_path / "none.json")
    assert result.exit_code == 0
    assert "no entries" in result.output


def test_release_settles_at_zero_backs_up_and_prints_the_ledger(tmp_path, ledger):
    before = ledger.read_text()
    result = budget(
        tmp_path,
        "release",
        "run_stuck",
        "--ledger",
        ledger,
        "--reason",
        "never reached Anthropic",
        "--yes",
    )
    assert result.exit_code == 0, result.output
    entry = next(e for e in load_ledger(ledger).entries if e.run_id == "run_stuck")
    assert (entry.status, entry.cost_usd) == ("settled", Decimal("0"))
    assert entry.note.endswith("never reached Anthropic")
    [backup] = tmp_path.glob("spend.json.bak-*")
    assert backup.read_text() == before
    assert f"Backup: {backup}" in result.output
    assert "reserved $2.0000" in result.output


@pytest.mark.parametrize(
    "args,message",
    [
        (["run_stuck", "--reason", "x"], "pass --yes to confirm"),
        (["run_smoke", "--reason", "x", "--yes"], "already settled"),
        (["run_nope", "--reason", "x", "--yes"], "no ledger entry for run run_nope"),
        (["run_batched", "--reason", "x", "--yes"], "carries Message Batch msgbatch_test"),
    ],
)
def test_release_refusals_are_exit_2_and_leave_the_ledger_alone(tmp_path, ledger, args, message):
    before = ledger.read_text()
    result = budget(tmp_path, "release", *args, "--ledger", ledger)
    assert result.exit_code == 2, result.output
    assert message in result.output
    assert ledger.read_text() == before
    assert list(tmp_path.glob("spend.json.bak-*")) == []


def test_force_batch_releases_a_batch_entry(tmp_path, ledger):
    result = budget(
        tmp_path,
        "release",
        "run_batched",
        "--ledger",
        ledger,
        "--reason",
        "batch never ran",
        "--yes",
        "--force-batch",
    )
    assert result.exit_code == 0, result.output
    entry = next(e for e in load_ledger(ledger).entries if e.run_id == "run_batched")
    assert (entry.status, entry.cost_usd) == ("settled", Decimal("0"))


def test_release_needs_an_existing_ledger(tmp_path):
    result = budget(
        tmp_path, "release", "run_x", "--ledger", tmp_path / "none.json", "--reason", "x", "--yes"
    )
    assert result.exit_code == 2
    assert "does not exist" in result.output
