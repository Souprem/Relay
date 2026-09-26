"""Human-readable output: run table and report, eval summary, frontier, and the eval report."""

from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Any

from relay.cases.models import CaseInput
from relay.decisions.base import DecisionBundle, DecisionId
from relay.evaluation.calibration import CalibrationReport, RunCalibration
from relay.evaluation.compare import Comparison
from relay.evaluation.confusion import ConfusionMatrix
from relay.evaluation.frontier import SELECTION_RULE, FrontierPoint, SweepResult
from relay.evaluation.metrics import EvalSummary, RunIdentity
from relay.evaluation.tracediff import GateDelta, TraceDiff, classify
from relay.traces.models import RunManifest, WorkflowTrace
from relay.workflow.outcomes import WorkflowAction

DISCLAIMER = (
    "Relay uses synthetic data only and is an engineering/evaluation prototype. "
    "It is not for clinical use or real authorization decisions."
)
GROUNDTRUTH_NOTE = "groundtruth provider: pipeline validation, not a model result."
RULES_NOTE = (
    "rules provider: deterministic pattern-matching baseline; probabilities are 0, 0.5 or 1 "
    "and are not calibrated."
)
CLAUDE_NOTE = (
    "claude provider: conventional LLM baseline (claude-opus-5, structured outputs); its "
    "probabilities are self-reported, and refusal fallbacks are disabled, so a refusal goes to "
    "HUMAN_REVIEW."
)
_LABEL_WIDTH = 26


def _p(bundle: DecisionBundle, qid: DecisionId) -> str:
    decision = bundle.get(qid)
    return f"{decision.p_yes:.2f}" if decision and decision.p_yes is not None else "-"


def _money(value: Decimal | None) -> str:
    return "unavailable" if value is None else f"${value:.7f}"


def _cache_text(s: EvalSummary) -> str:
    if s.cache_read_share is None:
        return "n/a"
    return f"{s.cache_read_share:.1%} of prompt tokens"


def _latency_count(s: EvalSummary) -> int:
    """Cases with a recorded latency (every case, for results written before latency_n)."""
    return s.n_cases if s.latency_n is None else s.latency_n


def _latency_unavailable(s: EvalSummary) -> str:
    return "unavailable (batch)" if "batch" in s.execution_modes else "unavailable"


def _latency_partial(s: EvalSummary) -> str:
    if _latency_count(s) < s.n_cases:
        return f" (measured on {_latency_count(s)} of {s.n_cases} cases)"
    return ""


def render_run_table(traces: Sequence[WorkflowTrace]) -> str:
    header = (
        f"{'CASE':<10}{'ACTION':<14}{'DIAG':>6}{'STEP':>6}{'DOCS':>6}{'CONTRA':>8}  "
        f"{'MISSING':<28}REASON"
    )
    rows = [header, "-" * len(header)]
    for t in traces:
        b = t.decisions
        missing = b.get(DecisionId.MISSING_EVIDENCE)
        missing_text = f"{missing.answer} ({missing.probability:.2f})" if missing else "-"
        reason = t.decision_reasons[0] if t.decision_reasons else ""
        if len(reason) > 70:
            reason = reason[:67] + "..."
        rows.append(
            f"{t.case_id:<10}{t.action:<14}{_p(b, DecisionId.DIAGNOSIS_SUPPORT):>6}"
            f"{_p(b, DecisionId.STEP_THERAPY):>6}{_p(b, DecisionId.DOCUMENTATION_COMPLETE):>6}"
            f"{_p(b, DecisionId.MATERIAL_CONTRADICTION):>8}  {missing_text:<28}{reason}"
        )
    return "\n".join(rows)


def _range(candidate: Mapping[str, Any]) -> str:
    if candidate["earliest"] == candidate["latest"]:
        return str(candidate["earliest"])
    return f"{candidate['earliest']}..{candidate['latest']}"


