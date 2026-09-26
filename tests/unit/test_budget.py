from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from relay.evaluation.budget import (
    PRIOR_COST_PER_CASE_USD,
    PROJECTION_SAFETY_MARGIN,
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


def test_projection_uses_the_max_per_case_of_its_own_mode_with_the_safety_margin():
    """C1: batch projects from real batch evidence (not sync x 0.5), sync from real sync
    evidence; each mode's own settled runs, not the other's."""
    ledger = ledger_with(("smoke", "sync", 10, "0.60"), ("dev", "batch", 400, "9.00"))
    assert cost_per_case(ledger, "sync") == Decimal("0.06")
    assert cost_per_case(ledger, "batch") == Decimal("0.0225")  # 9.00 / 400, not the sync figure
    assert (
        project_cost(ledger, 1000, "batch") == Decimal("0.0225") * PROJECTION_SAFETY_MARGIN * 1000
    )
    assert project_cost(ledger, 100, "sync") == Decimal("0.06") * PROJECTION_SAFETY_MARGIN * 100


def test_projection_uses_the_maximum_not_the_mean_across_runs():
    """C1: real per-case cost varied $0.0103-$0.0164 across batch runs; a mean would
    under-estimate the next run, so the worst run observed so far sets the projection."""
    ledger = ledger_with(
        ("dev-1", "batch", 400, "4.00"),  # $0.01/case
        ("holdout", "batch", 150, "2.4"),  # $0.016/case, the max
    )
    assert cost_per_case(ledger, "batch") == Decimal("2.4") / 150
    assert (
        project_cost(ledger, 100, "batch")
        == (Decimal("2.4") / 150) * PROJECTION_SAFETY_MARGIN * 100
    )


def test_zero_cost_settled_entries_are_excluded_as_bookkeeping_cruft():
    """A superseded/re-attached/canceled batch settles at $0 (its cost moved to another entry);
    it must not be treated as evidence that a run costs $0/case."""
    ledger = ledger_with(("canceled", "batch", 400, "0"), ("real", "batch", 378, "4.00"))
    assert cost_per_case(ledger, "batch") == Decimal("4.00") / 378
    ledger_only_zero = ledger_with(("canceled", "batch", 400, "0"))
    assert cost_per_case(ledger_only_zero, "batch") is None
    assert project_cost(ledger_only_zero, 100, "batch") == PRIOR_COST_PER_CASE_USD * 100 * Decimal(
        "0.5"
    )


def test_reservations_do_not_count_as_measured_cost_per_case():
    ledger = reserve(
        SpendLedger(), run_id="r", dataset_id="d", mode="sync", cases=10, projected=Decimal("5")
    )
    assert cost_per_case(ledger, "sync") is None
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
    assert '"spent_usd": "0.600000"' in path.read_text()
    assert load_ledger(path) == ledger


def test_write_ledger_rounds_cost_usd_to_6_decimal_places(tmp_path):
    """C8: the pricing arithmetic can produce far more than 6 decimal places (e.g. the cache
    write multiplier alone adds two); the persisted ledger should not carry that false
    precision."""
    path = tmp_path / "spend.json"
    ledger = reserve(
        SpendLedger(), run_id="r", dataset_id="d", mode="sync", cases=1, projected=Decimal("0")
    )
    ledger = settle(ledger, "r", Decimal("0.0123456789"))
    write_ledger(path, ledger)
    [entry] = load_ledger(path).entries
    assert entry.cost_usd == Decimal("0.012346")  # rounded, not truncated


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


def test_write_ledger_is_atomic_and_survives_crash_mid_write(tmp_path):
    """Write to temp file, fsync, then atomic replace. No temp file left after success or failure."""
    path = tmp_path / "results" / "claude-spend.json"
    ledger = ledger_with(("smoke", "sync", 10, "0.60"))
    write_ledger(path, ledger)

    # Verify no temp file is left behind after successful write
    tmp_files = list(tmp_path.glob("results/*.tmp"))
    assert len(tmp_files) == 0, f"Temp file(s) left behind after success: {tmp_files}"

    # Verify content round-trips
    assert load_ledger(path) == ledger

    # Simulate a crash during write: replace() fails, old file should be intact
    old_content = path.read_text()
    with patch("os.replace", side_effect=OSError("Simulated crash")):
        with pytest.raises(OSError, match="Simulated crash"):
            write_ledger(path, SpendLedger())

    # Old ledger should still be intact
    assert path.read_text() == old_content
    assert load_ledger(path) == ledger

    # Verify no temp file is left behind after failure
    tmp_files = list(tmp_path.glob("results/*.tmp"))
    assert len(tmp_files) == 0, f"Temp file(s) left behind after failure: {tmp_files}"


def test_reserve_refuses_duplicate_run_ids():
    """Cannot reserve a run_id that already exists (prevents leaked entries)."""
    ledger = reserve(
        SpendLedger(),
        run_id="r",
        dataset_id="d",
        mode="sync",
        cases=10,
        projected=Decimal("5"),
    )
    with pytest.raises(ValueError, match="run_id 'r' already reserved"):
        reserve(
            ledger,
            run_id="r",
            dataset_id="d2",
            mode="sync",
            cases=20,
            projected=Decimal("10"),
        )
