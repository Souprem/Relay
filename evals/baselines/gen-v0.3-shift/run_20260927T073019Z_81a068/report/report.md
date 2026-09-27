# Relay evaluation report — run_20260927T073019Z_81a068

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260927T073019Z_81a068`
- Dataset: `gen-v0.3-shift` (manifest hash `sha256:3f5a9c1cad24cf0ddd8c446999bc4c5e382503c65f1a6d8c54a8a2daf9710e53`)
- Provider: `rules` · model `rules-v0.1` · client n/a
- Question set: `rules-v0.1` (hash `sha256:5bd96c08e7c29353d55a180c4f465a2523a1f04563e31a4af0170fb1d9d92add`)
- Policy version: `v0.2` · policy text hash `sha256:1903451ebdb0a69adb1c7d40ea761297fdb54721cdab4585d668925332d0d8fb`
- Thresholds version: `v0.2`
- Relay commit: `6124ed3aec41ce138c58ac28d335bcc0be35cc61`

## Action metrics

```text
Relay eval — run run_20260927T073019Z_81a068
provider rules (rules-v0.1) · policy v0.2 · dataset gen-v0.3-shift · n=400
  Correct action rate       261/400 (65.2%)
  Automation rate           50/400 (12.5%)
  Request-info rate         207/400 (51.7%)
  Human escalation rate     143/400 (35.8%)
  Unsafe automation rate    6/50 (12.0%)
  Invalid outputs           0
  Latency p50 / p95         0 ms / 0 ms
  Cost                      $0.0000000 total, $0.0000000 per case

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         97.5%
  step_therapy              62.5%
  documentation_complete    97.2%
  material_contradiction    89.0%
  missing_evidence          97.2%
```

## Confusion matrices

Evaluation only: rows are the ground-truth answer, columns the provider's answer (yes/no at p_yes >= 0.5; the missing-evidence choice by its top answer). Invalid bundles excluded: 0.

### diagnosis_support

| truth / predicted | yes | no |
|---|---|---|
| yes | 369 | 0 |
| no | 10 | 21 |

### step_therapy

| truth / predicted | yes | no |
|---|---|---|
| yes | 101 | 15 |
| no | 135 | 149 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 286 | 0 |
| no | 11 | 103 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 33 | 11 |
| no | 33 | 323 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 21 | 0 | 0 | 0 | 0 | 10 |
| TREATMENT_HISTORY | 0 | 30 | 0 | 0 | 0 | 1 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 52 | 0 |
| NONE | 0 | 0 | 0 | 0 | 0 | 286 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

Partial missing_evidence distributions (probabilities summing to less than 1; the unassigned mass counts as 0 on every label in the Brier score): 124 of 400.

### diagnosis_support

n = 400 · Brier 0.006 · ECE 0.013

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 10 | 0.500 | 0.000 | -0.500 | low n (< 20) |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 390 | 1.000 | 1.000 | +0.000 |  |

### step_therapy

n = 400 · Brier 0.166 · ECE 0.164

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 169 | 0.500 | 0.254 | -0.246 |  |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 231 | 1.000 | 0.896 | -0.104 |  |

### documentation_complete

n = 400 · Brier 0.077 · ECE 0.128

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 124 | 0.500 | 0.911 | +0.411 |  |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 276 | 1.000 | 1.000 | +0.000 |  |

### material_contradiction

n = 400 · Brier 0.110 · ECE 0.110

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 400 | 1.000 | 0.890 | -0.110 |  |

### missing_evidence

n = 400 · Brier 0.105 · ECE 0.128

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 0 | — | — | — | empty |
| [0.5, 0.6) | 124 | 0.500 | 0.911 | +0.411 |  |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 276 | 1.000 | 1.000 | +0.000 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 50 | 12.5% | 6/50 (12.0%) | 35.8% | 65.2% |  |
| 0.55 | 50 | 12.5% | 6/50 (12.0%) | 35.8% | 65.2% |  |
| 0.60 | 50 | 12.5% | 6/50 (12.0%) | 35.8% | 65.2% |  |
| 0.65 | 50 | 12.5% | 6/50 (12.0%) | 35.8% | 65.2% |  |
| 0.70 | 50 | 12.5% | 6/50 (12.0%) | 35.8% | 65.2% |  |
| 0.75 | 50 | 12.5% | 6/50 (12.0%) | 35.8% | 65.2% |  |
| 0.80 | 50 | 12.5% | 6/50 (12.0%) | 35.8% | 65.2% |  |
| 0.85 | 50 | 12.5% | 6/50 (12.0%) | 35.8% | 65.2% |  |
| 0.90 | 50 | 12.5% | 6/50 (12.0%) | 35.8% | 65.2% |  |
| 0.95 | 50 | 12.5% | 6/50 (12.0%) | 35.8% | 65.2% |  |

No threshold meets the ceiling (UAR <= 1.0% with at least one AUTO_PROCESS); nothing selected.
Frontier is flat across all thresholds.
The UAR ceiling binds: at least one automated threshold's UAR exceeds it.

The selection above is computed on this run's own data. For a held-out report, the threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample selection is shown for reference only.

## Latency and cost

- Latency: p50 0 ms · p95 0 ms
- Estimated cost: $0.0000000 total · $0.0000000 per case

## Limitations

- Synthetic data only. Generated documents come from fixed templates and phrase banks, so they exercise the policy logic and pipeline, not real-world document variety.
- Expected actions are derived from the generator's ground-truth facts through the same engine; they are not independent expert labels.
- Step therapy is composed from date parts treated as independent, which is an approximation.
- Generator and pipeline conventions apply: month-only dates are judged conservatively, and the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).
- Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset must be confirmed on held-out data.
- gen-v0.2 has a residual contradiction tell: a day-precision, non-split MTX medication-history line predicts a contradiction roughly 81% of the time (never 100%), and the NEVER_TAKEN_OTHER_DMARD distractor wording has a weak base-rate skew of its own. Both bear on material_contradiction metrics and on any rule-based baseline built from surface phrasing.
