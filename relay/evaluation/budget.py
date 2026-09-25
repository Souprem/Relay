"""Claude spend ledger and the pre-run budget guard (2D spec L9).

The ledger (results/claude-spend.json by default; its committed copy is
evals/baselines/claude-spend.json) lists every Claude run and its cost. Before a run, the CLI
reserves the projected cost, so a run that dies midway still counts against the budget. When the
run finishes, the reservation is settled at the run's actual estimated cost.

Projection: the measured mean cost per case of the settled sync runs (the first is the smoke run)
x case count, x 0.5 in batch mode. Before any sync run is settled, a deliberately pessimistic
prior per case is used instead.
"""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from relay.decisions.claude import BATCH_DISCOUNT, Mode

DEFAULT_BUDGET_USD = Decimal("60")
DEFAULT_LEDGER = Path("results/claude-spend.json")
PRIOR_COST_PER_CASE_USD = Decimal("0.25")


class SpendEntry(BaseModel):
    run_id: str
    dataset_id: str
    mode: Mode
    cases: int
    status: Literal["reserved", "settled"]
    cost_usd: Decimal
    recorded_at: datetime
    batch_id: str | None = None


class SpendLedger(BaseModel):
    entries: list[SpendEntry] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def spent_usd(self) -> Decimal:
        """Settled costs plus outstanding reservations."""
        return sum((e.cost_usd for e in self.entries), Decimal("0"))


class BudgetExceeded(Exception):
    def __init__(self, spent: Decimal, projected: Decimal, budget: Decimal) -> None:
        self.spent, self.projected, self.budget = spent, projected, budget
        super().__init__(
            f"Claude budget exceeded: spent ${spent:.4f} + projected ${projected:.4f} "
            f"= ${spent + projected:.4f}, over the ${budget:.2f} budget"
        )


def load_ledger(path: Path) -> SpendLedger:
    if not path.exists():
        return SpendLedger()
    return SpendLedger.model_validate_json(path.read_text(encoding="utf-8"))


def write_ledger(path: Path, ledger: SpendLedger) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ledger.model_dump_json(indent=2) + "\n", encoding="utf-8")


def cost_per_case(ledger: SpendLedger) -> Decimal | None:
    """Mean measured cost per case over settled sync runs, or None if there are none."""
    sync = [e for e in ledger.entries if e.status == "settled" and e.mode == "sync" and e.cases]
    if not sync:
        return None
    return sum((e.cost_usd for e in sync), Decimal("0")) / sum(e.cases for e in sync)


def project_cost(ledger: SpendLedger, n_cases: int, mode: Mode) -> Decimal:
    per_case = cost_per_case(ledger)
    cost = (PRIOR_COST_PER_CASE_USD if per_case is None else per_case) * n_cases
    return cost * BATCH_DISCOUNT if mode == "batch" else cost


def check_budget(ledger: SpendLedger, projected: Decimal, budget: Decimal) -> None:
    if ledger.spent_usd + projected > budget:
        raise BudgetExceeded(ledger.spent_usd, projected, budget)


def reserve(
    ledger: SpendLedger,
    *,
    run_id: str,
    dataset_id: str,
    mode: Mode,
    cases: int,
    projected: Decimal,
    now: datetime | None = None,
) -> SpendLedger:
    entry = SpendEntry(
        run_id=run_id,
        dataset_id=dataset_id,
        mode=mode,
        cases=cases,
        status="reserved",
        cost_usd=projected,
        recorded_at=now or datetime.now(UTC),
    )
    return SpendLedger(entries=[*ledger.entries, entry])


def settle(
    ledger: SpendLedger,
    run_id: str,
    cost: Decimal,
    *,
    batch_id: str | None = None,
    now: datetime | None = None,
) -> SpendLedger:
    """Replace run_id's reservation with its actual cost. KeyError if it was never reserved."""
    indices = [i for i, e in enumerate(ledger.entries) if e.run_id == run_id]
    if not indices:
        raise KeyError(f"no ledger entry for run {run_id}")
    entries = list(ledger.entries)
    entries[indices[-1]] = entries[indices[-1]].model_copy(
        update={
            "status": "settled",
            "cost_usd": cost,
            "batch_id": batch_id,
            "recorded_at": now or datetime.now(UTC),
        }
    )
    return SpendLedger(entries=entries)


def attach_batch(ledger: SpendLedger, run_id: str, batch_id: str) -> SpendLedger:
    """Record the Message Batch a reserved run submitted, so a re-attached run can find it."""
    if not any(e.run_id == run_id for e in ledger.entries):
        raise KeyError(f"no ledger entry for run {run_id}")
    return SpendLedger(
        entries=[
            e.model_copy(update={"batch_id": batch_id}) if e.run_id == run_id else e
            for e in ledger.entries
        ]
    )


def find_batch(ledger: SpendLedger, batch_id: str) -> SpendEntry | None:
    """The first entry that submitted or settled this batch, if any."""
    return next((e for e in ledger.entries if e.batch_id == batch_id), None)
