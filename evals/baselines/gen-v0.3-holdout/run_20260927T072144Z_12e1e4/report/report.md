# Relay evaluation report — run_20260927T072144Z_12e1e4

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260927T072144Z_12e1e4`
- Dataset: `gen-v0.3-holdout` (manifest hash `sha256:2aefa63d082a957ea035a9b21ae9ca283ba5e47eb3ceeedc342250118c1d99e5`)
- Provider: `jev` · model `jev-1.13.0` · client `typesafe-sdk==0.7.1`
- Question set: `q-v0.3` (hash `sha256:4589d78b40d2be56216766beec111882b7f96c761be99d1f6ba218e3bfd2979c`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `01db05f27b983f5ab19b106eb905ecbe31e1deb2`

## Action metrics

```text
Relay eval — run run_20260927T072144Z_12e1e4
provider jev (jev-1.13.0) · policy v0.1 · dataset gen-v0.3-holdout · n=1000
  Correct action rate       711/1000 (71.1%)
  Automation rate           34/1000 (3.4%)
  Request-info rate         327/1000 (32.7%)
  Human escalation rate     639/1000 (63.9%)
  Unsafe automation rate    0/34 (0.0%)
  Invalid outputs           0
  Latency p50 / p95         193 ms / 260 ms
  Cost                      $0.1724217 total, $0.0001724 per case

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         100.0%
  step_therapy              97.8%
  documentation_complete    93.6%
  material_contradiction    97.7%
  missing_evidence          83.8%
```

## Confusion matrices

Evaluation only: rows are the ground-truth answer, columns the provider's answer (yes/no at p_yes >= 0.5; the missing-evidence choice by its top answer). Invalid bundles excluded: 0.

### diagnosis_support

| truth / predicted | yes | no |
|---|---|---|
| yes | 893 | 0 |
| no | 0 | 107 |

### step_therapy

| truth / predicted | yes | no |
|---|---|---|
| yes | 354 | 0 |
| no | 22 | 624 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 704 | 0 |
| no | 64 | 232 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 91 | 13 |
| no | 10 | 886 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 107 | 0 | 0 | 0 | 0 | 0 |
| TREATMENT_HISTORY | 0 | 76 | 0 | 0 | 0 | 0 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 113 | 0 |
| NONE | 0 | 162 | 0 | 0 | 0 | 542 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

Partial missing_evidence distributions (probabilities summing to less than 1; the unassigned mass counts as 0 on every label in the Brier score): 28 of 1000.

### diagnosis_support

n = 1000 · Brier 0.001 · ECE 0.029

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 1 | 0.780 | 1.000 | +0.220 | low n (< 20) |
| [0.8, 0.9) | 8 | 0.840 | 1.000 | +0.160 | low n (< 20) |
| [0.9, 1.0] | 991 | 0.972 | 1.000 | +0.028 |  |

### step_therapy

n = 1000 · Brier 0.014 · ECE 0.038

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 18 | 0.543 | 0.500 | -0.043 | low n (< 20) |
| [0.6, 0.7) | 18 | 0.649 | 0.389 | -0.260 | low n (< 20) |
| [0.7, 0.8) | 8 | 0.762 | 0.750 | -0.012 | low n (< 20) |
| [0.8, 0.9) | 55 | 0.873 | 1.000 | +0.127 |  |
| [0.9, 1.0] | 901 | 0.971 | 1.000 | +0.029 |  |

### documentation_complete

n = 1000 · Brier 0.036 · ECE 0.072

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 44 | 0.540 | 0.477 | -0.062 |  |
| [0.6, 0.7) | 41 | 0.640 | 0.439 | -0.201 |  |
| [0.7, 0.8) | 20 | 0.743 | 0.200 | -0.543 |  |
| [0.8, 0.9) | 18 | 0.870 | 0.889 | +0.019 | low n (< 20) |
| [0.9, 1.0] | 877 | 0.943 | 1.000 | +0.057 |  |

### material_contradiction

n = 1000 · Brier 0.032 · ECE 0.116

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 37 | 0.546 | 0.649 | +0.102 |  |
| [0.6, 0.7) | 41 | 0.649 | 0.805 | +0.156 |  |
| [0.7, 0.8) | 58 | 0.741 | 0.966 | +0.225 |  |
| [0.8, 0.9) | 477 | 0.866 | 1.000 | +0.134 |  |
| [0.9, 1.0] | 387 | 0.925 | 1.000 | +0.075 |  |

### missing_evidence

n = 1000 · Brier 0.196 · ECE 0.072

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 15 | 0.469 | 0.533 | +0.064 | low n (< 20) |
| [0.5, 0.6) | 83 | 0.547 | 0.458 | -0.089 |  |
| [0.6, 0.7) | 96 | 0.649 | 0.427 | -0.222 |  |
| [0.7, 0.8) | 124 | 0.749 | 0.685 | -0.063 |  |
| [0.8, 0.9) | 241 | 0.855 | 0.938 | +0.083 |  |
| [0.9, 1.0] | 441 | 0.966 | 0.998 | +0.032 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 245 | 24.5% | 0/245 (0.0%) | 42.8% | 92.2% |  |
| 0.55 | 245 | 24.5% | 0/245 (0.0%) | 42.8% | 92.2% |  |
| 0.60 | 245 | 24.5% | 0/245 (0.0%) | 42.8% | 92.2% |  |
| 0.64 | 245 | 24.5% | 0/245 (0.0%) | 42.8% | 92.2% | selected |
| 0.65 | 244 | 24.4% | 0/244 (0.0%) | 42.9% | 92.1% |  |
| 0.70 | 244 | 24.4% | 0/244 (0.0%) | 42.9% | 92.1% |  |
| 0.75 | 244 | 24.4% | 0/244 (0.0%) | 42.9% | 92.1% |  |
| 0.80 | 244 | 24.4% | 0/244 (0.0%) | 42.9% | 92.1% |  |
| 0.81 | 244 | 24.4% | 0/244 (0.0%) | 42.9% | 92.1% | --at |
| 0.85 | 242 | 24.2% | 0/242 (0.0%) | 43.1% | 91.9% |  |
| 0.90 | 214 | 21.4% | 0/214 (0.0%) | 45.9% | 89.1% |  |
| 0.95 | 34 | 3.4% | 0/34 (0.0%) | 63.9% | 71.1% |  |

Selected operating point: auto_process >= 0.64 (automation 24.5%, UAR 0/245, correct action 92.2%; ceiling UAR <= 1.0%)
The UAR ceiling does not bind at any threshold.

The selection above is computed on this run's own data. For a held-out report, the threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample selection is shown for reference only.

## Latency and cost

- Latency: p50 193 ms · p95 260 ms
- Estimated cost: $0.1724217 total · $0.0001724 per case

## Limitations

- Synthetic data only. Generated documents come from fixed templates and phrase banks, so they exercise the policy logic and pipeline, not real-world document variety.
- Expected actions are derived from the generator's ground-truth facts through the same engine; they are not independent expert labels.
- Step therapy is composed from date parts treated as independent, which is an approximation.
- Generator and pipeline conventions apply: month-only dates are judged conservatively, and the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).
- Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset must be confirmed on held-out data.
- gen-v0.2 has a residual contradiction tell: a day-precision, non-split MTX medication-history line predicts a contradiction roughly 81% of the time (never 100%), and the NEVER_TAKEN_OTHER_DMARD distractor wording has a weak base-rate skew of its own. Both bear on material_contradiction metrics and on any rule-based baseline built from surface phrasing.