def _case_section(trace: WorkflowTrace, case: CaseInput) -> list[str]:
    b = trace.decisions
    out = ["", f"## {trace.case_id} — {trace.action}", "", "**Why:**"]
    out += [f"- {reason}" for reason in trace.decision_reasons]
    out += [
        "",
        f"Provider `{b.provider}` · model `{b.provider_version}` · latency "
        f"{'unavailable' if b.latency_ms is None else f'{b.latency_ms} ms'} · "
        f"cost {_money(b.estimated_cost_usd)}",
        "",
    ]
    if b.error:
        out += [f"**Provider error:** {b.error}", ""]
    if b.decisions:
        out += ["| Decision | Result |", "|---|---|"]
        for d in b.decisions:
            if d.kind == "yes_no":
                result = f"p(yes) = {d.p_yes:.3f}"
            else:
                result = f"{d.answer} (p = {d.probability:.3f})"
            out.append(f"| {d.question_id} | {result} |")
        out.append("")
    step = b.derivations.get("step_therapy")
    if step:
        out += [
            "**Step-therapy derivation:**",
            f"- P(duration >= {step['min_days']} days) = {step['p_duration']:.3f}",
            f"- P(inadequate response documented) = {step['p_inadequate_response']:.3f}",
            f"- step_therapy p(yes) = {step['p_yes']:.3f}",
        ]
        for label, key in (("Start", "start_candidates"), ("End", "end_candidates")):
            top = sorted(step[key], key=lambda c: -c["probability"])[:3]
            text = ", ".join(f"{_range(c)} ({c['probability']:.2f})" for c in top)
            out.append(f"- {label} date candidates: {text or 'none resolved'}")
        out.append("")
    fired = b.derivations.get("rules")
    if fired:
        out.append("**Rules fired:**")
        for f in fired:
            where = f"{f['document_id']}:{f['line']}" if f["document_id"] else "structured field"
            out.append(f"- `{f['rule']}` ({where}): {f['match']}")
        out.append("")
    duration = b.derivations.get("duration")
    if duration:
        min_days = duration["min_days"]
        out += [
            f"Duration: {duration['start'] or 'unknown'} -> {duration['end'] or 'unknown'} "
            f"({duration['days'] if duration['days'] is not None else 'unknown'} days, "
            f"need >= {min_days})",
            "",
        ]
    out.append("**Policy gates:**")
    out += [
        f"- {'FIRED' if g.fired else 'passed'} `{g.gate}` — {g.detail}" for g in trace.gate_path
    ]
    out += ["", "**Documents:**"]
    for doc in case.documents:
        out += ["", f"_{doc.id}_ ({doc.kind})", "", "```text", doc.text.rstrip(), "```"]
    return out


def _distinct(values: Iterable[str | None], missing: str = "unknown") -> str:
    present = sorted({v for v in values if v is not None})
    return ", ".join(present) if present else missing


def render_run_report(
    manifest: RunManifest, traces: Sequence[WorkflowTrace], cases: Mapping[str, CaseInput]
) -> str:
    lines = [
        f"# Relay run report — {manifest.run_id}",
        "",
        f"> {DISCLAIMER}",
        "",
        f"- Dataset: `{manifest.dataset_id}` ({manifest.dataset_path})",
        f"- Provider: `{manifest.provider}`",
        f"- Policy version: `{manifest.policy_version}`",
        f"- Policy text hash: `{_distinct(t.policy_text_hash for t in traces)}`",
        f"- Question set: `{_distinct(t.question_set_version for t in traces)}`",
        f"- Client: `{_distinct((t.decisions.client_version for t in traces), 'n/a')}`",
        f"- Cases: {manifest.case_count}",
        f"- Relay commit: `{manifest.relay_git_sha or 'unknown'}`",
        f"- Traces: `{manifest.trace_file}`",
        "",
    ]
    if manifest.provider == "groundtruth":
        lines += [f"**{GROUNDTRUTH_NOTE}** Decisions come from labels, not a model.", ""]
    if manifest.provider == "rules":
        lines += [f"**{RULES_NOTE}**", ""]
    if manifest.provider == "claude":
        lines += [f"**{CLAUDE_NOTE}**", ""]
    lines += ["| Case | Action | First reason |", "|---|---|---|"]
    for t in traces:
        first = t.decision_reasons[0] if t.decision_reasons else ""
        lines.append(f"| {t.case_id} | {t.action} | {first} |")
    for t in traces:
        lines += _case_section(t, cases[t.case_id])
    return "\n".join(lines) + "\n"


