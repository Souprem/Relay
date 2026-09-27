# Phase 3E: Gate Ablation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure what the contradiction and missing-evidence gates of the policy engine are worth: re-decide the stored judgments of 10 committed runs with each gate (and both) disabled, gate every ablated run against its source with the 3B regression gate, commit the 30 results with a summary table, and report them (null results included) in the README. $0, offline.

**Architecture:** `determine_action` gains a keyword-only `ablate: frozenset[str]` switch (default: the engine exactly as it is). Traces and run manifests record `ablation`; `replay_trace` re-applies a trace's own ablation, so ablated traces reproduce under 3A and 3B. A new `relay ablate` command re-decides a stored run through `replay_run` with the ablation set and writes a simulated bundle with the 3D1 `write_simulated_bundle`. The existing `relay regression` gates each ablated bundle against its source at the same threshold; `scripts/phase3e_table.py` turns the 30 `regression.json` files into `summary.md`/`summary.json`.

**Tech Stack:** Python 3.12, uv, Pydantic v2, Typer CLI (`relay`), pytest, ruff, gzip.

**Spec:** `docs/superpowers/specs/2026-09-27-phase3e-ablation-design.md` (A1–A9, §3–§5).

## Global Constraints

- Synthetic data only.
- Never open `.env` (read, cat, grep or edit it).
- No paid calls: this phase costs $0. No command in this plan builds a provider client or needs a key.
- Offline commands use `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env ...` (the `R` function in the preamble).
- `results/*.json` is never touched (read or written).
- Stage files by explicit path. Never `git add -A` or `git add .`.
- Each commit uses two `-m` arguments. The second is exactly `-m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.
- Don't push.
- At the end of every task, `uv run ruff check . && uv run ruff format --check . && env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest -q` must pass (run `uv run ruff check --fix . && uv run ruff format .` first if needed).
- The committed gates must pass with `--strict-generated`: `R regression --config evals/regression/gates.json --strict-generated` exits 0. This needs `evals/generated/gen-v0.2-holdout`, `gen-v0.3-dev`, `gen-v0.3-holdout` and `gen-v0.3-shift` on disk (they are git-ignored and already present in the checkout; Task 6 Step 1 verifies them).
- gold-v0.1 (`evals/gold/`) is never edited, and existing committed artifacts (everything already under `evals/baselines/`, `evals/generated/manifests/`, `evals/regression/examples/`) are never modified. New artifacts go only under `evals/baselines/ablation/`. The only edit to an existing committed JSON is appending one gate to `evals/regression/gates.json` (Task 6).
- Branch: `feat/phase3` (Phases 3A–3D complete). Work from the repository root `/Users/joelbrook/Desktop/Code/Relay`.
- README: another agent may still be finishing the Phase 3D2 README task. Only Task 7 touches `README.md`, and it starts only when `git status --short README.md` prints nothing.

## Before Task 1 (controller)

The spec is already committed (`ecead55 docs: add Phase 3E gate ablation design`). Commit this plan:

```bash
git add docs/superpowers/plans/2026-09-27-phase3e-ablation.md
git commit -m "docs: add the Phase 3E gate-ablation plan" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Shell preamble

Shell state does not survive between tool calls. Start **every** shell block in this plan with this preamble (it only defines a variable and a function; checked in zsh and bash):

```bash
D=/tmp/relay-3e; mkdir -p "$D"
R() { env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env "$@"; }
```

## Verified facts this plan relies on (checked while planning, on a scratch copy of `feat/phase3` with this whole plan applied)

