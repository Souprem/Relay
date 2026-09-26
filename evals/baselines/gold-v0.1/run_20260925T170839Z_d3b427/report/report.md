# Relay evaluation report — run_20260925T170839Z_d3b427

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260925T170839Z_d3b427`
- Dataset: `gold-v0.1` (no dataset manifest)
- Provider: `rules` · model `rules-v0.1` · client n/a
- Question set: `rules-v0.1` (hash `sha256:5bd96c08e7c29353d55a180c4f465a2523a1f04563e31a4af0170fb1d9d92add`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `2dbcf2c9d24449c2faae54dda5467c69666aa63c`

## Action metrics

```text
Relay eval — run run_20260925T170839Z_d3b427
provider rules (rules-v0.1) · policy v0.1 · dataset gold-v0.1 · n=100
  Correct action rate       61/100 (61.0%)
  Automation rate           20/100 (20.0%)
  Request-info rate         66/100 (66.0%)
  Human escalation rate     14/100 (14.0%)
  Unsafe automation rate    6/20 (30.0%)
  Invalid outputs           0
  Latency p50 / p95         0 ms / 0 ms
  Cost                      $0.0000000 total, $0.0000000 per case

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         94.0%
  step_therapy              63.0%
  documentation_complete    89.0%
  material_contradiction    85.0%
  missing_evidence          87.0%
```

## Confusion matrices

Evaluation only: rows are the ground-truth answer, columns the provider's answer (yes/no at p_yes >= 0.5; the missing-evidence choice by its top answer). Invalid bundles excluded: 0.

### diagnosis_support

| truth / predicted | yes | no |
|---|---|---|
| yes | 88 | 0 |
| no | 6 | 6 |

### step_therapy

| truth / predicted | yes | no |
|---|---|---|
| yes | 49 | 1 |
| no | 36 | 14 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 63 | 2 |
| no | 9 | 26 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 1 | 13 |
| no | 2 | 84 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 6 | 2 | 0 | 0 | 0 | 2 |
| TREATMENT_HISTORY | 0 | 6 | 0 | 0 | 0 | 7 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 12 | 0 |
| NONE | 0 | 1 | 0 | 0 | 1 | 63 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

Partial missing_evidence distributions (probabilities summing to less than 1; the unassigned mass counts as 0 on every label in the Brier score): 39 of 100.

### diagnosis_support

n = 100 · Brier 0.065 · ECE 0.070

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 10 | 0.500 | 0.800 | +0.300 | low n (< 20) |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 90 | 1.000 | 0.956 | -0.044 |  |

### step_therapy

n = 100 · Brier 0.198 · ECE 0.115

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 51 | 0.500 | 0.412 | -0.088 |  |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 49 | 1.000 | 0.857 | -0.143 |  |

### documentation_complete

n = 100 · Brier 0.117 · ECE 0.125

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 39 | 0.500 | 0.769 | +0.269 |  |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 61 | 1.000 | 0.967 | -0.033 |  |

### material_contradiction

n = 100 · Brier 0.150 · ECE 0.150

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 100 | 1.000 | 0.850 | -0.150 |  |

### missing_evidence

n = 100 · Brier 0.268 · ECE 0.145

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 0 | — | — | — | empty |
| [0.5, 0.6) | 39 | 0.500 | 0.769 | +0.269 |  |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 61 | 1.000 | 0.934 | -0.066 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 20 | 20.0% | 6/20 (30.0%) | 14.0% | 61.0% |  |
| 0.55 | 20 | 20.0% | 6/20 (30.0%) | 14.0% | 61.0% |  |
| 0.60 | 20 | 20.0% | 6/20 (30.0%) | 14.0% | 61.0% |  |
| 0.65 | 20 | 20.0% | 6/20 (30.0%) | 14.0% | 61.0% |  |
| 0.70 | 20 | 20.0% | 6/20 (30.0%) | 14.0% | 61.0% |  |
| 0.75 | 20 | 20.0% | 6/20 (30.0%) | 14.0% | 61.0% |  |
| 0.80 | 20 | 20.0% | 6/20 (30.0%) | 14.0% | 61.0% |  |
| 0.85 | 20 | 20.0% | 6/20 (30.0%) | 14.0% | 61.0% |  |
| 0.90 | 20 | 20.0% | 6/20 (30.0%) | 14.0% | 61.0% |  |
| 0.95 | 20 | 20.0% | 6/20 (30.0%) | 14.0% | 61.0% |  |
| 0.99 | 20 | 20.0% | 6/20 (30.0%) | 14.0% | 61.0% | --at |

No threshold meets the ceiling (UAR <= 1.0% with at least one AUTO_PROCESS); nothing selected.
Frontier is flat across all thresholds.
The UAR ceiling binds: at least one automated threshold's UAR exceeds it.

The selection above is computed on this run's own data. For a held-out report, the threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample selection is shown for reference only.

## Latency and cost

- Latency: p50 0 ms · p95 0 ms
- Estimated cost: $0.0000000 total · $0.0000000 per case

## Limitations

- Synthetic data only. Generated documents come from fixed templates and phrase banks, so they exercise the policy logic and pipeline, not real-world document variety.
- Expected actions are derived from the generator's ground-truth facts through the same engine; they are not independent expert labels.
- Step therapy is composed from date parts treated as independent, which is an approximation.
- Generator and pipeline conventions apply: month-only dates are judged conservatively, and the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).
- Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset must be confirmed on held-out data.
- gen-v0.2 has a residual contradiction tell: a day-precision, non-split MTX medication-history line predicts a contradiction roughly 81% of the time (never 100%), and the NEVER_TAKEN_OTHER_DMARD distractor wording has a weak base-rate skew of its own. Both bear on material_contradiction metrics and on any rule-based baseline built from surface phrasing.
