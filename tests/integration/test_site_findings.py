"""index.json findings: every figure equals the committed artifacts, and README.md's "What I
found" quotes only numbers the export carries."""

import csv
import json
import re

from tests.site_support import REPO, load

BASE = REPO / "evals" / "baselines"


def _json(relative: str):
    return json.loads((BASE / relative).read_text(encoding="utf-8"))


def _frontier(run_dir: str, threshold: float) -> dict[str, int]:
    with (BASE / run_dir / "report" / "frontier.csv").open(encoding="utf-8") as f:
        [row] = [r for r in csv.DictReader(f) if abs(float(r["auto_threshold"]) - threshold) < 1e-9]
    return {k: int(row[k]) for k in ("n", "auto", "unsafe", "correct")}


def _counts(rate: dict) -> tuple[int, int]:
    return rate["count"], rate["n"]


def _findings(site_export) -> dict[str, dict]:
    return {f["id"]: f for f in load(site_export, "index.json")["findings"]}


def _text(finding: dict) -> str:
    return finding["title"] + " " + "".join(s["text"] for s in finding["body"])


def test_there_are_five_findings_each_linking_to_a_site_page_and_results_md(site_export):
    findings = load(site_export, "index.json")["findings"]
    assert [f["id"] for f in findings] == [
        "gating",
        "design-flaw",
        "contradiction-gate",
        "policy-shift",
        "frontier-llm",
    ]
    for f in findings:
        assert f["link"]["href"].startswith("/"), f["id"]
        assert "docs/RESULTS.md#" in f["source"], f["id"]
        assert {s["tone"] for s in f["body"]} <= {None, "unsafe", "correct"}, f["id"]


def test_the_gating_figures_match_the_committed_holdout_artifacts(site_export):
    fig = _findings(site_export)["gating"]["figures"]
    holdout = _json("gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/regression.json")["candidate"]
    assert _counts(fig["jev_q_v0_3"]["automation"]) == _counts(holdout["automation"]) == (244, 1000)
    assert _counts(fig["jev_q_v0_3"]["uar"]) == _counts(holdout["uar"]) == (0, 244)
    assert _counts(fig["jev_q_v0_3"]["correct"]) == _counts(holdout["correct"]) == (921, 1000)
    assert fig["jev_q_v0_3"]["uar"]["ci_high_pct"] == f"{holdout['uar']['ci95']['high']:.1%}"
    assert fig["jev_q_v0_3"]["auto_process"] == 0.81
    for key, run_dir, at in (
        ("jev_q_v0_2", "gen-v0.2-holdout/run_20260925T075242Z_fd455f", 0.89),
        ("rules", "gen-v0.2-holdout/run_20260925T092425Z_0aee97", 0.99),
    ):
        point = _frontier(run_dir, at)
        assert _counts(fig[key]["automation"]) == (point["auto"], point["n"]), key
        assert _counts(fig[key]["correct"]) == (point["correct"], point["n"]), key
    assert _counts(fig["rules"]["automation"]) == (134, 1000)
    assert _counts(fig["rules"]["correct"]) == (667, 1000)


def test_the_home_hero_figures_are_the_holdout_display_strings(site_export):
    index = load(site_export, "index.json")
    hero = index["hero"]
    holdout = _json("gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/regression.json")["candidate"]
    assert hero["run_id"] == "run_20260927T072144Z_12e1e4"
    assert (hero["label"], hero["dataset"], hero["n"], hero["auto_process"]) == (
        "Jev q-v0.3",
        "gen-v0.3-holdout",
        1000,
        0.81,
    )
    figures = {f["id"]: f for f in hero["figures"]}
    assert list(figures) == ["automation", "unsafe", "correct"]
    assert (figures["automation"]["value"], figures["automation"]["caption"]) == (
        "24.4%",
        "244 of 1000 cases",
    )
    assert figures["unsafe"]["value"] == "0 of 244"
    assert figures["unsafe"]["caption"] == f"95% upper bound {holdout['uar']['ci95']['high']:.1%}"
    assert (figures["correct"]["value"], figures["correct"]["caption"]) == (
        "92.1%",
        "921 of 1000 cases",
    )
    gating = _findings(site_export)["gating"]["figures"]["jev_q_v0_3"]
    assert figures["automation"]["value"] == gating["automation"]["pct"]
    assert figures["correct"]["value"] == gating["correct"]["pct"]


def test_the_design_flaw_figures_match_the_committed_artifacts(site_export):
    fig = _findings(site_export)["design-flaw"]["figures"]
    assert fig["case"] == "GOLD-TMP-17"
    results = next(c for c in load(site_export, "cases.json")["cases"] if c["id"] == "GOLD-TMP-17")[
        "results"
    ]
    by_run = {
        "run_20260925T170857Z_b95be9": results["jev-q-v0.2"]["verdict"],
        "run_20260926T011730Z_f1852f": results["claude"]["verdict"],
        "run_20260927T072623Z_ad6f44": results["jev-q-v0.3"]["verdict"],
    }
    assert fig["verdicts"] == by_run
    assert set(by_run.values()) == {"UNSAFE", "correct"}
    holdout = _json("gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/regression.json")
    assert (
        fig["holdout_correct"]
        == {
            "baseline": holdout["baseline"]["correct"]["count"],
            "candidate": holdout["candidate"]["correct"]["count"],
            "n": holdout["n"],
        }
        == {"baseline": 694, "candidate": 921, "n": 1000}
    )
    gold = _json("gold-v0.1/regression-q-v0.2-vs-q-v0.3/regression.json")
    assert fig["gold_newly_unsafe"] == [e["case_id"] for e in gold["newly_unsafe"]]
    assert fig["gold_newly_unsafe"] == ["GOLD-TMP-16"]
    assert "auto_process=0.97" in gold["baseline"]["label"]
    assert "auto_process=0.81" in gold["candidate"]["label"]
    assert fig["thresholds"] == {"before": 0.97, "after": 0.81}