- **Everything below ran as written.** Tasks 1–6 were implemented in a scratch copy: `ruff check`, `ruff format --check` and the full suite passed (1282 passed), and `R regression --config evals/regression/gates.json --strict-generated` exited 0 with the new gate PASS. Nothing was called and no key was set.
- **The default engine is unchanged.** With `ablate` empty, every branch of `determine_action` is the old one, byte for byte; every existing reproduce guard and committed gate stayed green.
- **Two existing test fakes need `**kwargs`.** `tests/integration/test_cli_regression.py::test_reproduce_passes_and_engine_drift_exits_3` and `tests/integration/test_committed_baselines.py::test_the_reproduce_guard_detects_engine_drift` monkeypatch `tracediff.determine_action` with a 4-argument function. Once `replay_trace` passes `ablate=`, they raise `TypeError` unless they accept and forward `**kwargs` (Task 2 Step 5). `tests/integration/test_cli_replay.py` already uses `*args, **kwargs`.
- **The 10 runs of spec A5, their committed directories and operating points** (the `at_point.auto_threshold` in each holdout run's `sweep.json`, which is the dev-selected point the README uses; gold uses the same per-provider points):

  | Dataset | Run dir name (Task 6) | Committed source directory under `evals/baselines/` | Provider | `--at` / `--baseline-at` |
  |---|---|---|---|---|
  | gen-v0.2-holdout | `jev-q-v0.2` | `gen-v0.2-holdout/run_20260925T075242Z_fd455f` | Jev q-v0.2 | 0.89 |
  | gen-v0.2-holdout | `rules` | `gen-v0.2-holdout/run_20260925T092425Z_0aee97` | rules-v0.1 | 0.99 |
  | gen-v0.2-holdout | `claude-150` | `gen-v0.2-holdout/run_20260925T212034Z_bbee49` (manifest `sample_limit` 150, `sample_seed` 7) | Claude | 0.55 |
  | gen-v0.3-holdout | `jev-q-v0.3` | `gen-v0.3-holdout/run_20260927T072144Z_12e1e4` | Jev q-v0.3 | 0.81 |
  | gen-v0.3-shift | `jev-q-v0.3-aware` | `gen-v0.3-shift/aware-immunara-v0.2` (run `run_20260927T072949Z_bd430c`, policy immunara-v0.2, thresholds v0.2) | Jev q-v0.3 | none (its recorded 0.95) |
  | gold-v0.1 | `groundtruth` | `gold-v0.1/run_20260925T170825Z_440df0` | ground truth | none (recorded 0.95; ground-truth probabilities are 0/1, so the threshold is immaterial) |
  | gold-v0.1 | `jev-q-v0.2` | `gold-v0.1/run_20260925T170857Z_b95be9` | Jev q-v0.2 | 0.89 |
  | gold-v0.1 | `rules` | `gold-v0.1/run_20260925T170839Z_d3b427` | rules-v0.1 | 0.99 |
  | gold-v0.1 | `claude` | `gold-v0.1/run_20260926T011730Z_f1852f` | Claude | 0.55 |
  | gold-v0.1 | `jev-q-v0.3` | `gold-v0.1/run_20260927T072623Z_ad6f44` | Jev q-v0.3 | 0.81 |

- **The Claude holdout run is a 150-case sample.** `relay ablate` and `relay regression` both read its `run-manifest.json` and subsample the 1000-case dataset with `sample_cases(cases, 150, 7)`; the ablated manifest carries `sample_limit`/`sample_seed` over.
- **The prototype's 30 results** (Task 6 must reproduce them; they are deterministic functions of the committed traces). "Newly unsafe" is the regression gate's count; "changed" is actions changed out of n.

  | Dataset / run | contradiction | missing_evidence | both |
  |---|---|---|---|
  | gen-v0.2-holdout / jev-q-v0.2 (n=1000) | 0 newly unsafe; 37 changed (12 regressed, 25 improved); auto 252 → 277, UAR 0/252 → 0/277 | 0; 100 changed (32 / 67); auto 252 → 252 | 0; 134 changed (41 / 92); auto 252 → 277 |
  | gen-v0.2-holdout / rules (n=1000) | 0; 17 changed (17 / 0); auto 134 → 134 | 0; **0 changed (null)** | 0; 17 changed (17 / 0) |
  | gen-v0.2-holdout / claude-150 (n=150) | 0; 3 changed (3 / 0); auto 37 → 37 | 0; 10 changed (7 / 3) | 0; 13 changed (10 / 3) |
  | gen-v0.3-holdout / jev-q-v0.3 (n=1000) | 0; 33 changed (16 / 17); auto 244 → 261, UAR 0/244 → 0/261 | 0; 93 changed (40 / 53); auto 244 → 244 | 0; 123 changed (53 / 70); auto 244 → 261 |
  | gen-v0.3-shift / jev-q-v0.3-aware (n=400) | 0; 7 changed (7 / 0); auto 13 → 13 | 0; 41 changed (15 / 26) | 0; 47 changed (21 / 26) |
  | gold-v0.1 / groundtruth (n=100) | 0; 1 changed (1 / 0): GOLD-CON-12 HUMAN_REVIEW → REQUEST_INFO | 0; **0 changed (null)** | 0; 1 changed (1 / 0) |
  | gold-v0.1 / jev-q-v0.2 | **2 (GOLD-CON-03, GOLD-CON-13)**, FAIL; 6 changed (5 / 1); auto 29 → 32, UAR 1/29 → 3/32 | 0; 5 changed (5 / 0) | **2**, FAIL; 9 changed (8 / 1) |
  | gold-v0.1 / rules | 0; **0 changed (null)**; UAR 6/20 both sides | 0; **0 changed (null)** | 0; **0 changed (null)** |
  | gold-v0.1 / claude | **2 (GOLD-CON-03, GOLD-CON-13)**, FAIL; 5 changed (3 / 2); auto 30 → 34, UAR 1/30 → 3/34 | 0; 6 changed (6 / 0) | **2**, FAIL; 11 changed (9 / 2) |
  | gold-v0.1 / jev-q-v0.3 | **2 (GOLD-CON-03, GOLD-CON-13)**, FAIL; 5 changed (4 / 1); auto 31 → 34, UAR 1/31 → 3/34 | 0; 4 changed (4 / 0) | **2**, FAIL; 8 changed (7 / 1) |

  So: 6 of the 30 pairs FAIL (every gold LLM-provider pair that removes contradiction detection, always the same two cases), 24 PASS, and 5 pairs change no action at all. The missing-evidence ablation never changes automation or UAR in any run.
- **The ground-truth row is not an upper bound (spec A7).** With perfect judgments, removing contradiction detection changes one gold action and creates no unsafe automation: every gold case with `contradiction_present: true` (GOLD-CON-01…14) also has `step_therapy_satisfied` or `diagnosis_supported` false, so the default review still catches it. The providers' two newly unsafe cases come from provider errors (they judged every required decision at or above the operating point on GOLD-CON-03 and GOLD-CON-13); only the contradiction gate held them back. Under ground truth the missing-evidence ablation changes nothing on gold or on any generated set (a case with missing evidence always has `documentation_complete: false`, so the documentation gate fires first).
- **Size.** The 30 directories total about 9.3 MB (each holds the ablated `traces.jsonl.gz`, and, where `--baseline-at` is used, the re-decided `baseline.jsonl.gz` that the `regression.md` replay commands point at, as in the committed 3D regression directories).

## Resolved ambiguities (decisions this plan makes)

1. **Ground truth has no `--at`.** Its probabilities are 0/1, so it is ablated and gated at its recorded thresholds (auto_process 0.95); `--baseline-at` is omitted too.
2. **"The aware run @0.95"** is `evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/` (the recomposed simulated run, policy immunara-v0.2, thresholds v0.2 with auto_process 0.95). It is ablated without `--at` and gated without `--baseline-at`.
3. **Directory names** are `evals/baselines/ablation/<dataset_id>/<run>/<ablation>/`, with `<run>` from the table above and `<ablation>` one of `contradiction`, `missing_evidence`, `contradiction+missing_evidence` (sorted names joined by `+`, as `ablation_name` returns). The ablated bundle (`traces.jsonl.gz`, `run-manifest.json`) and the regression output (`regression.json`, `regression.md`, plus `baseline.jsonl.gz`/`baseline.manifest.json` when `--baseline-at` is given) share that directory: `relay ablate` needs an empty `--out`, so it runs first, then `relay regression --out` writes beside it.
4. **Where "the auto_process used" goes.** The ablated manifest keeps the typed `ablation` field and the 3D extra keys `policy_id`/`thresholds`, and adds one extra key `auto_process` (the effective threshold after `--at`). `write_simulated_bundle` gains an optional `extra` mapping for it and records `ablation=first.ablation` for every bundle (None for recompose). `_write_simulated_run` in `regression_run.py` records `ablation` too, so a re-decided ablated candidate (`--candidate-at`) keeps it.
5. **Run ids.** An ablated run gets a fresh `new_run_id()` (as `relay recompose` does); each trace's `replay_of` is its source trace. Ablating an already-ablated run is refused (exit 2), so an ablation never stacks.
6. **`--disable` format.** Comma-separated names from `ABLATIONS`, whitespace around names ignored; an empty name, an unknown name or a repeat is exit 2.
7. **`relay ablate` output line.** It also re-decides the source without ablation at the same threshold and prints how many actions the ablation changed, so a null result is visible immediately.
8. **The diff line.** `TraceDiff` gains `ablation_original`/`ablation_candidate` (default None, so every existing construction still validates). `render_trace_diff` prints, after any POLICY CHANGED line, `ABLATION: <o> → <c>` when the sides differ or `ABLATION: <names> (both sides)` when they match, with `none` for an unablated side. It is printed only when at least one side is ablated.
9. **Labels.** `original_label` and `candidate_trace_label` append ` · ablate=<names>` for an ablated trace, and nothing otherwise, so every existing label string is unchanged. (Policy-replay and reproduce labels are fixed strings; the ABLATION line covers those diffs.)
10. **The ground-truth interpretation (A7).** The README calls the gold ground-truth row "the policy-level effect" and states plainly that it is not an upper bound on a gate's value, because the provider rows exceed it for contradiction detection (0 vs 2 newly unsafe). This corrects the spec's wording with the data.
11. **Summary table content.** One row per pair in dataset order (gen-v0.2-holdout, gen-v0.3-holdout, gen-v0.3-shift, gold-v0.1), then run order (groundtruth, jev-q-v0.2, rules, claude, claude-150, jev-q-v0.3, jev-q-v0.3-aware), then ablation order. Columns: provider, thresholds, gate verdict, actions changed (`n − change_counts.unchanged`), newly unsafe (count and ids), regressed, improved, automation and UAR on both sides with their Clopper-Pearson intervals. Two lists follow: null results (no action changed) and failing pairs. A committed test regenerates it from the committed `regression.json` files and requires byte equality.
12. **Only one new CI gate**, `gold-reproduce-ablated-jev-q-v0.3-contradiction` (reproduce, gold, no `requires_generated`). The 30 ablation regressions are not gates (spec A8).

## File structure

| File | Change | Responsibility |
|---|---|---|
| `relay/workflow/engine.py` | modify | `ABLATIONS`; `determine_action(..., *, ablate=frozenset())`; ABLATED gate-path entries |
| `relay/traces/models.py` | modify | `WorkflowTrace.ablation`, `RunManifest.ablation` |
| `relay/evaluation/tracediff.py` | modify | `replay_trace` re-applies `trace.ablation`; `TraceDiff.ablation_*`; `ablation_suffix` in labels |
| `relay/reporting.py` | modify | `ablation_line`; the ABLATION line in `render_trace_diff` |
| `relay/evaluation/recompose_run.py` | modify | `write_simulated_bundle(..., extra=None)` records `ablation` and extra keys |
| `relay/evaluation/ablate_run.py` | create | `parse_disable`, `ablation_name`, `ablate_run` |
| `relay/evaluation/regression_run.py` | modify | `_write_simulated_run` records `ablation` |
| `relay/cli.py` | modify | `relay ablate` |
| `scripts/phase3e_table.py` | create | `summary.md`/`summary.json` from the ablation `regression.json` files |
| `evals/baselines/ablation/**` | create | 30 ablated bundles + regression outputs + summary |
| `evals/regression/gates.json` | modify | one reproduce gate for an ablated bundle |
| `README.md` | modify | a Commands line and the "Gate ablation" section |
| `tests/unit/test_engine_ablation.py` | create | engine switch |
| `tests/unit/test_ablation_traces.py` | create | fields, replay pass-through, diff, labels, ABLATION line |
| `tests/unit/test_ablate_run.py` | create | `--disable` parsing, `ablate_run`, bundle manifest |
| `tests/integration/test_cli_ablate.py` | create | `relay ablate` end to end, offline |
| `tests/unit/test_phase3e_table.py` | create | the table script |
| `tests/integration/test_committed_ablation.py` | create | the committed artifacts and summary |
| `tests/integration/test_cli_regression.py`, `tests/integration/test_committed_baselines.py` | modify | test fakes forward `**kwargs` |
| `tests/integration/test_committed_gates.py` | modify | the new gate name |

---

### Task 1: The engine's ablation switch

**Files:**
- Modify: `relay/workflow/engine.py` (whole file shown below)
- Test: `tests/unit/test_engine_ablation.py` (create)

**Interfaces:**
- Consumes: nothing new.
- Produces: `relay.workflow.engine.ABLATIONS: frozenset[str]` = `frozenset({"contradiction", "missing_evidence"})`, and `determine_action(case: CaseInput, bundle: DecisionBundle, policy: AuthorizationPolicy, thresholds: Thresholds, *, ablate: frozenset[str] = frozenset()) -> PolicyOutcome`. An unknown name raises `ValueError("unknown ablation(s) [...]; known: [...]")`. A reached, ablated gate appears in `gate_path` as `GateResult(gate=<name>, fired=False, detail="ABLATED: <name> gate disabled")`. With `contradiction` ablated, the auto_process detail ends `contradiction auto-block ABLATED` and its AUTO_PROCESS reason is `all required judgments are at or above <t> (contradiction auto-block ABLATED)`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_engine_ablation.py`:

```python
"""determine_action(..., ablate=...): the Phase 3E gate-ablation switch (spec A1, A2)."""

import pytest

from relay.cases.policies import load_policy
from relay.workflow.engine import ABLATIONS, determine_action
from relay.workflow.outcomes import GateResult, WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1
from tests.factories import make_bundle, make_case_input

POLICY = load_policy("immunara-v0.1")
AUTO = WorkflowAction.AUTO_PROCESS
INFO = WorkflowAction.REQUEST_INFO
REVIEW = WorkflowAction.HUMAN_REVIEW
BOTH = frozenset({"contradiction", "missing_evidence"})


def decide(bundle, ablate=frozenset(), age=40):
    return determine_action(
        make_case_input(age=age), bundle, POLICY, THRESHOLDS_V0_1, ablate=ablate
    )


def gate(outcome, name):
    [result] = [g for g in outcome.gate_path if g.gate == name]
    return result


def test_the_ablatable_gates_are_exactly_contradiction_and_missing_evidence():
    assert ABLATIONS == BOTH


@pytest.mark.parametrize(
    "bundle_kwargs",
    [
        {},
        {"contra": 0.9},
        {"contra": 0.3},
        {"doc": 0.5, "missing": "TREATMENT_HISTORY", "missing_p": 0.8},
        {"missing": "INSURANCE_INFORMATION", "missing_p": 0.8},
        {"step": 0.9},
        {"error": "boom"},
    ],
)
def test_the_default_is_the_unablated_engine(bundle_kwargs):
    bundle = make_bundle(**bundle_kwargs)
    input_ = make_case_input()
    assert determine_action(input_, bundle, POLICY, THRESHOLDS_V0_1) == determine_action(
        input_, bundle, POLICY, THRESHOLDS_V0_1, ablate=frozenset()
    )


def test_an_unknown_ablation_raises():
    with pytest.raises(ValueError, match=r"unknown ablation\(s\) \['age'\]"):
        decide(make_bundle(), ablate=frozenset({"age"}))


def test_contradiction_ablation_turns_a_contradiction_review_into_auto_process():
    bundle = make_bundle(contra=0.9)
    assert decide(bundle).action is REVIEW
    outcome = decide(bundle, frozenset({"contradiction"}))
    assert outcome.action is AUTO
    assert gate(outcome, "contradiction") == GateResult(
        gate="contradiction", fired=False, detail="ABLATED: contradiction gate disabled"
    )
    auto = gate(outcome, "auto_process")
    assert auto.fired
    assert auto.detail.endswith(
        "p_yes(material_contradiction)=0.900, contradiction auto-block ABLATED"
    )
    assert outcome.reasons == [
        "all required judgments are at or above 0.95 (contradiction auto-block ABLATED)"
    ]


def test_contradiction_ablation_also_removes_the_auto_block():
    bundle = make_bundle(contra=0.3)  # below the 0.80 review gate, above the 0.20 auto-block
    unablated = decide(bundle)
    assert (unablated.action, unablated.gate_path[-1].gate) == (REVIEW, "default_review")
    assert decide(bundle, frozenset({"contradiction"})).action is AUTO


def test_contradiction_ablation_still_needs_the_required_judgments():
    outcome = decide(make_bundle(contra=0.9, step=0.9), frozenset({"contradiction"}))
    assert (outcome.action, outcome.gate_path[-1].gate) == (REVIEW, "default_review")
    assert outcome.reasons == ["step_therapy p_yes=0.900 is below the 0.95 autonomous-action bar"]


def test_missing_evidence_ablation_falls_through_to_the_next_gate():
    bundle = make_bundle(missing="INSURANCE_INFORMATION", missing_p=0.8)
    assert decide(bundle).action is INFO
    outcome = decide(bundle, frozenset({"missing_evidence"}))
    assert (outcome.action, outcome.gate_path[-1].gate) == (AUTO, "auto_process")
    assert gate(outcome, "missing_evidence") == GateResult(
        gate="missing_evidence", fired=False, detail="ABLATED: missing_evidence gate disabled"
    )
    lower = decide(
        make_bundle(missing="DIAGNOSIS", missing_p=0.8, diag=0.9), frozenset({"missing_evidence"})
    )
    assert (lower.action, lower.gate_path[-1].gate) == (REVIEW, "default_review")


def test_missing_evidence_ablation_keeps_the_documentation_gate():
    bundle = make_bundle(doc=0.5, missing="TREATMENT_HISTORY", missing_p=0.8)
    outcome = decide(bundle, frozenset({"missing_evidence"}))
    assert (outcome.action, outcome.gate_path[-1].gate) == (INFO, "documentation")


def test_missing_evidence_ablation_leaves_contradiction_detection_alone():
    outcome = decide(make_bundle(contra=0.9), frozenset({"missing_evidence"}))
    assert (outcome.action, outcome.gate_path[-1].gate) == (REVIEW, "contradiction")


def test_both_ablations_list_both_gates_as_ablated():
    bundle = make_bundle(contra=0.9, missing="INSURANCE_INFORMATION", missing_p=0.8)
    outcome = decide(bundle, BOTH)
    assert outcome.action is AUTO
    assert [g.gate for g in outcome.gate_path] == [
        "provider",
        "age",
        "contradiction",
        "documentation",
        "missing_evidence",
        "auto_process",
    ]
    assert [g.detail for g in outcome.gate_path if g.detail.startswith("ABLATED")] == [
        "ABLATED: contradiction gate disabled",
        "ABLATED: missing_evidence gate disabled",
    ]


def test_the_earlier_gates_still_fire_before_an_ablated_gate_is_reached():
    assert decide(make_bundle(contra=0.9), BOTH, age=16).gate_path[-1].gate == "age"
    outcome = decide(make_bundle(error="boom"), BOTH)
    assert [g.gate for g in outcome.gate_path] == ["provider"]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest tests/unit/test_engine_ablation.py -q`
Expected: collection error, `ImportError: cannot import name 'ABLATIONS' from 'relay.workflow.engine'`.

- [ ] **Step 3: Implement**

Replace the whole of `relay/workflow/engine.py` with the following. Only the module docstring, `ABLATIONS`, the `ablate` parameter, the `ablated` helper and the three gate branches (contradiction, missing_evidence, auto_process) change; `bundle_problem`, `_p_yes` and every other line are as before.

```python
"""Deterministic policy engine: judgments + thresholds -> one workflow action with reasons.

Probability is a signal, not a permission slip. Gates run in a fixed order and the first gate
that fires decides the action.

Phase 3E: `ablate` disables named safety gates for the gate-ablation experiment. It is an
analysis switch, never a production setting; the default (nothing ablated) is the engine as it
always was.
"""

from relay.cases.models import CaseInput, MissingEvidence
from relay.cases.policies import AuthorizationPolicy
from relay.decisions.base import DecisionBundle, DecisionId
from relay.workflow.outcomes import GateResult, PolicyOutcome, WorkflowAction
from relay.workflow.thresholds import Thresholds

_CHOICE_DECISIONS = {DecisionId.MISSING_EVIDENCE}
_MISSING_LABELS = {m.value for m in MissingEvidence}

# The gates `determine_action(..., ablate=...)` can disable (Phase 3E spec A1). "contradiction"
# removes contradiction detection entirely: the review gate AND the auto-block inside
# auto_process. "missing_evidence" skips only the missing-evidence REQUEST_INFO gate.
ABLATIONS = frozenset({"contradiction", "missing_evidence"})


def bundle_problem(bundle: DecisionBundle) -> str | None:
    """Return why a bundle cannot be trusted by the engine, or None if it is well-formed."""
    if bundle.error:
        return bundle.error
    missing = bundle.missing_decisions()
    if missing:
        return "missing decisions: " + ", ".join(missing)
    if len(bundle.decisions) != len(DecisionId):
        return "duplicate decisions in bundle"
    for decision in bundle.decisions:
        expected = "choice" if decision.question_id in _CHOICE_DECISIONS else "yes_no"
        if decision.kind != expected:
            return f"{decision.question_id} has kind {decision.kind}, expected {expected}"
    missing_evidence = bundle.get(DecisionId.MISSING_EVIDENCE)
    assert missing_evidence is not None
    if missing_evidence.answer not in _MISSING_LABELS:
        return f"missing_evidence answer {missing_evidence.answer!r} is not a known label"
    return None


def _p_yes(bundle: DecisionBundle, question_id: DecisionId) -> float:
    decision = bundle.get(question_id)
    assert decision is not None and decision.p_yes is not None
    return decision.p_yes


def determine_action(
    case: CaseInput,
    bundle: DecisionBundle,
    policy: AuthorizationPolicy,
    thresholds: Thresholds,
    *,
    ablate: frozenset[str] = frozenset(),
) -> PolicyOutcome:
    unknown = sorted(set(ablate) - ABLATIONS)
    if unknown:
        raise ValueError(f"unknown ablation(s) {unknown}; known: {sorted(ABLATIONS)}")
    t = thresholds
    path: list[GateResult] = []

    def passed(gate: str, detail: str) -> None:
        path.append(GateResult(gate=gate, fired=False, detail=detail))

    def ablated(gate: str) -> None:
        path.append(GateResult(gate=gate, fired=False, detail=f"ABLATED: {gate} gate disabled"))

    def fired(gate: str, detail: str, action: WorkflowAction, *reasons: str) -> PolicyOutcome:
        path.append(GateResult(gate=gate, fired=True, detail=detail))
        return PolicyOutcome(action=action, reasons=list(reasons), gate_path=path)

    problem = bundle_problem(bundle)
    if problem is not None:
        return fired(
            "provider", problem, WorkflowAction.HUMAN_REVIEW, f"provider failure: {problem}"
        )
    passed("provider", "all five decisions present and well-formed")

    age, min_age = case.patient.age, policy.min_age
    detail = f"patient.age={age}, policy min_age={min_age}"
    if age < min_age:
        return fired(
            "age",
            detail,
            WorkflowAction.HUMAN_REVIEW,
            f"patient age {age} is below the policy minimum of {min_age}",
        )
    passed("age", detail)

    contra = _p_yes(bundle, DecisionId.MATERIAL_CONTRADICTION)
    contradiction_ablated = "contradiction" in ablate
    detail = f"p_yes(material_contradiction)={contra:.3f}, review at >= {t.contradiction_review}"
    if contradiction_ablated:
        ablated("contradiction")
    elif contra >= t.contradiction_review:
        return fired(
            "contradiction",
            detail,
            WorkflowAction.HUMAN_REVIEW,
            f"a material contradiction is likely (p={contra:.3f})",
        )
    else:
        passed("contradiction", detail)

    missing = bundle.get(DecisionId.MISSING_EVIDENCE)
    assert missing is not None and missing.answer is not None
    missing_label = missing.answer.lower().replace("_", " ")
    doc = _p_yes(bundle, DecisionId.DOCUMENTATION_COMPLETE)
    detail = (
        f"p_yes(documentation_complete)={doc:.3f}, "
        f"request info below {t.documentation_request_info}"
    )
    if doc < t.documentation_request_info:
        reasons = [f"documentation is likely incomplete (p_yes={doc:.3f})"]
        if missing.answer != MissingEvidence.NONE:
            reasons.append(f"most likely missing: {missing_label} (p={missing.probability:.3f})")
        return fired("documentation", detail, WorkflowAction.REQUEST_INFO, *reasons)
    passed("documentation", detail)

    detail = (
        f"missing_evidence={missing.answer} (p={missing.probability:.3f}), "
        f"request info at >= {t.missing_evidence_request_info}"
    )
    if "missing_evidence" in ablate:
        ablated("missing_evidence")
    elif (
        missing.answer != MissingEvidence.NONE
        and missing.probability >= t.missing_evidence_request_info
    ):
        return fired(
            "missing_evidence",
            detail,
            WorkflowAction.REQUEST_INFO,
            f"missing {missing_label} (p={missing.probability:.3f})",
        )
    else:
        passed("missing_evidence", detail)

    required = {
        "diagnosis_support": _p_yes(bundle, DecisionId.DIAGNOSIS_SUPPORT),
        "step_therapy": _p_yes(bundle, DecisionId.STEP_THERAPY),
        "documentation_complete": doc,
    }
    below = [
        f"{name} p_yes={p:.3f} is below the {t.auto_process} autonomous-action bar"
        for name, p in required.items()
        if p < t.auto_process
    ]
    blocked = not contradiction_ablated and contra >= t.contradiction_auto_block
    block_rule = (
        "contradiction auto-block ABLATED"
        if contradiction_ablated
        else f"blocks at >= {t.contradiction_auto_block}"
    )
    detail = (
        f"min(required p_yes)={min(required.values()):.3f}, auto at >= {t.auto_process}; "
        f"p_yes(material_contradiction)={contra:.3f}, {block_rule}"
    )
    if not below and not blocked:
        reason = (
            f"all required judgments are at or above {t.auto_process} "
            "(contradiction auto-block ABLATED)"
            if contradiction_ablated
            else f"all required judgments are at or above {t.auto_process} and contradiction "
            f"risk is below {t.contradiction_auto_block}"
        )
        return fired("auto_process", detail, WorkflowAction.AUTO_PROCESS, reason)
    passed("auto_process", detail)

    reasons = list(below)
    if blocked:
        reasons.append(
            f"contradiction risk p={contra:.3f} blocks autonomous processing "
            f"(>= {t.contradiction_auto_block})"
        )
    return fired(
        "default_review",
        "case does not meet the autonomous-action bar",
        WorkflowAction.HUMAN_REVIEW,
        *reasons,
    )
```

- [ ] **Step 4: Run the tests**

Run: `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest tests/unit/test_engine_ablation.py tests/unit/test_engine.py -q`
Expected: all pass (17 new).

- [ ] **Step 5: Full check**

Run: `uv run ruff check . && uv run ruff format --check . && env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest -q`
Expected: all pass. (No caller passes `ablate` yet, so every reproduce guard is unaffected.)

- [ ] **Step 6: Commit**

```bash
git add relay/workflow/engine.py tests/unit/test_engine_ablation.py
git commit -m "feat: add the engine's gate-ablation switch (contradiction, missing_evidence)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Ablation in traces, manifests, replay, diffs and labels

**Files:**
- Modify: `relay/traces/models.py`
- Modify: `relay/evaluation/tracediff.py`
- Modify: `relay/reporting.py`
- Modify: `tests/integration/test_cli_regression.py:171-172`
- Modify: `tests/integration/test_committed_baselines.py:141-142`
- Test: `tests/unit/test_ablation_traces.py` (create)

**Interfaces:**
- Consumes: `determine_action(..., ablate=...)` from Task 1.
- Produces: `WorkflowTrace.ablation: list[str] | None = None`; `RunManifest.ablation: list[str] | None = None`; `TraceDiff.ablation_original` / `TraceDiff.ablation_candidate: list[str] | None = None`; `relay.evaluation.tracediff.ablation_suffix(trace: WorkflowTrace) -> str` (`" · ablate=a+b"` or `""`); `relay.reporting.ablation_line(diff: TraceDiff) -> str | None`. `replay_trace` (and so `replay_run`) re-decides with `ablate=frozenset(trace.ablation or ())` and keeps `trace.ablation` on the new trace (it is a `model_copy`).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_ablation_traces.py`:

```python
"""Ablation in traces, manifests, replay, diffs and labels (Phase 3E spec A3)."""

import json

from relay.cases.policies import load_policy
from relay.evaluation.runner import policy_text_hash
from relay.evaluation.tracediff import (
    candidate_trace_label,
    diff_traces,
    original_label,
    replay_run,
    replay_trace,
)
from relay.reporting import ablation_line, render_trace_diff
from relay.traces.models import RunManifest, WorkflowTrace
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1
from tests.factories import make_bundle, make_case, make_trace

POLICY = load_policy("immunara-v0.1")
CURRENT = policy_text_hash(POLICY)
CASE = make_case("T-01")
AUTO = WorkflowAction.AUTO_PROCESS
REVIEW = WorkflowAction.HUMAN_REVIEW


def ablated(trace, names=("contradiction",)):
    """`trace` re-decided with `names` ablated, the way relay ablate builds it."""
    marked = trace.model_copy(update={"ablation": list(names)})
    return replay_trace(marked, CASE, policy=POLICY, thresholds=trace.thresholds, git_sha="x")


def diff(a, b):
    return diff_traces(
        a,
        b,
        expected_original=REVIEW,
        expected_candidate=REVIEW,
        original_label="o",
        candidate_label="c",
        current_policy_text_hash=CURRENT,
    )


def test_a_trace_or_manifest_without_the_key_loads_as_not_ablated():
    trace = make_trace(CASE)
    raw = json.loads(trace.model_dump_json())
    del raw["ablation"]
    assert WorkflowTrace.model_validate(raw).ablation is None
    manifest = {
        "run_id": "run_x",
        "created_at": "2026-09-27T00:00:00Z",
        "dataset_id": "test",
        "dataset_path": "evals/smoke",
        "provider": "jev",
        "policy_version": "v0.1",
        "case_count": 1,
        "trace_file": "t.jsonl",
        "relay_git_sha": None,
    }
    assert RunManifest.model_validate(manifest).ablation is None
    assert RunManifest.model_validate(manifest | {"ablation": ["contradiction"]}).ablation == [
        "contradiction"
    ]


def test_replay_re_applies_the_trace_s_ablation_so_an_ablated_trace_reproduces():
    original = make_trace(CASE, make_bundle("T-01", contra=0.9))
    assert original.action is REVIEW
    once = ablated(original)
    assert (once.action, once.ablation) == (AUTO, ["contradiction"])
    again = replay_trace(once, CASE, policy=POLICY, thresholds=once.thresholds, git_sha="x")
    assert again.ablation == ["contradiction"]
    assert (again.action, again.decision_reasons, again.gate_path) == (
        once.action,
        once.decision_reasons,
        once.gate_path,
    )
    assert diff(once, again).identical


def test_replay_run_carries_ablation_through():
    original = make_trace(CASE, make_bundle("T-01", contra=0.9))
    [once] = replay_run(
        [original.model_copy(update={"ablation": ["contradiction"]})],
        [CASE],
        policy_id=None,
        auto_process=None,
    )
    assert (once.action, once.ablation) == (AUTO, ["contradiction"])


def test_diffs_record_each_side_s_ablation():
    original = make_trace(CASE, make_bundle("T-01", contra=0.9))
    candidate = ablated(original, ("contradiction", "missing_evidence"))
    d = diff(original, candidate)
    assert (d.ablation_original, d.ablation_candidate) == (
        None,
        ["contradiction", "missing_evidence"],
    )
    assert not d.identical


def test_the_ablation_line_appears_only_when_a_side_is_ablated():
    original = make_trace(CASE, make_bundle("T-01", contra=0.9))
    candidate = ablated(original, ("contradiction", "missing_evidence"))
    assert ablation_line(diff(original, original)) is None
    assert "ABLATION" not in render_trace_diff(diff(original, original))
    assert ablation_line(diff(original, candidate)) == (
        "ABLATION: none → contradiction+missing_evidence"
    )
    assert ablation_line(diff(candidate, candidate)) == (
        "ABLATION: contradiction+missing_evidence (both sides)"
    )
    text = render_trace_diff(diff(original, candidate), all_gates=True)
    assert "\nABLATION: none → contradiction+missing_evidence\n" in text
    assert "ABLATED: contradiction gate disabled" in text


def test_labels_name_the_ablation():
    plain = make_trace(CASE)
    abl = plain.model_copy(update={"ablation": ["contradiction", "missing_evidence"]})
    assert "ablate" not in original_label(plain)
    assert "ablate" not in candidate_trace_label(plain)
    assert original_label(abl).endswith("auto_process=0.95 · ablate=contradiction+missing_evidence")
    assert candidate_trace_label(abl) == (
        "candidate trace run_test · test q-test · ablate=contradiction+missing_evidence"
    )


def test_thresholds_are_untouched_by_ablation():
    original = make_trace(CASE, make_bundle("T-01", contra=0.9))
    assert ablated(original).thresholds == THRESHOLDS_V0_1
```

- [ ] **Step 2: Run it to verify it fails**

Run: `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest tests/unit/test_ablation_traces.py -q`
Expected: collection error, `ImportError: cannot import name 'ablation_line' from 'relay.reporting'`.

- [ ] **Step 3: The two model fields**

In `relay/traces/models.py`, replace:

```python
    replay_of: str | None = None
```

with:

```python
    replay_of: str | None = None
    # Phase 3E: the engine gates disabled when this trace's action was decided (sorted names from
    # relay.workflow.engine.ABLATIONS); None for every ordinary run and every pre-3E trace.
    ablation: list[str] | None = None
```

and, at the end of `RunManifest`, replace:

```python
    source_run_id: str | None = None
```

with:

```python
    source_run_id: str | None = None
    # Phase 3E: the engine gates this run disabled (relay ablate); None for an ordinary run.
    ablation: list[str] | None = None
```

- [ ] **Step 4: tracediff: the diff fields, the labels and replay**

In `relay/evaluation/tracediff.py`:

(a) At the end of `class TraceDiff`, replace:

```python
    identical: bool  # same action, reasons, gate path and decisions (volatile fields ignored)
```

with:

```python
    identical: bool  # same action, reasons, gate path and decisions (volatile fields ignored)
    # Phase 3E: each side's disabled engine gates (WorkflowTrace.ablation); None when not ablated.
    ablation_original: list[str] | None = None
    ablation_candidate: list[str] | None = None
```

(b) At the end of the `TraceDiff(...)` constructor call in `diff_traces`, replace:

```python
            and _comparable(original.decisions) == _comparable(candidate.decisions)
        ),
    )
