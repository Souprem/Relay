# Relay evaluation report — run_20260927T071846Z_e950c0

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260927T071846Z_e950c0`
- Dataset: `gen-v0.3-dev` (manifest hash `sha256:ae3dc2f88e0966889aee2193dc822bee3389ade3ffce85641a9f59495557d5ad`)
- Provider: `jev` · model `jev-1.13.0` · client `typesafe-sdk==0.7.1`
- Question set: `q-v0.2` (hash `sha256:89717c795a2dfea7efe30e038fb483c6d4ed72d343bfbfcefeabfc6483d7a4aa`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `796044c959dddf2a399d2a539ba5cf0a0e6517a2`

## Action metrics

```text
Relay eval — run run_20260927T071846Z_e950c0
provider jev (jev-1.13.0) · policy v0.1 · dataset gen-v0.3-dev · n=400
  Correct action rate       318/400 (79.5%)
  Automation rate           68/400 (17.0%)
  Request-info rate         113/400 (28.2%)
  Human escalation rate     219/400 (54.8%)
  Unsafe automation rate    4/68 (5.9%)
  Invalid outputs           0
  Latency p50 / p95         182 ms / 231 ms
  Cost                      $0.0451614 total, $0.0001129 per case

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         100.0%
  step_therapy              93.0%
  documentation_complete    93.0%
  material_contradiction    98.2%
  missing_evidence          83.8%
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
| yes | 158 | 0 |
| no | 28 | 214 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 291 | 0 |
| no | 28 | 81 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 50 | 5 |
| no | 2 | 343 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 43 | 0 | 0 | 0 | 0 | 0 |
| TREATMENT_HISTORY | 0 | 22 | 0 | 0 | 0 | 0 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 44 | 0 |
| NONE | 0 | 65 | 0 | 0 | 0 | 226 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

Partial missing_evidence distributions (probabilities summing to less than 1; the unassigned mass counts as 0 on every label in the Brier score): 12 of 400.

### diagnosis_support

n = 400 · Brier 0.001 · ECE 0.029

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 5 | 0.856 | 1.000 | +0.144 | low n (< 20) |
| [0.9, 1.0] | 395 | 0.972 | 1.000 | +0.028 |  |

### step_therapy

n = 400 · Brier 0.060 · ECE 0.037

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 8 | 0.548 | 0.500 | -0.048 | low n (< 20) |
| [0.6, 0.7) | 4 | 0.627 | 0.750 | +0.123 | low n (< 20) |
| [0.7, 0.8) | 3 | 0.770 | 1.000 | +0.230 | low n (< 20) |
| [0.8, 0.9) | 13 | 0.862 | 0.923 | +0.061 | low n (< 20) |
| [0.9, 1.0] | 372 | 0.974 | 0.941 | -0.033 |  |

### documentation_complete

n = 400 · Brier 0.039 · ECE 0.081

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 18 | 0.551 | 0.444 | -0.106 | low n (< 20) |
| [0.6, 0.7) | 14 | 0.651 | 0.357 | -0.294 | low n (< 20) |
| [0.7, 0.8) | 12 | 0.747 | 0.250 | -0.497 | low n (< 20) |
| [0.8, 0.9) | 6 | 0.883 | 1.000 | +0.117 | low n (< 20) |
| [0.9, 1.0] | 350 | 0.944 | 1.000 | +0.056 |  |

### material_contradiction

n = 400 · Brier 0.032 · ECE 0.120

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 16 | 0.558 | 0.875 | +0.317 | low n (< 20) |
| [0.6, 0.7) | 14 | 0.642 | 0.714 | +0.072 | low n (< 20) |
| [0.7, 0.8) | 30 | 0.754 | 0.967 | +0.213 |  |
| [0.8, 0.9) | 160 | 0.862 | 1.000 | +0.138 |  |
| [0.9, 1.0] | 180 | 0.924 | 1.000 | +0.076 |  |

### missing_evidence

n = 400 · Brier 0.193 · ECE 0.072

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 8 | 0.480 | 0.625 | +0.145 | low n (< 20) |
| [0.5, 0.6) | 33 | 0.544 | 0.394 | -0.150 |  |
| [0.6, 0.7) | 38 | 0.643 | 0.421 | -0.222 |  |
| [0.7, 0.8) | 47 | 0.751 | 0.723 | -0.028 |  |
| [0.8, 0.9) | 80 | 0.850 | 0.925 | +0.075 |  |
| [0.9, 1.0] | 194 | 0.958 | 0.995 | +0.036 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 131 | 32.8% | 18/131 (13.7%) | 39.0% | 88.2% |  |
| 0.55 | 131 | 32.8% | 18/131 (13.7%) | 39.0% | 88.2% |  |
| 0.60 | 131 | 32.8% | 18/131 (13.7%) | 39.0% | 88.2% |  |
| 0.65 | 131 | 32.8% | 18/131 (13.7%) | 39.0% | 88.2% |  |
| 0.70 | 131 | 32.8% | 18/131 (13.7%) | 39.0% | 88.2% |  |
| 0.75 | 131 | 32.8% | 18/131 (13.7%) | 39.0% | 88.2% |  |
| 0.80 | 131 | 32.8% | 18/131 (13.7%) | 39.0% | 88.2% |  |
| 0.85 | 131 | 32.8% | 18/131 (13.7%) | 39.0% | 88.2% |  |
| 0.90 | 131 | 32.8% | 18/131 (13.7%) | 39.0% | 88.2% |  |
| 0.95 | 68 | 17.0% | 4/68 (5.9%) | 54.8% | 79.5% |  |
| 0.97 | 10 | 2.5% | 0/10 (0.0%) | 69.2% | 67.0% | selected |

Selected operating point: auto_process >= 0.97 (automation 2.5%, UAR 0/10, correct action 67.0%; ceiling UAR <= 1.0%)
The UAR ceiling binds: at least one automated threshold's UAR exceeds it.

The selection above is computed on this run's own data. For a held-out report, the threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample selection is shown for reference only.

## Latency and cost

- Latency: p50 182 ms · p95 231 ms
- Estimated cost: $0.0451614 total · $0.0001129 per case

## Limitations

- Synthetic data only. Generated documents come from fixed templates and phrase banks, so they exercise the policy logic and pipeline, not real-world document variety.
- Expected actions are derived from the generator's ground-truth facts through the same engine; they are not independent expert labels.
- Step therapy is composed from date parts treated as independent, which is an approximation.
- Generator and pipeline conventions apply: month-only dates are judged conservatively, and the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).
- Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset must be confirmed on held-out data.
- gen-v0.2 has a residual contradiction tell: a day-precision, non-split MTX medication-history line predicts a contradiction roughly 81% of the time (never 100%), and the NEVER_TAKEN_OTHER_DMARD distractor wording has a weak base-rate skew of its own. Both bear on material_contradiction metrics and on any rule-based baseline built from surface phrasing.
