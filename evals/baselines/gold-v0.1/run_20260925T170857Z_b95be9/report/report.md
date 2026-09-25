# Relay evaluation report — run_20260925T170857Z_b95be9

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260925T170857Z_b95be9`
- Dataset: `gold-v0.1` (no dataset manifest)
- Provider: `jev` · model `jev-1.13.0` · client `typesafe-sdk==0.7.1`
- Question set: `q-v0.2` (hash `sha256:89717c795a2dfea7efe30e038fb483c6d4ed72d343bfbfcefeabfc6483d7a4aa`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `2dbcf2c9d24449c2faae54dda5467c69666aa63c`

## Action metrics

```text
Relay eval — run run_20260925T170857Z_b95be9
provider jev (jev-1.13.0) · policy v0.1 · dataset gold-v0.1 · n=100
  Correct action rate       82/100 (82.0%)
  Automation rate           18/100 (18.0%)
  Request-info rate         32/100 (32.0%)
  Human escalation rate     50/100 (50.0%)
  Unsafe automation rate    0/18 (0.0%)
  Invalid outputs           0
  Latency p50 / p95         163 ms / 249 ms
  Cost                      $0.0115131 total, $0.0001151 per case

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         98.0%
  step_therapy              89.0%
  documentation_complete    91.0%
  material_contradiction    95.0%
  missing_evidence          91.0%
