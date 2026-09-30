"""The GitHub Pages deploy workflow: parses as YAML, builds and deploys the static dashboard
export offline, and references no secrets."""

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "pages.yml"


def load():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def job(name: str):
    return load()["jobs"][name]


def steps(name: str = "build"):
    return job(name)["steps"]


def runs(name: str = "build") -> list[str]:
    return [step.get("run", "") for step in steps(name)]


def test_it_triggers_on_push_to_main_and_workflow_dispatch():
    data = load()
    triggers = data.get("on", data.get(True))  # YAML 1.1 reads a bare `on` key as True
    assert set(triggers) == {"push", "workflow_dispatch"}
    assert triggers["push"]["branches"] == ["main"]


def test_it_has_the_pages_permissions():
    permissions = load()["permissions"]
    assert permissions == {"contents": "read", "pages": "write", "id-token": "write"}


def test_it_has_a_non_cancelling_pages_concurrency_group():
    concurrency = load()["concurrency"]
    assert concurrency["group"] == "pages"
    assert concurrency["cancel-in-progress"] is False


def test_it_has_a_build_and_a_deploy_job():
    assert set(load()["jobs"]) == {"build", "deploy"}


def test_the_build_job_uses_ubuntu_uv_python_3_12_and_node_22():
    assert job("build")["runs-on"] == "ubuntu-latest"
    [setup] = [s for s in steps() if s.get("uses", "").startswith("astral-sh/setup-uv@")]
    assert setup["with"]["python-version"] == "3.12"
    [node_setup] = [s for s in steps() if s.get("uses", "").startswith("actions/setup-node@")]
    assert node_setup["with"]["node-version"] == "22"
    assert node_setup["with"]["cache"] == "npm"
    assert node_setup["with"]["cache-dependency-path"] == "web/package-lock.json"


def test_the_build_job_steps_run_in_order():
    commands = "\n".join(runs())
    uses = [s.get("uses", "") for s in steps()]
    expected_runs = [
        "uv sync --frozen",
        "uv run python -m scripts.prepare_dashboard",
        "export-site --out web/public/data",
        "npm ci",
        "npm run build",
        "touch web/out/.nojekyll",
    ]
    positions = [commands.index(fragment) for fragment in expected_runs]
    assert positions == sorted(positions)

    checkout_pos = next(i for i, u in enumerate(uses) if u.startswith("actions/checkout@"))
    configure_pos = next(i for i, u in enumerate(uses) if u.startswith("actions/configure-pages@"))
    upload_pos = next(
        i for i, u in enumerate(uses) if u.startswith("actions/upload-pages-artifact@")
    )
    assert checkout_pos < configure_pos < upload_pos


def test_export_site_requires_verified_generated_datasets():
    commands = "\n".join(runs())
    assert "uv run python -m scripts.prepare_dashboard" in commands
    assert (
        "uv run relay --env-file .no-such.env export-site --out web/public/data --strict-generated"
    ) in commands


def test_the_build_step_uses_the_pages_base_path():
    [build] = [s for s in steps() if s.get("run", "").strip() == "npm run build"]
    assert build.get("env", {}).get("NEXT_PUBLIC_BASE_PATH") == "/Relay"


def test_the_web_steps_run_in_the_web_directory():
    for name in ("npm ci", "npm run build"):
        [step] = [s for s in steps() if s.get("run", "").strip() == name]
        assert step.get("working-directory") == "web"


def test_the_upload_pages_artifact_step_points_at_the_static_export():
    [upload] = [
        s for s in steps() if s.get("uses", "").startswith("actions/upload-pages-artifact@")
    ]
    assert upload["with"]["path"] == "web/out"


def test_the_deploy_job_needs_build_and_uses_the_github_pages_environment():
    deploy = job("deploy")
    assert deploy["needs"] == "build"
    assert deploy["environment"]["name"] == "github-pages"
    assert deploy["environment"]["url"] == "${{ steps.deployment.outputs.page_url }}"
    [deploy_step] = [
        s for s in deploy["steps"] if s.get("uses", "").startswith("actions/deploy-pages@")
    ]
    assert deploy_step["id"] == "deployment"


def test_no_secrets_are_referenced():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text
    for name in load()["jobs"]:
        assert "env" not in job(name)
