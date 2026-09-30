# Relay

[![CI](https://github.com/Souprem/Relay/actions/workflows/ci.yml/badge.svg)](https://github.com/Souprem/Relay/actions/workflows/ci.yml)

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

**Live dashboard: <https://souprem.github.io/Relay/>**

Relay asks one question: **how can probabilistic AI judgments be turned into safe autonomous
workflow actions?** It works on synthetic prior-authorization cases. TypeSafe's
[Jev](https://docs.typesafe.ai/) answers narrow, typed questions about each case (is the diagnosis
supported, when did methotrexate start and stop, is there a contradiction) and returns
probabilities. A deterministic, versioned policy engine, not the model, then decides whether the
case is `AUTO_PROCESS`, `REQUEST_INFO` or `HUMAN_REVIEW`. Every decision is traced, so it can be
replayed, compared against another configuration, and gated in CI.

```text
Jev:   What does the available evidence most likely establish?
Relay: What is software permitted to do given those judgments and their confidence?
```

## Architecture

```text
 synthetic case documents (physician notes, medication history, labs, fax cover, insurance card)
                 │
                 ▼
 narrow judgments ── Jev (native probabilities) | Claude (stated confidence) | rules (0 / 0.5 / 1)
                 │   diagnosis · documentation · contradiction · missing evidence · MTX dates
                 ▼
 composition in code ── date parts → P(a methotrexate course of ≥ 12 weeks); no model arithmetic
                 │
                 ▼
 policy engine (versioned) ── provider → age → contradiction → documentation
                 │            → missing evidence → auto_process bar → human review
                 ▼
 action: AUTO_PROCESS | REQUEST_INFO | HUMAN_REVIEW
                 │
                 ▼
 trace (JSONL: case hash, model and question-set versions, policy, thresholds, raw answers, gate path)
                 │
                 ├──► relay replay       one case, stored run vs. a candidate, every difference labelled
                 ├──► relay regression   run-level gate: fails on a newly unsafe automation (CI)
                 └──► shadow mode        candidate proposes actions, never applies them; PROMOTE / HOLD
```

## Headline results

Each provider runs at its own `auto_process` threshold, chosen on a dev set before the holdout or
gold run. "Unsafe" means the engine auto-processed a case whose expected action was not
`AUTO_PROCESS`. The upper bound is the 95% Clopper-Pearson limit on the unsafe-automation rate, as
printed in the committed regression and ablation reports.

| Dataset | n | Provider | `auto_process` | Correct action | Automation | Unsafe / auto | Unsafe 95% upper bound |
|---|---|---|---|---|---|---|---|
| `gen-v0.2-holdout` | 1000 | Jev `q-v0.2` | 0.89 | 895/1000 (89.5%) | 252/1000 (25.2%) | 0/252 | 1.5% |
| `gen-v0.2-holdout` | 1000 | Rules `rules-v0.1` | 0.99 (flat) | 667/1000 (66.7%) | 134/1000 (13.4%) | 0/134 | 2.7% |
| `gen-v0.3-holdout` | 1000 | Jev `q-v0.3` | 0.81 | 921/1000 (92.1%) | 244/1000 (24.4%) | 0/244 | 1.5% |
| `gold-v0.1` | 100 | Jev `q-v0.2` | 0.89 | 91/100 (91.0%) | 29/100 (29.0%) | 1/29 (3.4%) | 17.8% |
| `gold-v0.1` | 100 | Claude `claude-opus-5` | 0.55 | 93/100 (93.0%) | 30/100 (30.0%) | 1/30 (3.3%) | 17.2% |
| `gold-v0.1` | 100 | Rules `rules-v0.1` | 0.99 (flat) | 61/100 (61.0%) | 20/100 (20.0%) | 6/20 (30.0%) | 54.3% |
| `gold-v0.1` | 100 | Jev `q-v0.3` (not blind) | 0.81 | 94/100 (94.0%) | 31/100 (31.0%) | 1/31 (3.2%) | 16.7% |

- **Gold exposes what the templates don't.** Jev (`q-v0.2`) and Claude each have one unsafe gold
  automation, and it is the same case: `GOLD-TMP-17`, an interrupted methotrexate course read as
  one 133-day course, because `q-v0.2` has no way to express a gap. All 6 rules failures are in
  the conflicting-evidence category, while the rules have 0 unsafe automations on the generated
  holdout.
- **The q-v0.3 fix.** `q-v0.3` adds seven questions about pauses and restarts. It was adopted on
  a new dev set by a rule fixed in advance, then run once on `gen-v0.3-holdout`: correct actions
  went from 694 to 921 of 1000, automation from 17 to 244, and unsafe automations from 1/17 to
  0/244. On gold it fails the regression gate: `GOLD-TMP-16` becomes newly unsafe at the lower
  0.81 threshold.
- **Policy shift.** The same stored Jev answers on `gen-v0.3-shift` (n=400, labelled under the new
  12-month recency rule in `immunara-v0.2`) give 3/16 unsafe automations when composed under the
  old policy (stale) and 0/13 under the new one (aware). The stale → aware gate passes with 0
  newly unsafe and 0 regressed.
- **Ablation.** Removing contradiction detection makes `GOLD-CON-03` and `GOLD-CON-13` newly unsafe
  for all three model providers on gold (for example Jev `q-v0.3`: 1/31 → 3/34). It creates no
  newly unsafe case on the generated sets, and removing the missing-evidence gate never changes an
  automation.

Caveats: all data is synthetic; gold labels were written and adjudicated by AI agents (Claude),
not reviewed by clinicians; Claude's holdout evidence is a 150-case sample, so it is not in the
table; gold is not a blind test for `q-v0.3`.

## What I found

**Confidence gating automated about a quarter of held-out cases with no unsafe approvals observed.**
Jev `q-v0.3` at 0.81 on `gen-v0.3-holdout` auto-processed 244/1000 (24.4%) of cases, 0/244
unsafe (95% upper bound 1.5%), and chose the correct action for 921/1000 (92.1%). On
`gen-v0.2-holdout` the rules baseline automated 134/1000 (13.4%) with 667/1000 (66.7%) correct,
against 252/1000 (25.2%) and 895/1000 (89.5%) for Jev `q-v0.2`. The cases are synthetic and
template-generated. ([Baselines](docs/RESULTS.md#baselines))

**The evaluation loop found a real design flaw, and the fix held on a fresh holdout.**
`GOLD-TMP-17`, an interrupted methotrexate course, was auto-approved unsafely by both Jev `q-v0.2`
at 0.89 and Claude at 0.55. The cause was my question design: `q-v0.2` asks for one start date and
one end date, so a paused course reads as one long course. `q-v0.3` adds questions about pauses and
restarts; on `gen-v0.3-holdout`, run once, correct actions went from 694 to 921 of 1000. Gold is
not a blind test for this change, and on gold `GOLD-TMP-16` became newly unsafe when the threshold
dropped from 0.97 to 0.81.
([Question set q-v0.3](docs/RESULTS.md#question-set-q-v03-interrupted-courses))

**The contradiction gate is doing real work, and it has a cost.** With contradiction detection
disabled, `GOLD-CON-03` and `GOLD-CON-13` become newly unsafe on gold for all 3 model configurations. On
the holdouts it only costs automation: Jev `q-v0.2` goes from 252 to 277 of 1000 automated and Jev
`q-v0.3` from 244 to 261 of 1000, still 0/277 and 0/261 unsafe. Disabling the missing-evidence gate
changed no automation and no unsafe count in any of the 10 runs, a null result.
([Gate ablation](docs/RESULTS.md#gate-ablation))

**Policy-aware logic matters when the policy changes.** Under `immunara-v0.2`'s new 12-month
recency rule, on 400 cases, the same stored Jev answers composed under the old policy gave 3/16
unsafe automations and under the new policy 0/13. The stale-to-aware gate passes, and shadow mode
recommends PROMOTE. ([Policy shift](docs/RESULTS.md#policy-shift-immunara-v02))

**At similar gold accuracy, Jev cost about 1/89th as much per case as Claude Opus 5.** On gold,
with the same questions, Claude got 93/100 correct with 30 automated and 1 unsafe; Jev `q-v0.2` got
91/100 with 29 automated and 1 unsafe. The 95% intervals on correct actions (86.1–97.1% and
83.6–95.8%) overlap. This 100-case comparison does not establish equivalence or a clear winner.
Claude's gold run cost $1.56 at batch prices, $0.0156 per case; Jev's `q-v0.3` gold run, with more
questions per case, cost $0.0175, $0.000175 per case. ([Gold set](docs/RESULTS.md#gold-set))

## Cost and speed

Cost per case on gold: Jev $0.00017 · Claude Opus 5 $0.016 (batch), about 89× more, at similar gold accuracy.

| Dataset | Claude Opus 5 (batch), per case | Jev, per case | Claude ÷ Jev |
|---|---|---|---|
| `gold-v0.1` | $0.0156 | $0.000175 (`q-v0.3`) | 89× |
| `gold-v0.1` | $0.0156 | $0.000115 (`q-v0.2`) | 136× |
| `gen-v0.2-dev` | $0.0110 | $0.000112 (`q-v0.2`) | 98× |
| `gen-v0.2-holdout` | $0.0164 (150-case sample) | $0.000112 (`q-v0.2`) | 146× |

On the same 10 smoke cases, Claude Opus 5 (sync) took 5,169 ms p50 and 6,781 ms p95 per case; Jev
q-v0.1 took 178 ms and 411 ms. In the parallelism bench (40 calls per size), Jev's p50 stayed
between 177 and 191 ms with 1 to 20 questions per call. The Claude figure is a 10-case sample.

Total spend: Claude $8.71 (ledger); Jev $0.715 ($0.502 in the Phase 3D ledger and $0.214 in trace
estimates for the Phase 2 runs). Costs come from the committed spend ledgers
([`claude-spend.json`](evals/baselines/claude-spend.json),
[`jev-spend-3d.json`](evals/baselines/jev-spend-3d.json)) or, where a run is in no ledger, from its
traces' estimated cost. The gen-v0.2-dev Claude figure includes the 22 cancelled cases' re-run.

- Claude was run as Opus 5 (claude-opus-5), the most capable and most expensive tier. Cheaper
  Claude models (Sonnet, Haiku) were not tested and would narrow the gap.
- Claude's batch figures already include the 50% Message Batches discount; at non-batch prices
  they would be about twice as high.
- “Similar accuracy” means not distinguishable on 100 gold cases, not proven equal.
- Prices are as billed in September 2026: Claude at list prices as of 2026-09-25, Jev at $0.042
  per million input tokens.
- The Claude latency sample is 10 cases (one sync run on the smoke set); Claude's batch runs record
  no latency.
- Jev's Phase 2 runs are in no ledger; their cost is the sum of the traces' own estimates, which
  match the ledger wherever a Jev run is in one.

## What's inside

Each item links to its section in [docs/RESULTS.md](docs/RESULTS.md), which has the full methods,
tables and artifact links.

- [Evaluation and calibration](docs/RESULTS.md#evaluation): dev/holdout protocol with rules fixed
  in advance, threshold sweeps, per-decision Brier score and ECE, confusion matrices.
- [Baselines](docs/RESULTS.md#baselines): a network-free rules provider and a Claude LLM provider
  asked the same questions, through the same engine.
- [Gold set](docs/RESULTS.md#gold-set): 100 individually written cases in five categories, with
  a blind second labelling pass and adjudication.
- [Replay](docs/RESULTS.md#replay): one case from a stored trace beside a candidate (today's
  engine, another policy or threshold, another run, or a live call), with every difference labelled.
- [Regression gate and CI](docs/RESULTS.md#regression-gate): run-level gate with confidence
  intervals, waivers, and 20 committed gates that CI runs on every push with no provider keys.
- [Shadow mode](docs/RESULTS.md#shadow-mode): a simulated incumbent and a shadow candidate whose
  actions are recorded but never applied, ending in PROMOTE or HOLD.
- [Question-set versioning](docs/RESULTS.md#question-set-q-v03-interrupted-courses): `q-v0.3`
  for interrupted courses, adopted on dev and confirmed once on holdout.
- [Policy shift](docs/RESULTS.md#policy-shift-immunara-v02): stored answers recomposed under a
  new policy version, stale versus aware.
- [Parallelism](docs/RESULTS.md#parallelism-narrow-decisions-per-call): Jev latency with 1 to 20
  questions per call.
- [Gate ablation](docs/RESULTS.md#gate-ablation): what the contradiction and missing-evidence
  gates are worth, over 30 run × ablation pairs.
- Spend guard: a [budget guard and ledger](docs/RESULTS.md#commands) that refuses a paid run
  projected to exceed its cap, and the [Jev spend record](docs/RESULTS.md#phase-3d-jev-spend).

## Quickstart

Everything below runs offline, with no API keys. The `groundtruth` and `rules` providers make no
network calls, and replay and regression read committed traces. The `env -u ...` prefix and
`--env-file .no-such.env` make sure no key is picked up from your shell or a `.env` file.

```bash
uv sync

# Smoke set (10 cases) through the full pipeline: ground-truth facts, then the rules baseline
env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env eval \
    --dataset evals/smoke --provider groundtruth
env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env eval \
    --dataset evals/smoke --provider rules

# Replay GOLD-TMP-17: Jev's committed gold run beside Claude's (exit 0)
env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env replay GOLD-TMP-17 \
    --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz \
    --dataset evals/gold \
    --candidate-traces evals/baselines/gold-v0.1/run_20260926T011730Z_f1852f/traces.jsonl.gz

# Regression gate FAIL demo: Jev's gold decisions re-decided at 0.89 automate GOLD-TMP-17 (exit 4)
env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env regression \
    --dataset evals/gold \
    --baseline evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz \
    --candidate-at 0.89

# Every committed gate, as CI runs them (exit 0)
env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env regression \
    --config evals/regression/gates.json

# Tests (no network; live tests are deselected by default)
uv run pytest -q
```

On a fresh clone the gates that need generated datasets report SKIPPED, because the case folders
are git-ignored. Regenerate them with the commands in
[Generated datasets](docs/RESULTS.md#generated-datasets) to run all 20.

**With a Jev key.** Put `TYPESAFE_API_KEY` in `.env` (see `.env.example`), then run the smoke set
against Jev. The committed reference run of these 10 cases cost about $0.001.

```bash
uv run relay eval --dataset evals/smoke --provider jev --policy v0.1
```

## Dashboard (local)

`web/` is a static Next.js site over the committed results: the headline table, all 110 gold
and smoke cases with each provider's judgments and gate path, every committed run's metrics,
frontier and calibration, the CI gates, and the experiments. It computes nothing itself: `relay
export-site` writes its data from the committed artifacts, offline and with no keys. Node 22.12
or newer is needed.

The same build is published automatically to GitHub Pages at
<https://souprem.github.io/Relay/> on every push to `main`
(`.github/workflows/pages.yml`), with `NEXT_PUBLIC_BASE_PATH=/Relay` set so links and assets
resolve under that prefix. Publishing restores the generated datasets from their committed
manifests and exports with `--strict-generated`, so every gate and experiment breakdown is
included. Locally, leave `NEXT_PUBLIC_BASE_PATH` unset.

```bash
# From the repository root: export the data (writes web/public/data, git-ignored)
env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env export-site \
    --out web/public/data

cd web
npm ci
npm run dev        # http://localhost:3000
npm run build      # static site in web/out/
npm run typecheck && npm run lint && npm test
```

Gates and the interrupted-course breakdown that need a generated dataset show as skipped until
you regenerate it (see [Generated datasets](docs/RESULTS.md#generated-datasets)).

## Repository layout

```text
relay/      the package: case models, decision providers, policy engine, evaluation, traces, CLI
tests/      unit and integration tests (offline by default)
evals/      smoke and gold datasets, generated-dataset manifests, committed baselines, regression gates
policies/   the synthetic payer policies (immunara-v0.1, immunara-v0.2)
scripts/    one-off analysis and table scripts behind the committed artifacts
docs/       RESULTS.md: detailed results and methods
.github/    CI workflow (offline gates, no secrets)
web/        the local dashboard (Next.js static site over the exported results)
```

## Limitations

The known limits (template-generated wording, AI-authored gold labels, a gate that is relative to
its baseline, simulated actions) are listed in
[docs/RESULTS.md#limitations](docs/RESULTS.md#limitations).

## License

[MIT](LICENSE). The synthetic data, policies and cases in this repository are fictional.
