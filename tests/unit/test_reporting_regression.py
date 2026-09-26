"""render_regression and render_gate_summary: the terminal output of `relay regression`."""

import re

from relay.evaluation.regression import Waiver, build_result
from relay.evaluation.tracediff import diff_runs, replay_run
from relay.reporting import GateRow, render_gate_summary, render_regression
from tests.factories import make_bundle, make_case, make_trace, make_truth


def result_for(*, waivers=(), reproduce=False, auto_process=0.9, replay=True):
    """T-01 improves, T-02 and T-03 become newly unsafe at `auto_process` (see test_regression)."""
    cases = [
        make_case("T-01"),
        make_case("T-02", truth=make_truth(step_therapy_satisfied=False)),
        make_case("T-03", truth=make_truth(step_therapy_satisfied=False)),
    ]
    baseline = [make_trace(c, make_bundle(c.input.id, step=0.93)) for c in cases]
    candidate = replay_run(
        baseline, cases, policy_id=None, auto_process=None if reproduce else auto_process
    )
    diffs = diff_runs(baseline, candidate, cases, original_label="base", candidate_label="cand")
    return build_result(
        diffs,
        baseline,
        candidate,
        cases,
        baseline_label="base run",
        candidate_label="cand run",
        gate="g1",
        reproduce=reproduce,
        waivers=list(waivers),
        max_regressed=None,
        replay_command=(lambda case_id: f"relay replay {case_id} --at 0.9") if replay else None,
    )


def waiver(case_id):
    return Waiver(
        case_id=case_id, gate="*", reason="reviewed", approved_by="rev", date="2026-09-26"
    )


def test_header_metrics_and_counts():
    text = render_regression(result_for())
    lines = text.splitlines()
    assert lines[:3] == [
        "Relay regression — gate g1 · dataset test · n=3",
        "BASELINE  base run",
        "CANDIDATE cand run",
    ]
    assert re.search(r"Automation rate\s+0/3 \(0\.0%\)\s+3/3 \(100\.0%\)\s+\+100\.0 pp", text)
    assert re.search(r"Unsafe automation rate\s+n/a\s+2/3 \(66\.7%\)\s+n/a\s+n/a\s+\[", text)
    assert (
        "CHANGES: improved 1 · unchanged 0 · regressed 2 · changed-both-wrong 0 · not identical 3"
    ) in lines


def test_newly_unsafe_comes_first_with_a_replay_command_and_the_gate_line_is_last():
    text = render_regression(result_for())
    lines = text.splitlines()
    assert lines.index("NEWLY UNSAFE (2)") < lines.index("REGRESSED (2)")
    assert "  T-02  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS" in lines
    assert "      answer changed: none · gated crossings: step_therapy: auto_process" in lines
    assert "      replay: relay replay T-02 --at 0.9" in lines
    assert (
        lines[-1] == "REGRESSION GATE: FAIL — 2 newly unsafe case(s) without a waiver: T-02, T-03"
    )
    assert "CALIBRATION (Δ = candidate − baseline)" in lines


def test_a_case_without_a_replay_command_says_how_to_get_one():
    text = render_regression(result_for(replay=False))
    assert "      replay: re-run with --out DIR for a replayable command" in text


def test_waived_and_stale_waivers_are_listed():
    text = render_regression(result_for(waivers=[waiver("T-02"), waiver("T-03"), waiver("OLD")]))
    lines = text.splitlines()
    assert "NEWLY UNSAFE" not in text.replace("WAIVED NEWLY UNSAFE", "")
    assert "WAIVED NEWLY UNSAFE (2) — reviewed, not failures" in lines
    assert "      waiver: reviewed (approved by rev, 2026-09-26, gate *)" in lines
    assert "STALE WAIVERS (1) — warning: no newly unsafe case" in lines
    assert "  OLD (gate *, approved by rev, 2026-09-26)" in lines
    assert lines[-1] == "REGRESSION GATE: PASS"


def test_reproduce_prints_its_note_and_passes_when_identical():
    text = render_regression(result_for(reproduce=True))
    assert "REPRODUCE: the baseline's stored decisions under the current engine" in text
    assert "ENGINE DRIFT" in text  # only in the note
    assert "ENGINE DRIFT (" not in text
    assert text.splitlines()[-1] == "REGRESSION GATE: PASS"


def test_regressed_cases_are_capped_at_20_unless_all():
    result = result_for()
    many = [result.regressed[0].model_copy(update={"case_id": f"R-{i:02d}"}) for i in range(25)]
    result = result.model_copy(update={"regressed": many})
    text = render_regression(result)
    assert "REGRESSED (25) — showing 20; --all shows every case" in text
    assert "  R-19  " in text and "  R-20  " not in text
    full = render_regression(result, show_all=True)
    assert "REGRESSED (25)" in full.splitlines() and "  R-24  " in full


def test_gate_summary_table():
    text = render_gate_summary(
        [
            GateRow("gold-reproduce-jev", "PASS", 0, 0, 0),
            GateRow(
                "holdout-reproduce-jev", "SKIPPED", None, None, 0, note="dataset not generated"
            ),
        ]
    )
    lines = text.splitlines()
    assert lines[0] == "REGRESSION GATES"
    assert re.match(r"GATE\s+VERDICT\s+NEWLY UNSAFE\s+REGRESSED\s+EXIT", lines[1])
    assert re.match(r"gold-reproduce-jev\s+PASS\s+0\s+0\s+0", lines[2])
    assert re.match(
        r"holdout-reproduce-jev\s+SKIPPED \(dataset not generated\)\s+—\s+—\s+0", lines[3]
    )
