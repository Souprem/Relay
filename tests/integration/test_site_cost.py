"""The cost block in index.json and experiments.json: every figure equals the committed spend
ledgers, run manifests and traces, the ratio is computed from them, and README.md's "Cost and
speed" section quotes the exported strings."""

import json
import re
from decimal import Decimal

from relay.evaluation.metrics import percentile
from relay.site.cost import ordinal, usd_sig
from relay.site.registry import RUNS, run_spec
from relay.traces.store import read_traces
from tests.site_support import REPO, load

BASE = REPO / "evals" / "baselines"
CLAUDE_GOLD = "run_20260926T011730Z_f1852f"
CLAUDE_DEV = "run_20260925T191752Z_288946"
CLAUDE_HOLDOUT = "run_20260925T212034Z_bbee49"
CLAUDE_SMOKE = "run_20260925T131052Z_f328de"
JEV_GOLD_V2 = "run_20260925T170857Z_b95be9"
JEV_GOLD_V3 = "run_20260927T072623Z_ad6f44"
JEV_HOLDOUT_V3 = "run_20260927T072144Z_12e1e4"
JEV_HOLDOUT_V3_Q2 = "run_20260927T072249Z_204814"
JEV_SMOKE = "run_20260925T042324Z_eee114"


def _ledger(name: str) -> dict:
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def _entry(name: str, run_id: str) -> dict:
    [entry] = [e for e in _ledger(name)["entries"] if e["run_id"] == run_id]
    return entry


def _traces(run_id: str):
    spec = run_spec(run_id)
    return read_traces(REPO / spec.run_dir / spec.trace_name)


def _trace_cost(run_id: str) -> Decimal:
    return sum((t.decisions.estimated_cost_usd for t in _traces(run_id)), Decimal(0))


def _cost(site_export) -> dict:
    return load(site_export, "index.json")["cost"]


def _runs(site_export) -> dict[str, dict]:
    return {r["run_id"]: r["cost"] for r in _all_run_payloads(site_export)}


def _all_run_payloads(site_export) -> list[dict]:
    return [load(site_export, f"runs/{r.run_id}.json") for r in RUNS]


def test_the_ledger_backed_run_costs_equal_the_ledgers_and_traces(site_export):
    costs = _runs(site_export)
    expected = {
        CLAUDE_GOLD: ("claude-spend.json", "1.560455", 100),
        CLAUDE_HOLDOUT: ("claude-spend.json", "2.456215", 150),
        CLAUDE_SMOKE: ("claude-spend.json", "0.254666", 10),
        JEV_GOLD_V3: ("jev-spend-3d.json", "0.017497", 100),
        JEV_HOLDOUT_V3: ("jev-spend-3d.json", "0.172422", 1000),
        JEV_HOLDOUT_V3_Q2: ("jev-spend-3d.json", "0.112539", 1000),
    }
    for run_id, (ledger, total, n) in expected.items():
        entry = _entry(ledger, run_id)
        cost = costs[run_id]
        assert cost["kind"] == "ledger", run_id
        assert cost["total_usd"] == entry["cost_usd"] == total, run_id
        assert cost["n"] == entry["cases"] == n, run_id
        assert Decimal(cost["per_case_usd"]) == Decimal(total) / n, run_id
        assert abs(_trace_cost(run_id) - Decimal(total)) <= Decimal("0.000001"), run_id
    assert costs[CLAUDE_GOLD]["per_case_text"] == "$0.0156"
    assert costs[CLAUDE_HOLDOUT]["per_case_text"] == "$0.0164"
    assert costs[CLAUDE_SMOKE]["per_case_text"] == "$0.0255"
    assert costs[CLAUDE_SMOKE]["mode"] == "sync"
    assert costs[CLAUDE_GOLD]["mode"] == costs[CLAUDE_HOLDOUT]["mode"] == "batch"
    assert costs[JEV_HOLDOUT_V3_Q2]["per_case_text"] == "$0.000113"
    assert costs[JEV_HOLDOUT_V3]["per_case_text"] == "$0.000172"
    assert costs[JEV_GOLD_V3]["per_case_text"] == "$0.000175"


def test_the_dev_claude_run_counts_both_batches_over_all_400_cases(site_export):
    cost = _runs(site_export)[CLAUDE_DEV]
    manifest = json.loads((BASE / "gen-v0.2-dev" / CLAUDE_DEV / "run-manifest.json").read_text())
    parts = [
        Decimal(_entry("claude-spend.json", p["run_id"])["cost_usd"])
        for p in manifest["source_runs"]
    ]
    assert [p["cases_used"] for p in manifest["source_runs"]] == [378, 22]
    assert parts == [Decimal("4.123975"), Decimal("0.274699")]
    assert cost["kind"] == "ledger-sum"
    assert Decimal(cost["total_usd"]) == sum(parts) == _trace_cost(CLAUDE_DEV)
    assert cost["n"] == 400
    assert Decimal(cost["per_case_usd"]) == sum(parts) / 400
    assert cost["per_case_text"] == "$0.0110"
    assert "22 cancelled" in cost["source"]


