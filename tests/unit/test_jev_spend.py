"""The Jev spend counter: estimate, cap check, reserve and settle on a tmp ledger."""

from decimal import Decimal

import pytest

from relay.evaluation.budget import BudgetExceeded, load_ledger, write_ledger
from relay.evaluation.jev_spend import (
    DEFAULT_JEV_LEDGER,
    JEV_ESTIMATE_PER_QUESTION_USD,
    check_jev_budget,
    estimate_jev_cost,
    estimate_line,
    reserve_jev,
    settle_jev,
)


def test_default_ledger_is_its_own_file_never_the_claude_ledger():
    assert DEFAULT_JEV_LEDGER.as_posix() == "results/jev-spend-3d.json"


def test_estimate_is_cases_times_questions_with_a_twelve_question_floor():
    assert JEV_ESTIMATE_PER_QUESTION_USD == Decimal("0.000013")
    assert estimate_jev_cost(400, 19) == Decimal("0.098800")
    assert estimate_jev_cost(1000, 12) == Decimal("0.156000")
    assert estimate_jev_cost(40, 1) == estimate_jev_cost(40, 12) == Decimal("0.006240")
    assert estimate_jev_cost(40, 20) == Decimal("0.010400")


def test_estimate_line_format():
    assert estimate_line(400, 19, Decimal("0.0988")) == (
        "jev estimate: 400 cases × 19 questions ≈ $0.0988"
    )


def test_reserve_check_and_settle_on_a_tmp_ledger(tmp_path):
    path = tmp_path / "jev-spend.json"
    ledger = load_ledger(path)  # a missing file is an empty ledger
    check_jev_budget(ledger, Decimal("0.5"), Decimal("1.00"))
    ledger = reserve_jev(
        ledger, run_id="run_a", dataset_id="gen-v0.3-dev", cases=400, estimate=Decimal("0.0988")
    )
    write_ledger(path, ledger)
    [entry] = load_ledger(path).entries
    assert (entry.status, entry.mode, entry.cost_usd) == ("reserved", "sync", Decimal("0.0988"))
    ledger = settle_jev(load_ledger(path), "run_a", Decimal("0.0712"))
    write_ledger(path, ledger)
    assert load_ledger(path).spent_usd == Decimal("0.0712")


def test_the_cap_counts_reservations_and_names_jev(tmp_path):
    ledger = reserve_jev(
        load_ledger(tmp_path / "none.json"),
        run_id="run_a",
        dataset_id="d",
        cases=1,
        estimate=Decimal("0.95"),
    )
    with pytest.raises(BudgetExceeded) as caught:
        check_jev_budget(ledger, Decimal("0.06"), Decimal("1.00"))
    assert str(caught.value) == (
        "Jev budget exceeded: spent $0.9500 + projected $0.0600 = $1.0100, over the $1.00 budget"
    )
    check_jev_budget(ledger, Decimal("0.05"), Decimal("1.00"))  # exactly at the cap is allowed
