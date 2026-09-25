import gzip
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from relay.traces.models import RunManifest
from relay.traces.store import (
    TraceStore,
    current_git_sha,
    new_run_id,
    new_trace_id,
    read_traces,
)
from tests.factories import make_case, make_trace


def manifest(run_id="run_x", trace_file="traces/run_x.jsonl"):
    return RunManifest(
        run_id=run_id,
        created_at=datetime(2026, 9, 24, tzinfo=UTC),
        dataset_id="test",
        dataset_path="evals/test",
        provider="test",
        policy_version="v0.1",
        case_count=1,
        trace_file=trace_file,
        relay_git_sha=None,
    )


def test_ids_have_expected_shape():
    assert re.fullmatch(r"run_\d{8}T\d{6}Z_[0-9a-f]{6}", new_run_id())
    assert new_run_id(datetime(2026, 9, 24, 23, 15, tzinfo=UTC)).startswith("run_20260924T231500Z_")
    assert re.fullmatch(r"tr_[0-9a-f]{32}", new_trace_id())
    assert new_trace_id() != new_trace_id()


def test_create_refuses_to_reuse_a_run_file(tmp_path):
    TraceStore.create(tmp_path, "run_x")
    with pytest.raises(FileExistsError):
        TraceStore.create(tmp_path, "run_x")


def test_append_and_read_round_trip(tmp_path):
    store = TraceStore.create(tmp_path, "run_x")
    first = make_trace(make_case("T-01"))
    second = make_trace(make_case("T-02"))
    store.append(first)
    before = store.path.read_text()
    store.append(second)
    assert store.path.read_text().startswith(before)
    assert read_traces(store.path) == [first, second]


def test_trace_json_contains_no_ground_truth(tmp_path):
    store = TraceStore.create(tmp_path, "run_x")
    store.append(make_trace(make_case()))
    text = store.path.read_text()
    assert "ground_truth" not in text
    assert "diagnosis_supported" not in text


def test_manifest_is_written_once(tmp_path):
    store = TraceStore.create(tmp_path, "run_x")
    path = store.write_manifest(manifest())
    assert path.name == "run_x.manifest.json"
    assert RunManifest.model_validate_json(path.read_text()).run_id == "run_x"
    with pytest.raises(FileExistsError):
        store.write_manifest(manifest())


def test_run_manifest_question_set_version_defaults_to_none():
    """C4: optional so a pre-C4 manifest (no such key) still validates."""
    assert manifest().question_set_version is None


def test_committed_manifests_without_question_set_version_still_load():
    for path in (
        REPO
        / "evals"
        / "baselines"
        / "smoke-v0.1"
        / "run_20260925T042324Z_eee114"
        / "run_20260925T042324Z_eee114.manifest.json",
        REPO
        / "evals"
        / "baselines"
        / "gen-v0.2-dev"
        / "run_20260925T071157Z_d6b218"
        / "run-manifest.json",
    ):
        assert "question_set_version" not in path.read_text()
        assert RunManifest.model_validate_json(path.read_text()).question_set_version is None


def test_current_git_sha_in_repo():
    sha = current_git_sha()
    assert sha is None or re.fullmatch(r"[0-9a-f]{40}(-dirty)?", sha)


def test_current_git_sha_outside_repo(tmp_path):
    assert current_git_sha(tmp_path) is None


REPO = Path(__file__).resolve().parents[2]
SMOKE_BASELINE = (
    REPO
    / "evals"
    / "baselines"
    / "smoke-v0.1"
    / "run_20260925T042324Z_eee114"
    / "run_20260925T042324Z_eee114.jsonl"
)


def test_gzipped_trace_file_round_trips(tmp_path):
    traces = [make_trace(make_case("T-01")), make_trace(make_case("T-02"))]
    path = tmp_path / "traces.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for trace in traces:
            handle.write(trace.model_dump_json() + "\n")
    assert read_traces(path) == traces


def test_corrupt_gzip_is_a_value_error_naming_the_file(tmp_path):
    path = tmp_path / "broken.jsonl.gz"
    path.write_bytes(b"this is not gzip data")
    with pytest.raises(ValueError, match="broken.jsonl.gz"):
        read_traces(path)


def test_committed_v0_1_baseline_still_loads_without_new_fields():
    traces = read_traces(SMOKE_BASELINE)
    assert len(traces) == 10
    assert all(t.policy_text_hash is None for t in traces)
    assert all(t.decisions.client_version is None for t in traces)
