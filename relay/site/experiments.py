"""experiments.json for the site: the q-v0.3 fix, the policy shift, parallelism and the ablation.

Everything is read from committed artifacts (regression reports, the bench record, the ablation
summary, report bundles). The interrupted-course breakdown is the one exception: it needs the
generated gen-v0.3 case folders, so it runs scripts/phase3d_course_split.py's functions when those
folders exist and is marked skipped otherwise.
"""

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from relay.evaluation.regression import RegressionResult
from relay.site.common import ExportError, read_json, write_json
from relay.site.gates import regression_json
from relay.site.registry import CLAUDE_150, CLAUDE_150_NOTE, RESULTS_URL

QV03_REPORTS = (
    ("dev", "evals/baselines/gen-v0.3-dev/regression-q-v0.2-vs-q-v0.3/regression.json"),
    ("holdout", "evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/regression.json"),
    ("gold", "evals/baselines/gold-v0.1/regression-q-v0.2-vs-q-v0.3/regression.json"),
)
COURSE_SPLIT = (
    (
        "gen-v0.3-dev",
        "evals/generated/gen-v0.3-dev",
        "evals/baselines/gen-v0.3-dev/run_20260927T071846Z_e950c0/traces.jsonl.gz",
        "evals/baselines/gen-v0.3-dev/run_20260927T071912Z_cdaf0c/traces.jsonl.gz",
    ),
    (
        "gen-v0.3-holdout",
        "evals/generated/gen-v0.3-holdout",
        "evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz",
        "evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz",
    ),
)
COURSE_TAGS = ("interrupted", "old_course", "other")
SHIFT_REGRESSION = "evals/baselines/gen-v0.3-shift/regression-stale-to-aware/regression.json"
SHIFT_SHADOW = "evals/baselines/gen-v0.3-shift/shadow-stale-to-aware/shadow.json"
SHIFT_RULES_SUMMARY = (
    "evals/baselines/gen-v0.3-shift/run_20260927T073019Z_81a068/report/summary.json"
)
BENCH = "evals/baselines/bench/parallelism.json"
ABLATION = "evals/baselines/ablation/summary.json"


def _regression(repo: Path, path: str) -> RegressionResult:
    return RegressionResult.model_validate(read_json(repo / path))


def _course_split_module(repo: Path) -> ModuleType:
    path = repo / "scripts" / "phase3d_course_split.py"
    spec = importlib.util.spec_from_file_location("relay_site_course_split", path)
    if spec is None or spec.loader is None:
        raise ExportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def course_split(repo: Path, *, strict_generated: bool) -> list[dict[str, Any]]:
    """step_therapy accuracy by course type (interrupted / old course / other), q-v0.2 vs q-v0.3,
    via scripts/phase3d_course_split.py. Skipped per dataset when its case folders are absent
    (an ExportError instead with strict_generated)."""
    rows = []
    module: ModuleType | None = None
    for dataset, folder, baseline, candidate in COURSE_SPLIT:
        dataset_dir = repo / folder
        if not dataset_dir.is_dir():
            note = f"dataset not generated; run relay generate to create {folder}"
            if strict_generated:
                raise ExportError(f"course split {dataset}: {note}")
            rows.append({"dataset": dataset, "status": "skipped", "note": note})
            continue
        module = module or _course_split_module(repo)
        tags = module.tag_dataset(dataset_dir)
        before = module.accuracy_by_tag(dataset_dir, tags, module.load_traces(repo / baseline))
        after = module.accuracy_by_tag(dataset_dir, tags, module.load_traces(repo / candidate))
        rows.append(
            {
                "dataset": dataset,
                "status": "ok",
                "n": len(tags),
                "tags": [
                    {
                        "tag": tag,
                        "n": before.get(tag, (0, 0))[1],
                        "q_v0_2": list(before.get(tag, (0, 0))),
                        "q_v0_3": list(after.get(tag, (0, 0))),
                    }
                    for tag in COURSE_TAGS
                ],
            }
        )
    return rows


def qv03_section(repo: Path, *, strict_generated: bool) -> dict[str, Any]:
    reports = {
        key: regression_json(
            _regression(repo, path),
            key=f"qv03-{key}",
            title=f"q-v0.2 to q-v0.3 on {key}",
            description="",
            source=path,
        )
        for key, path in QV03_REPORTS
    }
    return {
        "title": "The q-v0.3 fix",
        "link": f"{RESULTS_URL}#question-set-q-v03-interrupted-courses",
        "reports": reports,
        "course_split": course_split(repo, strict_generated=strict_generated),
    }


def shift_section(repo: Path) -> dict[str, Any]:
    result = _regression(repo, SHIFT_REGRESSION)
    shadow = read_json(repo / SHIFT_SHADOW)
    rules = read_json(repo / SHIFT_RULES_SUMMARY)["summary"]
    return {
        "title": "Policy shift",
        "link": f"{RESULTS_URL}#policy-shift-immunara-v02",
        "regression": regression_json(
            result,
            key="shift",
            title="Stale to aware",
            description="",
            source=SHIFT_REGRESSION,
        ),
        "shadow_decision": shadow["decision"],
        "rules": {
            "n": rules["n_cases"],
            "correct": rules["correct_actions"],
            "automation": rules["auto_process_count"],
            "unsafe": rules["unsafe_automation_count"],
        },
    }


def parallelism_section(repo: Path) -> dict[str, Any]:
    bench = read_json(repo / BENCH)
    return {
        "title": "Parallelism",
        "link": f"{RESULTS_URL}#parallelism-narrow-decisions-per-call",
        "dataset": bench["dataset_id"],
        "cases": bench["case_count"],
        "model": bench["model"],
        "sizes": [
            {
                "size": s["size"],
                "calls": s["calls"],
                "errors": s["errors"],
                "p50_ms": s["latency_ms_p50"],
                "p95_ms": s["latency_ms_p95"],
                "mean_ms": s["latency_ms_mean"],
                "input_tokens_mean": s["input_tokens_mean"],
                "cost_per_case_usd": s["cost_per_case_usd"],
            }
            for s in bench["sizes"]
        ],
        "total_cost_usd": bench["total_cost_usd"],
    }


def ablation_section(repo: Path) -> dict[str, Any]:
    rows = read_json(repo / ABLATION)
    return {
        "title": "Gate ablation",
        "link": f"{RESULTS_URL}#gate-ablation",
        "rows": [
            {
                "dataset": r["dataset"],
                "run": r["run"],
                "provider": r["provider"],
                "thresholds": r["thresholds"],
                "ablation": r["ablation"],
                "verdict": r["verdict"],
                "n": r["n"],
                "actions_changed": r["actions_changed"],
                "newly_unsafe": r["newly_unsafe"],
                "regressed": r["regressed"],
                "improved": r["improved"],
                "automation": r["automation"],
                "uar": r["uar"],
                "note": CLAUDE_150_NOTE if r["run"] == CLAUDE_150 else None,
            }
            for r in rows
        ],
    }


def export_experiments(repo: Path, out: Path, *, strict_generated: bool) -> list[Path]:
    payload = {
        "qv03": qv03_section(repo, strict_generated=strict_generated),
        "shift": shift_section(repo),
        "parallelism": parallelism_section(repo),
        "ablation": ablation_section(repo),
    }
    return [write_json(out / "experiments.json", payload)]
