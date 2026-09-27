"""relay.evaluation.ablate_run: --disable parsing, ablate_run, and the bundle manifest."""

import json

import pytest

from relay.evaluation.ablate_run import ablate_run, ablation_name, parse_disable
from relay.evaluation.metrics import EvalError
from relay.evaluation.recompose_run import write_simulated_bundle
from relay.traces.models import RunManifest
from relay.traces.store import read_traces
from relay.workflow.outcomes import WorkflowAction
from tests.factories import make_bundle, make_case, make_trace

AUTO = WorkflowAction.AUTO_PROCESS
REVIEW = WorkflowAction.HUMAN_REVIEW
INFO = WorkflowAction.REQUEST_INFO
CONTRA = frozenset({"contradiction"})


def run():
    """Three cases: a contradiction review, a missing-evidence request and a clean case whose
    step_therapy (0.93) automates only at auto_process <= 0.93."""
    cases = [make_case(i) for i in ("T-01", "T-02", "T-03")]
    bundles = [
        make_bundle("T-01", contra=0.9),
        make_bundle("T-02", missing="INSURANCE_INFORMATION", missing_p=0.8),
        make_bundle("T-03", step=0.93),
    ]
    return cases, [make_trace(c, b) for c, b in zip(cases, bundles, strict=True)]


@pytest.mark.parametrize(
    "value,expected",
    [
        ("contradiction", {"contradiction"}),
        ("missing_evidence", {"missing_evidence"}),
        ("contradiction,missing_evidence", {"contradiction", "missing_evidence"}),
        (" missing_evidence , contradiction ", {"contradiction", "missing_evidence"}),
    ],
)
def test_parse_disable(value, expected):
    assert parse_disable(value) == frozenset(expected)


@pytest.mark.parametrize(
    "value,message",
    [
        ("", "give gate names separated by commas"),
        ("contradiction,", "give gate names separated by commas"),
        ("age", r"cannot disable \['age'\]"),
        ("contradiction,contradiction", "names a gate twice"),
    ],
)
def test_parse_disable_refuses(value, message):
    with pytest.raises(ValueError, match=message):
        parse_disable(value)


def test_ablation_name_is_sorted_and_joined_with_plus():
    assert ablation_name(frozenset({"missing_evidence", "contradiction"})) == (
        "contradiction+missing_evidence"
    )


def test_ablate_run_re_decides_every_trace_as_one_simulated_run():
    cases, traces = run()
    out = ablate_run(traces, cases, disable=CONTRA, auto_process=None, run_id="run_abl")
    assert [t.case_id for t in out] == ["T-01", "T-02", "T-03"]
    assert [t.action for t in out] == [AUTO, INFO, REVIEW]
    assert {t.run_id for t in out} == {"run_abl"}
    assert {t.mode for t in out} == {"simulated"}
    assert {tuple(t.ablation) for t in out} == {("contradiction",)}
    assert [t.replay_of for t in out] == [t.trace_id for t in traces]
    assert [t.decisions for t in out] == [t.decisions for t in traces]
    assert [t.ablation for t in traces] == [None, None, None]  # the source is untouched


def test_ablate_run_applies_the_operating_point_first():
    cases, traces = run()
    both = frozenset({"contradiction", "missing_evidence"})
    out = ablate_run(traces, cases, disable=both, auto_process=0.9)
    assert [t.action for t in out] == [AUTO, AUTO, AUTO]
    assert {t.thresholds.version for t in out} == {"v0.1+at0.9"}
    assert {tuple(t.ablation) for t in out} == {("contradiction", "missing_evidence")}
    assert out[0].run_id.startswith("run_")


def test_ablate_run_refuses_bad_input():
    cases, traces = run()
    with pytest.raises(ValueError, match="nothing to disable"):
        ablate_run(traces, cases, disable=frozenset(), auto_process=None)
    with pytest.raises(ValueError, match="unknown ablation"):
        ablate_run(traces, cases, disable=frozenset({"age"}), auto_process=None)
    once = ablate_run(traces, cases, disable=CONTRA, auto_process=None)
    with pytest.raises(ValueError, match="is already ablated"):
        ablate_run(once, cases, disable=CONTRA, auto_process=None)
    with pytest.raises(EvalError, match="missing"):
        ablate_run(traces, [*cases, make_case("T-04")], disable=CONTRA, auto_process=None)


def test_the_bundle_manifest_records_ablation_and_extra_keys(tmp_path):
    cases, traces = run()
    out = ablate_run(traces, cases, disable=CONTRA, auto_process=0.9, run_id="run_abl")
    trace_path, manifest_path = write_simulated_bundle(
        tmp_path / "abl",
        out,
        dataset=tmp_path / "ds",
        source=traces,
        extra={"auto_process": 0.9},
    )
    raw = json.loads(manifest_path.read_text())
    manifest = RunManifest.model_validate(raw)
    assert (manifest.mode, manifest.source_run_id, manifest.ablation) == (
        "simulated",
        "run_test",
        ["contradiction"],
    )
    assert raw["auto_process"] == 0.9
    assert raw["thresholds"]["version"] == "v0.1+at0.9"
    assert [t.ablation for t in read_traces(trace_path)] == [["contradiction"]] * 3


def test_an_unablated_bundle_has_no_ablation_and_no_extra_keys(tmp_path):
    cases, traces = run()
    _, manifest_path = write_simulated_bundle(
        tmp_path / "plain", traces, dataset=tmp_path / "ds", source=traces
    )
    raw = json.loads(manifest_path.read_text())
    assert raw["ablation"] is None
    assert "auto_process" not in raw