```

## Confusion matrices

Evaluation only: rows are the ground-truth answer, columns the provider's answer (yes/no at p_yes >= 0.5; the missing-evidence choice by its top answer). Invalid bundles excluded: 0.

### diagnosis_support

| truth / predicted | yes | no |
|---|---|---|
| yes | 88 | 0 |
| no | 2 | 10 |

### step_therapy

| truth / predicted | yes | no |
|---|---|---|
| yes | 49 | 1 |
| no | 10 | 40 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 65 | 0 |
| no | 9 | 26 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 11 | 3 |
| no | 2 | 84 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 10 | 0 | 0 | 0 | 0 | 0 |
| TREATMENT_HISTORY | 0 | 12 | 0 | 0 | 0 | 1 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 12 | 0 |
| NONE | 1 | 7 | 0 | 0 | 0 | 57 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

Partial missing_evidence distributions (probabilities summing to less than 1; the unassigned mass counts as 0 on every label in the Brier score): 2 of 100.

### diagnosis_support

n = 100 · Brier 0.011 · ECE 0.049

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 1 | 0.570 | 0.000 | -0.570 | low n (< 20) |
| [0.6, 0.7) | 1 | 0.680 | 0.000 | -0.680 | low n (< 20) |
| [0.7, 0.8) | 2 | 0.730 | 1.000 | +0.270 | low n (< 20) |
| [0.8, 0.9) | 2 | 0.885 | 1.000 | +0.115 | low n (< 20) |
| [0.9, 1.0] | 94 | 0.969 | 1.000 | +0.031 |  |

### step_therapy

n = 100 · Brier 0.075 · ECE 0.049

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 4 | 0.553 | 0.250 | -0.303 | low n (< 20) |
| [0.6, 0.7) | 3 | 0.635 | 0.667 | +0.032 | low n (< 20) |
| [0.7, 0.8) | 5 | 0.735 | 0.600 | -0.135 | low n (< 20) |
| [0.8, 0.9) | 2 | 0.834 | 0.500 | -0.334 | low n (< 20) |
| [0.9, 1.0] | 86 | 0.980 | 0.953 | -0.026 |  |

### documentation_complete

n = 100 · Brier 0.063 · ECE 0.035

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 3 | 0.513 | 0.333 | -0.180 | low n (< 20) |
| [0.6, 0.7) | 3 | 0.637 | 0.667 | +0.030 | low n (< 20) |
| [0.7, 0.8) | 4 | 0.752 | 0.500 | -0.252 | low n (< 20) |
| [0.8, 0.9) | 6 | 0.845 | 0.833 | -0.012 | low n (< 20) |
| [0.9, 1.0] | 84 | 0.943 | 0.964 | +0.021 |  |

### material_contradiction

n = 100 · Brier 0.040 · ECE 0.086

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 3 | 0.553 | 0.667 | +0.113 | low n (< 20) |
| [0.6, 0.7) | 3 | 0.663 | 0.333 | -0.330 | low n (< 20) |
| [0.7, 0.8) | 4 | 0.765 | 0.750 | -0.015 | low n (< 20) |
| [0.8, 0.9) | 31 | 0.867 | 0.968 | +0.100 |  |
| [0.9, 1.0] | 59 | 0.931 | 1.000 | +0.069 |  |

### missing_evidence

n = 100 · Brier 0.120 · ECE 0.067

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 2 | 0.460 | 0.500 | +0.040 | low n (< 20) |
| [0.5, 0.6) | 8 | 0.532 | 0.375 | -0.157 | low n (< 20) |
| [0.6, 0.7) | 3 | 0.667 | 1.000 | +0.333 | low n (< 20) |
| [0.7, 0.8) | 9 | 0.733 | 0.778 | +0.044 | low n (< 20) |
| [0.8, 0.9) | 20 | 0.846 | 0.950 | +0.104 |  |
| [0.9, 1.0] | 58 | 0.967 | 1.000 | +0.033 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 33 | 33.0% | 2/33 (6.1%) | 35.0% | 94.0% |  |
| 0.55 | 33 | 33.0% | 2/33 (6.1%) | 35.0% | 94.0% |  |
| 0.60 | 33 | 33.0% | 2/33 (6.1%) | 35.0% | 94.0% |  |
| 0.65 | 32 | 32.0% | 2/32 (6.2%) | 36.0% | 93.0% |  |
| 0.70 | 32 | 32.0% | 2/32 (6.2%) | 36.0% | 93.0% |  |
| 0.75 | 32 | 32.0% | 2/32 (6.2%) | 36.0% | 93.0% |  |
| 0.80 | 32 | 32.0% | 2/32 (6.2%) | 36.0% | 93.0% |  |
| 0.85 | 30 | 30.0% | 1/30 (3.3%) | 38.0% | 92.0% |  |
| 0.89 | 29 | 29.0% | 1/29 (3.4%) | 39.0% | 91.0% | --at |
| 0.90 | 28 | 28.0% | 1/28 (3.6%) | 40.0% | 90.0% |  |
| 0.94 | 20 | 20.0% | 0/20 (0.0%) | 48.0% | 84.0% | selected |
| 0.95 | 18 | 18.0% | 0/18 (0.0%) | 50.0% | 82.0% |  |

Selected operating point: auto_process >= 0.94 (automation 20.0%, UAR 0/20, correct action 84.0%; ceiling UAR <= 1.0%)
The UAR ceiling binds: at least one automated threshold's UAR exceeds it.

The selection above is computed on this run's own data. For a held-out report, the threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample selection is shown for reference only.

## Latency and cost

- Latency: p50 163 ms · p95 249 ms
- Estimated cost: $0.0115131 total · $0.0001151 per case

## Limitations

- Synthetic data only. Generated documents come from fixed templates and phrase banks, so they exercise the policy logic and pipeline, not real-world document variety.
- Expected actions are derived from the generator's ground-truth facts through the same engine; they are not independent expert labels.
- Step therapy is composed from date parts treated as independent, which is an approximation.
- Generator and pipeline conventions apply: month-only dates are judged conservatively, and the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).
- Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset must be confirmed on held-out data.
- gen-v0.2 has a residual contradiction tell: a day-precision, non-split MTX medication-history line predicts a contradiction roughly 81% of the time (never 100%), and the NEVER_TAKEN_OTHER_DMARD distractor wording has a weak base-rate skew of its own. Both bear on material_contradiction metrics and on any rule-based baseline built from surface phrasing.