def test_unledgered_jev_runs_use_their_trace_estimates_and_free_runs_cost_nothing(site_export):
    costs = _runs(site_export)
    ledgered = {
        e["run_id"]
        for name in ("claude-spend.json", "jev-spend-3d.json")
        for e in _ledger(name)["entries"]
    }
    for spec in RUNS:
        cost = costs[spec.run_id]
        if spec.provider in ("rules", "groundtruth"):
            assert (cost["total_usd"], cost["kind"]) == ("0", "no-call"), spec.run_id
        elif cost["kind"] == "reused":
            assert cost["total_usd"] is None and cost["per_case_text"] is None, spec.run_id
            assert spec.dataset == "gen-v0.3-shift"
        elif cost["kind"] == "trace-estimate":
            assert spec.provider == "jev" and spec.run_id not in ledgered, spec.run_id
            assert Decimal(cost["total_usd"]) == _trace_cost(spec.run_id), spec.run_id
    assert costs[JEV_GOLD_V2]["kind"] == "trace-estimate"
    assert costs[JEV_GOLD_V2]["per_case_text"] == "$0.000115"


def test_the_headline_ratio_is_like_for_like_on_gold(site_export):
    headline = _cost(site_export)["comparison"]["headline"]
    claude = Decimal(_entry("claude-spend.json", CLAUDE_GOLD)["cost_usd"]) / 100
    jev = _trace_cost(JEV_GOLD_V2) / 100
    ratio = claude / jev
    assert headline["claude"]["run_id"] == CLAUDE_GOLD
    assert headline["jev"]["run_id"] == JEV_GOLD_V2
    assert headline["jev"]["question_set"] == "q-v0.2"
    assert headline["claude"]["question_set"].startswith("q-v0.2+")
    assert headline["jev"]["kind"] == "trace-estimate"
    assert headline["jev"]["estimate_label"] == "trace estimate"
    assert headline["ratio"]["value"] == float(ratio)
    assert headline["ratio"]["rounded"] == round(ratio) == 136
    assert headline["ratio"]["text"] == "136×"
    assert headline["ratio"]["fraction_text"] == "1/136th"
    assert (
        (headline["jev"]["per_case_text"], headline["claude"]["per_case_text"])
        == (
            usd_sig(jev),
            usd_sig(claude),
        )
        == ("$0.000115", "$0.0156")
    )
    assert headline["text"] == (
        "Cost per case on gold, same questions: Jev q-v0.2 $0.000115 (trace estimate) · "
        "Claude Opus 5 $0.0156 (batch), about 136× more, at similar gold accuracy."
    )
    assert "estimated cost" in headline["estimate_note"]
    assert _counts(headline["claude"]["correct"]) == (93, 100)
    assert _counts(headline["jev"]["correct"]) == (91, 100)


def test_the_ledgered_q_v0_3_row_stays_in_the_comparison(site_export):
    rows = _cost(site_export)["comparison"]["rows"]
    [row] = [r for r in rows if r["dataset"] == "gold-v0.1" and r["jev"]["run_id"] == JEV_GOLD_V3]
    claude = Decimal(_entry("claude-spend.json", CLAUDE_GOLD)["cost_usd"])
    jev = Decimal(_entry("jev-spend-3d.json", JEV_GOLD_V3)["cost_usd"])
    assert row["ratio"]["value"] == float(claude / jev)
    assert row["ratio"]["text"] == "89×"
    assert row["jev"]["kind"] == "ledger" and row["jev"]["estimate_label"] is None


def _counts(rate: dict) -> tuple[int, int]:
    return rate["count"], rate["n"]


def test_every_comparison_row_divides_the_exported_per_case_costs(site_export):
    comparison = _cost(site_export)["comparison"]
    rows = {(r["dataset"], r["jev"]["run_id"]): r for r in comparison["rows"]}
    for row in rows.values():
        ratio = Decimal(row["claude"]["per_case_usd"]) / Decimal(row["jev"]["per_case_usd"])
        assert row["ratio"]["rounded"] == round(ratio)
        assert row["claude"]["mode"] == "batch"
    assert rows[("gold-v0.1", JEV_GOLD_V2)]["ratio"]["text"] == "136×"
    assert rows[("gold-v0.1", JEV_GOLD_V3)]["ratio"]["text"] == "89×"
    assert rows[("gen-v0.2-dev", "run_20260925T071231Z_6f0b73")]["ratio"]["text"] == "98×"
    assert rows[("gen-v0.2-holdout", "run_20260925T075242Z_fd455f")]["ratio"]["text"] == "146×"
    assert comparison["ratio_range"] == {"low": 89, "high": 146}