def _rate(count: int, n: int) -> str:
    return f"{count}/{n} ({count / n:.1%})" if n else "unavailable"


def _row(label: str, value: str) -> str:
    return f"  {label:<{_LABEL_WIDTH}}{value}"


def render_eval_summary(s: EvalSummary, *, include_cases: bool = True) -> str:
    lines = [
        f"Relay eval — run {s.run_id}",
        f"provider {s.provider} ({', '.join(s.provider_versions)}) · policy {s.policy_version} · "
        f"dataset {s.dataset_id} · n={s.n_cases}",
    ]
    if s.provider == "groundtruth":
        lines.append(f"NOTE: {GROUNDTRUTH_NOTE}")
    if s.auto_process_count:
        uar = _rate(s.unsafe_automation_count, s.auto_process_count)
    else:
        uar = "n/a (no AUTO_PROCESS actions)"
    if s.latency_p50_ms is None or s.latency_p95_ms is None:
        latency = _latency_unavailable(s)
    else:
        latency = f"{s.latency_p50_ms} ms / {s.latency_p95_ms} ms" + _latency_partial(s)
        if s.latency_low_sample:
            latency += f"  [low-sample: n={_latency_count(s)} < 30]"
    if s.total_cost_usd is None or s.cost_per_case_usd is None:
        cost = "unavailable"
    else:
        cost = f"{_money(s.total_cost_usd)} total, {_money(s.cost_per_case_usd)} per case"
    lines += [
        _row("Correct action rate", _rate(s.correct_actions, s.n_cases)),
        _row("Automation rate", _rate(s.auto_process_count, s.n_cases)),
        _row("Request-info rate", _rate(s.request_info_count, s.n_cases)),
        _row("Human escalation rate", _rate(s.human_review_count, s.n_cases)),
        _row("Unsafe automation rate", uar),
        _row("Invalid outputs", str(s.invalid_outputs)),
        *([_row("Refusals", str(s.refusals))] if s.refusals is not None else []),
        _row("Latency p50 / p95", latency),
        _row("Cost", cost),
        *([_row("Prompt cache reads", _cache_text(s))] if s.cache_read_share is not None else []),
        "",
        "Per-question accuracy (yes/no at p >= 0.5; choice by top answer):",
    ]
    for question, accuracy in s.per_question_accuracy.items():
        lines.append(_row(question, "unavailable" if accuracy is None else f"{accuracy:.1%}"))
    if not include_cases:
        return "\n".join(lines)
    lines += ["", "Cases (expected -> actual):"]
    for c in s.cases:
        flags = "ok" if c.correct else "MISS"
        if c.unsafe_automation:
            flags += "  UNSAFE AUTO"
        if c.invalid_output:
            flags += "  INVALID OUTPUT"
        lines.append(f"  {c.case_id:<10}{c.expected_action:<14}-> {c.action:<14}{flags}")
    return "\n".join(lines)


FRONTIER_HEADERS: tuple[str, ...] = (
    "auto_process >=",
    "AUTO",
    "Automation",
    "Unsafe / auto (UAR)",
    "Human review",
    "Correct action",
    "Note",
)


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _threshold(value: float) -> str:
    """0.5 -> '0.50', 0.97 -> '0.97', 0.935 -> '0.935'."""
    text = f"{value:.4f}".rstrip("0")
    return text if len(text.split(".")[1]) >= 2 else f"{value:.2f}"


def frontier_rows(result: SweepResult) -> list[tuple[FrontierPoint, str]]:
    """Every 0.05 step, plus the selected and --at points, in threshold order."""
    chosen = {p.auto_threshold: p for p in result.points if round(p.auto_threshold * 100) % 5 == 0}
    notes: dict[float, list[str]] = {t: [] for t in chosen}
    for point, note in ((result.selected, "selected"), (result.at_point, "--at")):
        if point is not None:
            chosen.setdefault(point.auto_threshold, point)
            notes.setdefault(point.auto_threshold, []).append(note)
    return [(chosen[t], ", ".join(notes[t])) for t in sorted(chosen)]


