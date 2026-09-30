"""The home page's "What we found" block, built from numbers the export already reads.

Every figure comes from a committed artifact: the headline run payloads, the gold traces loaded
for the case pages, the committed regression and shadow reports, the ablation summary, and the
spend ledgers. Each finding carries its sentences as text segments (a figure may carry a tone,
"unsafe" or "correct", the only two colours the site gives a finding) and the raw figures, so a
test can check both against the artifacts. README.md's "What I found" quotes the same strings.
"""

from decimal import Decimal
from pathlib import Path
from typing import Any

from relay.cases.policies import load_policy
from relay.evaluation.labels import expected_action
from relay.evaluation.regression import RegressionResult
from relay.evaluation.tracediff import classify
from relay.site.common import ExportContext, ExportError, rate_display, read_json, trace_for
from relay.site.registry import RESULTS_URL, run_spec

HOLDOUT_V3_JEV = "run_20260927T072144Z_12e1e4"
HOLDOUT_V2_JEV = "run_20260925T075242Z_fd455f"
HOLDOUT_V2_RULES = "run_20260925T092425Z_0aee97"
GOLD_V2_JEV = "run_20260925T170857Z_b95be9"
GOLD_V3_JEV = "run_20260927T072623Z_ad6f44"
GOLD_CLAUDE = "run_20260926T011730Z_f1852f"
HOLDOUT_V2_V3_BASELINE = "run_20260927T072249Z_204814"  # q-v0.2 re-decided on gen-v0.3-holdout
DESIGN_FLAW_CASE = "GOLD-TMP-17"

QV03_HOLDOUT = "evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/regression.json"
QV03_GOLD = "evals/baselines/gold-v0.1/regression-q-v0.2-vs-q-v0.3/regression.json"
ABLATION = "evals/baselines/ablation/summary.json"
SHIFT_REGRESSION = "evals/baselines/gen-v0.3-shift/regression-stale-to-aware/regression.json"
SHIFT_SHADOW = "evals/baselines/gen-v0.3-shift/shadow-stale-to-aware/shadow.json"
CLAUDE_SPEND = "evals/baselines/claude-spend.json"
JEV_SPEND = "evals/baselines/jev-spend-3d.json"
MODEL_PROVIDERS = ("jev", "claude")


def _t(text: str, tone: str | None = None) -> dict[str, Any]:
    return {"text": text, "tone": tone}


def _txt(r: dict[str, Any]) -> str:
    """ "244/1000 (24.4%)", formatted exactly as the README and RESULTS.md print a rate."""
    return str(rate_display(r)["text"])


def _frac(r: dict[str, Any]) -> str:
    return f"{r['count']}/{r['n']}"


def _metrics(ctx: ExportContext, run_id: str) -> dict[str, Any]:
    return ctx.run_payloads[run_id]["metrics"]


def _at(ctx: ExportContext, run_id: str) -> str:
    return f"{ctx.run_payloads[run_id]['operating_point']['auto_process']:g}"


def _regression(repo: Path, path: str) -> RegressionResult:
    return RegressionResult.model_validate(read_json(repo / path))


def _run_cost(repo: Path, ledger: str, run_id: str) -> Decimal:
    entries = [e for e in read_json(repo / ledger).get("entries", []) if e["run_id"] == run_id]
    if len(entries) != 1:
        raise ExportError(f"{ledger}: expected one entry for {run_id}, found {len(entries)}")
    return Decimal(entries[0]["cost_usd"])


def _link(href: str, label: str) -> dict[str, str]:
    return {"href": href, "label": label}


