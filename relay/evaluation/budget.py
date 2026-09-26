"""Claude spend ledger and the pre-run budget guard (2D spec L9).

The ledger (results/claude-spend.json by default; its committed copy is
evals/baselines/claude-spend.json) lists every Claude run and its cost. Before a run, the CLI
reserves the projected cost, so a run that dies midway still counts against the budget. When the
run finishes, the reservation is settled at the run's actual estimated cost.

Projection: the MAXIMUM measured cost per case among the settled runs of the same mode (sync or
batch), times a safety margin (PROJECTION_SAFETY_MARGIN), times the case count. The maximum is
used rather than the mean because real per-case cost varies a lot between runs, and some entries'
`cases` count includes cases that were never actually billed (a batch canceled or superseded
before finishing still counts its full planned size, not the smaller number actually charged),
which makes a mean an under-estimate. Settled entries with cost_usd == 0 are excluded: those are
bookkeeping cruft (a superseded, re-attached, or canceled reservation that was zeroed out when a
later run collected the real cost), not evidence of a cheap run. Before any such entry exists for
a mode, a deliberately pessimistic prior is used instead: the full input price for every input
token (no cache-read discount) plus the output price, at that mode's price (half for batch).
"""

import os
import shutil
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from relay.decisions.claude import BATCH_DISCOUNT, Mode

DEFAULT_BUDGET_USD = Decimal("10")
DEFAULT_LEDGER = Path("results/claude-spend.json")
PRIOR_COST_PER_CASE_USD = Decimal("0.25")
# Applied to the max observed per-case cost before projecting a new run (C1): real data showed
# per-case cost varying between runs (e.g. $0.0103 to $0.0164), so a flat max is still not enough
# margin on its own.
PROJECTION_SAFETY_MARGIN = Decimal("1.25")
LEDGER_COST_DECIMAL_PLACES = Decimal("0.000001")


class SpendEntry(BaseModel):
    run_id: str
    dataset_id: str
    mode: Mode
    cases: int
    status: Literal["reserved", "settled"]
    cost_usd: Decimal
    recorded_at: datetime
    batch_id: str | None = None
    # Why an entry was changed by hand (`relay budget release`); None for every other entry and
    # for ledgers written before Phase 3B.
    note: str | None = None


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


def _round_costs(ledger: SpendLedger) -> SpendLedger:
    """Round every entry's cost_usd to 6 decimal places (C8): the pricing arithmetic in
    relay.decisions.claude can produce far more decimal places than a dollar amount ever needs
    (e.g. the cache-write multiplier alone adds two more), and that false precision has no
    business being persisted."""
    return SpendLedger(
        entries=[
            e.model_copy(
                update={
                    "cost_usd": e.cost_usd.quantize(
                        LEDGER_COST_DECIMAL_PLACES, rounding=ROUND_HALF_EVEN
                    )
                }
            )
            for e in ledger.entries
        ]
    )


def write_ledger(path: Path, ledger: SpendLedger) -> None:
    ledger = _round_costs(ledger)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file first, fsync, then atomically replace the original
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(ledger.model_dump_json(indent=2) + "\n", encoding="utf-8")
        # Ensure the temp file is flushed to disk before replacing
        with open(tmp_path, "rb") as f:
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        # Clean up temp file if any step fails and re-raise the original error
        tmp_path.unlink(missing_ok=True)
        raise


def cost_per_case(ledger: SpendLedger, mode: Mode) -> Decimal | None:
    """Maximum measured cost per case over settled runs of `mode`, or None if there are none.

    Entries with cost_usd == 0 are excluded (see the module docstring): they are bookkeeping
    cruft, not evidence that a run was cheap. The maximum, not the mean, is used because per-case
    cost varies a lot between runs and a mean would under-estimate.
    """
    billed = [
        e
        for e in ledger.entries
        if e.status == "settled" and e.mode == mode and e.cases and e.cost_usd > 0
    ]
    if not billed:
        return None
    return max(e.cost_usd / e.cases for e in billed)


def project_cost(ledger: SpendLedger, n_cases: int, mode: Mode) -> Decimal:
    """Projected cost of running `n_cases` more cases in `mode`. See the module docstring."""
    per_case = cost_per_case(ledger, mode)
    if per_case is not None:
        return per_case * PROJECTION_SAFETY_MARGIN * n_cases
    cost = PRIOR_COST_PER_CASE_USD * n_cases
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
    if any(e.run_id == run_id for e in ledger.entries):
        raise ValueError(f"run_id '{run_id}' already reserved")
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


class LedgerRefusal(ValueError):
    """`relay budget release` will not change this entry (exit 2)."""


def ledger_totals(ledger: SpendLedger) -> tuple[Decimal, Decimal, Decimal]:
    """(settled, reserved, total) spend across every entry."""
    settled = sum((e.cost_usd for e in ledger.entries if e.status == "settled"), Decimal("0"))
    reserved = sum((e.cost_usd for e in ledger.entries if e.status == "reserved"), Decimal("0"))
    return settled, reserved, settled + reserved


def release(
    ledger: SpendLedger,
    run_id: str,
    *,
    reason: str,
    force_batch: bool = False,
    now: datetime | None = None,
) -> SpendLedger:
    """Settle run_id's still-reserved entry at $0, recording why in its note.

    For a reservation that is known never to have been billed (an ambiguous submission that
    never reached Anthropic). Refused with LedgerRefusal: an unknown run, an entry that is
    already settled, an empty reason, and an entry carrying a batch id unless force_batch (that
    batch may still bill; re-attach with --batch-id instead).
    """
    indices = [i for i, e in enumerate(ledger.entries) if e.run_id == run_id]
    if not indices:
        raise LedgerRefusal(f"no ledger entry for run {run_id}")
    entry = ledger.entries[indices[-1]]
    if entry.status != "reserved":
        raise LedgerRefusal(
            f"run {run_id} is already settled at ${entry.cost_usd:.4f}; only a reserved entry "
            "can be released"
        )
    if entry.batch_id is not None and not force_batch:
        raise LedgerRefusal(
            f"run {run_id} carries Message Batch {entry.batch_id}, which may still bill: check "
            f"the Console Batches page and re-attach with --mode batch --batch-id "
            f"{entry.batch_id}; pass --force-batch only if that batch never ran"
        )
    if not reason.strip():
        raise LedgerRefusal("--reason must say why this reservation is being released")
    when = now or datetime.now(UTC)
    entries = list(ledger.entries)
    entries[indices[-1]] = entry.model_copy(
        update={
            "status": "settled",
            "cost_usd": Decimal("0"),
            "recorded_at": when,
            "note": (
                f"released by hand at $0 (was reserved at ${entry.cost_usd:.4f}): {reason.strip()}"
            ),
        }
    )
    return SpendLedger(entries=entries)


def backup_ledger(path: Path, now: datetime | None = None) -> Path:
    """Copy the ledger to <ledger>.bak-<UTC timestamp> before it is rewritten by hand."""
    when = now or datetime.now(UTC)
    backup = path.with_name(f"{path.name}.bak-{when:%Y%m%dT%H%M%SZ}")
    shutil.copy2(path, backup)
    return backup
