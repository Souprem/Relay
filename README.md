# Relay

[![CI](https://github.com/Souprem/Relay/actions/workflows/ci.yml/badge.svg)](https://github.com/Souprem/Relay/actions/workflows/ci.yml)

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
cp .env.example .env   # then set TYPESAFE_API_KEY (Jev) and ANTHROPIC_API_KEY (Claude baseline)
```

## Commands

```bash
uv run pytest                                                     # unit + integration (no network)
uv run pytest -m live                                             # one real Jev call and one real Claude call (a few cents)
uv run relay run  --dataset evals/smoke --provider jev --policy v0.1
uv run relay eval --dataset evals/smoke --provider jev --policy v0.1
uv run relay eval --dataset evals/smoke --traces traces/<run_id>.jsonl   # re-score, no API calls
uv run relay eval --dataset evals/smoke --provider groundtruth           # pipeline validation only
uv run relay eval --dataset evals/smoke --provider rules                 # rules-only baseline, no key
uv run relay eval --dataset evals/smoke --provider claude                # Claude LLM baseline, sync (ANTHROPIC_API_KEY; spends money)
uv run relay eval --dataset <dir> --provider claude --mode batch         # Message Batches: half price, no latency
uv run relay eval --dataset <dir> --provider claude --limit 100 --sample-seed 7   # deterministic subsample
uv run relay eval --dataset evals/smoke --provider jev --questions q-v0.1      # pick a question set (jev only; an error with other providers)
uv run relay sweep   --dataset <dir> --traces <file>                            # threshold frontier, no API calls
uv run relay report  --dataset <dir> --traces <file> [--at 0.95]                 # report bundle, no API calls
uv run relay compare --dataset <dir> --traces <a> --traces <b> [--labels a,b]    # side-by-side runs, no API calls
uv run relay replay CASE_ID --traces <file> --dataset <dir> [--at 0.9]           # one case beside a candidate (see "Replay")
uv run relay regression --dataset <dir> --baseline <file> --candidate-at 0.9     # run-level regression gate (see "Regression gate")
uv run relay regression --config evals/regression/gates.json                    # every committed gate, as CI runs them
uv run relay run --dataset <dir> --workflow simulated --from-traces <file> [--at X]    # the incumbent: actions become simulated case status (see "Shadow mode")
uv run relay run --dataset <dir> --workflow shadow --from-traces <file> --incumbent <file>   # a shadow candidate: proposals recorded, never applied; PROMOTE/HOLD
uv run relay budget show --ledger results/claude-spend.json                     # Claude spend ledger entries and totals
uv run relay generate --generator gen-v0.3 [--policy v0.2] --count N --seed S --dataset-id ID --out DIR   # gen-v0.3: interrupted and old courses
uv run relay eval --dataset <dir> --provider jev --questions q-v0.3 --jev-budget-usd 1.00 --jev-ledger <abs path>   # Jev spend counter: estimate first, refuse over the cap
uv run relay recompose --traces <jev file> --dataset <dir> --policy immunara-v0.1 --out <dir>   # stored Jev answers recomposed under a policy (offline)
uv run relay ablate --traces <file> --dataset <dir> --disable contradiction[,missing_evidence] [--at X] --out <dir>   # engine gates disabled, as a simulated run (offline; see "Gate ablation")
uv run relay bench --dataset <dir> --limit 40 --sample-seed 11 --sizes 1,5,10,20 --jev-budget-usd 1.00   # latency vs questions per call (paid)
```

`relay run` writes `traces/<run_id>.jsonl` and `reports/<run_id>.md`, a per-case explanation
covering the documents, decisions, step-therapy derivation, gates, and action. `relay eval` also
writes `results/<run_id>.json`.

`--provider claude` costs real money, so every Claude run passes a budget guard first. The CLI
projects the run's cost from the **maximum** measured cost per case among the ledger's own settled
runs of the same mode (sync or batch — batch is no longer derived from sync × 0.5), times a 1.25
safety margin, times the case count; entries settled at $0 (superseded/re-attached/canceled
bookkeeping) don't count as evidence. A max with a margin is used instead of a mean because
real per-case cost varies noticeably between runs, and a mean can under-estimate. Before any such
entry exists for a mode, a pessimistic prior is used instead: the full input price for every input
token (no cache-read discount) plus the output price, at that mode's price (half for batch). The
guard exits 2 if the ledger's spend plus the projection exceeds `--budget-usd` (default 10). The
ledger is `results/claude-spend.json` (`--ledger`) — pass an **absolute path** if you'll invoke
`relay` from more than one working directory, since a relative one resolves against the current
directory each time and a mismatch means the budget guard silently starts from an empty ledger. A
batch run prints its batch id when it submits; if the run is interrupted, re-attach with `--mode
batch --batch-id <id>` rather than paying for a second batch. Re-attaching to a batch id that is
already fully settled in the ledger is refused (nothing left to collect); re-attaching to one still
"reserved" reads its results and settles the real cost.

**Recovering an ambiguous submission.** If a batch submission fails with a connection error, a
timeout or a server error, the request may or may not have reached Anthropic, so its reservation
stays counted against the budget. `relay budget show --ledger PATH` lists every entry with its
status, cost and batch id, and the settled, reserved and total spend. To resolve a stuck
reservation:

1. Check the Console's Batches page for a batch submitted around the run's start time.
2. If the batch exists, re-attach with `--mode batch --batch-id <id>`. This collects its results
   and settles the real cost.
3. Otherwise, release the reservation: `relay budget release RUN_ID --ledger PATH --reason
   "why" --yes`. This settles the entry at $0 and stores the reason as the entry's `note`. It
   first backs the ledger up to `<ledger>.bak-<UTC timestamp>`. It refuses a settled entry, an
   unknown run, and an entry that carries a batch id (re-attach instead; `--force-batch`
   overrides this only for a batch you know never ran).

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

`relay generate` produces seeded synthetic cases (generator `gen-v0.2`) in the same case-folder
format as the smoke set. Case `i` of a dataset uses seed `seed * 1_000_000 + i`, and difficulty
rotates easy → medium → hard → adversarial, so each class is exactly a quarter of the dataset.
Ground truth records what the rendered documents establish under `immunara-v0.1`. Month-only
dates are judged conservatively (latest possible start, earliest possible end). Their qualifiers
never contradict that rule: a start may read "late March 2026" and an end "early June 2026", and
there is no "around". The generator doesn't write dates without a year. Expected actions are
derived by the engine, as for the smoke cases.

| Dataset | Seed | Cases | Expected actions (auto / request info / review) | Use |
|---|---|---|---|---|
| `gen-v0.2-dev` | 1 | 400 | 106 / 96 / 198 | Development: any tuning, threshold sweeps, question changes |
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

**Tune only on dev.** Do not change questions, thresholds, or the generator after looking at
holdout results. Run the holdout once per frozen configuration and report what it says.

```bash
uv run relay generate --count 400  --seed 1 --dataset-id gen-v0.2-dev     --out evals/generated/gen-v0.2-dev
uv run relay generate --count 1000 --seed 2 --dataset-id gen-v0.2-holdout --out evals/generated/gen-v0.2-holdout
uv run relay generate --verify evals/generated/manifests/gen-v0.2-dev.json --out evals/generated/gen-v0.2-dev
uv run relay eval --dataset evals/generated/gen-v0.2-dev --provider groundtruth   # pipeline validation only
```

The case folders are git-ignored. After cloning, regenerate them with the commands above (run
from the repository root: the manifest directory defaults to the relative path
`evals/generated/manifests`). Committed manifests in
[`evals/generated/manifests/`](evals/generated/manifests/) record the seed, count, generator
version, label and action counts, and a dataset hash. `relay generate` refuses to overwrite an
existing manifest unless you pass `--force`. `--verify` regenerates the dataset in a temporary
directory and compares it with the manifest. With `--out` it also checks the files there (a missing
`--out` directory is an error). It exits 2 on any mismatch. Any change to generator output requires
bumping `GENERATOR_VERSION` in `relay/generation/facts.py` and generating new, newly named
datasets. `gen-v0.2` replaced `gen-v0.1` before any model results were recorded. The changes are
listed in the [2A spec](docs/superpowers/specs/2026-09-25-phase2a-case-generator-design.md).

## Evaluation

Phase 2B analyses stored traces offline: per-decision calibration (five reliability bins over
[0.5, 1.0], plus [0.0, 0.5) for the missing-evidence choice; Brier score; ECE), confusion
matrices, an automation/safety frontier that re-runs the engine on the stored decisions with
`auto_process` swept from 0.50 to 0.99, and run comparison. None of these commands calls a model.

```bash
uv run relay eval    --dataset evals/generated/gen-v0.2-dev --provider jev --questions q-v0.2
uv run relay sweep   --dataset evals/generated/gen-v0.2-dev --traces traces/<run_id>.jsonl [--ceiling 0.01] [--at 0.95]
uv run relay report  --dataset evals/generated/gen-v0.2-holdout --traces <file>.jsonl.gz --at <t>
uv run relay compare --dataset evals/generated/gen-v0.2-dev --traces A.jsonl --traces B.jsonl --labels q-v0.1,q-v0.2
```

`report` writes `summary.json`, `calibration.json`, `calibration.csv`, `frontier.csv`,
`confusion.json` and `report.md`. Traces may be `.jsonl` or `.jsonl.gz`.

**Protocol.** Everything was decided on `gen-v0.2-dev`; `gen-v0.2-holdout` was run once, afterwards.

1. Question sets `q-v0.1` and `q-v0.2` (which counts "never took methotrexate" as documented
   treatment history) both ran on dev. Rule, fixed in advance: adopt `q-v0.2` iff its
   correct-action rate is ≥ q-v0.1's and its unsafe-automation count is ≤ q-v0.1's.
2. The adopted dev run was swept. Rule, fixed in advance: take the highest automation rate among
   thresholds with at least one `AUTO_PROCESS` and an unsafe automation rate ≤ 1%; ties go to the
   higher threshold; if nothing qualifies, select nothing.
3. Holdout ran once with the adopted question set and was reported at the dev-selected threshold
   (`--at`), with calibration measured on holdout.

**Results** (Jev `jev-1.13.0`, policy `v0.1`; all runs committed under
[`evals/baselines/`](evals/baselines/)). The **Correct action**, **Automation**, and **Unsafe /
auto** columns are computed at each run's own recorded thresholds (policy `v0.1`, `auto_process`
0.95 by default) — not at the dev-chosen threshold — which is why the holdout row's 81.5% differs
from the 89.5% in the `--at` table further down:

| Dataset | Questions | Run | Correct action | Automation | Unsafe / auto | Invalid | Selected (in-sample) | At `--at` | Cost |
|---|---|---|---|---|---|---|---|---|---|
| `gen-v0.2-dev` | `q-v0.1` | `run_20260925T071157Z_d6b218` | 257/400 (64.2%) | 29/400 (7.2%) | 0/29 (0.0%) | 0 | 0.87 (auto 99/400 (24.8%), unsafe 0) | none | $0.0442 |
| `gen-v0.2-dev` | `q-v0.2` | `run_20260925T071231Z_6f0b73` | 330/400 (82.5%) | 64/400 (16.0%) | 0/64 (0.0%) | 0 | 0.89 (auto 99/400 (24.8%), unsafe 0) | none | $0.0448 |
| `gen-v0.2-holdout` | `q-v0.2` | `run_20260925T075242Z_fd455f` | 815/1000 (81.5%) | 172/1000 (17.2%) | 0/172 (0.0%) | 0 | 0.91 (auto 252/1000 (25.2%), unsafe 0) | 0.89 (auto 252/1000 (25.2%), unsafe 0) | $0.1120 |

Total estimated cost of these runs: $0.2010

**Caveats.**

- The UAR ceiling never actually binds on these datasets: unsafe automation rate is 0 at every
  swept threshold from 0.50 to 0.97 (and nothing automates at 0.98–0.99) in all three committed
  frontiers ([dev q-v0.1](evals/baselines/gen-v0.2-dev/run_20260925T071157Z_d6b218/report/frontier.csv),
  [dev q-v0.2](evals/baselines/gen-v0.2-dev/run_20260925T071231Z_6f0b73/frontier.csv),
  [holdout](evals/baselines/gen-v0.2-holdout/run_20260925T075242Z_fd455f/frontier.csv)). So the
  selected threshold t\* is really the automation-plateau tie-break (the highest threshold with
  the same automation as the plateau), not a point where the 1% safety ceiling excluded anything.
  The sweep shows the automation cost of raising `auto_process`, not a safety trade-off; on these
  runs, unsafe automation is being prevented upstream, most likely by the contradiction and
  documentation gates rather than by `auto_process` itself (inferred from the gate order, not
  measured directly here).
- Small-n uncertainty: holdout saw 0 unsafe automations out of 252 (exact one-sided 95% upper
  bound on the true rate ≈ 1.18%, from 1 − 0.05^(1/n)); the dev threshold selection itself rests on
  0 unsafe out of 99 automated cases (≈ 2.98% upper bound). "Within the 1% ceiling" above is a point
  estimate (0.0%), not a statistical guarantee at this sample size.
- Part of q-v0.2's measured gain over q-v0.1 is alignment with the generator's own labelling
  convention — gen-v0.2's ground truth counts a record stating the patient never took
  methotrexate as documented treatment history, and q-v0.2's question wording says so explicitly
  (§6 of the [design spec](docs/superpowers/specs/2026-09-25-phase2b-evaluation-depth-design.md))
  — not solely because Jev reads the same evidence more accurately under q-v0.2.

**Question set.** Adoption on dev:

```text
Adoption rule (spec §6, dev only): adopt q-v0.2 iff its correct-action rate >= q-v0.1's
and its unsafe-automation count <= q-v0.1's.
  q-v0.1: run run_20260925T071157Z_d6b218 correct 257/400 (0.6425), unsafe 0
  q-v0.2: run run_20260925T071231Z_6f0b73 correct 330/400 (0.8250), unsafe 0
DECISION: ADOPT q-v0.2
```

`q-v0.2` was adopted: its correct-action rate (330/400, 82.5%) is above q-v0.1's (257/400, 64.2%)
and its unsafe-automation count (0) is no worse than q-v0.1's (0), so both legs of the rule pass.
[`compare-q-v0.1-vs-q-v0.2.txt`](evals/baselines/gen-v0.2-dev/compare-q-v0.1-vs-q-v0.2.txt) shows
73 action differences between the two question sets, 0 of which are new unsafe automations.

**Operating point (dev).** Selected operating point: auto_process >= 0.89 (automation 24.8%, UAR
0/99, correct action 91.2%; ceiling UAR <= 1.0%)

**Holdout at the dev-chosen threshold.** Full report:
[`report.md`](evals/baselines/gen-v0.2-holdout/run_20260925T075242Z_fd455f/report/report.md).

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.89 | 252 | 25.2% | 0/252 (0.0%) | 43.5% | 89.5% | --at |

0 of 252 automated cases were unsafe (0.0%), within the 1% ceiling chosen on dev.

**Calibration on holdout:**

| Decision | n | Brier | ECE |
|---|---|---|---|
| diagnosis_support | 1000 | 0.001 | 0.029 |
| step_therapy | 1000 | 0.011 | 0.022 |
| documentation_complete | 1000 | 0.032 | 0.075 |
| material_contradiction | 1000 | 0.030 | 0.121 |
| missing_evidence | 1000 | 0.212 | 0.078 |

Per-decision ECE on holdout ranges from 0.022 (`step_therapy`) to 0.121 (`material_contradiction`),
the highest of the five; unlike the other decisions, `material_contradiction`'s gap runs entirely in
the conservative direction — accuracy exceeds confidence in every one of its bins, i.e.
under-confidence rather than over-confidence. `step_therapy` has four of its five non-empty
confidence bins flagged low-n (fewer than 20 predictions); `diagnosis_support` has only three
non-empty bins to begin with (n=1, 8, 991), two of which are low-n. In both cases most of the
reliability curve besides the dominant [0.9, 1.0] bin is not statistically meaningful;
`material_contradiction` and `missing_evidence`, by contrast, have enough mass in every
mid-confidence bin to read the curve. There were 0 invalid outputs on the full 1000-case holdout.
Unexpectedly, `documentation_complete` is overconfident rather than underconfident in its
low-confidence bins: at mean confidence 0.643 its actual accuracy is only 0.314 (gap −0.329, n=35)
— the largest gap among bins with n >= 20. The largest gap of any bin in this run is actually a
low-n `documentation_complete` bin, [0.7, 0.8) at −0.402 (n=18).

These are template-generated synthetic cases scored against the generator's own ground truth,
so they show how the pipeline and thresholds behave on this distribution, not real-world accuracy.

### Baselines

**Rules-only baseline** (`--provider rules`, `rules-v0.1`,
[`relay/decisions/rules_baseline.py`](relay/decisions/rules_baseline.py)). A deterministic,
network-free provider turns explicit cues into the same five decisions: day-precision dates, fixed
phrases such as "never tried methotrexate" or "inadequate response", and the member-ID field. The
same policy engine and thresholds as Jev then decide the action. It reads `CaseInput` only, ignores
lines about relatives, and uses the fax cover only for the member-ID check. Its patterns are the
[2C spec](docs/superpowers/specs/2026-09-25-phase2c-rules-baseline-design.md)'s §3, fixed before
any rules run. Nothing was tuned after seeing results.

Those §3 patterns were written by someone who had already read the generator's phrase banks in
[`relay/generation/render.py`](relay/generation/render.py): the diagnosis negators
(`pending|suspected|not yet established|differential|...`) are the generator's own
pending-diagnosis vocabulary; the member-ID-missing pattern matches the generator's exact
`MEMBER_ID_MISSING` string verbatim; the ongoing/response cues ("continues", "remains on",
"ongoing", "inadequate response", "nausea", "side effect") are drawn from its treatment-outcome
templates; and the relative list is the generator's own relatives (mother, father, sister,
brother, aunt) plus uncle and grandparents, and also matches its "family history" phrasing. This
is template fit to gen-v0.2, not label leakage: the rules never read a case's or document's ID, a
dataset ID, or document ordering — only structured fields (`insurance.member_id`), a document's
declared `kind`, and its text.

Every rules probability is 0, 0.5 (abstain) or 1, so the rules are not calibrated and their
automation/safety **frontier is flat**: `auto_process` has no effect anywhere from 0.50 to 0.99.
`relay sweep` and `relay report` print `Frontier is flat across all thresholds.`, and every
rules `sweep.json` records `"frontier_flat": true`. The rules' "dev-selected" threshold
(0.99) is therefore only the selection rule's tie-break, not a tuned operating
point, and any threshold gives the same rules row.

```bash
uv run relay eval --dataset evals/generated/gen-v0.2-holdout --provider rules    # no key, no network
uv run relay compare --dataset evals/generated/gen-v0.2-holdout --traces <jev>.jsonl.gz --traces <rules>.jsonl.gz --labels jev-q-v0.2,rules-v0.1
```

**Rules vs Jev on `gen-v0.2-holdout`** (n=1000, policy `v0.1`):

| Provider | Run | `auto_process` | Correct action | Automation | Unsafe / auto (UAR) | Request info | Human review | Frontier flat |
|---|---|---|---|---|---|---|---|---|
| Jev `q-v0.2` | `run_20260925T075242Z_fd455f` | 0.95 (recorded) | 815/1000 (81.5%) | 172/1000 (17.2%) | 0/172 (0.0%) | 313/1000 (31.3%) | 515/1000 (51.5%) | no |
| Jev `q-v0.2` | `run_20260925T075242Z_fd455f` | 0.89 (dev-selected, `--at`) | 895/1000 (89.5%) | 252/1000 (25.2%) | 0/252 (0.0%) | 313/1000 (31.3%) | 435/1000 (43.5%) | no |
| Rules `rules-v0.1` | `run_20260925T092425Z_0aee97` | 0.95 (recorded) | 667/1000 (66.7%) | 134/1000 (13.4%) | 0/134 (0.0%) | 569/1000 (56.9%) | 297/1000 (29.7%) | yes |
| Rules `rules-v0.1` | `run_20260925T092425Z_0aee97` | 0.99 (dev-selected, `--at`) | 667/1000 (66.7%) | 134/1000 (13.4%) | 0/134 (0.0%) | 569/1000 (56.9%) | 297/1000 (29.7%) | yes |

Jev has both the higher correct-action rate (81.5% vs. 66.7% at the recorded 0.95 threshold) and the
higher automation rate (17.2% vs. 13.4%); neither provider has any unsafe automation on this
holdout (Jev 0/172, rules 0/134). Where the rules do not automate, they lean toward asking for more
documentation rather than escalating to a person: request-info is 56.9% for the rules against 31.3%
for Jev, while human review is 29.7% for the rules against 51.5% for Jev. Rules automate less than
Jev but just as safely — on the templates their patterns were written against. `compare-jev-vs-rules.txt`
puts the action-level disagreement at "Action differences jev-q-v0.2 -> rules-v0.1: 416 cases (0 new
unsafe automations)".

The holdout confusion matrices back that qualifier up: four of the five decisions
(`diagnosis_support`, `step_therapy`, `documentation_complete`, `missing_evidence`) never commit to
a confidently wrong answer on this holdout — the rules either match ground truth or abstain
(`p=0.5`, routed to `REQUEST_INFO`/`HUMAN_REVIEW`), never a confidently wrong `p=0` or `p=1`. Only
`material_contradiction` commits wrong answers, and even there it has zero false positives (0/881
`no`-truth cases predicted `yes`); every one of its 26 misses on this holdout turns out to use a
"never taken" phrasing outside `mtx_never`'s pattern list (e.g. "never been prescribed" rather than
"never tried/taken/took/received"). The rules' better `material_contradiction` calibration than Jev
on this holdout (Brier 0.026 / ECE 0.026 vs. Jev's 0.030 / 0.121) reflects that template fit, not a
general reasoning advantage over Jev.

The rules see only explicit conflicts and fixed phrasings. Wording outside their pattern lists
makes them abstain (usually `REQUEST_INFO`), and a contradiction they cannot see as an explicit
cue stays at 0. Both are documented weaknesses of a pattern floor, not things to tune away. The
rules do not key on generator IDs or document structure beyond a document's declared `kind`, so
that pattern floor is fit to gen-v0.2's fixed wording, not to anything about how the dataset is
generated or organized. `tests/unit/test_rules_anti_shortcut.py` checks that the rules do not key
on gen-v0.2's residual contradiction tell (see Limitations).

Artifacts: smoke
[`run_20260925T092347Z_cca17f`](evals/baselines/smoke-v0.1/run_20260925T092347Z_cca17f/), dev
[`run_20260925T092358Z_36888d`](evals/baselines/gen-v0.2-dev/run_20260925T092358Z_36888d/) (with
[`compare-jev-vs-rules.txt`](evals/baselines/gen-v0.2-dev/compare-jev-vs-rules.txt)), holdout
[`run_20260925T092425Z_0aee97`](evals/baselines/gen-v0.2-holdout/run_20260925T092425Z_0aee97/) (full
[`report.md`](evals/baselines/gen-v0.2-holdout/run_20260925T092425Z_0aee97/report/report.md)).

**Conventional LLM baseline** (`--provider claude`, `claude-opus-5`,
[`relay/decisions/claude.py`](relay/decisions/claude.py)). One structured-output request per case
asks Claude the same 12 questions as Jev, rendered from the same `build_questions()` q-v0.2
definitions ([`claude_prompt.py`](relay/decisions/claude_prompt.py); question set
`q-v0.2+claude-prompt-v1`). Each yes/no answer is a self-reported `p_yes`, each date-part or status
answer is an option plus its probability (the leftover mass counts for no option), and
`missing_evidence` is a six-label distribution normalized in code. The answers go through the same
composition code, step-therapy date arithmetic, policy engine and thresholds as Jev, so the
judgment source is the only thing that differs: Jev's native probabilities against an LLM's
verbalized confidence. Adaptive thinking is left at the model default, with `effort` `low` and
`max_tokens` 4096. Dev ran on the Message Batches API at half price; Claude's operating point was
chosen on dev with the same rule as Jev's, and the prompt, schema and code were frozen before any
Claude run. Nothing was tuned after seeing results.

**Refusal fallbacks are deliberately disabled.** The claude-api default would add a server-side
fallback model for refused requests. It is not used here for two reasons: the Batches API rejects
the `fallbacks` parameter, and a silent switch to another model would change what this baseline
measures. A refusal (or a reply cut off at `max_tokens`) becomes an invalid bundle, which the
engine routes to `HUMAN_REVIEW`, and refusals are counted below: zero, across all 660 Claude cases
run (10 smoke, 400 dev, 150 holdout sample, and 100 gold).

**Budget.** All of Phase 2D and 2E's Claude spend is capped at $10 (tightened mid-run from the
sub-project's original $60 guard by an explicit user decision), tracked in
[`claude-spend.json`](evals/baselines/claude-spend.json); the pre-bulk-run projection (made after
the smoke run, under the original $60 guard, before the cap was tightened) is in
[`claude-projection.txt`](evals/baselines/claude-projection.txt). Under the $10 cap, only dev (400
cases, the full set) and a deterministic 150-case sample of holdout (`--limit 150 --sample-seed
7`) were run; the full 1,000-case holdout and a dedicated sync latency sample were not run, so
latency below comes from the 10-case smoke sync run only (already a low-sample figure). The gold
set (`gold-v0.1`) ran separately, after this task, against its own reserved headroom; see below and
"Gold set" further down for the actual numbers.

```bash
uv run relay eval --dataset evals/generated/gen-v0.2-dev --provider claude --mode batch --budget-usd 10
uv run relay eval --dataset evals/generated/gen-v0.2-holdout --provider claude --mode batch --limit 150 --sample-seed 7 --budget-usd 10
uv run relay compare --dataset evals/generated/gen-v0.2-holdout --traces <jev-sample>.jsonl --traces <rules-sample>.jsonl --traces <claude-sample>.jsonl.gz --labels jev-q-v0.2,rules-v0.1,claude-opus-5
```

**Jev vs rules vs Claude on `gen-v0.2-dev`** (n=400, full dev set, policy `v0.1`; each provider's
`--at` row uses its own dev-selected threshold). Claude's correct-action rate is 288/400 (72.0%)
at the recorded `auto_process >= 0.95` threshold, against Jev's 330/400 (82.5%) and the rules'
261/400 (65.2%); at 0.95 Claude never automates (0/400), against Jev 64/400 (16.0%) and rules
56/400 (14.0%) — none of the three have any unsafe automation at 0.95. Claude's own dev sweep
selects a much lower operating point, `auto_process >= 0.55` (`T_CLAUDE`): 106/400 (26.5%)
automation, 0/106 unsafe (one-sided 95% upper bound on the true rate ≈2.79%, small-n), 394/400
(98.5%) correct action, 94/400 (23.5%) request-info, 200/400 (50.0%) human review. Full compare:
[`compare-jev-rules-claude.txt`](evals/baselines/gen-v0.2-dev/compare-jev-rules-claude.txt), which
puts the action-level disagreement at "Action differences jev-q-v0.2 -> claude-opus-5: 96 cases (0
new unsafe automations)".

The dev batch was not a clean single run: the original submission
(`msgbatch_01SpuLJxsxtaXJ8W2YPps8Tf`) stalled and was cancelled by the controller after roughly 5.7
hours with `succeeded=378, canceled=22`; the 378 completed bundles were collected at no extra cost,
the 22 canceled case ids were re-run as a second, much smaller batch
(`msgbatch_012TiAgwjfKK8DGZKdvhv5Hm`, $0.274699), and the two runs were combined into one 400-case
trace by [`scripts/combine_claude_dev.py`](scripts/combine_claude_dev.py) (committed, documented,
provenance recorded in the combined run's manifest). The combined dev run has 0 invalid outputs and
0 refusals; nothing about the prompt, schema or thresholds changed between the two batches.

**Claude's step-therapy probability is a structural lower bound under this design.** `step_therapy`
is composed in code from up to seven of Claude's own sub-answers (three date parts for the
treatment start, one end-status plus three date parts for the end, then multiplied again by
`mtx_inadequate_response`; [`relay/decisions/composition.py`](relay/decisions/composition.py),
[`step_therapy.py`](relay/decisions/step_therapy.py)). Every one of those sub-answers is a single
stated option plus a probability, with the leftover mass unassigned (2D spec L4), so the composed
`p_yes` is a product of several same-or-below-1 confidences — even fully accurate per-answer
confidences well above 0.9 compound down multiplicatively. This is a mechanism shared with Jev's
composition code, but it bites Claude harder because its self-reported per-answer confidences are
less peaked than Jev's native probabilities. As a descriptive diagnostic (no retuning): on dev, all
400/400 of Claude's `step_therapy` values fall below the 0.95 auto-process bar, and 246/400 (61.5%)
of those would clear it if the date-part and end-status sub-answers had been stated with full
certainty (i.e. `mtx_inadequate_response`'s own probability alone already reads >= 0.95); on the
holdout sample the same figures are 150/150 below 0.95, 99/150 (66.0%) attributable to this
composition effect rather than to low confidence that treatment was inadequate. This depresses both
Claude's step-therapy calibration (see below) and its automation rate at any fixed threshold.

**Jev vs rules vs Claude on `gen-v0.2-holdout`** (n=150, a deterministic sample —
`--limit 150 --sample-seed 7` — not the full 1,000-case holdout, because of the $10 API budget
above; policy `v0.1`; each provider's `--at` row uses its own dev-selected threshold; Jev and rules
are the same committed full-holdout traces restricted, offline, to this run's 150 case ids via
[`scripts/filter_traces_by_sample.py`](scripts/filter_traces_by_sample.py) — no new provider
calls):

| Provider | Run | `auto_process` | Correct action | Automation | Unsafe / auto (UAR) | Request info | Human review | Frontier flat |
|---|---|---|---|---|---|---|---|---|
| Jev `q-v0.2` | `run_20260925T212314Z_e49268` | 0.95 (recorded) | 125/150 (83.3%) | 23/150 (15.3%) | 0/23 (0.0%) | 55/150 (36.7%) | 72/150 (48.0%) | no |
| Jev `q-v0.2` | `run_20260925T212314Z_e49268` | 0.89 (dev-selected, `--at`) | 138/150 (92.0%) | 36/150 (24.0%) | 0/36 (0.0%) | 55/150 (36.7%) | 59/150 (39.3%) | no |
| Rules `rules-v0.1` | `run_20260925T212314Z_4b67b1` | 0.95 (recorded) | 102/150 (68.0%) | 20/150 (13.3%) | 0/20 (0.0%) | 92/150 (61.3%) | 38/150 (25.3%) | yes |
| Rules `rules-v0.1` | `run_20260925T212314Z_4b67b1` | 0.99 (dev-selected, `--at`) | 102/150 (68.0%) | 20/150 (13.3%) | 0/20 (0.0%) | 92/150 (61.3%) | 38/150 (25.3%) | yes |
| Claude `claude-opus-5` | `run_20260925T212034Z_bbee49` | 0.95 (recorded) | 110/150 (73.3%) | 0/150 (0.0%) | n/a | 47/150 (31.3%) | 103/150 (68.7%) | no |
| Claude `claude-opus-5` | `run_20260925T212034Z_bbee49` | 0.55 (dev-selected, `--at`) | 147/150 (98.0%) | 37/150 (24.7%) | 0/37 (0.0%) | 47/150 (31.3%) | 66/150 (44.0%) | no |

Small-n UAR upper bounds (one-sided 95%, from 1 − 0.05^(1/n) on 0 observed unsafe automations): Jev
0/36 ≈7.98%, rules 0/20 ≈13.91%, Claude 0/37 ≈7.78% at their own dev-selected thresholds — none of
these are statistical guarantees at this sample size, only point estimates of 0.0%.

**Calibration on the holdout sample** (Brier / ECE per decision; Claude's confidences are
self-reported):

| Decision | Jev Brier / ECE | Rules Brier / ECE | Claude Brier / ECE |
|---|---|---|---|
| diagnosis_support | 0.002 / 0.032 | 0.017 / 0.033 | 0.002 / 0.041 |
| step_therapy | 0.019 / 0.035 | 0.122 / 0.097 | 0.027 / 0.101 |
| documentation_complete | 0.045 / 0.096 | 0.098 / 0.123 | 0.044 / 0.029 |
| material_contradiction | 0.031 / 0.127 | 0.000 / 0.000 | 0.002 / 0.041 |
| missing_evidence | 0.169 / 0.102 | 0.172 / 0.123 | 0.083 / 0.137 |

**Multiclass Brier comparability.** Claude's `missing_evidence` answer is always the full six-label
distribution requested by the schema, normalized in code, so it has 0/150 partial distributions on
this sample; its other choice answers (the date parts and end-status) are single-answer +
probability, with the rest counted as unassigned mass, and are not scored as multiclass
distributions. Jev returns full distributions for every choice question. On this sample Jev has
4/150 partial `missing_evidence` distributions (mass on no label, which reads as 0 on every label
in the Brier score) and rules has 59/150 — so Jev's and Claude's `missing_evidence` Brier/ECE numbers
above are close to comparable (Jev's small partial share does not distort the comparison much), but
rules' is not (nearly 40% partial). Every other row compares full distributions to full
distributions, or single yes/no probabilities to single yes/no probabilities, and is directly
comparable across all three providers.

Claude's Brier is better than Jev's on `material_contradiction` (0.002 vs 0.031) and
`missing_evidence` (0.083 vs 0.169), about tied on `documentation_complete` (0.044 vs 0.045) and
`diagnosis_support` (0.002 vs 0.002), and worse on `step_therapy` (0.027 vs 0.019) — consistent with
the structural composition effect above. Claude's ECE is worse than Jev's on `diagnosis_support`,
`step_therapy` and `missing_evidence`, and better on `documentation_complete` and
`material_contradiction`; self-reported verbalized confidence is not uniformly better- or
worse-calibrated than Jev's native probabilities, it varies by decision.

**Claude runs: latency, cost, refusals, caching** (latency from the 10-case smoke sync run only —
no dedicated sync latency sample was run under the $10 cap, so this is already a low-sample figure;
batch has no latency at all; cost at list prices as of 2026-09-25, batch at half price):

| Claude run | Mode | n | Latency p50 / p95 | Cost per case | Cost per 1k cases | Refusals | Invalid | Prompt cache reads |
|---|---|---|---|---|---|---|---|---|
| smoke (`run_20260925T131052Z_f328de`) | sync | 10 | 5169 / 6781 ms | $0.02547 | $25.47 | 0 | 0 | 50.7% |
| dev (`run_20260925T191752Z_288946`) | batch | 400 | unavailable (batch) | $0.01100 | $11.00 | 0 | 0 | 65.5% |
| holdout sample (150, seed 7) (`run_20260925T212034Z_bbee49`) | batch | 150 | unavailable (batch) | $0.01637 | $16.37 | 0 | 0 | 29.6% |

Total Claude spend (ledger): $7.1500 across the first 8 entries (three are $0 bookkeeping entries:
two from recovering the interrupted dev batch — one settles the original, superseded reservation to
zero, one settles a stray $0 reservation left by a killed re-attach — and one a superseded holdout
reservation; none reflects real spend); unsettled reservations: none. Remaining headroom under the
$10 cap after this task: $2.8500, against an estimated gold-set (Phase 2E, 100 cases) reserve of
roughly $1.36 (100 × the measured dev batch cost/case of $0.01091 × a 1.25 safety margin). The gold
run has since happened (10 ledger entries after the gold run): it actually cost $1.560455, about
14% above that $1.36 estimate though still well under the printed $2.0468 projection (see "Gold
set" below), bringing total Claude spend to $8.710495 of the
$10 cap.

Claude's sync latency (smoke, n=10, low-sample) is far higher than Jev's: 5169/6781 ms p50/p95
against Jev's 163/198 ms on the holdout sample — Jev runs locally with no network round trip, so
this is an expected, large gap, not a surprise. Claude's cost per 1,000 cases ($11.00 on dev,
$16.37 on the holdout sample, both batch/half-price) is far higher than Jev's ($0.1119 per 1,000
cases, from the holdout sample's $0.0001119 per case) — Jev has no per-call API cost. The batch cost
projection under-estimated the holdout sample's actual cost: $2.0124 projected (from the
dev-and-smoke-derived sync-cost-per-case × 0.5 batch multiplier) against $2.456215 actually spent,
about 22% higher, mostly explained by the holdout sample's lower observed prompt-cache-read share
(29.6%) than dev's (65.5%) — a lower cache hit rate raises the realized per-token cost above the
projection's flat multiplier, and batch prompt caching is best-effort. All three providers have 0
unsafe automations at their own dev-selected thresholds on this sample (Jev 0/36, rules 0/20,
Claude 0/37); Claude had 0 refusals and 0 invalid outputs across every run. Quoting the holdout
sample compare file: "Action differences jev-q-v0.2 -> claude-opus-5: 33 cases (0 new unsafe
automations)".

The prompt-cache figure is what was observed (`usage.cache_read_input_tokens`), not assumed; cache
hits inside a batch are best-effort. Claude's run is one draw from a nondeterministic model, and
its probabilities are verbalized estimates rather than a model-native distribution.

Artifacts: smoke [`run_20260925T131052Z_f328de`](evals/baselines/smoke-v0.1/run_20260925T131052Z_f328de/),
dev [`run_20260925T191752Z_288946`](evals/baselines/gen-v0.2-dev/run_20260925T191752Z_288946/) (with
[`compare-jev-rules-claude.txt`](evals/baselines/gen-v0.2-dev/compare-jev-rules-claude.txt)),
holdout sample (150, seed 7)
[`run_20260925T212034Z_bbee49`](evals/baselines/gen-v0.2-holdout/run_20260925T212034Z_bbee49/) (full
[`report.md`](evals/baselines/gen-v0.2-holdout/run_20260925T212034Z_bbee49/report/report.md), and
[`compare-jev-rules-claude.txt`](evals/baselines/gen-v0.2-holdout/compare-jev-rules-claude.txt)). The
full 1,000-case holdout and a dedicated sync latency sample were not run (see Budget above).

## Gold set

[`evals/gold/`](evals/gold/) holds `gold-v0.1`: 100 individually written synthetic cases, 20
each of straightforward (STR), missing information (MIS), conflicting evidence (CON), temporal
reasoning (TMP) and tricky/ambiguous (TRK). Their wording and structure are not produced by the
generator, so they test generalization beyond its templates.

> **Provenance.** The cases and labels were written by AI agents (Claude) following
> [`AUTHORING_GUIDE.md`](evals/gold/AUTHORING_GUIDE.md), checked by a blind second labelling pass
> by a separate agent, and adjudicated by a third agent
> ([`ADJUDICATION.md`](evals/gold/ADJUDICATION.md)). They were not written or reviewed by a human
> domain expert. The authors, blind reviewer and adjudicator are all Claude agents, and Claude
> (`claude-opus-5`) is also an evaluated provider below. The 100% agreement reflects one model
> family applying one guide, not independent validation. Claude's gold results may benefit from
> shared interpretation, so a human review matters most for comparisons involving Claude. Have a
> qualified human review them before making any external claim.

Blind second-pass agreement before adjudication: `diagnosis_supported` 100/100 (100.0%),
`step_therapy_satisfied` 100/100 (100.0%), `documentation_complete` 100/100 (100.0%),
`contradiction_present` 100/100 (100.0%), `missing_evidence` 100/100 (100.0%), all five facts
100/100 (100.0%), derived action 100/100 (100.0%). Adjudication summary: 0 disagreements; no
labels or documents were changed.

**Never tune on gold.** Every provider ran on gold exactly once, after each provider's configuration
was frozen on `gen-v0.2-dev` (Jev and rules ran before 2D's final fixes, which do not touch their
code paths), with the configuration chosen on `gen-v0.2-dev`: Jev with question set `q-v0.2`, rules
`rules-v0.1`, and Claude `claude-opus-5` in batch. Each report's `--at` row uses that provider's
dev-selected threshold (Jev 0.89, rules 0.99, Claude 0.55). The ground-truth run is a pipeline
check, not a model result.

**Spend disclosure.** A first submission (`run_20260925T222258Z_91d2e1`) failed with a connection
error during batch upload; the user confirmed in the Anthropic console that no batch was ever
created, so its reservation was released at $0 (the $0.000000 `gold-v0.1` ledger entry) and the run
was resubmitted once, succeeding as `run_20260926T011730Z_f1852f`. The batch cost projection the
CLI prints is now conservative — the maximum observed per-case cost times 1.25, not a mean — which
is why the actual cost ($1.560455) came in well under the printed projection ($2.0468) for 100
cases, albeit about 14% above the Budget section's earlier $1.36 gold-set estimate above.

| Provider | Run | Correct action | Automation | Unsafe / auto | Request info | Review | Invalid | At dev t* (`--at`) | Cost |
|---|---|---|---|---|---|---|---|---|---|
| Ground truth | `run_20260925T170825Z_440df0` | 100/100 (100.0%) | 34/100 (34.0%) | 0/34 | 34/100 (34.0%) | 32/100 (32.0%) | 0 | — | $0.0000 |
| Jev `q-v0.2` | `run_20260925T170857Z_b95be9` | 82/100 (82.0%) | 18/100 (18.0%) | 0/18 | 32/100 (32.0%) | 50/100 (50.0%) | 0 | 0.89: correct 91/100 (91.0%), auto 29/100 (29.0%), unsafe 1 | $0.0115 |
| Rules `rules-v0.1` | `run_20260925T170839Z_d3b427` | 61/100 (61.0%) | 20/100 (20.0%) | 6/20 | 66/100 (66.0%) | 14/100 (14.0%) | 0 | 0.99: correct 61/100 (61.0%), auto 20/100 (20.0%), unsafe 6 | $0.0000 |
| Claude `claude-opus-5` (batch) | `run_20260926T011730Z_f1852f` | 65/100 (65.0%) | 0/100 (0.0%) | 0/0 | 33/100 (33.0%) | 67/100 (67.0%) | 0 | 0.55: correct 93/100 (93.0%), auto 30/100 (30.0%), unsafe 1 | $1.5605 |

Each committed `report/report.md` also prints its own in-sample "Selected operating point" line
(Jev 0.94, Claude 0.56, GT 0.99, from that run's own frontier sweep over gold) and `compare`'s
`Selected` row does the same; these are gold diagnostics only, computed after seeing gold, and are
never used as an operating point. The "At dev t*" column above, from each provider's `gen-v0.2-dev`
sweep, is the only operating point used anywhere in this report.

**Claude's 0% headline automation is the raw run's default threshold, not its dev-selected
operating point.** Every one of Claude's gold `step_therapy` values falls below that bar, for the
structural reason already documented in Baselines above: `step_therapy` is composed in code from
up to seven of Claude's self-reported sub-answer probabilities multiplied together, so even
accurate per-answer confidences compound down well below any individual confidence. At Claude's
dev-selected operating point (`--at 0.55`) gold automation is 30/100 with 1/30 unsafe, shown in the
table's last column; this is the same composition effect on a new, hand-written dataset, not a
new failure mode.

**Per category** (as run, policy `v0.1` thresholds;
[`per-category.md`](evals/baselines/gold-v0.1/per-category.md)):

| Provider | Category | Correct action | Automation | Unsafe / auto | Request info | Review | Invalid |
|---|---|---|---|---|---|---|---|
| Ground truth | STR | 20/20 (100%) | 10/20 (50%) | 0/10 | 10/20 (50%) | 0/20 (0%) | 0 |
| Ground truth | MIS | 20/20 (100%) | 3/20 (15%) | 0/3 | 16/20 (80%) | 1/20 (5%) | 0 |
| Ground truth | CON | 20/20 (100%) | 4/20 (20%) | 0/4 | 1/20 (5%) | 15/20 (75%) | 0 |
| Ground truth | TMP | 20/20 (100%) | 11/20 (55%) | 0/11 | 1/20 (5%) | 8/20 (40%) | 0 |
| Ground truth | TRK | 20/20 (100%) | 6/20 (30%) | 0/6 | 6/20 (30%) | 8/20 (40%) | 0 |
| Ground truth | ALL | 100/100 (100%) | 34/100 (34%) | 0/34 | 34/100 (34%) | 32/100 (32%) | 0 |
| Jev q-v0.2 | STR | 16/20 (80%) | 6/20 (30%) | 0/6 | 10/20 (50%) | 4/20 (20%) | 0 |
| Jev q-v0.2 | MIS | 18/20 (90%) | 1/20 (5%) | 0/1 | 16/20 (80%) | 3/20 (15%) | 0 |
| Jev q-v0.2 | CON | 18/20 (90%) | 2/20 (10%) | 0/2 | 1/20 (5%) | 17/20 (85%) | 0 |
| Jev q-v0.2 | TMP | 12/20 (60%) | 4/20 (20%) | 0/4 | 0/20 (0%) | 16/20 (80%) | 0 |
| Jev q-v0.2 | TRK | 18/20 (90%) | 5/20 (25%) | 0/5 | 5/20 (25%) | 10/20 (50%) | 0 |
| Jev q-v0.2 | ALL | 82/100 (82%) | 18/100 (18%) | 0/18 | 32/100 (32%) | 50/100 (50%) | 0 |
| Rules rules-v0.1 | STR | 17/20 (85%) | 7/20 (35%) | 0/7 | 13/20 (65%) | 0/20 (0%) | 0 |
| Rules rules-v0.1 | MIS | 17/20 (85%) | 0/20 (0%) | 0/0 | 19/20 (95%) | 1/20 (5%) | 0 |
| Rules rules-v0.1 | CON | 8/20 (40%) | 9/20 (45%) | 6/9 | 7/20 (35%) | 4/20 (20%) | 0 |
| Rules rules-v0.1 | TMP | 7/20 (35%) | 2/20 (10%) | 0/2 | 13/20 (65%) | 5/20 (25%) | 0 |
| Rules rules-v0.1 | TRK | 12/20 (60%) | 2/20 (10%) | 0/2 | 14/20 (70%) | 4/20 (20%) | 0 |
| Rules rules-v0.1 | ALL | 61/100 (61%) | 20/100 (20%) | 6/20 | 66/100 (66%) | 14/100 (14%) | 0 |
| Claude claude-opus-5 | STR | 10/20 (50%) | 0/20 (0%) | 0/0 | 10/20 (50%) | 10/20 (50%) | 0 |
| Claude claude-opus-5 | MIS | 17/20 (85%) | 0/20 (0%) | 0/0 | 16/20 (80%) | 4/20 (20%) | 0 |
| Claude claude-opus-5 | CON | 16/20 (80%) | 0/20 (0%) | 0/0 | 1/20 (5%) | 19/20 (95%) | 0 |
| Claude claude-opus-5 | TMP | 8/20 (40%) | 0/20 (0%) | 0/0 | 0/20 (0%) | 20/20 (100%) | 0 |
| Claude claude-opus-5 | TRK | 14/20 (70%) | 0/20 (0%) | 0/0 | 6/20 (30%) | 14/20 (70%) | 0 |
| Claude claude-opus-5 | ALL | 65/100 (65%) | 0/100 (0%) | 0/0 | 33/100 (33%) | 67/100 (67%) | 0 |

Rules had by far the most unsafe automations on gold: all 6 (30% UAR at its own dev-selected
`0.99` threshold; exact 95% Clopper-Pearson interval 11.9%-54.3%) are in CON (6/9 there,
29.9%-92.5%), with 0% UAR in every other category. Jev and Claude have 0 unsafe automations in
this raw (0.95) per-category view but 1 each at their own dev-selected `--at` points (Jev 0.89:
1/29, 0.1%-17.8%; Claude 0.55: 1/30, 0.1%-17.2%) — **and it is the same case for both**:
`GOLD-TMP-17`, an interrupted methotrexate course (2026-01-05 to 2026-02-23 = 49 days, held for
infection, then 2026-03-23 to 2026-05-18 = 56 days; neither segment reaches the policy's twelve
consecutive weeks, so the correct action is `HUMAN_REVIEW`). Both providers reported a single start
and end date (2026-01-05 to 2026-05-18, 133 days) instead, because the `q-v0.2` question set has
one start date and one end date and cannot represent a gap — a shared, structural limitation of the
question set, not two independent mistakes (Phase 3D's `q-v0.3` adds the missing questions; see
"Question set q-v0.3" below). Claude's composed `step_therapy` probability there was
0.5513, just 0.0013 above its 0.55 threshold; Jev's was 0.9316.

TMP is the weakest category by correct-action rate for every model provider — rules 7/20 (35%),
Jev 12/20 (60%), Claude 8/20 (40%) — while ground truth is 100% in every category by construction.
Jev's 91/100 (83.6%-95.8%) and Claude's 93/100 (86.1%-97.1%) correct-action rates at their own
`--at`, and their 29 vs. 30 automations, are not distinguishable at n=100.

On the five TMP cases that hinge on relative or inferable-year dates (`GOLD-TMP-12/13/14/15/16`,
Q3a/b), ground truth calls three (12, 14, 15) `AUTO_PROCESS`. At the recorded 0.95 bar, Jev
auto-processes only TMP-14 and Claude automates none of the five — but Claude automates nothing at
all at 0.95 on this dataset (see "Claude's 0% headline automation" above), so that comparison
reflects the threshold, not the dates specifically. At each provider's own dev threshold, Jev still auto-processes only TMP-14; Claude
auto-processes both TMP-14 and TMP-15. TMP-12 goes to `HUMAN_REVIEW` under both providers at every
threshold shown here, and TMP-16 (truth `REQUEST_INFO`) also goes to `HUMAN_REVIEW` under both —
wrong relative to ground truth, but safe, not an unsafe automation — under `q-v0.2` and Claude.
This no longer holds for `q-v0.3` at its adopted dev threshold of 0.81, where `GOLD-TMP-16`
becomes an unsafe `AUTO_PROCESS` (see "Question set q-v0.3" below).

`compare-jev-rules-claude.txt` computes action differences at each run's recorded 0.95 threshold,
where Claude has 0 `AUTO_PROCESS` actions at all: 6 new unsafe automations across the 47 cases
where jev-q-v0.2 and rules-v0.1 differ; 0 new unsafe automations (trivially, since Claude never
automates at 0.95) across the 19 cases where jev-q-v0.2 and claude-opus-5 differ; and 0 new unsafe
automations across the 53 cases where rules-v0.1 and claude-opus-5 differ, including rules' 6 CON
unsafe automations resolving to `HUMAN_REVIEW` under Claude (6 of those 53 differing cases; the
other 47 are unrelated to those unsafe cases). Computed offline instead from the committed traces
at each provider's own dev-selected `--at`
([`compare-own-thresholds.txt`](evals/baselines/gold-v0.1/compare-own-thresholds.txt)): jev→rules
44 differing cases (6 new unsafe automations), jev→claude 4 differing cases (0 new unsafe
automations), rules→claude 42 differing cases (1 new unsafe automation, `GOLD-TMP-17`, described
above). Claude had 0 refusals and 0 invalid outputs on the 100-case gold batch (refusal fallbacks
are disabled — see Baselines above), at a cost of $1.560455 (total ledger spend $8.710495 of the
$10 Phase 2 cap).

With 20 cases per category, one case is 5 percentage points, so per-category rates are indicative
only. All runs, including gzipped traces, are committed under
[`evals/baselines/gold-v0.1/`](evals/baselines/gold-v0.1/).

## Replay

`relay replay` puts one stored trace beside a candidate outcome for the same case and labels every
difference: judgments, confidence, thresholds, policy, gate path and action. It rebuilds the case
from `--dataset` and checks it against the content hash stored in the trace. If the inputs changed
since the run, it refuses with exit code 2, because replaying altered inputs is not replay.

You pick one candidate source:

- **Reproduce** (the default). The stored decisions go back through today's engine under the
  trace's own policy and thresholds. `REPRODUCED` means today's engine gives the same action,
  reasons and gate path. `ENGINE DRIFT` (exit 3) means it doesn't.
- **Policy replay** (`--policy ID`, `--latest-policy`, `--at X`). The stored decisions under
  another policy or `auto_process` threshold. The label always says the judgments were made against
  the original policy's questions, so a policy replay never looks like a policy-aware re-run.
- **Candidate traces** (`--candidate-traces FILE`). The same case's trace from another run.
- **Live candidate** (`--provider P`). A fresh provider call on the frozen inputs, written as an
  ordinary one-case run under `traces/` so it can itself be replayed later. It needs that
  provider's key. Claude runs sync only and goes through the budget guard.

The expected action is always printed, marked evaluation-only, and derived from ground truth the
same way `relay eval` derives it. Each side is judged `correct`, `wrong-safe` or `UNSAFE`. A
candidate that newly automates a case unsafely is flagged `NEWLY UNSAFE`, and the command exits 4
so scripts can gate on it. `--json` prints the diff as JSON and nothing else. `--all-gates` also
shows the gate rows that didn't change. Only a live candidate calls a provider: the other three
sources need no keys and make no network calls, as the commands below show (run with both keys
unset and no `.env`).

Jev beside Claude on `GOLD-TMP-17`, the interrupted methotrexate course described under "Gold
set", from the committed gold traces:

```text
$ env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env replay GOLD-TMP-17 \
    --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz \
    --dataset evals/gold \
    --candidate-traces evals/baselines/gold-v0.1/run_20260926T011730Z_f1852f/traces.jsonl.gz
Relay replay — GOLD-TMP-17
ORIGINAL run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE candidate trace run_20260926T011730Z_f1852f · claude q-v0.2+claude-prompt-v1
EXPECTED (evaluation-only): HUMAN_REVIEW

   DECISION                ORIGINAL     CANDIDATE    Δ       CROSSED
   diagnosis_support       p_yes=0.980  p_yes=0.970  -0.010
   step_therapy            p_yes=0.932  p_yes=0.551  -0.380
   documentation_complete  p_yes=0.970  p_yes=0.950  -0.020
   material_contradiction  p_yes=0.100  p_yes=0.030  -0.070  (auto_process)
   missing_evidence        NONE (0.85)  NONE (0.88)  +0.030
  ((name) = reported-only comparison: no engine gate acts on it)

GATES: same outcome at every gate (--all-gates shows every row)

ACTIONS
  ORIGINAL  HUMAN_REVIEW (correct)
      - step_therapy p_yes=0.932 is below the 0.95 autonomous-action bar
  CANDIDATE HUMAN_REVIEW (correct)
      - step_therapy p_yes=0.551 is below the 0.95 autonomous-action bar

ACTION UNCHANGED: HUMAN_REVIEW
```

Both providers escalate the case, which is correct, but Claude's composed `step_therapy`
probability is 0.380 lower than Jev's. The parenthesised `(auto_process)` on `material_contradiction`
is a reported-only comparison (1 − p_yes against the bar), not an engine gate, so no gate changes.

The same Jev trace under Jev's own dev-selected threshold, 0.89 (from
[`compare-own-thresholds.txt`](evals/baselines/gold-v0.1/compare-own-thresholds.txt)):

```text
$ env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env replay GOLD-TMP-17 \
    --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz \
    --dataset evals/gold \
    --at 0.89
Relay replay — GOLD-TMP-17
ORIGINAL run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE policy replay: STORED DECISIONS under policy immunara-v0.1 (v0.1), auto_process=0.89, thresholds v0.1+at0.89 — judgments were made against the original policy's questions
EXPECTED (evaluation-only): HUMAN_REVIEW

   DECISION                ORIGINAL     CANDIDATE    Δ       CROSSED
   diagnosis_support       p_yes=0.980  p_yes=0.980  +0.000
   step_therapy            p_yes=0.932  p_yes=0.932  +0.000  auto_process
   documentation_complete  p_yes=0.970  p_yes=0.970  +0.000
   material_contradiction  p_yes=0.100  p_yes=0.100  +0.000  (auto_process)
   missing_evidence        NONE (0.85)  NONE (0.85)  +0.000
  ((name) = reported-only comparison: no engine gate acts on it)

THRESHOLDS CHANGED
  auto_process  0.95 → 0.89

GATES (rows whose outcome differs; --all-gates shows every row)
  auto_process      passed → FIRED
      original:  min(required p_yes)=0.932, auto at >= 0.95; p_yes(material_contradiction)=0.100, blocks at >= 0.2
      candidate: min(required p_yes)=0.932, auto at >= 0.89; p_yes(material_contradiction)=0.100, blocks at >= 0.2
  default_review    FIRED → not reached
      original:  case does not meet the autonomous-action bar

ACTIONS
  ORIGINAL  HUMAN_REVIEW (correct)
      - step_therapy p_yes=0.932 is below the 0.95 autonomous-action bar
  CANDIDATE AUTO_PROCESS (UNSAFE)
      - all required judgments are at or above 0.89 and contradiction risk is below 0.2

ACTION CHANGED: HUMAN_REVIEW → AUTO_PROCESS (NEWLY UNSAFE)
```

This command exits 4. At 0.89, Jev's 0.932 `step_therapy` clears the bar and the case
auto-processes, but its expected action is `HUMAN_REVIEW`. This is the unsafe automation that
`compare-own-thresholds.txt` records for Jev on `GOLD-TMP-17`.

## Regression gate

`relay regression` compares a candidate run against an accepted baseline over the same frozen
dataset and fails loudly when the candidate automates a case unsafely that the baseline did not,
and nobody has reviewed it. The gate is relative to the baseline (see STILL UNSAFE below), so it
cannot catch an unsafe automation the baseline already makes. A candidate can be a new question
set, provider, policy or threshold. The command is offline: the
candidate is either an existing trace file (`--candidate-traces`, for example a run made earlier
with `relay eval`, which applies its own budget guard) or a policy replay of the baseline's stored
decisions (`--candidate-policy ID`, `--candidate-latest-policy`, `--candidate-at X`).
`--reproduce` replays the baseline under today's engine; that is the engine-drift gate.
`--baseline-at X` re-decides the baseline at its own dev-selected operating point first. Both
runs must cover exactly the dataset's cases with unchanged content hashes. A baseline recorded on
a `--limit/--sample-seed` subsample is paired with the same subsample, read from its run manifest.

The report puts both runs' rates side by side, each with a 95% Clopper-Pearson interval, then the
change counts. Newly unsafe cases come first, each with a `relay replay` command that reproduces
that case's diff, followed by STILL UNSAFE — cases the candidate automates unsafely that the
baseline already automated unsafely too, so they are not newly unsafe and never fail the gate,
only visible here — then engine drift (`--reproduce` mode), resolved and regressed cases and
calibration deltas. The gate fails when:

- a newly unsafe case is not covered by a waiver (exit 4)
- `--max-regressed N` is given and more than N cases regressed (exit 4)
- in `--reproduce` mode, any case is not identical (ENGINE DRIFT, exit 3)

Input and usage errors exit 2, and the highest applicable code wins. `--json` prints the result as
JSON and nothing else. `--out DIR` writes `regression.json` and `regression.md`, plus
`candidate.jsonl.gz` and `candidate.manifest.json` (`mode: "simulated"`) for a replayed candidate,
which `relay eval --traces`, `compare` and `replay` can read.

Jev's gold traces at its dev-selected threshold, 0.89, against the same traces as recorded at
0.95. This fails, because at 0.89 Jev automates `GOLD-TMP-17` (the interrupted methotrexate
course from "Replay" above):

```text
$ env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env regression \
    --dataset evals/gold \
    --baseline evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz \
    --candidate-at 0.89
Relay regression — dataset gold-v0.1 · n=100
BASELINE  run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE policy replay: STORED DECISIONS under policy immunara-v0.1 (v0.1), auto_process=0.89, thresholds v0.1+at0.89 — judgments were made against the original policy's questions

METRIC                  BASELINE        CANDIDATE       Δ         BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     82/100 (82.0%)  91/100 (91.0%)  +9.0 pp   [73.1%, 89.0%]   [83.6%, 95.8%]
Automation rate         18/100 (18.0%)  29/100 (29.0%)  +11.0 pp  [11.0%, 26.9%]   [20.4%, 38.9%]
Request-info rate       32/100 (32.0%)  32/100 (32.0%)  +0.0 pp   [23.0%, 42.1%]   [23.0%, 42.1%]
Human escalation rate   50/100 (50.0%)  39/100 (39.0%)  -11.0 pp  [39.8%, 60.2%]   [29.4%, 49.3%]
Unsafe automation rate  0/18 (0.0%)     1/29 (3.4%)     +3.4 pp   [0.0%, 18.5%]    [0.1%, 17.8%]
Invalid outputs         0               0               +0

CHANGES: improved 10 · unchanged 89 · regressed 1 · changed-both-wrong 0 · not identical 56

NEWLY UNSAFE (1)
  GOLD-TMP-17  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: step_therapy: auto_process
      replay: relay replay GOLD-TMP-17 --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz --dataset evals/gold --at 0.89

REGRESSED (1)
  GOLD-TMP-17  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: step_therapy: auto_process
      replay: relay replay GOLD-TMP-17 --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz --dataset evals/gold --at 0.89

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.011 → 0.011        +0.000   0.049 → 0.049      +0.000
 step_therapy            0.075 → 0.075        +0.000   0.049 → 0.049      +0.000
 documentation_complete  0.063 → 0.063        +0.000   0.035 → 0.035      +0.000
 material_contradiction  0.040 → 0.040        +0.000   0.086 → 0.086      +0.000
 missing_evidence        0.120 → 0.120        +0.000   0.067 → 0.067      +0.000

REGRESSION GATE: FAIL — 1 newly unsafe case(s) without a waiver: GOLD-TMP-17
```

The command exits 4. The same run passes with the committed example waiver
[`waiver-tmp17.json`](evals/regression/examples/waiver-tmp17.json), which exists only to show the
mechanism. It is not a real review:

```text
$ env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env regression \
    --dataset evals/gold \
    --baseline evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz \
    --candidate-at 0.89 \
    --waivers evals/regression/examples/waiver-tmp17.json
Relay regression — dataset gold-v0.1 · n=100
BASELINE  run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE policy replay: STORED DECISIONS under policy immunara-v0.1 (v0.1), auto_process=0.89, thresholds v0.1+at0.89 — judgments were made against the original policy's questions

METRIC                  BASELINE        CANDIDATE       Δ         BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     82/100 (82.0%)  91/100 (91.0%)  +9.0 pp   [73.1%, 89.0%]   [83.6%, 95.8%]
Automation rate         18/100 (18.0%)  29/100 (29.0%)  +11.0 pp  [11.0%, 26.9%]   [20.4%, 38.9%]
Request-info rate       32/100 (32.0%)  32/100 (32.0%)  +0.0 pp   [23.0%, 42.1%]   [23.0%, 42.1%]
Human escalation rate   50/100 (50.0%)  39/100 (39.0%)  -11.0 pp  [39.8%, 60.2%]   [29.4%, 49.3%]
Unsafe automation rate  0/18 (0.0%)     1/29 (3.4%)     +3.4 pp   [0.0%, 18.5%]    [0.1%, 17.8%]
Invalid outputs         0               0               +0

CHANGES: improved 10 · unchanged 89 · regressed 1 · changed-both-wrong 0 · not identical 56

WAIVED NEWLY UNSAFE (1) — reviewed, not failures
  GOLD-TMP-17  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: step_therapy: auto_process
      replay: relay replay GOLD-TMP-17 --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz --dataset evals/gold --at 0.89
      waiver: EXAMPLE ONLY, not a real review: shows how a reviewed waiver lets the README's gold demo (Jev at auto_process 0.89) pass despite automating the interrupted methotrexate course (approved by example (README demonstration), 2026-09-26, gate *)

REGRESSED (1)
  GOLD-TMP-17  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: step_therapy: auto_process
      replay: relay replay GOLD-TMP-17 --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz --dataset evals/gold --at 0.89

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.011 → 0.011        +0.000   0.049 → 0.049      +0.000
 step_therapy            0.075 → 0.075        +0.000   0.049 → 0.049      +0.000
 documentation_complete  0.063 → 0.063        +0.000   0.035 → 0.035      +0.000
 material_contradiction  0.040 → 0.040        +0.000   0.086 → 0.086      +0.000
 missing_evidence        0.120 → 0.120        +0.000   0.067 → 0.067      +0.000

REGRESSION GATE: PASS
```

**Committed gates.** [`evals/regression/gates.json`](evals/regression/gates.json) holds the 20
gates CI runs with `relay regression --config evals/regression/gates.json`. Each gate's report is
printed, then a summary table; the exit code is the highest across gates, and `--gate NAME` runs
only the named gates. `--strict-generated` turns a `requires_generated` gate whose dataset is
missing into an ERROR row (exit 2) instead of SKIPPED, so a failed, dropped or misnamed dataset
regeneration step cannot leave a holdout drift gate silently green; CI passes it.

| Gate | Baseline | Candidate | What it guards |
|---|---|---|---|
| `gold-reproduce-groundtruth`, `-rules`, `-jev`, `-claude` | each committed gold run | `--reproduce` | engine drift on gold, all four providers |
| `smoke-reproduce-jev` | the v0.1 smoke Jev run (its case hashes still match `evals/smoke`) | `--reproduce` | engine drift on the oldest committed trace, which predates policy-text hashes |
| `gold-jev-vs-claude` | Jev gold, re-decided at 0.89 | Claude gold traces, re-decided at 0.55 | Claude at its own operating point is not an unsafe regression versus Jev: 4 action differences (3 improved, 1 regressed), 0 newly unsafe. Both Jev at 0.89 and Claude at 0.55 automate `GOLD-TMP-17` unsafely; that is the baseline's own unsafe automation, so it is not newly unsafe — it shows up as 1 STILL UNSAFE instead. |
| `holdout-reproduce-jev`, `-rules`, `-claude-150` | each committed gen-v0.2-holdout run | `--reproduce` | engine drift on the holdout; `requires_generated`, so SKIPPED when `evals/generated/gen-v0.2-holdout` is absent (ERROR instead with `--strict-generated`, as CI runs it). The Claude gate uses the run's 150-case sample. |
| `gen-v0.3-dev-reproduce-jev-q-v0.2`, `-q-v0.3` | each committed gen-v0.3-dev run | `--reproduce` | engine drift on the q-v0.3 dev sets; `requires_generated` |
| `gen-v0.3-holdout-reproduce-jev-q-v0.3`, `-q-v0.2` | each committed gen-v0.3-holdout run | `--reproduce` | engine drift on the q-v0.3 holdout sets; `requires_generated` |
| `gen-v0.3-holdout-adoption-q-v0.2-to-q-v0.3` | q-v0.2 gen-v0.3-holdout, re-decided at 0.97 | q-v0.3 gen-v0.3-holdout, re-decided at 0.81 | the E1 holdout adoption check itself: PASS with 0 newly unsafe (10 correctness regressions; see "Question set q-v0.3"). Present only because the dev decision was ADOPT; `requires_generated` |
| `gold-reproduce-jev-q-v0.3` | the committed gold q-v0.3 Jev run | `--reproduce` | engine drift on the new gold q-v0.3 run; no `requires_generated` (gold-v0.1 is always on disk) |
| `gen-v0.3-shift-reproduce-jev-q-v0.3`, `-stale`, `-aware` | each committed gen-v0.3-shift / stale / aware run | `--reproduce` | engine drift on the paid shift run and its two `recompose` outputs; `requires_generated` |
| `gen-v0.3-shift-stale-to-aware` | stale (immunara-v0.1, policy-unaware) | aware (immunara-v0.2, policy-aware) | the E2 policy-shift check: PASS with 0 newly unsafe, 0 regressed (see "Policy shift"); `requires_generated` |
| `gold-reproduce-ablated-jev-q-v0.3-contradiction` | the committed ablated bundle (gold, Jev q-v0.3, `contradiction` gate disabled) | `--reproduce` | engine drift on an ablated trace: shows that ablated traces replay exactly, so `ABLATED` gate-path entries and the `ablation` field survive a reproduce round trip (see "Gate ablation"); no `requires_generated` (gold-v0.1 is always on disk) |

The failing demonstrations — Jev at auto_process 0.89 on `GOLD-TMP-17` (above) and gold
q-v0.2 → q-v0.3, which FAILs on `GOLD-TMP-16` (below, in "Question set q-v0.3") — are
deliberately not committed gates, so CI stays green.

**Adding a waiver.** A waiver is the deliberate, reviewed policy decision that lets a newly unsafe
case through. Add an entry to a waiver file, pass it with `--waivers FILE` (or `"waivers"` in a
gate), and get the change reviewed in its pull request; that review is the approval:

```json
{"waivers": [{"case_id": "GOLD-TMP-17", "gate": "gold-jev-vs-claude",
              "reason": "why this automation is acceptable", "approved_by": "reviewer",
              "date": "2026-09-26"}]}
```

Every field is required and non-empty, `date` is `YYYY-MM-DD`, and `gate` is a gate name or `*`
for every gate (a command-line run without `--config` has no gate name, so only `*` waivers apply
there). A malformed file exits 2. Waivers cover newly unsafe cases only: regressions and engine
drift cannot be waived. The report lists waived cases in their own section, and a waiver that
matches no newly unsafe case is reported as a stale waiver, which is a warning, not a failure.

**CI.** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every push and pull request
on ubuntu-latest with uv and Python 3.12. It installs with `uv sync --frozen`, runs `ruff check`,
`ruff format --check` and `pytest -q` (live tests are deselected by default), regenerates all five
generated datasets — gen-v0.2-dev, gen-v0.2-holdout, gen-v0.3-dev, gen-v0.3-holdout and
gen-v0.3-shift — with `relay generate` and checks each against its committed manifest with
`--verify` (a few seconds locally), then runs the committed gates with `--strict-generated` and
uploads `regression-report/` as an artifact, even when a step fails. The workflow references no
secrets and sets no provider keys, and a test checks that it contains no `secrets.` reference.

## Shadow mode

Shadow mode models a safe, progressive rollout. It does not pretend Relay has real production
traffic: every case is synthetic, and every status change is simulated in a local file. The
rollout ladder has three rungs:

1. **The simulated live system (the incumbent).** `relay run --workflow simulated` runs the
   accepted configuration (provider, question set, policy and thresholds). Each action becomes a
   simulated case-status transition in a small state file (default `state/case-status.json`,
   git-ignored): `RECEIVED` → `AUTO_APPROVED` (AUTO_PROCESS), `INFO_REQUESTED` (REQUEST_INFO) or
   `IN_HUMAN_REVIEW` (HUMAN_REVIEW).
2. **The shadow candidate.** `relay run --workflow shadow` runs a new configuration on the same
   cases. It records each proposed action as a `mode: "shadow"` trace and prints
   `SHADOW: Would auto-process CASE-ID; no action was taken.` The state file is only read. The
   command hashes it before and after the run, and prints `case state unchanged (verified)` only
   when the two hashes match. If they differ, it prints `SHADOW VIOLATION` and exits 3.
3. **The promotion check.** With `--incumbent TRACES`, the shadow run is compared with the
   incumbent. The agreement section uses no ground truth, so it is what a real shadow deployment
   could see: the action agreement rate, an incumbent × candidate action matrix, and the cases the
   candidate would newly auto-process or would stop auto-processing. The promotion check below it
   is labelled EVALUATION-ONLY. It is the regression gate from "Regression gate" above, with the
   incumbent as its baseline. Gate PASS prints `PROMOTION CHECK: PROMOTE` (exit 0), and gate FAIL
   prints `PROMOTION CHECK: HOLD — <failures>` (exit 4). STILL UNSAFE cases are listed but never
   cause a HOLD.

The guarantee is enforced in code, not only in the CLI. The status store's only writer refuses a
shadow trace with `ShadowWriteError` before it touches the file, and a test checks the file stays
byte-identical.

The handoff's `relay run --dataset evals/gold --mode shadow` is `relay run --dataset evals/gold
--workflow shadow` here, because `--mode` already selects Claude's sync or batch mode. Two
details follow from that choice:

- **Offline runs.** `--from-traces FILE [--at X]` re-issues a stored run's decisions as a new run
  in the requested mode, with `replay_of` set on every trace and `source_run_id` in the manifest.
  No provider is called. Without `--from-traces`, the run calls the provider with every existing
  guard: the Jev key check, and the Claude budget check and spend ledger.
- **Conflicts.** A second simulated run over cases the state file already moved is refused with
  exit 2. `--reset-state` first archives the file to `<state>.bak-<UTC timestamp>`.

`--waivers` and `--max-regressed` pass through to the promotion check, and `--out DIR` writes
`shadow.json` and `shadow.md`. The shadow traces and manifest go to `--traces-dir` (default
`traces/`), like any run.

The demos below use the committed gold traces only as frozen inputs, and nothing is tuned on
them. The per-case lines are trimmed (`[… N more … lines …]`); everything else is the commands'
real output. First, the incumbent: Jev's gold decisions at its dev-selected threshold, 0.89.

```text
$ env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env run \
    --dataset evals/gold --workflow simulated --state state/promote-demo.json \
    --from-traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz --at 0.89
SIMULATED: GOLD-CON-01 RECEIVED → IN_HUMAN_REVIEW (HUMAN_REVIEW)
SIMULATED: GOLD-CON-02 RECEIVED → IN_HUMAN_REVIEW (HUMAN_REVIEW)
SIMULATED: GOLD-CON-03 RECEIVED → IN_HUMAN_REVIEW (HUMAN_REVIEW)
[… 97 more SIMULATED lines, one per case …]

SIMULATED RUN run_20260927T053253Z_80ff2f: 100 transitions applied — AUTO_APPROVED 29 · INFO_REQUESTED 32 · IN_HUMAN_REVIEW 39
Traces: traces/run_20260927T053253Z_80ff2f.jsonl
Manifest: traces/run_20260927T053253Z_80ff2f.manifest.json
State: state/promote-demo.json
```

Then Claude at its own dev-selected threshold, 0.55, shadows it. This is the `gold-jev-vs-claude`
gate as a rollout: 96/100 actions agree, and the candidate is not an unsafe regression, so the
check says PROMOTE. Both configurations automate `GOLD-TMP-17` unsafely (see "Regression gate"
above), so it appears under STILL UNSAFE and not as a failure.

```text
$ env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env run \
    --dataset evals/gold --workflow shadow --state state/promote-demo.json \
    --from-traces evals/baselines/gold-v0.1/run_20260926T011730Z_f1852f/traces.jsonl.gz --at 0.55 \
    --incumbent traces/run_20260927T053253Z_80ff2f.jsonl
SHADOW: Would send GOLD-CON-01 to human review; no action was taken. (current status: IN_HUMAN_REVIEW by run_20260927T053253Z_80ff2f)
SHADOW: Would send GOLD-CON-02 to human review; no action was taken. (current status: IN_HUMAN_REVIEW by run_20260927T053253Z_80ff2f)
SHADOW: Would send GOLD-CON-03 to human review; no action was taken. (current status: IN_HUMAN_REVIEW by run_20260927T053253Z_80ff2f)
[… 97 more SHADOW lines, one per case …]

SHADOW RUN run_20260927T053259Z_9dc576: 100 proposals recorded; case state unchanged (verified).
Traces: traces/run_20260927T053259Z_9dc576.jsonl
Manifest: traces/run_20260927T053259Z_9dc576.manifest.json

Relay shadow comparison — dataset gold-v0.1 · n=100
INCUMBENT simulated run_20260927T053253Z_80ff2f · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.89
CANDIDATE shadow run_20260927T053259Z_9dc576 · claude q-v0.2+claude-prompt-v1 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.55

AGREEMENT (unlabelled; what a real shadow deployment sees)
  Action agreement: 96/100 (96.0%)  95% CI [90.1%, 98.9%]

  INCUMBENT \ CANDIDATE  AUTO_PROCESS  REQUEST_INFO  HUMAN_REVIEW
  AUTO_PROCESS           28            0             1
  REQUEST_INFO           0             32            0
  HUMAN_REVIEW           2             1             36

  Would newly auto-process (2): GOLD-MIS-17, GOLD-TMP-15
  Would stop auto-processing (1): GOLD-TMP-18

EVALUATION-ONLY (uses ground truth; not available in a real shadow deployment)
Relay regression — dataset gold-v0.1 · n=100
BASELINE  simulated run_20260927T053253Z_80ff2f · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.89
CANDIDATE shadow run_20260927T053259Z_9dc576 · claude q-v0.2+claude-prompt-v1 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.55

METRIC                  BASELINE        CANDIDATE       Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     91/100 (91.0%)  93/100 (93.0%)  +2.0 pp  [83.6%, 95.8%]   [86.1%, 97.1%]
Automation rate         29/100 (29.0%)  30/100 (30.0%)  +1.0 pp  [20.4%, 38.9%]   [21.2%, 40.0%]
Request-info rate       32/100 (32.0%)  33/100 (33.0%)  +1.0 pp  [23.0%, 42.1%]   [23.9%, 43.1%]
Human escalation rate   39/100 (39.0%)  37/100 (37.0%)  -2.0 pp  [29.4%, 49.3%]   [27.6%, 47.2%]
Unsafe automation rate  1/29 (3.4%)     1/30 (3.3%)     -0.1 pp  [0.1%, 17.8%]    [0.1%, 17.2%]
Invalid outputs         0               0               +0

CHANGES: improved 3 · unchanged 96 · regressed 1 · changed-both-wrong 0 · not identical 100

STILL UNSAFE (1) — also unsafe in the baseline; not a gate failure
  GOLD-TMP-17  expected HUMAN_REVIEW  AUTO_PROCESS → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-TMP-17 --traces traces/run_20260927T053253Z_80ff2f.jsonl --dataset evals/gold --candidate-traces traces/run_20260927T053259Z_9dc576.jsonl

REGRESSED (1)
  GOLD-TMP-18  expected AUTO_PROCESS  AUTO_PROCESS → HUMAN_REVIEW
      answer changed: step_therapy · gated crossings: step_therapy: auto_process
      replay: relay replay GOLD-TMP-18 --traces traces/run_20260927T053253Z_80ff2f.jsonl --dataset evals/gold --candidate-traces traces/run_20260927T053259Z_9dc576.jsonl

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.011 → 0.008        -0.003   0.049 → 0.049      -0.000
 step_therapy            0.075 → 0.084        +0.009   0.049 → 0.152      +0.102
 documentation_complete  0.063 → 0.046        -0.017   0.035 → 0.098      +0.064
 material_contradiction  0.040 → 0.007        -0.032   0.086 → 0.054      -0.032
 missing_evidence        0.120 → 0.076        -0.045   0.067 → 0.133      +0.065

REGRESSION GATE: PASS

PROMOTION CHECK: PROMOTE
```

The second demo is the FAIL demo from "Regression gate" in rollout terms. The incumbent is Jev
at the recorded 0.95, and the candidate is the same decisions at 0.89. The shadow line for
`GOLD-TMP-17` shows the candidate would auto-process a case the incumbent sent to human review,
and the promotion check holds the rollout. The command exits 4.

```text
$ env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env run \
    --dataset evals/gold --workflow simulated --state state/hold-demo.json \
    --from-traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz
SIMULATED: GOLD-CON-01 RECEIVED → IN_HUMAN_REVIEW (HUMAN_REVIEW)
SIMULATED: GOLD-CON-02 RECEIVED → IN_HUMAN_REVIEW (HUMAN_REVIEW)
SIMULATED: GOLD-CON-03 RECEIVED → IN_HUMAN_REVIEW (HUMAN_REVIEW)
[… 97 more SIMULATED lines, one per case …]

SIMULATED RUN run_20260927T053303Z_3c64c0: 100 transitions applied — AUTO_APPROVED 18 · INFO_REQUESTED 32 · IN_HUMAN_REVIEW 50
Traces: traces/run_20260927T053303Z_3c64c0.jsonl
Manifest: traces/run_20260927T053303Z_3c64c0.manifest.json
State: state/hold-demo.json

$ env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env run \
    --dataset evals/gold --workflow shadow --state state/hold-demo.json \
    --from-traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz --at 0.89 \
    --incumbent traces/run_20260927T053303Z_3c64c0.jsonl
SHADOW: Would send GOLD-CON-01 to human review; no action was taken. (current status: IN_HUMAN_REVIEW by run_20260927T053303Z_3c64c0)
SHADOW: Would send GOLD-CON-02 to human review; no action was taken. (current status: IN_HUMAN_REVIEW by run_20260927T053303Z_3c64c0)
SHADOW: Would send GOLD-CON-03 to human review; no action was taken. (current status: IN_HUMAN_REVIEW by run_20260927T053303Z_3c64c0)
[… 73 more SHADOW lines, one per case …]
SHADOW: Would auto-process GOLD-TMP-17; no action was taken. (current status: IN_HUMAN_REVIEW by run_20260927T053303Z_3c64c0)
[… 23 more SHADOW lines, one per case …]

SHADOW RUN run_20260927T053309Z_5ae601: 100 proposals recorded; case state unchanged (verified).
Traces: traces/run_20260927T053309Z_5ae601.jsonl
Manifest: traces/run_20260927T053309Z_5ae601.manifest.json

Relay shadow comparison — dataset gold-v0.1 · n=100
INCUMBENT simulated run_20260927T053303Z_3c64c0 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE shadow run_20260927T053309Z_5ae601 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.89

AGREEMENT (unlabelled; what a real shadow deployment sees)
  Action agreement: 89/100 (89.0%)  95% CI [81.2%, 94.4%]

  INCUMBENT \ CANDIDATE  AUTO_PROCESS  REQUEST_INFO  HUMAN_REVIEW
  AUTO_PROCESS           18            0             0
  REQUEST_INFO           0             32            0
  HUMAN_REVIEW           11            0             39

  Would newly auto-process (11): GOLD-MIS-19, GOLD-STR-01, GOLD-STR-03, GOLD-STR-04, GOLD-STR-06, GOLD-TMP-01, GOLD-TMP-03, GOLD-TMP-08, GOLD-TMP-17, GOLD-TMP-18, GOLD-TRK-16
  Would stop auto-processing (0): none

EVALUATION-ONLY (uses ground truth; not available in a real shadow deployment)
Relay regression — dataset gold-v0.1 · n=100
BASELINE  simulated run_20260927T053303Z_3c64c0 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE shadow run_20260927T053309Z_5ae601 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.89

METRIC                  BASELINE        CANDIDATE       Δ         BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     82/100 (82.0%)  91/100 (91.0%)  +9.0 pp   [73.1%, 89.0%]   [83.6%, 95.8%]
Automation rate         18/100 (18.0%)  29/100 (29.0%)  +11.0 pp  [11.0%, 26.9%]   [20.4%, 38.9%]
Request-info rate       32/100 (32.0%)  32/100 (32.0%)  +0.0 pp   [23.0%, 42.1%]   [23.0%, 42.1%]
Human escalation rate   50/100 (50.0%)  39/100 (39.0%)  -11.0 pp  [39.8%, 60.2%]   [29.4%, 49.3%]
Unsafe automation rate  0/18 (0.0%)     1/29 (3.4%)     +3.4 pp   [0.0%, 18.5%]    [0.1%, 17.8%]
Invalid outputs         0               0               +0

CHANGES: improved 10 · unchanged 89 · regressed 1 · changed-both-wrong 0 · not identical 56

NEWLY UNSAFE (1)
  GOLD-TMP-17  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: step_therapy: auto_process
      replay: relay replay GOLD-TMP-17 --traces traces/run_20260927T053303Z_3c64c0.jsonl --dataset evals/gold --candidate-traces traces/run_20260927T053309Z_5ae601.jsonl

REGRESSED (1)
  GOLD-TMP-17  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: step_therapy: auto_process
      replay: relay replay GOLD-TMP-17 --traces traces/run_20260927T053303Z_3c64c0.jsonl --dataset evals/gold --candidate-traces traces/run_20260927T053309Z_5ae601.jsonl

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.011 → 0.011        +0.000   0.049 → 0.049      +0.000
 step_therapy            0.075 → 0.075        +0.000   0.049 → 0.049      +0.000
 documentation_complete  0.063 → 0.063        +0.000   0.035 → 0.035      +0.000
 material_contradiction  0.040 → 0.040        +0.000   0.086 → 0.086      +0.000
 missing_evidence        0.120 → 0.120        +0.000   0.067 → 0.067      +0.000

REGRESSION GATE: FAIL — 1 newly unsafe case(s) without a waiver: GOLD-TMP-17

PROMOTION CHECK: HOLD — 1 newly unsafe case(s) without a waiver: GOLD-TMP-17
```

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

For an interrupted-and-restarted (variant (c)) course, labelling counts the final-stop outcome
documented after the short second segment, applied to the long first segment — the spec's resolved
ambiguity 8 (`relay/generation/labels.py`, `label_case`).

**Adoption on dev** (rule fixed in advance: adopt iff q-v0.3's dev correct-action rate is higher
and the dev regression gate passes with 0 newly unsafe), from
[`evals/baselines/gen-v0.3-dev/adoption.txt`](evals/baselines/gen-v0.3-dev/adoption.txt):

```text
Adoption rule (Phase 3D spec §5 E1, dev only): adopt q-v0.3 iff its correct-action rate is higher than
q-v0.2's and the dev regression gate q-v0.2 -> q-v0.3 passes (0 newly unsafe).
  q-v0.2: run run_20260927T071846Z_e950c0 correct 268/400 (0.6700) at thresholds v0.1+at0.97, unsafe 0
  q-v0.3: run run_20260927T071912Z_cdaf0c correct 373/400 (0.9325) at thresholds v0.1+at0.81, unsafe 0
  gate: PASS (newly unsafe 0, regressed 3, improved 108)
DECISION: ADOPT q-v0.3
```

Note the q-v0.2 thresholds above: `v0.1+at0.97` is q-v0.2's own **`gen-v0.3-dev`-selected** threshold
(the sweep's highest automation with UAR ≤ 1%, run fresh for this comparison), not the `0.89`
selected on `gen-v0.2-dev` in Phase 2. The two numbers are not comparable; q-v0.2's threshold moves
because `gen-v0.3-dev`'s case mix (interrupted and old courses) is different from `gen-v0.2-dev`'s:
on `gen-v0.3-dev`, q-v0.2 at 0.89 automates 131 cases with 18 unsafe (UAR 13.7%,
[`frontier.csv`](evals/baselines/gen-v0.3-dev/run_20260927T071846Z_e950c0/report/frontier.csv)),
all 18 interrupted-course cases, so the ≤ 1% UAR ceiling pushes its t\* to 0.97. Every q-v0.2
*re-decided* comparison in this section (the holdout and gold regressions, both re-decided at a
dev-selected threshold) uses that `0.97` figure. The GOLD-TMP-17/18 replays below are the one
exception: they show the traces at their **recorded** `auto_process=0.95`, not re-decided at 0.97
or 0.89.

**Holdout, once, at the dev-selected thresholds.** From
[`evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/regression.md`](evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/regression.md):

```text
Relay regression — dataset gen-v0.3-holdout · n=1000
BASELINE  replay-run_20260927T072249Z_204814 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.97
CANDIDATE candidate trace run_20260927T072144Z_12e1e4 · jev q-v0.3 · re-decided at auto_process=0.81

METRIC                  BASELINE          CANDIDATE         Δ         BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     694/1000 (69.4%)  921/1000 (92.1%)  +22.7 pp  [66.4%, 72.2%]   [90.3%, 93.7%]
Automation rate         17/1000 (1.7%)    244/1000 (24.4%)  +22.7 pp  [1.0%, 2.7%]     [21.8%, 27.2%]
Request-info rate       323/1000 (32.3%)  327/1000 (32.7%)  +0.4 pp   [29.4%, 35.3%]   [29.8%, 35.7%]
Human escalation rate   660/1000 (66.0%)  429/1000 (42.9%)  -23.1 pp  [63.0%, 68.9%]   [39.8%, 46.0%]
Unsafe automation rate  1/17 (5.9%)       0/244 (0.0%)      -5.9 pp   [0.1%, 28.7%]    [0.0%, 1.5%]
Invalid outputs         0                 0                 +0

CHANGES: improved 237 · unchanged 753 · regressed 10 · changed-both-wrong 0 · not identical 1000

UNSAFE RESOLVED (1)
  GEN-04000653  expected HUMAN_REVIEW  AUTO_PROCESS → HUMAN_REVIEW
      answer changed: step_therapy · gated crossings: step_therapy: auto_process
      replay: relay replay GEN-04000653 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz

REGRESSED (10)
  GEN-04000114  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000114 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000195  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: diagnosis_support: auto_process; documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000195 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000459  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000459 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000479  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: diagnosis_support: auto_process; documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000479 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000556  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000556 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000583  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000583 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000771  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: diagnosis_support: auto_process; documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000771 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000839  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: diagnosis_support: auto_process; documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000839 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000847  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000847 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000999  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: documentation_complete: auto_process; material_contradiction: contradiction_auto_block; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000999 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.001 → 0.001        -0.000   0.029 → 0.029      -0.000
 step_therapy            0.045 → 0.014        -0.031   0.020 → 0.038      +0.018
 documentation_complete  0.036 → 0.036        +0.001   0.073 → 0.072      -0.001
 material_contradiction  0.032 → 0.032        -0.000   0.118 → 0.116      -0.002
 missing_evidence        0.192 → 0.196        +0.003   0.068 → 0.072      +0.003

REGRESSION GATE: PASS
```

The 10 REGRESSED cases above (all `HUMAN_REVIEW` → `REQUEST_INFO`) are correctness regressions,
not safety regressions: none of them changed to an unsafe automation, and each is still a
non-automated action. In each, Jev's `missing_evidence = TREATMENT_HISTORY` confidence reached
the 0.7 request-info bar under q-v0.3 (e.g. GEN-04000114 0.63 → 0.77, GEN-04000999 0.64 → 0.72),
while the truth is `NONE` — producing an unnecessary information request to the submitter rather
than an automation.

**Gold (not blind for this change; see above).** From
[`evals/baselines/gold-v0.1/regression-q-v0.2-vs-q-v0.3/regression.md`](evals/baselines/gold-v0.1/regression-q-v0.2-vs-q-v0.3/regression.md):

```text
Relay regression — dataset gold-v0.1 · n=100
BASELINE  replay-run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.97
CANDIDATE candidate trace run_20260927T072623Z_ad6f44 · jev q-v0.3 · re-decided at auto_process=0.81

METRIC                  BASELINE        CANDIDATE       Δ         BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     69/100 (69.0%)  94/100 (94.0%)  +25.0 pp  [59.0%, 77.9%]   [87.4%, 97.8%]
Automation rate         5/100 (5.0%)    31/100 (31.0%)  +26.0 pp  [1.6%, 11.3%]    [22.1%, 41.0%]
Request-info rate       32/100 (32.0%)  32/100 (32.0%)  +0.0 pp   [23.0%, 42.1%]   [23.0%, 42.1%]
Human escalation rate   63/100 (63.0%)  37/100 (37.0%)  -26.0 pp  [52.8%, 72.4%]   [27.6%, 47.2%]
Unsafe automation rate  0/5 (0.0%)      1/31 (3.2%)     +3.2 pp   [0.0%, 52.2%]    [0.1%, 16.7%]
Invalid outputs         0               0               +0

CHANGES: improved 25 · unchanged 74 · regressed 0 · changed-both-wrong 1 · not identical 100

NEWLY UNSAFE (1)
  GOLD-TMP-16  expected REQUEST_INFO  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: diagnosis_support: auto_process; step_therapy: auto_process; documentation_complete: auto_process
      replay: relay replay GOLD-TMP-16 --traces evals/baselines/gold-v0.1/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/gold-v0.1/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.011 → 0.010        -0.001   0.049 → 0.048      -0.001
 step_therapy            0.075 → 0.067        -0.008   0.049 → 0.044      -0.005
 documentation_complete  0.063 → 0.063        -0.000   0.035 → 0.037      +0.002
 material_contradiction  0.040 → 0.041        +0.002   0.086 → 0.094      +0.008
 missing_evidence        0.120 → 0.117        -0.003   0.067 → 0.090      +0.022

REGRESSION GATE: FAIL — 1 newly unsafe case(s) without a waiver: GOLD-TMP-16
```

**How GOLD-TMP-16 becomes newly unsafe.** `relay replay GOLD-TMP-16` with `--all-gates`, offline:

```text
Relay replay — GOLD-TMP-16
ORIGINAL replay-run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.97
CANDIDATE candidate trace replay-run_20260927T072623Z_ad6f44 · jev q-v0.3
EXPECTED (evaluation-only): REQUEST_INFO

   DECISION                ORIGINAL     CANDIDATE    Δ       CROSSED
   diagnosis_support       p_yes=0.940  p_yes=0.940  +0.000  auto_process
   step_therapy            p_yes=0.811  p_yes=0.836  +0.024  auto_process
   documentation_complete  p_yes=0.910  p_yes=0.910  +0.000  auto_process
   material_contradiction  p_yes=0.090  p_yes=0.090  +0.000  (auto_process)
   missing_evidence        NONE (0.78)  NONE (0.81)  +0.030  (auto_process)
  ((name) = reported-only comparison: no engine gate acts on it)

THRESHOLDS CHANGED
  auto_process  0.97 → 0.81

GATES (all rows)
  provider          passed
      all five decisions present and well-formed
  age               passed
      patient.age=47, policy min_age=18
  contradiction     passed
      p_yes(material_contradiction)=0.090, review at >= 0.8
  documentation     passed
      p_yes(documentation_complete)=0.910, request info below 0.6
  missing_evidence  passed
      original:  missing_evidence=NONE (p=0.780), request info at >= 0.7
      candidate: missing_evidence=NONE (p=0.810), request info at >= 0.7
  auto_process      passed → FIRED
      original:  min(required p_yes)=0.811, auto at >= 0.97; p_yes(material_contradiction)=0.090, blocks at >= 0.2
      candidate: min(required p_yes)=0.836, auto at >= 0.81; p_yes(material_contradiction)=0.090, blocks at >= 0.2
  default_review    FIRED → not reached
      original:  case does not meet the autonomous-action bar

ACTIONS
  ORIGINAL  HUMAN_REVIEW (wrong-safe)
      - diagnosis_support p_yes=0.940 is below the 0.97 autonomous-action bar
      - step_therapy p_yes=0.811 is below the 0.97 autonomous-action bar
      - documentation_complete p_yes=0.910 is below the 0.97 autonomous-action bar
  CANDIDATE AUTO_PROCESS (UNSAFE)
      - all required judgments are at or above 0.81 and contradiction risk is below 0.2

ACTION CHANGED: HUMAN_REVIEW → AUTO_PROCESS (NEWLY UNSAFE)
```

None of GOLD-TMP-16's five raw judgments moved by more than 0.03. What changed the action is the
lower `auto_process` bar alone (`0.97 → 0.81`): `diagnosis_support` at 0.94, `documentation_complete`
at 0.91 and `step_therapy` at about 0.836 all now clear the 0.81 bar, where at 0.97 none of them did.
The `missing_evidence` gate did run (`GATES` shows it passed on both sides), but it only routes to
`REQUEST_INFO` when the most likely answer is a missing item (not `NONE`) with probability ≥ 0.7
(`relay/workflow/engine.py`). Jev answered `NONE` both times (0.78, then 0.81), whereas gold labels
the case `TREATMENT_HISTORY` (the methotrexate dates carry no year;
[`evals/gold/ADJUDICATION.md`](evals/gold/ADJUDICATION.md)). The gate therefore had nothing to act
on, and the lower `auto_process` bar let the case through.

GOLD-TMP-17 replayed across the two question sets:

```text
Relay replay — GOLD-TMP-17
ORIGINAL run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE candidate trace run_20260927T072623Z_ad6f44 · jev q-v0.3
EXPECTED (evaluation-only): HUMAN_REVIEW

    DECISION                ORIGINAL     CANDIDATE    Δ       CROSSED
    diagnosis_support       p_yes=0.980  p_yes=0.980  +0.000
 *  step_therapy            p_yes=0.932  p_yes=0.027  -0.904
    documentation_complete  p_yes=0.970  p_yes=0.970  +0.000
    material_contradiction  p_yes=0.100  p_yes=0.100  +0.000
    missing_evidence        NONE (0.85)  NONE (0.90)  +0.050
  (* = answer changed)

GATES: same outcome at every gate (--all-gates shows every row)

ACTIONS
  ORIGINAL  HUMAN_REVIEW (correct)
      - step_therapy p_yes=0.932 is below the 0.95 autonomous-action bar
  CANDIDATE HUMAN_REVIEW (correct)
      - step_therapy p_yes=0.027 is below the 0.95 autonomous-action bar

ACTION UNCHANGED: HUMAN_REVIEW
```

**Where the interrupted-course accuracy comes from.** The q-v0.2 → q-v0.3 `step_therapy` accuracy
gain, on both dev and holdout, concentrates on interrupted-course cases, not old-course ones.
[`scripts/phase3d_course_split.py`](scripts/phase3d_course_split.py) tags each case from its
committed `ground_truth.json` `notes` field (written at generation time by
`relay/generation/labels.py`: `"interrupted ("` for an interrupted-and-restarted course, `"ended
Nd before as-of"` with N > 365 for an old course) — no dataset regeneration, no random draw, just
the committed files — and reports `step_therapy` accuracy (prediction = `p_yes >= 0.5` vs
`ground_truth.step_therapy_satisfied`) per tag, run offline against the committed traces:

```text
$ uv run python -m scripts.phase3d_course_split evals/generated/gen-v0.3-dev \
    evals/baselines/gen-v0.3-dev/run_20260927T071846Z_e950c0/traces.jsonl.gz q-v0.2 \
    evals/baselines/gen-v0.3-dev/run_20260927T071912Z_cdaf0c/traces.jsonl.gz q-v0.3
gen-v0.3-dev (n=400): interrupted 73, old_course 58, other 269
  interrupted  q-v0.2 50/73 = 0.6849   q-v0.3 72/73 = 0.9863
  old_course   q-v0.2 57/58 = 0.9828   q-v0.3 56/58 = 0.9655
  other        q-v0.2 265/269 = 0.9851   q-v0.3 261/269 = 0.9703

$ uv run python -m scripts.phase3d_course_split evals/generated/gen-v0.3-holdout \
    evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz q-v0.2 \
    evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz q-v0.3
gen-v0.3-holdout (n=1000): interrupted 188, old_course 142, other 670
  interrupted  q-v0.2 147/188 = 0.7819   q-v0.3 188/188 = 1.0000
  old_course   q-v0.2 142/142 = 1.0000   q-v0.3 137/142 = 0.9648
  other        q-v0.2 658/670 = 0.9821   q-v0.3 653/670 = 0.9746
```

q-v0.3 is not a uniform win: on both dev and holdout, its `step_therapy` accuracy is slightly
*lower* than q-v0.2's on old-course and other cases (dev old-course 57/58 → 56/58, other
265/269 → 261/269; holdout old-course 142/142 → 137/142, other 658/670 → 653/670) — a small
negative result alongside the large interrupted-course gain.

**Findings.** The dev gate passed (0 newly unsafe, 3 regressed, 108 improved) with q-v0.3's correct-action
rate higher than q-v0.2's (373/400 vs 268/400), so the fixed-in-advance rule ADOPTed q-v0.3. Holdout,
run once, confirmed the direction at much larger scale: 921/1000 correct and 244/1000 automated for
q-v0.3@0.81 against 694/1000 correct and 17/1000 automated for q-v0.2@0.97, with the one q-v0.2 unsafe
automation (1/17) resolved and 0/244 unsafe under q-v0.3; the 10 regressed cases are correctness
regressions, not safety regressions. The GOLD-TMP-17 replay shows the read q-v0.3 was designed to fix:
`step_therapy` drops from p_yes=0.932 to p_yes=0.027 once the question set can represent an
interruption, though the action stays `HUMAN_REVIEW` (correct) on both sides at the traces'
recorded `auto_process` of 0.95 (q-v0.2 automated it only at Phase 2's 0.89; at q-v0.3's
`step_therapy` p_yes of 0.027 it is `HUMAN_REVIEW` at every threshold, including 0.81). By
contrast, the committed `GOLD-TMP-18` replay (also recorded at 0.95) moves from wrong-safe
`HUMAN_REVIEW` under q-v0.2 to correct `AUTO_PROCESS` under q-v0.3, since its later segment alone
clears the 12-week bar once q-v0.3 can see it. The negative result: on gold (not blind for this
change) the regression gate FAILED, with GOLD-TMP-16 newly unsafe — not because any raw judgment
moved much, but because the dev-selected `auto_process` bar dropped from 0.97 to 0.81 and let
diagnosis (0.94), documentation (0.91) and step therapy (about 0.84) all clear it, while the
`missing_evidence` gate never had anything to act on: Jev's answer was `NONE` both times, and the
gate only fires on a non-`NONE` answer at ≥ 0.7.

## Policy shift (immunara-v0.2)

immunara-v0.2 is immunara-v0.1 plus one added prior-treatment requirement ("policy_v5" in the
handoff): *"The qualifying methotrexate course must have been ongoing, or have ended, within the
12 months (365 days) before the request date."* Recency is part of step therapy, which Relay composes
in code, so the policy engine needed no new gate. One paid q-v0.3 Jev run on `gen-v0.3-shift`
(ground truth labelled under v0.2) was recomposed twice from the same stored answers with
`relay recompose`: **stale** composes under immunara-v0.1 (policy-unaware), and **aware** under
immunara-v0.2. Both are scored against the v0.2 ground truth at auto_process 0.95 (the recorded
default, not q-v0.3's `gen-v0.3-dev` t\* of 0.81, so that no threshold chosen on another dataset
enters the stale/aware comparison).

From [`evals/baselines/gen-v0.3-shift/shift-summary.md`](evals/baselines/gen-v0.3-shift/shift-summary.md):

| Run | Policy composed under | Correct action | Automation | Unsafe / auto (UAR) |
|---|---|---|---|---|
| stale (`run_20260927T072948Z_e5915e`) | v0.1 | 294/400 (73.5%) | 16/400 (4.0%) | 3/16 (18.8%) |
| aware (`run_20260927T072949Z_bd430c`) | v0.2 | 297/400 (74.2%) | 13/400 (3.2%) | 0/13 (0.0%) |

Stale-only unsafe automations (3): GEN-05000118, GEN-05000257, GEN-05000289
Still unsafe in both (0): none
Gate stale → aware: PASS (newly unsafe 0, regressed 0)

The stale-only unsafe automations are approvals that pass v0.1's rule but break the recency
requirement. The committed gate `gen-v0.3-shift-stale-to-aware` runs stale → aware in CI.

**Shadow demo.** Stale is the simulated incumbent and aware the shadow candidate:

```text
SHADOW RUN run_20260927T073007Z_c1a0ba: 400 proposals recorded; case state unchanged (verified).
PROMOTION CHECK: PROMOTE
```

**Rules baseline, for context.** rules-v0.1 has no recency rule, so it is naive by construction:

```text
  Correct action rate       261/400 (65.2%)
  Automation rate           50/400 (12.5%)
  Unsafe automation rate    6/50 (12.0%)
```

**Findings.** Under immunara-v0.2, the stale (policy-unaware) recomposition of the same stored Jev
answers has 3 unsafe automations out of 16 (18.8% UAR) — approvals that satisfy v0.1's rule but
break the new 365-day recency requirement. Recomposing the same answers as aware resolves all
three (0/13 unsafe) while giving up 3 automated cases (16 → 13, about 0.8 pp of the 400-case set)
and gaining a small amount of correct-action rate (73.5% → 74.2%). The stale → aware regression
gate PASSes (0 newly unsafe, 0 regressed), and the shadow demo, run over the same 400 cases with
stale as the simulated incumbent and aware as the candidate, verdicts PROMOTE.

## Parallelism (narrow decisions per call)

Handoff experiment 4 asks whether adding narrow decisions costs latency. `relay bench` sent 40
gen-v0.3-dev cases (sample seed 11) to Jev with 1, 5, 10 and 20 questions per call. Every call is
one `system_one` request carrying all of its questions, and the typesafe-sdk client returns no
per-question timing. Calls ran one at a time. Size 20 is q-v0.3's 19 questions plus one duplicated
question (controlled padding). The runs are latency-only; their decisions are not scored.

Dataset gen-v0.3-dev, 40 cases (--limit 40 --sample-seed 11); model jev-1.13.0; q-v0.3 ordering.

| Questions per call | Calls | Errors | p50 latency (ms) | p95 latency (ms) | Mean latency (ms) | Mean input tokens | Est. cost / case |
|---|---|---|---|---|---|---|---|
| 1 | 40 | 0 | 178 | 230 | 186 | 982 | $0.000041 |
| 5 | 40 | 0 | 177 | 225 | 183 | 1526 | $0.000064 |
| 10 | 40 | 0 | 186 | 207 | 186 | 2534 | $0.000106 |
| 20 | 40 | 0 | 191 | 290 | 202 | 4207 | $0.000177 |

Total estimated cost: $0.0155

- Batching: Each call is one system_one request carrying all k questions for one case (typesafe-sdk==0.7.1); the client does not split a request.
- Per-question latency: Not measured: typesafe-sdk==0.7.1 returns no per-question timing (one HTTP request per call).
- Padding: Size 20 is q-v0.3's 19 questions plus 'diagnosis_support_padding', a duplicate of 'diagnosis_support' under another id (controlled padding).
- Size order: size order rotated per case (offset = (sample seed 11 + case index) mod len(sizes), a Latin square), so each size appears equally often in each call position.
- Calls ran one at a time; latency is wall time around one request, retries included.
- Latency-only: these runs' decisions are not scored.
- Question ordering: diagnosis_support, documentation_complete, material_contradiction, missing_evidence, mtx_start_month, mtx_start_day, mtx_start_year, mtx_end_status, mtx_end_month, mtx_end_day, mtx_end_year, mtx_inadequate_response, mtx_interrupted, mtx_pause_month, mtx_pause_day, mtx_pause_year, mtx_restart_month, mtx_restart_day, mtx_restart_year, diagnosis_support_padding

**Findings.** The "size order rotated per case" note above describes a cyclic Latin square (each
case's call order is a fixed rotation of `1, 5, 10, 20` by `(sample seed + case index) mod 4`), not
a Williams design (which balances first-order carryover pairs); this run only balances position,
not adjacency, and n = 40 per size. p50 latency and the mean rise only about 7-9% from 1 to 20
questions (p50 178 → 191 ms, mean 186 → 202 ms). p95 rises more at size 20 (230 → 290 ms, +26%),
but at n = 40 the nearest-rank p95 is the 38th of 40 calls, and the three slowest size-20 calls are
290, 304 and 404 ms — a thin tail, so that figure is not a stable estimate. Estimated cost per case
scales with the token count, from $0.000041 at 1 question to $0.000177 at 20 — about 4.3× for 20×
the questions, since the fixed per-call overhead is amortized.

## Phase 3D Jev spend

Every paid Phase 3D run went through the Jev spend counter (cap $1.00). The committed copy of the ledger
is [`evals/baselines/jev-spend-3d.json`](evals/baselines/jev-spend-3d.json). No Claude calls were made.

From `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env budget show --ledger evals/baselines/jev-spend-3d.json` (`budget show` labels every ledger "Claude spend ledger"; this one is Jev's):

```text
Claude spend ledger — evals/baselines/jev-spend-3d.json
RUN                          DATASET           MODE  CASES  STATUS   COST     BATCH  NOTE
run_20260927T071846Z_e950c0  gen-v0.3-dev      sync  400    settled  $0.0452  —
run_20260927T071912Z_cdaf0c  gen-v0.3-dev      sync  400    settled  $0.0691  —
run_20260927T072144Z_12e1e4  gen-v0.3-holdout  sync  1000   settled  $0.1724  —
run_20260927T072249Z_204814  gen-v0.3-holdout  sync  1000   settled  $0.1125  —
run_20260927T072623Z_ad6f44  gold-v0.1         sync  100    settled  $0.0175  —
run_20260927T072915Z_007c7c  gen-v0.3-shift    sync  400    settled  $0.0696  —
run_20260927T073246Z_3a5f87  gen-v0.3-dev      sync  40     settled  $0.0155  —
```

Total: $0.501850 (sum of the ledger's `cost_usd` entries; the CLI's own summary line, omitted
above, rounds it to "Settled $0.5018") of the $1.00 cap. Total Claude spend is unchanged at $8.710495 of the
$10.00 default budget (`results/claude-spend.json`, `evals/baselines/claude-spend.json`); no Claude
calls were made in Phase 3.

## Gate ablation

Handoff experiment 6 asks what the contradiction and missing-evidence gates are worth.
`relay ablate` re-decides a committed run's stored decisions with one gate or both disabled, at
the run's own operating point (its dev-selected `--at`, or the recorded 0.95 for ground truth and
the aware shift run), and writes a simulated bundle whose traces record the ablation.
`relay regression` then gates the ablated run against the same run at the same threshold, case
by case. Expected actions always come from the full engine, so an ablated run is
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

| Dataset | Run | Provider | Thresholds | Ablation | Gate | Actions changed | Newly unsafe | Regressed | Improved | Automation (baseline → ablated) | UAR (baseline → ablated) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gen-v0.2-holdout | jev-q-v0.2 (`run_20260925T075242Z_fd455f`) | jev q-v0.2 | v0.1+at0.89 | contradiction | PASS | 37/1000 | 0 | 12 | 25 | 252/1000 (25.2%) [22.5%, 28.0%] → 277/1000 (27.7%) [24.9%, 30.6%] | 0/252 (0.0%) [0.0%, 1.5%] → 0/277 (0.0%) [0.0%, 1.3%] |
| gen-v0.2-holdout | jev-q-v0.2 (`run_20260925T075242Z_fd455f`) | jev q-v0.2 | v0.1+at0.89 | missing_evidence | PASS | 100/1000 | 0 | 32 | 67 | 252/1000 (25.2%) [22.5%, 28.0%] → 252/1000 (25.2%) [22.5%, 28.0%] | 0/252 (0.0%) [0.0%, 1.5%] → 0/252 (0.0%) [0.0%, 1.5%] |
| gen-v0.2-holdout | jev-q-v0.2 (`run_20260925T075242Z_fd455f`) | jev q-v0.2 | v0.1+at0.89 | contradiction+missing_evidence | PASS | 134/1000 | 0 | 41 | 92 | 252/1000 (25.2%) [22.5%, 28.0%] → 277/1000 (27.7%) [24.9%, 30.6%] | 0/252 (0.0%) [0.0%, 1.5%] → 0/277 (0.0%) [0.0%, 1.3%] |
| gen-v0.2-holdout | rules (`run_20260925T092425Z_0aee97`) | rules rules-v0.1 | v0.1+at0.99 | contradiction | PASS | 17/1000 | 0 | 17 | 0 | 134/1000 (13.4%) [11.3%, 15.7%] → 134/1000 (13.4%) [11.3%, 15.7%] | 0/134 (0.0%) [0.0%, 2.7%] → 0/134 (0.0%) [0.0%, 2.7%] |
| gen-v0.2-holdout | rules (`run_20260925T092425Z_0aee97`) | rules rules-v0.1 | v0.1+at0.99 | missing_evidence | PASS | 0/1000 | 0 | 0 | 0 | 134/1000 (13.4%) [11.3%, 15.7%] → 134/1000 (13.4%) [11.3%, 15.7%] | 0/134 (0.0%) [0.0%, 2.7%] → 0/134 (0.0%) [0.0%, 2.7%] |
| gen-v0.2-holdout | rules (`run_20260925T092425Z_0aee97`) | rules rules-v0.1 | v0.1+at0.99 | contradiction+missing_evidence | PASS | 17/1000 | 0 | 17 | 0 | 134/1000 (13.4%) [11.3%, 15.7%] → 134/1000 (13.4%) [11.3%, 15.7%] | 0/134 (0.0%) [0.0%, 2.7%] → 0/134 (0.0%) [0.0%, 2.7%] |
| gen-v0.2-holdout | claude-150 (`run_20260925T212034Z_bbee49`) | claude q-v0.2+claude-prompt-v1 | v0.1+at0.55 | contradiction | PASS | 3/150 | 0 | 3 | 0 | 37/150 (24.7%) [18.0%, 32.4%] → 37/150 (24.7%) [18.0%, 32.4%] | 0/37 (0.0%) [0.0%, 9.5%] → 0/37 (0.0%) [0.0%, 9.5%] |
| gen-v0.2-holdout | claude-150 (`run_20260925T212034Z_bbee49`) | claude q-v0.2+claude-prompt-v1 | v0.1+at0.55 | missing_evidence | PASS | 10/150 | 0 | 7 | 3 | 37/150 (24.7%) [18.0%, 32.4%] → 37/150 (24.7%) [18.0%, 32.4%] | 0/37 (0.0%) [0.0%, 9.5%] → 0/37 (0.0%) [0.0%, 9.5%] |
| gen-v0.2-holdout | claude-150 (`run_20260925T212034Z_bbee49`) | claude q-v0.2+claude-prompt-v1 | v0.1+at0.55 | contradiction+missing_evidence | PASS | 13/150 | 0 | 10 | 3 | 37/150 (24.7%) [18.0%, 32.4%] → 37/150 (24.7%) [18.0%, 32.4%] | 0/37 (0.0%) [0.0%, 9.5%] → 0/37 (0.0%) [0.0%, 9.5%] |
| gen-v0.3-holdout | jev-q-v0.3 (`run_20260927T072144Z_12e1e4`) | jev q-v0.3 | v0.1+at0.81 | contradiction | PASS | 33/1000 | 0 | 16 | 17 | 244/1000 (24.4%) [21.8%, 27.2%] → 261/1000 (26.1%) [23.4%, 28.9%] | 0/244 (0.0%) [0.0%, 1.5%] → 0/261 (0.0%) [0.0%, 1.4%] |
| gen-v0.3-holdout | jev-q-v0.3 (`run_20260927T072144Z_12e1e4`) | jev q-v0.3 | v0.1+at0.81 | missing_evidence | PASS | 93/1000 | 0 | 40 | 53 | 244/1000 (24.4%) [21.8%, 27.2%] → 244/1000 (24.4%) [21.8%, 27.2%] | 0/244 (0.0%) [0.0%, 1.5%] → 0/244 (0.0%) [0.0%, 1.5%] |
| gen-v0.3-holdout | jev-q-v0.3 (`run_20260927T072144Z_12e1e4`) | jev q-v0.3 | v0.1+at0.81 | contradiction+missing_evidence | PASS | 123/1000 | 0 | 53 | 70 | 244/1000 (24.4%) [21.8%, 27.2%] → 261/1000 (26.1%) [23.4%, 28.9%] | 0/244 (0.0%) [0.0%, 1.5%] → 0/261 (0.0%) [0.0%, 1.4%] |
| gen-v0.3-shift | jev-q-v0.3-aware (`run_20260927T072949Z_bd430c`) | jev q-v0.3 | v0.2 | contradiction | PASS | 7/400 | 0 | 7 | 0 | 13/400 (3.2%) [1.7%, 5.5%] → 13/400 (3.2%) [1.7%, 5.5%] | 0/13 (0.0%) [0.0%, 24.7%] → 0/13 (0.0%) [0.0%, 24.7%] |
| gen-v0.3-shift | jev-q-v0.3-aware (`run_20260927T072949Z_bd430c`) | jev q-v0.3 | v0.2 | missing_evidence | PASS | 41/400 | 0 | 15 | 26 | 13/400 (3.2%) [1.7%, 5.5%] → 13/400 (3.2%) [1.7%, 5.5%] | 0/13 (0.0%) [0.0%, 24.7%] → 0/13 (0.0%) [0.0%, 24.7%] |
| gen-v0.3-shift | jev-q-v0.3-aware (`run_20260927T072949Z_bd430c`) | jev q-v0.3 | v0.2 | contradiction+missing_evidence | PASS | 47/400 | 0 | 21 | 26 | 13/400 (3.2%) [1.7%, 5.5%] → 13/400 (3.2%) [1.7%, 5.5%] | 0/13 (0.0%) [0.0%, 24.7%] → 0/13 (0.0%) [0.0%, 24.7%] |
| gold-v0.1 | groundtruth (`run_20260925T170825Z_440df0`) | groundtruth groundtruth | v0.1 | contradiction | PASS | 1/100 | 0 | 1 | 0 | 34/100 (34.0%) [24.8%, 44.2%] → 34/100 (34.0%) [24.8%, 44.2%] | 0/34 (0.0%) [0.0%, 10.3%] → 0/34 (0.0%) [0.0%, 10.3%] |
| gold-v0.1 | groundtruth (`run_20260925T170825Z_440df0`) | groundtruth groundtruth | v0.1 | missing_evidence | PASS | 0/100 | 0 | 0 | 0 | 34/100 (34.0%) [24.8%, 44.2%] → 34/100 (34.0%) [24.8%, 44.2%] | 0/34 (0.0%) [0.0%, 10.3%] → 0/34 (0.0%) [0.0%, 10.3%] |
| gold-v0.1 | groundtruth (`run_20260925T170825Z_440df0`) | groundtruth groundtruth | v0.1 | contradiction+missing_evidence | PASS | 1/100 | 0 | 1 | 0 | 34/100 (34.0%) [24.8%, 44.2%] → 34/100 (34.0%) [24.8%, 44.2%] | 0/34 (0.0%) [0.0%, 10.3%] → 0/34 (0.0%) [0.0%, 10.3%] |
| gold-v0.1 | jev-q-v0.2 (`run_20260925T170857Z_b95be9`) | jev q-v0.2 | v0.1+at0.89 | contradiction | FAIL | 6/100 | 2 (GOLD-CON-03, GOLD-CON-13) | 5 | 1 | 29/100 (29.0%) [20.4%, 38.9%] → 32/100 (32.0%) [23.0%, 42.1%] | 1/29 (3.4%) [0.1%, 17.8%] → 3/32 (9.4%) [2.0%, 25.0%] |
| gold-v0.1 | jev-q-v0.2 (`run_20260925T170857Z_b95be9`) | jev q-v0.2 | v0.1+at0.89 | missing_evidence | PASS | 5/100 | 0 | 5 | 0 | 29/100 (29.0%) [20.4%, 38.9%] → 29/100 (29.0%) [20.4%, 38.9%] | 1/29 (3.4%) [0.1%, 17.8%] → 1/29 (3.4%) [0.1%, 17.8%] |
| gold-v0.1 | jev-q-v0.2 (`run_20260925T170857Z_b95be9`) | jev q-v0.2 | v0.1+at0.89 | contradiction+missing_evidence | FAIL | 9/100 | 2 (GOLD-CON-03, GOLD-CON-13) | 8 | 1 | 29/100 (29.0%) [20.4%, 38.9%] → 32/100 (32.0%) [23.0%, 42.1%] | 1/29 (3.4%) [0.1%, 17.8%] → 3/32 (9.4%) [2.0%, 25.0%] |
| gold-v0.1 | rules (`run_20260925T170839Z_d3b427`) | rules rules-v0.1 | v0.1+at0.99 | contradiction | PASS | 0/100 | 0 | 0 | 0 | 20/100 (20.0%) [12.7%, 29.2%] → 20/100 (20.0%) [12.7%, 29.2%] | 6/20 (30.0%) [11.9%, 54.3%] → 6/20 (30.0%) [11.9%, 54.3%] |
| gold-v0.1 | rules (`run_20260925T170839Z_d3b427`) | rules rules-v0.1 | v0.1+at0.99 | missing_evidence | PASS | 0/100 | 0 | 0 | 0 | 20/100 (20.0%) [12.7%, 29.2%] → 20/100 (20.0%) [12.7%, 29.2%] | 6/20 (30.0%) [11.9%, 54.3%] → 6/20 (30.0%) [11.9%, 54.3%] |
| gold-v0.1 | rules (`run_20260925T170839Z_d3b427`) | rules rules-v0.1 | v0.1+at0.99 | contradiction+missing_evidence | PASS | 0/100 | 0 | 0 | 0 | 20/100 (20.0%) [12.7%, 29.2%] → 20/100 (20.0%) [12.7%, 29.2%] | 6/20 (30.0%) [11.9%, 54.3%] → 6/20 (30.0%) [11.9%, 54.3%] |
| gold-v0.1 | claude (`run_20260926T011730Z_f1852f`) | claude q-v0.2+claude-prompt-v1 | v0.1+at0.55 | contradiction | FAIL | 5/100 | 2 (GOLD-CON-03, GOLD-CON-13) | 3 | 2 | 30/100 (30.0%) [21.2%, 40.0%] → 34/100 (34.0%) [24.8%, 44.2%] | 1/30 (3.3%) [0.1%, 17.2%] → 3/34 (8.8%) [1.9%, 23.7%] |
| gold-v0.1 | claude (`run_20260926T011730Z_f1852f`) | claude q-v0.2+claude-prompt-v1 | v0.1+at0.55 | missing_evidence | PASS | 6/100 | 0 | 6 | 0 | 30/100 (30.0%) [21.2%, 40.0%] → 30/100 (30.0%) [21.2%, 40.0%] | 1/30 (3.3%) [0.1%, 17.2%] → 1/30 (3.3%) [0.1%, 17.2%] |
| gold-v0.1 | claude (`run_20260926T011730Z_f1852f`) | claude q-v0.2+claude-prompt-v1 | v0.1+at0.55 | contradiction+missing_evidence | FAIL | 11/100 | 2 (GOLD-CON-03, GOLD-CON-13) | 9 | 2 | 30/100 (30.0%) [21.2%, 40.0%] → 34/100 (34.0%) [24.8%, 44.2%] | 1/30 (3.3%) [0.1%, 17.2%] → 3/34 (8.8%) [1.9%, 23.7%] |
| gold-v0.1 | jev-q-v0.3 (`run_20260927T072623Z_ad6f44`) | jev q-v0.3 | v0.1+at0.81 | contradiction | FAIL | 5/100 | 2 (GOLD-CON-03, GOLD-CON-13) | 4 | 1 | 31/100 (31.0%) [22.1%, 41.0%] → 34/100 (34.0%) [24.8%, 44.2%] | 1/31 (3.2%) [0.1%, 16.7%] → 3/34 (8.8%) [1.9%, 23.7%] |
| gold-v0.1 | jev-q-v0.3 (`run_20260927T072623Z_ad6f44`) | jev q-v0.3 | v0.1+at0.81 | missing_evidence | PASS | 4/100 | 0 | 4 | 0 | 31/100 (31.0%) [22.1%, 41.0%] → 31/100 (31.0%) [22.1%, 41.0%] | 1/31 (3.2%) [0.1%, 16.7%] → 1/31 (3.2%) [0.1%, 16.7%] |
| gold-v0.1 | jev-q-v0.3 (`run_20260927T072623Z_ad6f44`) | jev q-v0.3 | v0.1+at0.81 | contradiction+missing_evidence | FAIL | 8/100 | 2 (GOLD-CON-03, GOLD-CON-13) | 7 | 1 | 31/100 (31.0%) [22.1%, 41.0%] → 34/100 (34.0%) [24.8%, 44.2%] | 1/31 (3.2%) [0.1%, 16.7%] → 3/34 (8.8%) [1.9%, 23.7%] |

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

  For example, on GOLD-CON-03 (a case where `medication_history` and the physician's note
  disagree about how long a methotrexate course ran, so ground truth marks
  `step_therapy_satisfied: false`), Jev q-v0.3 judged `step_therapy` at `p_yes=0.905` — above its
  own 0.81 operating point, its own misjudgment of the disputed course — while its
  `material_contradiction` probability was only `p_yes=0.270`: too low to trigger the 0.80
  HUMAN_REVIEW gate, but enough to trip the auto-block gate's 0.20 bar and force HUMAN_REVIEW
  anyway. With `contradiction` ablated that auto-block is gone, so the run becomes an unsafe
  `AUTO_PROCESS` (confirmed offline: `relay replay GOLD-CON-03 --traces
  evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset
  evals/gold --candidate-traces
  evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/traces.jsonl.gz`). GOLD-CON-13 is
  caught by the other half of the gate: Jev q-v0.3 judged `step_therapy` at `p_yes=0.849` (above
  0.81) and `material_contradiction` at `p_yes=0.820`, so the 0.80 HUMAN_REVIEW gate itself fired
  (confirmed offline: `relay replay GOLD-CON-13 --traces
  evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset
  evals/gold --candidate-traces
  evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/traces.jsonl.gz` prints `contradiction
  FIRED → passed`, not an auto-block). Across the three providers, the review gate held three of
  the six newly unsafe cases (Jev q-v0.2 and q-v0.3 on CON-13, Claude on CON-03) and the auto-block
  held the other three (Jev q-v0.2 and q-v0.3 on CON-03, Claude on CON-13), so the `contradiction`
  ablation needs both halves removed to show the effect. In both cases, the contradiction gate is
  what caught the provider's own judgment error, not an artificial floor a perfect judge would
  never need.
- **On the generated holdouts the contradiction auto-block costs correct automation.** Removing
  contradiction detection raises Jev's automation from 252/1000 to 277/1000 (q-v0.2,
  gen-v0.2-holdout) and from 244/1000 to 261/1000 (q-v0.3, gen-v0.3-holdout) with UAR still 0
  (0/277, 0/261), so every added automation was correct; the same ablations regress 12 and 16
  cases respectively. For rules on gen-v0.2-holdout (17), Claude's 150-case sample (3) and the
  aware shift run (7), it only regresses cases and leaves automation unchanged. This is a real
  trade-off, not a reason to remove the gate: the gold rows above show the same gate catching
  genuine provider judgment errors, and the generator's contradictions are template-derived (see
  Limitations), so the holdouts have few of the kinds of contradiction that fooled providers on
  gold.