def gating_finding(ctx: ExportContext) -> dict[str, Any]:
    v3 = _metrics(ctx, HOLDOUT_V3_JEV)
    v2 = _metrics(ctx, HOLDOUT_V2_JEV)
    rules = _metrics(ctx, HOLDOUT_V2_RULES)
    return {
        "id": "gating",
        "title": "Confidence gating automated about a quarter of held-out cases with no "
        "unsafe approvals observed.",
        "body": [
            _t(f"Jev q-v0.3 at {_at(ctx, HOLDOUT_V3_JEV)} on gen-v0.3-holdout auto-processed "),
            _t(_txt(v3["automation"])),
            _t(" of cases, "),
            _t(f"{_frac(v3['uar'])} unsafe", "correct"),
            _t(
                f" (95% upper bound {rate_display(v3['uar'])['ci_high_pct']}), and chose the "
                "correct action for "
            ),
            _t(_txt(v3["correct"]), "correct"),
            _t(". On gen-v0.2-holdout the rules baseline automated "),
            _t(_txt(rules["automation"])),
            _t(" with "),
            _t(_txt(rules["correct"])),
            _t(" correct, against "),
            _t(_txt(v2["automation"])),
            _t(" and "),
            _t(_txt(v2["correct"])),
            _t(" for Jev q-v0.2. The cases are synthetic and template-generated."),
        ],
        "link": _link(f"/evals/{HOLDOUT_V3_JEV}/", "The holdout run"),
        "source": f"{RESULTS_URL}#baselines",
        "figures": {
            "jev_q_v0_3": {
                "run_id": HOLDOUT_V3_JEV,
                "auto_process": ctx.run_payloads[HOLDOUT_V3_JEV]["operating_point"]["auto_process"],
                "automation": v3["automation"],
                "uar": v3["uar"],
                "correct": v3["correct"],
            },
            "jev_q_v0_2": {
                "run_id": HOLDOUT_V2_JEV,
                "automation": v2["automation"],
                "correct": v2["correct"],
            },
            "rules": {
                "run_id": HOLDOUT_V2_RULES,
                "automation": rules["automation"],
                "correct": rules["correct"],
            },
        },
    }


def _gold_verdict(ctx: ExportContext, run_id: str, case_id: str) -> str:
    trace = trace_for(ctx.loaded_runs[run_id].at_op, case_id)
    case = next(c for c in ctx.dataset_cases["gold-v0.1"] if c.input.id == case_id)
    return classify(
        trace.action, expected_action(case, load_policy(trace.policy_id), trace.thresholds)
    )


def design_flaw_finding(repo: Path, ctx: ExportContext) -> dict[str, Any]:
    verdicts = {
        run_id: _gold_verdict(ctx, run_id, DESIGN_FLAW_CASE)
        for run_id in (GOLD_V2_JEV, GOLD_CLAUDE, GOLD_V3_JEV)
    }
    if verdicts != {GOLD_V2_JEV: "UNSAFE", GOLD_CLAUDE: "UNSAFE", GOLD_V3_JEV: "correct"}:
        raise ExportError(
            f"{DESIGN_FLAW_CASE}: the design-flaw finding no longer holds: {verdicts}"
        )
    holdout = _regression(repo, QV03_HOLDOUT)
    gold = _regression(repo, QV03_GOLD)
    newly = [e.case_id for e in gold.newly_unsafe]
    before = run_spec(HOLDOUT_V2_V3_BASELINE).operating_point
    after = run_spec(GOLD_V3_JEV).operating_point
    return {
        "id": "design-flaw",
        "title": "The evaluation loop found a real design flaw, and the fix held on a fresh "
        "holdout.",
        "body": [
            _t(f"{DESIGN_FLAW_CASE}, an interrupted methotrexate course, was auto-approved "),
            _t("unsafely", "unsafe"),
            _t(
                f" by both Jev q-v0.2 at {_at(ctx, GOLD_V2_JEV)} and Claude at "
                f"{_at(ctx, GOLD_CLAUDE)}. The cause was the question design: q-v0.2 asks for "
                "one start date and one end date, so a paused course reads as one long course. "
                "q-v0.3 adds questions about pauses and restarts; on gen-v0.3-holdout, run once, "
                "correct actions went from "
            ),
            _t(f"{holdout.baseline.correct.count}"),
            _t(" to "),
            _t(f"{holdout.candidate.correct.count} of {holdout.n}", "correct"),
            _t(". Gold is not a blind test for this change, and on gold "),
            _t(", ".join(newly) + " became newly unsafe", "unsafe"),
            _t(f" when the threshold dropped from {before:g} to {after:g}."),
        ],
        "link": _link(f"/cases/{DESIGN_FLAW_CASE}/", DESIGN_FLAW_CASE),
        "source": f"{RESULTS_URL}#question-set-q-v03-interrupted-courses",
        "figures": {
            "case": DESIGN_FLAW_CASE,
            "verdicts": verdicts,
            "holdout_correct": {
                "baseline": holdout.baseline.correct.count,
                "candidate": holdout.candidate.correct.count,
                "n": holdout.n,
            },
            "gold_newly_unsafe": newly,
            "thresholds": {"before": before, "after": after},
        },
    }


