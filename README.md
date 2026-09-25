# Relay

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

Relay is an evaluation-first, confidence-aware workflow engine for **synthetic** prior-authorization
cases. TypeSafe's [Jev](https://docs.typesafe.ai/) answers narrow, typed questions with
probabilities. A deterministic, versioned policy engine, not the model, then decides whether each
case is `AUTO_PROCESS`, `REQUEST_INFO`, or `HUMAN_REVIEW`.

```text
Jev:   What does the available evidence most likely establish?
Relay: What is software permitted to do given those judgments and their confidence?
```

## How it works

- **One Jev call per case, 12 questions.** Four yes/no Nouls (diagnosis, documentation,
  contradiction, inadequate response), one missing-evidence Choice, and seven Choices that read
  methotrexate start/end date parts. The model is pinned to `jev-1.13.0`.
- **Jev never does date arithmetic.** Code turns the date-part probabilities into a conservative
  P(treatment ≥ 12 weeks). Month-only dates count from the latest possible start to the earliest
  possible end, and unknown dates contribute nothing.
- **The policy engine owns the action.** Gates, in order: provider validity → age (a structured
  field, checked in code) → likely contradiction → incomplete documentation → confident missing
  evidence → autonomous-action bar (every requirement ≥ 0.95 and contradiction < 0.20) → human
  review.
- **Every case run is traced.** Append-only JSONL with a case hash, model version, question-set
  hash, policy version and thresholds, raw Jev answers, the step-therapy derivation, and the full
  gate path. Traces never contain ground truth or secrets.
- **Expected actions are derived, not hand-labelled.** Ground-truth facts go through the same
  engine at probability 1.0/0.0.

## Setup

```bash
uv sync
cp .env.example .env   # then set TYPESAFE_API_KEY
```

## Commands

```bash
uv run pytest                                                     # unit + integration (no network)
uv run pytest -m live                                             # one real Jev call
uv run relay run  --dataset evals/smoke --provider jev --policy v0.1
uv run relay eval --dataset evals/smoke --provider jev --policy v0.1
uv run relay eval --dataset evals/smoke --traces traces/<run_id>.jsonl   # re-score, no API calls
uv run relay eval --dataset evals/smoke --provider groundtruth           # pipeline validation only
```

`relay run` writes `traces/<run_id>.jsonl` and `reports/<run_id>.md`, a per-case explanation
covering the documents, decisions, step-therapy derivation, gates, and action. `relay eval` also
writes `results/<run_id>.json`.

## Reference smoke run

Committed under [`evals/baselines/smoke-v0.1/run_20260925T042324Z_eee114/`](evals/baselines/smoke-v0.1/).

```text
Relay eval — run run_20260925T042324Z_eee114
provider jev (jev-1.13.0) · policy v0.1 · dataset smoke-v0.1 · n=10
  Correct action rate       8/10 (80.0%)
  Automation rate           2/10 (20.0%)
  Request-info rate         4/10 (40.0%)
  Human escalation rate     4/10 (40.0%)
  Unsafe automation rate    0/2 (0.0%)
  Invalid outputs           0
  Latency p50 / p95         178 ms / 411 ms  [low-sample: n=10 < 30]
  Cost                      $0.0010917 total, $0.0001092 per case

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         100.0%
  step_therapy              100.0%
  documentation_complete    100.0%
  material_contradiction    100.0%
  missing_evidence          80.0%

Cases (expected -> actual):
  ADV-01    HUMAN_REVIEW  -> HUMAN_REVIEW  ok
  ADV-02    HUMAN_REVIEW  -> REQUEST_INFO  MISS
  AUTO-01   AUTO_PROCESS  -> AUTO_PROCESS  ok
  AUTO-02   AUTO_PROCESS  -> AUTO_PROCESS  ok
  AUTO-03   AUTO_PROCESS  -> HUMAN_REVIEW  MISS
  REV-01    HUMAN_REVIEW  -> HUMAN_REVIEW  ok
  REV-02    HUMAN_REVIEW  -> HUMAN_REVIEW  ok
  RI-01     REQUEST_INFO  -> REQUEST_INFO  ok
  RI-02     REQUEST_INFO  -> REQUEST_INFO  ok
  RI-03     REQUEST_INFO  -> REQUEST_INFO  ok

Results: results/run_20260925T042324Z_eee114.json
```

