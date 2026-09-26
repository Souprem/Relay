# Phase 3D Design: q-v0.3 (interrupted courses), the policy-shift experiment, and the parallelism experiment

- **Date:** 2026-09-26
- **Status:** Approved by controller (Phase 3 design is delegated by the user).
- **Depends on:** 3A replay, 3B regression gate, 3C shadow mode, and the 2A generator.
- **Parent:** handoff Phase 3: "Add policy versioning/distribution-shift experiment". The handoff's experiments include #4 (parallelism: 1/5/10/20 narrow decisions, p50/p95 latency and cost) and #5 (distribution shift: "introduce policy_v5 with an added prior-treatment requirement; compare policy-aware behavior with stale/naive logic"). This sub-project also takes the Phase 2 finding that question set q-v0.2 cannot represent an interrupted methotrexate course. That gap caused GOLD-TMP-17, the only unsafe automation for Jev and for Claude on gold.
- **Budget:** Jev spend ≤ $1.00 for the whole of 3D. The per-run estimate is printed before each run. No Claude calls.

## 1. Honesty constraint: gold is no longer blind for this change

The README rule says "No question … change may be motivated by gold results". q-v0.3 **is** motivated by a gold finding: GOLD-TMP-17's interrupted course. The rule's own remedy is new data under a new dataset id. So:
- Develop q-v0.3 on a new generated dev set, and evaluate it once on a new generated holdout. That holdout is the primary evidence.
- q-v0.3 runs on gold-v0.1 exactly once, for completeness. The README states that gold is **not a blind test for q-v0.3** on interruption and restart cases (GOLD-TMP-17 and GOLD-TMP-18), because the change was motivated by one of them. Gold results for q-v0.3 are reported beside that caveat, never as headline evidence.
- gold-v0.1 is not edited.

## 2. Generator gen-v0.3

`GENERATOR_VERSION` stays `gen-v0.2` for the frozen gen-v0.2 manifests. The generator gains a `version` parameter so both versions can be generated, and `relay generate --generator gen-v0.3` selects the new one. gen-v0.2 output must stay byte-identical; the existing `--verify` tests guard this.

What gen-v0.3 adds to `CaseFacts`:
- **Interrupted courses (rule D8 from the gold guide).** `mtx_segments: tuple[tuple[date, date|None], ...] | None`. Two segments are separated by a documented hold, pause or stop reason (infection, surgery, travel, lab abnormality) and a restart. The label rule: `step_therapy_satisfied` requires a **single** segment of at least `policy.min_weeks*7` days, plus a documented inadequate response or intolerance. The renderer writes the hold and restart in the note and, when present, in the medication history (two rows).
  - Scenario mix in gen-v0.3 datasets: about 20% of taken-MTX cases are interrupted.
  - Within those, the split is roughly equal across three variants: (a) no segment reaches the minimum even though the total does, the TMP-17 pattern; (b) the later segment qualifies, the TMP-18 pattern; (c) the earlier segment qualifies.
  - Everything else follows the gen-v0.2 scenario distributions.
- **Course recency** (for the policy shift). `mtx_end` values are drawn so that about 25% of taken-MTX courses ended more than 365 days before `as_of_date`. This is recorded in facts, and it doesn't change v0.1 labels.
- **Policy-aware labelling.** `labels.py` derives `step_therapy_satisfied` from facts **given a policy**, so the same facts can be labelled under immunara-v0.1 and immunara-v0.2. Each case's `ground_truth.json` is labelled under the case's own `policy_id`.

**Datasets.** Manifests are committed; case directories are git-ignored, as with gen-v0.2.

| Dataset | Seed | Count | Policy | Purpose |
|---|---|---|---|---|
| `gen-v0.3-dev` | 3 | 400 | immunara-v0.1 | q-v0.3 development and threshold selection |
| `gen-v0.3-holdout` | 4 | 1000 | immunara-v0.1 | one-shot q-v0.2 vs q-v0.3 evaluation |
| `gen-v0.3-shift` | 5 | 400 | immunara-v0.2 | policy-shift experiment (one shot) |

The generation audit test (tests/unit/test_generation_audit.py) is extended to gen-v0.3:
- no label words leak into documents
- the interrupted variants appear in the stated proportions, ±5 percentage points
- labels agree with rule D8 on hand-checked fixtures

## 3. Policy immunara-v0.2 ("policy_v5" in the handoff)

