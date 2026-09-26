# Relay evaluation report — run_20260925T071231Z_6f0b73

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260925T071231Z_6f0b73`
- Dataset: `gen-v0.2-dev` (manifest hash `sha256:3eec030bbc12d075e3b723bdde174c645641afd3b02d77f9de2f5dbeac16c2ce`)
- Provider: `jev` · model `jev-1.13.0` · client `typesafe-sdk==0.7.1`
- Question set: `q-v0.2` (hash `sha256:89717c795a2dfea7efe30e038fb483c6d4ed72d343bfbfcefeabfc6483d7a4aa`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `d30071e658b316aa34e24d248fafbc56c48fa3d2`

## Action metrics

```text
Relay eval — run run_20260925T071231Z_6f0b73
provider jev (jev-1.13.0) · policy v0.1 · dataset gen-v0.2-dev · n=400
  Correct action rate       330/400 (82.5%)
  Automation rate           64/400 (16.0%)
  Request-info rate         124/400 (31.0%)
  Human escalation rate     212/400 (53.0%)
  Unsafe automation rate    0/64 (0.0%)
  Invalid outputs           0
  Latency p50 / p95         168 ms / 214 ms
  Cost                      $0.0447707 total, $0.0001119 per case

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         100.0%
  step_therapy              98.5%
  documentation_complete    95.2%
  material_contradiction    99.5%
  missing_evidence          84.0%
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
| no | 19 | 90 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 38 | 1 |
| no | 1 | 360 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 44 | 0 | 0 | 0 | 0 | 0 |
| TREATMENT_HISTORY | 0 | 29 | 0 | 0 | 0 | 0 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 36 | 0 |
| NONE | 0 | 64 | 0 | 0 | 0 | 227 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

### diagnosis_support

n = 400 · Brier 0.001 · ECE 0.030

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 1 | 0.780 | 1.000 | +0.220 | low n (< 20) |
| [0.8, 0.9) | 3 | 0.870 | 1.000 | +0.130 | low n (< 20) |
| [0.9, 1.0] | 396 | 0.972 | 1.000 | +0.028 |  |

### step_therapy

n = 400 · Brier 0.010 · ECE 0.021

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 5 | 0.537 | 0.600 | +0.063 | low n (< 20) |
| [0.6, 0.7) | 7 | 0.648 | 0.571 | -0.077 | low n (< 20) |
| [0.7, 0.8) | 6 | 0.763 | 0.833 | +0.070 | low n (< 20) |
| [0.8, 0.9) | 6 | 0.869 | 1.000 | +0.131 | low n (< 20) |
| [0.9, 1.0] | 376 | 0.983 | 1.000 | +0.017 |  |

### documentation_complete

n = 400 · Brier 0.035 · ECE 0.084

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 17 | 0.536 | 0.882 | +0.346 | low n (< 20) |
| [0.6, 0.7) | 17 | 0.631 | 0.471 | -0.160 | low n (< 20) |
| [0.7, 0.8) | 8 | 0.745 | 0.125 | -0.620 | low n (< 20) |
| [0.8, 0.9) | 9 | 0.876 | 0.889 | +0.013 | low n (< 20) |
| [0.9, 1.0] | 349 | 0.943 | 1.000 | +0.057 |  |

### material_contradiction

n = 400 · Brier 0.029 · ECE 0.135

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 16 | 0.552 | 0.875 | +0.323 | low n (< 20) |
| [0.6, 0.7) | 18 | 0.645 | 1.000 | +0.355 | low n (< 20) |
| [0.7, 0.8) | 29 | 0.752 | 1.000 | +0.248 |  |
| [0.8, 0.9) | 164 | 0.863 | 1.000 | +0.137 |  |
| [0.9, 1.0] | 173 | 0.926 | 1.000 | +0.074 |  |

### missing_evidence

n = 400 · Brier 0.199 · ECE 0.055

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 2 | 0.480 | 0.500 | +0.020 | low n (< 20) |
| [0.5, 0.6) | 35 | 0.548 | 0.457 | -0.091 |  |
| [0.6, 0.7) | 39 | 0.650 | 0.513 | -0.137 |  |
| [0.7, 0.8) | 54 | 0.744 | 0.704 | -0.041 |  |
| [0.8, 0.9) | 100 | 0.856 | 0.920 | +0.064 |  |
| [0.9, 1.0] | 170 | 0.965 | 0.994 | +0.029 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 99 | 24.8% | 0/99 (0.0%) | 44.2% | 91.2% |  |
| 0.55 | 99 | 24.8% | 0/99 (0.0%) | 44.2% | 91.2% |  |
| 0.60 | 99 | 24.8% | 0/99 (0.0%) | 44.2% | 91.2% |  |
| 0.65 | 99 | 24.8% | 0/99 (0.0%) | 44.2% | 91.2% |  |
| 0.70 | 99 | 24.8% | 0/99 (0.0%) | 44.2% | 91.2% |  |
| 0.75 | 99 | 24.8% | 0/99 (0.0%) | 44.2% | 91.2% |  |
| 0.80 | 99 | 24.8% | 0/99 (0.0%) | 44.2% | 91.2% |  |
| 0.85 | 99 | 24.8% | 0/99 (0.0%) | 44.2% | 91.2% |  |
| 0.89 | 99 | 24.8% | 0/99 (0.0%) | 44.2% | 91.2% | selected |
| 0.90 | 98 | 24.5% | 0/98 (0.0%) | 44.5% | 91.0% |  |
| 0.95 | 64 | 16.0% | 0/64 (0.0%) | 53.0% | 82.5% |  |

Selected operating point: auto_process >= 0.89 (automation 24.8%, UAR 0/99, correct action 91.2%; ceiling UAR <= 1.0%)

The selection above is computed on this run's own data. For a held-out report, the threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample selection is shown for reference only.

## Latency and cost

- Latency: p50 168 ms · p95 214 ms
- Estimated cost: $0.0447707 total · $0.0001119 per case

## Limitations

- Synthetic data only. Generated documents come from fixed templates and phrase banks, so they exercise the policy logic and pipeline, not real-world document variety.
- Expected actions are derived from the generator's ground-truth facts through the same engine; they are not independent expert labels.
- Step therapy is composed from date parts treated as independent, which is an approximation.
- Generator and pipeline conventions apply: month-only dates are judged conservatively, and the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).
- Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset must be confirmed on held-out data.
