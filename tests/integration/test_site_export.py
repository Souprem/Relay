"""relay.site export core: index.json, runs, cases. Offline, deterministic, and in agreement with
the README headline table."""

import json

import pytest

from relay.site.common import ExportError, load_cases, load_run
from relay.site.core import bundle_run_payload, category_of, committed_run_payload
from relay.site.registry import RUNS, dataset_spec, run_spec
from tests.site_support import EXPORTED_AT, GIT_SHA, REPO, fake_repo, load, run_export

GOLD_IDS = sorted(p.name for p in (REPO / "evals" / "gold").iterdir() if p.is_dir())
SMOKE_IDS = sorted(p.name for p in (REPO / "evals" / "smoke").iterdir() if p.is_dir())

# The README headline table: (dataset, label, auto_process, correct, automation, unsafe, upper %).
README_HEADLINE = [
    ("gen-v0.2-holdout", "Jev q-v0.2", 0.89, 895, 252, 0, 1.5),
    ("gen-v0.2-holdout", "Rules", 0.99, 667, 134, 0, 2.7),
    ("gen-v0.3-holdout", "Jev q-v0.3", 0.81, 921, 244, 0, 1.5),
    ("gold-v0.1", "Jev q-v0.2", 0.89, 91, 29, 1, 17.8),
    ("gold-v0.1", "Claude", 0.55, 93, 30, 1, 17.2),
    ("gold-v0.1", "Rules", 0.99, 61, 20, 6, 54.3),
    ("gold-v0.1", "Jev q-v0.3", 0.81, 94, 31, 1, 16.7),
]


def test_it_writes_the_index_runs_and_one_file_per_case(site_export):
    names = {p.name for p in site_export.iterdir()}
    assert {"index.json", "runs.json", "cases.json", "runs", "cases"} <= names
    assert sorted(p.stem for p in (site_export / "cases").glob("*.json")) == sorted(
        GOLD_IDS + SMOKE_IDS
    )
    assert sorted(p.stem for p in (site_export / "runs").glob("*.json")) == sorted(
        r.run_id for r in RUNS
    )


def test_the_headline_table_matches_the_readme(site_export):
    index = load(site_export, "index.json")
    rows = [
        (
            r["dataset"],
            r["label"],
            r["auto_process"],
            r["correct"]["count"],
            r["automation"]["count"],
            r["uar"]["count"],
            round(r["uar"]["ci95"]["high"] * 100, 1),
        )
        for r in index["headline"]
    ]
    assert rows == README_HEADLINE
    assert [r["flat"] for r in index["headline"]] == [False, True, False, False, False, True, False]
    assert index["headline"][-1]["note"] == "not blind"


def test_the_index_records_spend_counts_and_the_pinned_export_time(site_export):
    index = load(site_export, "index.json")
    assert index["exported_at"] == EXPORTED_AT
    assert index["git_sha"] == GIT_SHA
    assert index["spend"] == {"claude_usd": "8.710495", "jev_3d_usd": "0.501850"}
    assert index["counts"]["cases"] == 110
    assert index["counts"]["by_dataset"] == {"gold-v0.1": 100, "smoke-v0.1": 10}
    assert index["entry_cases"] == {"easy": "GOLD-STR-01", "hard": "GOLD-CON-03"}
    assert "synthetic data only" in index["disclaimer"]


def test_every_gold_and_smoke_case_is_listed_exactly_once(site_export):
    cases = load(site_export, "cases.json")["cases"]
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)) == 110
    assert sorted(ids) == sorted(GOLD_IDS + SMOKE_IDS)
    assert {c["category"] for c in cases} == {"STR", "MIS", "CON", "TMP", "TRK", "SMOKE"}
    gold = next(c for c in cases if c["id"] == "GOLD-TMP-17")
    assert gold["expected"] == "HUMAN_REVIEW"
    assert gold["results"]["jev-q-v0.2"] == {"action": "AUTO_PROCESS", "verdict": "UNSAFE"}
    assert gold["results"]["jev-q-v0.3"] == {"action": "HUMAN_REVIEW", "verdict": "correct"}
    assert "groundtruth" not in gold["results"]