- `policies/immunara-v0.2.md` is v0.1's text plus one added prior-treatment requirement: *"The qualifying methotrexate course must have been ongoing, or have ended, within the 12 months (365 days) before the request date."*
- `AuthorizationPolicy` gains `max_days_since_therapy: int | None = None`, which is None for v0.1 and 365 for v0.2. The registry entry is `immunara-v0.2`, and `latest_policy_for("immunara-v0.1")` now returns v0.2.
- Thresholds gets a `v0.2` entry with the same values as v0.1. No tuning is involved; a thresholds object is needed per policy version.
- The engine itself needs no new gate. Recency is part of `step_therapy`, which is composed in code, so the stale-vs-aware difference lives entirely in composition. That keeps the experiment clean.

## 4. Question set q-v0.3

These are added to q-v0.2. Every q-v0.2 question keeps the same text, so q-v0.2 answers remain comparable.
- `mtx_interrupted` (Noul): "Do the documents describe the patient's own methotrexate being held, paused or stopped and later restarted?" The true criterion names a hold or stop followed by resumption. The false criterion covers one continuous course, never taken, or a relative's treatment.
- `mtx_pause_{month,day,year}`: the date the first segment was held or stopped.
- `mtx_restart_{month,day,year}`: the date it was resumed.
- `mtx_start_*` still asks for the **first** start; `mtx_end_status` and `mtx_end_*` still ask for the **final** status and stop. The existing wording already means this; q-v0.3 adds "(the first time, if it was restarted)" and "(the last time, if it was restarted)" to those instructions. Those two text edits are why q-v0.3 is a new version. They change the question-set hash.
- That makes 19 questions per case, up from 12.

**Composition** (`relay/decisions/step_therapy.py` + `composition.py`), written as p(consecutive segment ≥ N):
- p = (1 − p_int) · P(first start → final end ≥ N) + p_int · P(first start → pause ≥ N **or** restart → final end ≥ N)
- The two segment events are combined with inclusion-exclusion, under the same independence approximation as today. The approximation is documented in the docstring.
- When the policy has `max_days_since_therapy`, a qualifying segment must also end (ongoing counts as ending at as_of) no more than that many days before `as_of_date`. The recency test is applied per candidate pair, with the same conservative month-range rule.
- Derivations record the segment probabilities.
- q-v0.2 composition is unchanged. It is the q-v0.2 code path, selected by question-set version.

**Stale vs aware composition from the same answers.** A new function, `recompose(bundle, *, policy, question_set_version) -> DecisionBundle`, rebuilds `step_therapy` from the stored raw date-part answers in `bundle.raw_answers` under a given policy. Nothing is called. The policy-shift experiment then needs only one Jev run: stale = compose under immunara-v0.1, aware = compose under immunara-v0.2, from identical answers.

## 5. Experiments (paid Jev runs listed exactly; all others offline)

Jev cost per case is about $0.00015 (Phase 2 measured about $0.21 for 1,400 cases). Every paid run first prints `jev estimate: n cases × q questions ≈ $X` and aborts if the cumulative 3D Jev spend, recorded in a small ledger `results/jev-spend-3d.json` (git-ignored), would exceed $1.00. This is a lightweight counter in the CLI for Jev runs launched with `--jev-budget-usd`. It reuses `relay/evaluation/budget.py` with provider `jev`.

**E1: q-v0.3 adoption (policy v0.1).**
1. Paid: Jev q-v0.2 and Jev q-v0.3 on `gen-v0.3-dev` (400 + 400).
2. Offline: sweep, choose t* per question set on dev, and run `relay regression` with baseline q-v0.2@t*₂ and candidate q-v0.3@t*₃ on dev.
3. Adoption rule, decided on dev only:
   - ADOPT q-v0.3 if its dev correct-action rate is higher and the dev regression gate PASSes (0 newly unsafe).
   - Otherwise KEEP q-v0.2.
   - Record `evals/baselines/gen-v0.3-dev/adoption.txt` in the same format as the 2B adoption file.
4. Paid, once: both question sets on `gen-v0.3-holdout` (1000 + 1000). Report, compare, and run the regression gate q-v0.2 → q-v0.3 at the dev-selected thresholds.
5. Paid, once: q-v0.3 on gold-v0.1 (100). Run regression vs the committed q-v0.2 gold run, with the §1 caveat.
6. Replay GOLD-TMP-17 across the two question sets and paste the output in the README. It shows whether the interruption is now read.

