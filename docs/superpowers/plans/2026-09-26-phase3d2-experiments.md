# Phase 3D2: Experiments E1–E3 (q-v0.3 adoption, policy shift, parallelism) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the Phase 3D experiments once each, within the $1.00 Jev cap: E1 (q-v0.3 adoption on dev, one-shot holdout, gold for completeness), E2 (the immunara-v0.2 policy shift: stale vs aware from one paid run), and E3 (latency vs narrow decisions per call). Then commit their artifacts, gates, CI regeneration and README sections, with real numbers.

**Architecture:** Each experiment uses tools built in plan 3D1 (`docs/superpowers/plans/2026-09-26-phase3d1-generator-policy-questions.md`, which must be complete first). Paid Jev runs go through `relay eval … --jev-budget-usd 1.00 --jev-ledger <absolute ledger>` or `relay bench`, each its own step, run exactly once. Everything else is offline: bundling, sweeps, `relay regression`, `relay recompose`, `relay run --workflow simulated|shadow`, replay, and `scripts/phase3d_report.py`. Artifacts use the committed-bundle format under `evals/baselines/`.

**Tech Stack:** Python 3.12, uv, Typer CLI (`relay`), pytest, ruff, gzip.

**Spec:** `docs/superpowers/specs/2026-09-26-phase3d-questions-and-policy-shift-design.md` §1, §5, §7, §9.

## Global Constraints

- Synthetic data only.
- Never open `.env` (read, cat, grep or edit it). Paid commands let the `relay` CLI load it (the default `--env-file .env`); you never look inside it.
- No Claude calls. Every command unsets `ANTHROPIC_API_KEY`. `--provider claude` is never used.
- Jev spend for all of 3D is ≤ $1.00, enforced by the spend counter: every paid step passes `--jev-budget-usd 1.00 --jev-ledger /Users/joelbrook/Desktop/Code/Relay/results/jev-spend-3d.json`.
- Offline commands use `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env ...` (the `R` function in the preamble).
- `results/claude-spend.json` is never read or written.
- Stage files by explicit path. Never `git add -A` or `git add .`.
- Each commit uses two `-m` arguments. The second is exactly `-m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.
- Don't push.
- At the end of every task, `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q` must pass.
- The committed gates must pass with `--strict-generated`: `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env regression --config evals/regression/gates.json --strict-generated` exits 0. This needs `evals/generated/gen-v0.2-holdout` and, after Task 1, the three gen-v0.3 datasets on disk.
- gold-v0.1 (`evals/gold/`) is never edited. New gold *runs* go under `evals/baselines/gold-v0.1/`.
- No question, threshold or generator change may be made after seeing holdout, shift or gold results. Only dev results feed a decision (spec §1).
- Branch: `feat/phase3`, with plan 3D1 complete. Work from the repository root `/Users/joelbrook/Desktop/Code/Relay`.

## Paid steps: the rules

There are exactly seven paid steps: Task 3 Steps 1 and 2, Task 4 Steps 1 and 3, Task 5 Step 1, Task 6 Step 1, and Task 7 Step 1. Each one:

1. **Runs exactly once.** Never re-run a paid step for any reason, including a crash, a network error, a bad result or a typo afterwards. If it fails, stop and report.
2. **Prints the estimate first.** The counter's first line is `jev estimate: N cases × Q questions ≈ $X`, followed by `Jev budget: spent $S of the $1.00 cap (…)`. Check that the printed estimate equals the one in the step.
3. **Stops the plan (report to the user, commit nothing from that step) when:**
   - the counter refuses (exit 2, `Jev budget exceeded: …`), or any other refusal of the counter;
   - the printed estimate exceeds the remaining cap (1.00 − S), which the counter enforces;
   - invalid outputs exceed 2% of the run: the `Invalid outputs` line of the eval summary is above the step's stated limit (the bench: the summed `Errors` column above 3 of 160 calls);
   - the command fails in any other way.

   When stopping, include `R budget show --ledger /Users/joelbrook/Desktop/Code/Relay/results/jev-spend-3d.json` in the report. The ledger itself is not a stop reason. `budget show` prints Claude's "$10.00 default budget" on its last line; ignore that, because the Jev cap is the $1.00 passed to every paid step.
4. **Records its output.** stdout and stderr are teed to `/tmp/relay-3d/<step>.txt`; later steps read run ids from those files.

**Budget (estimates from the counter; actuals from measured cost).** Committed Jev traces cost $0.000111–0.000115 per case with 12 questions (max $0.000126882); question text is billed once per call. Upper bound for q-v0.3: 19/12 × $0.000112 = $0.000177 per case.

| Paid step | Run | Counter estimate | Expected actual (upper) |
|---|---|---|---|
| Task 3 Step 1 | Jev q-v0.2 on gen-v0.3-dev (400 × 12) | $0.0624 | $0.045 |
| Task 3 Step 2 | Jev q-v0.3 on gen-v0.3-dev (400 × 19) | $0.0988 | $0.071 |
| Task 4 Step 1 | Jev q-v0.3 on gen-v0.3-holdout (1000 × 19) | $0.2470 | $0.177 |
| Task 4 Step 3 | Jev q-v0.2 on gen-v0.3-holdout (1000 × 12), only if the fallback check allows | $0.1560 | $0.112 |
| Task 5 Step 1 | Jev q-v0.3 on gold-v0.1 (100 × 19) | $0.0247 | $0.018 |
| Task 6 Step 1 | Jev q-v0.3 on gen-v0.3-shift, policy v0.2 (400 × 19) | $0.0988 | $0.071 |
| Task 7 Step 1 | `relay bench`, 40 cases × sizes 1, 5, 10, 20 (160 calls) | $0.0291 | $0.021 |
| **Total** | | **$0.7168** | **≤ $0.515** |

Even if every run cost its full estimate ($0.7168), the total stays under the cap. The spec's "≈ $0.70" assumed $0.00015 per case; the measured figure is $0.000112.

## Shell preamble

Shell state does not survive between tool calls. Start **every** shell block in this plan with this preamble (it only defines variables and functions):

```bash
D=/tmp/relay-3d; mkdir -p "$D"
LEDGER=/Users/joelbrook/Desktop/Code/Relay/results/jev-spend-3d.json
R() { env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env "$@"; }
P() { env -u ANTHROPIC_API_KEY uv run relay "$@"; }   # PAID: the relay CLI loads TYPESAFE_API_KEY from .env; never open .env yourself
run_of() { grep '^Traces: ' "$1" | cut -d' ' -f2 | xargs basename | sed 's/\.jsonl$//'; }
invalid_of() { grep 'Invalid outputs' "$1" | awk '{print $3}'; }
selected() { uv run python -c "import json,sys; s=json.load(open(sys.argv[1]))['selected']; print(s['auto_threshold'] if s else '')" "$1"; }
run_dir() {  # run_dir BASELINE_DIR QUESTION_SET: the single committed Jev run directory with that question set
  uv run python -c "
import json, pathlib, sys
hits = [p for p in sorted(pathlib.Path(sys.argv[1]).glob('run_*'))
        if (m := json.loads((p / 'run-manifest.json').read_text()))['provider'] == 'jev'
        and m.get('question_set_version') == sys.argv[2]]
assert len(hits) == 1, hits
print(hits[0])" "$1" "$2"
}
spent() { uv run python -c "import json,sys; print(sum(float(e['cost_usd']) for e in json.load(open(sys.argv[1]))['entries']))" "$LEDGER"; }
bundle() {  # bundle RUN DATASET_DIR DEST [AT]: the committed-bundle layout of evals/baselines/
  local run=$1 ds=$2 dest=$3 at=${4:-}
  local extra=(); [ -n "$at" ] && extra=(--at "$at")
  mkdir -p "$dest"
  gzip -n -c "traces/$run.jsonl" > "$dest/traces.jsonl.gz"
  cp "traces/$run.manifest.json" "$dest/run-manifest.json"
  cp "results/$run.json" "$dest/results.json"
  R report --dataset "$ds" --traces "$dest/traces.jsonl.gz" "${extra[@]}" --out "$dest/report" > /dev/null
  R sweep --dataset "$ds" --traces "$dest/traces.jsonl.gz" "${extra[@]}" --out "$D/sweep-$run" > /dev/null
  cp "$D/sweep-$run/$run.sweep.json" "$dest/sweep.json"
  cp "$D/sweep-$run/$run.frontier.csv" "$dest/frontier.csv"
}
```

`bundle` produces the same file set as the committed 2B bundles: `traces.jsonl.gz`, `run-manifest.json`, `results.json`, `report/` (summary, calibration, confusion, frontier, report.md), `sweep.json` and `frontier.csv`. The JSON files are compact, as the current code writes them. The preamble was checked in both zsh and bash.

## Verified facts this plan relies on (checked while planning, on a scratch copy with plan 3D1 applied)

- **Dry run of every offline command.** A fake Jev client stood in for the paid runs (no network). With it, every offline command in Tasks 3–9 ran as written on the gen-v0.3 datasets: `bundle`, `sweep` and `selected`, `regression` with `--baseline-at`/`--candidate-at`/`--out`, `recompose` into `stale-immunara-v0.1/` and `aware-immunara-v0.2/`, `eval --traces` on the recomposed runs, the stale → aware gate (PASS), `relay run --workflow simulated` then `--workflow shadow … --incumbent … --out` (PROMOTE), rules on the shift set (`--policy v0.2`), `relay bench`, and `scripts/phase3d_report.py` on the regression outputs. The counter printed `jev estimate: 400 cases × 12 questions ≈ $0.0624`, `… 400 cases × 19 questions ≈ $0.0988` and `jev estimate: 40 cases × (1+5+10+20) questions ≈ $0.0291`, then settled each run.
- **The stale → aware gate cannot fail on newly unsafe cases.** immunara-v0.2 only removes qualifying date pairs, so the aware step_therapy `p_yes` is ≤ the stale one on every case, and v0.2's thresholds equal v0.1's. The aware run's AUTO_PROCESS cases are therefore a subset of the stale run's.
- **The rules baseline on gen-v0.3-shift (policy v0.2), offline:** 261/400 correct, 50/400 automated, 6/50 unsafe. It has no recency rule, so it is naive by construction.
- **Room for the effect:** 18 shift cases would be auto-processed under v0.1 labels but not under v0.2 (planning count from the facts).

## Resolved ambiguities (decisions this plan makes)

1. **Paid-step order and the fallback.** E1 holdout runs q-v0.3 first (the primary evidence), then q-v0.2 only if the spend so far plus the estimates of every remaining paid step ($0.1560 + $0.0247 + $0.0988 + $0.0291 = $0.3086) is ≤ $1.00. Otherwise q-v0.2 on holdout is skipped and reported as skipped (spec §5).
2. **t\* per question set.** t\* is the dev sweep's `selected.auto_threshold` for that run (the 2B rule: the highest automation with at least one AUTO_PROCESS and UAR ≤ 1%; ties go to the higher threshold). If the sweep selects nothing, that set runs at its recorded thresholds (auto_process 0.95), and the `--at`/`--baseline-at`/`--candidate-at` flag is omitted.
3. **"Correct-action rate is higher".** The rates compared are those in the dev gate's `regression.json` (each side at its t\*), and higher means strictly higher. `scripts/phase3d_report.py adoption` writes `adoption.txt` from that file, in the 2B format.
4. **The adoption gate** (holdout, q-v0.2 → q-v0.3 at the dev t\*s) goes into `gates.json` only when the decision is ADOPT, because it must PASS then. If the decision is KEEP, its result is still committed under `evals/baselines/gen-v0.3-holdout/` and reported in the README, but it is not a CI gate: a gate that is not required to pass would make CI red for a documented negative result. If holdout q-v0.2 was skipped, there is no adoption gate.
5. **The gold regression** compares the committed q-v0.2 gold run (`run_20260925T170857Z_b95be9`) with the new q-v0.3 gold run, each at its dev-selected t\*. It is committed with the §1 caveat and is not a CI gate. The new gold run gets a reproduce gate.
6. **E2 run layout.** The paid source run (policy immunara-v0.2, so aware by construction) is `evals/baselines/gen-v0.3-shift/<run_id>/`. The recomposed runs go to `evals/baselines/gen-v0.3-shift/stale-immunara-v0.1/` and `aware-immunara-v0.2/`, written by `relay recompose --out` in bundle format, plus `results.json` and `report/`. Scoring is against the shift set's ground truth, which is labelled under immunara-v0.2.
7. **"Stale-only unsafe automations"** are the `unsafe_resolved` cases of the stale → aware gate: unsafe in the stale run and not in the aware run. Since only recency differs, these are exactly the approvals that pass v0.1's rule but break the recency requirement.
8. **The shadow demo** uses its own state file, `state/shift-demo.json` (git-ignored by 3C), and writes `shadow.json`/`shadow.md` to `evals/baselines/gen-v0.3-shift/shadow-stale-to-aware/`. The per-case SIMULATED/SHADOW lines are captured under `/tmp/relay-3d/` and not committed.
9. **Rules on the shift set** is an ordinary committed bundle (`--policy v0.2`). It is reported as naive and gets no gate.
10. **Reproduce gates** (`requires_generated: true`) cover every new generated-dataset run: dev q-v0.2 and q-v0.3, holdout q-v0.3 (and q-v0.2 if run), the shift source run, stale and aware. The gold q-v0.3 run gets one without `requires_generated`. The `shift-stale-to-aware` gate is added and must PASS.
11. **The Jev ledger stays git-ignored** at `results/jev-spend-3d.json`. A copy is committed as `evals/baselines/jev-spend-3d.json`, as with `claude-spend.json`, so the ≤ $1.00 total is auditable.
12. **Bench errors.** The stop rule for E3 is the summed `Errors` column above 3 (2% of 160 calls). The bench's files are written before the rule can be checked; if it trips, nothing is committed.

---


### Task 1: gen-v0.3 datasets, committed manifests, CI regeneration and drift-guard coverage

**Files:**
- Modify: `.github/workflows/ci.yml`
- Test (modify): `tests/integration/test_committed_baselines.py`
- Test (modify): `tests/unit/test_ci_workflow.py`
- Test (modify): `tests/unit/test_trace_store.py`

**Interfaces:**
- Consumes: `relay generate --generator gen-v0.3 [--policy v0.2]` (plan 3D1, Task 8).
- Produces:
  - `evals/generated/manifests/gen-v0.3-dev.json` (seed 3, 400), `gen-v0.3-holdout.json` (seed 4, 1000) and `gen-v0.3-shift.json` (seed 5, 400, `"policy_version": "v0.2"`), committed. The case folders under `evals/generated/gen-v0.3-*/` stay git-ignored.
  - `.github/workflows/ci.yml` regenerates and verifies all three after the gen-v0.2 datasets, so `--strict-generated` gates on them can run in CI.
  - `tests/integration/test_committed_baselines.py`: the drift guard also covers every committed `evals/baselines/gen-v0.3-*` run directory (a directory holding `traces.jsonl.gz`; regression `--out` directories are skipped).
  - `tests/unit/test_trace_store.py`: the 3C pin `test_every_committed_manifest_loads_as_an_evaluate_run` keeps its guarantee for the 14 pre-3C manifests. Manifests committed from Task 3 on carry a `mode` key (evaluate, or simulated with a `source_run_id`), so without this change that test would fail in Task 3. It passes both before and after the new runs.

- [ ] **Step 1: Write the failing tests**

In `tests/integration/test_committed_baselines.py`, replace:

```python
# Committed datasets whose case folders are tracked (not regenerated).
DATASET_DIRS: dict[str, Path] = {"gold-v0.1": REPO / "evals" / "gold"}

