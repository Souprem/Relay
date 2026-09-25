"""relay run/eval --questions, with a fake TypeSafe client (no network, no real key)."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner
from typesafe_sdk import SystemOneResponse

import relay.cli as cli_module
from relay.cases.policies import load_policy
from relay.cli import app
from relay.decisions.questions import DEFAULT_QUESTION_SET_VERSION, question_set_hash
from relay.traces.store import read_traces

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
FIXTURE = REPO / "tests" / "fixtures" / "jev" / "auto01_response.json"
runner = CliRunner()


class FakeAsyncClient:
    """Stands in for AsyncTypeSafeClient and answers every case with the AUTO-01 fixture."""

    sent: list[dict] = []

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def system_one(self, state, questions, *, model=None, **kwargs):
        FakeAsyncClient.sent.append(questions)
        return SystemOneResponse.model_validate(json.loads(FIXTURE.read_text()))


@pytest.fixture
def fake_jev(monkeypatch):
    FakeAsyncClient.sent = []
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", FakeAsyncClient)
    return FakeAsyncClient


def run_jev(tmp_path, *extra):
    return runner.invoke(
        app,
        [
            "--env-file",
            str(tmp_path / "missing.env"),
            "run",
            "--dataset",
            str(SMOKE),
            "--provider",
            "jev",
            "--traces-dir",
            str(tmp_path / "traces"),
            "--reports-dir",
            str(tmp_path / "reports"),
            *extra,
        ],
    )


@pytest.mark.parametrize("version", ["q-v0.1", "q-v0.2"])
def test_run_uses_the_requested_question_set(tmp_path, fake_jev, version):
    result = run_jev(tmp_path, "--questions", version)
    assert result.exit_code == 0, result.output
    [trace_file] = (tmp_path / "traces").glob("*.jsonl")
    traces = read_traces(trace_file)
    assert len(traces) == 10
    expected_hash = question_set_hash(load_policy("immunara-v0.1"), version)
    assert {(t.question_set_version, t.question_set_hash) for t in traces} == {
        (version, expected_hash)
    }
    options = {q["missing_evidence"].criteria["TREATMENT_HISTORY"] for q in fake_jev.sent}
    assert len(options) == 1
    assert ("never took methotrexate" in options.pop()) is (version == "q-v0.2")
    [manifest_file] = (tmp_path / "traces").glob("*.manifest.json")
    manifest = json.loads(manifest_file.read_text())
    assert manifest["question_set_version"] == version  # C4: filled by the CLI run path


def test_run_defaults_to_the_default_question_set(tmp_path, fake_jev):
    result = run_jev(tmp_path)
    assert result.exit_code == 0, result.output
    [trace_file] = (tmp_path / "traces").glob("*.jsonl")
    assert {t.question_set_version for t in read_traces(trace_file)} == {
        DEFAULT_QUESTION_SET_VERSION
    }


def test_unknown_question_set_is_rejected_by_the_cli(tmp_path, fake_jev):
    result = run_jev(tmp_path, "--questions", "q-v9")
    assert result.exit_code == 2
    assert not (tmp_path / "traces").exists()