- **The missing-evidence gate never changes an automation.** In all ten runs, removing it leaves
  automation and UAR exactly as they were and creates no newly unsafe case. For ground truth that
  is guaranteed: the documentation gate runs before the missing-evidence gate, and `GroundTruth`'s
  validator (`relay/cases/models.py`) ties `missing_evidence != NONE` to
  `documentation_complete: false`, so ground truth always stops at the documentation gate. Its
  missing-evidence ablation therefore changes 0 actions on any dataset (0/100 on gold). For
  providers the gate can act only on a bundle that calls documentation complete
  (`p_yes >= 0.6`) while naming a missing item at probability ≥ 0.7. In these runs every such
  case moved REQUEST_INFO → HUMAN_REVIEW and none became an automation, but that is an observed
  result, not a structural one. For Jev on the generated sets more of those moves are corrections
  than errors (q-v0.2 on gen-v0.2-holdout: 67 improved, 32 regressed of 100 changed; q-v0.3 on
  gen-v0.3-holdout: 53 and 40 of 93; the aware shift run: 26 and 15 of 41); for Claude's 150-case
  sample it is the other way round (3 improved, 7 regressed of 10), and on gold it only regresses
  (Jev q-v0.2 5, Claude 6, Jev q-v0.3 4).
- **Null results.** Five pairs change no action at all: rules × missing_evidence on
  gen-v0.2-holdout, ground truth × missing_evidence on gold, and all three rules ablations on
  gold. The rules baseline's 6 unsafe gold automations (6/20) are already automated with both gates
  in place, so removing a gate cannot add or remove them. The two missing_evidence nulls (rules,
  ground truth) follow the documentation-gate ordering above: every rules bundle that names a
  missing item at probability ≥ 0.7 also reports `documentation_complete < 0.6` (28/28 on gold,
  219/219 on the gen-v0.2 holdout), so the documentation gate always fires first and
  missing_evidence never gets a chance to change the outcome. The rules × contradiction nulls on
  gold follow a similar pattern: rules reports `material_contradiction p_yes=0.0` on 97/100 gold
  cases, including every CON case it automates unsafely; its 3 flagged cases (GOLD-CON-02,
  GOLD-TMP-17, GOLD-TMP-18) still end in HUMAN_REVIEW with the gate removed, because another gate
  (not contradiction) is what stops them.