# Every committed gen-v0.2-* run directory: (dataset_id, run_dir).
RUN_DIRS: list[tuple[str, Path]] = sorted(
    (dataset_dir.name, run_dir)
    for dataset_dir in [*BASELINES.glob("gen-v0.2-*"), BASELINES / "gold-v0.1"]
    if dataset_dir.is_dir()
    for run_dir in dataset_dir.iterdir()
    if run_dir.is_dir()
)

KEY_METRICS = (
```

with:

```python
# Committed datasets whose case folders are tracked (not regenerated).
DATASET_DIRS: dict[str, Path] = {"gold-v0.1": REPO / "evals" / "gold"}

# Every committed gen-v0.2-* / gen-v0.3-* and gold run directory: (dataset_id, run_dir). A
# directory counts when it holds traces.jsonl.gz (a regression --out directory does not).
RUN_DIRS: list[tuple[str, Path]] = sorted(
    (dataset_dir.name, run_dir)
    for dataset_dir in [
        *BASELINES.glob("gen-v0.2-*"),
        *BASELINES.glob("gen-v0.3-*"),
        BASELINES / "gold-v0.1",
    ]
    if dataset_dir.is_dir()
    for run_dir in dataset_dir.iterdir()
    if run_dir.is_dir() and (run_dir / "traces.jsonl.gz").is_file()
)

KEY_METRICS = (
```

In `tests/unit/test_ci_workflow.py`, replace:

```python
        "--dataset-id gen-v0.2-holdout",
        "--verify evals/generated/manifests/gen-v0.2-dev.json",
        "--verify evals/generated/manifests/gen-v0.2-holdout.json",
        "regression --config evals/regression/gates.json --strict-generated --out regression-report",
    ]
    positions = [commands.index(fragment) for fragment in expected]
```

with:

```python
        "--dataset-id gen-v0.2-holdout",
        "--verify evals/generated/manifests/gen-v0.2-dev.json",
        "--verify evals/generated/manifests/gen-v0.2-holdout.json",
        "--dataset-id gen-v0.3-dev",
        "--dataset-id gen-v0.3-holdout",
        "--dataset-id gen-v0.3-shift",
        "--verify evals/generated/manifests/gen-v0.3-dev.json",
        "--verify evals/generated/manifests/gen-v0.3-holdout.json",
        "--verify evals/generated/manifests/gen-v0.3-shift.json",
        "regression --config evals/regression/gates.json --strict-generated --out regression-report",
    ]
    positions = [commands.index(fragment) for fragment in expected]
```

In `tests/unit/test_ci_workflow.py`, replace:

```python
            f"--out evals/generated/{name} --count {manifest['count']} --seed {manifest['seed']} "
            f"--dataset-id {name}"
        ) in commands


def test_the_regression_gate_step_uses_strict_generated():
```

with:

```python
            f"--out evals/generated/{name} --count {manifest['count']} --seed {manifest['seed']} "
            f"--dataset-id {name}"
        ) in commands


def test_the_gen_v0_3_regeneration_flags_match_the_committed_manifests():
    commands = " ".join("\n".join(runs()).replace("\\\n", " ").split())
    for name in ("gen-v0.3-dev", "gen-v0.3-holdout", "gen-v0.3-shift"):
        manifest = json.loads((REPO / "evals/generated/manifests" / f"{name}.json").read_text())
        assert manifest["generator_version"] == "gen-v0.3"
        policy = manifest.get("policy_version", "v0.1")
        flags = (
            f"--out evals/generated/{name} --count {manifest['count']} --seed {manifest['seed']} "
            f"--dataset-id {name} --generator gen-v0.3"
        )
        if policy != "v0.1":
            flags += f" --policy {policy}"
        assert flags + " --manifests-dir" in commands, name


def test_the_regression_gate_step_uses_strict_generated():
```

In `tests/unit/test_trace_store.py`, replace:

```python


def test_every_committed_manifest_loads_as_an_evaluate_run():
    paths = sorted((REPO / "evals" / "baselines").rglob("*manifest.json"))
    assert len(paths) == 14
    for path in paths:
        assert '"mode"' not in path.read_text()
        loaded = RunManifest.model_validate_json(path.read_text())
        assert (loaded.mode, loaded.source_run_id) == ("evaluate", None), path
```

with:

```python


def test_every_committed_manifest_loads_as_an_evaluate_run():
    """The 14 manifests committed before Phase 3C have no mode key and load as evaluate runs.
    Manifests committed since (Phase 3D) carry a mode: evaluate, or simulated with a
    source_run_id (relay recompose, and the re-decided runs of a regression --out)."""
    paths = sorted((REPO / "evals" / "baselines").rglob("*manifest.json"))
    legacy = [p for p in paths if '"mode"' not in p.read_text()]
    assert len(legacy) == 14
    for path in paths:
        loaded = RunManifest.model_validate_json(path.read_text())
        if path in legacy:
            assert (loaded.mode, loaded.source_run_id) == ("evaluate", None), path
        else:
            assert loaded.mode in ("evaluate", "simulated"), path
            assert (loaded.mode == "simulated") == (loaded.source_run_id is not None), path
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run: `uv run pytest -q tests/integration/test_committed_baselines.py tests/unit/test_ci_workflow.py tests/unit/test_trace_store.py`

