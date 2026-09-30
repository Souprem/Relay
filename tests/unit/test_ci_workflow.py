"""The CI workflow: parses as YAML, runs the offline gates in order, and references no secrets."""

import json
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"
GATES = REPO / "evals" / "regression" / "gates.json"


def load():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def job(name: str):
    return load()["jobs"][name]


def steps(name: str = "offline-gates"):
    return job(name)["steps"]


def runs(name: str = "offline-gates") -> list[str]:
    return [step.get("run", "") for step in steps(name)]


def test_it_runs_on_push_and_pull_request():
    data = load()
    triggers = data.get("on", data.get(True))  # YAML 1.1 reads a bare `on` key as True
    assert set(triggers) == {"push", "pull_request"}


def test_it_uses_ubuntu_uv_and_python_3_12():
    assert job("offline-gates")["runs-on"] == "ubuntu-latest"
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
        "--dataset-id gen-v0.3-dev",
        "--dataset-id gen-v0.3-holdout",
        "--dataset-id gen-v0.3-shift",
        "--verify evals/generated/manifests/gen-v0.3-dev.json",
        "--verify evals/generated/manifests/gen-v0.3-holdout.json",
        "--verify evals/generated/manifests/gen-v0.3-shift.json",
        "regression --config evals/regression/gates.json --strict-generated --out regression-report",
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


def test_the_gen_v0_3_regeneration_flags_match_the_committed_manifests():
    commands = " ".join("\n".join(runs()).replace("\\\n", " ").split())
    for name in ("gen-v0.3-dev", "gen-v0.3-holdout", "gen-v0.3-shift"):
        manifest = json.loads((REPO / "evals/generated/manifests" / f"{name}.json").read_text())
        assert manifest["generator_version"] == "gen-v0.3"
        policy = manifest.get("policy_version", "v0.1")
        flags = (
            f"--out evals/generated/{name} --count {manifest['count']} --seed {manifest['seed']} "
            f"--dataset-id {name} --generator gen-v0.3"
        )
        if policy != "v0.1":
            flags += f" --policy {policy}"
        assert flags + " --manifests-dir" in commands, name


def test_the_regression_gate_step_uses_strict_generated():
    """I2: a requires_generated gate whose dataset is missing (a typo, a rename, a failed or
    dropped regeneration step) must be an ERROR, not a silently green SKIPPED, in CI."""
    commands = " ".join("\n".join(runs()).replace("\\\n", " ").split())
    assert "regression --config evals/regression/gates.json --strict-generated" in commands


def test_every_requires_generated_gate_dataset_is_regenerated_in_ci():
    """I2 (test half): ties gates.json's requires_generated datasets to the --out directories
    this workflow actually regenerates, so --strict-generated (the enforcement half) has
    something real to check against — a typo or a future rename in either file fails this."""
    commands = " ".join("\n".join(runs()).replace("\\\n", " ").split())
    regenerated = set(re.findall(r"--out (evals/generated/[\w.-]+) --count", commands))
    assert regenerated  # the regex actually matched something
    gates = json.loads(GATES.read_text(encoding="utf-8"))["gates"]
    requires_generated = [g for g in gates if g.get("requires_generated")]
    assert requires_generated  # there is at least one such gate to check
    for gate in requires_generated:
        assert gate["dataset"] in regenerated, gate["name"]


def test_the_regression_report_is_uploaded_even_on_failure():
    [upload] = [s for s in steps() if s.get("uses", "").startswith("actions/upload-artifact@")]
    assert upload["if"] == "always()"
    assert upload["with"]["path"] == "regression-report/"


def test_no_secrets_are_referenced():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text
    for name in load()["jobs"]:
        assert "env" not in job(name)


def test_it_has_an_offline_gates_and_a_web_job():
    assert set(load()["jobs"]) == {"offline-gates", "web"}


def test_the_web_job_uses_ubuntu_uv_node_22_and_the_committed_data():
    assert job("web")["runs-on"] == "ubuntu-latest"
    [setup] = [s for s in steps("web") if s.get("uses", "").startswith("astral-sh/setup-uv@")]
    assert setup["with"]["python-version"] == "3.12"
    [node_setup] = [s for s in steps("web") if s.get("uses", "").startswith("actions/setup-node@")]
    assert node_setup["with"]["node-version"] == "22"
    assert node_setup["with"]["cache"] == "npm"
    assert node_setup["with"]["cache-dependency-path"] == "web/package-lock.json"


def test_the_web_job_steps_run_in_order():
    commands = "\n".join(runs("web"))
    expected = [
        "uv sync --frozen",
        "uv run python -m scripts.prepare_dashboard",
        "export-site --out web/public/data",
        "npm ci",
        "npm run typecheck",
        "npm run lint",
        "npm test",
        "npm run build",
    ]
    positions = [commands.index(fragment) for fragment in expected]
    assert positions == sorted(positions)


def test_the_web_job_exports_site_data_offline():
    commands = "\n".join(runs("web"))
    assert (
        "uv run relay --env-file .no-such.env export-site --out web/public/data --strict-generated"
    ) in commands


def test_the_web_job_builds_with_the_pages_base_path():
    [build] = [s for s in steps("web") if s.get("run", "").strip() == "npm run build"]
    assert build.get("env", {}).get("NEXT_PUBLIC_BASE_PATH") == "/Relay"


def test_the_web_job_steps_run_in_the_web_directory():
    for name in ("npm ci", "npm run typecheck", "npm run lint", "npm test", "npm run build"):
        [step] = [s for s in steps("web") if s.get("run", "").strip() == name]
        assert step.get("working-directory") == "web"
