# Relay evaluation report — run_20260926T011730Z_f1852f

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260926T011730Z_f1852f`
- Dataset: `gold-v0.1` (no dataset manifest)
- Provider: `claude` · model `claude-opus-5` · client `anthropic==1.8.0`
- Question set: `q-v0.2+claude-prompt-v1` (hash `sha256:d24c74fa140ca4682e6202ea36a2bdc978085216c8b220fe413c4e09005cc9b6`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `c59937ddf209e4a2916cad4946ad11011e882e7e`

## Action metrics

```text
Relay eval — run run_20260926T011730Z_f1852f
provider claude (claude-opus-5) · policy v0.1 · dataset gold-v0.1 · n=100
  Correct action rate       65/100 (65.0%)
  Automation rate           0/100 (0.0%)
  Request-info rate         33/100 (33.0%)
  Human escalation rate     67/100 (67.0%)
  Unsafe automation rate    n/a (no AUTO_PROCESS actions)
  Invalid outputs           0
  Refusals                  0
  Latency p50 / p95         unavailable (batch)
  Cost                      $1.5604550 total, $0.0156046 per case
  Prompt cache reads        35.3% of prompt tokens

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         98.0%
  step_therapy              94.0%
  documentation_complete    92.0%
  material_contradiction    99.0%
  missing_evidence          96.0%
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
| yes | 47 | 3 |
| no | 3 | 47 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 65 | 0 |
| no | 8 | 27 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 14 | 0 |
| no | 1 | 85 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 10 | 0 | 0 | 0 | 0 | 0 |
| TREATMENT_HISTORY | 0 | 12 | 0 | 0 | 0 | 1 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 12 | 0 |
| NONE | 1 | 2 | 0 | 0 | 0 | 62 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

Partial missing_evidence distributions (probabilities summing to less than 1; the unassigned mass counts as 0 on every label in the Brier score): 0 of 100.

### diagnosis_support

n = 100 · Brier 0.008 · ECE 0.049

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 1 | 0.500 | 0.000 | -0.500 | low n (< 20) |
| [0.6, 0.7) | 1 | 0.600 | 0.000 | -0.600 | low n (< 20) |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 98 | 0.961 | 1.000 | +0.039 |  |

### step_therapy

n = 100 · Brier 0.084 · ECE 0.152

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 4 | 0.562 | 0.500 | -0.062 | low n (< 20) |
| [0.6, 0.7) | 29 | 0.661 | 0.931 | +0.270 |  |
| [0.7, 0.8) | 25 | 0.736 | 0.960 | +0.224 |  |
| [0.8, 0.9) | 3 | 0.835 | 1.000 | +0.165 | low n (< 20) |
| [0.9, 1.0] | 39 | 1.000 | 0.974 | -0.026 |  |

### documentation_complete

n = 100 · Brier 0.046 · ECE 0.098

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 1 | 0.500 | 0.000 | -0.500 | low n (< 20) |
| [0.6, 0.7) | 2 | 0.600 | 0.000 | -0.600 | low n (< 20) |
| [0.7, 0.8) | 5 | 0.750 | 0.400 | -0.350 | low n (< 20) |
| [0.8, 0.9) | 4 | 0.865 | 0.500 | -0.365 | low n (< 20) |
| [0.9, 1.0] | 88 | 0.944 | 1.000 | +0.056 |  |

### material_contradiction

n = 100 · Brier 0.007 · ECE 0.054

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 1 | 0.500 | 0.000 | -0.500 | low n (< 20) |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 3 | 0.717 | 1.000 | +0.283 | low n (< 20) |
| [0.8, 0.9) | 3 | 0.850 | 1.000 | +0.150 | low n (< 20) |
| [0.9, 1.0] | 93 | 0.962 | 1.000 | +0.038 |  |

### missing_evidence

n = 100 · Brier 0.076 · ECE 0.133

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 1 | 0.450 | 0.000 | -0.450 | low n (< 20) |
| [0.5, 0.6) | 1 | 0.510 | 1.000 | +0.490 | low n (< 20) |
| [0.6, 0.7) | 8 | 0.636 | 0.625 | -0.011 | low n (< 20) |
| [0.7, 0.8) | 15 | 0.754 | 1.000 | +0.246 | low n (< 20) |
| [0.8, 0.9) | 38 | 0.861 | 1.000 | +0.139 |  |
| [0.9, 1.0] | 37 | 0.912 | 1.000 | +0.088 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 31 | 31.0% | 1/31 (3.2%) | 36.0% | 94.0% |  |
| 0.55 | 30 | 30.0% | 1/30 (3.3%) | 37.0% | 93.0% | --at |
| 0.56 | 29 | 29.0% | 0/29 (0.0%) | 38.0% | 94.0% | selected |
| 0.60 | 28 | 28.0% | 0/28 (0.0%) | 39.0% | 93.0% |  |
| 0.65 | 25 | 25.0% | 0/25 (0.0%) | 42.0% | 90.0% |  |
| 0.70 | 16 | 16.0% | 0/16 (0.0%) | 51.0% | 81.0% |  |
| 0.75 | 4 | 4.0% | 0/4 (0.0%) | 63.0% | 69.0% |  |
| 0.80 | 0 | 0.0% | n/a (no AUTO) | 67.0% | 65.0% |  |
| 0.85 | 0 | 0.0% | n/a (no AUTO) | 67.0% | 65.0% |  |
| 0.90 | 0 | 0.0% | n/a (no AUTO) | 67.0% | 65.0% |  |
| 0.95 | 0 | 0.0% | n/a (no AUTO) | 67.0% | 65.0% |  |

Selected operating point: auto_process >= 0.56 (automation 29.0%, UAR 0/29, correct action 94.0%; ceiling UAR <= 1.0%)
The UAR ceiling binds: at least one automated threshold's UAR exceeds it.

The selection above is computed on this run's own data. For a held-out report, the threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample selection is shown for reference only.

## Latency and cost

- Latency: unavailable (batch)
- Estimated cost: $1.5604550 total · $0.0156046 per case

## Limitations

- Synthetic data only. Generated documents come from fixed templates and phrase banks, so they exercise the policy logic and pipeline, not real-world document variety.
- Expected actions are derived from the generator's ground-truth facts through the same engine; they are not independent expert labels.
- Step therapy is composed from date parts treated as independent, which is an approximation.
- Generator and pipeline conventions apply: month-only dates are judged conservatively, and the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).
- Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset must be confirmed on held-out data.
- gen-v0.2 has a residual contradiction tell: a day-precision, non-split MTX medication-history line predicts a contradiction roughly 81% of the time (never 100%), and the NEVER_TAKEN_OTHER_DMARD distractor wording has a weak base-rate skew of its own. Both bear on material_contradiction metrics and on any rule-based baseline built from surface phrasing.