Expected: FAIL. the new CI test fails with `FileNotFoundError` for `evals/generated/manifests/gen-v0.3-dev.json` (the manifests don't exist yet), and the step-order test can't find `--dataset-id gen-v0.3-dev`.

- [ ] **Step 3: Implement**

First generate the three datasets with the default manifest directory, so the manifests are written to `evals/generated/manifests/`. Then verify them. Start with the shell preamble (see "Shell preamble" above).

```bash
R generate --generator gen-v0.3 --count 400 --seed 3 --dataset-id gen-v0.3-dev --out evals/generated/gen-v0.3-dev
R generate --generator gen-v0.3 --count 1000 --seed 4 --dataset-id gen-v0.3-holdout --out evals/generated/gen-v0.3-holdout
R generate --generator gen-v0.3 --policy v0.2 --count 400 --seed 5 --dataset-id gen-v0.3-shift --out evals/generated/gen-v0.3-shift
for d in dev holdout shift; do R generate --verify evals/generated/manifests/gen-v0.3-$d.json --out evals/generated/gen-v0.3-$d; done
git check-ignore -q evals/generated/gen-v0.3-dev/GEN-03000000/case.json && echo ignored
```

Expected: three `OK:` lines and `ignored`. The dataset hashes are exactly `sha256:ae3dc2f88e0966889aee2193dc822bee3389ade3ffce85641a9f59495557d5ad` (dev, expected actions 122 / 93 / 185), `sha256:2aefa63d082a957ea035a9b21ae9ca283ba5e47eb3ceeedc342250118c1d99e5` (holdout, 265 / 269 / 466) and `sha256:3f5a9c1cad24cf0ddd8c446999bc4c5e382503c65f1a6d8c54a8a2daf9710e53` (shift, 85 / 99 / 216), as planned in 3D1 Task 8. If a hash differs, stop: the 3D1 generator does not match its plan.

Then apply the edits:

In `.github/workflows/ci.yml`, replace:

```yaml
            --verify evals/generated/manifests/gen-v0.2-dev.json --out evals/generated/gen-v0.2-dev
          uv run relay --env-file .no-such.env generate \
            --verify evals/generated/manifests/gen-v0.2-holdout.json --out evals/generated/gen-v0.2-holdout

      - name: Regression gate
        run: >-
```

with:

```yaml
            --verify evals/generated/manifests/gen-v0.2-dev.json --out evals/generated/gen-v0.2-dev
          uv run relay --env-file .no-such.env generate \
            --verify evals/generated/manifests/gen-v0.2-holdout.json --out evals/generated/gen-v0.2-holdout
          uv run relay --env-file .no-such.env generate --out evals/generated/gen-v0.3-dev \
            --count 400 --seed 3 --dataset-id gen-v0.3-dev --generator gen-v0.3 --manifests-dir "$RUNNER_TEMP/manifests"
          uv run relay --env-file .no-such.env generate --out evals/generated/gen-v0.3-holdout \
            --count 1000 --seed 4 --dataset-id gen-v0.3-holdout --generator gen-v0.3 --manifests-dir "$RUNNER_TEMP/manifests"
          uv run relay --env-file .no-such.env generate --out evals/generated/gen-v0.3-shift \
            --count 400 --seed 5 --dataset-id gen-v0.3-shift --generator gen-v0.3 --policy v0.2 --manifests-dir "$RUNNER_TEMP/manifests"
          uv run relay --env-file .no-such.env generate \
            --verify evals/generated/manifests/gen-v0.3-dev.json --out evals/generated/gen-v0.3-dev
          uv run relay --env-file .no-such.env generate \
            --verify evals/generated/manifests/gen-v0.3-holdout.json --out evals/generated/gen-v0.3-holdout
          uv run relay --env-file .no-such.env generate \
            --verify evals/generated/manifests/gen-v0.3-shift.json --out evals/generated/gen-v0.3-shift

      - name: Regression gate
        run: >-
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run pytest -q tests/integration/test_committed_baselines.py tests/unit/test_ci_workflow.py tests/unit/test_trace_store.py`

Expected: PASS.

- [ ] **Step 5: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`

Expected: all pass.

Also run the CI regeneration flags once, as CI will, into a temp manifests dir (this must not touch the committed manifests):

```bash
S=$(mktemp -d); for d in dev holdout shift; do rm -rf "$S/$d"; done
R generate --out "$S/dev" --count 400 --seed 3 --dataset-id gen-v0.3-dev --generator gen-v0.3 --manifests-dir "$S/m" | grep 'Dataset hash'
R generate --out "$S/shift" --count 400 --seed 5 --dataset-id gen-v0.3-shift --generator gen-v0.3 --policy v0.2 --manifests-dir "$S/m" | grep 'Dataset hash'
git status --short evals/generated/manifests/
```

Expected: the dev and shift hashes above. `git status` lists only the three new, untracked `gen-v0.3-*.json` files.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml tests/integration/test_committed_baselines.py tests/unit/test_ci_workflow.py tests/unit/test_trace_store.py evals/generated/manifests/gen-v0.3-dev.json evals/generated/manifests/gen-v0.3-holdout.json evals/generated/manifests/gen-v0.3-shift.json
git commit -m "feat: commit the gen-v0.3 dataset manifests and regenerate them in CI" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 2: The Phase 3D report helper (adoption decision and shift table)

**Files:**
- Create: `scripts/phase3d_report.py`
- Test (create): `tests/unit/test_phase3d_report.py`

**Interfaces:**
- Consumes: a `relay regression` `regression.json` (`RegressionResult`: `baseline`/`candidate` `SideMetrics` with `identity.run_id`, `identity.policy_versions`, `identity.thresholds_versions`, `correct`/`automation`/`uar` `Rate`s (`count`, `n`, `rate`); `newly_unsafe`, `still_unsafe`, `unsafe_resolved`, `regressed`, `improved` lists of `{case_id, …}`; `verdict`).
- Produces: `scripts/phase3d_report.py` with `adoption_decision(result) -> bool`, `adoption_text(result) -> str`, `shift_markdown(result) -> str`, `main(argv) -> int`. Usage: `uv run python -m scripts.phase3d_report adoption|shift REGRESSION_JSON`. Tasks 3 and 6 use it; its output is committed verbatim.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_phase3d_report.py`:

```python
"""scripts/phase3d_report.py: the E1 adoption decision and the E2 shift table."""

import json

from scripts.phase3d_report import adoption_decision, adoption_text, main, shift_markdown


def rate(count, n):
    return {"count": count, "n": n, "rate": count / n if n else None, "ci95": None}


def side(run_id, correct, auto, unsafe, *, policy="v0.1", thresholds="v0.1+at0.89"):
    return {
        "identity": {
            "run_id": run_id,
            "policy_versions": [policy],
            "thresholds_versions": [thresholds],
        },
        "correct": rate(correct, 400),
        "automation": rate(auto, 400),
        "uar": rate(unsafe, auto),
    }


def entry(case_id):
    return {"case_id": case_id}


def result(q2_correct, q3_correct, *, newly_unsafe=(), verdict="PASS"):
    return {
        "baseline": side("replay-run_a", q2_correct, 90, 0),
        "candidate": side("replay-run_b", q3_correct, 95, 0, thresholds="v0.1+at0.9"),
        "newly_unsafe": [entry(c) for c in newly_unsafe],
        "still_unsafe": [],
        "unsafe_resolved": [],
        "regressed": [],
        "improved": [entry("GEN-1")],
        "verdict": verdict,
    }


def test_adopt_needs_a_strictly_higher_correct_rate_and_a_passing_gate():
    assert adoption_decision(result(330, 340))
    assert not adoption_decision(result(330, 330))  # equal is not higher
    assert not adoption_decision(result(330, 320))
    assert not adoption_decision(result(330, 340, newly_unsafe=["GEN-2"], verdict="FAIL"))


def test_adoption_text():
    text = adoption_text(result(330, 340))
    assert text.splitlines()[2:] == [
        "  q-v0.2: run run_a correct 330/400 (0.8250) at thresholds v0.1+at0.89, unsafe 0",
        "  q-v0.3: run run_b correct 340/400 (0.8500) at thresholds v0.1+at0.9, unsafe 0",
        "  gate: PASS (newly unsafe 0, regressed 0, improved 1)",
        "DECISION: ADOPT q-v0.3",
    ]
    assert adoption_text(result(330, 330)).endswith("DECISION: KEEP q-v0.2")


def test_shift_markdown_lists_stale_only_unsafe_automations():
    shift = {
        "baseline": side("run_stale", 300, 60, 5),
        "candidate": side("run_aware", 318, 55, 0, policy="v0.2", thresholds="v0.2"),
        "newly_unsafe": [],
        "still_unsafe": [],
        "unsafe_resolved": [entry("GEN-05000001"), entry("GEN-05000007")],
        "regressed": [],
        "verdict": "PASS",
    }
    text = shift_markdown(shift)
    assert "| stale (`run_stale`) | v0.1 | 300/400 (75.0%) | 60/400 (15.0%) | 5/60 (8.3%) |" in text
    assert "| aware (`run_aware`) | v0.2 | 318/400 (79.5%) | 55/400 (13.8%) | 0/55 (0.0%) |" in text
    assert "Stale-only unsafe automations (2): GEN-05000001, GEN-05000007" in text
    assert "Gate stale → aware: PASS (newly unsafe 0, regressed 0)" in text


def test_main_reads_a_file_and_rejects_bad_usage(tmp_path, capsys):
    path = tmp_path / "regression.json"
    path.write_text(json.dumps(result(330, 340)))
    assert main(["adoption", str(path)]) == 0
    assert capsys.readouterr().out.strip().endswith("DECISION: ADOPT q-v0.3")
    assert main(["nope", str(path)]) == 2
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run: `uv run pytest -q tests/unit/test_phase3d_report.py`

Expected: FAIL. `ModuleNotFoundError: No module named 'scripts.phase3d_report'`.

- [ ] **Step 3: Implement**

Create `scripts/phase3d_report.py`:

```python
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
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run pytest -q tests/unit/test_phase3d_report.py`

Expected: PASS.

- [ ] **Step 5: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/phase3d_report.py tests/unit/test_phase3d_report.py
git commit -m "feat: add the Phase 3D report helper for the adoption decision and the shift table" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 3: E1 on dev: two paid runs, t\*, the dev gate and the adoption decision

**Files:**
- Create: `evals/baselines/gen-v0.3-dev/<q-v0.2 run_id>/` and `evals/baselines/gen-v0.3-dev/<q-v0.3 run_id>/` (bundles)
- Create: `evals/baselines/gen-v0.3-dev/compare-q-v0.2-vs-q-v0.3.txt`
- Create: `evals/baselines/gen-v0.3-dev/regression-q-v0.2-vs-q-v0.3/` (`regression.json`, `regression.md`, and the re-decided `baseline.*`/`candidate.*` runs when a t\* is set)
- Create: `evals/baselines/gen-v0.3-dev/adoption.txt`

**Interfaces:**
- Consumes: the preamble; `relay eval --jev-budget-usd/--jev-ledger` and `--questions q-v0.3` (3D1 Tasks 3, 4 and 9); `scripts/phase3d_report.py adoption` (Task 2); the gen-v0.3-dev dataset (Task 1).
- Produces: the two dev bundles, found later with `run_dir evals/baselines/gen-v0.3-dev q-v0.2|q-v0.3`; each bundle's `sweep.json`, whose `selected.auto_threshold` is that question set's t\* (read with `selected`); and `adoption.txt`, whose last line is `DECISION: ADOPT q-v0.3` or `DECISION: KEEP q-v0.2`.

This task follows the spec's adoption rule, fixed before any run: ADOPT q-v0.3 iff its dev correct-action rate is higher and the dev regression gate PASSes (0 newly unsafe); otherwise KEEP q-v0.2.

- [ ] **Step 1 (PAID, run exactly once): Jev q-v0.2 on gen-v0.3-dev**

Expected estimate: `jev estimate: 400 cases × 12 questions ≈ $0.0624`. Invalid-output limit: 8.

```bash
# (preamble)
P eval --dataset evals/generated/gen-v0.3-dev --provider jev --questions q-v0.2 --policy v0.1 \
  --jev-budget-usd 1.00 --jev-ledger "$LEDGER" > "$D/e1-dev-q-v0.2.txt" 2>&1; echo "exit $?"
head -2 "$D/e1-dev-q-v0.2.txt"; grep '^Jev spend' "$D/e1-dev-q-v0.2.txt"
echo "invalid=$(invalid_of "$D/e1-dev-q-v0.2.txt") run=$(run_of "$D/e1-dev-q-v0.2.txt")"
```

Expected: `exit 0`, the estimate line above, `Jev spend: this run $… ; total $… of the $1.00 cap (…)`, `invalid` ≤ 8. Otherwise apply the stop rules ("Paid steps: the rules").

- [ ] **Step 2 (PAID, run exactly once): Jev q-v0.3 on gen-v0.3-dev**

Expected estimate: `jev estimate: 400 cases × 19 questions ≈ $0.0988`. Invalid-output limit: 8.

```bash
# (preamble)
P eval --dataset evals/generated/gen-v0.3-dev --provider jev --questions q-v0.3 --policy v0.1 \
  --jev-budget-usd 1.00 --jev-ledger "$LEDGER" > "$D/e1-dev-q-v0.3.txt" 2>&1; echo "exit $?"
head -2 "$D/e1-dev-q-v0.3.txt"; grep '^Jev spend' "$D/e1-dev-q-v0.3.txt"
echo "invalid=$(invalid_of "$D/e1-dev-q-v0.3.txt") run=$(run_of "$D/e1-dev-q-v0.3.txt")"
```

Expected: `exit 0`, the estimate line above, `invalid` ≤ 8. Otherwise stop.

- [ ] **Step 3: Bundle both runs and read t\* per question set (offline)**

```bash
# (preamble)
Q2=$(run_of "$D/e1-dev-q-v0.2.txt"); Q3=$(run_of "$D/e1-dev-q-v0.3.txt")
bundle "$Q2" evals/generated/gen-v0.3-dev "evals/baselines/gen-v0.3-dev/$Q2"
bundle "$Q3" evals/generated/gen-v0.3-dev "evals/baselines/gen-v0.3-dev/$Q3"
echo "t*(q-v0.2)=[$(selected evals/baselines/gen-v0.3-dev/$Q2/sweep.json)] t*(q-v0.3)=[$(selected evals/baselines/gen-v0.3-dev/$Q3/sweep.json)]"
ls evals/baselines/gen-v0.3-dev/$Q2 evals/baselines/gen-v0.3-dev/$Q3
```

Expected: each directory lists `frontier.csv report results.json run-manifest.json sweep.json traces.jsonl.gz`. An empty `[]` t\* means that sweep selected nothing, and the set runs at auto_process 0.95 (resolved ambiguity 2).

- [ ] **Step 4: Compare the two runs and run the dev gate at the dev t\*s (offline)**

```bash
# (preamble)
A=$(run_dir evals/baselines/gen-v0.3-dev q-v0.2); B=$(run_dir evals/baselines/gen-v0.3-dev q-v0.3)
T2=$(selected "$A/sweep.json"); T3=$(selected "$B/sweep.json")
BA=(); [ -n "$T2" ] && BA=(--baseline-at "$T2"); CA=(); [ -n "$T3" ] && CA=(--candidate-at "$T3")
R compare --dataset evals/generated/gen-v0.3-dev --traces "$A/traces.jsonl.gz" --traces "$B/traces.jsonl.gz" \
  --labels q-v0.2,q-v0.3 > evals/baselines/gen-v0.3-dev/compare-q-v0.2-vs-q-v0.3.txt; echo "compare exit $?"
R regression --dataset evals/generated/gen-v0.3-dev --baseline "$A/traces.jsonl.gz" "${BA[@]}" \
  --candidate-traces "$B/traces.jsonl.gz" "${CA[@]}" \
  --out evals/baselines/gen-v0.3-dev/regression-q-v0.2-vs-q-v0.3 > "$D/e1-dev-gate.txt"; echo "gate exit $?"
tail -1 "$D/e1-dev-gate.txt"
```

Expected: `compare exit 0`. `gate exit` is 0 (`REGRESSION GATE: PASS`) or 4 (`REGRESSION GATE: FAIL — …`). Both are results: a FAIL means KEEP. Exit 2 is an input error: stop and report it, and don't change any data to make it pass.

- [ ] **Step 5: Write the adoption decision (offline)**

```bash
# (preamble)
uv run python -m scripts.phase3d_report adoption \
  evals/baselines/gen-v0.3-dev/regression-q-v0.2-vs-q-v0.3/regression.json \
  > evals/baselines/gen-v0.3-dev/adoption.txt
cat evals/baselines/gen-v0.3-dev/adoption.txt
```

Expected: the 2B-style block ending in `DECISION: ADOPT q-v0.3` or `DECISION: KEEP q-v0.2`. The decision is final: nothing is tuned after it.

- [ ] **Step 6: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`

Expected: all pass. The drift guard (`tests/integration/test_committed_baselines.py`) now re-scores both dev bundles. Then:

```bash
# (preamble)
R regression --config evals/regression/gates.json --strict-generated > /dev/null; echo "gates exit $?"
git status --short
```

Expected: `gates exit 0`. `git status` lists only the new paths under `evals/baselines/gen-v0.3-dev/` (plus the untracked, git-ignored `traces/` and `results/` files, which don't appear).

- [ ] **Step 7: Commit**

```bash
# (preamble)
Q2=$(run_of "$D/e1-dev-q-v0.2.txt"); Q3=$(run_of "$D/e1-dev-q-v0.3.txt")
git add "evals/baselines/gen-v0.3-dev/$Q2" "evals/baselines/gen-v0.3-dev/$Q3" \
  evals/baselines/gen-v0.3-dev/compare-q-v0.2-vs-q-v0.3.txt \
  evals/baselines/gen-v0.3-dev/regression-q-v0.2-vs-q-v0.3 \
  evals/baselines/gen-v0.3-dev/adoption.txt
git commit -m "feat: add gen-v0.3-dev Jev runs for q-v0.2 and q-v0.3 and the adoption decision" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: E1 on holdout: q-v0.3 once, q-v0.2 once if the budget allows, and the holdout gate

**Files:**
- Create: `evals/baselines/gen-v0.3-holdout/<q-v0.3 run_id>/` (bundle, reported at the dev t\* for q-v0.3)
- Create (if Step 3 runs): `evals/baselines/gen-v0.3-holdout/<q-v0.2 run_id>/`, `evals/baselines/gen-v0.3-holdout/compare-q-v0.2-vs-q-v0.3.txt`, `evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/`
- Create (if Step 3 is skipped): `evals/baselines/gen-v0.3-holdout/q-v0.2-skipped.txt`

**Interfaces:**
- Consumes: the dev t\*s (`selected "$(run_dir evals/baselines/gen-v0.3-dev q-v0.X)/sweep.json"`) and `adoption.txt` (Task 3).
- Produces: the holdout bundles (`run_dir evals/baselines/gen-v0.3-holdout q-v0.3|q-v0.2`) and the holdout gate result that Task 8 turns into the adoption gate when the decision was ADOPT.

Holdout is evaluated once, at thresholds chosen on dev. Nothing is re-chosen here.

- [ ] **Step 1 (PAID, run exactly once): Jev q-v0.3 on gen-v0.3-holdout**

Expected estimate: `jev estimate: 1000 cases × 19 questions ≈ $0.2470`. Invalid-output limit: 20.

```bash
# (preamble)
P eval --dataset evals/generated/gen-v0.3-holdout --provider jev --questions q-v0.3 --policy v0.1 \
  --jev-budget-usd 1.00 --jev-ledger "$LEDGER" > "$D/e1-holdout-q-v0.3.txt" 2>&1; echo "exit $?"
head -2 "$D/e1-holdout-q-v0.3.txt"; grep '^Jev spend' "$D/e1-holdout-q-v0.3.txt"
echo "invalid=$(invalid_of "$D/e1-holdout-q-v0.3.txt") run=$(run_of "$D/e1-holdout-q-v0.3.txt")"
```

Expected: `exit 0`, the estimate line above, `invalid` ≤ 20. Otherwise stop.

- [ ] **Step 2: The fallback check (offline, spec §5)**

```bash
# (preamble)
uv run python -c "import sys; s=float(sys.argv[1]); need=0.1560+0.0247+0.0988+0.0291; print(f'spent {s:.4f} + remaining estimates {need:.4f} = {s+need:.4f}:', 'RUN q-v0.2 holdout' if s+need <= 1.00 else 'SKIP q-v0.2 holdout')" "$(spent)"
```

If it prints `RUN q-v0.2 holdout`, do Step 3. If it prints `SKIP q-v0.2 holdout`, don't run Step 3. Instead, write the printed line into `evals/baselines/gen-v0.3-holdout/q-v0.2-skipped.txt`, followed by the sentence `The q-v0.2 baseline on gen-v0.3-holdout was skipped under the spec §5 budget fallback; q-v0.3 is reported alone.` Then continue at Step 4.

- [ ] **Step 3 (PAID, run exactly once, only if Step 2 said RUN): Jev q-v0.2 on gen-v0.3-holdout**

Expected estimate: `jev estimate: 1000 cases × 12 questions ≈ $0.1560`. Invalid-output limit: 20.

```bash
# (preamble)
P eval --dataset evals/generated/gen-v0.3-holdout --provider jev --questions q-v0.2 --policy v0.1 \
  --jev-budget-usd 1.00 --jev-ledger "$LEDGER" > "$D/e1-holdout-q-v0.2.txt" 2>&1; echo "exit $?"
head -2 "$D/e1-holdout-q-v0.2.txt"; grep '^Jev spend' "$D/e1-holdout-q-v0.2.txt"
echo "invalid=$(invalid_of "$D/e1-holdout-q-v0.2.txt") run=$(run_of "$D/e1-holdout-q-v0.2.txt")"
```

Expected: `exit 0`, the estimate line above, `invalid` ≤ 20. Otherwise stop.

- [ ] **Step 4: Bundle, compare and gate at the dev t\*s (offline)**

```bash
# (preamble)
T2=$(selected "$(run_dir evals/baselines/gen-v0.3-dev q-v0.2)/sweep.json")
T3=$(selected "$(run_dir evals/baselines/gen-v0.3-dev q-v0.3)/sweep.json")
H3=$(run_of "$D/e1-holdout-q-v0.3.txt")
bundle "$H3" evals/generated/gen-v0.3-holdout "evals/baselines/gen-v0.3-holdout/$H3" "$T3"
if [ -f "$D/e1-holdout-q-v0.2.txt" ]; then
  H2=$(run_of "$D/e1-holdout-q-v0.2.txt")
  bundle "$H2" evals/generated/gen-v0.3-holdout "evals/baselines/gen-v0.3-holdout/$H2" "$T2"
  BA=(); [ -n "$T2" ] && BA=(--baseline-at "$T2"); CA=(); [ -n "$T3" ] && CA=(--candidate-at "$T3")
  R compare --dataset evals/generated/gen-v0.3-holdout \
    --traces "evals/baselines/gen-v0.3-holdout/$H2/traces.jsonl.gz" \
    --traces "evals/baselines/gen-v0.3-holdout/$H3/traces.jsonl.gz" \
    --labels q-v0.2,q-v0.3 > evals/baselines/gen-v0.3-holdout/compare-q-v0.2-vs-q-v0.3.txt; echo "compare exit $?"
  R regression --dataset evals/generated/gen-v0.3-holdout \
    --baseline "evals/baselines/gen-v0.3-holdout/$H2/traces.jsonl.gz" "${BA[@]}" \
    --candidate-traces "evals/baselines/gen-v0.3-holdout/$H3/traces.jsonl.gz" "${CA[@]}" \
    --out evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3 > "$D/e1-holdout-gate.txt"; echo "gate exit $?"
  tail -1 "$D/e1-holdout-gate.txt"
fi
tail -1 evals/baselines/gen-v0.3-dev/adoption.txt
```

Expected: gate exit 0 or 4, or no gate if q-v0.2 was skipped. **If the dev decision was ADOPT and the holdout gate exits 4 (FAIL), stop and report.** The spec requires the adoption gate to PASS, and no threshold or question may be changed after seeing holdout. With KEEP, a FAIL is simply reported.

- [ ] **Step 5: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`, then `R regression --config evals/regression/gates.json --strict-generated > /dev/null; echo "gates exit $?"` (with the preamble).

Expected: all tests pass (the drift guard re-scores the holdout bundles); `gates exit 0`.

- [ ] **Step 6: Commit**

```bash
# (preamble)
H3=$(run_of "$D/e1-holdout-q-v0.3.txt")
git add "evals/baselines/gen-v0.3-holdout/$H3"
if [ -f "$D/e1-holdout-q-v0.2.txt" ]; then
  git add "evals/baselines/gen-v0.3-holdout/$(run_of "$D/e1-holdout-q-v0.2.txt")" \
    evals/baselines/gen-v0.3-holdout/compare-q-v0.2-vs-q-v0.3.txt \
    evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3
else
  git add evals/baselines/gen-v0.3-holdout/q-v0.2-skipped.txt
fi
git status --short
git commit -m "feat: add the one-shot gen-v0.3-holdout Jev runs and the q-v0.2 to q-v0.3 holdout gate" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: E1 on gold (for completeness, not blind for this change), and the GOLD-TMP-17 replay

**Files:**
- Create: `evals/baselines/gold-v0.1/<q-v0.3 run_id>/` (bundle)
- Create: `evals/baselines/gold-v0.1/regression-q-v0.2-vs-q-v0.3/`
- Create: `evals/baselines/gold-v0.1/replay-GOLD-TMP-17-q-v0.2-vs-q-v0.3.txt`, `evals/baselines/gold-v0.1/replay-GOLD-TMP-18-q-v0.2-vs-q-v0.3.txt`

**Interfaces:**
- Consumes: the dev t\*s (Task 3); the committed q-v0.2 gold Jev run `evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/`.
- Produces: the gold q-v0.3 bundle (`run_dir evals/baselines/gold-v0.1 q-v0.3`), the gold regression and the two replay texts, which the README pastes verbatim.

Spec §1: q-v0.3 was motivated by GOLD-TMP-17, so gold is **not a blind test** for q-v0.3 on the interruption and restart cases (GOLD-TMP-17 and GOLD-TMP-18). This run happens exactly once, and its results are reported beside that caveat, never as headline evidence. `evals/gold/` is not edited.

- [ ] **Step 1 (PAID, run exactly once): Jev q-v0.3 on gold-v0.1**

Expected estimate: `jev estimate: 100 cases × 19 questions ≈ $0.0247`. Invalid-output limit: 2.

```bash
# (preamble)
P eval --dataset evals/gold --provider jev --questions q-v0.3 --policy v0.1 \
  --jev-budget-usd 1.00 --jev-ledger "$LEDGER" > "$D/e1-gold-q-v0.3.txt" 2>&1; echo "exit $?"
head -2 "$D/e1-gold-q-v0.3.txt"; grep '^Jev spend' "$D/e1-gold-q-v0.3.txt"
echo "invalid=$(invalid_of "$D/e1-gold-q-v0.3.txt") run=$(run_of "$D/e1-gold-q-v0.3.txt")"
```

Expected: `exit 0`, the estimate line above, `invalid` ≤ 2. Otherwise stop.

- [ ] **Step 2: Bundle, regress against the committed q-v0.2 gold run, and replay the interruption cases (offline)**

```bash
# (preamble)
G=$(run_of "$D/e1-gold-q-v0.3.txt"); OLD=evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9
T2=$(selected "$(run_dir evals/baselines/gen-v0.3-dev q-v0.2)/sweep.json")
T3=$(selected "$(run_dir evals/baselines/gen-v0.3-dev q-v0.3)/sweep.json")
bundle "$G" evals/gold "evals/baselines/gold-v0.1/$G" "$T3"
BA=(); [ -n "$T2" ] && BA=(--baseline-at "$T2"); CA=(); [ -n "$T3" ] && CA=(--candidate-at "$T3")
R regression --dataset evals/gold --baseline "$OLD/traces.jsonl.gz" "${BA[@]}" \
  --candidate-traces "evals/baselines/gold-v0.1/$G/traces.jsonl.gz" "${CA[@]}" \
  --out evals/baselines/gold-v0.1/regression-q-v0.2-vs-q-v0.3 > "$D/e1-gold-gate.txt"; echo "gate exit $?"
for c in GOLD-TMP-17 GOLD-TMP-18; do
  R replay "$c" --traces "$OLD/traces.jsonl.gz" --dataset evals/gold \
    --candidate-traces "evals/baselines/gold-v0.1/$G/traces.jsonl.gz" \
    > "evals/baselines/gold-v0.1/replay-$c-q-v0.2-vs-q-v0.3.txt"; echo "$c replay exit $?"
done
head -30 evals/baselines/gold-v0.1/replay-GOLD-TMP-17-q-v0.2-vs-q-v0.3.txt
```

Expected: the gate exit is 0 or 4 and each replay exit is 0 or 4. All of these are results; exit 2 is an input error (stop). The GOLD-TMP-17 replay shows whether q-v0.3 now reads the interruption: look at the step_therapy row and the action line.

- [ ] **Step 3: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`, then (with the preamble) `R regression --config evals/regression/gates.json --strict-generated > /dev/null; echo "gates exit $?"`.

Expected: all tests pass. `test_every_committed_gold_trace_reproduces` now also covers the new gold run (100 traces, no ENGINE DRIFT). `gates exit 0`.

- [ ] **Step 4: Commit**

```bash
# (preamble)
G=$(run_of "$D/e1-gold-q-v0.3.txt")
git add "evals/baselines/gold-v0.1/$G" evals/baselines/gold-v0.1/regression-q-v0.2-vs-q-v0.3 \
  evals/baselines/gold-v0.1/replay-GOLD-TMP-17-q-v0.2-vs-q-v0.3.txt \
  evals/baselines/gold-v0.1/replay-GOLD-TMP-18-q-v0.2-vs-q-v0.3.txt
git status --short
git commit -m "feat: add the q-v0.3 gold run, its regression against q-v0.2 and the TMP-17/18 replays" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: E2, the policy shift: one paid run, stale and aware recomposed, the gate, the shadow demo and the rules context

**Files:**
- Create: `evals/baselines/gen-v0.3-shift/<source run_id>/` (the paid run under immunara-v0.2, bundle)
- Create: `evals/baselines/gen-v0.3-shift/stale-immunara-v0.1/` and `evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/` (`traces.jsonl.gz`, `run-manifest.json`, `results.json`, `report/`)
- Create: `evals/baselines/gen-v0.3-shift/regression-stale-to-aware/`, `evals/baselines/gen-v0.3-shift/shift-summary.md`
- Create: `evals/baselines/gen-v0.3-shift/shadow-stale-to-aware/` (`shadow.json`, `shadow.md`)
- Create: `evals/baselines/gen-v0.3-shift/<rules run_id>/` (bundle)

**Interfaces:**
- Consumes: `relay recompose` (3D1 Task 10); `relay run --workflow simulated|shadow` (3C); `scripts/phase3d_report.py shift` (Task 2).
- Produces: the stale and aware runs at fixed paths (Task 8 gates them); `shift-summary.md` (the README table); the shadow report.

Both runs score against the shift set's ground truth, which is labelled under immunara-v0.2. Both use their policy's recorded thresholds (v0.1 and v0.2, identical values, auto_process 0.95). This isolates the effect of composition.

- [ ] **Step 1 (PAID, run exactly once): Jev q-v0.3 on gen-v0.3-shift under immunara-v0.2**

Expected estimate: `jev estimate: 400 cases × 19 questions ≈ $0.0988`. Invalid-output limit: 8.

```bash
# (preamble)
P eval --dataset evals/generated/gen-v0.3-shift --provider jev --questions q-v0.3 --policy v0.2 \
  --jev-budget-usd 1.00 --jev-ledger "$LEDGER" > "$D/e2-shift-q-v0.3.txt" 2>&1; echo "exit $?"
head -2 "$D/e2-shift-q-v0.3.txt"; grep '^Jev spend' "$D/e2-shift-q-v0.3.txt"
echo "invalid=$(invalid_of "$D/e2-shift-q-v0.3.txt") run=$(run_of "$D/e2-shift-q-v0.3.txt")"
```

Expected: `exit 0`, the estimate line above, `invalid` ≤ 8. Otherwise stop.

- [ ] **Step 2: Bundle the source run and recompose stale and aware (offline)**

```bash
# (preamble)
S=$(run_of "$D/e2-shift-q-v0.3.txt"); SH=evals/generated/gen-v0.3-shift; OUT=evals/baselines/gen-v0.3-shift
bundle "$S" "$SH" "$OUT/$S"
R recompose --traces "$OUT/$S/traces.jsonl.gz" --dataset "$SH" --policy immunara-v0.1 --out "$OUT/stale-immunara-v0.1" | tee "$D/e2-stale.txt"
R recompose --traces "$OUT/$S/traces.jsonl.gz" --dataset "$SH" --policy immunara-v0.2 --out "$OUT/aware-immunara-v0.2" | tee "$D/e2-aware.txt"
for side in stale-immunara-v0.1 aware-immunara-v0.2; do
  R eval --dataset "$SH" --traces "$OUT/$side/traces.jsonl.gz" --results-dir "$D/results-$side" > "$D/e2-eval-$side.txt"; echo "$side eval exit $?"
  cp "$(grep '^Results: ' "$D/e2-eval-$side.txt" | cut -d' ' -f2)" "$OUT/$side/results.json"
  R report --dataset "$SH" --traces "$OUT/$side/traces.jsonl.gz" --out "$OUT/$side/report" > /dev/null; echo "$side report exit $?"
done
```

Expected: the aware recompose prints `… step_therapy changed on 0 case(s), action changed on 0 case(s).`, because the source run was already composed under immunara-v0.2. The stale recompose shows the cases that recency changes. Both evals and reports exit 0.

- [ ] **Step 3: Gate stale → aware, and write the summary (offline)**

```bash
# (preamble)
OUT=evals/baselines/gen-v0.3-shift
R regression --dataset evals/generated/gen-v0.3-shift --baseline "$OUT/stale-immunara-v0.1/traces.jsonl.gz" \
  --candidate-traces "$OUT/aware-immunara-v0.2/traces.jsonl.gz" --out "$OUT/regression-stale-to-aware" \
  > "$D/e2-gate.txt"; echo "gate exit $?"
tail -1 "$D/e2-gate.txt"
uv run python -m scripts.phase3d_report shift "$OUT/regression-stale-to-aware/regression.json" > "$OUT/shift-summary.md"
cat "$OUT/shift-summary.md"
```

Expected: `gate exit 0` and `REGRESSION GATE: PASS`. The aware AUTO_PROCESS cases are a subset of the stale ones, so nothing can be newly unsafe. **Any other exit: stop and report.** `shift-summary.md` holds the table (UAR, automation, correct for each run) and the stale-only unsafe automations.

- [ ] **Step 4: The shadow demo: stale as the simulated incumbent, aware as the shadow candidate (offline)**

```bash
# (preamble)
OUT=evals/baselines/gen-v0.3-shift; SH=evals/generated/gen-v0.3-shift
[ -e state/shift-demo.json ] && mv state/shift-demo.json "state/shift-demo.json.old-$(date -u +%Y%m%dT%H%M%SZ)"; true
R run --dataset "$SH" --workflow simulated --state state/shift-demo.json \
  --from-traces "$OUT/stale-immunara-v0.1/traces.jsonl.gz" > "$D/e2-simulated.txt"; echo "simulated exit $?"
INC=$(grep '^Traces: ' "$D/e2-simulated.txt" | cut -d' ' -f2)
R run --dataset "$SH" --workflow shadow --state state/shift-demo.json \
  --from-traces "$OUT/aware-immunara-v0.2/traces.jsonl.gz" --incumbent "$INC" \
  --out "$OUT/shadow-stale-to-aware" > "$D/e2-shadow.txt"; echo "shadow exit $?"
grep -E '^SIMULATED RUN' "$D/e2-simulated.txt"; grep -E 'case state unchanged|PROMOTION CHECK' "$D/e2-shadow.txt"
ls "$OUT/shadow-stale-to-aware"
```

Expected: `simulated exit 0`, `shadow exit 0`, a `… case state unchanged (verified)` line, `PROMOTION CHECK: PROMOTE`, and `shadow.json shadow.md`. Any other outcome: stop and report. By the subset argument it can't HOLD without `--max-regressed`.

- [ ] **Step 5: The rules baseline on the shift set, for context (offline, network-free)**

```bash
# (preamble)
R eval --dataset evals/generated/gen-v0.3-shift --provider rules --policy v0.2 > "$D/e2-rules.txt"; echo "exit $?"
RR=$(run_of "$D/e2-rules.txt"); bundle "$RR" evals/generated/gen-v0.3-shift "evals/baselines/gen-v0.3-shift/$RR"
grep -E 'Correct action rate|Automation rate|Unsafe automation rate' "$D/e2-rules.txt"
```

Expected: `exit 0`. The numbers were 261/400 correct, 50/400 automated and 6/50 unsafe when planned; the rules are deterministic, so they must match. rules-v0.1 has no recency rule, so it is naive by construction and reported as such.

- [ ] **Step 6: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`, then (with the preamble) `R regression --config evals/regression/gates.json --strict-generated > /dev/null; echo "gates exit $?"`.

Expected: all tests pass (the drift guard re-scores the source, stale, aware and rules runs); `gates exit 0`.

- [ ] **Step 7: Commit**

```bash
# (preamble)
OUT=evals/baselines/gen-v0.3-shift
git add "$OUT/$(run_of "$D/e2-shift-q-v0.3.txt")" "$OUT/$(run_of "$D/e2-rules.txt")" \
  "$OUT/stale-immunara-v0.1" "$OUT/aware-immunara-v0.2" "$OUT/regression-stale-to-aware" \
  "$OUT/shift-summary.md" "$OUT/shadow-stale-to-aware"
git status --short
git commit -m "feat: add the immunara-v0.2 policy-shift run, stale and aware recompositions, gate and shadow demo" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: E3, parallelism: one paid bench

**Files:**
- Create: `evals/baselines/bench/parallelism.json`, `evals/baselines/bench/parallelism.md`

**Interfaces:**
- Consumes: `relay bench` (3D1 Task 11).
- Produces: the latency table that the README pastes verbatim.

- [ ] **Step 1 (PAID, run exactly once): relay bench on 40 gen-v0.3-dev cases, sample seed 11, sizes 1, 5, 10, 20**

Expected estimate: `jev estimate: 40 cases × (1+5+10+20) questions ≈ $0.0291`. Error limit: 3 of 160 calls.

```bash
# (preamble)
P bench --dataset evals/generated/gen-v0.3-dev --limit 40 --sample-seed 11 --sizes 1,5,10,20 \
  --jev-budget-usd 1.00 --jev-ledger "$LEDGER" --out evals/baselines/bench > "$D/e3-bench.txt" 2>&1; echo "exit $?"
head -2 "$D/e3-bench.txt"; grep '^Jev spend' "$D/e3-bench.txt"
uv run python -c "import json; d=json.load(open('evals/baselines/bench/parallelism.json')); print('errors', sum(s['errors'] for s in d['sizes']), 'of', sum(s['calls'] for s in d['sizes']))"
cat evals/baselines/bench/parallelism.md
```

Expected: `exit 0`, the estimate line above, `errors` ≤ 3 `of 160`. Otherwise stop, and don't commit the files.

- [ ] **Step 2: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`

Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add evals/baselines/bench/parallelism.json evals/baselines/bench/parallelism.md
git commit -m "feat: add the parallelism bench (latency vs narrow decisions per call)" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Committed gates for the new runs, and the spend record

**Files:**
- Modify: `evals/regression/gates.json`
- Modify: `tests/integration/test_committed_gates.py`
- Create: `evals/baselines/jev-spend-3d.json` (a copy of the git-ignored ledger)

**Interfaces:**
- Consumes: every committed run from Tasks 3–6, `adoption.txt`, and the dev `sweep.json` files.
- Produces: the reproduce gates, the adoption gate (only when ADOPT and holdout q-v0.2 ran) and `gen-v0.3-shift-stale-to-aware`, all passing with `--strict-generated`.

- [ ] **Step 1: Append the Phase 3D gates to `evals/regression/gates.json`**

Save this as `/tmp/relay-3d/add_gates.py`. It is a scratch tool; don't commit it. Run it from the repository root with `uv run python /tmp/relay-3d/add_gates.py`. It finds the runs by provider and question set, reads the dev t\*s, and appends entries in the file's existing style. The adoption gate is added only when `adoption.txt` says ADOPT and a holdout q-v0.2 run exists.

```python
import json
from pathlib import Path

B = Path("evals/baselines")
GATES = Path("evals/regression/gates.json")


def run_dirs(base: str, provider: str, question_set: str) -> list[Path]:
    out = []
    for p in sorted((B / base).glob("run_*")):
        m = json.loads((p / "run-manifest.json").read_text())
        if m["provider"] == provider and m.get("question_set_version") == question_set:
            out.append(p)
    return out


def one(base: str, question_set: str) -> Path:
    [hit] = run_dirs(base, "jev", question_set)
    return hit


def tstar(run: Path) -> float | None:
    selected = json.loads((run / "sweep.json").read_text())["selected"]
    return None if selected is None else selected["auto_threshold"]


def entry(name, dataset, baseline, candidate, *, baseline_at=None, generated=True) -> str:
    lines = [
        "    {",
        f'      "name": "{name}",',
        f'      "dataset": "{dataset}",',
        f'      "baseline": "{baseline}",',
    ]
    if baseline_at is not None:
        lines.append(f'      "baseline_at": {baseline_at},')
    lines.append(f'      "candidate": {json.dumps(candidate)}' + ("," if generated else ""))
    if generated:
        lines.append('      "requires_generated": true')
    lines.append("    }")
    return "\n".join(lines)


def traces(run: Path) -> str:
    return f"{run.as_posix()}/traces.jsonl.gz"


REPRO = {"reproduce": True}
dev2, dev3 = one("gen-v0.3-dev", "q-v0.2"), one("gen-v0.3-dev", "q-v0.3")
hold3 = one("gen-v0.3-holdout", "q-v0.3")
hold2 = run_dirs("gen-v0.3-holdout", "jev", "q-v0.2")  # empty if the fallback skipped it
gold3 = one("gold-v0.1", "q-v0.3")
shift3 = one("gen-v0.3-shift", "q-v0.3")
adopt = (B / "gen-v0.3-dev" / "adoption.txt").read_text().rstrip().endswith("DECISION: ADOPT q-v0.3")
entries = [
    entry("gen-v0.3-dev-reproduce-jev-q-v0.2", "evals/generated/gen-v0.3-dev", traces(dev2), REPRO),
    entry("gen-v0.3-dev-reproduce-jev-q-v0.3", "evals/generated/gen-v0.3-dev", traces(dev3), REPRO),
    entry(
        "gen-v0.3-holdout-reproduce-jev-q-v0.3",
        "evals/generated/gen-v0.3-holdout",
        traces(hold3),
        REPRO,
    ),
]
if hold2:
    entries.append(
        entry(
            "gen-v0.3-holdout-reproduce-jev-q-v0.2",
            "evals/generated/gen-v0.3-holdout",
            traces(hold2[0]),
            REPRO,
        )
    )
    if adopt:
        candidate = {"traces": traces(hold3)}
        if tstar(dev3) is not None:
            candidate["at"] = tstar(dev3)
        entries.append(
            entry(
                "gen-v0.3-holdout-adoption-q-v0.2-to-q-v0.3",
                "evals/generated/gen-v0.3-holdout",
                traces(hold2[0]),
                candidate,
                baseline_at=tstar(dev2),
            )
        )
entries += [
    entry("gold-reproduce-jev-q-v0.3", "evals/gold", traces(gold3), REPRO, generated=False),
    entry(
        "gen-v0.3-shift-reproduce-jev-q-v0.3", "evals/generated/gen-v0.3-shift", traces(shift3), REPRO
    ),
    entry(
        "gen-v0.3-shift-reproduce-stale",
        "evals/generated/gen-v0.3-shift",
        "evals/baselines/gen-v0.3-shift/stale-immunara-v0.1/traces.jsonl.gz",
        REPRO,
    ),
    entry(
        "gen-v0.3-shift-reproduce-aware",
        "evals/generated/gen-v0.3-shift",
        "evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz",
        REPRO,
    ),
    entry(
        "gen-v0.3-shift-stale-to-aware",
        "evals/generated/gen-v0.3-shift",
        "evals/baselines/gen-v0.3-shift/stale-immunara-v0.1/traces.jsonl.gz",
        {"traces": "evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz"},
    ),
]
text = GATES.read_text()
tail = "\n    }\n  ]\n}\n"
assert text.endswith(tail), "unexpected end of gates.json"
GATES.write_text(text[: -len(tail)] + "\n    },\n" + ",\n".join(entries) + "\n  ]\n}\n")
names = [g["name"] for g in json.loads(GATES.read_text())["gates"]]
print("\n".join(names))
```

Expected: it prints every gate name. The first nine are unchanged, followed by 8 to 10 new names. (The script was checked on a mock tree while planning: the JSON parses, and the entries match the existing style.)

- [ ] **Step 2: Update the committed-gates name test**

In `tests/integration/test_committed_gates.py`, replace:

```python
        "holdout-reproduce-rules",
        "holdout-reproduce-claude-150",
    ]
```

with the following, **deleting** the `gen-v0.3-holdout-reproduce-jev-q-v0.2` line if holdout q-v0.2 was skipped, and the `gen-v0.3-holdout-adoption-q-v0.2-to-q-v0.3` line unless it was printed in Step 1. The list must equal the names Step 1 printed, in order:

```python
        "holdout-reproduce-rules",
        "holdout-reproduce-claude-150",
        "gen-v0.3-dev-reproduce-jev-q-v0.2",
        "gen-v0.3-dev-reproduce-jev-q-v0.3",
        "gen-v0.3-holdout-reproduce-jev-q-v0.3",
        "gen-v0.3-holdout-reproduce-jev-q-v0.2",
        "gen-v0.3-holdout-adoption-q-v0.2-to-q-v0.3",
        "gold-reproduce-jev-q-v0.3",
        "gen-v0.3-shift-reproduce-jev-q-v0.3",
        "gen-v0.3-shift-reproduce-stale",
        "gen-v0.3-shift-reproduce-aware",
        "gen-v0.3-shift-stale-to-aware",
    ]
```

- [ ] **Step 3: Run every gate strictly, and record the spend**

```bash
# (preamble)
R regression --config evals/regression/gates.json --strict-generated --out "$D/gates" > "$D/gates.txt"; echo "gates exit $?"
sed -n '/^REGRESSION GATES/,$p' "$D/gates.txt"
cp "$LEDGER" evals/baselines/jev-spend-3d.json
R budget show --ledger evals/baselines/jev-spend-3d.json
```

Expected: `gates exit 0` and every row `PASS`, with no SKIPPED or ERROR. The ledger has one settled entry per paid step that ran (6 or 7), no `reserved` entries, and a total ≤ $1.00. If the total is over $1.00 or any entry is still reserved, stop and report.

- [ ] **Step 4: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`

Expected: all pass. `test_the_committed_gates_pass` runs the new gates too (the gen-v0.3 datasets are on disk).

- [ ] **Step 5: Commit**

```bash
git add evals/regression/gates.json tests/integration/test_committed_gates.py evals/baselines/jev-spend-3d.json
git commit -m "feat: gate the Phase 3D runs (reproduce, adoption, stale to aware) and record the Jev spend" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: README: q-v0.3, the policy shift, parallelism and the Phase 3D spend

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: every artifact from Tasks 1–8. The README contains only numbers that appear in those artifacts, including negative results.

Rules for this task: paste artifact text verbatim, don't round differently, and don't describe a result the artifacts don't show. Where the text below says *(from FILE)*, copy the exact content of that file or line. Where it says *write*, write plain sentences whose every number appears in a pasted artifact.

- [ ] **Step 1: Commands**

In `README.md`, replace:

```markdown
uv run relay budget show --ledger results/claude-spend.json                     # Claude spend ledger entries and totals
```

with:

```markdown
uv run relay budget show --ledger results/claude-spend.json                     # Claude spend ledger entries and totals
uv run relay generate --generator gen-v0.3 [--policy v0.2] --count N --seed S --dataset-id ID --out DIR   # gen-v0.3: interrupted and old courses
uv run relay eval --dataset <dir> --provider jev --questions q-v0.3 --jev-budget-usd 1.00 --jev-ledger <abs path>   # Jev spend counter: estimate first, refuse over the cap
uv run relay recompose --traces <jev file> --dataset <dir> --policy immunara-v0.1 --out <dir>   # stored Jev answers recomposed under a policy (offline)
uv run relay bench --dataset <dir> --limit 40 --sample-seed 11 --sizes 1,5,10,20 --jev-budget-usd 1.00   # latency vs questions per call (paid)
```

- [ ] **Step 2: Generated datasets**

In `README.md`, replace:

```markdown
| `gen-v0.2-holdout` | 2 | 1000 | 281 / 236 / 483 | Final reporting only |
```

with the following. The action counts come from the committed gen-v0.3 manifests and equal the planning values; check them against `evals/generated/manifests/gen-v0.3-*.json`.

```markdown
| `gen-v0.2-holdout` | 2 | 1000 | 281 / 236 / 483 | Final reporting only |
| `gen-v0.3-dev` | 3 | 400 | 122 / 93 / 185 | q-v0.3 development and threshold selection (gen-v0.3) |
| `gen-v0.3-holdout` | 4 | 1000 | 265 / 269 / 466 | One-shot q-v0.2 vs q-v0.3 evaluation (gen-v0.3) |
| `gen-v0.3-shift` | 5 | 400 | 85 / 99 / 216 | Policy-shift experiment, labelled under immunara-v0.2 (gen-v0.3) |

`gen-v0.3` (`--generator gen-v0.3`) keeps every gen-v0.2 distribution and adds two things.
About 20% of taken methotrexate courses are interrupted (held for an infection, surgery, travel
or a lab recheck, then restarted), split evenly between no segment reaching 12 weeks although
the whole span does (the GOLD-TMP-17 pattern), the later segment qualifying (GOLD-TMP-18), and
the earlier one qualifying. Labels follow gold rule D8: only a single segment of at least 84 days
counts. About 25% of taken courses ended more than 365 days before the request. Labels are
derived under each case's own policy, so `gen-v0.3-shift` (`--policy v0.2`) is labelled under
immunara-v0.2's recency rule. gen-v0.2 output is unchanged (`--verify` still passes).
```

- [ ] **Step 3: The two new sections and the parallelism table**

Insert the following immediately before the line `## Limitations`. Fill each *(from …)* with the exact file content, fenced as `text` where marked, and write the three **Findings** paragraphs as instructed.

````markdown
## Question set q-v0.3 (interrupted courses)

**Honesty constraint.** q-v0.3 was motivated by a gold finding: GOLD-TMP-17's interrupted
methotrexate course, which q-v0.2 read as one 133-day course and which both Jev and Claude
therefore auto-approved. The README rule forbids question changes motivated by gold, so q-v0.3 was
developed on a new generated dev set (`gen-v0.3-dev`) and evaluated once on a new holdout
(`gen-v0.3-holdout`), which is the primary evidence. It ran on gold-v0.1 exactly once, for
completeness. **Gold is not a blind test for q-v0.3 on the interruption and restart cases
(GOLD-TMP-17 and GOLD-TMP-18).** gold-v0.1 was not edited.

q-v0.3 keeps all 12 q-v0.2 questions and adds 7 (19 in all): whether the patient's own methotrexate
was held, paused or stopped and later restarted, and the date parts of the pause and of the restart.
Two instructions gain "(the first time, if it was restarted)" and "(the last time, if it was
restarted)". Code composes P(some consecutive segment ≥ 12 weeks) =
(1 − p_int) · P(first start → final end) + p_int · P(start → pause **or** restart → end).
The two segment events are combined by inclusion-exclusion, under the same independence
approximation as the date parts.

**Adoption on dev** (rule fixed in advance: adopt iff q-v0.3's dev correct-action rate is higher
and the dev regression gate passes with 0 newly unsafe), *(from `evals/baselines/gen-v0.3-dev/adoption.txt`, fenced as text)*.

**Holdout, once, at the dev-selected thresholds.** *(from `evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/regression.md`: the lines from `Relay regression — dataset gen-v0.3-holdout` through the `CHANGES:` line, and the `NEWLY UNSAFE` / `STILL UNSAFE` / `UNSAFE RESOLVED` sections if present, fenced as text; or, if q-v0.2 was skipped, the text of `q-v0.2-skipped.txt` plus the `Correct action rate`, `Automation rate` and `Unsafe automation rate` lines of `/tmp/relay-3d/e1-holdout-q-v0.3.txt`.)*

**Gold (not blind for this change; see above).** *(from `evals/baselines/gold-v0.1/regression-q-v0.2-vs-q-v0.3/regression.md`: the lines from `Relay regression — dataset gold-v0.1` through the `CHANGES:` line, the `NEWLY UNSAFE` / `STILL UNSAFE` / `UNSAFE RESOLVED` sections if present, and the final `REGRESSION GATE:` line, fenced as text.)*

GOLD-TMP-17 replayed across the two question sets:

*(from `evals/baselines/gold-v0.1/replay-GOLD-TMP-17-q-v0.2-vs-q-v0.3.txt`, the whole file, fenced as text)*

**Findings.** *Write* 3–5 sentences: the decision and its two legs (correct-action counts and the gate verdict), what holdout showed (or that q-v0.2 was skipped), whether the TMP-17 replay shows the interruption read (the step_therapy row and the action), and any negative result (for example, newly unsafe or regressed cases on holdout or gold).

## Policy shift (immunara-v0.2)

immunara-v0.2 is immunara-v0.1 plus one added prior-treatment requirement ("policy_v5" in the
handoff): *"The qualifying methotrexate course must have been ongoing, or have ended, within the
12 months (365 days) before the request date."* Recency is part of step therapy, which Relay composes
in code, so the policy engine needed no new gate. One paid q-v0.3 Jev run on `gen-v0.3-shift`
(ground truth labelled under v0.2) was recomposed twice from the same stored answers with
`relay recompose`: **stale** composes under immunara-v0.1 (policy-unaware), and **aware** under
immunara-v0.2. Both are scored against the v0.2 ground truth at auto_process 0.95.

*(from `evals/baselines/gen-v0.3-shift/shift-summary.md`, pasted as Markdown, not fenced)*

The stale-only unsafe automations are approvals that pass v0.1's rule but break the recency
requirement. The committed gate `gen-v0.3-shift-stale-to-aware` runs stale → aware in CI.

**Shadow demo.** Stale is the simulated incumbent and aware the shadow candidate:
*(from `/tmp/relay-3d/e2-shadow.txt`, only the `SHADOW RUN … case state unchanged (verified).` line and the last line `PROMOTION CHECK: …`, fenced as text)*

**Rules baseline, for context.** rules-v0.1 has no recency rule, so it is naive by construction:
*(from `/tmp/relay-3d/e2-rules.txt`, the `Correct action rate`, `Automation rate` and `Unsafe automation rate` lines, fenced as text)*

**Findings.** *Write* 2–4 sentences: how many stale-only unsafe automations there were and what they cost in UAR, what aware gave up in automation, and the shadow verdict.

## Parallelism (narrow decisions per call)

Handoff experiment 4 asks whether adding narrow decisions costs latency. `relay bench` sent 40
gen-v0.3-dev cases (sample seed 11) to Jev with 1, 5, 10 and 20 questions per call. Every call is
one `system_one` request carrying all of its questions, and the typesafe-sdk client returns no
per-question timing. Calls ran one at a time. Size 20 is q-v0.3's 19 questions plus one duplicated
question (controlled padding). The runs are latency-only; their decisions are not scored.

*(from `evals/baselines/bench/parallelism.md`: the table and the lines below it, not the `#` title, pasted as Markdown)*

**Findings.** *Write* 1–3 sentences comparing p50/p95 latency and cost per case from 1 to 20 questions.

## Phase 3D Jev spend

Every paid Phase 3D run went through the Jev spend counter (cap $1.00). The committed copy of the ledger
is [`evals/baselines/jev-spend-3d.json`](evals/baselines/jev-spend-3d.json). No Claude calls were made.

*(from `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env budget show --ledger evals/baselines/jev-spend-3d.json`, every line except the last, fenced as text)*

Total: *(the `Settled $… · reserved $0.0000 · total $…` line's total)* of the $1.00 cap.
````

- [ ] **Step 4: Project docs**

In `README.md`, replace:

```markdown
- [Phase 3C implementation plan](docs/superpowers/plans/2026-09-26-phase3c-shadow-mode.md)
```

with:

```markdown
- [Phase 3C implementation plan](docs/superpowers/plans/2026-09-26-phase3c-shadow-mode.md)
- [Phase 3D design (q-v0.3, policy shift, parallelism)](docs/superpowers/specs/2026-09-26-phase3d-questions-and-policy-shift-design.md)
- [Phase 3D1 implementation plan](docs/superpowers/plans/2026-09-26-phase3d1-generator-policy-questions.md)
- [Phase 3D2 implementation plan](docs/superpowers/plans/2026-09-26-phase3d2-experiments.md)
```

- [ ] **Step 5: Final verification**

```bash
# (preamble)
uv run ruff check --fix . && uv run ruff format . && uv run pytest -q
R regression --config evals/regression/gates.json --strict-generated > /dev/null; echo "gates exit $?"
for m in evals/generated/manifests/gen-v0.*.json; do d=$(basename "$m" .json); R generate --verify "$m" --out "evals/generated/$d"; done
grep -c 'PASTE\|(from `' README.md
git status --short
```

Expected: all tests pass; `gates exit 0`; five `OK:` lines; `grep -c` prints `0` (no unfilled marker is left); `git status` shows only `README.md` modified.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: add the q-v0.3, policy-shift, parallelism and Phase 3D spend sections" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```



---

## Self-review (done while planning)

- **Spec coverage (the 3D2 part).** §2 datasets: manifests committed and case folders ignored (Task 1). §5 E1: two dev runs, sweep, t\* per question set, dev gate and adoption file (Task 3); holdout once for both sets with the budget fallback, compared and gated at the dev thresholds (Task 4); gold once with the §1 caveat, and the GOLD-TMP-17 replay in the README (Tasks 5 and 9). E2: one paid run under immunara-v0.2, stale and aware via `recompose`, UAR/automation/correct and the stale-only unsafe list, the stale → aware gate, the shadow demo and the rules context (Task 6). E3: 40 cases, seed 11, sizes 1, 5, 10, 20, padding disclosed, `parallelism.json`/`.md` (Task 7). The budget: every paid step has its estimate, the counter and the absolute ledger; total estimates $0.7168 ≤ $1.00 (header table). §7: bundles under `evals/baselines/gen-v0.3-{dev,holdout,shift}/` and `gold-v0.1/`; the adoption file; gates (reproduce, adoption if ADOPT, stale → aware) in Task 8; CI regeneration in Task 1; README sections in Task 9. §9: tests, ruff, and `--strict-generated` gates after every task; real numbers only; spend reported (Tasks 8 and 9); no Claude calls.
- **Paid steps.** Exactly seven, each its own step, each with its expected estimate line, `--jev-budget-usd 1.00`, the absolute ledger `/Users/joelbrook/Desktop/Code/Relay/results/jev-spend-3d.json`, run-once wording and stop rules (invalid outputs > 2%, an estimate over the remaining cap, any refusal of the counter, any failure).
- **Placeholders.** The only values not fixed in advance are experimental results. Task 9 says, for each, exactly which artifact line or file supplies it. Every command and code block is complete.
- **Consistency.** The run-directory names, gate names (Task 8 Step 1 and Step 2), file names and the preamble's function names (`R`, `P`, `run_of`, `invalid_of`, `selected`, `run_dir`, `spent`, `bundle`) are the same wherever they are used.
