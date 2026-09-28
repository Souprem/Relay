"""The simulated case-status store (Phase 3C): where the incumbent's actions take effect.

A JSON file mapping case id -> {status, history}. Every case starts RECEIVED (implicitly: a case
with no entry is RECEIVED) and a simulated run moves it to the status its action implies. Only
apply_transitions (and apply_transition, one trace) writes the file, and it refuses a shadow
trace with ShadowWriteError before touching anything: that refusal is the enforced guarantee that
a shadow candidate cannot change case state. Writes are atomic (temp file + os.replace).
"""

import hashlib
import os
import tempfile
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationError

from relay.traces.models import WorkflowTrace
from relay.workflow.outcomes import WorkflowAction

DEFAULT_STATE = Path("state/case-status.json")


class CaseStatus(StrEnum):
    RECEIVED = "RECEIVED"
    AUTO_APPROVED = "AUTO_APPROVED"
    INFO_REQUESTED = "INFO_REQUESTED"
    IN_HUMAN_REVIEW = "IN_HUMAN_REVIEW"


ACTION_STATUS: dict[WorkflowAction, CaseStatus] = {
    WorkflowAction.AUTO_PROCESS: CaseStatus.AUTO_APPROVED,
    WorkflowAction.REQUEST_INFO: CaseStatus.INFO_REQUESTED,
    WorkflowAction.HUMAN_REVIEW: CaseStatus.IN_HUMAN_REVIEW,
}


class StatusStoreError(ValueError):
    """The status store cannot be read, or this write is not allowed (a usage error: exit 2)."""


class ShadowWriteError(StatusStoreError):
    """A shadow trace was offered to the status store. Shadow proposals never take effect."""


class ConflictError(StatusStoreError):
    """A case was already moved past RECEIVED by another run (use --reset-state to start over)."""


class Transition(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    from_status: CaseStatus = Field(alias="from")
    to: CaseStatus
    action: WorkflowAction
    trace_id: str
    run_id: str
    at: datetime


class CaseRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: CaseStatus
    history: list[Transition]


class StatusStore(RootModel[dict[str, CaseRecord]]):
    """case id -> record. A case missing from the store is RECEIVED."""

    root: dict[str, CaseRecord] = {}

    def status_of(self, case_id: str) -> CaseStatus:
        record = self.root.get(case_id)
        return CaseStatus.RECEIVED if record is None else record.status

    def last_transition(self, case_id: str) -> Transition | None:
        record = self.root.get(case_id)
        return None if record is None or not record.history else record.history[-1]


def load_store(path: Path) -> StatusStore:
    """The store at `path`; an empty store when the file does not exist."""
    if not path.exists():
        return StatusStore()
    try:
        return StatusStore.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValidationError, OSError) as error:
        raise StatusStoreError(f"{path}: malformed status store: {error}") from error


def state_digest(path: Path) -> str:
    """sha256 of the file's bytes, or "absent" when there is no file."""
    if not path.exists():
        return "absent"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, store: StatusStore) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(store.model_dump_json(by_alias=True, indent=2) + "\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def ensure_unclaimed(store: StatusStore, case_ids: Iterable[str]) -> None:
    """ConflictError if any of these cases was already moved past RECEIVED. A new simulated run
    checks this before it decides anything, so a conflict costs no provider call."""
    claimed = sorted(
        f"{case_id} ({store.status_of(case_id)} by {t.run_id})"
        for case_id in set(case_ids)
        if (t := store.last_transition(case_id)) is not None
    )
    if claimed:
        shown = ", ".join(claimed[:5]) + (
            f" and {len(claimed) - 5} more" if len(claimed) > 5 else ""
        )
        raise ConflictError(
            f"{len(claimed)} case(s) already moved past RECEIVED by an earlier simulated run: "
            f"{shown}. Pass --reset-state to archive the state file and start over."
        )


def apply_transitions(
    path: Path, traces: Sequence[WorkflowTrace], *, now: datetime | None = None
) -> tuple[StatusStore, list[Transition]]:
    """Apply a simulated run's actions to the store at `path` in one atomic write.

    Every trace is checked before anything is written: a shadow trace raises ShadowWriteError, a
    trace of any other non-simulated mode raises StatusStoreError, and a case already moved past
    RECEIVED raises ConflictError unless the recorded transition has this trace's trace_id (then
    it is an idempotent no-op). Returns the new store and the transitions recorded (no-ops
    excluded). With nothing to record the file is not rewritten.
    """
    for trace in traces:
        if trace.mode == "shadow":
            raise ShadowWriteError(
                f"{trace.case_id}: trace {trace.trace_id} is a shadow proposal (run "
                f"{trace.run_id}); shadow traces never change case state"
            )
        if trace.mode != "simulated":
            raise StatusStoreError(
                f"{trace.case_id}: trace {trace.trace_id} has mode {trace.mode!r}; only "
                "simulated traces change case state"
            )
    store = load_store(path)
    when = now or datetime.now(UTC)
    records = dict(store.root)
    recorded: list[Transition] = []
    for trace in traces:
        last = store.last_transition(trace.case_id)
        if last is not None:
            if last.trace_id == trace.trace_id:
                continue
            raise ConflictError(
                f"{trace.case_id} is already {store.status_of(trace.case_id)} by run "
                f"{last.run_id}; run {trace.run_id} cannot move it again. Pass --reset-state "
                "to archive the state file and start over."
            )
        if trace.case_id in records:
            raise ConflictError(f"{trace.case_id} appears twice in run {trace.run_id}")
        transition = Transition(
            from_status=CaseStatus.RECEIVED,
            to=ACTION_STATUS[trace.action],
            action=trace.action,
            trace_id=trace.trace_id,
            run_id=trace.run_id,
            at=when,
        )
        records[trace.case_id] = CaseRecord(status=transition.to, history=[transition])
        recorded.append(transition)
    updated = StatusStore(records)
    if recorded:
        _write(path, updated)
    return updated, recorded


def apply_transition(
    path: Path, trace: WorkflowTrace, *, now: datetime | None = None
) -> Transition | None:
    """One trace through apply_transitions: the transition recorded, or None for a no-op."""
    _, recorded = apply_transitions(path, [trace], now=now)
    return recorded[0] if recorded else None


def reset_state(path: Path, now: datetime | None = None) -> Path | None:
    """Archive the state file to <state>.bak-<UTC timestamp> (os.replace, so the state is then
    absent), or <state>.bak-<UTC timestamp>-<n> (n = 1, 2, ...) when that name is already taken
    (two resets in the same second, or --reset-state run twice against `now`). Returns the
    archive path, or None when there was no state file.

    N1: this never raises for a name collision. `_run_simulated` calls this only after the run's
    inputs (and, for a live provider, its spend) are already committed to, so a raise here would
    otherwise discard a run that already happened for nothing.
    """
    if not path.exists():
        return None
    when = now or datetime.now(UTC)
    base = f"{path.name}.bak-{when:%Y%m%dT%H%M%SZ}"
    backup = path.with_name(base)
    suffix = 1
    while backup.exists():
        backup = path.with_name(f"{base}-{suffix}")
        suffix += 1
    os.replace(path, backup)
    return backup