```

with:

```python
            and _comparable(original.decisions) == _comparable(candidate.decisions)
        ),
        ablation_original=original.ablation,
        ablation_candidate=candidate.ablation,
    )
```

(c) Replace `original_label`:

```python
def original_label(trace: WorkflowTrace) -> str:
    return (
        f"{trace.run_id} · {trace.provider} {trace.question_set_version} · policy "
        f"{trace.policy_id} ({trace.policy_version}) · thresholds "
        f"auto_process={trace.thresholds.auto_process:g}"
    )
```

with:

```python
def ablation_suffix(trace: WorkflowTrace) -> str:
    """The label suffix " · ablate=<names>" for an ablated trace (Phase 3E), else ""."""
    return f" · ablate={'+'.join(trace.ablation)}" if trace.ablation else ""


def original_label(trace: WorkflowTrace) -> str:
    return (
        f"{trace.run_id} · {trace.provider} {trace.question_set_version} · policy "
        f"{trace.policy_id} ({trace.policy_version}) · thresholds "
        f"auto_process={trace.thresholds.auto_process:g}{ablation_suffix(trace)}"
    )
```

(d) Replace `candidate_trace_label`:

```python
def candidate_trace_label(trace: WorkflowTrace) -> str:
    return f"candidate trace {trace.run_id} · {trace.provider} {trace.question_set_version}"
```

with:

```python
def candidate_trace_label(trace: WorkflowTrace) -> str:
    return (
        f"candidate trace {trace.run_id} · {trace.provider} {trace.question_set_version}"
        f"{ablation_suffix(trace)}"
    )
```

(e) In `replay_trace`, replace the docstring sentence:

```python
    `git_sha` defaults to current_git_sha(); replay_run passes it once for a whole run. Raises
    ValueError if `case` is not the trace's case or its inputs changed.
