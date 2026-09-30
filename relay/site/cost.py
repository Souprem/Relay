"""Cost and speed for the site: what each committed run cost, Jev against Claude per case, and
latency.

Every figure comes from a committed file:
- a run's cost is its spend-ledger entry (evals/baselines/claude-spend.json, jev-spend-3d.json);
  the gen-v0.2-dev Claude run, assembled from two batches, is the sum of its two source entries
  named in its run manifest; a Jev run in no ledger (the Phase 2 runs) is the sum of its traces'
  estimated_cost_usd; rules and ground truth make no provider call and cost $0; a recomposition
  (the policy-shift runs) reuses another run's stored answers and made no new call;
- every ledger-backed cost is checked against its traces' estimated_cost_usd;
- latency is the nearest-rank p50 / p95 of the smoke traces' latency_ms (relay.evaluation.metrics
  .percentile, as docs/RESULTS.md prints it) and the committed parallelism bench.

Display strings are formatted here, so the site never rounds a number itself.
"""

from collections.abc import Sequence
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any

from relay.decisions.claude import BATCH_DISCOUNT, CLAUDE_MODEL, PRICES_AS_OF
from relay.decisions.jev import PRICE_PER_INPUT_TOKEN_USD
from relay.evaluation.metrics import execution_mode, percentile
from relay.site.common import ExportContext, ExportError, rate_display, read_json, read_run_traces
from relay.site.registry import BASELINES, RESULTS_URL, RUNS, RunSpec, run_spec
from relay.traces.models import WorkflowTrace

CLAUDE_SPEND = f"{BASELINES}/claude-spend.json"
JEV_SPEND = f"{BASELINES}/jev-spend-3d.json"
BENCH = f"{BASELINES}/bench/parallelism.json"
CLAUDE_LABEL = "Claude Opus 5"

GOLD = "gold-v0.1"
GOLD_CLAUDE = "run_20260926T011730Z_f1852f"
GOLD_V2_JEV = "run_20260925T170857Z_b95be9"
GOLD_V3_JEV = "run_20260927T072623Z_ad6f44"
# The headline is like for like: the same gold cases and the same questions (q-v0.2), the
# 93/100 against 91/100 accuracy pairing. Jev q-v0.2's gold cost is a trace estimate.
HEADLINE_JEV = GOLD_V2_JEV
# (dataset, Claude run, Jev run, note) for the per-dataset cost ratios.
PAIRS: tuple[tuple[str, str, str, str | None], ...] = (
    (
        GOLD,
        GOLD_CLAUDE,
        GOLD_V2_JEV,
        "The same questions Claude was asked; the headline pair. Jev's cost is a trace estimate.",
    ),
    (GOLD, GOLD_CLAUDE, GOLD_V3_JEV, "Jev's costlier question set; its cost is in the ledger."),
    ("gen-v0.2-dev", "run_20260925T191752Z_288946", "run_20260925T071231Z_6f0b73", None),
    (
        "gen-v0.2-holdout",
        "run_20260925T212034Z_bbee49",
        "run_20260925T075242Z_fd455f",
        "Claude ran a 150-case sample; Jev ran all 1000.",
    ),
)
SMOKE_CLAUDE = "run_20260925T131052Z_f328de"
SMOKE_JEV = "run_20260925T042324Z_eee114"
TOLERANCE = Decimal("0.000001")  # ledgers record six decimal places


# ---- formatting ---------------------------------------------------------------------------


def usd_sig(value: Decimal | None, digits: int = 3) -> str | None:
    """$ with `digits` significant figures, rounded half to even: 0.01560455 -> "$0.0156"."""
    if value is None:
        return None
    if value == 0:
        return "$0"
    exponent = value.adjusted() - digits + 1
    rounded = value.quantize(Decimal(1).scaleb(exponent), rounding=ROUND_HALF_EVEN)
    return f"${rounded:f}"


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def ratio_json(numerator: Decimal, denominator: Decimal) -> dict[str, Any]:
    ratio = numerator / denominator
    whole = int(ratio.to_integral_value(rounding=ROUND_HALF_EVEN))
    return {
        "value": float(ratio),
        "rounded": whole,
        "text": f"{whole}×",
        "fraction_text": f"1/{ordinal(whole)}",
    }


# ---- per-run cost -------------------------------------------------------------------------


def _ledger_entries(repo: Path, ledger: str) -> dict[str, dict[str, Any]]:
    data = read_json(repo / ledger)
    entries: dict[str, dict[str, Any]] = {}
    for e in data.get("entries", []):
        if e["run_id"] in entries:
            raise ExportError(f"{ledger}: two entries for {e['run_id']}")
        entries[e["run_id"]] = e
    return entries


