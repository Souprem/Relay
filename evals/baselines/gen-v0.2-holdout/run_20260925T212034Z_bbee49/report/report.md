# Relay evaluation report — run_20260925T212034Z_bbee49

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260925T212034Z_bbee49`
- Dataset: `gen-v0.2-holdout` (no dataset manifest)
- Provider: `claude` · model `claude-opus-5` · client `anthropic==1.8.0`
- Question set: `q-v0.2+claude-prompt-v1` (hash `sha256:d24c74fa140ca4682e6202ea36a2bdc978085216c8b220fe413c4e09005cc9b6`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `b08461302f57c5645af4018a9a0114a59472907a`

## Action metrics

```text
Relay eval — run run_20260925T212034Z_bbee49
provider claude (claude-opus-5) · policy v0.1 · dataset gen-v0.2-holdout · n=150
  Correct action rate       110/150 (73.3%)
  Automation rate           0/150 (0.0%)
  Request-info rate         47/150 (31.3%)
  Human escalation rate     103/150 (68.7%)
  Unsafe automation rate    n/a (no AUTO_PROCESS actions)
  Invalid outputs           0
  Refusals                  0
  Latency p50 / p95         unavailable (batch)
  Cost                      $2.4562150 total, $0.0163748 per case
  Prompt cache reads        29.6% of prompt tokens

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         100.0%
  step_therapy              100.0%
  documentation_complete    94.7%
  material_contradiction    100.0%
  missing_evidence          96.0%
```

## Confusion matrices

Evaluation only: rows are the ground-truth answer, columns the provider's answer (yes/no at p_yes >= 0.5; the missing-evidence choice by its top answer). Invalid bundles excluded: 0.

### diagnosis_support

| truth / predicted | yes | no |
|---|---|---|
| yes | 133 | 0 |
| no | 0 | 17 |

### step_therapy

| truth / predicted | yes | no |
|---|---|---|
| yes | 52 | 0 |
| no | 0 | 98 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 101 | 0 |
| no | 8 | 41 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 12 | 0 |
| no | 0 | 138 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 17 | 0 | 0 | 0 | 0 | 0 |
| TREATMENT_HISTORY | 0 | 15 | 0 | 0 | 0 | 0 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 17 | 0 |
| NONE | 0 | 6 | 0 | 0 | 0 | 95 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

Partial missing_evidence distributions (probabilities summing to less than 1; the unassigned mass counts as 0 on every label in the Brier score): 0 of 150.

### diagnosis_support

n = 150 · Brier 0.002 · ECE 0.041

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 5 | 0.854 | 1.000 | +0.146 | low n (< 20) |
| [0.9, 1.0] | 145 | 0.963 | 1.000 | +0.037 |  |

### step_therapy

n = 150 · Brier 0.027 · ECE 0.101

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 16 | 0.678 | 1.000 | +0.322 | low n (< 20) |
| [0.7, 0.8) | 33 | 0.744 | 1.000 | +0.256 |  |
| [0.8, 0.9) | 5 | 0.812 | 1.000 | +0.188 | low n (< 20) |
| [0.9, 1.0] | 96 | 0.993 | 1.000 | +0.007 |  |

### documentation_complete

n = 150 · Brier 0.044 · ECE 0.029

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 1 | 0.550 | 0.000 | -0.550 | low n (< 20) |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 5 | 0.720 | 0.800 | +0.080 | low n (< 20) |
| [0.8, 0.9) | 8 | 0.838 | 0.875 | +0.037 | low n (< 20) |
| [0.9, 1.0] | 136 | 0.941 | 0.963 | +0.023 |  |

### material_contradiction

n = 150 · Brier 0.002 · ECE 0.041

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 4 | 0.880 | 1.000 | +0.120 | low n (< 20) |
| [0.9, 1.0] | 146 | 0.961 | 1.000 | +0.039 |  |

### missing_evidence

n = 150 · Brier 0.083 · ECE 0.137

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 0 | — | — | — | empty |
| [0.5, 0.6) | 3 | 0.500 | 0.333 | -0.167 | low n (< 20) |
| [0.6, 0.7) | 10 | 0.647 | 0.900 | +0.253 | low n (< 20) |
| [0.7, 0.8) | 29 | 0.742 | 0.897 | +0.154 |  |
| [0.8, 0.9) | 57 | 0.851 | 1.000 | +0.149 |  |
| [0.9, 1.0] | 51 | 0.911 | 1.000 | +0.089 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 37 | 24.7% | 0/37 (0.0%) | 44.0% | 98.0% |  |
| 0.55 | 37 | 24.7% | 0/37 (0.0%) | 44.0% | 98.0% | --at |
| 0.60 | 37 | 24.7% | 0/37 (0.0%) | 44.0% | 98.0% |  |
| 0.64 | 37 | 24.7% | 0/37 (0.0%) | 44.0% | 98.0% | selected |
| 0.65 | 35 | 23.3% | 0/35 (0.0%) | 45.3% | 96.7% |  |
| 0.70 | 26 | 17.3% | 0/26 (0.0%) | 51.3% | 90.7% |  |
| 0.75 | 8 | 5.3% | 0/8 (0.0%) | 63.3% | 78.7% |  |
| 0.80 | 2 | 1.3% | 0/2 (0.0%) | 67.3% | 74.7% |  |
| 0.85 | 0 | 0.0% | n/a (no AUTO) | 68.7% | 73.3% |  |
| 0.90 | 0 | 0.0% | n/a (no AUTO) | 68.7% | 73.3% |  |
| 0.95 | 0 | 0.0% | n/a (no AUTO) | 68.7% | 73.3% |  |

Selected operating point: auto_process >= 0.64 (automation 24.7%, UAR 0/37, correct action 98.0%; ceiling UAR <= 1.0%)
The UAR ceiling does not bind at any threshold.

The selection above is computed on this run's own data. For a held-out report, the threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample selection is shown for reference only.

## Latency and cost

- Latency: unavailable (batch)
- Estimated cost: $2.4562150 total · $0.0163748 per case

## Limitations

- Synthetic data only. Generated documents come from fixed templates and phrase banks, so they exercise the policy logic and pipeline, not real-world document variety.
- Expected actions are derived from the generator's ground-truth facts through the same engine; they are not independent expert labels.
- Step therapy is composed from date parts treated as independent, which is an approximation.
- Generator and pipeline conventions apply: month-only dates are judged conservatively, and the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).
- Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset must be confirmed on held-out data.
- gen-v0.2 has a residual contradiction tell: a day-precision, non-split MTX medication-history line predicts a contradiction roughly 81% of the time (never 100%), and the NEVER_TAKEN_OTHER_DMARD distractor wording has a weak base-rate skew of its own. Both bear on material_contradiction metrics and on any rule-based baseline built from surface phrasing.