def test_per_provider_verdicts_match_the_committed_gold_results(site_export):
    cases = [c for c in load(site_export, "cases.json")["cases"] if c["dataset"] == "gold-v0.1"]

    def count(slug, verdict):
        return sum(c["results"][slug]["verdict"] == verdict for c in cases)

    assert (count("jev-q-v0.2", "correct"), count("jev-q-v0.2", "UNSAFE")) == (91, 1)
    assert (count("claude", "correct"), count("claude", "UNSAFE")) == (93, 1)
    assert (count("rules", "correct"), count("rules", "UNSAFE")) == (61, 6)
    assert (count("jev-q-v0.3", "correct"), count("jev-q-v0.3", "UNSAFE")) == (94, 1)


def test_a_case_file_has_inputs_truth_providers_gates_and_ticks(site_export):
    case = load(site_export, "cases/GOLD-TMP-17.json")
    assert case["input"]["content_hash"].startswith("sha256:")
    assert [d["kind"] for d in case["input"]["documents"]]
    assert case["ground_truth"]["expected_action"] == "HUMAN_REVIEW"
    assert [p["slug"] for p in case["providers"]] == [
        "jev-q-v0.2",
        "jev-q-v0.3",
        "claude",
        "rules",
        "groundtruth",
    ]
    jev = case["providers"][0]
    assert jev["thresholds"]["auto_process"] == 0.89
    assert [g["status"] for g in jev["gates"]] == [
        "passed",
        "passed",
        "passed",
        "passed",
        "passed",
        "FIRED",
        "not reached",
    ]
    ticks = {d["id"]: [(t["name"], t["value"]) for t in d["ticks"]] for d in jev["decisions"]}
    assert ticks["step_therapy"] == [("auto_process", 0.89)]
    assert ticks["material_contradiction"] == [
        ("contradiction_review", 0.8),
        ("contradiction_auto_block", 0.2),
    ]
    assert ticks["missing_evidence"] == [("missing_evidence_request_info", 0.7)]
    step = next(d for d in jev["decisions"] if d["id"] == "step_therapy")
    assert step["p_yes"] == pytest.approx(0.9316, abs=1e-4)
    assert jev["action"] == "AUTO_PROCESS" and jev["verdict"] == "UNSAFE"


def test_the_demonstrated_cases_carry_their_replay_diffs(site_export):
    expected = {
        "GOLD-TMP-17": ("AUTO_PROCESS", "HUMAN_REVIEW", False, True),
        "GOLD-TMP-18": ("AUTO_PROCESS", "AUTO_PROCESS", False, False),
        "GOLD-TMP-16": ("HUMAN_REVIEW", "AUTO_PROCESS", True, False),
        "GOLD-CON-03": ("HUMAN_REVIEW", "AUTO_PROCESS", True, False),
        "GOLD-CON-13": ("HUMAN_REVIEW", "AUTO_PROCESS", True, False),
    }
    for case_id, (before, after, newly, resolved) in expected.items():
        [diff] = load(site_export, f"cases/{case_id}.json")["diffs"]
        assert (diff["action_original"], diff["action_candidate"]) == (before, after), case_id
        assert (diff["newly_unsafe"], diff["unsafe_resolved"]) == (newly, resolved), case_id
        if newly:
            assert diff["verdict_candidate"] == "UNSAFE", case_id
        if resolved:
            assert diff["verdict_original"] == "UNSAFE", case_id
    assert load(site_export, "cases/GOLD-STR-01.json")["diffs"] == []
    listed = [c["id"] for c in load(site_export, "cases.json")["cases"] if c["has_diff"]]
    assert sorted(listed) == sorted(expected)


