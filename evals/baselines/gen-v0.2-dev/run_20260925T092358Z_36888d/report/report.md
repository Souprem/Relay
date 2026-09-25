# Relay evaluation report — run_20260925T092358Z_36888d

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260925T092358Z_36888d`
- Dataset: `gen-v0.2-dev` (manifest hash `sha256:3eec030bbc12d075e3b723bdde174c645641afd3b02d77f9de2f5dbeac16c2ce`)
- Provider: `rules` · model `rules-v0.1` · client n/a
- Question set: `rules-v0.1` (hash `sha256:5bd96c08e7c29353d55a180c4f465a2523a1f04563e31a4af0170fb1d9d92add`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `a7f6a297f42bdc78f87a64fc1d8e0c1d5dd97a54-dirty`

## Action metrics

```text
Relay eval — run run_20260925T092358Z_36888d
provider rules (rules-v0.1) · policy v0.1 · dataset gen-v0.2-dev · n=400
  Correct action rate       261/400 (65.2%)
  Automation rate           56/400 (14.0%)
  Request-info rate         235/400 (58.8%)
  Human escalation rate     109/400 (27.3%)
  Unsafe automation rate    0/56 (0.0%)
  Invalid outputs           0
  Latency p50 / p95         0 ms / 0 ms
  Cost                      $0.0000000 total, $0.0000000 per case

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         93.8%
  step_therapy              63.0%
  documentation_complete    93.5%
  material_contradiction    97.8%
  missing_evidence          93.5%
```

## Confusion matrices

Evaluation only: rows are the ground-truth answer, columns the provider's answer (yes/no at p_yes >= 0.5; the missing-evidence choice by its top answer). Invalid bundles excluded: 0.

### diagnosis_support

| truth / predicted | yes | no |
|---|---|---|
| yes | 356 | 0 |
| no | 25 | 19 |

### step_therapy

| truth / predicted | yes | no |
|---|---|---|
| yes | 132 | 0 |
| no | 148 | 120 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 291 | 0 |
| no | 26 | 83 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 30 | 9 |
| no | 0 | 361 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 19 | 0 | 0 | 0 | 0 | 25 |
| TREATMENT_HISTORY | 0 | 28 | 0 | 0 | 0 | 1 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 36 | 0 |
| NONE | 0 | 0 | 0 | 0 | 0 | 291 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

### diagnosis_support

n = 400 · Brier 0.016 · ECE 0.031

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 25 | 0.500 | 0.000 | -0.500 |  |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 375 | 1.000 | 1.000 | +0.000 |  |

### step_therapy

n = 400 · Brier 0.131 · ECE 0.109

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 209 | 0.500 | 0.292 | -0.208 |  |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 191 | 1.000 | 1.000 | +0.000 |  |

### documentation_complete

n = 400 · Brier 0.110 · ECE 0.155

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 176 | 0.500 | 0.852 | +0.352 |  |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 224 | 1.000 | 1.000 | +0.000 |  |

### material_contradiction

n = 400 · Brier 0.022 · ECE 0.022

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 400 | 1.000 | 0.978 | -0.022 |  |

### missing_evidence

n = 400 · Brier 0.175 · ECE 0.155

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 0 | — | — | — | empty |
| [0.5, 0.6) | 176 | 0.500 | 0.852 | +0.352 |  |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 224 | 1.000 | 1.000 | +0.000 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 56 | 14.0% | 0/56 (0.0%) | 27.3% | 65.2% |  |
| 0.55 | 56 | 14.0% | 0/56 (0.0%) | 27.3% | 65.2% |  |
| 0.60 | 56 | 14.0% | 0/56 (0.0%) | 27.3% | 65.2% |  |
| 0.65 | 56 | 14.0% | 0/56 (0.0%) | 27.3% | 65.2% |  |
| 0.70 | 56 | 14.0% | 0/56 (0.0%) | 27.3% | 65.2% |  |
| 0.75 | 56 | 14.0% | 0/56 (0.0%) | 27.3% | 65.2% |  |
| 0.80 | 56 | 14.0% | 0/56 (0.0%) | 27.3% | 65.2% |  |
| 0.85 | 56 | 14.0% | 0/56 (0.0%) | 27.3% | 65.2% |  |
| 0.90 | 56 | 14.0% | 0/56 (0.0%) | 27.3% | 65.2% |  |
| 0.95 | 56 | 14.0% | 0/56 (0.0%) | 27.3% | 65.2% |  |
| 0.99 | 56 | 14.0% | 0/56 (0.0%) | 27.3% | 65.2% | selected |

Selected operating point: auto_process >= 0.99 (automation 14.0%, UAR 0/56, correct action 65.2%; ceiling UAR <= 1.0%)
Frontier is flat across all thresholds.
The UAR ceiling does not bind at any threshold.

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