```

with:

```python
    `git_sha` defaults to current_git_sha(); replay_run passes it once for a whole run. The
    trace's own ablation (Phase 3E) is re-applied, so an ablated trace reproduces. Raises
    ValueError if `case` is not the trace's case or its inputs changed.
```

and replace:

```python
    outcome = determine_action(case.input, trace.decisions, policy, thresholds)
    return trace.model_copy(
```

with:

```python
    outcome = determine_action(
        case.input, trace.decisions, policy, thresholds, ablate=frozenset(trace.ablation or ())
    )
    return trace.model_copy(
```

- [ ] **Step 5: The two test fakes forward `**kwargs`**

In `tests/integration/test_cli_regression.py` (inside `test_reproduce_passes_and_engine_drift_exits_3`), replace:

```python
    def drifted(case, bundle, policy, thresholds):
        outcome = real(case, bundle, policy, thresholds)
```

with:

```python
    def drifted(case, bundle, policy, thresholds, **kwargs):
        outcome = real(case, bundle, policy, thresholds, **kwargs)
```

In `tests/integration/test_committed_baselines.py` (inside `test_the_reproduce_guard_detects_engine_drift`), replace:

```python
    def drifted_engine(case, bundle, policy, thresholds):
        outcome = real(case, bundle, policy, thresholds)
```

with:

```python
    def drifted_engine(case, bundle, policy, thresholds, **kwargs):
        outcome = real(case, bundle, policy, thresholds, **kwargs)
```

- [ ] **Step 6: reporting: the ABLATION line**

In `relay/reporting.py`, immediately before `def render_trace_diff(`, insert:

```python
def _ablation_names(names: list[str] | None) -> str:
    return "none" if not names else "+".join(names)


def ablation_line(diff: TraceDiff) -> str | None:
    """The "ABLATION: ..." line when either side ran with disabled engine gates (Phase 3E)."""
    o, c = diff.ablation_original, diff.ablation_candidate
    if not o and not c:
        return None
    if o == c:
        return f"ABLATION: {_ablation_names(o)} (both sides)"
    return f"ABLATION: {_ablation_names(o)} → {_ablation_names(c)}"


```

and inside `render_trace_diff` replace:

```python
    if diff.policy is not None:
        lines += ["", f"POLICY CHANGED: {diff.policy[0]} → {diff.policy[1]}"]
    lines += [""] + _gate_lines(diff.gates, all_gates)
```

with:

```python
    if diff.policy is not None:
        lines += ["", f"POLICY CHANGED: {diff.policy[0]} → {diff.policy[1]}"]
    ablation = ablation_line(diff)
    if ablation is not None:
        lines += ["", ablation]
    lines += [""] + _gate_lines(diff.gates, all_gates)
```

- [ ] **Step 7: Run the tests**

Run: `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest tests/unit/test_ablation_traces.py tests/integration/test_cli_regression.py tests/integration/test_committed_baselines.py -q`
Expected: all pass (7 new).

- [ ] **Step 8: Full check, including the committed gates**

Run:

```bash
D=/tmp/relay-3e; mkdir -p "$D"
R() { env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env "$@"; }
uv run ruff check . && uv run ruff format --check . && env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest -q
R regression --config evals/regression/gates.json --strict-generated > "$D/gates-task2.txt"; echo "gates exit $?"; tail -22 "$D/gates-task2.txt"
```

Expected: all pass; `gates exit 0` with every gate PASS (old traces have no `ablation`, so replay passes an empty frozenset: the engine's default).

- [ ] **Step 9: Commit**

```bash
git add relay/traces/models.py relay/evaluation/tracediff.py relay/reporting.py tests/unit/test_ablation_traces.py tests/integration/test_cli_regression.py tests/integration/test_committed_baselines.py
git commit -m "feat: record ablation in traces and manifests, replay it, and show it in diffs and labels" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `ablate_run` and the bundle manifest

**Files:**
- Create: `relay/evaluation/ablate_run.py`
- Modify: `relay/evaluation/recompose_run.py` (`write_simulated_bundle`)
- Test: `tests/unit/test_ablate_run.py` (create)

**Interfaces:**
- Consumes: `replay_run(traces, cases, *, policy_id, auto_process, mode="simulated", run_id=None)` from `relay.evaluation.tracediff` (re-applies `trace.ablation`, Task 2); `ABLATIONS` (Task 1); `new_run_id()` from `relay.traces.store`.
- Produces:
  - `relay.evaluation.ablate_run.parse_disable(value: str) -> frozenset[str]` (ValueError messages: `--disable '<v>': give gate names separated by commas`, `cannot disable [...]; the gates that can be disabled are [...]`, `--disable '<v>' names a gate twice`).
  - `relay.evaluation.ablate_run.ablation_name(disable: frozenset[str]) -> str` (sorted, joined by `+`).
  - `relay.evaluation.ablate_run.ablate_run(traces: Sequence[WorkflowTrace], cases: Sequence[PriorAuthCase], *, disable: frozenset[str], auto_process: float | None, run_id: str | None = None) -> list[WorkflowTrace]` (ValueError `nothing to disable`, `unknown ablation(s) ...`, `run <id> is already ablated; ablate its source run`; EvalError from pairing).
  - `write_simulated_bundle(out, traces, *, dataset, source, source_manifest=None, extra: Mapping[str, object] | None = None) -> tuple[Path, Path]`: the manifest now has `ablation=traces[0].ablation`, and `extra` keys are merged into the manifest JSON after `policy_id`/`thresholds`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_ablate_run.py`:

```python
"""relay.evaluation.ablate_run: --disable parsing, ablate_run, and the bundle manifest."""

import json

import pytest

from relay.evaluation.ablate_run import ablate_run, ablation_name, parse_disable
from relay.evaluation.metrics import EvalError
from relay.evaluation.recompose_run import write_simulated_bundle
from relay.traces.models import RunManifest
from relay.traces.store import read_traces
from relay.workflow.outcomes import WorkflowAction
from tests.factories import make_bundle, make_case, make_trace

AUTO = WorkflowAction.AUTO_PROCESS
REVIEW = WorkflowAction.HUMAN_REVIEW
INFO = WorkflowAction.REQUEST_INFO
CONTRA = frozenset({"contradiction"})


def run():
    """Three cases: a contradiction review, a missing-evidence request and a clean case whose
    step_therapy (0.93) automates only at auto_process <= 0.93."""
    cases = [make_case(i) for i in ("T-01", "T-02", "T-03")]
    bundles = [
        make_bundle("T-01", contra=0.9),
        make_bundle("T-02", missing="INSURANCE_INFORMATION", missing_p=0.8),
        make_bundle("T-03", step=0.93),
    ]
    return cases, [make_trace(c, b) for c, b in zip(cases, bundles, strict=True)]


@pytest.mark.parametrize(
    "value,expected",
    [
        ("contradiction", {"contradiction"}),
        ("missing_evidence", {"missing_evidence"}),
        ("contradiction,missing_evidence", {"contradiction", "missing_evidence"}),
        (" missing_evidence , contradiction ", {"contradiction", "missing_evidence"}),
    ],
)
def test_parse_disable(value, expected):
    assert parse_disable(value) == frozenset(expected)


@pytest.mark.parametrize(
    "value,message",
    [
        ("", "give gate names separated by commas"),
        ("contradiction,", "give gate names separated by commas"),
        ("age", r"cannot disable \['age'\]"),
        ("contradiction,contradiction", "names a gate twice"),
    ],
)
def test_parse_disable_refuses(value, message):
    with pytest.raises(ValueError, match=message):
        parse_disable(value)


def test_ablation_name_is_sorted_and_joined_with_plus():
    assert ablation_name(frozenset({"missing_evidence", "contradiction"})) == (
        "contradiction+missing_evidence"
    )


def test_ablate_run_re_decides_every_trace_as_one_simulated_run():
    cases, traces = run()
    out = ablate_run(traces, cases, disable=CONTRA, auto_process=None, run_id="run_abl")
    assert [t.case_id for t in out] == ["T-01", "T-02", "T-03"]
    assert [t.action for t in out] == [AUTO, INFO, REVIEW]
    assert {t.run_id for t in out} == {"run_abl"}
    assert {t.mode for t in out} == {"simulated"}
    assert {tuple(t.ablation) for t in out} == {("contradiction",)}
    assert [t.replay_of for t in out] == [t.trace_id for t in traces]
    assert [t.decisions for t in out] == [t.decisions for t in traces]
    assert [t.ablation for t in traces] == [None, None, None]  # the source is untouched


def test_ablate_run_applies_the_operating_point_first():
    cases, traces = run()
    both = frozenset({"contradiction", "missing_evidence"})
    out = ablate_run(traces, cases, disable=both, auto_process=0.9)
    assert [t.action for t in out] == [AUTO, AUTO, AUTO]
    assert {t.thresholds.version for t in out} == {"v0.1+at0.9"}
    assert {tuple(t.ablation) for t in out} == {("contradiction", "missing_evidence")}
    assert out[0].run_id.startswith("run_")


def test_ablate_run_refuses_bad_input():
    cases, traces = run()
    with pytest.raises(ValueError, match="nothing to disable"):
        ablate_run(traces, cases, disable=frozenset(), auto_process=None)
    with pytest.raises(ValueError, match="unknown ablation"):
        ablate_run(traces, cases, disable=frozenset({"age"}), auto_process=None)
    once = ablate_run(traces, cases, disable=CONTRA, auto_process=None)
    with pytest.raises(ValueError, match="is already ablated"):
        ablate_run(once, cases, disable=CONTRA, auto_process=None)
    with pytest.raises(EvalError, match="missing"):
        ablate_run(traces, [*cases, make_case("T-04")], disable=CONTRA, auto_process=None)


def test_the_bundle_manifest_records_ablation_and_extra_keys(tmp_path):
    cases, traces = run()
    out = ablate_run(traces, cases, disable=CONTRA, auto_process=0.9, run_id="run_abl")
    trace_path, manifest_path = write_simulated_bundle(
        tmp_path / "abl",
        out,
        dataset=tmp_path / "ds",
        source=traces,
        extra={"auto_process": 0.9},
    )
    raw = json.loads(manifest_path.read_text())
    manifest = RunManifest.model_validate(raw)
    assert (manifest.mode, manifest.source_run_id, manifest.ablation) == (
        "simulated",
        "run_test",
        ["contradiction"],
    )
    assert raw["auto_process"] == 0.9
    assert raw["thresholds"]["version"] == "v0.1+at0.9"
    assert [t.ablation for t in read_traces(trace_path)] == [["contradiction"]] * 3


def test_an_unablated_bundle_has_no_ablation_and_no_extra_keys(tmp_path):
    cases, traces = run()
    _, manifest_path = write_simulated_bundle(
        tmp_path / "plain", traces, dataset=tmp_path / "ds", source=traces
    )
    raw = json.loads(manifest_path.read_text())
    assert raw["ablation"] is None
    assert "auto_process" not in raw
```

- [ ] **Step 2: Run it to verify it fails**

Run: `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest tests/unit/test_ablate_run.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'relay.evaluation.ablate_run'`.

- [ ] **Step 3: Create `relay/evaluation/ablate_run.py`**

```python
"""relay ablate: a stored run re-decided with named engine gates disabled (Phase 3E), offline.

Each trace's stored decisions go through determine_action again with `ablate` set, under the
trace's own policy and thresholds (auto_process overridden first when given: the provider's
operating point). Nothing is called. The result is one new simulated run whose traces carry
`ablation`, written in the committed-bundle format by write_simulated_bundle.
"""

from collections.abc import Sequence

from relay.cases.models import PriorAuthCase
from relay.evaluation.tracediff import replay_run
from relay.traces.models import WorkflowTrace
from relay.traces.store import new_run_id
from relay.workflow.engine import ABLATIONS


def parse_disable(value: str) -> frozenset[str]:
    """The gate names of a --disable value ("contradiction", "missing_evidence" or both,
    comma-separated). ValueError for an empty, unknown or repeated name."""
    names = [name.strip() for name in value.split(",")]
    if any(not name for name in names):
        raise ValueError(f"--disable {value!r}: give gate names separated by commas")
    unknown = sorted(set(names) - ABLATIONS)
    if unknown:
        raise ValueError(
            f"cannot disable {unknown}; the gates that can be disabled are {sorted(ABLATIONS)}"
        )
    if len(set(names)) != len(names):
        raise ValueError(f"--disable {value!r} names a gate twice")
    return frozenset(names)


def ablation_name(disable: frozenset[str]) -> str:
    """The ablation's name as used in paths and labels: sorted gate names joined by "+"."""
    return "+".join(sorted(disable))


def ablate_run(
    traces: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
    *,
    disable: frozenset[str],
    auto_process: float | None,
    run_id: str | None = None,
) -> list[WorkflowTrace]:
    """Every trace re-decided with the `disable` gates ablated, in trace order, as one new
    simulated run (run_id `run_id`, default a fresh run id; each trace's replay_of is its
    source trace).

    Pairing and hash checks are replay_run's (paired_cases: one run, full coverage, unchanged
    inputs; EvalError otherwise). ValueError for an empty or unknown `disable`, or for a run that
    is already ablated.
    """
    if not disable:
        raise ValueError("nothing to disable")
    unknown = sorted(set(disable) - ABLATIONS)
    if unknown:
        raise ValueError(f"unknown ablation(s) {unknown}; known: {sorted(ABLATIONS)}")
    if any(t.ablation for t in traces):
        raise ValueError(f"run {traces[0].run_id} is already ablated; ablate its source run")
    names = sorted(disable)
    marked = [t.model_copy(update={"ablation": names}) for t in traces]
    return replay_run(
        marked,
        cases,
        policy_id=None,
        auto_process=auto_process,
        mode="simulated",
        run_id=run_id or new_run_id(),
    )
```

- [ ] **Step 4: `write_simulated_bundle` records ablation and extra keys**

In `relay/evaluation/recompose_run.py`, replace:

```python
from collections.abc import Sequence
```

with:

```python
from collections.abc import Mapping, Sequence
```

Then replace:

```python
    source_manifest: RunManifest | None = None,
) -> tuple[Path, Path]:
    """Write out/traces.jsonl.gz and out/run-manifest.json. Refuses a non-empty `out`
    (FileExistsError). The source run's sample_limit/sample_seed carry over when its manifest is
    given."""
```

with:

```python
    source_manifest: RunManifest | None = None,
    extra: Mapping[str, object] | None = None,
) -> tuple[Path, Path]:
    """Write out/traces.jsonl.gz and out/run-manifest.json. Refuses a non-empty `out`
    (FileExistsError). The source run's sample_limit/sample_seed carry over when its manifest is
    given; the traces' ablation (Phase 3E) is recorded; `extra` keys are added to the manifest
    JSON beside policy_id and thresholds."""
```

and replace:

```python
        source_run_id=source[0].run_id,
    )
    data = manifest.model_dump(mode="json") | {
        "policy_id": first.policy_id,
        "thresholds": first.thresholds.model_dump(mode="json"),
    }