def test_a_run_file_has_metrics_with_intervals_frontier_and_calibration(site_export):
    run = load(site_export, "runs/run_20260925T170857Z_b95be9.json")
    assert run["operating_point"] == {
        "auto_process": 0.89,
        "recorded": 0.95,
        "source": "chosen on gen-v0.2-dev",
    }
    assert run["metrics"]["correct"]["count"] == 91
    assert run["metrics"]["uar"]["ci95"]["high"] == pytest.approx(0.178, abs=1e-3)
    assert len(run["frontier"]["points"]) == 50
    assert set(run["calibration"]["decisions"]) == {
        "diagnosis_support",
        "step_therapy",
        "documentation_complete",
        "material_contradiction",
        "missing_evidence",
    }
    runs = load(site_export, "runs.json")
    assert [d["id"] for d in runs["datasets"]][:2] == ["gold-v0.1", "smoke-v0.1"]


def test_a_committed_report_bundle_reads_back_as_the_live_computation():
    """Generated-set runs are read from their report bundles; on gold, where both paths exist,
    the bundle must give the same frontier and calibration as re-scoring the traces."""
    spec = run_spec("run_20260925T170857Z_b95be9")
    cases = load_cases(REPO, dataset_spec("gold-v0.1"))
    live = committed_run_payload(load_run(REPO, spec, cases), cases)
    bundle = bundle_run_payload(REPO, spec)
    assert bundle["frontier"] == live["frontier"]
    assert bundle["calibration"] == live["calibration"]
    assert bundle["metrics"] == live["metrics"]


def test_re_export_is_byte_identical(site_export, tmp_path):
    again = tmp_path / "data"
    run_export(again)
    first = sorted(p.relative_to(site_export) for p in site_export.rglob("*") if p.is_file())
    second = sorted(p.relative_to(again) for p in again.rglob("*") if p.is_file())
    assert first == second
    for relative in first:
        assert (site_export / relative).read_bytes() == (again / relative).read_bytes(), relative


def test_it_refuses_a_changed_case(tmp_path):
    repo = fake_repo(tmp_path / "repo", copy_gold=True)
    note = repo / "evals" / "gold" / "GOLD-STR-01" / "documents" / "physician_note.txt"
    note.write_text(note.read_text(encoding="utf-8") + "\nEdited.\n", encoding="utf-8")
    with pytest.raises(ExportError, match="content hash changed"):
        run_export(tmp_path / "out", repo=repo)


def test_it_refuses_a_missing_dataset(tmp_path):
    repo = fake_repo(tmp_path / "repo", omit=("evals/smoke",))
    with pytest.raises(ExportError, match="dataset smoke-v0.1 is missing"):
        run_export(tmp_path / "out", repo=repo)


def test_it_refuses_a_missing_run(tmp_path):
    repo = fake_repo(tmp_path / "repo", omit=("evals/baselines/smoke-v0.1",))
    with pytest.raises(ExportError, match="missing run"):
        run_export(tmp_path / "out", repo=repo)


def test_it_never_clears_a_directory_that_holds_no_export(tmp_path):
    out = tmp_path / "somewhere"
    out.mkdir()
    (out / "keep.txt").write_text("mine", encoding="utf-8")
    with pytest.raises(ExportError, match="not empty"):
        run_export(out)
    assert (out / "keep.txt").read_text(encoding="utf-8") == "mine"


def test_json_files_are_sorted_and_end_with_one_newline(site_export):
    text = (site_export / "index.json").read_text(encoding="utf-8")
    assert text.endswith("}\n") and not text.endswith("\n\n")
    data = json.loads(text)
    assert list(data) == sorted(data)


def test_category_comes_from_the_gold_id():
    assert category_of("GOLD-STR-01") == "STR"
    assert category_of("GOLD-TRK-20") == "TRK"
    assert category_of("AUTO-01") == "SMOKE"
    assert category_of("GOLD-XYZ-01") == "SMOKE"