def test_the_latency_comes_from_the_smoke_traces_and_the_bench(site_export):
    latency = _cost(site_export)["latency"]
    for key, run_id, figures in (
        ("claude_sync", CLAUDE_SMOKE, (5169, 6781)),
        ("jev_smoke", JEV_SMOKE, (178, 411)),
    ):
        values = [t.decisions.latency_ms for t in _traces(run_id)]
        assert (
            (latency[key]["p50_ms"], latency[key]["p95_ms"])
            == (
                percentile(values, 50),
                percentile(values, 95),
            )
            == figures
        )
        assert latency[key]["n"] == len(values) == 10
    results = (REPO / "docs" / "RESULTS.md").read_text(encoding="utf-8")
    assert "5169 / 6781 ms" in results
    bench = json.loads((BASE / "bench" / "parallelism.json").read_text())
    p50s = [round(s["latency_ms_p50"]) for s in bench["sizes"]]
    assert (latency["jev_bench"]["p50_ms_low"], latency["jev_bench"]["p50_ms_high"]) == (
        min(p50s),
        max(p50s),
    )
    assert latency["ratio_p50"]["text"] == "29×"


def test_the_totals_equal_the_ledgers_plus_the_unledgered_trace_estimates(site_export):
    totals = _cost(site_export)["totals"]
    assert totals["claude_ledger_usd"] == _ledger("claude-spend.json")["spent_usd"] == "8.710495"
    assert totals["jev_ledger_usd"] == _ledger("jev-spend-3d.json")["spent_usd"] == "0.501850"
    estimates = sum((_trace_cost(r) for r in totals["jev_trace_estimate_runs"]), Decimal(0))
    assert Decimal(totals["jev_trace_estimate_usd"]) == estimates
    assert Decimal(totals["jev_total_usd"]) == Decimal("0.501850") + estimates
    assert sorted(totals["jev_trace_estimate_runs"]) == sorted(
        [
            JEV_GOLD_V2,
            JEV_SMOKE,
            "run_20260925T071231Z_6f0b73",
            "run_20260925T071157Z_d6b218",
            "run_20260925T075242Z_fd455f",
        ]
    )


def test_experiments_and_runs_carry_the_same_cost_figures(site_export):
    cost = _cost(site_export)
    experiments = load(site_export, "experiments.json")["cost"]
    assert experiments == cost | {"title": "Cost and speed"}
    by_run = _runs(site_export)
    for dataset in load(site_export, "runs.json")["datasets"]:
        for row in dataset["runs"]:
            assert row["cost"] == by_run[row["run_id"]], row["run_id"]
    assert len(cost["caveats"]) >= 5


def test_the_frontier_finding_title_leads_with_the_exported_ratio(site_export):
    index = load(site_export, "index.json")
    finding = next(f for f in index["findings"] if f["id"] == "frontier-llm")
    ratio = index["cost"]["comparison"]["headline"]["ratio"]
    assert finding["title"] == (
        "At similar gold accuracy and with the same questions, Jev cost about "
        f"{ratio['fraction_text']} as much per case as Claude Opus 5."
    )
    assert finding["figures"]["ratio"] == ratio
    assert finding["link"]["href"] == "/experiments/#cost"


def test_ordinal_suffixes():
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 89, 112, 136)] == [
        "1st",
        "2nd",
        "3rd",
        "4th",
        "11th",
        "12th",
        "13th",
        "21st",
        "89th",
        "112th",
        "136th",
    ]


# ---- README ---------------------------------------------------------------------------------


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("`", "")).strip()


def _readme_cost() -> str:
    text = (REPO / "README.md").read_text(encoding="utf-8")
    match = re.search(r"^## Cost and speed\n(.*?)^## ", text, flags=re.S | re.M)
    assert match, "README.md has no 'Cost and speed' section"
    return match.group(1)


def test_the_readme_cost_section_quotes_the_exported_strings(site_export):
    cost = _cost(site_export)
    section = _readme_cost()
    flat = _flat(section)
    assert cost["comparison"]["headline"]["text"] in flat
    assert _flat(cost["comparison"]["headline"]["estimate_note"]) in flat
    assert _flat(cost["latency"]["summary"]) in flat
    for caveat in cost["caveats"]:
        assert _flat(caveat) in flat, caveat
    totals = cost["totals"]
    assert (
        f"Claude {totals['claude_ledger_text']} (ledger); Jev {totals['jev_total_text']} "
        f"({totals['jev_ledger_text']} in the Phase 3D ledger and "
        f"{totals['jev_trace_estimate_text']} in trace estimates" in flat
    )
    table = [
        [c.strip().replace("`", "") for c in line.strip("|").split("|")]
        for line in section.splitlines()
        if line.startswith("| ") and not line.startswith("| Dataset")
    ]
    assert len(table) == len(cost["comparison"]["rows"])
    for cells, row in zip(table, cost["comparison"]["rows"], strict=True):
        assert cells[0] == row["dataset"]
        assert cells[1].split(" ")[0] == row["claude"]["per_case_text"]
        assert cells[2] == f"{row['jev']['per_case_text']} ({row['jev']['question_set']})"
        assert cells[3] == row["ratio"]["text"]