```

with:

```python
        source_run_id=source[0].run_id,
        ablation=first.ablation,
    )
    data = (
        manifest.model_dump(mode="json")
        | {
            "policy_id": first.policy_id,
            "thresholds": first.thresholds.model_dump(mode="json"),
        }
        | dict(extra or {})
    )
```

- [ ] **Step 5: Run the tests**

Run: `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest tests/unit/test_ablate_run.py tests/integration/test_cli_recompose.py -q`
Expected: all pass (14 new; recompose unchanged).

- [ ] **Step 6: Full check**

Run: `uv run ruff check . && uv run ruff format --check . && env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add relay/evaluation/ablate_run.py relay/evaluation/recompose_run.py tests/unit/test_ablate_run.py
git commit -m "feat: add ablate_run and record ablation in simulated bundle manifests" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `relay ablate`

**Files:**
- Modify: `relay/cli.py` (module docstring, one import, a new command after `recompose`)
- Modify: `relay/evaluation/regression_run.py` (`_write_simulated_run`)
- Test: `tests/integration/test_cli_ablate.py` (create)

**Interfaces:**
- Consumes: `parse_disable`, `ablation_name`, `ablate_run` (Task 3); `write_simulated_bundle(..., extra=...)` (Task 3); existing CLI helpers `_fail`, `_load_cases`, `_read_trace_file`, `find_run_manifest`, `sample_cases`, `replay_run`, `EvalError`, `RegressionInputError`, and the `TraceFile`/`Dataset` option types, all already imported in `relay/cli.py`.
- Produces: `relay ablate --traces FILE --dataset DIR --disable NAME[,NAME] [--at X] --out DIR`. Exit 0 prints three lines: `Ablated run <source run_id> (<provider> <question set>): <ablation name> disabled at auto_process=<t:g>, thresholds <version>: action changed on <k> of <n> case(s) versus the same run at the same threshold.`, `Simulated run: <run_id>`, `Traces: <path>` / `Manifest: <path>`. Exit 2 for every input problem. The candidate manifest a regression `--out` writes for a re-decided candidate carries `ablation`.

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_cli_ablate.py`:

```python
"""relay ablate, offline: smoke runs from the groundtruth provider, a doctored copy with one
provider mistake, and the regression gate over the ablated bundle. Never builds a client."""

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

import relay.cli as cli_module
from relay.cases.loader import load_dataset
from relay.cases.policies import load_policy
from relay.cli import app
from relay.evaluation.tracediff import replay_trace
from relay.traces.models import RunManifest
from relay.traces.store import read_traces
from relay.workflow.outcomes import WorkflowAction
from tests.factories import make_bundle

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
runner = CliRunner()


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--env-file", str(tmp_path / "missing.env"), *map(str, args)])


class NoClient:
    def __init__(self, *args, **kwargs):
        raise AssertionError("relay ablate must not build a network client")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", NoClient)
    monkeypatch.setattr(cli_module, "AsyncAnthropic", NoClient)


@pytest.fixture(scope="module")
def groundtruth_run(tmp_path_factory):
    root = tmp_path_factory.mktemp("ablate-cli")
    result = invoke(
        root,
        "run",
        "--dataset",
        SMOKE,
        "--provider",
        "groundtruth",
        "--traces-dir",
        root / "traces",
        "--reports-dir",
        root / "reports",
    )
    assert result.exit_code == 0, result.output
    [trace_file] = (root / "traces").glob("*.jsonl")
    return trace_file


@pytest.fixture(scope="module")
def mistaken_run(groundtruth_run, tmp_path_factory):
    """The groundtruth run with one provider mistake: ADV-01 (a material contradiction; step
    therapy is NOT satisfied) judged all-high except contradiction p=0.9. Only the contradiction
    gate keeps it from AUTO_PROCESS."""
    root = tmp_path_factory.mktemp("ablate-mistaken")
    cases = {c.input.id: c for c in load_dataset(SMOKE)}
    policy = load_policy("immunara-v0.1")
    traces = []
    for trace in read_traces(groundtruth_run):
        if trace.case_id == "ADV-01":
            doctored = trace.model_copy(update={"decisions": make_bundle("ADV-01", contra=0.9)})
            trace = replay_trace(
                doctored,
                cases["ADV-01"],
                policy=policy,
                thresholds=trace.thresholds,
                git_sha="test",
                mode="evaluate",
                run_id=trace.run_id,
            ).model_copy(update={"replay_of": None})
        traces.append(trace)
    path = root / "mistaken.jsonl"
    path.write_text("".join(t.model_dump_json() + "\n" for t in traces), encoding="utf-8")
    return path


def ablate(tmp_path, traces, disable, name, *extra):
    return invoke(
        tmp_path,
        "ablate",
        "--traces",
        traces,
        "--dataset",
        SMOKE,
        "--disable",
        disable,
        "--out",
        tmp_path / name,
        *extra,
    )


def test_ablate_writes_a_simulated_bundle(tmp_path, groundtruth_run):
    result = ablate(tmp_path, groundtruth_run, "contradiction,missing_evidence", "both")
    assert result.exit_code == 0, result.output
    source = read_traces(groundtruth_run)
    assert (
        f"Ablated run {source[0].run_id} (groundtruth groundtruth): "
        "contradiction+missing_evidence disabled at auto_process=0.95, thresholds v0.1: "
        "action changed on 0 of 10 case(s) versus the same run at the same threshold."
    ) in result.output
    out = read_traces(tmp_path / "both" / "traces.jsonl.gz")
    assert [t.case_id for t in out] == [t.case_id for t in source]
    assert {tuple(t.ablation) for t in out} == {("contradiction", "missing_evidence")}
    assert {t.mode for t in out} == {"simulated"}
    raw = json.loads((tmp_path / "both" / "run-manifest.json").read_text())
    manifest = RunManifest.model_validate(raw)
    assert (manifest.mode, manifest.source_run_id, manifest.ablation) == (
        "simulated",
        source[0].run_id,
        ["contradiction", "missing_evidence"],
    )
    assert (raw["auto_process"], raw["thresholds"]["version"], raw["policy_id"]) == (
        0.95,
        "v0.1",
        "immunara-v0.1",
    )
    assert f"Simulated run: {out[0].run_id}" in result.output


def test_at_applies_the_operating_point(tmp_path, groundtruth_run):
    result = ablate(tmp_path, groundtruth_run, "missing_evidence", "me", "--at", "0.9")
    assert result.exit_code == 0, result.output
    assert "missing_evidence disabled at auto_process=0.9, thresholds v0.1+at0.9" in result.output
    raw = json.loads((tmp_path / "me" / "run-manifest.json").read_text())
    assert (raw["auto_process"], raw["ablation"]) == (0.9, ["missing_evidence"])


def test_a_contradiction_ablation_makes_a_newly_unsafe_case_the_gate_reports(
    tmp_path, mistaken_run
):
    result = ablate(tmp_path, mistaken_run, "contradiction", "contra")
    assert result.exit_code == 0, result.output
    assert "action changed on 1 of 10 case(s)" in result.output
    [adv] = [
        t for t in read_traces(tmp_path / "contra" / "traces.jsonl.gz") if t.case_id == "ADV-01"
    ]
    assert adv.action is WorkflowAction.AUTO_PROCESS
    gate = invoke(
        tmp_path,
        "regression",
        "--dataset",
        SMOKE,
        "--baseline",
        mistaken_run,
        "--candidate-traces",
        tmp_path / "contra" / "traces.jsonl.gz",
        "--out",
        tmp_path / "contra",
    )
    assert gate.exit_code == 4, gate.output
    assert "· ablate=contradiction" in gate.output
    assert gate.output.splitlines()[-1] == (
        "REGRESSION GATE: FAIL — 1 newly unsafe case(s) without a waiver: ADV-01"
    )
    verdict = json.loads((tmp_path / "contra" / "regression.json").read_text())
    assert [e["case_id"] for e in verdict["newly_unsafe"]] == ["ADV-01"]


def test_an_ablated_bundle_reproduces(tmp_path, mistaken_run):
    assert ablate(tmp_path, mistaken_run, "contradiction", "contra").exit_code == 0
    trace_file = tmp_path / "contra" / "traces.jsonl.gz"
    gate = invoke(
        tmp_path, "regression", "--dataset", SMOKE, "--baseline", trace_file, "--reproduce"
    )
    assert gate.exit_code == 0, gate.output
    replay = invoke(tmp_path, "replay", "ADV-01", "--traces", trace_file, "--dataset", SMOKE)
    assert replay.exit_code == 0, replay.output
    assert "ABLATION: contradiction (both sides)" in replay.output


def test_a_re_decided_ablated_candidate_keeps_its_ablation(tmp_path, mistaken_run):
    assert ablate(tmp_path, mistaken_run, "contradiction", "contra").exit_code == 0
    gate = invoke(
        tmp_path,
        "regression",
        "--dataset",
        SMOKE,
        "--baseline",
        mistaken_run,
        "--candidate-traces",
        tmp_path / "contra" / "traces.jsonl.gz",
        "--candidate-at",
        "0.9",
        "--out",
        tmp_path / "gate",
    )
    assert gate.exit_code == 4, gate.output
    raw = json.loads((tmp_path / "gate" / "candidate.manifest.json").read_text())
    assert raw["ablation"] == ["contradiction"]


def test_a_sampled_run_is_ablated_on_its_own_sample(tmp_path):
    run = invoke(
        tmp_path,
        "run",
        "--dataset",
        SMOKE,
        "--provider",
        "groundtruth",
        "--limit",
        "5",
        "--sample-seed",
        "7",
        "--traces-dir",
        tmp_path / "traces",
        "--reports-dir",
        tmp_path / "reports",
    )
    assert run.exit_code == 0, run.output
    [trace_file] = (tmp_path / "traces").glob("*.jsonl")
    result = ablate(tmp_path, trace_file, "contradiction", "sampled")
    assert result.exit_code == 0, result.output
    assert "action changed on 0 of 5 case(s)" in result.output
    manifest = RunManifest.model_validate_json(
        (tmp_path / "sampled" / "run-manifest.json").read_text()
    )
    assert (manifest.case_count, manifest.sample_limit, manifest.sample_seed) == (5, 5, 7)


@pytest.mark.parametrize(
    "args,message",
    [
        (["--disable", "age"], "cannot disable ['age']"),
        (["--disable", ""], "give gate names separated by commas"),
        (["--disable", "contradiction", "--at", "0"], "--at must be > 0"),
    ],
)
def test_bad_flags_are_exit_2(tmp_path, groundtruth_run, args, message):
    result = invoke(
        tmp_path,
        "ablate",
        "--traces",
        groundtruth_run,
        "--dataset",
        SMOKE,
        "--out",
        tmp_path / "x",
        *args,
    )
    assert result.exit_code == 2
    assert message in result.output
    assert not (tmp_path / "x").exists()


def test_input_refusals_are_exit_2(tmp_path, groundtruth_run):
    assert ablate(tmp_path, groundtruth_run, "contradiction", "once").exit_code == 0
    again = ablate(tmp_path, groundtruth_run, "contradiction", "once")
    assert again.exit_code == 2 and "is not empty" in again.output
    twice = ablate(tmp_path, tmp_path / "once" / "traces.jsonl.gz", "missing_evidence", "twice")
    assert twice.exit_code == 2 and "is already ablated" in twice.output
    other = tmp_path / "other"
    shutil.copytree(SMOKE / "AUTO-01", other / "AUTO-01")
    partial = invoke(
        tmp_path,
        "ablate",
        "--traces",
        groundtruth_run,
        "--dataset",
        other,
        "--disable",
        "contradiction",
        "--out",
        tmp_path / "partial",
    )
    assert partial.exit_code == 2 and "trace for unknown case" in partial.output