def contradiction_finding(repo: Path) -> dict[str, Any]:
    rows = read_json(repo / ABLATION)
    gold = [
        r
        for r in rows
        if r["dataset"] == "gold-v0.1"
        and r["ablation"] == "contradiction"
        and r["provider"].split()[0] in MODEL_PROVIDERS
    ]
    unsafe_sets = {tuple(r["newly_unsafe"]) for r in gold}
    if len(unsafe_sets) != 1 or not gold:
        raise ExportError(f"{ABLATION}: the gold contradiction rows disagree: {unsafe_sets}")
    [cases] = unsafe_sets

    def holdout(dataset: str, run: str) -> dict[str, Any]:
        [row] = [
            r
            for r in rows
            if r["dataset"] == dataset and r["run"] == run and r["ablation"] == "contradiction"
        ]
        return row

    v2 = holdout("gen-v0.2-holdout", "jev-q-v0.2")
    v3 = holdout("gen-v0.3-holdout", "jev-q-v0.3")
    missing = [r for r in rows if r["ablation"] == "missing_evidence"]
    unchanged = all(
        r["automation"]["baseline"]["count"] == r["automation"]["ablated"]["count"]
        and r["uar"]["baseline"]["count"] == r["uar"]["ablated"]["count"]
        and not r["newly_unsafe"]
        for r in missing
    )
    if not unchanged:
        raise ExportError(f"{ABLATION}: a missing-evidence ablation changed an automation")

    def auto(row: dict[str, Any]) -> str:
        a = row["automation"]
        return f"{a['baseline']['count']} to {a['ablated']['count']} of {a['ablated']['n']}"

    return {
        "id": "contradiction-gate",
        "title": "The contradiction gate is doing real work, and it has a cost.",
        "body": [
            _t("With contradiction detection disabled, "),
            _t(" and ".join(cases) + " become newly unsafe", "unsafe"),
            _t(
                f" on gold for all {len(gold)} model configurations. On the holdouts it only costs "
                f"automation: Jev q-v0.2 goes from {auto(v2)} automated and Jev q-v0.3 from "
                f"{auto(v3)}, still "
            ),
            _t(
                f"{_frac(v2['uar']['ablated'])} and {_frac(v3['uar']['ablated'])} unsafe", "correct"
            ),
            _t(
                f". Disabling the missing-evidence gate changed no automation and no unsafe count "
                f"in any of the {len(missing)} runs, a null result."
            ),
        ],
        "link": _link("/experiments/#ablation", "The ablation"),
        "source": f"{RESULTS_URL}#gate-ablation",
        "figures": {
            "gold_newly_unsafe": list(cases),
            "gold_model_providers": len(gold),
            "holdout": {
                "jev_q_v0_2": {"automation": v2["automation"], "uar": v2["uar"]},
                "jev_q_v0_3": {"automation": v3["automation"], "uar": v3["uar"]},
            },
            "missing_evidence_runs": len(missing),
            "missing_evidence_changed_automation": not unchanged,
        },
    }


def shift_finding(repo: Path) -> dict[str, Any]:
    result = _regression(repo, SHIFT_REGRESSION)
    decision = read_json(repo / SHIFT_SHADOW)["decision"]
    stale, aware = result.baseline.uar, result.candidate.uar
    return {
        "id": "policy-shift",
        "title": "Policy-aware logic matters when the policy changes.",
        "body": [
            _t(
                f"Under immunara-v0.2's new 12-month recency rule, on {result.n} cases, the same "
                "stored Jev answers composed under the old policy gave "
            ),
            _t(f"{stale.count}/{stale.n} unsafe automations", "unsafe" if stale.count else None),
            _t(" and under the new policy "),
            _t(f"{aware.count}/{aware.n}", "correct" if not aware.count else "unsafe"),
            _t(f". The stale-to-aware gate passes, and shadow mode recommends {decision}."),
        ],
        "link": _link("/experiments/#shift", "The policy shift"),
        "source": f"{RESULTS_URL}#policy-shift-immunara-v02",
        "figures": {
            "n": result.n,
            "stale_uar": stale.model_dump(mode="json"),
            "aware_uar": aware.model_dump(mode="json"),
            "gate": result.verdict,
            "shadow_decision": decision,
        },
    }


