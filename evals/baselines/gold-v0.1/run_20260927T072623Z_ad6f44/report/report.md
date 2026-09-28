# Relay evaluation report — run_20260927T072623Z_ad6f44

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260927T072623Z_ad6f44`
- Dataset: `gold-v0.1` (no dataset manifest)
- Provider: `jev` · model `jev-1.13.0` · client `typesafe-sdk==0.7.1`
- Question set: `q-v0.3` (hash `sha256:4589d78b40d2be56216766beec111882b7f96c761be99d1f6ba218e3bfd2979c`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `4424c54269ed01b1bb7c716ace42310aaa1e3e80`

## Action metrics

```text
Relay eval — run run_20260927T072623Z_ad6f44
provider jev (jev-1.13.0) · policy v0.1 · dataset gold-v0.1 · n=100
  Correct action rate       65/100 (65.0%)
  Automation rate           1/100 (1.0%)
  Request-info rate         32/100 (32.0%)
  Human escalation rate     67/100 (67.0%)
  Unsafe automation rate    0/1 (0.0%)
  Invalid outputs           0
  Latency p50 / p95         175 ms / 256 ms
  Cost                      $0.0174972 total, $0.0001750 per case

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         98.0%
  step_therapy              90.0%
  documentation_complete    92.0%
  material_contradiction    94.0%
  missing_evidence          90.0%
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
| yes | 48 | 2 |
| no | 8 | 42 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 65 | 0 |
| no | 8 | 27 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 11 | 3 |
| no | 3 | 83 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 10 | 0 | 0 | 0 | 0 | 0 |
| TREATMENT_HISTORY | 0 | 11 | 0 | 0 | 0 | 2 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 12 | 0 |
| NONE | 1 | 7 | 0 | 0 | 0 | 57 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

Partial missing_evidence distributions (probabilities summing to less than 1; the unassigned mass counts as 0 on every label in the Brier score): 2 of 100.

### diagnosis_support

n = 100 · Brier 0.010 · ECE 0.048

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 1 | 0.560 | 0.000 | -0.560 | low n (< 20) |
| [0.6, 0.7) | 1 | 0.680 | 0.000 | -0.680 | low n (< 20) |
| [0.7, 0.8) | 2 | 0.780 | 1.000 | +0.220 | low n (< 20) |
| [0.8, 0.9) | 2 | 0.875 | 1.000 | +0.125 | low n (< 20) |
| [0.9, 1.0] | 94 | 0.970 | 1.000 | +0.030 |  |

### step_therapy

n = 100 · Brier 0.067 · ECE 0.044

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 1 | 0.535 | 0.000 | -0.535 | low n (< 20) |
| [0.6, 0.7) | 7 | 0.663 | 0.429 | -0.235 | low n (< 20) |
| [0.7, 0.8) | 5 | 0.733 | 0.800 | +0.067 | low n (< 20) |
| [0.8, 0.9) | 9 | 0.866 | 0.778 | -0.088 | low n (< 20) |
| [0.9, 1.0] | 78 | 0.961 | 0.974 | +0.014 |  |

### documentation_complete

n = 100 · Brier 0.063 · ECE 0.037

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 5 | 0.546 | 0.600 | +0.054 | low n (< 20) |
| [0.6, 0.7) | 1 | 0.650 | 1.000 | +0.350 | low n (< 20) |
| [0.7, 0.8) | 3 | 0.743 | 0.333 | -0.410 | low n (< 20) |
| [0.8, 0.9) | 8 | 0.850 | 0.875 | +0.025 | low n (< 20) |
| [0.9, 1.0] | 83 | 0.944 | 0.964 | +0.020 |  |

### material_contradiction

n = 100 · Brier 0.041 · ECE 0.094

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 2 | 0.505 | 0.000 | -0.505 | low n (< 20) |
| [0.6, 0.7) | 3 | 0.653 | 0.667 | +0.013 | low n (< 20) |
| [0.7, 0.8) | 4 | 0.762 | 0.500 | -0.262 | low n (< 20) |
| [0.8, 0.9) | 31 | 0.865 | 0.968 | +0.103 |  |
| [0.9, 1.0] | 60 | 0.931 | 1.000 | +0.069 |  |

### missing_evidence

n = 100 · Brier 0.117 · ECE 0.090

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 1 | 0.490 | 0.000 | -0.490 | low n (< 20) |
| [0.5, 0.6) | 7 | 0.539 | 0.143 | -0.396 | low n (< 20) |
| [0.6, 0.7) | 5 | 0.660 | 0.800 | +0.140 | low n (< 20) |
| [0.7, 0.8) | 9 | 0.746 | 1.000 | +0.254 | low n (< 20) |
| [0.8, 0.9) | 16 | 0.844 | 0.875 | +0.031 | low n (< 20) |
| [0.9, 1.0] | 62 | 0.964 | 1.000 | +0.036 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 32 | 32.0% | 1/32 (3.1%) | 36.0% | 95.0% |  |
| 0.55 | 32 | 32.0% | 1/32 (3.1%) | 36.0% | 95.0% |  |
| 0.60 | 32 | 32.0% | 1/32 (3.1%) | 36.0% | 95.0% |  |
| 0.65 | 32 | 32.0% | 1/32 (3.1%) | 36.0% | 95.0% |  |
| 0.70 | 31 | 31.0% | 1/31 (3.2%) | 37.0% | 94.0% |  |
| 0.75 | 31 | 31.0% | 1/31 (3.2%) | 37.0% | 94.0% |  |
| 0.80 | 31 | 31.0% | 1/31 (3.2%) | 37.0% | 94.0% |  |
| 0.81 | 31 | 31.0% | 1/31 (3.2%) | 37.0% | 94.0% | --at |
| 0.84 | 29 | 29.0% | 0/29 (0.0%) | 39.0% | 93.0% | selected |
| 0.85 | 28 | 28.0% | 0/28 (0.0%) | 40.0% | 92.0% |  |
| 0.90 | 23 | 23.0% | 0/23 (0.0%) | 45.0% | 87.0% |  |
| 0.95 | 1 | 1.0% | 0/1 (0.0%) | 67.0% | 65.0% |  |

Selected operating point: auto_process >= 0.84 (automation 29.0%, UAR 0/29, correct action 93.0%; ceiling UAR <= 1.0%)
The UAR ceiling binds: at least one automated threshold's UAR exceeds it.

The selection above is computed on this run's own data. For a held-out report, the threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample selection is shown for reference only.

## Latency and cost

- Latency: p50 175 ms · p95 256 ms
- Estimated cost: $0.0174972 total · $0.0001750 per case

## Limitations

- Synthetic data only. Generated documents come from fixed templates and phrase banks, so they exercise the policy logic and pipeline, not real-world document variety.
- Expected actions are derived from the generator's ground-truth facts through the same engine; they are not independent expert labels.
- Step therapy is composed from date parts treated as independent, which is an approximation.
- Generator and pipeline conventions apply: month-only dates are judged conservatively, and the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).
- Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset must be confirmed on held-out data.
- gen-v0.2 has a residual contradiction tell: a day-precision, non-split MTX medication-history line predicts a contradiction roughly 81% of the time (never 100%), and the NEVER_TAKEN_OTHER_DMARD distractor wording has a weak base-rate skew of its own. Both bear on material_contradiction metrics and on any rule-based baseline built from surface phrasing.
