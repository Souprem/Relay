"""relay replay, offline: smoke traces from the groundtruth and rules providers, plus fakes for
the live candidates. Never touches the network."""

import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner
from typesafe_sdk import SystemOneResponse

import relay.cases.policies as policies_module
import relay.cli as cli_module
import relay.evaluation.tracediff as tracediff
import relay.workflow.thresholds as thresholds_module
from relay.cases.loader import load_case
from relay.cases.policies import load_policy
from relay.cli import app
from relay.evaluation.budget import load_ledger
from relay.evaluation.labels import expected_action
from relay.evaluation.runner import policy_text_hash
from relay.evaluation.tracediff import (
    TraceDiff,
    diff_traces,
    original_label,
    policy_replay_label,
    replay_trace,
)
from relay.reporting import DRIFT_LINE, REPRODUCED_LINE
from relay.traces.store import read_traces
from relay.workflow.thresholds import THRESHOLDS_V0_1, override_auto_process
from tests.claude_fakes import FakeBatches, FakeMessages, message
from tests.factories import make_bundle

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
JEV_FIXTURE = REPO / "tests" / "fixtures" / "jev" / "auto01_response.json"
runner = CliRunner()


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--env-file", str(tmp_path / "missing.env"), *args])


@pytest.fixture(scope="module")
def smoke_runs(tmp_path_factory):
    """One groundtruth and one rules trace file over the smoke dataset, made once."""
    root = tmp_path_factory.mktemp("smoke-runs")
    files = {}
    for provider in ("groundtruth", "rules"):
        out = root / provider
        result = invoke(
            root,
            "run",
            "--dataset",
            str(SMOKE),
            "--provider",
            provider,
            "--traces-dir",
            str(out / "traces"),
            "--reports-dir",
            str(out / "reports"),
        )
        assert result.exit_code == 0, result.output
        [files[provider]] = (out / "traces").glob("*.jsonl")
    return files


def replay(tmp_path, case_id, traces, *extra, dataset=SMOKE):
    return invoke(
        tmp_path, "replay", case_id, "--traces", str(traces), "--dataset", str(dataset), *extra
    )


def as_diff(result) -> TraceDiff:
    return TraceDiff.model_validate_json(result.stdout)


def row(diff, question_id):
    return next(d for d in diff.decisions if d.question_id == question_id)


# ---- reproduce ----


def test_reproduce_is_the_default_and_reproduces(tmp_path, smoke_runs):
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"])
    assert result.exit_code == 0, result.output
    assert result.output.count(REPRODUCED_LINE) == 2
    assert "\nORIGINAL run_" in result.output
    assert "CANDIDATE reproduce: stored decisions, current engine, original policy" in result.output
    assert "EXPECTED (evaluation-only): AUTO_PROCESS" in result.output
    assert "ACTION UNCHANGED: AUTO_PROCESS" in result.output


def test_an_engine_change_is_engine_drift_with_exit_3(tmp_path, smoke_runs, monkeypatch):
    real = tracediff.determine_action

    def drifted(*args, **kwargs):
        outcome = real(*args, **kwargs)
        return outcome.model_copy(update={"reasons": [*outcome.reasons, "a new reason"]})

    monkeypatch.setattr(tracediff, "determine_action", drifted)
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"])
    assert result.exit_code == 3, result.output
    assert DRIFT_LINE in result.output
    assert REPRODUCED_LINE not in result.output
    json_result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], "--json")
    assert json_result.exit_code == 3
    assert as_diff(json_result).identical is False


# ---- policy replay ----