def _frontier_cells(point: FrontierPoint, note: str) -> list[str]:
    uar = f"{point.unsafe}/{point.auto} ({_pct(point.uar)})" if point.auto else "n/a (no AUTO)"
    return [
        _threshold(point.auto_threshold),
        str(point.auto),
        _pct(point.automation_rate),
        uar,
        _pct(point.human_review_rate),
        _pct(point.correct_action_rate),
        note,
    ]


def describe_selection(result: SweepResult) -> str:
    ceiling = f"UAR <= {result.ceiling:.1%}"
    if result.selected is None:
        lines = [
            f"No threshold meets the ceiling ({ceiling} with at least one AUTO_PROCESS); "
            "nothing selected."
        ]
    else:
        p = result.selected
        lines = [
            f"Selected operating point: auto_process >= {_threshold(p.auto_threshold)} "
            f"(automation {_pct(p.automation_rate)}, UAR {p.unsafe}/{p.auto}, "
            f"correct action {_pct(p.correct_action_rate)}; ceiling {ceiling})"
        ]
    if result.frontier_flat:
        lines.append("Frontier is flat across all thresholds.")
    lines.append(
        "The UAR ceiling does not bind at any threshold."
        if not result.ceiling_binding
        else "The UAR ceiling binds: at least one automated threshold's UAR exceeds it."
    )
    return "\n".join(lines)


def render_frontier_table(result: SweepResult) -> str:
    widths = (16, 6, 12, 21, 14, 16, 0)
    n = result.points[0].n if result.points else 0
    lines = [
        f"Frontier — run {result.run_id} · dataset {result.dataset_id} · n={n}",
        "auto_process swept 0.50-0.99; every other threshold fixed at the run's version.",
        "".join(h.ljust(w) for h, w in zip(FRONTIER_HEADERS, widths, strict=True)).rstrip(),
    ]
    for point, note in frontier_rows(result):
        cells = _frontier_cells(point, note)
        lines.append("".join(c.ljust(w) for c, w in zip(cells, widths, strict=True)).rstrip())
    lines += ["", describe_selection(result), f"Rule: {SELECTION_RULE}."]
    return "\n".join(lines)


LOW_BIN_N = 20
REPORT_SECTIONS: tuple[str, ...] = (
    "## Run identity",
    "## Action metrics",
    "## Confusion matrices",
    "## Calibration",
    "## Automation/safety frontier",
    "## Latency and cost",
    "## Limitations",
)
LIMITATIONS: tuple[str, ...] = (
    "Synthetic data only. Generated documents come from fixed templates and phrase banks, so "
    "they exercise the policy logic and pipeline, not real-world document variety.",
    "Expected actions are derived from the generator's ground-truth facts through the same "
    "engine; they are not independent expert labels.",
    "Step therapy is composed from date parts treated as independent, which is an approximation.",
    "Generator and pipeline conventions apply: month-only dates are judged conservatively, and "
    "the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).",
    "Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset "
    "must be confirmed on held-out data.",
    "gen-v0.2 has a residual contradiction tell: a day-precision, non-split MTX "
    "medication-history line predicts a contradiction roughly 81% of the time (never 100%), "
    "and the NEVER_TAKEN_OTHER_DMARD distractor wording has a weak base-rate skew of its own. "
    "Both bear on material_contradiction metrics and on any rule-based baseline built from "
    "surface phrasing.",
)