**Caveats.** gold-v0.1 is not a blind test for q-v0.3 (see "Question set q-v0.3"). Claude's
gen-v0.2-holdout row is the 150-case deterministic sample (`--limit 150 --sample-seed 7`), not
the full set. Gold has 100 cases, so its intervals are wide (Jev q-v0.3's ablated UAR 3/34 has
a 95% interval of 1.9%–23.7%). The generated sets' contradictions come from templates (see
Limitations), which bears on how often a provider's contradiction signal is the last line of
defense there.

## Limitations

- The regression gate (G5) is relative to its baseline, so it cannot catch an unsafe automation
  the baseline already makes: a case that both the baseline and the candidate automate unsafely
  is not newly unsafe and does not fail the gate. `relay regression` surfaces it as STILL UNSAFE
  so it is visible, but reviewing it is on the reader, not the gate (see "Regression gate" above).
- Ten hand-written smoke cases plus template-generated dev and holdout sets. Generated wording
  comes from fixed phrase banks, so it exercises the policy logic and pipeline, not real-world
  document variety. Gold-set results (100 hand-written cases, `gold-v0.1`) are in "Gold set" above.
- Date parts are treated as independent when composing step therapy, which is an approximation.
- Dates without a stated year count as unknown in the pipeline, so they reduce automation instead of
  being guessed. The generator doesn't produce them; gold-v0.1 does (TMP-14/15/16); see Gold set.
