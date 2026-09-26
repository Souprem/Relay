"""Pipeline check on gold-v0.1: the ground-truth provider must reproduce every derived action."""

import json
from collections import Counter

from typer.testing import CliRunner

from relay.cli import app
from tests.gold_support import GOLD_DIR, INTENDED

runner = CliRunner()


def test_groundtruth_eval_on_gold_is_perfect(tmp_path):
    result = runner.invoke(
        app,
        [
            "--env-file",
            str(tmp_path / "missing.env"),
            "eval",
            "--dataset",
            str(GOLD_DIR),
            "--provider",
            "groundtruth",
            "--traces-dir",
            str(tmp_path / "traces"),
            "--reports-dir",
            str(tmp_path / "reports"),
            "--results-dir",
            str(tmp_path / "results"),
        ],
    )
    assert result.exit_code == 0, result.output
    results = json.loads(next((tmp_path / "results").glob("*.json")).read_text())
    actions = Counter(row.action for row in INTENDED.values())
    assert results["dataset_id"] == "gold-v0.1"
    assert results["n_cases"] == 100
    assert results["correct_actions"] == 100
    assert results["unsafe_automation_count"] == 0
    assert results["auto_process_count"] == actions["AUTO_PROCESS"]
    assert results["request_info_count"] == actions["REQUEST_INFO"]
    assert results["human_review_count"] == actions["HUMAN_REVIEW"]