def _num(value: float | None, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _ids(values: Sequence[str]) -> str:
    return ", ".join(f"`{v}`" for v in values) if values else "unknown"


def render_identity_markdown(identity: RunIdentity) -> list[str]:
    dataset = f"`{identity.dataset_id}`"
    if identity.dataset_hash:
        dataset += f" (manifest hash `{identity.dataset_hash}`)"
    else:
        dataset += " (no dataset manifest)"
    return [
        "## Run identity",
        "",
        f"- Run: `{identity.run_id}`",
        f"- Dataset: {dataset}",
        f"- Provider: `{identity.provider}` · model {_ids(identity.provider_versions)}"
        f" · client {_ids(identity.client_versions) if identity.client_versions else 'n/a'}",
        f"- Question set: {_ids(identity.question_set_versions)}"
        f" (hash {_ids(identity.question_set_hashes)})",
        f"- Policy version: {_ids(identity.policy_versions)}"
        f" · policy text hash {_ids(identity.policy_text_hashes)}",
        f"- Thresholds version: {_ids(identity.thresholds_versions)}",
        f"- Relay commit: {_ids(identity.relay_git_shas)}",
        "",
    ]


def render_confusion_markdown(matrices: Mapping[str, ConfusionMatrix]) -> list[str]:
    invalid = next(iter(matrices.values())).invalid_excluded if matrices else 0
    lines = [
        "## Confusion matrices",
        "",
        "Evaluation only: rows are the ground-truth answer, columns the provider's answer "
        "(yes/no at p_yes >= 0.5; the missing-evidence choice by its top answer). "
        f"Invalid bundles excluded: {invalid}.",
        "",
    ]
    for decision, m in matrices.items():
        lines += [
            f"### {decision}",
            "",
            "| truth / predicted | " + " | ".join(m.labels) + " |",
            "|---|" + "---|" * len(m.labels),
        ]
        for label, row in zip(m.labels, m.counts, strict=True):
            lines.append(f"| {label} | " + " | ".join(str(c) for c in row) + " |")
        lines.append("")
    return lines


def _calibration_table(decision: str, report: CalibrationReport) -> list[str]:
    lines = [
        f"### {decision}",
        "",
        f"n = {report.n} · Brier {_num(report.brier)} · ECE {_num(report.ece)}",
        "",
        "| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |",
        "|---|---|---|---|---|---|",
    ]
    for i, b in enumerate(report.bins):
        closing = "]" if i == len(report.bins) - 1 else ")"
        gap = None
        if b.accuracy is not None and b.mean_confidence is not None:
            gap = b.accuracy - b.mean_confidence
        flag = "empty" if b.n == 0 else (f"low n (< {LOW_BIN_N})" if b.n < LOW_BIN_N else "")
        lines.append(
            f"| [{b.lower:.1f}, {b.upper:.1f}{closing} | {b.n} | {_num(b.mean_confidence)} | "
            f"{_num(b.accuracy)} | {'—' if gap is None else f'{gap:+.3f}'} | {flag} |"
        )
    return lines + [""]


def render_calibration_markdown(calibration: RunCalibration) -> list[str]:
    lines = [
        "## Calibration",
        "",
        "Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the "
        "chosen answer for missing evidence. Calibration only means something on data that was "
        "not used to tune anything (held-out data). Bins with fewer than "
        f"{LOW_BIN_N} predictions are flagged: their accuracy is unreliable. "
        f"Invalid bundles excluded: {calibration.invalid_excluded}.",
        "",
        "Partial missing_evidence distributions (probabilities summing to less than 1; the "
        "unassigned mass counts as 0 on every label in the Brier score): "
        f"{calibration.partial_choice_distributions} of "
        f"{calibration.decisions[DecisionId.MISSING_EVIDENCE.value].n}.",
        "",
    ]
    for decision, report in calibration.decisions.items():
        lines += _calibration_table(decision, report)
    return lines


def render_frontier_markdown(result: SweepResult) -> list[str]:
    lines = [
        "## Automation/safety frontier",
        "",
        "Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays "
        "at the run's version. The engine is re-run on the stored decisions, so this costs no "
        f"API calls. Ceiling: unsafe automation rate <= {result.ceiling:.1%}. "
        f"Selection rule: {SELECTION_RULE}.",
        "",
        "| " + " | ".join(FRONTIER_HEADERS) + " |",
        "|" + "---|" * len(FRONTIER_HEADERS),
    ]
    for point, note in frontier_rows(result):
        lines.append("| " + " | ".join(_frontier_cells(point, note)) + " |")
    lines += [
        "",
        describe_selection(result),
        "",
        "The selection above is computed on this run's own data. For a held-out report, the "
        "threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample "
        "selection is shown for reference only.",
        "",
    ]
    return lines


def _latency_cost_markdown(s: EvalSummary) -> list[str]:
    if s.latency_p50_ms is None or s.latency_p95_ms is None:
        latency = _latency_unavailable(s)
    else:
        latency = f"p50 {s.latency_p50_ms} ms · p95 {s.latency_p95_ms} ms" + _latency_partial(s)
        if s.latency_low_sample:
            latency += f" (low sample: n={_latency_count(s)})"
    if s.total_cost_usd is None or s.cost_per_case_usd is None:
        cost = "unavailable"
    else:
        cost = f"{_money(s.total_cost_usd)} total · {_money(s.cost_per_case_usd)} per case"
    return ["## Latency and cost", "", f"- Latency: {latency}", f"- Estimated cost: {cost}", ""]


def render_eval_report(
    identity: RunIdentity,
    summary: EvalSummary,
    calibration: RunCalibration,
    confusion: Mapping[str, ConfusionMatrix],
    sweep: SweepResult,
) -> str:
    lines = [f"# Relay evaluation report — {identity.run_id}", "", f"> {DISCLAIMER}", ""]
    if identity.provider == "groundtruth":
        lines += [f"**{GROUNDTRUTH_NOTE}**", ""]
    lines += render_identity_markdown(identity)
    lines += [
        "## Action metrics",
        "",
        "```text",
        render_eval_summary(summary, include_cases=False),
        "```",
        "",
    ]
    lines += render_confusion_markdown(confusion)
    lines += render_calibration_markdown(calibration)
    lines += render_frontier_markdown(sweep)
    lines += _latency_cost_markdown(summary)
    lines += ["## Limitations", ""] + [f"- {item}" for item in LIMITATIONS]
    return "\n".join(lines) + "\n"


def _point_text(point: FrontierPoint | None) -> str:
    if point is None:
        return "none"
    return (
        f"{_threshold(point.auto_threshold)} (auto {_pct(point.automation_rate)}, "
        f"UAR {point.unsafe}/{point.auto})"
    )


def _latency_cell(s: EvalSummary) -> str:
    if s.latency_p50_ms is None or s.latency_p95_ms is None:
        return _latency_unavailable(s)
    return f"{s.latency_p50_ms} / {s.latency_p95_ms} ms" + _latency_partial(s)


def _comparison_rows(c: Comparison) -> list[list[str]]:
    rows = [
        ["Run"] + [r.identity.run_id for r in c.runs],
        ["Provider / model"]
        + [f"{r.identity.provider} {','.join(r.identity.provider_versions)}" for r in c.runs],
        ["Question set"] + [",".join(r.identity.question_set_versions) for r in c.runs],
        ["Correct action rate"]
        + [_rate(r.summary.correct_actions, r.summary.n_cases) for r in c.runs],
        ["Automation rate"]
        + [_rate(r.summary.auto_process_count, r.summary.n_cases) for r in c.runs],
        ["Unsafe automation rate"]
        + [
            _rate(r.summary.unsafe_automation_count, r.summary.auto_process_count)
            if r.summary.auto_process_count
            else "n/a (no AUTO)"
            for r in c.runs
        ],
        ["Request-info rate"]
        + [_rate(r.summary.request_info_count, r.summary.n_cases) for r in c.runs],
        ["Human escalation rate"]
        + [_rate(r.summary.human_review_count, r.summary.n_cases) for r in c.runs],
        ["Invalid outputs"] + [str(r.summary.invalid_outputs) for r in c.runs],
        ["Refusals"]
        + ["n/a" if r.summary.refusals is None else str(r.summary.refusals) for r in c.runs],
        ["Latency p50 / p95"] + [_latency_cell(r.summary) for r in c.runs],
        ["Cost per case"] + [_money(r.summary.cost_per_case_usd) for r in c.runs],
        ["Prompt cache reads"] + [_cache_text(r.summary) for r in c.runs],
        ["Partial missing_evidence distributions"]
        + [
            f"{r.calibration.partial_choice_distributions}/"
            f"{r.calibration.decisions[DecisionId.MISSING_EVIDENCE.value].n}"
            for r in c.runs
        ],
    ]
    for decision in c.runs[0].calibration.decisions:
        rows.append(
            [f"Brier / ECE {decision}"]
            + [
                f"{_num(r.calibration.decisions[decision].brier)} / "
                f"{_num(r.calibration.decisions[decision].ece)}"
                for r in c.runs
            ]
        )
    rows.append(
        [f"Selected (UAR <= {c.runs[0].sweep.ceiling:.1%})"]
        + [_point_text(r.sweep.selected) for r in c.runs]
    )
    if c.runs[0].sweep.at_point is not None:
        at = _threshold(c.runs[0].sweep.at_point.auto_threshold)
        rows.append([f"At {at}"] + [_point_text(r.sweep.at_point) for r in c.runs])
    return rows


def render_comparison(c: Comparison) -> str:
    header = ["Metric"] + [r.label for r in c.runs]
    rows = [header] + _comparison_rows(c)
    widths = [max(len(row[i]) for row in rows) + 2 for i in range(len(header))]
    lines = [f"Relay compare — dataset {c.dataset_id} · n={c.n_cases}", ""]
    for row in rows:
        lines.append("".join(cell.ljust(w) for cell, w in zip(row, widths, strict=True)).rstrip())
    lines += ["", f"Action diffs computed {c.threshold_note}."]
    for pair in c.pairs:
        lines.append("")
        if not pair.diffs:
            lines.append(f"No action differences between {pair.a} and {pair.b}.")
            continue
        new_unsafe = sum(d.new_unsafe for d in pair.diffs)
        lines.append(
            f"Action differences {pair.a} -> {pair.b}: {len(pair.diffs)} cases "
            f"({new_unsafe} new unsafe automations)"
        )
        a_width = max(len(pair.a), 14) + 2
        b_width = max(len(pair.b), 14) + 2
        lines.append(
            f"  {'CASE':<14}{'EXPECTED':<14}{pair.a:<{a_width}}{pair.b:<{b_width}}FLAG".rstrip()
        )
        for d in pair.diffs:
            flag = (
                "NEW UNSAFE AUTO"
                if d.new_unsafe
                else ("unsafe resolved" if d.resolved_unsafe else "")
            )
            lines.append(
                f"  {d.case_id:<14}{d.expected:<14}{d.action_a:<{a_width}}"
                f"{d.action_b:<{b_width}}{flag}".rstrip()
            )
    return "\n".join(lines)


REPRODUCED_LINE = "REPRODUCED: identical action, reasons and gate path"
DRIFT_LINE = "ENGINE DRIFT: today's policy engine no longer reproduces this trace"


def _short_hash(value: str | None) -> str:
    return "unknown" if value is None else value.split(":", 1)[-1][:8]


UNLABELLED_LINE = "EXPECTED: not available (unlabelled)"

REPORTED_ONLY_LEGEND = "  ((name) = reported-only comparison: no engine gate acts on it)"


def _expected_line(diff: TraceDiff) -> str:
    if diff.expected_original is None:
        return UNLABELLED_LINE
    if diff.expected_original == diff.expected_candidate:
        return f"EXPECTED (evaluation-only): {diff.expected_original}"
    if diff.policy is not None:
        before, after = diff.policy
    else:
        before, after = "original thresholds", "candidate thresholds"
    return (
        f"EXPECTED (evaluation-only) under {before}: {diff.expected_original} · "
        f"under {after}: {diff.expected_candidate}"
    )


def _table(rows: list[list[str]]) -> list[str]:
    widths = [max(len(r[i]) for r in rows) + 2 for i in range(len(rows[0]))]
    return [
        "".join(cell.ljust(w) for cell, w in zip(r, widths, strict=True)).rstrip() for r in rows
    ]


def _decision_lines(diff: TraceDiff) -> list[str]:
    rows = [["", "DECISION", "ORIGINAL", "CANDIDATE", "Δ", "CROSSED"]]
    for d in diff.decisions:
        rows.append(
            [
                "*" if d.answer_changed else "",
                d.question_id.value,
                d.original,
                d.candidate,
                "—" if d.delta is None else f"{d.delta:+.3f}",
                ", ".join(n if n in d.crossed_gated else f"({n})" for n in d.crossed),
            ]
        )
    legend = []
    if any(d.answer_changed for d in diff.decisions):
        legend.append("  (* = answer changed)")
    if any(set(d.crossed) - set(d.crossed_gated) for d in diff.decisions):
        legend.append(REPORTED_ONLY_LEGEND)
    return [" " + line for line in _table(rows)] + legend


def _gate_lines(gates: list[GateDelta], all_gates: bool) -> list[str]:
    shown = gates if all_gates else [g for g in gates if g.original != g.candidate]
    if not all_gates and not shown:
        return ["GATES: same outcome at every gate (--all-gates shows every row)"]
    title = "all rows" if all_gates else "rows whose outcome differs; --all-gates shows every row"
    lines = [f"GATES ({title})"]
    for g in shown:
        status = g.original if g.original == g.candidate else f"{g.original} → {g.candidate}"
        lines.append(f"  {g.gate:<18}{status}")
        if g.detail_original == g.detail_candidate:
            if g.detail_original is not None:
                lines.append(f"      {g.detail_original}")
            continue
        if g.detail_original is not None:
            lines.append(f"      original:  {g.detail_original}")
        if g.detail_candidate is not None:
            lines.append(f"      candidate: {g.detail_candidate}")
    return lines


def _action_lines(
    side: str, action: WorkflowAction, expected: WorkflowAction | None, reasons: list[str]
) -> list[str]:
    verdict = "" if expected is None else f" ({classify(action, expected)})"
    return [f"  {side:<10}{action}{verdict}"] + [f"      - {reason}" for reason in reasons]


def replay_summary(diff: TraceDiff) -> str:
    """ACTION CHANGED: A → B (flag), or ACTION UNCHANGED: A (flag).

    NEWLY UNSAFE / UNSAFE RESOLVED can happen even when the action itself is unchanged (for
    example different policies on the two sides), so both forms carry the flag rather than only
    the changed one (Minor 1). "(unchanged)" is never shown for two differing actions that are
    each correct under their own side's expectation; that prints "(both correct)" instead.
    """
    unchanged = diff.action_original == diff.action_candidate
    if diff.newly_unsafe:
        flag = "NEWLY UNSAFE"
    elif diff.unsafe_resolved:
        flag = "UNSAFE RESOLVED"
    elif unchanged or diff.change is None:
        flag = None
    elif diff.change == "unchanged":
        flag = "both correct"
    else:
        flag = diff.change
    if unchanged:
        base = f"ACTION UNCHANGED: {diff.action_original}"
    else:
        base = f"ACTION CHANGED: {diff.action_original} → {diff.action_candidate}"
    return base if flag is None else f"{base} ({flag})"


def render_trace_diff(diff: TraceDiff, all_gates: bool = False, *, reproduce: bool = False) -> str:
    """Terminal output for `relay replay`: header, expected action, decisions, thresholds,
    gates, actions and a summary line. In reproduce mode the REPRODUCED / ENGINE DRIFT verdict
    is printed under the header and again as the last line."""
    verdict = (REPRODUCED_LINE if diff.identical else DRIFT_LINE) if reproduce else None
    lines = [
        f"Relay replay — {diff.case_id}",
        f"ORIGINAL {diff.original_label}",
        f"CANDIDATE {diff.candidate_label}",
    ]
    if verdict is not None:
        lines.append(verdict)
    if diff.policy_text_changed is None:
        lines.append("policy text hash not recorded")
    elif diff.policy_text_changed:
        lines.append(
            "POLICY TEXT CHANGED since the original run "
            f"({_short_hash(diff.policy_text_hash_original)} → "
            f"{_short_hash(diff.policy_text_hash_current)})"
        )
    lines += [_expected_line(diff), ""]
    lines += _decision_lines(diff)
    if diff.thresholds:
        lines += ["", "THRESHOLDS CHANGED"]
        lines += [
            f"  {name}  {before:g} → {after:g}" for name, (before, after) in diff.thresholds.items()
        ]
    if diff.policy is not None:
        lines += ["", f"POLICY CHANGED: {diff.policy[0]} → {diff.policy[1]}"]
    lines += [""] + _gate_lines(diff.gates, all_gates)
    lines += ["", "ACTIONS"]
    lines += _action_lines(
        "ORIGINAL", diff.action_original, diff.expected_original, diff.reasons_original
    )
    lines += _action_lines(
        "CANDIDATE", diff.action_candidate, diff.expected_candidate, diff.reasons_candidate
    )
    lines += ["", replay_summary(diff)]
    if verdict is not None:
        lines.append(verdict)
    return "\n".join(lines)
