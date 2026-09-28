"""The Phase 3D Jev spend counter: an estimate before every paid Jev run, and a small ledger.

It reuses the Claude ledger machinery in relay.evaluation.budget (SpendLedger, reserve, settle,
check_budget) on its own file, results/jev-spend-3d.json by default, so Jev spend is never mixed
with results/claude-spend.json. Jev calls are synchronous, so every entry has mode "sync".

Estimate: cases x questions per case x JEV_ESTIMATE_PER_QUESTION_USD, with every call priced as
at least JEV_MIN_BILLED_QUESTIONS questions. The rate is the largest measured per-case cost of the
committed Jev runs ($0.000127 for 12 questions, gold-v0.1), divided by 12, times 1.25 and rounded
up. The floor exists because a call pays for its state (policy and documents) however few
questions it asks, which matters for relay bench's 1- and 5-question calls.
"""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from relay.evaluation.budget import SpendLedger, check_budget, reserve, settle

DEFAULT_JEV_LEDGER = Path("results/jev-spend-3d.json")
JEV_ESTIMATE_PER_QUESTION_USD = Decimal("0.000013")
JEV_MIN_BILLED_QUESTIONS = 12
JEV_LABEL = "Jev"


@dataclass(frozen=True)
class JevBudget:
    """--jev-budget-usd and --jev-ledger: the cap on the ledger's total Jev spend."""

    budget_usd: Decimal
    ledger: Path


def estimate_jev_cost(cases: int, questions_per_case: int) -> Decimal:
    """The pre-run estimate for `cases` calls of `questions_per_case` questions each."""
    billed = max(questions_per_case, JEV_MIN_BILLED_QUESTIONS)
    return JEV_ESTIMATE_PER_QUESTION_USD * cases * billed


def estimate_line(cases: int, questions: int | str, estimate: Decimal) -> str:
    """'jev estimate: 400 cases × 19 questions ≈ $0.0988' (printed before every paid run)."""
    return f"jev estimate: {cases} cases × {questions} questions ≈ ${estimate:.4f}"


def check_jev_budget(ledger: SpendLedger, estimate: Decimal, budget: Decimal) -> None:
    """BudgetExceeded ("Jev budget exceeded: ...") if the ledger's spend (settled costs plus open
    reservations) plus `estimate` would exceed `budget`."""
    check_budget(ledger, estimate, budget, label=JEV_LABEL)


def reserve_jev(
    ledger: SpendLedger, *, run_id: str, dataset_id: str, cases: int, estimate: Decimal
) -> SpendLedger:
    return reserve(
        ledger, run_id=run_id, dataset_id=dataset_id, mode="sync", cases=cases, projected=estimate
    )


def settle_jev(ledger: SpendLedger, run_id: str, actual: Decimal) -> SpendLedger:
    return settle(ledger, run_id, actual)
