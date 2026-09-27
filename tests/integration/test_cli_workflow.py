"""relay run --workflow simulated | shadow (Phase 3C). Offline: --from-traces over smoke runs made
in tmp by the groundtruth and rules providers. The live provider path uses fakes only. Every
state file is under tmp_path; nothing here touches state/ or the real spend ledger."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner
from typesafe_sdk import SystemOneResponse

import relay.cli as cli_module
import relay.workflow.status as status_module
from relay.cli import app
from relay.evaluation.tracediff import replay_run as real_replay_run
from relay.traces.store import read_traces
from relay.workflow.status import load_store, state_digest
from tests.claude_fakes import FakeBatches, FakeMessages, message

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
JEV_FIXTURE = REPO / "tests" / "fixtures" / "jev" / "auto01_response.json"
runner = CliRunner()

STATUS_OF = {
    "AUTO_PROCESS": "AUTO_APPROVED",
    "REQUEST_INFO": "INFO_REQUESTED",
    "HUMAN_REVIEW": "IN_HUMAN_REVIEW",
}
PROPOSAL = {
    "AUTO_PROCESS": "SHADOW: Would auto-process {}; no action was taken.",
    "REQUEST_INFO": "SHADOW: Would request information for {}; no action was taken.",
    "HUMAN_REVIEW": "SHADOW: Would send {} to human review; no action was taken.",
}


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--env-file", str(tmp_path / "missing.env"), *map(str, args)])


def workflow(tmp_path, kind, *args):
    return invoke(
        tmp_path,
        "run",
        "--dataset",
        SMOKE,
        "--workflow",
        kind,
        "--traces-dir",
        tmp_path / "traces",
        "--state",
        tmp_path / "state" / "case-status.json",
        *args,
    )


def new_run(tmp_path, result):
    """The trace file and manifest a workflow run printed."""
    lines = result.output.splitlines()
    trace_file = Path(next(x for x in lines if x.startswith("Traces: ")).removeprefix("Traces: "))
    manifest = json.loads(trace_file.with_suffix(".manifest.json").read_text())
    return trace_file, manifest


@pytest.fixture(scope="module")
def smoke_runs(tmp_path_factory):
    """One ordinary (evaluate) smoke run per offline provider, made once for the module."""
    root = tmp_path_factory.mktemp("workflow-smoke")
    files = {}
    for provider in ("groundtruth", "rules"):
        result = invoke(
            root,
            "run",
            "--dataset",
            SMOKE,
            "--provider",
            provider,
            "--traces-dir",
            root / provider / "traces",
            "--reports-dir",
            root / provider / "reports",
        )
        assert result.exit_code == 0, result.output
        [files[provider]] = (root / provider / "traces").glob("*.jsonl")
    return files


# ---- simulated ----


def test_simulated_applies_every_action_to_the_state(tmp_path, smoke_runs):
    result = workflow(tmp_path, "simulated", "--from-traces", smoke_runs["groundtruth"])
    assert result.exit_code == 0, result.output
    trace_file, manifest = new_run(tmp_path, result)
    traces = read_traces(trace_file)
    source = {t.case_id: t for t in read_traces(smoke_runs["groundtruth"])}
    assert len(traces) == 10
    assert {t.mode for t in traces} == {"simulated"}
    assert {t.run_id for t in traces} == {manifest["run_id"]}
    assert all(t.replay_of == source[t.case_id].trace_id for t in traces)
    assert (manifest["mode"], manifest["source_run_id"]) == (
        "simulated",
        smoke_runs["groundtruth"].stem,
    )
    lines = result.output.splitlines()
    for t in traces:
        expected = f"SIMULATED: {t.case_id} RECEIVED → {STATUS_OF[t.action]} ({t.action})"
        assert expected in lines
    assert lines[:10] == sorted(lines[:10])  # one line per case, by case id
    assert (
        f"SIMULATED RUN {manifest['run_id']}: 10 transitions applied — AUTO_APPROVED 3 · "
        "INFO_REQUESTED 3 · IN_HUMAN_REVIEW 4"
    ) in lines
    state = tmp_path / "state" / "case-status.json"
    assert lines[-1] == f"State: {state}"
    store = load_store(state)
    assert {c: store.status_of(c) for c in source} == {
        c: STATUS_OF[t.action] for c, t in source.items()
    }
    assert {store.last_transition(c).run_id for c in source} == {manifest["run_id"]}


def test_a_second_simulated_run_conflicts_until_the_state_is_reset(tmp_path, smoke_runs):
    first = workflow(tmp_path, "simulated", "--from-traces", smoke_runs["groundtruth"])
    assert first.exit_code == 0, first.output
    state = tmp_path / "state" / "case-status.json"
    before = state.read_bytes()
    runs_before = sorted((tmp_path / "traces").glob("*.jsonl"))
    again = workflow(tmp_path, "simulated", "--from-traces", smoke_runs["rules"])
    assert again.exit_code == 2
    assert "10 case(s) already moved past RECEIVED" in again.output
    assert "--reset-state" in again.output
    assert state.read_bytes() == before
    assert sorted((tmp_path / "traces").glob("*.jsonl")) == runs_before  # checked before running
    reset = workflow(tmp_path, "simulated", "--from-traces", smoke_runs["rules"], "--reset-state")
    assert reset.exit_code == 0, reset.output
    [backup] = (tmp_path / "state").glob("case-status.json.bak-*")
    assert backup.read_bytes() == before
    assert f"State archived: {backup}" in reset.output.splitlines()
    _, manifest = new_run(tmp_path, reset)
    assert load_store(state).last_transition("AUTO-01").run_id == manifest["run_id"]


def test_at_re_decides_the_stored_run(tmp_path, smoke_runs):
    result = workflow(tmp_path, "simulated", "--from-traces", smoke_runs["rules"], "--at", "0.5")
    assert result.exit_code == 0, result.output
    trace_file, _ = new_run(tmp_path, result)
    assert {t.thresholds.version for t in read_traces(trace_file)} == {"v0.1+at0.5"}


def test_reset_state_with_a_bad_from_traces_leaves_the_state_file_in_place(tmp_path, smoke_runs):
    """M1: --reset-state must not archive the state file until the run's inputs are known good.
    A --from-traces file that doesn't pair with the dataset (wrong case ids) is a usage error;
    it must fail before anything is archived, not after."""
    first = workflow(tmp_path, "simulated", "--from-traces", smoke_runs["groundtruth"])
    assert first.exit_code == 0, first.output
    state = tmp_path / "state" / "case-status.json"
    before = state.read_bytes()
    bad_from_traces = REPO / "evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz"
    result = workflow(tmp_path, "simulated", "--from-traces", bad_from_traces, "--reset-state")
    assert result.exit_code == 2, result.output
    assert "--from-traces" in result.output
    assert "State archived" not in result.output
    assert state.exists() and state.read_bytes() == before
    assert not list((tmp_path / "state").glob("case-status.json.bak-*"))


def test_reset_state_twice_in_the_same_second_picks_a_unique_archive_name(
    tmp_path, smoke_runs, monkeypatch
):
    """N1: reset_state's archive name is <state>.bak-<UTC timestamp>, one-second resolution. Two
    --reset-state runs that land in the same second used to raise StatusStoreError only after
    that run's traces (and, live, its spend) were already written. It must now pick a unique
    suffix instead, so a run that already happened is never discarded for nothing."""
    fixed = datetime(2026, 9, 27, 5, 0, 0, tzinfo=UTC)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    monkeypatch.setattr(status_module, "datetime", _FixedDatetime)
    first = workflow(tmp_path, "simulated", "--from-traces", smoke_runs["groundtruth"])
    assert first.exit_code == 0, first.output
    second = workflow(tmp_path, "simulated", "--from-traces", smoke_runs["rules"], "--reset-state")
    assert second.exit_code == 0, second.output
    third = workflow(
        tmp_path, "simulated", "--from-traces", smoke_runs["groundtruth"], "--reset-state"
    )
    assert third.exit_code == 0, third.output
    backups = sorted(p.name for p in (tmp_path / "state").glob("case-status.json.bak-*"))
    assert backups == [
        "case-status.json.bak-20260927T050000Z",
        "case-status.json.bak-20260927T050000Z-1",
    ]


# ---- shadow ----


def test_shadow_uses_the_handoff_wording_and_never_touches_the_state(tmp_path, smoke_runs):
    sim = workflow(tmp_path, "simulated", "--from-traces", smoke_runs["groundtruth"])
    assert sim.exit_code == 0, sim.output
    _, sim_manifest = new_run(tmp_path, sim)
    state = tmp_path / "state" / "case-status.json"
    digest = state_digest(state)
    result = workflow(tmp_path, "shadow", "--from-traces", smoke_runs["rules"])
    assert result.exit_code == 0, result.output
    assert state_digest(state) == digest
    trace_file, manifest = new_run(tmp_path, result)
    traces = read_traces(trace_file)
    assert {t.mode for t in traces} == {"shadow"}
    assert (manifest["mode"], manifest["source_run_id"]) == ("shadow", smoke_runs["rules"].stem)
    store = load_store(state)
    lines = result.output.splitlines()
    for t in traces:
        current = f" (current status: {store.status_of(t.case_id)} by {sim_manifest['run_id']})"
        assert PROPOSAL[t.action].format(t.case_id) + current in lines
    assert lines[11] == (
        f"SHADOW RUN {manifest['run_id']}: 10 proposals recorded; case state unchanged (verified)."
    )


def test_shadow_without_a_state_file_has_no_status_suffix_and_creates_nothing(tmp_path, smoke_runs):
    result = workflow(tmp_path, "shadow", "--from-traces", smoke_runs["rules"])
    assert result.exit_code == 0, result.output
    assert not (tmp_path / "state").exists()
    trace_file, _ = new_run(tmp_path, result)
    for t in read_traces(trace_file):
        assert PROPOSAL[t.action].format(t.case_id) in result.output.splitlines()
    assert "current status" not in result.output


def test_a_state_change_during_a_shadow_run_is_a_shadow_violation(
    tmp_path, smoke_runs, monkeypatch
):
    state = tmp_path / "state" / "case-status.json"
    assert (
        workflow(tmp_path, "simulated", "--from-traces", smoke_runs["groundtruth"]).exit_code == 0
    )

    def tampering_replay_run(*args, **kwargs):
        state.write_text(state.read_text() + " ")
        return real_replay_run(*args, **kwargs)

    monkeypatch.setattr(cli_module, "replay_run", tampering_replay_run)
    result = workflow(tmp_path, "shadow", "--from-traces", smoke_runs["rules"])
    assert result.exit_code == 3
    assert "SHADOW VIOLATION" in result.output
    assert "Would " not in result.output
    assert "unchanged (verified)" not in result.output


# ---- flags ----


@pytest.mark.parametrize(
    "args,message",
    [
        (["--from-traces", "{gt}"], "--from-traces needs --workflow"),
        (["--state", "s.json"], "--state needs --workflow"),
        (["--workflow", "shadow", "--at", "0.9"], "--at needs --from-traces"),
        (["--workflow", "shadow", "--from-traces", "{gt}", "--at", "0"], "--at must be in (0, 1]"),
        (
            ["--workflow", "shadow", "--from-traces", "{gt}", "--provider", "rules"],
            "--provider cannot be combined with --from-traces",
        ),
        (
            ["--workflow", "shadow", "--from-traces", "{gt}", "--policy", "v0.1"],
            "--policy cannot be combined with --from-traces",
        ),
        (
            ["--workflow", "shadow", "--from-traces", "{gt}", "--reset-state"],
            "--reset-state applies only to --workflow simulated",
        ),
    ],
)
def test_usage_errors_exit_2_before_anything_is_written(tmp_path, smoke_runs, args, message):
    args = [a.replace("{gt}", str(smoke_runs["groundtruth"])) for a in args]
    result = invoke(tmp_path, "run", "--dataset", SMOKE, "--traces-dir", tmp_path / "traces", *args)
    assert result.exit_code == 2
    assert message in result.output
    assert not (tmp_path / "traces").exists()


def test_from_traces_over_another_dataset_is_an_input_error(tmp_path, smoke_runs):
    gold_jev = REPO / "evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz"
    result = workflow(tmp_path, "shadow", "--from-traces", gold_jev)
    assert result.exit_code == 2
    assert "--from-traces" in result.output
    assert not (tmp_path / "traces").exists()


# ---- the live provider path (fakes only) ----


class FakeTypeSafe:
    """Stands in for AsyncTypeSafeClient: every case gets the AUTO-01 fixture."""

    calls = 0

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def system_one(self, state, questions, *, model=None, **kwargs):
        FakeTypeSafe.calls += 1
        return SystemOneResponse.model_validate(json.loads(JEV_FIXTURE.read_text()))


class FakeAnthropic:
    """Stands in for AsyncAnthropic: every case gets the same well-formed sync reply."""

    def __init__(self, **kwargs):
        self.messages = FakeMessages(message(), batches=FakeBatches([]))

    def with_options(self, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None


@pytest.fixture
def fake_jev(monkeypatch):
    FakeTypeSafe.calls = 0
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", FakeTypeSafe)
    return FakeTypeSafe


def test_a_live_shadow_run_goes_through_the_provider(tmp_path, fake_jev):
    result = workflow(tmp_path, "shadow", "--provider", "jev")
    assert result.exit_code == 0, result.output
    assert fake_jev.calls == 10
    trace_file, manifest = new_run(tmp_path, result)
    assert {(t.mode, t.provider) for t in read_traces(trace_file)} == {("shadow", "jev")}
    assert (manifest["mode"], manifest["source_run_id"]) == ("shadow", None)
    assert "SHADOW: Would " in result.output
    assert not (tmp_path / "state").exists()


def test_a_live_run_keeps_the_jev_key_guard(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    result = workflow(tmp_path, "shadow", "--provider", "jev")
    assert result.exit_code == 2
    assert "TYPESAFE_API_KEY is not set" in result.output
    assert not (tmp_path / "traces").exists()


def test_a_simulated_conflict_is_found_before_the_provider_is_called(
    tmp_path, smoke_runs, fake_jev
):
    assert workflow(tmp_path, "simulated", "--from-traces", smoke_runs["rules"]).exit_code == 0
    result = workflow(tmp_path, "simulated", "--provider", "jev")
    assert result.exit_code == 2
    assert "already moved past RECEIVED" in result.output
    assert fake_jev.calls == 0


def test_a_live_claude_simulated_run_uses_the_budget_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncAnthropic", FakeAnthropic)
    ledger = tmp_path / "spend.json"
    result = workflow(tmp_path, "simulated", "--provider", "claude", "--ledger", ledger)
    assert result.exit_code == 0, result.output
    assert "Claude budget: spent $0.0000, projected $2.5000 for 10 cases (sync)" in result.output
    [entry] = json.loads(ledger.read_text())["entries"]
    assert entry["status"] == "settled"
    trace_file, manifest = new_run(tmp_path, result)
    assert entry["run_id"] == manifest["run_id"]
    assert {t.mode for t in read_traces(trace_file)} == {"simulated"}
    assert len(load_store(tmp_path / "state" / "case-status.json").root) == 10


def test_a_live_claude_run_without_a_key_exits_2_before_the_ledger(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ledger = tmp_path / "spend.json"
    result = workflow(tmp_path, "shadow", "--provider", "claude", "--ledger", ledger)
    assert result.exit_code == 2
    assert "ANTHROPIC_API_KEY is not set" in result.output
    assert not ledger.exists()