def test_the_contradiction_figures_match_the_ablation_summary(site_export):
    fig = _findings(site_export)["contradiction-gate"]["figures"]
    rows = _json("ablation/summary.json")
    gold = [
        r
        for r in rows
        if r["dataset"] == "gold-v0.1"
        and r["ablation"] == "contradiction"
        and r["run"] not in ("rules", "groundtruth")
    ]
    assert fig["gold_model_providers"] == len(gold) == 3
    assert all(r["newly_unsafe"] == fig["gold_newly_unsafe"] for r in gold)
    assert fig["gold_newly_unsafe"] == ["GOLD-CON-03", "GOLD-CON-13"]
    for key, dataset, run, auto in (
        ("jev_q_v0_2", "gen-v0.2-holdout", "jev-q-v0.2", (252, 277)),
        ("jev_q_v0_3", "gen-v0.3-holdout", "jev-q-v0.3", (244, 261)),
    ):
        [row] = [
            r
            for r in rows
            if (r["dataset"], r["run"], r["ablation"]) == (dataset, run, "contradiction")
        ]
        got = fig["holdout"][key]
        for side in ("baseline", "ablated"):
            assert _counts(got["automation"][side]) == _counts(row["automation"][side]), key
            assert _counts(got["uar"][side]) == _counts(row["uar"][side]), key
        assert (
            got["automation"]["baseline"]["count"],
            got["automation"]["ablated"]["count"],
        ) == auto
        assert got["uar"]["ablated"]["count"] == 0
    missing = [r for r in rows if r["ablation"] == "missing_evidence"]
    assert fig["missing_evidence_runs"] == len(missing) == 10
    assert fig["missing_evidence_changed_automation"] is False
    assert all(
        r["automation"]["baseline"]["count"] == r["automation"]["ablated"]["count"]
        and r["uar"]["baseline"]["count"] == r["uar"]["ablated"]["count"]
        for r in missing
    )


def test_the_policy_shift_figures_match_the_committed_reports(site_export):
    fig = _findings(site_export)["policy-shift"]["figures"]
    regression = _json("gen-v0.3-shift/regression-stale-to-aware/regression.json")
    shadow = _json("gen-v0.3-shift/shadow-stale-to-aware/shadow.json")
    assert fig["n"] == regression["n"] == 400
    assert _counts(fig["stale_uar"]) == _counts(regression["baseline"]["uar"]) == (3, 16)
    assert _counts(fig["aware_uar"]) == _counts(regression["candidate"]["uar"]) == (0, 13)
    assert fig["gate"] == regression["verdict"] == "PASS"
    assert fig["shadow_decision"] == shadow["decision"] == "PROMOTE"


def test_the_frontier_llm_figures_match_the_gold_runs_and_spend_ledgers(site_export):
    fig = _findings(site_export)["frontier-llm"]["figures"]
    for key, run_dir, at in (
        ("claude", "gold-v0.1/run_20260926T011730Z_f1852f", 0.55),
        ("jev_q_v0_2", "gold-v0.1/run_20260925T170857Z_b95be9", 0.89),
    ):
        point = _frontier(run_dir, at)
        assert _counts(fig[key]["correct"]) == (point["correct"], point["n"]), key
        assert _counts(fig[key]["automation"]) == (point["auto"], point["n"]), key
        assert _counts(fig[key]["uar"]) == (point["unsafe"], point["auto"]), key
    assert _counts(fig["claude"]["correct"]) == (93, 100)
    assert _counts(fig["jev_q_v0_2"]["correct"]) == (91, 100)

    def cost(ledger: str, run_id: str) -> str:
        [entry] = [e for e in _json(ledger)["entries"] if e["run_id"] == run_id]
        return entry["cost_usd"]

    assert fig["claude"]["cost_usd"] == cost("claude-spend.json", fig["claude"]["run_id"])
    assert fig["claude"]["cost_usd"] == "1.560455"
    assert fig["jev_q_v0_3_cost_usd"] == cost("jev-spend-3d.json", "run_20260927T072623Z_ad6f44")
    assert fig["jev_q_v0_3_cost_usd"] == "0.017497"


# Identifiers that contain digits but are not numbers: case ids, versions, dataset names, runs.
_IDENTIFIER = re.compile(r"[A-Za-z][\w.]*-[\w.-]*\d[\w.-]*|\bv\d[\w.]*|run_\w+")
_NUMBER = re.compile(r"\$?\d+(?:\.\d+)?(?:[/–]\d+(?:\.\d+)?)?%?")


def _readme_findings() -> str:
    text = (REPO / "README.md").read_text(encoding="utf-8")
    match = re.search(r"^## What I found\n(.*?)^## ", text, flags=re.S | re.M)
    assert match, "README.md has no 'What I found' section"
    return match.group(1)


def _numbers(text: str) -> list[str]:
    text = re.sub(r"\]\([^)]*\)", "]", text)  # link targets
    text = _IDENTIFIER.sub(" ", text.replace("`", ""))
    return _NUMBER.findall(text)


def test_every_number_in_the_readme_findings_appears_in_the_export(site_export):
    section = _readme_findings()
    paragraphs = [p for p in section.split("\n\n") if p.strip()]
    findings = load(site_export, "index.json")["findings"]
    assert len(paragraphs) == len(findings)
    for paragraph, finding in zip(paragraphs, findings, strict=True):
        numbers = _numbers(paragraph)
        exported = _numbers(_text(finding))
        assert numbers, finding["id"]
        assert numbers == exported, finding["id"]
