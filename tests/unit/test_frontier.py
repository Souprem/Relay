import pytest

from relay.cases.policies import load_policy
from relay.decisions.ground_truth import bundle_from_truth
from relay.evaluation.frontier import (
    DEFAULT_CEILING,
    FRONTIER_FIELDS,
    SWEEP_POINTS,
    FrontierPoint,
    evaluate_threshold,
    frontier_csv,
    run_sweep,
    select_operating_point,
    sweep,
)
from relay.evaluation.labels import expected_action
from relay.evaluation.metrics import EvalError
from relay.workflow.thresholds import THRESHOLDS_V0_1
from tests.factories import make_bundle, make_case, make_trace, make_truth


def known_run():
    """Four cases whose automation changes at thresholds 0.90, 0.93 and 0.97.

    A: expected AUTO, min required p_yes 0.97 -> auto while t <= 0.97
    B: expected AUTO, min required p_yes 0.90 -> auto while t <= 0.90
    C: expected REVIEW (true contradiction the model missed), min p 0.93 -> UNSAFE auto, t <= 0.93
    D: expected REVIEW (step therapy not met), step p_yes 0.3 -> never auto
    """
    cases = [
        make_case("A"),
        make_case("B"),
        make_case("C", truth=make_truth(contradiction_present=True)),
        make_case("D", truth=make_truth(step_therapy_satisfied=False)),
    ]
    bundles = [
        make_bundle("A", diag=0.97),
        make_bundle("B", diag=0.90),
        make_bundle("C", diag=0.93, step=0.93, doc=0.93),
        make_bundle("D", step=0.3),
    ]
    traces = [make_trace(c, b) for c, b in zip(cases, bundles, strict=True)]
    return traces, cases


def at(points, threshold):
    [point] = [p for p in points if p.auto_threshold == threshold]
    return point


def pt(threshold, auto, unsafe, n=100):
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


def test_sweep_points_are_0_50_to_0_99_in_steps_of_0_01():
    assert len(SWEEP_POINTS) == 50
    assert SWEEP_POINTS[0] == 0.50 and SWEEP_POINTS[-1] == 0.99
    assert SWEEP_POINTS[43] == 0.93
    assert DEFAULT_CEILING == 0.01


def test_sweep_on_a_hand_built_run():
    traces, cases = known_run()
    points = sweep(traces, cases)
    assert [p.auto_threshold for p in points] == list(SWEEP_POINTS)

    low = at(points, 0.90)  # A, B, C auto (C unsafe); D review
    assert (low.n, low.auto, low.unsafe, low.correct, low.human_review) == (4, 3, 1, 3, 1)
    assert low.automation_rate == pytest.approx(0.75)  # 3/4
    assert low.uar == pytest.approx(1 / 3)  # 1 unsafe / 3 auto
    assert low.correct_action_rate == pytest.approx(0.75)  # A, B, D

    mid = at(points, 0.91)  # A, C auto (C unsafe); B, D review (B is a miss)
    assert (mid.auto, mid.unsafe, mid.correct) == (2, 1, 2)
    assert mid.uar == pytest.approx(0.5)  # 1/2
    assert at(points, 0.93).auto == 2  # p_yes 0.93 is not below a 0.93 bar

    safe = at(points, 0.94)  # only A auto; B, C, D review
    assert (safe.auto, safe.unsafe, safe.correct) == (1, 0, 3)
    assert safe.uar == 0.0
    assert safe.human_review_rate == pytest.approx(0.75)  # 3/4
    assert at(points, 0.97).auto == 1

    none = at(points, 0.98)  # nothing automated
    assert (none.auto, none.uar, none.correct) == (0, None, 2)  # C and D correct
    assert none.correct_action_rate == pytest.approx(0.5)


def test_rates_add_up_at_every_point():
    traces, cases = known_run()
    for p in sweep(traces, cases):
        assert p.auto + p.request_info + p.human_review == p.n


def test_sweep_accepts_custom_points_and_evaluate_threshold_matches():
    traces, cases = known_run()
    points = sweep(traces, cases, points=[0.935, 0.5])
    assert [p.auto_threshold for p in points] == [0.935, 0.5]
    assert points[0].auto == 1  # C's 0.93 is below 0.935
    assert evaluate_threshold(traces, cases, 0.935) == points[0]


