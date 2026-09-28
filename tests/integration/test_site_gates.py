"""relay.site gates.json and experiments.json, and the relay export-site command."""

import anthropic
import pytest
from typer.testing import CliRunner

from relay.cli import app
from relay.evaluation.regression_run import load_gates
from relay.site.common import ExportError
from tests.site_support import REPO, fake_repo, load, no_network, run_export

GENERATED = REPO / "evals" / "generated"
HAVE_GENERATED = all(
    (GENERATED / name).is_dir()
    for name in (
        "gen-v0.2-holdout",
        "gen-v0.3-dev",
        "gen-v0.3-holdout",
        "gen-v0.3-shift",
    )
)


def by_key(items, key="key"):
    return {item[key]: item for item in items}


def test_the_guard_refuses_a_provider_client():
    with no_network(), pytest.raises(AssertionError, match="network"):
        anthropic.AsyncAnthropic(api_key="test-not-a-key")


def test_every_committed_gate_is_listed_in_config_order(site_export):
    gates = load(site_export, "gates.json")["gates"]
    config = load_gates(REPO / "evals" / "regression" / "gates.json").gates
    assert [g["name"] for g in gates] == [g.name for g in config]
    assert len(gates) == 20
    for gate in gates:
        if gate["requires_generated"]:
            assert gate["verdict"] in {"PASS", "SKIPPED"}, gate["name"]
        else:
            assert gate["verdict"] == "PASS", gate["name"]
    rows = by_key(gates, "name")
    assert rows["gold-reproduce-rules"]["still_unsafe"] == 6
    assert rows["gold-jev-vs-claude"]["kind"] == "compare"
    assert rows["gold-jev-vs-claude"]["still_unsafe"] == 1


@pytest.mark.skipif(not HAVE_GENERATED, reason="generated datasets are not on disk")
def test_with_generated_datasets_every_gate_runs_and_passes(site_export):
    gates = load(site_export, "gates.json")["gates"]
    assert {g["verdict"] for g in gates} == {"PASS"}


def test_the_regression_demos(site_export):
    reports = by_key(load(site_export, "gates.json")["regressions"])
    assert list(reports) == [
        "gold-fail",
        "gold-waiver",
        "gold-jev-vs-claude",
        "holdout-adoption",
        "stale-to-aware",
    ]
    fail = reports["gold-fail"]
    assert fail["verdict"] == "FAIL" and fail["exit_code"] == 4
    assert [e["case_id"] for e in fail["newly_unsafe"]] == ["GOLD-TMP-17"]
    waiver = reports["gold-waiver"]
    assert waiver["verdict"] == "PASS" and waiver["newly_unsafe"] == []
    assert [w["case_id"] for w in waiver["waived"]] == ["GOLD-TMP-17"]
    assert waiver["waived"][0]["waiver"]["approved_by"] == "example (README demonstration)"
    assert [e["case_id"] for e in reports["gold-jev-vs-claude"]["still_unsafe"]] == ["GOLD-TMP-17"]
    adoption = reports["holdout-adoption"]
    assert adoption["verdict"] == "PASS"
    assert (
        adoption["baseline"]["correct"]["count"],
        adoption["baseline"]["automation"]["count"],
        adoption["baseline"]["uar"]["count"],
    ) == (694, 17, 1)
    assert (
        adoption["candidate"]["correct"]["count"],
        adoption["candidate"]["automation"]["count"],
        adoption["candidate"]["uar"]["count"],
    ) == (921, 244, 0)
    shift = reports["stale-to-aware"]
    assert (shift["baseline"]["uar"]["count"], shift["baseline"]["uar"]["n"]) == (3, 16)
    assert (shift["candidate"]["uar"]["count"], shift["candidate"]["uar"]["n"]) == (0, 13)


def test_the_shadow_demos_promote_and_hold_with_state_verified(site_export):
    shadow = by_key(load(site_export, "gates.json")["shadow"])
    promote, hold = shadow["promote"], shadow["hold"]
    assert promote["decision"] == "PROMOTE"
    assert promote["agreement"]["agreed"]["count"] == 96
    assert promote["still_unsafe"] == ["GOLD-TMP-17"]
    assert promote["agreement"]["newly_auto"] == ["GOLD-MIS-17", "GOLD-TMP-15"]
    assert hold["decision"] == "HOLD"
    assert hold["newly_unsafe"] == ["GOLD-TMP-17"]
    assert hold["agreement"]["agreed"]["count"] == 89
    for demo in (promote, hold):
        assert demo["state_verified"] is True
        assert demo["state_line"] == "case state unchanged (verified)"
        assert demo["proposals"] == 100


