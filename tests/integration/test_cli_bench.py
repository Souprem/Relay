"""relay bench with a fake TypeSafe client: estimate, counter, outputs (no network)."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

import relay.cli as cli_module
from relay.cli import app
from relay.evaluation.budget import load_ledger
from tests.jev_fakes import GenericSystemOneClient

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
runner = CliRunner()


class FakeAsyncClient(GenericSystemOneClient):
    instances: list["FakeAsyncClient"] = []

    def __init__(self, **kwargs):
        super().__init__()
        FakeAsyncClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None


@pytest.fixture
def fake_jev(monkeypatch):
    FakeAsyncClient.instances = []
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", FakeAsyncClient)
    return FakeAsyncClient


def bench(tmp_path, *extra):
    return runner.invoke(
        app,
        [
            "--env-file",
            str(tmp_path / "missing.env"),
            "bench",
            "--dataset",
            str(SMOKE),
            "--jev-ledger",
            str(tmp_path / "jev-spend.json"),
            "--out",
            str(tmp_path / "bench"),
            *extra,
        ],
    )


def test_bench_prints_the_estimate_runs_every_size_and_writes_both_files(tmp_path, fake_jev):
    result = bench(tmp_path, "--jev-budget-usd", "1.00", "--limit", "4", "--sample-seed", "11")
    assert result.exit_code == 0, result.output
    # 4 cases x (12 + 12 + 12 + 20) billed questions x $0.000013
    assert "jev estimate: 4 cases × (1+5+10+20) questions ≈ $0.0029" in result.output
    [client] = fake_jev.instances
    # Sizes are rotated per case (I1), offset by sample seed 11 + case index, mod 4:
    # case 0 -> offset 3 (20,1,5,10), case 1 -> offset 0 (1,5,10,20),
    # case 2 -> offset 1 (5,10,20,1), case 3 -> offset 2 (10,20,1,5).
    assert [len(c["questions"]) for c in client.calls] == [
        20,
        1,
        5,
        10,
        1,
        5,
        10,
        20,
        5,
        10,
        20,
        1,
        10,
        20,
        1,
        5,
    ]
    data = json.loads((tmp_path / "bench" / "parallelism.json").read_text())
    assert [s["size"] for s in data["sizes"]] == [1, 5, 10, 20]
    assert (data["sample_limit"], data["sample_seed"], data["case_count"]) == (4, 11, 4)
    assert data["question_set_version"] == "q-v0.3"
    md = (tmp_path / "bench" / "parallelism.md").read_text()
    assert md.startswith("# Relay bench: narrow decisions per call vs latency")
    [entry] = load_ledger(tmp_path / "jev-spend.json").entries
    # 16 calls; tokens 1000 + 50k: 4 x (1050 + 1250 + 1500 + 2000) = 23,200 tokens
    assert (entry.status, entry.cost_usd) == ("settled", Decimal("0.000974"))
    assert "Jev spend: this bench $0.0010; total $0.0010 of the $1.00 cap" in result.output


def test_bench_requires_the_counter(tmp_path, fake_jev):
    result = bench(tmp_path)
    assert result.exit_code == 2
    assert "--jev-budget-usd" in result.output
    assert fake_jev.instances == []


def test_bench_refuses_over_the_cap_before_any_call(tmp_path, fake_jev):
    result = bench(tmp_path, "--jev-budget-usd", "0.001")
    assert result.exit_code == 2
    assert "Jev budget exceeded" in result.output
    assert fake_jev.instances == []


def test_bench_refuses_bad_sizes_and_existing_outputs(tmp_path, fake_jev):
    bad = bench(tmp_path, "--jev-budget-usd", "1", "--sizes", "1,21")
    assert bad.exit_code == 2 and "between 1 and 20" in bad.output
    (tmp_path / "bench").mkdir()
    (tmp_path / "bench" / "parallelism.json").write_text("{}")
    exists = bench(tmp_path, "--jev-budget-usd", "1")
    assert exists.exit_code == 2 and "refusing to overwrite" in exists.output
    assert fake_jev.instances == []


def test_bench_needs_the_typesafe_key(tmp_path, fake_jev, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY")
    result = bench(tmp_path, "--jev-budget-usd", "1")
    assert result.exit_code == 2 and "TYPESAFE_API_KEY is not set" in result.output
