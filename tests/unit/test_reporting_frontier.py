from relay.evaluation.frontier import FrontierPoint, SweepResult
from relay.reporting import describe_selection, frontier_rows, render_frontier_table


def pt(threshold, auto=10, unsafe=0, n=100):
    return FrontierPoint(
        auto_threshold=threshold,
        n=n,
        auto=auto,
        request_info=0,
        human_review=n - auto,
        unsafe=unsafe,
        correct=n - unsafe,
        automation_rate=auto / n,
        uar=unsafe / auto if auto else None,
        human_review_rate=(n - auto) / n,
        correct_action_rate=(n - unsafe) / n,
    )


def result(selected=None, at_point=None, points=None, ceiling=0.01):
    points = points or [pt(round(0.50 + i / 100, 2)) for i in range(50)]
    return SweepResult(
        run_id="run_x",
        dataset_id="gen-test",
        provider="test",
        question_set_version="q-test",
        ceiling=ceiling,
        selected=selected,
        at_point=at_point,
        points=points,
    )


def test_frontier_rows_every_0_05_plus_selected_and_at():
    r = result(selected=pt(0.97), at_point=pt(0.935))
    rows = frontier_rows(r)
    thresholds = [p.auto_threshold for p, _ in rows]
    assert thresholds == [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.935, 0.95, 0.97]
    notes = {p.auto_threshold: note for p, note in rows}
    assert notes[0.97] == "selected" and notes[0.935] == "--at" and notes[0.95] == ""


def test_frontier_rows_merge_notes_on_the_same_threshold():
    rows = frontier_rows(result(selected=pt(0.95), at_point=pt(0.95)))
    assert [note for p, note in rows if p.auto_threshold == 0.95] == ["selected, --at"]


def test_describe_selection_with_and_without_a_point():
    # The default fixture points are all identical (auto=10, unsafe=0), so the frontier is flat
    # and the ceiling (unsafe always 0) never binds; both notes are appended (C2).
    flat_and_slack = (
        "\nFrontier is flat across all thresholds.\nThe UAR ceiling does not bind at any threshold."
    )
    assert describe_selection(result(selected=pt(0.97, auto=25))) == (
        "Selected operating point: auto_process >= 0.97 (automation 25.0%, UAR 0/25, "
        "correct action 100.0%; ceiling UAR <= 1.0%)" + flat_and_slack
    )
    assert describe_selection(result()) == (
        "No threshold meets the ceiling (UAR <= 1.0% with at least one AUTO_PROCESS); "
        "nothing selected." + flat_and_slack
    )


def test_describe_selection_reports_a_changing_frontier_and_a_binding_ceiling():
    points = [pt(0.90, auto=100, unsafe=5), pt(0.95, auto=50, unsafe=0)]
    text = describe_selection(result(selected=pt(0.95, auto=50), points=points))
    assert "Frontier is flat across all thresholds." not in text
    assert "The UAR ceiling binds: at least one automated threshold's UAR exceeds it." in text


def test_render_frontier_table_shows_rows_rule_and_zero_auto():
    r = result(selected=pt(0.97), points=[pt(0.95), pt(0.97), pt(0.99, auto=0)])
    text = render_frontier_table(r)
    assert "run run_x" in text and "n=100" in text
    assert "0.95" in text and "0.97" in text
    assert "n/a (no AUTO)" not in text  # 0.99 is neither a 0.05 step nor marked
    assert "Selected operating point: auto_process >= 0.97" in text
    assert "ties go to the higher threshold" in text
    zero = render_frontier_table(result(at_point=pt(0.99, auto=0)))
    assert "n/a (no AUTO)" in zero and "--at" in zero


def test_off_grid_thresholds_keep_their_precision():
    text = render_frontier_table(result(at_point=pt(0.935)))
    assert "0.935" in text and "0.94 " not in text
    assert "0.50 " in text
