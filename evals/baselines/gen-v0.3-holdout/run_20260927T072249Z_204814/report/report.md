# Relay evaluation report — run_20260927T072249Z_204814

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260927T072249Z_204814`
- Dataset: `gen-v0.3-holdout` (manifest hash `sha256:2aefa63d082a957ea035a9b21ae9ca283ba5e47eb3ceeedc342250118c1d99e5`)
- Provider: `jev` · model `jev-1.13.0` · client `typesafe-sdk==0.7.1`
- Question set: `q-v0.2` (hash `sha256:89717c795a2dfea7efe30e038fb483c6d4ed72d343bfbfcefeabfc6483d7a4aa`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `01db05f27b983f5ab19b106eb905ecbe31e1deb2`

## Action metrics

```text
Relay eval — run run_20260927T072249Z_204814
provider jev (jev-1.13.0) · policy v0.1 · dataset gen-v0.3-holdout · n=1000
  Correct action rate       797/1000 (79.7%)
  Automation rate           134/1000 (13.4%)
  Request-info rate         323/1000 (32.3%)
  Human escalation rate     543/1000 (54.3%)
  Unsafe automation rate    8/134 (6.0%)
  Invalid outputs           0
  Latency p50 / p95         182 ms / 235 ms
  Cost                      $0.1125385 total, $0.0001125 per case

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         100.0%
  step_therapy              94.7%
  documentation_complete    93.5%
  material_contradiction    97.9%
  missing_evidence          84.1%
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
| no | 53 | 593 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 704 | 0 |
| no | 65 | 231 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 91 | 13 |
| no | 8 | 888 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 107 | 0 | 0 | 0 | 0 | 0 |
| TREATMENT_HISTORY | 0 | 76 | 0 | 0 | 0 | 0 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 113 | 0 |
| NONE | 0 | 159 | 0 | 0 | 0 | 545 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

Partial missing_evidence distributions (probabilities summing to less than 1; the unassigned mass counts as 0 on every label in the Brier score): 20 of 1000.

### diagnosis_support

n = 1000 · Brier 0.001 · ECE 0.029

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 1 | 0.770 | 1.000 | +0.230 | low n (< 20) |
| [0.8, 0.9) | 9 | 0.844 | 1.000 | +0.156 | low n (< 20) |
| [0.9, 1.0] | 990 | 0.972 | 1.000 | +0.028 |  |

### step_therapy

n = 1000 · Brier 0.045 · ECE 0.020

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 11 | 0.543 | 0.545 | +0.002 | low n (< 20) |
| [0.6, 0.7) | 18 | 0.660 | 0.667 | +0.006 | low n (< 20) |
| [0.7, 0.8) | 8 | 0.768 | 0.875 | +0.107 | low n (< 20) |
| [0.8, 0.9) | 22 | 0.870 | 0.955 | +0.084 |  |
| [0.9, 1.0] | 941 | 0.976 | 0.957 | -0.019 |  |

### documentation_complete

n = 1000 · Brier 0.036 · ECE 0.073

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 43 | 0.536 | 0.395 | -0.141 |  |
| [0.6, 0.7) | 40 | 0.638 | 0.475 | -0.163 |  |
| [0.7, 0.8) | 22 | 0.730 | 0.273 | -0.457 |  |
| [0.8, 0.9) | 13 | 0.861 | 0.846 | -0.015 | low n (< 20) |
| [0.9, 1.0] | 882 | 0.943 | 1.000 | +0.057 |  |

### material_contradiction

n = 1000 · Brier 0.032 · ECE 0.118

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 37 | 0.548 | 0.703 | +0.155 |  |
| [0.6, 0.7) | 44 | 0.646 | 0.818 | +0.173 |  |
| [0.7, 0.8) | 56 | 0.746 | 0.982 | +0.236 |  |
| [0.8, 0.9) | 476 | 0.866 | 0.998 | +0.132 |  |
| [0.9, 1.0] | 387 | 0.925 | 1.000 | +0.075 |  |

### missing_evidence

n = 1000 · Brier 0.192 · ECE 0.068

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 15 | 0.468 | 0.533 | +0.065 | low n (< 20) |
| [0.5, 0.6) | 83 | 0.551 | 0.458 | -0.094 |  |
| [0.6, 0.7) | 92 | 0.644 | 0.424 | -0.220 |  |
| [0.7, 0.8) | 130 | 0.747 | 0.708 | -0.040 |  |
| [0.8, 0.9) | 238 | 0.853 | 0.941 | +0.088 |  |
| [0.9, 1.0] | 442 | 0.965 | 0.995 | +0.030 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 275 | 27.5% | 30/275 (10.9%) | 40.2% | 89.4% |  |
| 0.55 | 275 | 27.5% | 30/275 (10.9%) | 40.2% | 89.4% |  |
| 0.60 | 275 | 27.5% | 30/275 (10.9%) | 40.2% | 89.4% |  |
| 0.65 | 275 | 27.5% | 30/275 (10.9%) | 40.2% | 89.4% |  |
| 0.70 | 275 | 27.5% | 30/275 (10.9%) | 40.2% | 89.4% |  |
| 0.75 | 275 | 27.5% | 30/275 (10.9%) | 40.2% | 89.4% |  |
| 0.80 | 275 | 27.5% | 30/275 (10.9%) | 40.2% | 89.4% |  |
| 0.85 | 275 | 27.5% | 30/275 (10.9%) | 40.2% | 89.4% |  |
| 0.90 | 271 | 27.1% | 29/271 (10.7%) | 40.6% | 89.2% |  |
| 0.95 | 134 | 13.4% | 8/134 (6.0%) | 54.3% | 79.7% |  |
| 0.97 | 17 | 1.7% | 1/17 (5.9%) | 66.0% | 69.4% | --at |

No threshold meets the ceiling (UAR <= 1.0% with at least one AUTO_PROCESS); nothing selected.
The UAR ceiling binds: at least one automated threshold's UAR exceeds it.

The selection above is computed on this run's own data. For a held-out report, the threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample selection is shown for reference only.

## Latency and cost

- Latency: p50 182 ms · p95 235 ms
- Estimated cost: $0.1125385 total · $0.0001125 per case

## Limitations

- Synthetic data only. Generated documents come from fixed templates and phrase banks, so they exercise the policy logic and pipeline, not real-world document variety.
- Expected actions are derived from the generator's ground-truth facts through the same engine; they are not independent expert labels.
- Step therapy is composed from date parts treated as independent, which is an approximation.
- Generator and pipeline conventions apply: month-only dates are judged conservatively, and the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).
- Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset must be confirmed on held-out data.
- gen-v0.2 has a residual contradiction tell: a day-precision, non-split MTX medication-history line predicts a contradiction roughly 81% of the time (never 100%), and the NEVER_TAKEN_OTHER_DMARD distractor wording has a weak base-rate skew of its own. Both bear on material_contradiction metrics and on any rule-based baseline built from surface phrasing.
