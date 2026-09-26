# Relay evaluation report — run_20260925T071157Z_d6b218

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260925T071157Z_d6b218`
- Dataset: `gen-v0.2-dev` (manifest hash `sha256:3eec030bbc12d075e3b723bdde174c645641afd3b02d77f9de2f5dbeac16c2ce`)
- Provider: `jev` · model `jev-1.13.0` · client `typesafe-sdk==0.7.1`
- Question set: `q-v0.1` (hash `sha256:b395531673a539ec02c1e66bb03d5952b8608eba15f041939549ece2617ac77a`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `d30071e658b316aa34e24d248fafbc56c48fa3d2`

## Action metrics

```text
Relay eval — run run_20260925T071157Z_d6b218
provider jev (jev-1.13.0) · policy v0.1 · dataset gen-v0.2-dev · n=400
  Correct action rate       257/400 (64.2%)
  Automation rate           29/400 (7.2%)
  Request-info rate         162/400 (40.5%)
  Human escalation rate     209/400 (52.2%)
  Unsafe automation rate    0/29 (0.0%)
  Invalid outputs           0
  Latency p50 / p95         174 ms / 221 ms
  Cost                      $0.0442331 total, $0.0001106 per case

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         100.0%
  step_therapy              98.5%
  documentation_complete    96.2%
  material_contradiction    98.8%
  missing_evidence          77.0%
```

## Confusion matrices

Evaluation only: rows are the ground-truth answer, columns the provider's answer (yes/no at p_yes >= 0.5; the missing-evidence choice by its top answer). Invalid bundles excluded: 0.

### diagnosis_support

| truth / predicted | yes | no |
|---|---|---|
| yes | 356 | 0 |
| no | 0 | 44 |

### step_therapy

| truth / predicted | yes | no |
|---|---|---|
| yes | 132 | 0 |
| no | 6 | 262 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 291 | 0 |
| no | 15 | 94 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 37 | 2 |
| no | 3 | 358 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 44 | 0 | 0 | 0 | 0 | 0 |
| TREATMENT_HISTORY | 0 | 29 | 0 | 0 | 0 | 0 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 4 | 0 | 0 | 32 | 0 |
| NONE | 0 | 88 | 0 | 0 | 0 | 203 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

### diagnosis_support

n = 400 · Brier 0.001 · ECE 0.029

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 1 | 0.770 | 1.000 | +0.230 | low n (< 20) |
| [0.8, 0.9) | 3 | 0.877 | 1.000 | +0.123 | low n (< 20) |
| [0.9, 1.0] | 396 | 0.972 | 1.000 | +0.028 |  |

### step_therapy

n = 400 · Brier 0.010 · ECE 0.021

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 6 | 0.541 | 0.500 | -0.041 | low n (< 20) |
| [0.6, 0.7) | 5 | 0.651 | 0.600 | -0.051 | low n (< 20) |
| [0.7, 0.8) | 5 | 0.744 | 0.800 | +0.056 | low n (< 20) |
| [0.8, 0.9) | 9 | 0.851 | 1.000 | +0.149 | low n (< 20) |
| [0.9, 1.0] | 375 | 0.983 | 1.000 | +0.017 |  |

### documentation_complete

n = 400 · Brier 0.030 · ECE 0.067

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 18 | 0.546 | 0.556 | +0.009 | low n (< 20) |
| [0.6, 0.7) | 17 | 0.640 | 0.706 | +0.066 | low n (< 20) |
| [0.7, 0.8) | 7 | 0.734 | 0.857 | +0.123 | low n (< 20) |
| [0.8, 0.9) | 40 | 0.869 | 0.975 | +0.106 |  |
| [0.9, 1.0] | 318 | 0.936 | 1.000 | +0.064 |  |

### material_contradiction

n = 400 · Brier 0.029 · ECE 0.127

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 14 | 0.543 | 0.643 | +0.100 | low n (< 20) |
| [0.6, 0.7) | 19 | 0.647 | 1.000 | +0.353 | low n (< 20) |
| [0.7, 0.8) | 32 | 0.749 | 1.000 | +0.251 |  |
| [0.8, 0.9) | 157 | 0.862 | 1.000 | +0.138 |  |
| [0.9, 1.0] | 178 | 0.926 | 1.000 | +0.074 |  |

### missing_evidence

n = 400 · Brier 0.406 · ECE 0.146

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 2 | 0.475 | 0.500 | +0.025 | low n (< 20) |
| [0.5, 0.6) | 17 | 0.548 | 0.588 | +0.041 | low n (< 20) |
| [0.6, 0.7) | 21 | 0.652 | 0.762 | +0.110 |  |
| [0.7, 0.8) | 38 | 0.751 | 0.658 | -0.093 |  |
| [0.8, 0.9) | 82 | 0.854 | 0.890 | +0.036 |  |
| [0.9, 1.0] | 240 | 0.967 | 0.762 | -0.204 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 99 | 24.8% | 0/99 (0.0%) | 34.8% | 81.8% |  |
| 0.55 | 99 | 24.8% | 0/99 (0.0%) | 34.8% | 81.8% |  |
| 0.60 | 99 | 24.8% | 0/99 (0.0%) | 34.8% | 81.8% |  |
| 0.65 | 99 | 24.8% | 0/99 (0.0%) | 34.8% | 81.8% |  |
| 0.70 | 99 | 24.8% | 0/99 (0.0%) | 34.8% | 81.8% |  |
| 0.75 | 99 | 24.8% | 0/99 (0.0%) | 34.8% | 81.8% |  |
| 0.80 | 99 | 24.8% | 0/99 (0.0%) | 34.8% | 81.8% |  |
| 0.85 | 99 | 24.8% | 0/99 (0.0%) | 34.8% | 81.8% |  |
| 0.87 | 99 | 24.8% | 0/99 (0.0%) | 34.8% | 81.8% | selected |
| 0.90 | 93 | 23.2% | 0/93 (0.0%) | 36.2% | 80.2% |  |
| 0.95 | 29 | 7.2% | 0/29 (0.0%) | 52.2% | 64.2% |  |

Selected operating point: auto_process >= 0.87 (automation 24.8%, UAR 0/99, correct action 81.8%; ceiling UAR <= 1.0%)

The selection above is computed on this run's own data. For a held-out report, the threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample selection is shown for reference only.

## Latency and cost

- Latency: p50 174 ms · p95 221 ms
- Estimated cost: $0.0442331 total · $0.0001106 per case

## Limitations

- Synthetic data only. Generated documents come from fixed templates and phrase banks, so they exercise the policy logic and pipeline, not real-world document variety.
- Expected actions are derived from the generator's ground-truth facts through the same engine; they are not independent expert labels.
- Step therapy is composed from date parts treated as independent, which is an approximation.
- Generator and pipeline conventions apply: month-only dates are judged conservatively, and the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).
- Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset must be confirmed on held-out data.