```

- [ ] **Step 2: Run it to verify it fails**

Run: `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest tests/integration/test_cli_ablate.py -q`
Expected: failures; `relay ablate` exits 2 with `No such command 'ablate'`.

- [ ] **Step 3: The command**

In `relay/cli.py`:

(a) Replace the module docstring's second line:

```python
"""relay run / eval / generate, and the offline analyses sweep / report / compare / replay /
regression."""
```

with:

```python
"""relay run / eval / generate, and the offline analyses sweep / report / compare / replay /
regression / recompose / ablate."""
```

(b) Replace:

```python
from relay.evaluation.artifacts import write_eval_bundle
```

with:

```python
from relay.evaluation.ablate_run import ablate_run, ablation_name, parse_disable
from relay.evaluation.artifacts import write_eval_bundle
```

(c) Insert this command between the end of `recompose` (its last line is `    typer.echo(f"Traces: {trace_path}\nManifest: {manifest_path}")`) and `@app.command()` / `def bench(`:

```python
@app.command()
def ablate(
    traces: TraceFile,
    dataset: Dataset,
    disable: Annotated[
        str,
        typer.Option(
            help="Engine gate(s) to disable, comma-separated: contradiction, missing_evidence."
        ),
    ],
    out: Annotated[
        Path, typer.Option(help="Directory for traces.jsonl.gz and run-manifest.json (new).")
    ],
    at: Annotated[
        float | None,
        typer.Option(
            min=0.0,
            max=1.0,
            help="Re-decide at this auto_process threshold (the provider's operating point).",
        ),
    ] = None,
) -> None:
    """Re-decide a stored run with engine gates disabled, as a simulated run (offline).

    The gate-ablation experiment (Phase 3E): the stored decisions go through today's engine with
    the --disable gates skipped; nothing is called. Exit 2 on any input problem (unknown gate,
    cases changed, an already-ablated run, non-empty --out).
    """
    try:
        names = parse_disable(disable)
    except ValueError as error:
        raise _fail(str(error)) from error
    if at is not None and at <= 0.0:
        raise _fail("--at must be > 0 (auto_process must be > 0)")
    cases = _load_cases(dataset)
    source = _read_trace_file(traces)
    if not source:
        raise _fail(f"{traces}: no traces")
    try:
        manifest = find_run_manifest(traces)
    except RegressionInputError as error:
        raise _fail(str(error)) from error
    if manifest is not None and manifest.run_id != source[0].run_id:
        manifest = None  # a manifest left over from another run: carry nothing over
    if manifest is not None and manifest.sample_limit is not None:
        if manifest.sample_seed is None:
            raise _fail(f"{traces}: run manifest has sample_limit but no sample_seed")
        cases = sample_cases(cases, manifest.sample_limit, manifest.sample_seed)
    try:
        ablated = ablate_run(source, cases, disable=names, auto_process=at)
        unablated = replay_run(source, cases, policy_id=None, auto_process=at)
    except (EvalError, ValueError) as error:
        raise _fail(f"--traces {traces}: {error}") from error
    first = ablated[0]
    try:
        trace_path, manifest_path = write_simulated_bundle(
            out,
            ablated,
            dataset=dataset,
            source=source,
            source_manifest=manifest,
            extra={"auto_process": first.thresholds.auto_process},
        )
    except FileExistsError as error:
        raise _fail(str(error)) from error
    changed = sum(a.action != u.action for a, u in zip(ablated, unablated, strict=True))
    typer.echo(
        f"Ablated run {source[0].run_id} ({first.provider} {first.question_set_version}): "
        f"{ablation_name(names)} disabled at auto_process={first.thresholds.auto_process:g}, "
        f"thresholds {first.thresholds.version}: action changed on {changed} of "
        f"{len(ablated)} case(s) versus the same run at the same threshold."
    )
    typer.echo(f"Simulated run: {first.run_id}")
    typer.echo(f"Traces: {trace_path}\nManifest: {manifest_path}")


```

- [ ] **Step 4: A re-decided ablated regression candidate keeps its ablation**

In `relay/evaluation/regression_run.py`, inside `_write_simulated_run`, replace:

```python
        source_run_id=first.run_id.removeprefix("replay-"),
    )
```

with:

```python
        source_run_id=first.run_id.removeprefix("replay-"),
        ablation=first.ablation,
    )
```

- [ ] **Step 5: Run the tests**

Run: `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest tests/integration/test_cli_ablate.py tests/integration/test_cli_regression.py tests/integration/test_regression_run.py -q`
Expected: all pass (10 new).

- [ ] **Step 6: Smoke the command by hand (offline)**

```bash
D=/tmp/relay-3e; mkdir -p "$D"
R() { env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env "$@"; }
rm -rf "$D/smoke-ablate"
R ablate --traces evals/baselines/gold-v0.1/run_20260927T072623Z_ad6f44/traces.jsonl.gz --dataset evals/gold --disable contradiction --at 0.81 --out "$D/smoke-ablate"
```

Expected first line: `Ablated run run_20260927T072623Z_ad6f44 (jev q-v0.3): contradiction disabled at auto_process=0.81, thresholds v0.1+at0.81: action changed on 5 of 100 case(s) versus the same run at the same threshold.` Nothing is written inside the repository.

- [ ] **Step 7: Full check**

Run: `uv run ruff check . && uv run ruff format --check . && env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add relay/cli.py relay/evaluation/regression_run.py tests/integration/test_cli_ablate.py
git commit -m "feat: add relay ablate (engine gates disabled, as an offline simulated run)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The summary-table script

**Files:**
- Create: `scripts/phase3e_table.py`
- Test: `tests/unit/test_phase3e_table.py` (create)

**Interfaces:**
- Consumes: the `RegressionResult` JSON shape written by `relay regression --out` (keys used: `n`, `verdict`, `change_counts.unchanged`, `newly_unsafe[].case_id`, `regressed`, `improved`, and per side `identity.run_id`/`provider`/`question_set_versions`/`thresholds_versions`, `automation`, `uar` as `{count, n, rate, ci95: {low, high} | null}`).
- Produces: `scripts.phase3e_table.summary_row(dataset, run, ablation, result) -> dict`, `collect(root: Path) -> list[dict]`, `render(rows) -> str`, `main(argv) -> int`. `uv run python -m scripts.phase3e_table [ROOT]` (default `evals/baselines/ablation`) writes `ROOT/summary.md` (exactly `render(collect(ROOT))`) and `ROOT/summary.json` (`json.dumps(rows, indent=2) + "\n"`) and prints the Markdown; exit 2 on bad usage or no files.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_phase3e_table.py`:

```python
"""scripts/phase3e_table.py: the ablation summary over regression.json files."""

import json

from scripts.phase3e_table import collect, main, render, summary_row


def rate(count, n):
    if n == 0:
        return {"count": count, "n": n, "rate": None, "ci95": None}
    return {"count": count, "n": n, "rate": count / n, "ci95": {"low": 0.01, "high": 0.5}}


def result(*, newly_unsafe=(), unchanged=98, auto=(29, 32), unsafe=(1, 3), verdict="FAIL"):
    def side(run_id, auto_count, unsafe_count):
        return {
            "identity": {
                "run_id": run_id,
                "provider": "jev",
                "question_set_versions": ["q-v0.3"],
                "thresholds_versions": ["v0.1+at0.81"],
            },
            "automation": rate(auto_count, 100),
            "uar": rate(unsafe_count, auto_count),
        }

    return {
        "n": 100,
        "verdict": verdict,
        "baseline": side("replay-run_src", auto[0], unsafe[0]),
        "candidate": side("run_abl", auto[1], unsafe[1]),
        "change_counts": {
            "improved": 0,
            "unchanged": unchanged,
            "regressed": 100 - unchanged,
            "changed-both-wrong": 0,
        },
        "newly_unsafe": [{"case_id": c} for c in newly_unsafe],
        "regressed": [{"case_id": "X"}] * (100 - unchanged),
        "improved": [],
    }


def write(root, dataset, run, ablation, data):
    path = root / dataset / run / ablation / "regression.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_summary_row():
    row = summary_row("gold-v0.1", "jev-q-v0.3", "contradiction", result(newly_unsafe=["G-1"]))
    assert row["source_run_id"] == "run_src"
    assert (row["provider"], row["thresholds"]) == ("jev q-v0.3", "v0.1+at0.81")
    assert (row["actions_changed"], row["newly_unsafe"], row["regressed"]) == (2, ["G-1"], 2)
    assert row["automation"]["ablated"]["count"] == 32


def test_rows_follow_dataset_run_and_ablation_order(tmp_path):
    still = result(unchanged=100, auto=(10, 10), unsafe=(0, 0), verdict="PASS")
    write(tmp_path, "gold-v0.1", "jev-q-v0.3", "missing_evidence", still)
    write(tmp_path, "gold-v0.1", "jev-q-v0.3", "contradiction", result(newly_unsafe=["G-1"]))
    write(tmp_path, "gold-v0.1", "groundtruth", "contradiction", still)
    write(tmp_path, "gen-v0.2-holdout", "rules", "contradiction+missing_evidence", still)
    rows = collect(tmp_path)
    assert [(r["dataset"], r["run"], r["ablation"]) for r in rows] == [
        ("gen-v0.2-holdout", "rules", "contradiction+missing_evidence"),
        ("gold-v0.1", "groundtruth", "contradiction"),
        ("gold-v0.1", "jev-q-v0.3", "contradiction"),
        ("gold-v0.1", "jev-q-v0.3", "missing_evidence"),
    ]


def test_render_marks_null_results_and_failing_pairs(tmp_path):
    still = result(unchanged=100, auto=(10, 10), unsafe=(0, 0), verdict="PASS")
    write(tmp_path, "gold-v0.1", "jev-q-v0.3", "contradiction", result(newly_unsafe=["G-1"]))
    write(tmp_path, "gold-v0.1", "jev-q-v0.3", "missing_evidence", still)
    text = render(collect(tmp_path))
    assert (
        "| gold-v0.1 | jev-q-v0.3 (`run_src`) | jev q-v0.3 | v0.1+at0.81 | contradiction | FAIL "
        "| 2/100 | 1 (G-1) | 2 | 0 | 29/100 (29.0%) [1.0%, 50.0%] → 32/100 (32.0%) [1.0%, 50.0%] "
        "| 1/29 (3.4%) [1.0%, 50.0%] → 3/32 (9.4%) [1.0%, 50.0%] |"
    ) in text
    assert "| missing_evidence | PASS | 0/100 | 0 | 0 | 0 |" in text
    assert (
        "Null results (no action changed): 1\n- gold-v0.1 / jev-q-v0.3 × missing_evidence" in text
    )
    assert (
        "Pairs whose gate FAILs (a newly unsafe automation): 1\n"
        "- gold-v0.1 / jev-q-v0.3 × contradiction: G-1"
    ) in text


def test_an_empty_rate_renders_as_n_a(tmp_path):
    none = result(unchanged=100, auto=(0, 0), unsafe=(0, 0), verdict="PASS")
    write(tmp_path, "gold-v0.1", "rules", "contradiction", none)
    assert "0/0 (n/a) → 0/0 (n/a)" in render(collect(tmp_path))


def test_main_writes_summary_md_and_json(tmp_path, capsys):
    write(tmp_path, "gold-v0.1", "jev-q-v0.3", "contradiction", result(newly_unsafe=["G-1"]))
    assert main([str(tmp_path)]) == 0
    printed = capsys.readouterr().out
    assert (tmp_path / "summary.md").read_text() == printed
    [row] = json.loads((tmp_path / "summary.json").read_text())
    assert row["newly_unsafe"] == ["G-1"]
    assert main([str(tmp_path / "empty")]) == 2
    assert main(["a", "b"]) == 2
```

- [ ] **Step 2: Run it to verify it fails**

Run: `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest tests/unit/test_phase3e_table.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'scripts.phase3e_table'`.

- [ ] **Step 3: Create `scripts/phase3e_table.py`**

```python
"""Phase 3E summary table over the committed ablation regression.json files (offline).

uv run python -m scripts.phase3e_table [ROOT]
    ROOT (default evals/baselines/ablation) holds <dataset>/<run>/<ablation>/regression.json,
    one per (run, ablation) pair: the run at its operating point (baseline) against the same
    stored decisions re-decided with the named gate(s) disabled (candidate). Writes
    ROOT/summary.md and ROOT/summary.json and prints the Markdown.
"""

import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("evals/baselines/ablation")
DATASET_ORDER = ("gen-v0.2-holdout", "gen-v0.3-holdout", "gen-v0.3-shift", "gold-v0.1")
RUN_ORDER = (
    "groundtruth",
    "jev-q-v0.2",
    "rules",
    "claude",
    "claude-150",
    "jev-q-v0.3",
    "jev-q-v0.3-aware",
)
ABLATION_ORDER = ("contradiction", "missing_evidence", "contradiction+missing_evidence")

HEADER = [
    "# Gate ablation (Phase 3E)",
    "",
    "Generated by `uv run python -m scripts.phase3e_table` from the committed `regression.json`",
    "files beside it. Each row re-decides one committed run's stored decisions with the named",
    "engine gate(s) disabled (the candidate) and gates it against the same run at the same",
    "threshold (the baseline). Expected actions always come from the full engine. Offline, $0.",
    "",
    "| Dataset | Run | Provider | Thresholds | Ablation | Gate | Actions changed | Newly unsafe "
    "| Regressed | Improved | Automation (baseline → ablated) | UAR (baseline → ablated) |",
    "|---|---|---|---|---|---|---|---|---|---|---|---|",
]


def _rate(rate: dict[str, Any]) -> str:
    if rate["rate"] is None:
        return f"{rate['count']}/{rate['n']} (n/a)"
    ci = rate["ci95"]
    return f"{rate['count']}/{rate['n']} ({rate['rate']:.1%}) [{ci['low']:.1%}, {ci['high']:.1%}]"


def _order(values: tuple[str, ...], value: str) -> tuple[int, str]:
    return (values.index(value) if value in values else len(values), value)


