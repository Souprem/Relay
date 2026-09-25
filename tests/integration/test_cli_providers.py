"""The CLI's explicit provider factory, per-provider key preflight, and --questions handling."""

import json
from contextlib import AsyncExitStack
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

import relay.cli as cli_module
from relay.cases.loader import load_dataset
from relay.cli import PROVIDER_KEYS, PROVIDER_QUESTION_SETS, ProviderName, app
from relay.decisions.questions import DEFAULT_QUESTION_SET_VERSION, QUESTION_SET_VERSIONS
from relay.decisions.rules_baseline import RULES_VERSION, rules_hash
from relay.reporting import RULES_NOTE
from relay.traces.store import read_traces

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
runner = CliRunner()


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--env-file", str(tmp_path / "missing.env"), *args])


def dirs(tmp_path):
    return [
        "--traces-dir",
        str(tmp_path / "traces"),
        "--reports-dir",
        str(tmp_path / "reports"),
    ]


class FakeAsyncClient:
    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None


def test_env_file_help_text_is_provider_generic():
    """C4: more providers than jev may need a key (ANTHROPIC_API_KEY is coming), so the help
    text should not name TYPESAFE_API_KEY specifically."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "dotenv file with provider API keys" in result.output
    assert "TYPESAFE_API_KEY" not in result.output


def test_every_provider_has_a_key_entry_and_only_jev_needs_one():
    assert set(PROVIDER_KEYS) == set(ProviderName)
    assert {p for p, key in PROVIDER_KEYS.items() if key} == {ProviderName.jev}
    assert PROVIDER_KEYS[ProviderName.jev] == "TYPESAFE_API_KEY"


async def test_every_provider_name_has_an_explicit_factory(monkeypatch):
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", FakeAsyncClient)
    cases = load_dataset(SMOKE)
    async with AsyncExitStack() as stack:
        for name in ProviderName:
            questions = cli_module._resolve_questions(name, None)
            provider = await cli_module._build_provider(name, cases, questions, stack)
            assert provider.name == name.value


def test_rules_eval_on_smoke_needs_no_key(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    result = invoke(
        tmp_path,
        "eval",
        "--dataset",
        str(SMOKE),
        "--provider",
        "rules",
        *dirs(tmp_path),
        "--results-dir",
        str(tmp_path / "results"),
    )
    assert result.exit_code == 0, result.output
    assert RULES_NOTE in result.output
    results = json.loads(next((tmp_path / "results").glob("*.json")).read_text())
    # Pinned in tests/unit/test_rules_datasets.py: 9 of 10 correct (AUTO-03 abstains to
    # REQUEST_INFO), AUTO-01 and AUTO-02 automated, none unsafe.
    assert (results["correct_actions"], results["auto_process_count"]) == (9, 2)
    assert results["unsafe_automation_count"] == 0
    assert results["question_set_versions"] == [RULES_VERSION]
    [trace_file] = (tmp_path / "traces").glob("*.jsonl")
    traces = read_traces(trace_file)
    assert {(t.provider, t.question_set_version, t.question_set_hash) for t in traces} == {
        ("rules", RULES_VERSION, rules_hash())
    }
    [manifest_file] = (tmp_path / "traces").glob("*.manifest.json")
    manifest = json.loads(manifest_file.read_text())
    assert (manifest["provider"], manifest["question_set_version"]) == ("rules", RULES_VERSION)
    report = next((tmp_path / "reports").glob("*.md")).read_text()
    assert RULES_NOTE in report
    assert "**Rules fired:**" in report
    assert "`mtx_never` (physician_note:" in report


@pytest.mark.parametrize("provider", ["rules", "groundtruth"])
def test_explicit_questions_is_rejected_for_providers_without_a_question_set(tmp_path, provider):
    result = invoke(
        tmp_path,
        "run",
        "--dataset",
        str(SMOKE),
        "--provider",
        provider,
        "--questions",
        "q-v0.2",
        *dirs(tmp_path),
    )
    assert result.exit_code == 2
    assert f"the {provider} provider has no question set" in result.output
    assert "providers with one: jev" in result.output
    assert not (tmp_path / "traces").exists()


def test_jev_key_preflight_still_fails_fast_with_an_explicit_question_set(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    result = invoke(
        tmp_path,
        "run",
        "--dataset",
        str(SMOKE),
        "--provider",
        "jev",
        "--questions",
        "q-v0.1",
        *dirs(tmp_path),
    )
    assert result.exit_code == 2
    assert "TYPESAFE_API_KEY" in result.output
    assert not (tmp_path / "traces").exists()


def test_question_sets_are_declared_per_provider():
    assert set(PROVIDER_QUESTION_SETS) == {ProviderName.jev}
    jev = PROVIDER_QUESTION_SETS[ProviderName.jev]
    assert (jev.allowed, jev.default) == (QUESTION_SET_VERSIONS, DEFAULT_QUESTION_SET_VERSION)


def test_resolve_questions_defaults_per_provider_and_checks_membership():
    assert cli_module._resolve_questions(ProviderName.jev, None) == DEFAULT_QUESTION_SET_VERSION
    assert cli_module._resolve_questions(ProviderName.jev, "q-v0.1") == "q-v0.1"
    assert cli_module._resolve_questions(ProviderName.rules, None) is None
    with pytest.raises(typer.Exit):
        cli_module._resolve_questions(ProviderName.jev, "q-v9")
    with pytest.raises(typer.Exit):
        cli_module._resolve_questions(ProviderName.groundtruth, "q-v0.2")


def test_a_question_set_the_provider_does_not_allow_lists_the_choices(tmp_path):
    result = invoke(
        tmp_path,
        "run",
        "--dataset",
        str(SMOKE),
        "--provider",
        "jev",
        "--questions",
        "q-v9",
        *dirs(tmp_path),
    )
    assert result.exit_code == 2
    assert "choose one of: q-v0.1, q-v0.2" in result.output
    assert not (tmp_path / "traces").exists()
