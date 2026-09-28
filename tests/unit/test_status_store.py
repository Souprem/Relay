"""The simulated case-status store: transitions, atomic writes, idempotence, conflicts, resets,
and the guarantee that a shadow trace never changes case state."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

import relay.workflow.status as status_module
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.status import (
    ACTION_STATUS,
    DEFAULT_STATE,
    CaseStatus,
    ConflictError,
    ShadowWriteError,
    StatusStore,
    StatusStoreError,
    apply_transition,
    apply_transitions,
    ensure_unclaimed,
    load_store,
    reset_state,
    state_digest,
)
from tests.factories import make_bundle, make_case, make_trace

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 26, 12, tzinfo=UTC)


def trace(case_id="T-01", *, mode="simulated", run_id="run_a", **bundle):
    case = make_case(case_id)
    t = make_trace(case, make_bundle(case_id, **bundle), run_id=run_id)
    return t.model_copy(update={"mode": mode, "trace_id": f"tr_{run_id}_{case_id}"})


def test_the_default_state_path_is_in_the_git_ignored_state_dir():
    assert DEFAULT_STATE.as_posix() == "state/case-status.json"
    assert "/state/" in (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_each_action_maps_to_one_status():
    assert ACTION_STATUS == {
        WorkflowAction.AUTO_PROCESS: CaseStatus.AUTO_APPROVED,
        WorkflowAction.REQUEST_INFO: CaseStatus.INFO_REQUESTED,
        WorkflowAction.HUMAN_REVIEW: CaseStatus.IN_HUMAN_REVIEW,
    }


def test_a_missing_file_is_an_empty_store_and_every_case_is_received(tmp_path):
    store = load_store(tmp_path / "none.json")
    assert store.root == {}
    assert store.status_of("T-01") is CaseStatus.RECEIVED
    assert store.last_transition("T-01") is None
    assert state_digest(tmp_path / "none.json") == "absent"


@pytest.mark.parametrize(
    "bundle,status",
    [
        ({}, CaseStatus.AUTO_APPROVED),
        ({"doc": 0.3}, CaseStatus.INFO_REQUESTED),
        ({"step": 0.5}, CaseStatus.IN_HUMAN_REVIEW),
    ],
)
def test_a_simulated_trace_moves_its_case_from_received(tmp_path, bundle, status):
    path = tmp_path / "state" / "case-status.json"
    t = trace(**bundle)
    transition = apply_transition(path, t, now=NOW)
    assert transition is not None
    assert (transition.from_status, transition.to, transition.action) == (
        CaseStatus.RECEIVED,
        status,
        t.action,
    )
    assert (transition.trace_id, transition.run_id, transition.at) == (t.trace_id, "run_a", NOW)
    stored = json.loads(path.read_text())
    assert stored == {
        "T-01": {
            "status": status.value,
            "history": [
                {
                    "from": "RECEIVED",
                    "to": status.value,
                    "action": t.action.value,
                    "trace_id": t.trace_id,
                    "run_id": "run_a",
                    "at": "2026-09-26T12:00:00Z",
                }
            ],
        }
    }
    assert load_store(path).status_of("T-01") is status


def test_a_run_is_applied_in_one_write(tmp_path, monkeypatch):
    path = tmp_path / "s.json"
    writes = []
    real = status_module._write
    monkeypatch.setattr(status_module, "_write", lambda p, s: (writes.append(p), real(p, s)))
    store, recorded = apply_transitions(path, [trace("T-01"), trace("T-02", doc=0.3)], now=NOW)
    assert len(writes) == 1 and len(recorded) == 2
    assert store.status_of("T-02") is CaseStatus.INFO_REQUESTED


def test_the_write_is_atomic_and_leaves_no_temp_file(tmp_path, monkeypatch):
    path = tmp_path / "s.json"
    apply_transition(path, trace("T-01"), now=NOW)
    before = path.read_bytes()

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(status_module.os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        apply_transition(path, trace("T-02"), now=NOW)
    assert path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["s.json"]


def test_reapplying_the_same_trace_is_an_idempotent_no_op(tmp_path):
    path = tmp_path / "s.json"
    t = trace()
    apply_transition(path, t, now=NOW)
    before = path.read_bytes()
    os.utime(path, (0, 0))
    assert apply_transition(path, t, now=datetime(2027, 1, 1, tzinfo=UTC)) is None
    assert path.read_bytes() == before
    assert path.stat().st_mtime == 0  # not rewritten


def test_another_run_on_a_moved_case_is_a_conflict(tmp_path):
    path = tmp_path / "s.json"
    apply_transition(path, trace(run_id="run_a"), now=NOW)
    before = path.read_bytes()
    with pytest.raises(ConflictError, match="T-01 is already AUTO_APPROVED by run run_a"):
        apply_transitions(path, [trace("T-02", run_id="run_b"), trace("T-01", run_id="run_b")])
    assert path.read_bytes() == before  # nothing from run_b was written, not even T-02


def test_a_case_twice_in_one_run_is_a_conflict(tmp_path):
    with pytest.raises(ConflictError, match="appears twice"):
        apply_transitions(tmp_path / "s.json", [trace("T-01"), trace("T-01", doc=0.3)])
    assert not (tmp_path / "s.json").exists()


def test_ensure_unclaimed_names_the_claimed_cases(tmp_path):
    path = tmp_path / "s.json"
    apply_transitions(path, [trace("T-01"), trace("T-02", step=0.5)], now=NOW)
    store = load_store(path)
    ensure_unclaimed(store, ["T-03"])
    with pytest.raises(ConflictError) as error:
        ensure_unclaimed(store, ["T-03", "T-02", "T-01"])
    message = str(error.value)
    assert "2 case(s) already moved past RECEIVED" in message
    assert "T-01 (AUTO_APPROVED by run_a), T-02 (IN_HUMAN_REVIEW by run_a)" in message
    assert "--reset-state" in message


def test_a_shadow_trace_raises_and_leaves_the_file_byte_identical(tmp_path):
    path = tmp_path / "s.json"
    apply_transition(path, trace("T-01"), now=NOW)
    before = path.read_bytes()
    digest = state_digest(path)
    with pytest.raises(ShadowWriteError, match="shadow traces never change case state"):
        apply_transition(path, trace("T-02", mode="shadow", run_id="run_s"))
    with pytest.raises(ShadowWriteError):
        apply_transitions(path, [trace("T-03"), trace("T-04", mode="shadow")])
    assert path.read_bytes() == before
    assert state_digest(path) == digest
    assert sorted(p.name for p in tmp_path.iterdir()) == ["s.json"]


def test_a_shadow_trace_never_creates_the_state_file(tmp_path):
    path = tmp_path / "s.json"
    with pytest.raises(ShadowWriteError):
        apply_transition(path, trace(mode="shadow"))
    assert not path.exists()


def test_an_evaluate_trace_is_refused_too(tmp_path):
    with pytest.raises(StatusStoreError, match="only simulated traces"):
        apply_transition(tmp_path / "s.json", trace(mode="evaluate"))
    assert not (tmp_path / "s.json").exists()


def test_reset_state_archives_the_file(tmp_path):
    path = tmp_path / "s.json"
    assert reset_state(path, NOW) is None
    apply_transition(path, trace(), now=NOW)
    content = path.read_bytes()
    backup = reset_state(path, NOW)
    assert backup == tmp_path / "s.json.bak-20260926T120000Z"
    assert backup.read_bytes() == content
    assert not path.exists()
    apply_transition(path, trace(run_id="run_b"), now=NOW)  # no conflict after a reset
    content_b = path.read_bytes()
    again = reset_state(path, NOW)  # N1: a same-second archive name picks a unique suffix
    assert again == tmp_path / "s.json.bak-20260926T120000Z-1"
    assert again.read_bytes() == content_b
    assert backup.read_bytes() == content  # the first archive is untouched
    assert not path.exists()


def test_a_malformed_state_file_is_a_store_error(tmp_path):
    path = tmp_path / "s.json"
    path.write_text('{"T-01": {"status": "LOST"}}')
    with pytest.raises(StatusStoreError, match="malformed status store"):
        load_store(path)


def test_state_digest_tracks_the_bytes(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{}")
    first = state_digest(path)
    assert first.startswith("sha256:") and first == state_digest(path)
    path.write_text("{} ")
    assert state_digest(path) != first


def test_store_round_trips_by_alias():
    store = StatusStore.model_validate(
        {
            "T-01": {
                "status": "AUTO_APPROVED",
                "history": [
                    {
                        "from": "RECEIVED",
                        "to": "AUTO_APPROVED",
                        "action": "AUTO_PROCESS",
                        "trace_id": "tr_1",
                        "run_id": "run_a",
                        "at": "2026-09-26T12:00:00Z",
                    }
                ],
            }
        }
    )
    assert StatusStore.model_validate_json(store.model_dump_json(by_alias=True)) == store