def test_at_shows_the_crossed_threshold(tmp_path, smoke_runs):
    # rules on AUTO-03: step_therapy and documentation_complete are 0.5, below 0.95.
    result = replay(tmp_path, "AUTO-03", smoke_runs["rules"], "--at", "0.5")
    assert result.exit_code == 0, result.output
    assert (
        "CANDIDATE policy replay: STORED DECISIONS under policy immunara-v0.1 (v0.1), "
        "auto_process=0.5, thresholds v0.1+at0.5 — judgments were made against the original "
        "policy's questions"
    ) in result.output
    assert "  auto_process  0.95 → 0.5" in result.output
    assert "ACTION UNCHANGED: REQUEST_INFO" in result.output  # the documentation gate still fires
    diff = as_diff(replay(tmp_path, "AUTO-03", smoke_runs["rules"], "--at", "0.5", "--json"))
    assert diff.thresholds == {"auto_process": (0.95, 0.5)}
    assert row(diff, "step_therapy").crossed == ["auto_process"]
    assert row(diff, "documentation_complete").crossed == ["auto_process"]
    assert row(diff, "diagnosis_support").crossed == []


def test_latest_policy_and_explicit_policy_resolve_today_to_immunara_v0_1(tmp_path, smoke_runs):
    for flags in (["--latest-policy"], ["--policy", "immunara-v0.1"]):
        result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], *flags)
        assert result.exit_code == 0, result.output
        assert (
            "STORED DECISIONS under policy immunara-v0.1 (v0.1), thresholds v0.1 — judgments"
        ) in result.output
        assert "ACTION UNCHANGED: AUTO_PROCESS" in result.output
        assert REPRODUCED_LINE not in result.output  # policy replay never claims reproduction


def test_an_unknown_policy_is_exit_2(tmp_path, smoke_runs):
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], "--policy", "nope-v1")
    assert result.exit_code == 2
    assert "unknown policy 'nope-v1'" in result.output


# ---- candidate traces ----


def test_candidate_traces_classify_the_change(tmp_path, smoke_runs):
    # AUTO-03: groundtruth AUTO_PROCESS (correct), rules REQUEST_INFO (wrong-safe).
    result = replay(
        tmp_path, "AUTO-03", smoke_runs["groundtruth"], "--candidate-traces", smoke_runs["rules"]
    )
    assert result.exit_code == 0, result.output
    assert "CANDIDATE candidate trace run_" in result.output
    assert "· rules rules-v0.1" in result.output
    assert "ACTION CHANGED: AUTO_PROCESS → REQUEST_INFO (regressed)" in result.output
    reverse = replay(
        tmp_path, "AUTO-03", smoke_runs["rules"], "--candidate-traces", smoke_runs["groundtruth"]
    )
    assert reverse.exit_code == 0, reverse.output
    assert "ACTION CHANGED: REQUEST_INFO → AUTO_PROCESS (improved)" in reverse.output


def test_a_newly_unsafe_candidate_exits_4_and_still_prints_everything(tmp_path, smoke_runs):
    # REV-02 is expected HUMAN_REVIEW; confident judgments on every question auto-process it.
    [original] = [t for t in read_traces(smoke_runs["groundtruth"]) if t.case_id == "REV-02"]
    case = load_case(SMOKE / "REV-02")
    confident = original.model_copy(
        update={"decisions": make_bundle("REV-02"), "run_id": "run_confident"}
    )
    unsafe = replay_trace(
        confident, case, policy=load_policy("immunara-v0.1"), thresholds=original.thresholds
    )
    candidate_file = tmp_path / "unsafe.jsonl"
    candidate_file.write_text(unsafe.model_dump_json() + "\n", encoding="utf-8")
    result = replay(
        tmp_path, "REV-02", smoke_runs["groundtruth"], "--candidate-traces", candidate_file
    )
    assert result.exit_code == 4, result.output
    assert "ACTION CHANGED: HUMAN_REVIEW → AUTO_PROCESS (NEWLY UNSAFE)" in result.output
    assert "  CANDIDATE AUTO_PROCESS (UNSAFE)" in result.output
    assert "DECISION" in result.output and "GATES" in result.output
    json_result = replay(
        tmp_path,
        "REV-02",
        smoke_runs["groundtruth"],
        "--candidate-traces",
        candidate_file,
        "--json",
    )
    assert json_result.exit_code == 4
    assert as_diff(json_result).newly_unsafe is True


