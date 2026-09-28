# Relay evaluation report — run_20260927T071912Z_cdaf0c

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260927T071912Z_cdaf0c`
- Dataset: `gen-v0.3-dev` (manifest hash `sha256:ae3dc2f88e0966889aee2193dc822bee3389ade3ffce85641a9f59495557d5ad`)
- Provider: `jev` · model `jev-1.13.0` · client `typesafe-sdk==0.7.1`
- Question set: `q-v0.3` (hash `sha256:4589d78b40d2be56216766beec111882b7f96c761be99d1f6ba218e3bfd2979c`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `796044c959dddf2a399d2a539ba5cf0a0e6517a2`

## Action metrics

```text
Relay eval — run run_20260927T071912Z_cdaf0c
provider jev (jev-1.13.0) · policy v0.1 · dataset gen-v0.3-dev · n=400
  Correct action rate       276/400 (69.0%)
  Automation rate           17/400 (4.2%)
  Request-info rate         112/400 (28.0%)
  Human escalation rate     271/400 (67.8%)
  Unsafe automation rate    0/17 (0.0%)
  Invalid outputs           0
  Latency p50 / p95         196 ms / 257 ms
  Cost                      $0.0691268 total, $0.0001728 per case

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         100.0%
  step_therapy              97.2%
  documentation_complete    93.5%
  material_contradiction    98.0%
  missing_evidence          83.5%
```

## Confusion matrices

Evaluation only: rows are the ground-truth answer, columns the provider's answer (yes/no at p_yes >= 0.5; the missing-evidence choice by its top answer). Invalid bundles excluded: 0.

### diagnosis_support

| truth / predicted | yes | no |
|---|---|---|
| yes | 357 | 0 |
| no | 0 | 43 |

### step_therapy

| truth / predicted | yes | no |
|---|---|---|
| yes | 157 | 1 |
| no | 10 | 232 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 291 | 0 |
| no | 26 | 83 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 50 | 5 |
| no | 3 | 342 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 43 | 0 | 0 | 0 | 0 | 0 |
| TREATMENT_HISTORY | 0 | 22 | 0 | 0 | 0 | 0 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 44 | 0 |
| NONE | 0 | 66 | 0 | 0 | 0 | 225 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

Partial missing_evidence distributions (probabilities summing to less than 1; the unassigned mass counts as 0 on every label in the Brier score): 11 of 400.

### diagnosis_support

n = 400 · Brier 0.001 · ECE 0.029

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 6 | 0.860 | 1.000 | +0.140 | low n (< 20) |
| [0.9, 1.0] | 394 | 0.972 | 1.000 | +0.028 |  |

### step_therapy

n = 400 · Brier 0.016 · ECE 0.048

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 9 | 0.536 | 0.222 | -0.314 | low n (< 20) |
| [0.6, 0.7) | 5 | 0.641 | 0.600 | -0.041 | low n (< 20) |
| [0.7, 0.8) | 5 | 0.760 | 0.600 | -0.160 | low n (< 20) |
| [0.8, 0.9) | 29 | 0.865 | 1.000 | +0.135 |  |
| [0.9, 1.0] | 352 | 0.968 | 1.000 | +0.032 |  |

### documentation_complete

n = 400 · Brier 0.039 · ECE 0.084

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 17 | 0.552 | 0.647 | +0.095 | low n (< 20) |
| [0.6, 0.7) | 16 | 0.643 | 0.250 | -0.393 | low n (< 20) |
| [0.7, 0.8) | 10 | 0.745 | 0.200 | -0.545 | low n (< 20) |
| [0.8, 0.9) | 7 | 0.870 | 1.000 | +0.130 | low n (< 20) |
| [0.9, 1.0] | 350 | 0.945 | 1.000 | +0.055 |  |

### material_contradiction

n = 400 · Brier 0.032 · ECE 0.118

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 15 | 0.555 | 0.667 | +0.111 | low n (< 20) |
| [0.6, 0.7) | 18 | 0.642 | 0.889 | +0.247 | low n (< 20) |
| [0.7, 0.8) | 24 | 0.750 | 0.958 | +0.208 |  |
| [0.8, 0.9) | 160 | 0.861 | 1.000 | +0.139 |  |
| [0.9, 1.0] | 183 | 0.924 | 1.000 | +0.076 |  |

### missing_evidence

n = 400 · Brier 0.190 · ECE 0.078

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 8 | 0.475 | 0.375 | -0.100 | low n (< 20) |
| [0.5, 0.6) | 37 | 0.549 | 0.459 | -0.090 |  |
| [0.6, 0.7) | 39 | 0.653 | 0.385 | -0.268 |  |
| [0.7, 0.8) | 41 | 0.744 | 0.707 | -0.036 |  |
| [0.8, 0.9) | 81 | 0.851 | 0.951 | +0.100 |  |
| [0.9, 1.0] | 194 | 0.958 | 0.995 | +0.037 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 114 | 28.5% | 0/114 (0.0%) | 43.5% | 93.2% |  |
| 0.55 | 114 | 28.5% | 0/114 (0.0%) | 43.5% | 93.2% |  |
| 0.60 | 114 | 28.5% | 0/114 (0.0%) | 43.5% | 93.2% |  |
| 0.65 | 114 | 28.5% | 0/114 (0.0%) | 43.5% | 93.2% |  |
| 0.70 | 114 | 28.5% | 0/114 (0.0%) | 43.5% | 93.2% |  |
| 0.75 | 114 | 28.5% | 0/114 (0.0%) | 43.5% | 93.2% |  |
| 0.80 | 114 | 28.5% | 0/114 (0.0%) | 43.5% | 93.2% |  |
| 0.81 | 114 | 28.5% | 0/114 (0.0%) | 43.5% | 93.2% | selected |
| 0.85 | 112 | 28.0% | 0/112 (0.0%) | 44.0% | 92.8% |  |
| 0.90 | 101 | 25.2% | 0/101 (0.0%) | 46.8% | 90.0% |  |
| 0.95 | 17 | 4.2% | 0/17 (0.0%) | 67.8% | 69.0% |  |

Selected operating point: auto_process >= 0.81 (automation 28.5%, UAR 0/114, correct action 93.2%; ceiling UAR <= 1.0%)
The UAR ceiling does not bind at any threshold.

The selection above is computed on this run's own data. For a held-out report, the threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample selection is shown for reference only.

## Latency and cost

- Latency: p50 196 ms · p95 257 ms
- Estimated cost: $0.0691268 total · $0.0001728 per case

## Limitations

- Synthetic data only. Generated documents come from fixed templates and phrase banks, so they exercise the policy logic and pipeline, not real-world document variety.
- Expected actions are derived from the generator's ground-truth facts through the same engine; they are not independent expert labels.
- Step therapy is composed from date parts treated as independent, which is an approximation.
- Generator and pipeline conventions apply: month-only dates are judged conservatively, and the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).
- Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset must be confirmed on held-out data.
- gen-v0.2 has a residual contradiction tell: a day-precision, non-split MTX medication-history line predicts a contradiction roughly 81% of the time (never 100%), and the NEVER_TAKEN_OTHER_DMARD distractor wording has a weak base-rate skew of its own. Both bear on material_contradiction metrics and on any rule-based baseline built from surface phrasing.
