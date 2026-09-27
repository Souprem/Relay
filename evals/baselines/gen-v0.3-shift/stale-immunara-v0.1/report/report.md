# Relay evaluation report — run_20260927T072948Z_e5915e

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260927T072948Z_e5915e`
- Dataset: `gen-v0.3-shift` (manifest hash `sha256:3f5a9c1cad24cf0ddd8c446999bc4c5e382503c65f1a6d8c54a8a2daf9710e53`)
- Provider: `jev` · model `jev-1.13.0` · client `typesafe-sdk==0.7.1`
- Question set: `q-v0.3` (hash `sha256:4589d78b40d2be56216766beec111882b7f96c761be99d1f6ba218e3bfd2979c`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `6124ed3aec41ce138c58ac28d335bcc0be35cc61`

## Action metrics

```text
Relay eval — run run_20260927T072948Z_e5915e
provider jev (jev-1.13.0) · policy v0.1 · dataset gen-v0.3-shift · n=400
  Correct action rate       294/400 (73.5%)
  Automation rate           16/400 (4.0%)
  Request-info rate         130/400 (32.5%)
  Human escalation rate     254/400 (63.5%)
  Unsafe automation rate    3/16 (18.8%)
  Invalid outputs           0
  Latency p50 / p95         189 ms / 247 ms
  Cost                      $0.0695668 total, $0.0001739 per case

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         100.0%
  step_therapy              90.8%
  documentation_complete    94.0%
  material_contradiction    98.5%
  missing_evidence          81.8%
```

## Confusion matrices

Evaluation only: rows are the ground-truth answer, columns the provider's answer (yes/no at p_yes >= 0.5; the missing-evidence choice by its top answer). Invalid bundles excluded: 0.

### diagnosis_support

| truth / predicted | yes | no |
|---|---|---|
| yes | 369 | 0 |
| no | 0 | 31 |

### step_therapy

| truth / predicted | yes | no |
|---|---|---|
| yes | 115 | 1 |
| no | 36 | 248 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 286 | 0 |
| no | 24 | 90 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 40 | 4 |
| no | 2 | 354 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 31 | 0 | 0 | 0 | 0 | 0 |
| TREATMENT_HISTORY | 0 | 31 | 0 | 0 | 0 | 0 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 52 | 0 |
| NONE | 0 | 73 | 0 | 0 | 0 | 213 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

Partial missing_evidence distributions (probabilities summing to less than 1; the unassigned mass counts as 0 on every label in the Brier score): 19 of 400.

### diagnosis_support

n = 400 · Brier 0.001 · ECE 0.027

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 2 | 0.870 | 1.000 | +0.130 | low n (< 20) |
| [0.9, 1.0] | 398 | 0.973 | 1.000 | +0.027 |  |

### step_therapy

n = 400 · Brier 0.072 · ECE 0.051

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 6 | 0.544 | 0.500 | -0.044 | low n (< 20) |
| [0.6, 0.7) | 9 | 0.646 | 0.444 | -0.202 | low n (< 20) |
| [0.7, 0.8) | 4 | 0.748 | 0.000 | -0.748 | low n (< 20) |
| [0.8, 0.9) | 17 | 0.866 | 0.941 | +0.075 | low n (< 20) |
| [0.9, 1.0] | 364 | 0.973 | 0.934 | -0.039 |  |

### documentation_complete

n = 400 · Brier 0.032 · ECE 0.081

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 13 | 0.548 | 0.385 | -0.163 | low n (< 20) |
| [0.6, 0.7) | 8 | 0.644 | 0.125 | -0.519 | low n (< 20) |
| [0.7, 0.8) | 9 | 0.747 | 0.111 | -0.636 | low n (< 20) |
| [0.8, 0.9) | 7 | 0.871 | 0.857 | -0.014 | low n (< 20) |
| [0.9, 1.0] | 363 | 0.944 | 1.000 | +0.056 |  |

### material_contradiction

n = 400 · Brier 0.030 · ECE 0.120

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 9 | 0.554 | 0.889 | +0.334 | low n (< 20) |
| [0.6, 0.7) | 18 | 0.641 | 0.722 | +0.081 | low n (< 20) |
| [0.7, 0.8) | 33 | 0.755 | 1.000 | +0.245 |  |
| [0.8, 0.9) | 150 | 0.861 | 1.000 | +0.139 |  |
| [0.9, 1.0] | 190 | 0.923 | 1.000 | +0.077 |  |

### missing_evidence

n = 400 · Brier 0.208 · ECE 0.104

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 8 | 0.476 | 0.625 | +0.149 | low n (< 20) |
| [0.5, 0.6) | 25 | 0.550 | 0.200 | -0.350 |  |
| [0.6, 0.7) | 37 | 0.645 | 0.405 | -0.239 |  |
| [0.7, 0.8) | 55 | 0.752 | 0.600 | -0.152 |  |
| [0.8, 0.9) | 96 | 0.849 | 0.958 | +0.109 |  |
| [0.9, 1.0] | 179 | 0.966 | 0.989 | +0.023 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 93 | 23.2% | 17/93 (18.3%) | 44.2% | 85.8% |  |
| 0.55 | 93 | 23.2% | 17/93 (18.3%) | 44.2% | 85.8% |  |
| 0.60 | 93 | 23.2% | 17/93 (18.3%) | 44.2% | 85.8% |  |
| 0.65 | 93 | 23.2% | 17/93 (18.3%) | 44.2% | 85.8% |  |
| 0.70 | 93 | 23.2% | 17/93 (18.3%) | 44.2% | 85.8% |  |
| 0.75 | 93 | 23.2% | 17/93 (18.3%) | 44.2% | 85.8% |  |
| 0.80 | 93 | 23.2% | 17/93 (18.3%) | 44.2% | 85.8% |  |
| 0.85 | 93 | 23.2% | 17/93 (18.3%) | 44.2% | 85.8% |  |
| 0.90 | 82 | 20.5% | 17/82 (20.7%) | 47.0% | 83.0% |  |
| 0.95 | 16 | 4.0% | 3/16 (18.8%) | 63.5% | 73.5% |  |

No threshold meets the ceiling (UAR <= 1.0% with at least one AUTO_PROCESS); nothing selected.
The UAR ceiling binds: at least one automated threshold's UAR exceeds it.

The selection above is computed on this run's own data. For a held-out report, the threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample selection is shown for reference only.

## Latency and cost

- Latency: p50 189 ms · p95 247 ms
- Estimated cost: $0.0695668 total · $0.0001739 per case

## Limitations

- Synthetic data only. Generated documents come from fixed templates and phrase banks, so they exercise the policy logic and pipeline, not real-world document variety.
- Expected actions are derived from the generator's ground-truth facts through the same engine; they are not independent expert labels.
- Step therapy is composed from date parts treated as independent, which is an approximation.
- Generator and pipeline conventions apply: month-only dates are judged conservatively, and the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).
- Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset must be confirmed on held-out data.
- gen-v0.2 has a residual contradiction tell: a day-precision, non-split MTX medication-history line predicts a contradiction roughly 81% of the time (never 100%), and the NEVER_TAKEN_OTHER_DMARD distractor wording has a weak base-rate skew of its own. Both bear on material_contradiction metrics and on any rule-based baseline built from surface phrasing.