def test_the_experiments(site_export):
    experiments = load(site_export, "experiments.json")
    qv03 = experiments["qv03"]
    holdout = qv03["reports"]["holdout"]
    assert holdout["candidate"]["correct"]["count"] == 921
    assert qv03["reports"]["gold"]["verdict"] == "FAIL"
    assert [e["case_id"] for e in qv03["reports"]["gold"]["newly_unsafe"]] == ["GOLD-TMP-16"]
    assert qv03["link"].endswith("#question-set-q-v03-interrupted-courses")
    shift = experiments["shift"]
    assert shift["shadow_decision"] == "PROMOTE"
    assert shift["rules"] == {"n": 400, "correct": 261, "automation": 50, "unsafe": 6}
    sizes = experiments["parallelism"]["sizes"]
    assert [s["size"] for s in sizes] == [1, 5, 10, 20]
    assert round(sizes[0]["p50_ms"]) == 178 and round(sizes[-1]["p50_ms"]) == 191
    ablation = experiments["ablation"]["rows"]
    assert len(ablation) == 30
    newly = {(r["dataset"], r["run"], r["ablation"]) for r in ablation if r["newly_unsafe"]}
    assert all(dataset == "gold-v0.1" for dataset, _, _ in newly)
    assert all("contradiction" in ablation_name for _, _, ablation_name in newly)


@pytest.mark.skipif(not HAVE_GENERATED, reason="generated datasets are not on disk")
def test_the_interrupted_course_breakdown_when_generated_sets_exist(site_export):
    split = by_key(load(site_export, "experiments.json")["qv03"]["course_split"], "dataset")
    holdout = by_key(split["gen-v0.3-holdout"]["tags"], "tag")
    assert holdout["interrupted"]["q_v0_2"] == [147, 188]
    assert holdout["interrupted"]["q_v0_3"] == [188, 188]
    assert holdout["old_course"]["q_v0_3"] == [137, 142]


def test_without_generated_sets_those_gates_and_the_breakdown_are_skipped(tmp_path):
    repo = fake_repo(tmp_path / "repo")
    out = tmp_path / "out"
    run_export(out, repo=repo)
    gates = load(out, "gates.json")["gates"]
    assert {g["verdict"] for g in gates if g["requires_generated"]} == {"SKIPPED"}
    assert {g["verdict"] for g in gates if not g["requires_generated"]} == {"PASS"}
    split = load(out, "experiments.json")["qv03"]["course_split"]
    assert {s["status"] for s in split} == {"skipped"}


def test_strict_generated_refuses_instead_of_skipping(tmp_path):
    repo = fake_repo(tmp_path / "repo")
    with pytest.raises(ExportError, match="dataset not generated"):
        run_export(tmp_path / "out", repo=repo, strict_generated=True)


def test_the_cli_writes_the_data(tmp_path, monkeypatch):
    repo = fake_repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    out = tmp_path / "data"
    with no_network():
        result = CliRunner().invoke(
            app,
            [
                "--env-file",
                str(tmp_path / "missing.env"),
                "export-site",
                "--out",
                str(out),
                "--exported-at",
                "2026-09-28T12:00:00Z",
            ],
        )
    assert result.exit_code == 0, result.output
    assert "Site data:" in result.output
    assert load(out, "index.json")["exported_at"] == "2026-09-28T12:00:00Z"


def test_the_cli_exits_2_on_an_input_error(tmp_path, monkeypatch):
    repo = fake_repo(tmp_path / "repo", omit=("evals/smoke",))
    monkeypatch.chdir(repo)
    with no_network():
        result = CliRunner().invoke(
            app,
            [
                "--env-file",
                str(tmp_path / "missing.env"),
                "export-site",
                "--out",
                str(tmp_path / "o"),
            ],
        )
    assert result.exit_code == 2
    assert "dataset smoke-v0.1 is missing" in result.output