def summary_row(dataset: str, run: str, ablation: str, result: dict[str, Any]) -> dict[str, Any]:
    """One table row from one regression.json (as a dict)."""
    base, cand = result["baseline"], result["candidate"]
    identity = cand["identity"]
    return {
        "dataset": dataset,
        "run": run,
        "source_run_id": base["identity"]["run_id"].removeprefix("replay-"),
        "provider": f"{identity['provider']} {', '.join(identity['question_set_versions'])}",
        "thresholds": ", ".join(identity["thresholds_versions"]),
        "ablation": ablation,
        "verdict": result["verdict"],
        "n": result["n"],
        "actions_changed": result["n"] - result["change_counts"]["unchanged"],
        "newly_unsafe": [entry["case_id"] for entry in result["newly_unsafe"]],
        "regressed": len(result["regressed"]),
        "improved": len(result["improved"]),
        "automation": {"baseline": base["automation"], "ablated": cand["automation"]},
        "uar": {"baseline": base["uar"], "ablated": cand["uar"]},
    }


def collect(root: Path) -> list[dict[str, Any]]:
    """Every <dataset>/<run>/<ablation>/regression.json under root, as rows in table order."""
    rows = [
        summary_row(
            path.parts[-4],
            path.parts[-3],
            path.parts[-2],
            json.loads(path.read_text(encoding="utf-8")),
        )
        for path in root.glob("*/*/*/regression.json")
    ]
    return sorted(
        rows,
        key=lambda r: (
            _order(DATASET_ORDER, r["dataset"]),
            _order(RUN_ORDER, r["run"]),
            _order(ABLATION_ORDER, r["ablation"]),
        ),
    )


def render(rows: list[dict[str, Any]]) -> str:
    lines = list(HEADER)
    for r in rows:
        unsafe = r["newly_unsafe"]
        unsafe_cell = f"{len(unsafe)} ({', '.join(unsafe)})" if unsafe else "0"
        lines.append(
            f"| {r['dataset']} | {r['run']} (`{r['source_run_id']}`) | {r['provider']} | "
            f"{r['thresholds']} | {r['ablation']} | {r['verdict']} | "
            f"{r['actions_changed']}/{r['n']} | {unsafe_cell} | {r['regressed']} | "
            f"{r['improved']} | {_rate(r['automation']['baseline'])} → "
            f"{_rate(r['automation']['ablated'])} | {_rate(r['uar']['baseline'])} → "
            f"{_rate(r['uar']['ablated'])} |"
        )
    null = [r for r in rows if r["actions_changed"] == 0]
    lines += ["", f"Null results (no action changed): {len(null)}"]
    lines += [f"- {r['dataset']} / {r['run']} × {r['ablation']}" for r in null] or ["- none"]
    failing = [r for r in rows if r["verdict"] == "FAIL"]
    lines += ["", f"Pairs whose gate FAILs (a newly unsafe automation): {len(failing)}"]
    lines += [
        f"- {r['dataset']} / {r['run']} × {r['ablation']}: {', '.join(r['newly_unsafe'])}"
        for r in failing
    ] or ["- none"]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(argv[0]) if argv else DEFAULT_ROOT
    rows = collect(root)
    if not rows:
        print(f"no */*/*/regression.json under {root}", file=sys.stderr)
        return 2
    text = render(rows)
    (root / "summary.md").write_text(text, encoding="utf-8")
    (root / "summary.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the tests**

Run: `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest tests/unit/test_phase3e_table.py -q`
Expected: 5 passed.

- [ ] **Step 5: Full check**

Run: `uv run ruff check . && uv run ruff format --check . && env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/phase3e_table.py tests/unit/test_phase3e_table.py
git commit -m "feat: add the Phase 3E ablation summary-table script" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The 30 ablations, their regressions, the summary and the reproduce gate

**Files:**
- Create: `evals/baselines/ablation/<dataset>/<run>/<ablation>/` × 30 (generated), `evals/baselines/ablation/summary.md`, `evals/baselines/ablation/summary.json`
- Modify: `evals/regression/gates.json` (append one gate)
- Modify: `tests/integration/test_committed_gates.py` (the gate-name list)
- Test: `tests/integration/test_committed_ablation.py` (create)

**Interfaces:**
- Consumes: `relay ablate` (Task 4), `relay regression` (3B), `scripts/phase3e_table.py` (Task 5).
- Produces: the committed artifacts Task 7 quotes, and the gate `gold-reproduce-ablated-jev-q-v0.3-contradiction`.

- [ ] **Step 1: Preflight**

```bash
D=/tmp/relay-3e; mkdir -p "$D"
R() { env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env "$@"; }
git status --short
test ! -e evals/baselines/ablation && echo "ablation dir absent: OK"
for d in gen-v0.2-holdout gen-v0.3-holdout gen-v0.3-shift; do
  R generate --verify "evals/generated/manifests/$d.json" --out "evals/generated/$d" | tail -1
done
```

Expected: `git status --short` lists nothing of yours (a ` M README.md` from the other agent's unfinished task is the only acceptable line; leave it alone); `ablation dir absent: OK`; three lines starting `OK: gen-v0.2-holdout regenerates to sha256:958fbfc3…`, `OK: gen-v0.3-holdout regenerates to sha256:2aefa63d…`, `OK: gen-v0.3-shift regenerates to sha256:3f5a9c1c…`. If a dataset is missing or does not verify, stop and report (do not regenerate into the checkout without asking).

- [ ] **Step 2: Write the failing test**

Create `tests/integration/test_committed_ablation.py`:

```python
"""The committed Phase 3E ablation artifacts (evals/baselines/ablation/): 10 runs × 3 ablations,
each an ablated simulated bundle plus its regression output, and summary.md/summary.json
regenerated byte for byte from the committed regression.json files. Offline."""

import json
from pathlib import Path

from relay.traces.models import RunManifest
from scripts.phase3e_table import collect, render

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "evals" / "baselines" / "ablation"
ABLATIONS = {
    "contradiction": ["contradiction"],
    "missing_evidence": ["missing_evidence"],
    "contradiction+missing_evidence": ["contradiction", "missing_evidence"],
}
# (dataset, run directory name) -> (committed source run directory, auto_process used)
RUNS = {
    ("gen-v0.2-holdout", "jev-q-v0.2"): ("gen-v0.2-holdout/run_20260925T075242Z_fd455f", 0.89),
    ("gen-v0.2-holdout", "rules"): ("gen-v0.2-holdout/run_20260925T092425Z_0aee97", 0.99),
    ("gen-v0.2-holdout", "claude-150"): ("gen-v0.2-holdout/run_20260925T212034Z_bbee49", 0.55),
    ("gen-v0.3-holdout", "jev-q-v0.3"): ("gen-v0.3-holdout/run_20260927T072144Z_12e1e4", 0.81),
    ("gen-v0.3-shift", "jev-q-v0.3-aware"): ("gen-v0.3-shift/aware-immunara-v0.2", 0.95),
    ("gold-v0.1", "groundtruth"): ("gold-v0.1/run_20260925T170825Z_440df0", 0.95),
    ("gold-v0.1", "jev-q-v0.2"): ("gold-v0.1/run_20260925T170857Z_b95be9", 0.89),
    ("gold-v0.1", "rules"): ("gold-v0.1/run_20260925T170839Z_d3b427", 0.99),
    ("gold-v0.1", "claude"): ("gold-v0.1/run_20260926T011730Z_f1852f", 0.55),
    ("gold-v0.1", "jev-q-v0.3"): ("gold-v0.1/run_20260927T072623Z_ad6f44", 0.81),
}


def test_every_run_has_all_three_ablations_and_nothing_else():
    found = {tuple(p.relative_to(ROOT).parts[:3]) for p in ROOT.glob("*/*/*/regression.json")}
    assert found == {(d, r, a) for (d, r) in RUNS for a in ABLATIONS}


def test_each_bundle_records_its_source_ablation_and_operating_point():
    for (dataset, run), (source_dir, auto_process) in RUNS.items():
        source = json.loads(
            (REPO / "evals/baselines" / source_dir / "run-manifest.json").read_text()
        )
        for ablation, names in ABLATIONS.items():
            directory = ROOT / dataset / run / ablation
            raw = json.loads((directory / "run-manifest.json").read_text())
            manifest = RunManifest.model_validate(raw)
            label = f"{dataset}/{run}/{ablation}"
            assert (manifest.mode, manifest.ablation) == ("simulated", names), label
            assert manifest.source_run_id == source["run_id"], label
            assert raw["auto_process"] == auto_process, label
            assert manifest.sample_limit == source.get("sample_limit"), label
            assert (directory / "traces.jsonl.gz").is_file(), label
            assert (directory / "regression.md").is_file(), label


def test_the_summary_is_regenerated_from_the_committed_regression_files():
    rows = collect(ROOT)
    assert len(rows) == 30
    assert (ROOT / "summary.md").read_text(encoding="utf-8") == render(rows)
    assert json.loads((ROOT / "summary.json").read_text(encoding="utf-8")) == rows
```

- [ ] **Step 3: Run it to verify it fails**

Run: `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest tests/integration/test_committed_ablation.py -q`
Expected: 3 failed (no `evals/baselines/ablation/` yet: the set comparison fails, then `FileNotFoundError`s).

- [ ] **Step 4: Generate the 30 ablated bundles and their regressions**

Write the driver to `/tmp/relay-3e/ablate_all.sh` and run it with bash from the repository root. Each pair runs `relay ablate` into an empty directory, then `relay regression --out` into the same directory. Regression exit 4 (a FAIL) is an expected result here, not an error.

```bash
D=/tmp/relay-3e; mkdir -p "$D"
cat > "$D/ablate_all.sh" <<'SH'
set -u
R() { env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env "$@"; }
B=evals/baselines
# dataset_id | dataset dir | source run dir (under evals/baselines) | run name | operating point or -
RUNS="gen-v0.2-holdout|evals/generated/gen-v0.2-holdout|gen-v0.2-holdout/run_20260925T075242Z_fd455f|jev-q-v0.2|0.89
gen-v0.2-holdout|evals/generated/gen-v0.2-holdout|gen-v0.2-holdout/run_20260925T092425Z_0aee97|rules|0.99
gen-v0.2-holdout|evals/generated/gen-v0.2-holdout|gen-v0.2-holdout/run_20260925T212034Z_bbee49|claude-150|0.55
gen-v0.3-holdout|evals/generated/gen-v0.3-holdout|gen-v0.3-holdout/run_20260927T072144Z_12e1e4|jev-q-v0.3|0.81
gen-v0.3-shift|evals/generated/gen-v0.3-shift|gen-v0.3-shift/aware-immunara-v0.2|jev-q-v0.3-aware|-
gold-v0.1|evals/gold|gold-v0.1/run_20260925T170825Z_440df0|groundtruth|-
gold-v0.1|evals/gold|gold-v0.1/run_20260925T170857Z_b95be9|jev-q-v0.2|0.89
gold-v0.1|evals/gold|gold-v0.1/run_20260925T170839Z_d3b427|rules|0.99
gold-v0.1|evals/gold|gold-v0.1/run_20260926T011730Z_f1852f|claude|0.55
gold-v0.1|evals/gold|gold-v0.1/run_20260927T072623Z_ad6f44|jev-q-v0.3|0.81"
echo "$RUNS" | while IFS='|' read -r ds dir run name at; do
  for abl in contradiction missing_evidence contradiction+missing_evidence; do
    out="$B/ablation/$ds/$name/$abl"
    ablate_at=(); baseline_at=()
    if [ "$at" != "-" ]; then ablate_at=(--at "$at"); baseline_at=(--baseline-at "$at"); fi
    R ablate --traces "$B/$run/traces.jsonl.gz" --dataset "$dir" --disable "${abl/+/,}" \
      "${ablate_at[@]}" --out "$out" | head -1
    [ -s "$out/traces.jsonl.gz" ] || { echo "ABLATE FAILED: $out"; exit 1; }
    R regression --dataset "$dir" --baseline "$B/$run/traces.jsonl.gz" "${baseline_at[@]}" \
      --candidate-traces "$out/traces.jsonl.gz" --out "$out" > /dev/null
    echo "  $ds/$name/$abl regression exit $?"
  done
done
SH
bash "$D/ablate_all.sh" 2>&1 | tee "$D/ablate_all.txt"
```

Expected (about 40 s): 30 `Ablated run …` lines and 30 `regression exit` lines. The exit codes are `4` for exactly these six pairs and `0` for the other 24:

```text
  gold-v0.1/jev-q-v0.2/contradiction regression exit 4
  gold-v0.1/jev-q-v0.2/contradiction+missing_evidence regression exit 4
  gold-v0.1/claude/contradiction regression exit 4
  gold-v0.1/claude/contradiction+missing_evidence regression exit 4
  gold-v0.1/jev-q-v0.3/contradiction regression exit 4
  gold-v0.1/jev-q-v0.3/contradiction+missing_evidence regression exit 4
```

Check with `grep -c 'regression exit 0' "$D/ablate_all.txt"` (expect `24`) and `grep 'regression exit 4' "$D/ablate_all.txt"` (expect the six lines above). The `action changed on k of n` counts in the `Ablated run` lines must match the "changed" figures in this plan's results table (for example `gen-v0.2-holdout … jev q-v0.2 … contradiction … action changed on 37 of 1000`, `gold-v0.1 … groundtruth … missing_evidence … action changed on 0 of 100`). Any exit code other than 0 or 4, an `ABLATE FAILED` line, or a count that differs from the table: stop and report; do not commit.

- [ ] **Step 5: The summary**

```bash
D=/tmp/relay-3e; mkdir -p "$D"
uv run python -m scripts.phase3e_table > "$D/summary.txt"; echo "exit $?"
tail -15 evals/baselines/ablation/summary.md
find evals/baselines/ablation -type f | wc -l
```

Expected: `exit 0`; 170 files; the tail is exactly:

```text
Null results (no action changed): 5
- gen-v0.2-holdout / rules × missing_evidence
- gold-v0.1 / groundtruth × missing_evidence
- gold-v0.1 / rules × contradiction
- gold-v0.1 / rules × missing_evidence
- gold-v0.1 / rules × contradiction+missing_evidence

Pairs whose gate FAILs (a newly unsafe automation): 6
- gold-v0.1 / jev-q-v0.2 × contradiction: GOLD-CON-03, GOLD-CON-13
- gold-v0.1 / jev-q-v0.2 × contradiction+missing_evidence: GOLD-CON-03, GOLD-CON-13
- gold-v0.1 / claude × contradiction: GOLD-CON-03, GOLD-CON-13
- gold-v0.1 / claude × contradiction+missing_evidence: GOLD-CON-03, GOLD-CON-13
- gold-v0.1 / jev-q-v0.3 × contradiction: GOLD-CON-03, GOLD-CON-13
- gold-v0.1 / jev-q-v0.3 × contradiction+missing_evidence: GOLD-CON-03, GOLD-CON-13
```

and `summary.md` contains this row verbatim:

```text
| gold-v0.1 | jev-q-v0.3 (`run_20260927T072623Z_ad6f44`) | jev q-v0.3 | v0.1+at0.81 | contradiction | FAIL | 5/100 | 2 (GOLD-CON-03, GOLD-CON-13) | 4 | 1 | 31/100 (31.0%) [22.1%, 41.0%] → 34/100 (34.0%) [24.8%, 44.2%] | 1/31 (3.2%) [0.1%, 16.7%] → 3/34 (8.8%) [1.9%, 23.7%] |
```

- [ ] **Step 6: Run the artifact test**

Run: `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest tests/integration/test_committed_ablation.py tests/unit/test_trace_store.py -q`
Expected: all pass (the ablated and baseline manifests are `simulated` with a `source_run_id`, which `test_every_committed_manifest_loads_as_an_evaluate_run` accepts).

- [ ] **Step 7: The reproduce gate for one ablated bundle**

In `evals/regression/gates.json`, replace the end of the file:

```json
      "candidate": {"traces": "evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz"},
      "requires_generated": true
    }
  ]
}
```

with:

```json
      "candidate": {"traces": "evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz"},
      "requires_generated": true
    },
    {
      "name": "gold-reproduce-ablated-jev-q-v0.3-contradiction",
      "dataset": "evals/gold",
      "baseline": "evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/traces.jsonl.gz",
      "candidate": {"reproduce": true}
    }
  ]
}
```

In `tests/integration/test_committed_gates.py`, in `test_the_committed_gates_are_the_spec_s_initial_set`, replace:

```python
        "gen-v0.3-shift-stale-to-aware",
    ]
