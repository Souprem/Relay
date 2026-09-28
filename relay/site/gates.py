"""gates.json for the site: the committed CI gates, the regression demos and the shadow demos.

The gates run exactly as `relay regression --config evals/regression/gates.json` runs them
(run_regression, offline). A gate whose generated dataset is not on disk is SKIPPED, as in the
CLI, unless strict_generated is set. The shadow demos re-issue committed gold decisions with
replay_run, apply the incumbent to a throwaway status file, and hash that file before and after
the shadow run, the check behind the CLI's "case state unchanged (verified)".
"""

import dataclasses
import tempfile
from pathlib import Path
from typing import Any

from relay.evaluation.regression import CaseEntry, RegressionResult
from relay.evaluation.regression_run import (
    CandidateSpec,
    RegressionInputError,
    RegressionRequest,
    load_gates,
    run_regression,
)
from relay.evaluation.shadow import build_shadow_report
from relay.evaluation.tracediff import original_label, replay_run
from relay.site.common import ExportContext, ExportError, rate_json, read_json, write_json
from relay.site.registry import GATES_CONFIG, RESULTS_URL, WAIVER_EXAMPLE
from relay.workflow.status import StatusStoreError, apply_transitions, state_digest

GOLD = "evals/gold"
GOLD_JEV = "evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz"
GOLD_JEV_ID = "run_20260925T170857Z_b95be9"
GOLD_CLAUDE_ID = "run_20260926T011730Z_f1852f"
COMMITTED_REPORTS = (
    (
        "holdout-adoption",
        "q-v0.2 to q-v0.3 on gen-v0.3-holdout",
        "evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/regression.json",
        "The adoption gate: q-v0.2 at its gen-v0.3-dev threshold (0.97) against q-v0.3 at 0.81, "
        "run once on the holdout.",
    ),
    (
        "stale-to-aware",
        "Stale to aware on gen-v0.3-shift",
        "evals/baselines/gen-v0.3-shift/regression-stale-to-aware/regression.json",
        "The same stored Jev answers composed under the old policy (stale) and under "
        "immunara-v0.2 (aware).",
    ),
)
STATE_VERIFIED = "case state unchanged (verified)"


def _entry(entry: CaseEntry) -> dict[str, Any]:
    return {
        "case_id": entry.case_id,
        "expected": entry.expected.value,
        "action_baseline": entry.action_baseline.value,
        "action_candidate": entry.action_candidate.value,
        "answer_changed": entry.answer_changed,
        "crossed_gated": entry.crossed_gated,
    }


def _side(result: RegressionResult, side: str) -> dict[str, Any]:
    metrics = getattr(result, side)
    return {
        "label": metrics.label,
        "n": metrics.n,
        "correct": rate_json(metrics.correct),
        "automation": rate_json(metrics.automation),
        "request_info": rate_json(metrics.request_info),
        "human_review": rate_json(metrics.human_review),
        "uar": rate_json(metrics.uar),
    }


def regression_json(
    result: RegressionResult, *, key: str, title: str, description: str, source: str
) -> dict[str, Any]:
    """A RegressionResult without the parts that depend on the machine (paths, git SHAs)."""
    return {
        "key": key,
        "title": title,
        "description": description,
        "source": source,
        "dataset": result.dataset_id,
        "n": result.n,
        "baseline": _side(result, "baseline"),
        "candidate": _side(result, "candidate"),
        "change_counts": result.change_counts,
        "newly_unsafe": [_entry(e) for e in result.newly_unsafe],
        "waived": [
            _entry(w.entry) | {"waiver": w.waiver.model_dump(mode="json")} for w in result.waived
        ],
        "still_unsafe": [_entry(e) for e in result.still_unsafe],
        "unsafe_resolved": [_entry(e) for e in result.unsafe_resolved],
        "regressed": [_entry(e) for e in result.regressed],
        "improved": len(result.improved),
        "verdict": result.verdict,
        "failures": result.failures,
        "exit_code": result.exit_code,
    }


