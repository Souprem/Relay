"""scripts/phase3d_report.py: the E1 adoption decision and the E2 shift table."""

import json

from scripts.phase3d_report import adoption_decision, adoption_text, main, shift_markdown


def rate(count, n):
    return {"count": count, "n": n, "rate": count / n if n else None, "ci95": None}


def side(run_id, correct, auto, unsafe, *, policy="v0.1", thresholds="v0.1+at0.89"):
    return {
        "identity": {
            "run_id": run_id,
            "policy_versions": [policy],
            "thresholds_versions": [thresholds],
        },
        "correct": rate(correct, 400),
        "automation": rate(auto, 400),
        "uar": rate(unsafe, auto),
    }


def entry(case_id):
    return {"case_id": case_id}


def result(q2_correct, q3_correct, *, newly_unsafe=(), verdict="PASS"):
    return {
        "baseline": side("replay-run_a", q2_correct, 90, 0),
        "candidate": side("replay-run_b", q3_correct, 95, 0, thresholds="v0.1+at0.9"),
        "newly_unsafe": [entry(c) for c in newly_unsafe],
        "still_unsafe": [],
        "unsafe_resolved": [],
        "regressed": [],
        "improved": [entry("GEN-1")],
        "verdict": verdict,
    }


def test_adopt_needs_a_strictly_higher_correct_rate_and_a_passing_gate():
    assert adoption_decision(result(330, 340))
    assert not adoption_decision(result(330, 330))  # equal is not higher
    assert not adoption_decision(result(330, 320))
    assert not adoption_decision(result(330, 340, newly_unsafe=["GEN-2"], verdict="FAIL"))


def test_adoption_text():
    text = adoption_text(result(330, 340))
    assert text.splitlines()[2:] == [
        "  q-v0.2: run run_a correct 330/400 (0.8250) at thresholds v0.1+at0.89, unsafe 0",
        "  q-v0.3: run run_b correct 340/400 (0.8500) at thresholds v0.1+at0.9, unsafe 0",
        "  gate: PASS (newly unsafe 0, regressed 0, improved 1)",
        "DECISION: ADOPT q-v0.3",
    ]
    assert adoption_text(result(330, 330)).endswith("DECISION: KEEP q-v0.2")


def test_shift_markdown_lists_stale_only_unsafe_automations():
    shift = {
        "baseline": side("run_stale", 300, 60, 5),
        "candidate": side("run_aware", 318, 55, 0, policy="v0.2", thresholds="v0.2"),
        "newly_unsafe": [],
        "still_unsafe": [],
        "unsafe_resolved": [entry("GEN-05000001"), entry("GEN-05000007")],
        "regressed": [],
        "verdict": "PASS",
    }
    text = shift_markdown(shift)
    assert "| stale (`run_stale`) | v0.1 | 300/400 (75.0%) | 60/400 (15.0%) | 5/60 (8.3%) |" in text
    assert "| aware (`run_aware`) | v0.2 | 318/400 (79.5%) | 55/400 (13.8%) | 0/55 (0.0%) |" in text
    assert "Stale-only unsafe automations (2): GEN-05000001, GEN-05000007" in text
    assert "Gate stale → aware: PASS (newly unsafe 0, regressed 0)" in text


def test_main_reads_a_file_and_rejects_bad_usage(tmp_path, capsys):
    path = tmp_path / "regression.json"
    path.write_text(json.dumps(result(330, 340)))
    assert main(["adoption", str(path)]) == 0
    assert capsys.readouterr().out.strip().endswith("DECISION: ADOPT q-v0.3")
    assert main(["nope", str(path)]) == 2
