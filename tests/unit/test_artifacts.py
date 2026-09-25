import csv
import json

from relay.evaluation.artifacts import (
    BUNDLE_FILES,
    CALIBRATION_CSV_FIELDS,
    calibration_csv,
    write_eval_bundle,
)
from relay.evaluation.calibration import calibrate_run
from relay.evaluation.confusion import confusion_matrices
from relay.evaluation.frontier import run_sweep
from relay.evaluation.metrics import run_identity, score_run
from relay.reporting import (
    DISCLAIMER,
    LOW_BIN_N,
    REPORT_SECTIONS,
    render_eval_report,
    render_identity_markdown,
)
from tests.factories import make_bundle, make_case, make_trace, make_truth

GROUND_TRUTH_FIELDS = (
    "ground_truth",
    "diagnosis_supported",
    "step_therapy_satisfied",
    "contradiction_present",
)


def sample():
    cases = [
        make_case("A"),
        make_case("B", truth=make_truth(contradiction_present=True)),
        make_case("C", truth=make_truth(step_therapy_satisfied=False)),
    ]
    bundles = [
        make_bundle("A").model_copy(update={"client_version": "typesafe-sdk==0.7.1"}),
        make_bundle("B", contra=0.9),
        make_bundle("C", step=0.2),
    ]
    traces = [
        make_trace(c, b).model_copy(update={"policy_text_hash": "sha256:policy"})
        for c, b in zip(cases, bundles, strict=True)
    ]
    return traces, cases


def parts(traces, cases, at=None):
    return {
        "identity": run_identity(traces, dataset_hash="sha256:dataset"),
        "summary": score_run(traces, cases),
        "calibration": calibrate_run(traces, cases),
        "confusion": confusion_matrices(traces, cases),
        "sweep": run_sweep(traces, cases, at=at),
    }


def test_run_identity_collects_versions_from_traces():
    traces, _ = sample()
    identity = run_identity(traces, dataset_hash="sha256:dataset")
    assert identity.run_id == "run_test" and identity.dataset_id == "test"
    assert identity.dataset_hash == "sha256:dataset"
    assert identity.provider_versions == ["test-v1"]
    assert identity.client_versions == ["typesafe-sdk==0.7.1"]  # None values are dropped
    assert identity.question_set_versions == ["q-test"]
    assert identity.policy_text_hashes == ["sha256:policy"]
    assert identity.thresholds_versions == ["v0.1"]
    assert identity.relay_git_shas == ["abc123"]


def test_identity_markdown_without_a_manifest():
    traces, _ = sample()
    lines = render_identity_markdown(run_identity(traces))
    assert "- Dataset: `test` (no dataset manifest)" in lines


def test_report_has_every_section_in_order_and_no_ground_truth_fields():
    traces, cases = sample()
    p = parts(traces, cases, at=0.9)
    report = render_eval_report(
        p["identity"], p["summary"], p["calibration"], p["confusion"], p["sweep"]
    )
    assert report.startswith("# Relay evaluation report — run_test")
    assert DISCLAIMER in report
    positions = [report.index(header) for header in REPORT_SECTIONS]
    assert positions == sorted(positions)
    assert "manifest hash `sha256:dataset`" in report
    assert "policy text hash `sha256:policy`" in report
    assert "client `typesafe-sdk==0.7.1`" in report
    assert "Correct action rate" in report and "Cases (expected -> actual)" not in report
    assert "### material_contradiction" in report
    assert f"low n (< {LOW_BIN_N})" in report  # 3 predictions per decision
    assert "| 0.90 |" in report and "--at" in report
    assert "Selection rule:" in report
    assert "independent" in report  # step-therapy approximation in Limitations
    for field in GROUND_TRUTH_FIELDS:
        assert field not in report, field


def test_calibration_csv_header_is_stable():
    traces, cases = sample()
    text = calibration_csv(calibrate_run(traces, cases))
    header, *rows = text.splitlines()
    assert header == "decision,lower,upper,n,mean_confidence,accuracy,gap"
    assert header.split(",") == list(CALIBRATION_CSV_FIELDS)
    assert len(rows) == 4 * 5 + 6  # four yes/no decisions x 5 bins + missing_evidence x 6 bins
    assert rows[0] == "diagnosis_support,0.5,0.6,0,,,"


def test_write_eval_bundle_writes_all_files(tmp_path):
    traces, cases = sample()
    out = tmp_path / "bundle"
    paths = write_eval_bundle(out, **parts(traces, cases))
    assert (
        [p.name for p in paths]
        == list(BUNDLE_FILES)
        == [
            "summary.json",
            "calibration.json",
            "calibration.csv",
            "frontier.csv",
            "confusion.json",
            "report.md",
        ]
    )
    assert all(p.parent == out and p.stat().st_size > 0 for p in paths)
    summary = json.loads((out / "summary.json").read_text())
    assert set(summary) == {
        "identity",
        "summary",
        "ceiling",
        "selection_rule",
        "selected",
        "at_point",
    }
    assert summary["summary"]["n_cases"] == 3
    assert summary["identity"]["dataset_hash"] == "sha256:dataset"
    calibration = json.loads((out / "calibration.json").read_text())
    assert list(calibration["decisions"]) == [
        "diagnosis_support",
        "step_therapy",
        "documentation_complete",
        "material_contradiction",
        "missing_evidence",
    ]
    confusion = json.loads((out / "confusion.json").read_text())
    assert confusion["material_contradiction"]["counts"] == [[1, 0], [0, 2]]
    frontier = list(csv.DictReader((out / "frontier.csv").open()))
    assert len(frontier) == 50
    for field in GROUND_TRUTH_FIELDS:
        assert field not in (out / "report.md").read_text()