- gen-v0.2 has a residual contradiction tell: a day-precision, non-split MTX medication-history
  line predicts a contradiction roughly 81% of the time (never 100%), and the
  `NEVER_TAKEN_OTHER_DMARD` distractor wording has a weak base-rate skew of its own. Both bear on
  `material_contradiction` metrics above and on any rule-based baseline built from surface
  phrasing rather than genuine reasoning. The rules baseline is tested not to key on the tell
  (`tests/unit/test_rules_anti_shortcut.py`).
- rules-v0.1 is frozen (no pattern/logic changes) and reported above exactly as it runs on
  gen-v0.2; that decision was made before any gold-set results existed, and rules-v0.1 was run on
  the gold set (`gold-v0.1`) as-is and reported honestly (see "Gold set" above: 6/20 unsafe
  automations, all in category CON). Its patterns have demonstrated out-of-template failure modes
  on hand-written text — none of which occur on gen-v0.2's fixed templates — that would produce an
  unsafe `AUTO_PROCESS`: a response cue with no negation counts
  as a response (e.g. "tolerating it well without nausea or side effects"); a response cue on a
  neighbouring line about a different, non-MTX medication counts; the nearest date-role keyword
  has no distance bound, so a later, unrelated visit date can become the stop date; "since"
  anywhere on a line counts as a start; `mtx_ongoing` fires on symptom words (e.g. "due to ongoing
  nausea"); the diagnosis negators miss "ruled out", "does not meet criteria" and "no evidence of";
  a "line" is a whole paragraph because the generator joins sentences with a single space rather
  than a newline; and an ISO-shaped date embedded in a hyphenated ID (e.g. a claim number) can be
  matched as a real date.
- The Claude baseline is one run per dataset of a nondeterministic model (adaptive thinking at
  effort `low`), and its probabilities are self-reported, so a re-run would give somewhat different
  numbers. It ran on gen-v0.2's templated text first; `gold-v0.1` (100 hand-written cases) was its
  first test on hand-written documents (see "Gold set" above). Its holdout evidence is a 150-case
  deterministic sample (`--limit 150 --sample-seed 7`), not the full
  1,000-case set, because of a $10 API budget cap set mid-project; the dev evidence (400 cases) is
  complete. `step_therapy`'s multiplicative composition (see Baselines above) is a structural
  property of the shared composition code, not something specific to gen-v0.2, so it also
  depressed Claude's automation rate on gold: 0% at the raw run's default threshold and 30% at its
  dev-selected `--at 0.55` (1/30 unsafe), as detailed in "Gold set" above.
- The gold set (`gold-v0.1`, 100 cases) was authored and labelled by AI agents, not human domain
  experts, and has 20 cases per category, so per-category rates carry wide uncertainty.
- The `q-v0.2` question set asks for one treatment start date and one end date, so it cannot
  represent an interrupted course with a gap (two segments). `GOLD-TMP-17` is exactly this case,
  and it is the only unsafe automation Jev (q-v0.2) or Claude has on gold at its own threshold
  (see "Gold set" above). `q-v0.3` adds interruption and restart questions and was adopted on
  `gen-v0.3-dev` and confirmed on `gen-v0.3-holdout` (see "Question set q-v0.3" above). It still
  models only one interruption per course (the generator's variants (a)/(b)/(c)), not multiple
  holds and restarts, and it is not blind for `GOLD-TMP-17`/`GOLD-TMP-18` on gold. At its adopted
  dev threshold (0.81) it automates `GOLD-TMP-16` unsafely, a new negative result of the change
  (see "Question set q-v0.3" above).
- The authors, blind reviewer and adjudicator of `gold-v0.1` are all Claude agents, and
  `claude-opus-5` is also an evaluated provider on that same set (see "Gold set" above). The 100%
  blind agreement reflects one model family applying one guide consistently, not independent human
  validation. Claude's gold results may benefit from shared interpretation with its own labels, so
  a human review matters most for comparisons involving Claude.
- Actions are simulated. Relay never submits anything anywhere. Shadow mode's agreement section
  is the only part a real shadow deployment could compute; its promotion check uses ground truth,
  which a real deployment would not have (see "Shadow mode" above).

## Project docs

- [Project handoff](docs/RELAY_PROJECT_HANDOFF.md)
- [v0.1 design spec](docs/superpowers/specs/2026-09-24-relay-v0.1-milestone-design.md)
- [v0.1 implementation plan](docs/superpowers/plans/2026-09-24-relay-v0.1-milestone.md)
- [Phase 2A case generator design](docs/superpowers/specs/2026-09-25-phase2a-case-generator-design.md)
- [Phase 2A implementation plan](docs/superpowers/plans/2026-09-25-phase2a-case-generator.md)
- [Phase 2B evaluation depth design](docs/superpowers/specs/2026-09-25-phase2b-evaluation-depth-design.md)
- [Phase 2B implementation plan](docs/superpowers/plans/2026-09-25-phase2b-evaluation-depth.md)
- [Phase 2C rules baseline design](docs/superpowers/specs/2026-09-25-phase2c-rules-baseline-design.md)
- [Phase 2C implementation plan](docs/superpowers/plans/2026-09-25-phase2c-rules-baseline.md)
- [Phase 2D LLM baseline design](docs/superpowers/specs/2026-09-25-phase2d-llm-baseline-design.md)
- [Phase 2D implementation plan](docs/superpowers/plans/2026-09-25-phase2d-llm-baseline.md)
- [Phase 2E gold set design](docs/superpowers/specs/2026-09-25-phase2e-gold-set-design.md)
- [Phase 2E implementation plan](docs/superpowers/plans/2026-09-25-phase2e-gold-set.md)
- [Phase 3A replay design](docs/superpowers/specs/2026-09-26-phase3a-replay-design.md)
- [Phase 3A implementation plan](docs/superpowers/plans/2026-09-26-phase3a-replay.md)
- [Phase 3B regression gate design](docs/superpowers/specs/2026-09-26-phase3b-regression-gate-design.md)
- [Phase 3B implementation plan](docs/superpowers/plans/2026-09-26-phase3b-regression-gate.md)
- [Phase 3C shadow mode design](docs/superpowers/specs/2026-09-26-phase3c-shadow-mode-design.md)
- [Phase 3C implementation plan](docs/superpowers/plans/2026-09-26-phase3c-shadow-mode.md)
- [Phase 3D design (q-v0.3, policy shift, parallelism)](docs/superpowers/specs/2026-09-26-phase3d-questions-and-policy-shift-design.md)
- [Phase 3D1 implementation plan](docs/superpowers/plans/2026-09-26-phase3d1-generator-policy-questions.md)
- [Phase 3D2 implementation plan](docs/superpowers/plans/2026-09-26-phase3d2-experiments.md)
- [Phase 3E gate ablation design](docs/superpowers/specs/2026-09-27-phase3e-ablation-design.md)
- [Phase 3E implementation plan](docs/superpowers/plans/2026-09-27-phase3e-ablation.md)
