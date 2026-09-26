"""The CI workflow: parses as YAML, runs the offline gates in order, and references no secrets."""

import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"


def load():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def steps():
    [job] = load()["jobs"].values()
    return job["steps"]


def runs() -> list[str]:
    return [step.get("run", "") for step in steps()]


def test_it_runs_on_push_and_pull_request():
    data = load()
    triggers = data.get("on", data.get(True))  # YAML 1.1 reads a bare `on` key as True
    assert set(triggers) == {"push", "pull_request"}


def test_it_uses_ubuntu_uv_and_python_3_12():
    [job] = load()["jobs"].values()
    assert job["runs-on"] == "ubuntu-latest"
    [setup] = [s for s in steps() if s.get("uses", "").startswith("astral-sh/setup-uv@")]
    assert setup["with"]["python-version"] == "3.12"


def test_the_steps_run_in_order():
    commands = "\n".join(runs())
    expected = [
        "uv sync --frozen",
        "uv run ruff check .",
        "uv run ruff format --check .",
        "uv run pytest -q",
        "--dataset-id gen-v0.2-dev",
        "--dataset-id gen-v0.2-holdout",
        "--verify evals/generated/manifests/gen-v0.2-dev.json",
        "--verify evals/generated/manifests/gen-v0.2-holdout.json",
        "regression --config evals/regression/gates.json --out regression-report",
    ]
    positions = [commands.index(fragment) for fragment in expected]
    assert positions == sorted(positions)


def test_the_regeneration_flags_match_the_committed_manifests():
    commands = " ".join("\n".join(runs()).replace("\\\n", " ").split())
    for name in ("gen-v0.2-dev", "gen-v0.2-holdout"):
        manifest = json.loads((REPO / "evals/generated/manifests" / f"{name}.json").read_text())
        assert (
            f"--out evals/generated/{name} --count {manifest['count']} --seed {manifest['seed']} "
            f"--dataset-id {name}"
        ) in commands


def test_the_regression_report_is_uploaded_even_on_failure():
    [upload] = [s for s in steps() if s.get("uses", "").startswith("actions/upload-artifact@")]
    assert upload["if"] == "always()"
    assert upload["with"]["path"] == "regression-report/"


def test_no_secrets_are_referenced():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text
    [job] = load()["jobs"].values()
    assert "env" not in job
    assert all("env" not in step for step in steps())