def _rooted(repo: Path, request: RegressionRequest) -> RegressionRequest:
    """The request with every path resolved against the repository root."""
    candidate = request.candidate
    if candidate.traces is not None:
        candidate = candidate.model_copy(update={"traces": str(repo / candidate.traces)})
    return dataclasses.replace(
        request,
        dataset=repo / request.dataset,
        baseline=repo / request.baseline,
        waivers=None if request.waivers is None else repo / request.waivers,
        candidate=candidate,
    )


def _run(repo: Path, request: RegressionRequest) -> RegressionResult:
    try:
        return run_regression(_rooted(repo, request)).result
    except RegressionInputError as error:
        raise ExportError(f"regression {request.gate or request.baseline}: {error}") from error


def gate_rows(repo: Path, *, strict_generated: bool) -> list[dict[str, Any]]:
    try:
        gates = load_gates(repo / GATES_CONFIG).gates
    except RegressionInputError as error:
        raise ExportError(str(error)) from error
    rows = []
    for spec in gates:
        row: dict[str, Any] = {
            "name": spec.name,
            "dataset": spec.dataset,
            "kind": "reproduce" if spec.candidate.reproduce else "compare",
            "requires_generated": spec.requires_generated,
        }
        if spec.requires_generated and not (repo / spec.dataset).is_dir():
            note = f"dataset not generated; run relay generate to create {spec.dataset}"
            if strict_generated:
                raise ExportError(f"gate {spec.name}: {note}")
            rows.append(row | {"verdict": "SKIPPED", "note": note})
            continue
        result = _run(repo, RegressionRequest.from_gate(spec))
        rows.append(
            row
            | {
                "verdict": result.verdict,
                "note": None,
                "n": result.n,
                "baseline": result.baseline.label,
                "candidate": result.candidate.label,
                "newly_unsafe": len(result.newly_unsafe),
                "still_unsafe": len(result.still_unsafe),
                "waived": len(result.waived),
                "regressed": len(result.regressed),
                "exit_code": result.exit_code,
            }
        )
    return rows


def regression_reports(repo: Path) -> list[dict[str, Any]]:
    fail = RegressionRequest(
        dataset=Path(GOLD), baseline=Path(GOLD_JEV), candidate=CandidateSpec(at=0.89)
    )
    reports = [
        regression_json(
            _run(repo, fail),
            key="gold-fail",
            title="Jev at 0.89 on gold",
            description="Jev's gold decisions, recorded at 0.95, re-decided at its dev-selected "
            "0.89. GOLD-TMP-17 becomes an automation of a case that needs human review.",
            source="relay regression --dataset evals/gold --baseline "
            f"{GOLD_JEV} --candidate-at 0.89",
        ),
        regression_json(
            _run(repo, dataclasses.replace(fail, waivers=Path(WAIVER_EXAMPLE))),
            key="gold-waiver",
            title="The same change with a reviewed waiver",
            description="An example waiver names GOLD-TMP-17, the reviewer and the reason. The "
            "gate passes and still lists the waived case.",
            source=f"... --candidate-at 0.89 --waivers {WAIVER_EXAMPLE}",
        ),
    ]
    gates = {g.name: g for g in load_gates(repo / GATES_CONFIG).gates}
    reports.append(
        regression_json(
            _run(repo, RegressionRequest.from_gate(gates["gold-jev-vs-claude"])),
            key="gold-jev-vs-claude",
            title="Jev against Claude on gold",
            description="Each provider at its own dev-selected threshold. Both automate "
            "GOLD-TMP-17, so it is STILL UNSAFE, not a new failure.",
            source="gate gold-jev-vs-claude in evals/regression/gates.json",
        )
    )
    for key, title, path, description in COMMITTED_REPORTS:
        result = RegressionResult.model_validate(read_json(repo / path))
        reports.append(
            regression_json(result, key=key, title=title, description=description, source=path)
        )
    return reports