def _trace_sum(traces: Sequence[WorkflowTrace]) -> tuple[Decimal, int]:
    """The traces' summed estimated_cost_usd and how many traces carry none."""
    costs = [t.decisions.estimated_cost_usd for t in traces]
    return sum((c for c in costs if c is not None), Decimal(0)), sum(c is None for c in costs)


def _check(run_id: str, recorded: Decimal, estimated: Decimal) -> None:
    if abs(recorded - estimated) > TOLERANCE:
        raise ExportError(
            f"{run_id}: ledger cost {recorded} disagrees with its traces' {estimated}"
        )


def _mode(spec: RunSpec, traces: Sequence[WorkflowTrace]) -> str | None:
    if spec.provider == "jev":
        return "sync"  # one Jev call per case; the Jev provider has no batch mode
    if spec.provider == "claude":
        modes = {execution_mode(t.decisions) for t in traces}
        if len(modes) != 1 or None in modes:
            raise ExportError(f"{spec.run_id}: expected one recorded execution mode, got {modes}")
        return modes.pop()
    return None


def run_cost(
    repo: Path,
    spec: RunSpec,
    traces: Sequence[WorkflowTrace],
    ledgers: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    """One run's cost, cost per case and where the figure comes from."""
    n = len(traces)
    estimated, unpriced = _trace_sum(traces)
    manifest_path = repo / spec.run_dir / "run-manifest.json"
    manifest = read_json(manifest_path) if manifest_path.is_file() else {}
    ledger_entry = next(
        ((name, ledger[spec.run_id]) for name, ledger in ledgers.items() if spec.run_id in ledger),
        None,
    )
    total: Decimal | None
    if spec.provider in ("rules", "groundtruth"):
        if estimated != 0:
            raise ExportError(f"{spec.run_id}: a {spec.provider} run recorded a cost")
        total, kind = Decimal(0), "no-call"
        source = "No provider call"
    elif manifest.get("source_run_id"):
        total, kind = None, "reused"
        source = (
            f"Recomposed from {manifest['source_run_id']}'s stored answers; no new provider calls"
        )
    elif ledger_entry is not None:
        name, entry = ledger_entry
        if entry["cases"] != n:
            raise ExportError(f"{spec.run_id}: ledger has {entry['cases']} cases, traces {n}")
        total, kind = Decimal(entry["cost_usd"]), "ledger"
        _check(spec.run_id, total, estimated)
        source = f"{'Claude' if name == CLAUDE_SPEND else 'Jev'} spend ledger"
    elif manifest.get("source_runs"):
        parts = []
        for part in manifest["source_runs"]:
            entry = ledgers[CLAUDE_SPEND].get(part["run_id"])
            if entry is None:
                raise ExportError(f"{spec.run_id}: source run {part['run_id']} is in no ledger")
            parts.append((part, Decimal(entry["cost_usd"])))
        total, kind = sum((c for _, c in parts), Decimal(0)), "ledger-sum"
        _check(spec.run_id, total, estimated)
        billed = " + ".join(f"{p['run_id'][-6:]} ({p['cases_used']} cases, ${c})" for p, c in parts)
        dropped = sum(p.get("cases_dropped_as_canceled", 0) for p, _ in parts)
        source = (
            f"Claude spend ledger, two batches: {billed}; {dropped} cancelled cases were re-run "
            "and billed once"
        )
    elif spec.provider == "jev":
        if unpriced:
            raise ExportError(f"{spec.run_id}: {unpriced} traces carry no estimated cost")
        total, kind = estimated, "trace-estimate"
        source = "Sum of the traces' estimated cost; not in a committed ledger"
    else:
        raise ExportError(f"{spec.run_id}: no committed cost")
    per_case = None if total is None else total / n
    return {
        "run_id": spec.run_id,
        "dataset": spec.dataset,
        "provider": spec.provider,
        "label": spec.label,
        "question_set": spec.question_set,
        "mode": None if kind == "reused" else _mode(spec, traces),
        "n": n,
        "total_usd": None if total is None else str(total),
        "per_case_usd": None if per_case is None else str(per_case),
        "trace_estimate_usd": str(estimated),
        "total_text": usd_sig(total),
        "per_case_text": usd_sig(per_case),
        "kind": kind,
        "source": source,
    }


def run_costs(repo: Path, ctx: ExportContext) -> dict[str, dict[str, Any]]:
    """Every registered run's cost, keyed by run id, in registry order."""
    ledgers = {
        CLAUDE_SPEND: _ledger_entries(repo, CLAUDE_SPEND),
        JEV_SPEND: _ledger_entries(repo, JEV_SPEND),
    }
    costs = {}
    for spec in RUNS:
        loaded = ctx.loaded_runs.get(spec.run_id)
        traces = (
            loaded.recorded
            if loaded is not None
            else read_run_traces(repo / spec.run_dir / spec.trace_name)
        )
        costs[spec.run_id] = run_cost(repo, spec, traces, ledgers)
    return costs


# ---- comparison, latency, totals ----------------------------------------------------------


def _side(ctx: ExportContext, costs: dict[str, dict[str, Any]], run_id: str) -> dict[str, Any]:
    cost = costs[run_id]
    payload = ctx.run_payloads[run_id]
    label = CLAUDE_LABEL if cost["provider"] == "claude" else cost["label"]
    return {
        "run_id": run_id,
        "label": label,
        "question_set": cost["question_set"],
        "mode": cost["mode"],
        "n": cost["n"],
        "per_case_usd": cost["per_case_usd"],
        "per_case_text": cost["per_case_text"],
        "per_case_short": usd_sig(Decimal(cost["per_case_usd"]), 2),
        "total_text": cost["total_text"],
        "source": cost["source"],
        "kind": cost["kind"],
        "estimate_label": "trace estimate" if cost["kind"] == "trace-estimate" else None,
        "correct": payload["metrics"]["correct"],
    }


def comparison(ctx: ExportContext, costs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for run_id in {c for _, c, _, _ in PAIRS}:
        versions = ctx.run_payloads[run_id]["identity"]["provider_versions"]
        if versions != [CLAUDE_MODEL]:
            raise ExportError(f"{run_id}: expected {CLAUDE_MODEL}, got {versions}")
        if costs[run_id]["mode"] != "batch":
            raise ExportError(f"{run_id}: the comparison expects a batch Claude run")
    rows = []
    for dataset, claude_id, jev_id, note in PAIRS:
        claude, jev = _side(ctx, costs, claude_id), _side(ctx, costs, jev_id)
        rows.append(
            {
                "dataset": dataset,
                "claude": claude,
                "jev": jev,
                "ratio": ratio_json(Decimal(claude["per_case_usd"]), Decimal(jev["per_case_usd"])),
                "note": note,
            }
        )
    headline = next(r for r in rows if r["dataset"] == GOLD and r["jev"]["run_id"] == HEADLINE_JEV)
    ledgered = next(r for r in rows if r["dataset"] == GOLD and r["jev"]["run_id"] == GOLD_V3_JEV)
    ratios = [r["ratio"]["rounded"] for r in rows]
    claude, jev = headline["claude"], headline["jev"]
    if claude["question_set"].split("+")[0] != jev["question_set"]:
        raise ExportError("the headline pair no longer shares a question set")
    c, j = rate_display(claude["correct"]), rate_display(jev["correct"])
    estimate = f" ({jev['estimate_label']})" if jev["estimate_label"] else ""
    note = (
        f"{jev['label']}'s gold run is in no ledger, so its cost is the sum of its traces' "
        "estimated cost, which matches the ledger wherever a Jev run is in one."
        if jev["estimate_label"]
        else ""
    )
    return {
        "dataset": GOLD,
        "headline": {
            "claude": claude,
            "jev": jev,
            "ratio": headline["ratio"],
            "text": (
                f"Cost per case on gold, same questions: {jev['label']} {jev['per_case_text']}"
                f"{estimate} · {CLAUDE_LABEL} {claude['per_case_text']} (batch), about "
                f"{headline['ratio']['text']} more, at similar gold accuracy."
            ),
            "estimate_note": note or None,
            "summary": (
                f"On the same {claude['n']} gold cases with the same questions, {CLAUDE_LABEL} "
                f"cost {claude['per_case_text']} per case at batch prices and {jev['label']} "
                f"{jev['per_case_text']}: Claude cost about {headline['ratio']['text']} as much. "
                "Their correct "
                f"actions ({claude['correct']['count']}/{claude['correct']['n']} and "
                f"{jev['correct']['count']}/{jev['correct']['n']}) have overlapping 95% intervals "
                f"({c['ci_text']} and {j['ci_text']}). {note} {ledgered['jev']['label']}, whose "
                f"gold run is in the ledger, cost {ledgered['jev']['per_case_text']} per case, "
                f"so Claude cost {ledgered['ratio']['text']} as much."
            ).replace("  ", " "),
        },
        "rows": rows,
        "ratio_range": {"low": min(ratios), "high": max(ratios)},
    }


def latency(repo: Path, ctx: ExportContext) -> dict[str, Any]:
    def smoke(run_id: str) -> dict[str, Any]:
        traces = ctx.loaded_runs[run_id].recorded
        values = [t.decisions.latency_ms for t in traces]
        if any(v is None for v in values):
            raise ExportError(f"{run_id}: a trace has no latency")
        measured = [v for v in values if v is not None]
        spec = run_spec(run_id)
        return {
            "run_id": run_id,
            "dataset": spec.dataset,
            "label": CLAUDE_LABEL if spec.provider == "claude" else spec.label,
            "question_set": spec.question_set,
            "n": len(measured),
            "p50_ms": percentile(measured, 50),
            "p95_ms": percentile(measured, 95),
        }

    claude, jev = smoke(SMOKE_CLAUDE), smoke(SMOKE_JEV)
    if execution_mode(ctx.loaded_runs[SMOKE_CLAUDE].recorded[0].decisions) != "sync":
        raise ExportError(f"{SMOKE_CLAUDE}: the latency run must be sync")
    bench = read_json(repo / BENCH)
    p50s = [round(s["latency_ms_p50"]) for s in bench["sizes"]]
    return {
        "claude_sync": claude,
        "jev_smoke": jev,
        "jev_bench": {
            "source": BENCH,
            "model": bench["model"],
            "dataset": bench["dataset_id"],
            "calls_per_size": bench["sizes"][0]["calls"],
            "sizes": [s["size"] for s in bench["sizes"]],
            "p50_ms_low": min(p50s),
            "p50_ms_high": max(p50s),
        },
        "ratio_p50": ratio_json(Decimal(claude["p50_ms"]), Decimal(jev["p50_ms"])),
        "summary": (
            f"On the same {claude['n']} smoke cases, {CLAUDE_LABEL} (sync) took "
            f"{claude['p50_ms']:,} ms p50 and {claude['p95_ms']:,} ms p95 per case; "
            f"{jev['label']} took {jev['p50_ms']} ms and {jev['p95_ms']} ms. In the parallelism "
            f"bench ({bench['sizes'][0]['calls']} calls per size), Jev's p50 stayed between "
            f"{min(p50s)} and {max(p50s)} ms with {bench['sizes'][0]['size']} to "
            f"{bench['sizes'][-1]['size']} questions per call. The Claude figure is a "
            f"{claude['n']}-case sample."
        ),
    }


def totals(repo: Path, costs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    claude = Decimal(str(read_json(repo / CLAUDE_SPEND)["spent_usd"]))
    jev_ledger = Decimal(str(read_json(repo / JEV_SPEND)["spent_usd"]))
    unledgered = [c for c in costs.values() if c["kind"] == "trace-estimate"]
    jev_traces = sum((Decimal(c["total_usd"]) for c in unledgered), Decimal(0))
    return {
        "claude_ledger_usd": str(claude),
        "claude_ledger_text": f"${claude:.2f}",
        "jev_ledger_usd": str(jev_ledger),
        "jev_ledger_text": f"${jev_ledger:.3f}",
        "jev_trace_estimate_usd": str(jev_traces),
        "jev_trace_estimate_text": f"${jev_traces:.3f}",
        "jev_trace_estimate_runs": [c["run_id"] for c in unledgered],
        "jev_total_usd": str(jev_ledger + jev_traces),
        "jev_total_text": f"${jev_ledger + jev_traces:.3f}",
    }


def caveats(latency_n: int, gold_n: int) -> list[str]:
    discount = f"{BATCH_DISCOUNT:.0%}"
    jev_price = PRICE_PER_INPUT_TOKEN_USD * 1_000_000
    return [
        f"Claude was run as Opus 5 ({CLAUDE_MODEL}), the most capable and most expensive tier. "
        "Cheaper "
        "Claude models (Sonnet, Haiku) were not tested and would narrow the gap.",
        f"Claude's batch figures already include the {discount} Message Batches discount; at "
        "non-batch prices they would be about twice as high.",
        f"“Similar accuracy” means not distinguishable on {gold_n} gold cases, not proven equal.",
        f"Prices are as billed in September 2026: Claude at list prices as of {PRICES_AS_OF}, "
        f"Jev at ${jev_price:.3f} per million input tokens.",
        f"The Claude latency sample is {latency_n} cases (one sync run on the smoke set); Claude's "
        "batch runs record no latency.",
        "Jev's Phase 2 runs are in no ledger; their cost is the sum of the traces' own estimates, "
        "which match the ledger wherever a Jev run is in one.",
    ]


def build_cost(repo: Path, ctx: ExportContext, costs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The cost block for index.json and experiments.json."""
    compare = comparison(ctx, costs)
    speed = latency(repo, ctx)
    return {
        "comparison": compare,
        "latency": speed,
        "totals": totals(repo, costs),
        "runs": [costs[r.run_id] for r in RUNS if costs[r.run_id]["provider"] in ("jev", "claude")],
        "caveats": caveats(speed["claude_sync"]["n"], compare["headline"]["claude"]["n"]),
        "link": f"{RESULTS_URL}#baselines",
    }
