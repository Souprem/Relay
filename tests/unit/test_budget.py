from datetime import UTC, datetime
from decimal import Decimal

import pytest

from relay.evaluation.budget import (
    PRIOR_COST_PER_CASE_USD,
    BudgetExceeded,
    SpendLedger,
    attach_batch,
    check_budget,
    cost_per_case,
    find_batch,
    load_ledger,
    project_cost,
    reserve,
    settle,
    write_ledger,
)

NOW = datetime(2026, 9, 25, tzinfo=UTC)


def ledger_with(*runs):
    """runs: (run_id, mode, cases, cost) tuples, each reserved and then settled."""
    ledger = SpendLedger()
    for run_id, mode, cases, cost in runs:
        ledger = reserve(
            ledger,
            run_id=run_id,
            dataset_id="d",
            mode=mode,
            cases=cases,
            projected=Decimal("1"),
            now=NOW,
        )
        ledger = settle(ledger, run_id, Decimal(cost), now=NOW)
    return ledger


def test_a_missing_ledger_file_is_an_empty_ledger(tmp_path):
    ledger = load_ledger(tmp_path / "none.json")
    assert ledger.entries == [] and ledger.spent_usd == Decimal("0")


def test_projection_uses_the_pessimistic_prior_before_any_sync_run():
    assert PRIOR_COST_PER_CASE_USD == Decimal("0.25")
    assert project_cost(SpendLedger(), 10, "sync") == Decimal("2.50")
    assert project_cost(SpendLedger(), 400, "batch") == Decimal("50.000")


def test_projection_uses_the_measured_sync_cost_per_case_and_halves_batch():
    ledger = ledger_with(("smoke", "sync", 10, "0.60"), ("dev", "batch", 400, "9.00"))
    assert cost_per_case(ledger) == Decimal("0.06")  # batch runs do not count
    assert project_cost(ledger, 1000, "batch") == Decimal("30.00")
    assert project_cost(ledger, 100, "sync") == Decimal("6.00")


def test_reservations_do_not_count_as_measured_cost_per_case():
    ledger = reserve(
        SpendLedger(), run_id="r", dataset_id="d", mode="sync", cases=10, projected=Decimal("5")
    )
    assert cost_per_case(ledger) is None
    assert ledger.spent_usd == Decimal("5")


def test_check_budget_refuses_when_spent_plus_projected_exceeds_it():
    ledger = ledger_with(("smoke", "sync", 10, "50"))
    check_budget(ledger, Decimal("10"), Decimal("60"))  # exactly at the budget is allowed
    with pytest.raises(BudgetExceeded) as caught:
        check_budget(ledger, Decimal("12"), Decimal("60"))
    assert str(caught.value) == (
        "Claude budget exceeded: spent $50.0000 + projected $12.0000 = $62.0000, "
        "over the $60.00 budget"
    )


def test_settle_replaces_the_reservation_with_the_actual_cost():
    ledger = reserve(
        SpendLedger(), run_id="r", dataset_id="d", mode="batch", cases=4, projected=Decimal("3")
    )
    ledger = settle(ledger, "r", Decimal("1.25"), batch_id="msgbatch_1", now=NOW)
    [entry] = ledger.entries
    assert (entry.status, entry.cost_usd, entry.batch_id) == (
        "settled",
        Decimal("1.25"),
        "msgbatch_1",
    )
    assert ledger.spent_usd == Decimal("1.25")
    with pytest.raises(KeyError):
        settle(ledger, "unknown", Decimal("1"))


def test_the_ledger_round_trips_through_json(tmp_path):
    path = tmp_path / "results" / "claude-spend.json"
    ledger = ledger_with(("smoke", "sync", 10, "0.60"))
    write_ledger(path, ledger)
    assert '"spent_usd": "0.60"' in path.read_text()
    assert load_ledger(path) == ledger


def test_a_submitted_batch_is_attached_to_its_reservation_and_can_be_found():
    ledger = reserve(
        SpendLedger(), run_id="r", dataset_id="d", mode="batch", cases=4, projected=Decimal("3")
    )
    ledger = attach_batch(ledger, "r", "msgbatch_1")
    entry = find_batch(ledger, "msgbatch_1")
    assert (entry.run_id, entry.status, entry.cost_usd) == ("r", "reserved", Decimal("3"))
    assert find_batch(ledger, "msgbatch_other") is None
    with pytest.raises(KeyError):
        attach_batch(ledger, "unknown", "msgbatch_1")