def test_a_candidate_made_on_different_inputs_is_exit_2(tmp_path, smoke_runs):
    [trace] = [t for t in read_traces(smoke_runs["rules"]) if t.case_id == "AUTO-01"]
    other = tmp_path / "other.jsonl"
    other.write_text(
        trace.model_copy(update={"case_content_hash": "sha256:other"}).model_dump_json() + "\n",
        encoding="utf-8",
    )
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], "--candidate-traces", other)
    assert result.exit_code == 2
    assert "different case inputs" in result.output


# ---- input errors ----


def test_changed_case_inputs_are_refused_with_both_hashes(tmp_path, smoke_runs):
    edited = tmp_path / "smoke-edited"
    shutil.copytree(SMOKE, edited)
    note = edited / "AUTO-01" / "documents" / "physician_note.txt"
    note.write_text(note.read_text(encoding="utf-8") + "\nAn added line.\n", encoding="utf-8")
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], dataset=edited)
    assert result.exit_code == 2
    assert "the case inputs changed since run" in result.output
    [trace] = [t for t in read_traces(smoke_runs["groundtruth"]) if t.case_id == "AUTO-01"]
    assert trace.case_content_hash in result.output


def test_a_case_with_no_trace_or_two_traces_is_exit_2(tmp_path, smoke_runs):
    [trace] = [t for t in read_traces(smoke_runs["groundtruth"]) if t.case_id == "AUTO-01"]
    doubled = tmp_path / "doubled.jsonl"
    doubled.write_text((trace.model_dump_json() + "\n") * 2, encoding="utf-8")
    result = replay(tmp_path, "AUTO-01", doubled)
    assert result.exit_code == 2
    assert "expected exactly one trace for AUTO-01, found 2" in result.output
    result = replay(tmp_path, "NOPE-01", smoke_runs["groundtruth"])
    assert result.exit_code == 2
    assert "expected exactly one trace for NOPE-01, found 0" in result.output


@pytest.mark.parametrize(
    "flags,message",
    [
        (["--at", "0.9", "--candidate-traces", "RULES"], "choose one candidate source"),
        (["--policy", "immunara-v0.1", "--candidate-traces", "RULES"], "choose one"),
        (["--provider", "rules", "--at", "0.9"], "choose one candidate source"),
        (["--provider", "rules", "--candidate-traces", "RULES"], "choose one candidate source"),
        (["--policy", "immunara-v0.1", "--latest-policy"], "mutually exclusive"),
        (["--questions", "q-v0.2"], "applies only to a live candidate"),
        (["--mode", "sync"], "applies only to a live candidate"),
        (["--provider", "claude", "--mode", "batch"], "--mode batch is not supported"),
        (["--provider", "rules", "--budget-usd", "1"], "applies only to --provider claude"),
        (["--provider", "rules", "--questions", "q-v0.2"], "has no question set"),
    ],
)
def test_conflicting_flags_are_exit_2(tmp_path, smoke_runs, flags, message):
    flags = [str(smoke_runs["rules"]) if f == "RULES" else f for f in flags]
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], *flags)
    assert result.exit_code == 2, result.output
    assert message in result.output


@pytest.mark.parametrize("at", ["0", "0.0"])
def test_at_zero_is_exit_2(tmp_path, smoke_runs, at):
    """I3: --at <= 0 makes a false requirement (x >= 0) pass for every case, so the expected
    action itself becomes AUTO_PROCESS and unsafe automation is marked "correct". Reject it
    outright rather than silently mislabel every case."""
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], "--at", at)
    assert result.exit_code == 2, result.output
    assert "--at must be > 0" in result.output


def test_at_negative_is_exit_2(tmp_path, smoke_runs):
    """A negative --at is already refused by typer's own range check (min=0.0); confirm it is
    still a usage error even though the message differs from the explicit `at <= 0` check."""
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], "--at", "-0.5")
    assert result.exit_code == 2, result.output


# ---- JSON and keyless operation ----


def test_json_prints_only_the_trace_diff(tmp_path, smoke_runs):
    result = replay(tmp_path, "AUTO-03", smoke_runs["rules"], "--at", "0.5", "--json")
    assert result.exit_code == 0, result.output
    assert result.stdout.lstrip().startswith("{")
    diff = as_diff(result)
    assert diff.case_id == "AUTO-03"
    assert json.loads(result.stdout)["candidate_label"].startswith("policy replay: ")


