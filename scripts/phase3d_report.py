"""Phase 3D report helpers over committed regression.json files (offline, no provider calls).

uv run python -m scripts.phase3d_report adoption DEV_REGRESSION_JSON
    The E1 adoption decision (spec §5): ADOPT q-v0.3 iff its dev correct-action rate is higher
    than q-v0.2's and the dev regression gate q-v0.2 -> q-v0.3 passed (0 newly unsafe).
uv run python -m scripts.phase3d_report shift SHIFT_REGRESSION_JSON
    The E2 table (stale vs aware: correct action, automation, UAR) and the stale-only unsafe
    automations (unsafe in the stale run, resolved in the aware run).
"""

import json
import sys
from pathlib import Path
from typing import Any


def _rate(rate: dict[str, Any]) -> str:
    value = rate["rate"]
    shown = "n/a" if value is None else f"{value:.1%}"
    return f"{rate['count']}/{rate['n']} ({shown})"


def _run_id(side: dict[str, Any]) -> str:
    return side["identity"]["run_id"].removeprefix("replay-")


def _thresholds(side: dict[str, Any]) -> str:
    return ", ".join(side["identity"]["thresholds_versions"])


def adoption_decision(result: dict[str, Any]) -> bool:
    baseline, candidate = result["baseline"]["correct"], result["candidate"]["correct"]
    higher = candidate["count"] * baseline["n"] > baseline["count"] * candidate["n"]
    return higher and result["verdict"] == "PASS" and not result["newly_unsafe"]


def adoption_text(result: dict[str, Any]) -> str:
    lines = [
        "Adoption rule (Phase 3D spec §5 E1, dev only): adopt q-v0.3 iff its correct-action rate "
        "is higher than",
        "q-v0.2's and the dev regression gate q-v0.2 -> q-v0.3 passes (0 newly unsafe).",
    ]
    for name, side in (("q-v0.2", result["baseline"]), ("q-v0.3", result["candidate"])):
        correct = side["correct"]
        lines.append(
            f"  {name}: run {_run_id(side)} correct {correct['count']}/{correct['n']} "
            f"({correct['count'] / correct['n']:.4f}) at thresholds {_thresholds(side)}, "
            f"unsafe {side['uar']['count']}"
        )
    lines.append(
        f"  gate: {result['verdict']} (newly unsafe {len(result['newly_unsafe'])}, "
        f"regressed {len(result['regressed'])}, improved {len(result['improved'])})"
    )
    lines.append(f"DECISION: {'ADOPT q-v0.3' if adoption_decision(result) else 'KEEP q-v0.2'}")
    return "\n".join(lines)


def shift_markdown(result: dict[str, Any]) -> str:
    lines = [
        "| Run | Policy composed under | Correct action | Automation | Unsafe / auto (UAR) |",
        "|---|---|---|---|---|",
    ]
    for name, side in (("stale", result["baseline"]), ("aware", result["candidate"])):
        policy = ", ".join(side["identity"]["policy_versions"])
        lines.append(
            f"| {name} (`{_run_id(side)}`) | {policy} | {_rate(side['correct'])} | "
            f"{_rate(side['automation'])} | {_rate(side['uar'])} |"
        )
    resolved = [entry["case_id"] for entry in result["unsafe_resolved"]]
    lines += [
        "",
        f"Stale-only unsafe automations ({len(resolved)}): "
        + (", ".join(resolved) if resolved else "none"),
        f"Still unsafe in both ({len(result['still_unsafe'])}): "
        + (", ".join(e["case_id"] for e in result["still_unsafe"]) or "none"),
        f"Gate stale → aware: {result['verdict']} "
        f"(newly unsafe {len(result['newly_unsafe'])}, regressed {len(result['regressed'])})",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("adoption", "shift"):
        print(__doc__, file=sys.stderr)
        return 2
    result = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    print(adoption_text(result) if argv[0] == "adoption" else shift_markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
