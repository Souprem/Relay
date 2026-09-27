# Phase 3E Design: Gate Ablation

- **Date:** 2026-09-27
- **Status:** Approved by controller (Phase 3 design is delegated by the user).
- **Depends on:** 3A replay (`replay_trace`/`replay_run`), 3B regression gate, and 3D runs.
- **Parent:** handoff experiment 6. "Ablation: remove contradiction detection or missing-evidence routing and quantify the safety/automation effect."
- **Cost:** $0. The whole experiment re-decides stored judgments offline. No provider is called.

## 1. Goal

Measure what each safety gate of the policy engine is worth. The same stored judgments are re-decided with a gate disabled. The 3B regression gate then reports, case by case, which automations become unsafe and which correct routings are lost. A negative or null result, where a gate never changes an action on a dataset, is reported as-is.

## 2. Settled decisions

| # | Decision |
|---|---|
| A1 | **The ablations.** Each is a named, versioned engine switch:<br>• `contradiction`: the contradiction review gate is skipped, AND the contradiction auto-block inside the auto_process gate is treated as not blocking. This removes contradiction detection entirely, as the handoff says.<br>• `missing_evidence`: the missing-evidence REQUEST_INFO gate is skipped. The documentation gate stays.<br>• `contradiction+missing_evidence`: both.<br>Nothing else can be ablated. The provider, age and documentation gates stay, because the handoff names only these two, and YAGNI. |
| A2 | **Engine API.** `determine_action(case, bundle, policy, thresholds, *, ablate: frozenset[str] = frozenset())`.<br>• The default gives byte-identical behaviour. All reproduce guards and gates must stay green.<br>• An unknown name raises `ValueError`.<br>• A skipped gate still appears in `gate_path` as `GateResult(gate=<name>, fired=False, detail="ABLATED: <name> gate disabled")`, so traces explain themselves.<br>• With `contradiction` ablated, the auto_process gate's detail shows `contradiction auto-block ABLATED`. |
| A3 | **Traces and manifests record it.** `WorkflowTrace.ablation: list[str] \| None = None` and `RunManifest.ablation: list[str] \| None = None`, sorted names, both backward compatible.<br>• `replay_trace`/`replay_run` pass `trace.ablation` through, so an ablated trace reproduces in 3A reproduce mode.<br>• 3A `diff_traces` shows an `ABLATION: <names>` line when either side has one.<br>• The 3B regression label includes `ablate=<names>`. |
| A4 | **CLI.** `relay ablate --traces FILE --dataset DIR --disable NAME[,NAME] [--at X] --out DIR` writes a simulated bundle (`traces.jsonl.gz`, `run-manifest.json`) with mode `simulated`, `source_run_id`, `ablation`, and the auto_process used. `--at` applies the provider's operating point first. The case pairing and hash checks are the same as `recompose`/`replay_run`. It is offline only and constructs no network client. |
| A5 | **Runs to ablate.** These are all committed traces, each at its provider's own dev-selected operating point, the same points the README uses:<br>• gen-v0.2-holdout: Jev q-v0.2 @0.89 and rules @0.99. The Claude holdout-150 sample @0.55 uses its `sample_limit`/`sample_seed` from the manifest.<br>• gen-v0.3-holdout: Jev q-v0.3 @0.81.<br>• gen-v0.3-shift: the aware run @0.95, its recorded threshold.<br>• gold-v0.1: ground truth, Jev q-v0.2 @0.89, rules @0.99, Claude @0.55, Jev q-v0.3 @0.81.<br>Each of the 10 runs gets the three ablations, 30 ablated bundles in total. |
| A6 | **Analysis.** For every (run, ablation) pair, `relay regression --baseline <run> --baseline-at X --candidate-traces <ablated>` (the ablated traces already carry X):<br>• the gate verdict<br>• newly unsafe (count and case ids)<br>• regressed and improved counts<br>• automation and UAR with Clopper-Pearson intervals<br>A committed helper, `scripts/phase3e_table.py`, reads all the `regression.json` files and writes `evals/baselines/ablation/summary.md`, one table row per pair, plus `summary.json`. |
| A7 | **The ground-truth row is the policy-level effect.** With perfect judgments, how many expected actions does removing a gate change? That is the upper bound on what the gate can matter on this dataset. It separates "the gate is useless" from "the providers never trigger it". The README explains the difference. |
| A8 | **Not CI gates.** Ablated candidates are expected to FAIL the regression gate, since that demonstrates a gate's value, and CI must stay green. The artifacts are committed under `evals/baselines/ablation/<dataset>/<run>/<ablation>/` (bundle plus the regression output). One reproduce gate is added for a single ablated bundle (gold, Jev q-v0.3, `contradiction`) to prove that ablated traces replay. |
| A9 | **Honesty.** Where an ablation changes nothing, say so plainly. That can happen because a provider never produces a high contradiction probability, or because the generator has few contradictions of a given kind. Tie such null results to the ground-truth row (A7). Also disclose that gold is not blind for q-v0.3 (3D caveat) and that Claude's holdout is a 150-case sample. |

## 3. Components

- `relay/workflow/engine.py`: the `ablate` parameter, and `ABLATIONS = frozenset({"contradiction", "missing_evidence"})`.
- `relay/traces/models.py`: the two new fields.
- `relay/evaluation/tracediff.py`: pass-through, and the diff line.
- `relay/evaluation/ablate_run.py`: `ablate_run(traces, cases, *, disable, auto_process) -> list[WorkflowTrace]` and a bundle writer that reuses the 3D1 `write_simulated_bundle`.
- `relay/cli.py`: `ablate`.
- `scripts/phase3e_table.py`
- README: an "Ablation" section with the summary table and interpretation. Every number comes from `summary.md`.

## 4. Testing

- **Engine.**
  - A default-parameter golden test: every committed trace in `evals/baselines` reproduces. This is the existing guard, and it must stay green.
  - Unit tests per ablation. Contradiction ablation on a high-contradiction bundle changes HUMAN_REVIEW to AUTO_PROCESS when the other decisions are high, and the auto-block is also removed. Missing-evidence ablation on a confident-missing bundle changes REQUEST_INFO to the next gate's outcome.
  - An unknown name raises.
  - The ABLATED gate_path entries appear.
- **Traces.** Old traces load (ablation None). Ablated traces reproduce via replay.
- **CLI.** A smoke dataset with rules and ground-truth tmp traces checks the flags, the manifest fields, refusals (exit 2) and pure offline operation (no client, keys unset).
- **Table script.** A fixture with regression.json files.
- **Gates.** All committed gates pass with `--strict-generated`, plus the new ablated reproduce gate.

## 5. Definition of done

- Tests, ruff and gates pass.
- The 30 ablated bundles, their regression outputs, and `summary.md`/`summary.json` are committed.
- The README Ablation section has real numbers and states null results plainly.
- $0 spent.