class NoNetworkClient:
    def __init__(self, *args, **kwargs):
        raise AssertionError("replay constructed a network client")


@pytest.mark.parametrize(
    "flags",
    [[], ["--latest-policy"], ["--at", "0.9"], ["--candidate-traces", "RULES"]],
    ids=["reproduce", "latest-policy", "at", "candidate-traces"],
)
def test_offline_modes_need_no_key_and_build_no_client(tmp_path, smoke_runs, monkeypatch, flags):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", NoNetworkClient)
    monkeypatch.setattr(cli_module, "AsyncAnthropic", NoNetworkClient)
    flags = [str(smoke_runs["rules"]) if f == "RULES" else f for f in flags]
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], *flags)
    assert result.exit_code == 0, result.output


# ---- live candidates (fakes only) ----


class FakeTypeSafe:
    """Stands in for AsyncTypeSafeClient; answers with the AUTO-01 fixture."""

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def system_one(self, state, questions, *, model=None, **kwargs):
        return SystemOneResponse.model_validate(json.loads(JEV_FIXTURE.read_text()))


class FakeAnthropic:
    """Stands in for anthropic.AsyncAnthropic; one well-formed sync reply."""

    def __init__(self, **kwargs):
        self.messages = FakeMessages(message(), batches=FakeBatches([]))

    def with_options(self, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None


def live_trace(tmp_path):
    [trace_file] = (tmp_path / "live").glob("*.jsonl")
    [trace] = read_traces(trace_file)
    assert trace_file.with_suffix(".manifest.json").exists()
    return trace


def test_live_rules_candidate_is_an_ordinary_one_case_run(tmp_path, smoke_runs):
    result = replay(
        tmp_path,
        "AUTO-03",
        smoke_runs["groundtruth"],
        "--provider",
        "rules",
        "--traces-dir",
        str(tmp_path / "live"),
    )
    assert result.exit_code == 0, result.output
    trace = live_trace(tmp_path)
    assert f"Live candidate run {trace.run_id}: " in result.output
    assert f"CANDIDATE live run {trace.run_id} · rules rules-v0.1 on frozen inputs" in (
        result.output
    )
    assert "ACTION CHANGED: AUTO_PROCESS → REQUEST_INFO (regressed)" in result.output


def test_live_jev_candidate_uses_the_fake_client(tmp_path, smoke_runs, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", FakeTypeSafe)
    result = replay(
        tmp_path,
        "AUTO-01",
        smoke_runs["groundtruth"],
        "--provider",
        "jev",
        "--question-set",
        "q-v0.2",
        "--traces-dir",
        str(tmp_path / "live"),
    )
    assert result.exit_code == 0, result.output
    trace = live_trace(tmp_path)
    assert (trace.provider, trace.question_set_version) == ("jev", "q-v0.2")
    assert f"CANDIDATE live run {trace.run_id} · jev q-v0.2 on frozen inputs" in result.output


def test_live_jev_without_a_key_is_exit_2_before_any_run(tmp_path, smoke_runs, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", NoNetworkClient)
    result = replay(
        tmp_path,
        "AUTO-01",
        smoke_runs["groundtruth"],
        "--provider",
        "jev",
        "--traces-dir",
        str(tmp_path / "live"),
    )
    assert result.exit_code == 2
    assert "TYPESAFE_API_KEY is not set" in result.output
    assert not (tmp_path / "live").exists()


def test_live_claude_candidate_goes_through_the_budget_guard(tmp_path, smoke_runs, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncAnthropic", FakeAnthropic)
    ledger = tmp_path / "spend.json"
    result = replay(
        tmp_path,
        "AUTO-01",
        smoke_runs["groundtruth"],
        "--provider",
        "claude",
        "--ledger",
        str(ledger),
        "--traces-dir",
        str(tmp_path / "live"),
    )
    assert result.exit_code == 0, result.output
    assert "Claude budget:" in result.output and "(sync)" in result.output
    trace = live_trace(tmp_path)
    assert trace.provider == "claude"
    [entry] = load_ledger(ledger).entries
    assert (entry.mode, entry.cases, entry.status) == ("sync", 1, "settled")
    assert entry.cost_usd == Decimal("0.0219")


def test_live_claude_over_budget_is_exit_2_and_writes_nothing(tmp_path, smoke_runs, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncAnthropic", FakeAnthropic)
    result = replay(
        tmp_path,
        "AUTO-01",
        smoke_runs["groundtruth"],
        "--provider",
        "claude",
        "--budget-usd",
        "0.1",
        "--ledger",
        str(tmp_path / "spend.json"),
        "--traces-dir",
        str(tmp_path / "live"),
    )
    assert result.exit_code == 2
    assert not (tmp_path / "live").exists()
    assert not (tmp_path / "spend.json").exists()


def test_live_json_keeps_stdout_pure(tmp_path, smoke_runs, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncAnthropic", FakeAnthropic)
    result = replay(
        tmp_path,
        "AUTO-01",
        smoke_runs["groundtruth"],
        "--provider",
        "claude",
        "--ledger",
        str(tmp_path / "spend.json"),
        "--traces-dir",
        str(tmp_path / "live"),
        "--json",
    )
    assert result.exit_code == 0, result.output
    diff = as_diff(result)
    assert diff.candidate_label.startswith("live run ")
    assert "Claude budget:" in result.stderr


# ---- F1: a policy replay onto another policy version brings that version's thresholds ----


def register_v0_2(monkeypatch, *, with_thresholds: bool = True):
    spec = dict(policies_module._POLICIES["immunara-v0.1"], version="v0.2")
    monkeypatch.setitem(policies_module._POLICIES, "immunara-v0.2", spec)
    if with_thresholds:
        v2 = THRESHOLDS_V0_1.model_copy(update={"version": "v0.2", "auto_process": 0.9})
        monkeypatch.setitem(thresholds_module._BY_VERSION, "v0.2", v2)


def test_policy_replay_onto_another_version_uses_its_thresholds(tmp_path, smoke_runs, monkeypatch):
    register_v0_2(monkeypatch)
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], "--latest-policy")
    assert result.exit_code == 0, result.output
    assert "under policy immunara-v0.2 (v0.2), thresholds v0.2 — judgments" in result.output
    assert "  auto_process  0.95 → 0.9" in result.output
    at = replay(
        tmp_path, "AUTO-01", smoke_runs["groundtruth"], "--policy", "immunara-v0.2", "--at", "0.8"
    )
    assert at.exit_code == 0, at.output
    assert "auto_process=0.8, thresholds v0.2+at0.8 — judgments" in at.output


def test_policy_replay_onto_a_version_without_thresholds_is_exit_2(
    tmp_path, smoke_runs, monkeypatch
):
    register_v0_2(monkeypatch, with_thresholds=False)
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], "--policy", "immunara-v0.2")
    assert result.exit_code == 2, result.output
    assert "unknown thresholds version 'v0.2'" in result.output


def test_replay_json_matches_a_hand_built_diff(tmp_path, smoke_runs):
    """F2: routing `relay replay` through diff_case changed nothing: its JSON equals the diff
    built by hand from diff_traces, as replay built it before."""
    [original] = [t for t in read_traces(smoke_runs["rules"]) if t.case_id == "AUTO-03"]
    case = load_case(SMOKE / "AUTO-03")
    policy = load_policy("immunara-v0.1")
    thresholds = override_auto_process(original.thresholds, 0.5)
    candidate = replay_trace(original, case, policy=policy, thresholds=thresholds)
    by_hand = diff_traces(
        original,
        candidate,
        expected_original=expected_action(case, policy, original.thresholds),
        expected_candidate=expected_action(case, policy, thresholds),
        original_label=original_label(original),
        candidate_label=policy_replay_label(policy, thresholds, 0.5),
        current_policy_text_hash=policy_text_hash(policy),
    )
    result = replay(tmp_path, "AUTO-03", smoke_runs["rules"], "--at", "0.5", "--json")
    assert result.exit_code == 0, result.output
    assert as_diff(result) == by_hand
