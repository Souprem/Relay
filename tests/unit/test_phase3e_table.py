"""scripts/phase3e_table.py: the ablation summary over regression.json files."""

import json

from scripts.phase3e_table import collect, main, render, summary_row


def rate(count, n):
    if n == 0:
        return {"count": count, "n": n, "rate": None, "ci95": None}
    return {"count": count, "n": n, "rate": count / n, "ci95": {"low": 0.01, "high": 0.5}}


def result(*, newly_unsafe=(), unchanged=98, auto=(29, 32), unsafe=(1, 3), verdict="FAIL"):
    def side(run_id, auto_count, unsafe_count):
        return {
            "identity": {
                "run_id": run_id,
                "provider": "jev",
                "question_set_versions": ["q-v0.3"],
                "thresholds_versions": ["v0.1+at0.81"],
            },
            "automation": rate(auto_count, 100),
            "uar": rate(unsafe_count, auto_count),
        }

    return {
        "n": 100,
        "verdict": verdict,
        "baseline": side("replay-run_src", auto[0], unsafe[0]),
        "candidate": side("run_abl", auto[1], unsafe[1]),
        "change_counts": {
            "improved": 0,
            "unchanged": unchanged,
            "regressed": 100 - unchanged,
            "changed-both-wrong": 0,
        },
        "newly_unsafe": [{"case_id": c} for c in newly_unsafe],
        "regressed": [{"case_id": "X"}] * (100 - unchanged),
        "improved": [],
    }


def write(root, dataset, run, ablation, data):
    path = root / dataset / run / ablation / "regression.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_summary_row():
    row = summary_row("gold-v0.1", "jev-q-v0.3", "contradiction", result(newly_unsafe=["G-1"]))
    assert row["source_run_id"] == "run_src"
    assert (row["provider"], row["thresholds"]) == ("jev q-v0.3", "v0.1+at0.81")
    assert (row["actions_changed"], row["newly_unsafe"], row["regressed"]) == (2, ["G-1"], 2)
    assert row["automation"]["ablated"]["count"] == 32


def test_rows_follow_dataset_run_and_ablation_order(tmp_path):
    still = result(unchanged=100, auto=(10, 10), unsafe=(0, 0), verdict="PASS")
    write(tmp_path, "gold-v0.1", "jev-q-v0.3", "missing_evidence", still)
    write(tmp_path, "gold-v0.1", "jev-q-v0.3", "contradiction", result(newly_unsafe=["G-1"]))
    write(tmp_path, "gold-v0.1", "groundtruth", "contradiction", still)
    write(tmp_path, "gen-v0.2-holdout", "rules", "contradiction+missing_evidence", still)
    rows = collect(tmp_path)
    assert [(r["dataset"], r["run"], r["ablation"]) for r in rows] == [
        ("gen-v0.2-holdout", "rules", "contradiction+missing_evidence"),
        ("gold-v0.1", "groundtruth", "contradiction"),
        ("gold-v0.1", "jev-q-v0.3", "contradiction"),
        ("gold-v0.1", "jev-q-v0.3", "missing_evidence"),
    ]


def test_render_marks_null_results_and_failing_pairs(tmp_path):
    still = result(unchanged=100, auto=(10, 10), unsafe=(0, 0), verdict="PASS")
    write(tmp_path, "gold-v0.1", "jev-q-v0.3", "contradiction", result(newly_unsafe=["G-1"]))
    write(tmp_path, "gold-v0.1", "jev-q-v0.3", "missing_evidence", still)
    text = render(collect(tmp_path))
    assert (
        "| gold-v0.1 | jev-q-v0.3 (`run_src`) | jev q-v0.3 | v0.1+at0.81 | contradiction | FAIL "
        "| 2/100 | 1 (G-1) | 2 | 0 | 29/100 (29.0%) [1.0%, 50.0%] → 32/100 (32.0%) [1.0%, 50.0%] "
        "| 1/29 (3.4%) [1.0%, 50.0%] → 3/32 (9.4%) [1.0%, 50.0%] |"
    ) in text
    assert "| missing_evidence | PASS | 0/100 | 0 | 0 | 0 |" in text
    assert (
        "Null results (no action changed): 1\n- gold-v0.1 / jev-q-v0.3 × missing_evidence" in text
    )
    assert (
        "Pairs whose gate FAILs (a newly unsafe automation): 1\n"
        "- gold-v0.1 / jev-q-v0.3 × contradiction: G-1"
    ) in text


def test_an_empty_rate_renders_as_n_a(tmp_path):
    none = result(unchanged=100, auto=(0, 0), unsafe=(0, 0), verdict="PASS")
    write(tmp_path, "gold-v0.1", "rules", "contradiction", none)
    assert "0/0 (n/a) → 0/0 (n/a)" in render(collect(tmp_path))


def test_main_writes_summary_md_and_json(tmp_path, capsys):
    write(tmp_path, "gold-v0.1", "jev-q-v0.3", "contradiction", result(newly_unsafe=["G-1"]))
    assert main([str(tmp_path)]) == 0
    printed = capsys.readouterr().out
    assert (tmp_path / "summary.md").read_text() == printed
    [row] = json.loads((tmp_path / "summary.json").read_text())
    assert row["newly_unsafe"] == ["G-1"]
    assert main([str(tmp_path / "empty")]) == 2
    assert main(["a", "b"]) == 2
