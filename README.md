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
engine routes to `HUMAN_REVIEW`, and refusals are counted below: zero, across all 560 Claude cases
run (10 smoke, 400 dev, 150 holdout sample).

**Budget.** All of Phase 2D and 2E's Claude spend is capped at $10 (tightened mid-run from the
sub-project's original $60 guard by an explicit user decision), tracked in
[`claude-spend.json`](evals/baselines/claude-spend.json); the pre-bulk-run projection (made after
the smoke run, under the original $60 guard, before the cap was tightened) is in
[`claude-projection.txt`](evals/baselines/claude-projection.txt). Under the $10 cap, only dev (400
cases, the full set) and a deterministic 150-case sample of holdout (`--limit 150 --sample-seed
7`) were run; the full 1,000-case holdout and a dedicated sync latency sample were not run, so
latency below comes from the 10-case smoke sync run only (already a low-sample figure). The gold
set (Phase 2E) is unaffected and keeps its own reserved headroom; see below for the final numbers.

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

Total Claude spend (ledger): $7.1500 across 8 entries (two are $0 bookkeeping entries from
recovering the interrupted dev batch — one settles the original, superseded reservation to zero,
one settles a stray $0 reservation left by a killed re-attach; neither reflects real spend);
unsettled reservations: none. Remaining headroom under the $10 cap after this task: $2.8500,
against an estimated gold-set (Phase 2E, 100 cases) reserve of roughly $1.36 (100 × the measured
dev batch cost/case of $0.01091 × a 1.25 safety margin).

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

## Limitations

- Ten hand-written smoke cases plus template-generated dev and holdout sets. Generated wording
  comes from fixed phrase banks, so it exercises the policy logic and pipeline, not real-world
  document variety. No gold set yet (Phase 2E); the rules-only and Claude baselines are above.
- Date parts are treated as independent when composing step therapy, which is an approximation.
- Dates without a stated year count as unknown in the pipeline, so they reduce automation instead of
  being guessed. The generator doesn't produce them.
- gen-v0.2 has a residual contradiction tell: a day-precision, non-split MTX medication-history
  line predicts a contradiction roughly 81% of the time (never 100%), and the
  `NEVER_TAKEN_OTHER_DMARD` distractor wording has a weak base-rate skew of its own. Both bear on
  `material_contradiction` metrics above and on any rule-based baseline built from surface
  phrasing rather than genuine reasoning. The rules baseline is tested not to key on the tell
  (`tests/unit/test_rules_anti_shortcut.py`).
- rules-v0.1 is frozen (no pattern/logic changes) and reported above exactly as it runs on
  gen-v0.2; that decision was made before any gold-set results exist, and rules-v0.1 will be run
  on the future gold set (Phase 2E) as-is and reported honestly. Its patterns have demonstrated
  out-of-template failure modes on hand-written text — none of which occur on gen-v0.2's fixed
  templates — that would produce an unsafe `AUTO_PROCESS`: a response cue with no negation counts
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
  numbers. Like the other providers it has only seen gen-v0.2's templated text; the Phase 2E gold
  set will be its first test on hand-written documents. Its holdout evidence is a 150-case
  deterministic sample (`--limit 150 --sample-seed 7`), not the full 1,000-case set, because of a
  $10 API budget cap set mid-project; the dev evidence (400 cases) is complete. `step_therapy`'s
  multiplicative composition (see Baselines above) is a structural property of the shared
  composition code, not something specific to gen-v0.2, so it will also depress Claude's automation
  rate on the gold set.
- Actions are simulated. Relay never submits anything anywhere.

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