**E2: policy shift.**
1. Paid, once: Jev q-v0.3 on `gen-v0.3-shift` (400), run with the case policy immunara-v0.2.
2. Offline: build the stale run with `recompose(..., policy=immunara-v0.1)` and the aware run with `recompose(..., policy=immunara-v0.2)`. Score both against the v0.2 ground truth.
3. Report UAR, automation and correct rate for each, plus the list of **stale-only unsafe automations**: approvals that pass v0.1's rule but violate the new recency requirement.
4. Gate `stale → aware` with `relay regression` (both as simulated traces written via `--out`).
5. Shadow demo: stale as the simulated incumbent, aware as the shadow candidate, giving a PROMOTE/HOLD verdict.
6. Also add the rules baseline, network-free, on the shift set for context. rules-v0.1 has no recency rule, so it is naive by construction and is reported as such.

**E3: parallelism (handoff experiment 4).**
- Paid: 40 cases from gen-v0.3-dev, fixed sample seed 11, run with Jev under four question configurations: 1, 5, 10 and 20 narrow decisions per case.
  - The 1/5/10 configurations are prefixes of a fixed ordering of the q-v0.3 questions.
  - "20" is q-v0.3's 19 questions plus one duplicated question (a controlled padding question, disclosed).
- Measure per-case wall latency p50 and p95, per-question latency where the client exposes it, and estimated cost per case.
- These are latency-only runs: their decisions are not scored, because partial question sets can't form a bundle. A new `relay bench` command writes `evals/baselines/bench/parallelism.json` and `.md`.
- Concurrency: the existing client call submits all questions of one case in one `system_one` request. If the client already parallelizes internally, the experiment measures exactly the handoff's question, "does adding narrow decisions cost latency".
- If the TypeSafe client does not support a single call with k questions, the bench measures k sequential calls versus one batched call and says so.
- About 40 × (1+5+10+20) question-evaluations: a few cents.

**Budget arithmetic.** E1 is 2,900 cases × about $0.00015 × (19/12 for q-v0.3) ≈ $0.55. E2 is about $0.09. E3 is under $0.05. The total, about $0.70, is under the $1.00 cap. If measured costs come in higher, drop E1 step 4's q-v0.2 holdout re-run first: the q-v0.2 baseline on gen-v0.3-holdout can't be replaced from existing runs, so the fallback is to evaluate q-v0.3 alone and report that the q-v0.2 comparison was skipped.

## 6. CLI changes

- `relay generate --generator gen-v0.2|gen-v0.3`, default gen-v0.2.
- `relay eval --jev-budget-usd N --jev-ledger PATH` wraps Jev runs with the spend counter. It is required for paid Jev runs in 3D.
- `relay recompose --traces FILE --dataset DIR --policy ID --out DIR` writes a simulated run: stored raw answers recomposed under the policy. The manifest has `mode="simulated"`, `source_run_id`, and the policy used.
- `relay bench --dataset DIR --limit 40 --sample-seed 11 --sizes 1,5,10,20 --jev-budget-usd N`.

## 7. Committed artifacts

- All runs go under `evals/baselines/gen-v0.3-{dev,holdout,shift}/…` and `gold-v0.1/<q-v0.3 run>/`, in the standard bundle format.
- Adoption file.
- `evals/regression/gates.json` gains:
  - reproduce gates for the new runs (`requires_generated: true`)
  - the adoption gate q-v0.2 → q-v0.3 on gen-v0.3-holdout, which must PASS if ADOPTed
  - the `stale → aware` shift gate, which must PASS
- The CI workflow regenerates the gen-v0.3 datasets too, with the manifest flags.
- The README gets two sections, "Question set q-v0.3 (interrupted courses)" and "Policy shift (immunara-v0.2)", plus a parallelism table. All numbers are pasted from artifacts, including negative results.

## 8. Testing

- **Generator:** gen-v0.2 byte-identical (existing verify); gen-v0.3 audit; D8 labelling fixtures; v0.1 vs v0.2 labels on the same facts.
- **Composition:** the interrupted-course cases reproduce TMP-17 and TMP-18 on fixture answers; recency; q-v0.2 path unchanged (a golden test on the committed gen-v0.2 traces: recomposing under v0.1 with q-v0.2 equals the stored step_therapy to 1e-9).
- **`recompose`:** stale and aware from the same bundle.
- **Budget counter:** a tmp ledger.
- **Bench:** Jev fake with a latency stub.
- **Everything else:** existing gates and reproduce guards stay green.

## 9. Definition of done

- Tests, ruff and the committed gates pass, including `--strict-generated`.
- E1–E3 artifacts and README sections are committed, with real numbers.
- Total 3D Jev spend ≤ $1.00, reported.
- No Claude calls.