def test_expected_actions_do_not_change_across_thresholds():
    traces, cases = known_run()
    for case in cases:
        policy = load_policy(case.input.policy_id)
        actions = {
            expected_action(case, policy, THRESHOLDS_V0_1.model_copy(update={"auto_process": t}))
            for t in SWEEP_POINTS
        }
        assert len(actions) == 1, case.input.id


def test_certain_bundles_give_identical_results_at_every_threshold():
    cases = [
        make_case("A"),
        make_case("B", truth=make_truth(contradiction_present=True)),
        make_case("C", age=16),
    ]
    traces = [make_trace(c, bundle_from_truth(c.input.id, c.ground_truth)) for c in cases]
    points = sweep(traces, cases)
    shapes = {(p.auto, p.request_info, p.human_review, p.unsafe, p.correct) for p in points}
    assert shapes == {(1, 0, 2, 0, 3)}
    assert select_operating_point(points).auto_threshold == 0.99  # every tie -> highest


def test_select_maximizes_automation_under_the_ceiling():
    traces, cases = known_run()
    points = sweep(traces, cases)
    # Only 0.94-0.97 have UAR <= 0.01 (UAR 0, automation 1/4); the tie goes to 0.97.
    assert select_operating_point(points).auto_threshold == 0.97
    # With a 0.4 ceiling, 0.50-0.90 qualify (UAR 1/3, automation 3/4); tie -> 0.90.
    assert select_operating_point(points, ceiling=0.4).auto_threshold == 0.90
    # 0.3 excludes UAR 1/3 and 1/2, so back to 0.97.
    assert select_operating_point(points, ceiling=0.3).auto_threshold == 0.97


def test_select_ceiling_is_inclusive():
    points = [pt(0.90, auto=100, unsafe=1), pt(0.95, auto=50, unsafe=0)]
    # 1/100 = 0.01 <= 0.01, and 100 autos beat 50.
    assert select_operating_point(points, ceiling=0.01).auto_threshold == 0.90


def test_select_ties_go_to_the_higher_threshold():
    points = [pt(0.95, auto=40, unsafe=0), pt(0.96, auto=40, unsafe=0), pt(0.94, auto=40, unsafe=0)]
    assert select_operating_point(points).auto_threshold == 0.96


def test_select_returns_none_when_no_point_qualifies():
    only_unsafe = [pt(0.90, auto=10, unsafe=5), pt(0.95, auto=2, unsafe=1)]
    assert select_operating_point(only_unsafe) is None


def test_zero_auto_points_never_qualify():
    # UAR is undefined with no automation, so 0.99 must not be "selected" as perfectly safe.
    assert select_operating_point([pt(0.98, auto=0, unsafe=0), pt(0.99, auto=0, unsafe=0)]) is None
    traces, cases = known_run()
    c_only = [t for t in traces if t.case_id == "C"]
    assert select_operating_point(sweep(c_only, [cases[2]])) is None  # unsafe or zero-auto


def test_sweep_validates_coverage():
    traces, cases = known_run()
    with pytest.raises(EvalError, match="D"):
        sweep(traces[:3], cases)


def test_run_sweep_bundles_points_selection_and_at_point():
    traces, cases = known_run()
    result = run_sweep(traces, cases, at=0.935)
    assert (result.run_id, result.dataset_id, result.provider) == ("run_test", "test", "test")
    assert result.question_set_version == "q-test"
    assert result.ceiling == 0.01
    assert result.selected.auto_threshold == 0.97
    assert result.at_point.auto_threshold == 0.935 and result.at_point.auto == 1
    assert len(result.points) == 50
    assert run_sweep(traces, cases).at_point is None


def test_frontier_csv_has_a_stable_header_and_blank_for_missing_uar():
    traces, cases = known_run()
    text = frontier_csv(sweep(traces, cases, points=[0.90, 0.99]))
    lines = text.splitlines()
    assert lines[0] == (
        "auto_threshold,n,auto,request_info,human_review,unsafe,correct,"
        "automation_rate,uar,human_review_rate,correct_action_rate"
    )
    assert lines[0].split(",") == list(FRONTIER_FIELDS)
    assert lines[1].startswith("0.9,4,3,0,1,1,3,0.75,0.3333333333333333,")
    assert lines[2] == "0.99,4,0,0,4,0,2,0.0,,1.0,0.5"
    assert text.endswith("\n")