def frontier_finding(repo: Path, ctx: ExportContext) -> dict[str, Any]:
    claude = _metrics(ctx, GOLD_CLAUDE)
    jev = _metrics(ctx, GOLD_V2_JEV)
    claude_cost = _run_cost(repo, CLAUDE_SPEND, GOLD_CLAUDE)
    jev_cost = _run_cost(repo, JEV_SPEND, GOLD_V3_JEV)
    c, j = rate_display(claude["correct"]), rate_display(jev["correct"])
    return {
        "id": "frontier-llm",
        "title": "The gold comparison does not establish a clear model winner.",
        "body": [
            _t("On gold, with the same questions, Claude got "),
            _t(f"{claude['correct']['count']}/{claude['correct']['n']}"),
            _t(f" correct with {claude['automation']['count']} automated and "),
            _t(f"{claude['uar']['count']} unsafe", "unsafe" if claude["uar"]["count"] else None),
            _t("; Jev q-v0.2 got "),
            _t(f"{jev['correct']['count']}/{jev['correct']['n']}"),
            _t(f" with {jev['automation']['count']} automated and "),
            _t(f"{jev['uar']['count']} unsafe", "unsafe" if jev["uar"]["count"] else None),
            _t(
                f". The 95% intervals on correct actions ({c['ci_text']} and {j['ci_text']}) overlap. "
                f"This {claude['correct']['n']}-case comparison does not establish equivalence or "
                "a clear winner. Claude's gold run cost "
                f"${claude_cost:.2f} at batch prices; Jev's q-v0.3 gold run, with more questions "
                f"per case, cost ${jev_cost:.4f}."
            ),
        ],
        "link": _link("/evals/", "Every run"),
        "source": f"{RESULTS_URL}#gold-set",
        "figures": {
            "claude": {
                "run_id": GOLD_CLAUDE,
                "correct": claude["correct"],
                "automation": claude["automation"],
                "uar": claude["uar"],
                "cost_usd": str(claude_cost),
            },
            "jev_q_v0_2": {
                "run_id": GOLD_V2_JEV,
                "correct": jev["correct"],
                "automation": jev["automation"],
                "uar": jev["uar"],
            },
            "jev_q_v0_3_cost_usd": str(jev_cost),
        },
    }


def build_hero(ctx: ExportContext) -> dict[str, Any]:
    """The home page's three headline figures: Jev q-v0.3 on gen-v0.3-holdout at its operating
    point. Values and captions are display strings, so the page never formats a number."""
    payload = ctx.run_payloads[HOLDOUT_V3_JEV]
    m = payload["metrics"]
    automation, uar, correct = m["automation"], m["uar"], m["correct"]
    return {
        "run_id": HOLDOUT_V3_JEV,
        "label": payload["label"],
        "dataset": payload["dataset"],
        "n": payload["n"],
        "auto_process": payload["operating_point"]["auto_process"],
        "figures": [
            {
                "id": "automation",
                "value": rate_display(automation)["pct"],
                "label": "of held-out cases auto-processed",
                "caption": f"{automation['count']} of {automation['n']} cases",
            },
            {
                "id": "unsafe",
                "value": f"{uar['count']} of {uar['n']}",
                "label": "unsafe automations observed",
                "caption": f"95% upper bound {rate_display(uar)['ci_high_pct']}",
            },
            {
                "id": "correct",
                "value": rate_display(correct)["pct"],
                "label": "chose the correct action",
                "caption": f"{correct['count']} of {correct['n']} cases",
            },
        ],
    }


def build_findings(repo: Path, ctx: ExportContext) -> list[dict[str, Any]]:
    return [
        gating_finding(ctx),
        design_flaw_finding(repo, ctx),
        contradiction_finding(repo),
        shift_finding(repo),
        frontier_finding(repo, ctx),
    ]
