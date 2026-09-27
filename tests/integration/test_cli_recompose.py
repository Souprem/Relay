"""relay recompose: stale and aware simulated runs from one stored Jev run (fake client)."""

import json

import pytest
from typer.testing import CliRunner
from typesafe_sdk import SystemOneResponse

import relay.cli as cli_module
from relay.cli import app
from relay.decisions.base import DecisionId
from relay.generation.generator import generate_dataset
from relay.traces.models import RunManifest
from relay.traces.store import read_traces
from tests.jev_fakes import q_v0_3_payload, raw_date

runner = CliRunner()


def old_course_payload():
    """Methotrexate 2025-01-13 -> 2025-06-02 (140 days, ended well over a year before every
    gen-v0.3 as-of date), inadequate response 0.97, not interrupted."""
    return q_v0_3_payload(
        **raw_date("mtx_start", "January", "13", "2025"),
        **raw_date("mtx_end", "June", "2", "2025"),
    )


class FakeAsyncClient:
    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def system_one(self, state, questions, *, model=None, **kwargs):
        return SystemOneResponse.model_validate(old_course_payload())


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--env-file", str(tmp_path / "missing.env"), *args])


@pytest.fixture
def shift_run(tmp_path, monkeypatch):
    """An 8-case gen-v0.3 dataset under immunara-v0.2 and one fake q-v0.3 Jev run on it."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", FakeAsyncClient)
    dataset = tmp_path / "shift"
    generate_dataset(
        8, 5, "gen-shift", dataset, generator_version="gen-v0.3", policy_version="v0.2"
    )
    result = invoke(
        tmp_path,
        "eval",
        "--dataset",
        str(dataset),
        "--provider",
        "jev",
        "--questions",
        "q-v0.3",
        "--policy",
        "v0.2",
        "--traces-dir",
        str(tmp_path / "traces"),
        "--reports-dir",
        str(tmp_path / "reports"),
        "--results-dir",
        str(tmp_path / "results"),
    )
    assert result.exit_code == 0, result.output
    [trace_file] = (tmp_path / "traces").glob("*.jsonl")
    return dataset, trace_file


def recompose(tmp_path, dataset, trace_file, policy, name):
    return invoke(
        tmp_path,
        "recompose",
        "--traces",
        str(trace_file),
        "--dataset",
        str(dataset),
        "--policy",
        policy,
        "--out",
        str(tmp_path / name),
    )


def step(trace):
    return trace.decisions.get(DecisionId.STEP_THERAPY).p_yes


def test_stale_and_aware_from_one_run(tmp_path, shift_run):
    dataset, trace_file = shift_run
    source = read_traces(trace_file)
    stale_result = recompose(tmp_path, dataset, trace_file, "immunara-v0.1", "stale")
    aware_result = recompose(tmp_path, dataset, trace_file, "immunara-v0.2", "aware")
    assert stale_result.exit_code == 0, stale_result.output
    assert aware_result.exit_code == 0, aware_result.output
    assert "under policy immunara-v0.1 (v0.1), thresholds v0.1: step_therapy changed on 8" in (
        stale_result.output
    )
    assert "step_therapy changed on 0 case(s), action changed on 0 case(s)" in (aware_result.output)
    stale = read_traces(tmp_path / "stale" / "traces.jsonl.gz")
    aware = read_traces(tmp_path / "aware" / "traces.jsonl.gz")
    assert [t.case_id for t in stale] == [t.case_id for t in source]
    assert {step(t) for t in aware} == {0.0}
    assert all(step(t) == pytest.approx(0.98 * 0.97) for t in stale)
    assert [t.decisions for t in aware] == [t.decisions for t in source]
    assert {(t.policy_id, t.thresholds.version, t.mode) for t in stale} == {
        ("immunara-v0.1", "v0.1", "simulated")
    }
    assert {(t.policy_id, t.thresholds.version) for t in aware} == {("immunara-v0.2", "v0.2")}
    assert {t.replay_of for t in stale} == {t.trace_id for t in source}
    assert len({t.run_id for t in stale}) == 1 and stale[0].run_id != source[0].run_id


def test_the_manifest_records_mode_source_and_policy(tmp_path, shift_run):
    dataset, trace_file = shift_run
    assert recompose(tmp_path, dataset, trace_file, "immunara-v0.1", "stale").exit_code == 0
    raw = json.loads((tmp_path / "stale" / "run-manifest.json").read_text())
    manifest = RunManifest.model_validate(raw)
    source = read_traces(trace_file)
    assert (manifest.mode, manifest.source_run_id) == ("simulated", source[0].run_id)
    assert (manifest.policy_version, manifest.question_set_version) == ("v0.1", "q-v0.3")
    assert raw["policy_id"] == "immunara-v0.1"
    assert raw["thresholds"]["version"] == "v0.1"
    assert manifest.trace_file == str(tmp_path / "stale" / "traces.jsonl.gz")


def test_recomposed_runs_score_and_gate_offline(tmp_path, shift_run):
    dataset, trace_file = shift_run
    recompose(tmp_path, dataset, trace_file, "immunara-v0.1", "stale")
    recompose(tmp_path, dataset, trace_file, "immunara-v0.2", "aware")
    scored = invoke(
        tmp_path,
        "eval",
        "--dataset",
        str(dataset),
        "--traces",
        str(tmp_path / "stale" / "traces.jsonl.gz"),
        "--results-dir",
        str(tmp_path / "results"),
    )
    assert scored.exit_code == 0, scored.output
    gate = invoke(
        tmp_path,
        "regression",
        "--dataset",
        str(dataset),
        "--baseline",
        str(tmp_path / "stale" / "traces.jsonl.gz"),
        "--candidate-traces",
        str(tmp_path / "aware" / "traces.jsonl.gz"),
    )
    assert gate.exit_code == 0, gate.output  # aware never automates: nothing newly unsafe


def test_refusals_are_exit_2(tmp_path, shift_run):
    dataset, trace_file = shift_run
    unknown = recompose(tmp_path, dataset, trace_file, "nope-v1", "x")
    assert unknown.exit_code == 2 and "unknown policy 'nope-v1'" in unknown.output
    assert recompose(tmp_path, dataset, trace_file, "immunara-v0.1", "stale").exit_code == 0
    again = recompose(tmp_path, dataset, trace_file, "immunara-v0.1", "stale")
    assert again.exit_code == 2 and "is not empty" in again.output
    rules = invoke(
        tmp_path,
        "eval",
        "--dataset",
        str(dataset),
        "--provider",
        "rules",
        "--policy",
        "v0.2",
        "--traces-dir",
        str(tmp_path / "rules"),
        "--reports-dir",
        str(tmp_path / "reports"),
        "--results-dir",
        str(tmp_path / "results"),
    )
    assert rules.exit_code == 0, rules.output
    [rules_file] = (tmp_path / "rules").glob("*.jsonl")
    refused = recompose(tmp_path, dataset, rules_file, "immunara-v0.1", "rules-out")
    assert refused.exit_code == 2 and "only Jev bundles can be recomposed" in refused.output
    assert not (tmp_path / "rules-out").exists()


def test_a_dataset_that_does_not_match_the_run_is_exit_2(tmp_path, shift_run):
    _, trace_file = shift_run
    other = tmp_path / "other"
    generate_dataset(4, 6, "gen-other", other, generator_version="gen-v0.3", policy_version="v0.2")
    result = recompose(tmp_path, other, trace_file, "immunara-v0.1", "x")
    assert result.exit_code == 2
    assert "trace for unknown case" in result.output
