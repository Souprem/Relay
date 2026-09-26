# Relay evaluation report — run_20260925T191752Z_288946

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260925T191752Z_288946`
- Dataset: `gen-v0.2-dev` (manifest hash `sha256:3eec030bbc12d075e3b723bdde174c645641afd3b02d77f9de2f5dbeac16c2ce`)
- Provider: `claude` · model `claude-opus-5` · client `anthropic==1.8.0`
- Question set: `q-v0.2+claude-prompt-v1` (hash `sha256:d24c74fa140ca4682e6202ea36a2bdc978085216c8b220fe413c4e09005cc9b6`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `b08461302f57c5645af4018a9a0114a59472907a`

## Action metrics

```text
Relay eval — run run_20260925T191752Z_288946
provider claude (claude-opus-5) · policy v0.1 · dataset gen-v0.2-dev · n=400
  Correct action rate       288/400 (72.0%)
  Automation rate           0/400 (0.0%)
  Request-info rate         94/400 (23.5%)
  Human escalation rate     306/400 (76.5%)
  Unsafe automation rate    n/a (no AUTO_PROCESS actions)
  Invalid outputs           0
  Refusals                  0
  Latency p50 / p95         unavailable (batch)
  Cost                      $4.3986740 total, $0.0109967 per case
  Prompt cache reads        65.5% of prompt tokens

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         100.0%
  step_therapy              99.8%
  documentation_complete    94.2%
  material_contradiction    100.0%
  missing_evidence          95.2%
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
| yes | 131 | 1 |
| no | 0 | 268 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 291 | 0 |
| no | 23 | 86 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 39 | 0 |
| no | 0 | 361 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 43 | 1 | 0 | 0 | 0 | 0 |
| TREATMENT_HISTORY | 0 | 29 | 0 | 0 | 0 | 0 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 36 | 0 |
| NONE | 0 | 18 | 0 | 0 | 0 | 273 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

Partial missing_evidence distributions (probabilities summing to less than 1; the unassigned mass counts as 0 on every label in the Brier score): 0 of 400.

### diagnosis_support

n = 400 · Brier 0.002 · ECE 0.040

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 1 | 0.750 | 1.000 | +0.250 | low n (< 20) |
| [0.8, 0.9) | 11 | 0.870 | 1.000 | +0.130 | low n (< 20) |
| [0.9, 1.0] | 388 | 0.963 | 1.000 | +0.037 |  |

### step_therapy

n = 400 · Brier 0.030 · ECE 0.094

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 8 | 0.576 | 1.000 | +0.424 | low n (< 20) |
| [0.6, 0.7) | 36 | 0.662 | 1.000 | +0.338 |  |
| [0.7, 0.8) | 78 | 0.744 | 1.000 | +0.256 |  |
| [0.8, 0.9) | 9 | 0.824 | 1.000 | +0.176 | low n (< 20) |
| [0.9, 1.0] | 269 | 0.994 | 0.996 | +0.002 |  |

### documentation_complete

n = 400 · Brier 0.040 · ECE 0.069

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 3 | 0.500 | 0.000 | -0.500 | low n (< 20) |
| [0.6, 0.7) | 8 | 0.619 | 0.625 | +0.006 | low n (< 20) |
| [0.7, 0.8) | 17 | 0.744 | 0.529 | -0.215 | low n (< 20) |
| [0.8, 0.9) | 23 | 0.840 | 0.696 | -0.144 |  |
| [0.9, 1.0] | 349 | 0.940 | 0.994 | +0.054 |  |

### material_contradiction

n = 400 · Brier 0.002 · ECE 0.043

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 6 | 0.870 | 1.000 | +0.130 | low n (< 20) |
| [0.9, 1.0] | 394 | 0.959 | 1.000 | +0.041 |  |

### missing_evidence

n = 400 · Brier 0.088 · ECE 0.148

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 4 | 0.460 | 0.500 | +0.040 | low n (< 20) |
| [0.5, 0.6) | 22 | 0.545 | 0.455 | -0.090 |  |
| [0.6, 0.7) | 30 | 0.637 | 0.900 | +0.263 |  |
| [0.7, 0.8) | 69 | 0.752 | 0.971 | +0.219 |  |
| [0.8, 0.9) | 182 | 0.859 | 1.000 | +0.141 |  |
| [0.9, 1.0] | 93 | 0.910 | 1.000 | +0.090 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 106 | 26.5% | 0/106 (0.0%) | 50.0% | 98.5% |  |
| 0.55 | 106 | 26.5% | 0/106 (0.0%) | 50.0% | 98.5% | selected |
| 0.60 | 101 | 25.2% | 0/101 (0.0%) | 51.2% | 97.2% |  |
| 0.65 | 88 | 22.0% | 0/88 (0.0%) | 54.5% | 94.0% |  |
| 0.70 | 72 | 18.0% | 0/72 (0.0%) | 58.5% | 90.0% |  |
| 0.75 | 26 | 6.5% | 0/26 (0.0%) | 70.0% | 78.5% |  |
| 0.80 | 7 | 1.8% | 0/7 (0.0%) | 74.8% | 73.8% |  |
| 0.85 | 0 | 0.0% | n/a (no AUTO) | 76.5% | 72.0% |  |
| 0.90 | 0 | 0.0% | n/a (no AUTO) | 76.5% | 72.0% |  |
| 0.95 | 0 | 0.0% | n/a (no AUTO) | 76.5% | 72.0% |  |

Selected operating point: auto_process >= 0.55 (automation 26.5%, UAR 0/106, correct action 98.5%; ceiling UAR <= 1.0%)
The UAR ceiling does not bind at any threshold.

The selection above is computed on this run's own data. For a held-out report, the threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample selection is shown for reference only.

## Latency and cost

- Latency: unavailable (batch)
- Estimated cost: $4.3986740 total · $0.0109967 per case

## Limitations

- Synthetic data only. Generated documents come from fixed templates and phrase banks, so they exercise the policy logic and pipeline, not real-world document variety.
- Expected actions are derived from the generator's ground-truth facts through the same engine; they are not independent expert labels.
- Step therapy is composed from date parts treated as independent, which is an approximation.
- Generator and pipeline conventions apply: month-only dates are judged conservatively, and the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).
- Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset must be confirmed on held-out data.
- gen-v0.2 has a residual contradiction tell: a day-precision, non-split MTX medication-history line predicts a contradiction roughly 81% of the time (never 100%), and the NEVER_TAKEN_OTHER_DMARD distractor wording has a weak base-rate skew of its own. Both bear on material_contradiction metrics and on any rule-based baseline built from surface phrasing.