These numbers come from **ten** hand-authored synthetic cases. They show the pipeline working end
to end; they are not a statistically meaningful benchmark.

The case list above is ordered by case ID (a fix landed after this run to make eval output
deterministic regardless of run mode); every metric is unchanged from the original run. The
committed manifest and report still reference the original, git-ignored `traces/` path used at
run time, and the manifest's recorded git SHA ends in `-dirty` because the run happened before the
README/baseline commit; `relay/` and `policies/` were unchanged between that SHA and the baseline
commit.

## Generated datasets

`relay generate` produces seeded synthetic cases (generator `gen-v0.1`) in the same case-folder
format as the smoke set. Case `i` of a dataset uses seed `seed * 1_000_000 + i`, and difficulty
rotates easy → medium → hard → adversarial, so each class is exactly a quarter of the dataset.
Ground truth records what the rendered documents establish under `immunara-v0.1`. Month-only
dates are judged conservatively and yearless dates establish nothing. Expected actions are derived
by the engine, as for the smoke cases.

| Dataset | Seed | Cases | Expected actions (auto / request info / review) | Use |
|---|---|---|---|---|
| `gen-v0.1-dev` | 1 | 400 | 102 / 111 / 187 | Development: any tuning, threshold sweeps, question changes |
| `gen-v0.1-holdout` | 2 | 1000 | 264 / 279 / 457 | Final reporting only |

**Tune only on dev.** Do not change questions, thresholds, or the generator after looking at
holdout results. Run the holdout once per frozen configuration and report what it says.

```bash
uv run relay generate --count 400  --seed 1 --dataset-id gen-v0.1-dev     --out evals/generated/gen-v0.1-dev
uv run relay generate --count 1000 --seed 2 --dataset-id gen-v0.1-holdout --out evals/generated/gen-v0.1-holdout
uv run relay generate --verify evals/generated/manifests/gen-v0.1-dev.json --out evals/generated/gen-v0.1-dev
uv run relay eval --dataset evals/generated/gen-v0.1-dev --provider groundtruth   # pipeline validation only
```

The case folders are git-ignored. After cloning, regenerate them with the commands above.
Committed manifests in [`evals/generated/manifests/`](evals/generated/manifests/) record the
seed, count, generator version, label and action counts, and a dataset hash. `--verify` regenerates
the dataset in a temporary directory and compares it with the manifest. It also checks the files in
`--out` if they exist, and exits 2 on any mismatch. Any change to generator output requires bumping
`GENERATOR_VERSION` in `relay/generation/facts.py` and generating new, newly named datasets.

## Limitations

- Ten hand-written smoke cases plus template-generated dev and holdout sets. Generated wording
  comes from fixed phrase banks, so it exercises the policy logic and pipeline, not real-world
  document variety. No gold set, calibration analysis, or baselines yet (Phase 2B–2D).
- Date parts are treated as independent when composing step therapy, which is an approximation.
- Dates without a stated year count as unknown, so they reduce automation instead of being guessed.
- Actions are simulated. Relay never submits anything anywhere.

## Project docs

- [Project handoff](docs/RELAY_PROJECT_HANDOFF.md)
- [v0.1 design spec](docs/superpowers/specs/2026-09-24-relay-v0.1-milestone-design.md)
- [v0.1 implementation plan](docs/superpowers/plans/2026-09-24-relay-v0.1-milestone.md)
- [Phase 2A case generator design](docs/superpowers/specs/2026-09-25-phase2a-case-generator-design.md)
- [Phase 2A implementation plan](docs/superpowers/plans/2026-09-25-phase2a-case-generator.md)