```

with:

```python
        "gen-v0.3-shift-stale-to-aware",
        "gold-reproduce-ablated-jev-q-v0.3-contradiction",
    ]
```

- [ ] **Step 8: Gates and full check**

```bash
D=/tmp/relay-3e; mkdir -p "$D"
R() { env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env "$@"; }
R regression --config evals/regression/gates.json --strict-generated > "$D/gates-task6.txt"; echo "gates exit $?"; tail -23 "$D/gates-task6.txt"
uv run ruff check . && uv run ruff format --check . && env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest -q
```

Expected: `gates exit 0`; 20 gates, all PASS; the last row is
`gold-reproduce-ablated-jev-q-v0.3-contradiction  PASS     0             3             0       0          0     —`
(STILL UNSAFE 3: the ablated run's own three unsafe automations, reproduced exactly). Tests and ruff pass.

- [ ] **Step 9: Commit**

Check `git status --short` first: the only new or changed paths are `evals/baselines/ablation/`, `evals/regression/gates.json`, `tests/integration/test_committed_ablation.py` and `tests/integration/test_committed_gates.py` (plus the other agent's README, which you do not stage).

```bash
git add evals/baselines/ablation evals/regression/gates.json tests/integration/test_committed_ablation.py tests/integration/test_committed_gates.py
git commit -m "feat: add the 30 gate-ablation runs, their regressions, the summary and a reproduce gate" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: README: the Commands line and the "Gate ablation" section

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: `evals/baselines/ablation/summary.md` (Task 6). Every number in the new text appears in that file; the table is pasted from it verbatim.

Rules for this task: start only when `git status --short README.md` prints nothing (the other agent's README work is committed). Paste artifact text verbatim, don't round differently, and don't describe a result the artifacts don't show. Before committing, check every number in the section against `summary.md`.

- [ ] **Step 1: Commands**

In `README.md`, replace:

```markdown
uv run relay recompose --traces <jev file> --dataset <dir> --policy immunara-v0.1 --out <dir>   # stored Jev answers recomposed under a policy (offline)
```

with:

```markdown
uv run relay recompose --traces <jev file> --dataset <dir> --policy immunara-v0.1 --out <dir>   # stored Jev answers recomposed under a policy (offline)
uv run relay ablate --traces <file> --dataset <dir> --disable contradiction[,missing_evidence] [--at X] --out <dir>   # engine gates disabled, as a simulated run (offline; see "Gate ablation")
```

If that anchor line is not present verbatim (the other agent may have reworded it), insert the new line directly after whichever line documents `relay recompose` in the Commands block.

- [ ] **Step 2: The section**

Insert the following immediately before the line `## Limitations`. Where it says *(paste …)*, paste the named lines of `evals/baselines/ablation/summary.md` exactly.

````markdown
## Gate ablation

Handoff experiment 6 asks what the contradiction and missing-evidence gates are worth.
`relay ablate` re-decides a committed run's stored decisions with one gate or both disabled, at
the run's own dev-selected operating point, and writes a simulated bundle whose traces record the
ablation. `relay regression` then gates the ablated run against the same run at the same
threshold, case by case. Expected actions always come from the full engine, so an ablated run is
scored against what the policy actually requires. Nothing is called: the experiment cost $0.

- `contradiction` removes contradiction detection entirely: the contradiction review gate
  (`p_yes(material_contradiction) >= 0.80` → HUMAN_REVIEW) and the auto-block inside the
  auto-process gate (`>= 0.20` blocks AUTO_PROCESS).
- `missing_evidence` skips the missing-evidence REQUEST_INFO gate (a named missing item with
  probability `>= 0.70`). The documentation gate stays.

Ten committed runs × three ablations give 30 pairs, each under
`evals/baselines/ablation/<dataset>/<run>/<ablation>/` (the ablated bundle, `regression.json`,
`regression.md`, and the re-decided baseline its replay commands use). An ablated trace shows
`ABLATED: <gate> gate disabled` in its gate path, and `relay replay` prints an `ABLATION:` line.
The ablated runs are expected to fail the gate, so they are not CI gates. One of them (gold,
Jev q-v0.3, `contradiction`) has a reproduce gate, `gold-reproduce-ablated-jev-q-v0.3-contradiction`,
which shows that ablated traces replay exactly.

From [`evals/baselines/ablation/summary.md`](evals/baselines/ablation/summary.md):

*(paste the table: from the line starting `| Dataset | Run | Provider |` through the last table row, the gold-v0.1 jev-q-v0.3 contradiction+missing_evidence row)*

*(paste the two lists: from `Null results (no action changed): 5` through the last line of the file)*

**Findings.**

- **Contradiction detection is the only gate whose removal creates unsafe automation, and only
  on gold.** On gold-v0.1, removing it makes GOLD-CON-03 and GOLD-CON-13 newly unsafe for all
  three model providers, and each of those gates FAILs: Jev q-v0.2 at 0.89 (UAR 1/29 → 3/32),
  Jev q-v0.3 at 0.81 (1/31 → 3/34) and Claude at 0.55 (1/30 → 3/34). On the three generated sets
  it creates no newly unsafe case for any provider.
- **The ground-truth row is the policy-level effect, not an upper bound.** With perfect
  judgments, removing contradiction detection changes one gold action (1/100, a regression) and
  creates no unsafe automation: in gold-v0.1 every case with a material contradiction also fails
  another requirement in its ground truth, so the default review still catches it. The providers'
  2 newly unsafe cases are therefore provider errors (they judged every required decision at or
  above their operating point on GOLD-CON-03 and GOLD-CON-13) that only the contradiction gate
  held back. On gold the gate's value is defense in depth against judgment errors, which a
  ground-truth run cannot show.
- **On the generated holdouts the contradiction auto-block costs correct automation.** Removing
  contradiction detection raises Jev's automation from 252/1000 to 277/1000 (q-v0.2,
  gen-v0.2-holdout) and from 244/1000 to 261/1000 (q-v0.3, gen-v0.3-holdout) with UAR still 0
  (0/277, 0/261), so every added automation was correct; the same ablations regress 12 and 16
  cases respectively. For rules on gen-v0.2-holdout (17), Claude's 150-case sample (3) and the
  aware shift run (7), it only regresses cases and leaves automation unchanged.
- **The missing-evidence gate never changes an automation.** In all ten runs, removing it leaves
  automation and UAR exactly as they were and creates no newly unsafe case. Its policy-level
  effect on gold is zero (ground truth: 0/100 actions changed). With providers it only moves
  cases between REQUEST_INFO and HUMAN_REVIEW. For Jev on the generated sets more of those moves
  are corrections than errors (q-v0.2 on gen-v0.2-holdout: 67 improved, 32 regressed of 100
  changed; q-v0.3 on gen-v0.3-holdout: 53 and 40 of 93; the aware shift run: 26 and 15 of 41);
  for Claude's 150-case sample it is the other way round (3 improved, 7 regressed of 10), and on
  gold it only regresses (Jev q-v0.2 5, Claude 6, Jev q-v0.3 4).
- **Null results.** Five pairs change no action at all: rules × missing_evidence on
  gen-v0.2-holdout, ground truth × missing_evidence on gold, and all three rules ablations on
  gold. The rules baseline's 6 unsafe gold automations (6/20) are already automated with both gates in
  place, so removing a gate cannot add or remove them.

**Caveats.** gold-v0.1 is not a blind test for q-v0.3 (see "Question set q-v0.3"). Claude's
gen-v0.2-holdout row is the 150-case deterministic sample (`--limit 150 --sample-seed 7`), not
the full set. Gold has 100 cases, so its intervals are wide (Jev q-v0.3's ablated UAR 3/34 has
a 95% interval of 1.9%–23.7%). The generated sets' contradictions come from templates (see
Limitations), which bears on how often a provider's contradiction signal is the last line of
defense there.
````

- [ ] **Step 3: Check every number**

Open `evals/baselines/ablation/summary.md` beside the new section and confirm, one by one, each number in the Findings and Caveats: the six FAIL pairs and their case ids; the UAR pairs 1/29 → 3/32, 1/31 → 3/34, 1/30 → 3/34; the ground-truth rows (contradiction 1/100 changed, 1 regressed; missing_evidence 0/100); automation 252/1000 → 277/1000 and 244/1000 → 261/1000 with UAR 0/277 and 0/261 and regressed 12 and 16; the contradiction regressions 17, 3 and 7 with unchanged automation; the missing_evidence improved/regressed/changed figures (67/32/100, 53/40/93, 26/15/41, Claude-150 3/7/10; gold 5, 6, 4 regressed, 0 improved); the five null pairs; rules' 6/20 UAR on both sides; the interval 1.9%–23.7%. Confirm the statement about gold contradiction cases with:

```bash
uv run python -c "
import json, pathlib
rows = [json.loads(p.read_text()) for p in sorted(pathlib.Path('evals/gold').glob('GOLD-*/ground_truth.json'))]
con = [r for r in rows if r['contradiction_present']]
print(len(con), all(not (r['step_therapy_satisfied'] and r['diagnosis_supported'] and r['documentation_complete']) for r in con))"
```

Expected: `14 True`. If any number differs from the artifact, fix the text to match the artifact (never the reverse) and report the difference.

- [ ] **Step 4: Full check**

Run: `uv run ruff check . && uv run ruff format --check . && env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add the Gate ablation section (Phase 3E) with the committed results" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Self-review (done while writing this plan)

- **Spec coverage.** A1 → Task 1 (the two ablations, both; contradiction includes the auto-block). A2 → Task 1 (keyword-only `ablate`, default unchanged, unknown name raises, ABLATED gate-path entries, `contradiction auto-block ABLATED`). A3 → Task 2 (trace and manifest fields, replay pass-through, the ABLATION diff line, `ablate=` in regression labels) and Task 3/4 (manifests of ablated and re-decided runs). A4 → Task 4 (`relay ablate`, `--disable`, `--at`, mode/source_run_id/ablation/auto_process, pairing and hash checks via `paired_cases`, no client). A5 → Task 6 (the ten runs and operating points, Claude's sample). A6 → Task 6 (`relay regression --baseline … --baseline-at X --candidate-traces …`) and Task 5 (`scripts/phase3e_table.py`, `summary.md`/`summary.json`). A7 → Task 7 (the ground-truth row, with the correction in resolved ambiguity 10). A8 → Task 6 (artifacts committed, not CI gates, one reproduce gate). A9 → Task 7 (null results, the gold-q-v0.3 and Claude-sample caveats). §4 testing → Tasks 1–6 tests. §5 definition of done → Tasks 6 and 7.
- **Placeholders.** None: every code step has the full code; Task 7's only paste markers point at exact lines of a file Task 6 generates, whose key lines are given in Task 6 Step 5.
- **Types and names.** `ABLATIONS`, `determine_action(..., ablate=)`, `WorkflowTrace.ablation`, `RunManifest.ablation`, `TraceDiff.ablation_original/ablation_candidate`, `ablation_suffix`, `ablation_line`, `parse_disable`, `ablation_name`, `ablate_run(..., disable=, auto_process=, run_id=)`, `write_simulated_bundle(..., extra=)`, `summary_row/collect/render/main` are used with the same names and signatures in every task.
