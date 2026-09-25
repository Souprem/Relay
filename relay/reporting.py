"""Human-readable output: terminal run table, Markdown run report, eval summary."""

from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Any

from relay.cases.models import CaseInput
from relay.decisions.base import DecisionBundle, DecisionId
from relay.evaluation.frontier import SELECTION_RULE, FrontierPoint, SweepResult
from relay.evaluation.metrics import EvalSummary
from relay.traces.models import RunManifest, WorkflowTrace

DISCLAIMER = (
    "Relay uses synthetic data only and is an engineering/evaluation prototype. "
    "It is not for clinical use or real authorization decisions."
)
GROUNDTRUTH_NOTE = "groundtruth provider: pipeline validation, not a model result."
_LABEL_WIDTH = 26


def _p(bundle: DecisionBundle, qid: DecisionId) -> str:
    decision = bundle.get(qid)
    return f"{decision.p_yes:.2f}" if decision and decision.p_yes is not None else "-"


def _money(value: Decimal | None) -> str:
    return "unavailable" if value is None else f"${value:.7f}"


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
        f"Provider `{b.provider}` · model `{b.provider_version}` · latency {b.latency_ms} ms · "
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


def render_eval_summary(s: EvalSummary) -> str:
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
        latency = "unavailable"
    else:
        latency = f"{s.latency_p50_ms} ms / {s.latency_p95_ms} ms"
        if s.latency_low_sample:
            latency += f"  [low-sample: n={s.n_cases} < 30]"
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
        _row("Latency p50 / p95", latency),
        _row("Cost", cost),
        "",
        "Per-question accuracy (yes/no at p >= 0.5; choice by top answer):",
    ]
    for question, accuracy in s.per_question_accuracy.items():
        lines.append(_row(question, "unavailable" if accuracy is None else f"{accuracy:.1%}"))
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
        return (
            f"No threshold meets the ceiling ({ceiling} with at least one AUTO_PROCESS); "
            "nothing selected."
        )
    p = result.selected
    return (
        f"Selected operating point: auto_process >= {_threshold(p.auto_threshold)} "
        f"(automation {_pct(p.automation_rate)}, UAR {p.unsafe}/{p.auto}, "
        f"correct action {_pct(p.correct_action_rate)}; ceiling {ceiling})"
    )


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