def shadow_demo(
    ctx: ExportContext,
    *,
    key: str,
    title: str,
    description: str,
    incumbent_run: str,
    incumbent_at: float | None,
    candidate_run: str,
    candidate_at: float,
) -> dict[str, Any]:
    cases = ctx.dataset_cases["gold-v0.1"]
    incumbent = replay_run(
        ctx.loaded_runs[incumbent_run].recorded,
        cases,
        policy_id=None,
        auto_process=incumbent_at,
        mode="simulated",
        run_id=f"site-{key}-incumbent",
    )
    with tempfile.TemporaryDirectory() as tmp:
        state = Path(tmp) / "case-status.json"
        try:
            apply_transitions(state, incumbent)
        except StatusStoreError as error:
            raise ExportError(f"shadow demo {key}: {error}") from error
        before = state_digest(state)
        shadow = replay_run(
            ctx.loaded_runs[candidate_run].recorded,
            cases,
            policy_id=None,
            auto_process=candidate_at,
            mode="shadow",
            run_id=f"site-{key}-shadow",
        )
        report = build_shadow_report(
            incumbent,
            shadow,
            cases,
            incumbent_label=f"simulated {original_label(incumbent[0])}",
            candidate_label=f"shadow {original_label(shadow[0])}",
        )
        verified = state_digest(state) == before
    agreement = report.agreement
    return {
        "key": key,
        "title": title,
        "description": description,
        "dataset": report.dataset_id,
        "n": report.n,
        "incumbent": f"{ctx.loaded_runs[incumbent_run].spec.label} @"
        f"{incumbent[0].thresholds.auto_process:g}",
        "candidate": f"{ctx.loaded_runs[candidate_run].spec.label} @{candidate_at:g}",
        "proposals": len(shadow),
        "state_verified": verified,
        "state_line": STATE_VERIFIED if verified else "SHADOW VIOLATION",
        "agreement": {
            "agreed": rate_json(agreement.agreed),
            "matrix": {
                a.value: {b.value: n for b, n in row.items()} for a, row in agreement.matrix.items()
            },
            "newly_auto": agreement.newly_auto,
            "stopped_auto": agreement.stopped_auto,
        },
        "decision": report.decision,
        "failures": report.promotion.failures,
        "newly_unsafe": [e.case_id for e in report.promotion.newly_unsafe],
        "still_unsafe": [e.case_id for e in report.promotion.still_unsafe],
    }


def export_gates(
    repo: Path, out: Path, ctx: ExportContext, *, strict_generated: bool
) -> list[Path]:
    payload = {
        "gates": gate_rows(repo, strict_generated=strict_generated),
        "regressions": regression_reports(repo),
        "shadow": [
            shadow_demo(
                ctx,
                key="promote",
                title="Claude shadows Jev: PROMOTE",
                description="The incumbent is Jev at 0.89. Claude at 0.55 runs in shadow; its "
                "proposals are recorded and never applied.",
                incumbent_run=GOLD_JEV_ID,
                incumbent_at=0.89,
                candidate_run=GOLD_CLAUDE_ID,
                candidate_at=0.55,
            ),
            shadow_demo(
                ctx,
                key="hold",
                title="Jev at a lower threshold: HOLD",
                description="The incumbent is Jev at the recorded 0.95. The same decisions at "
                "0.89 would auto-process GOLD-TMP-17, so the rollout is held.",
                incumbent_run=GOLD_JEV_ID,
                incumbent_at=None,
                candidate_run=GOLD_JEV_ID,
                candidate_at=0.89,
            ),
        ],
        "links": {
            "regression": f"{RESULTS_URL}#regression-gate",
            "shadow": f"{RESULTS_URL}#shadow-mode",
        },
    }
    return [write_json(out / "gates.json", payload)]
