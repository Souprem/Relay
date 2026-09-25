# Relay evaluation report — run_20260925T092425Z_0aee97

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260925T092425Z_0aee97`
- Dataset: `gen-v0.2-holdout` (manifest hash `sha256:958fbfc3e42f7defe76e0a25bca4350e2b97083cc1470ea2e60bcd557c00c786`)
- Provider: `rules` · model `rules-v0.1` · client n/a
- Question set: `rules-v0.1` (hash `sha256:5bd96c08e7c29353d55a180c4f465a2523a1f04563e31a4af0170fb1d9d92add`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `a7f6a297f42bdc78f87a64fc1d8e0c1d5dd97a54-dirty`

## Action metrics

```text
Relay eval — run run_20260925T092425Z_0aee97
provider rules (rules-v0.1) · policy v0.1 · dataset gen-v0.2-holdout · n=1000
  Correct action rate       667/1000 (66.7%)
  Automation rate           134/1000 (13.4%)
  Request-info rate         569/1000 (56.9%)
  Human escalation rate     297/1000 (29.7%)
  Unsafe automation rate    0/134 (0.0%)
  Invalid outputs           0
  Latency p50 / p95         0 ms / 0 ms
  Cost                      $0.0000000 total, $0.0000000 per case

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         95.5%
  step_therapy              68.6%
  documentation_complete    95.0%
  material_contradiction    97.4%
  missing_evidence          95.0%
```

## Confusion matrices

Evaluation only: rows are the ground-truth answer, columns the provider's answer (yes/no at p_yes >= 0.5; the missing-evidence choice by its top answer). Invalid bundles excluded: 0.

### diagnosis_support

| truth / predicted | yes | no |
|---|---|---|
| yes | 910 | 0 |
| no | 45 | 45 |

### step_therapy

| truth / predicted | yes | no |
|---|---|---|
| yes | 352 | 0 |
| no | 314 | 334 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 731 | 0 |
| no | 50 | 219 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 93 | 26 |
| no | 0 | 881 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 45 | 0 | 0 | 0 | 0 | 45 |
| TREATMENT_HISTORY | 0 | 77 | 0 | 0 | 0 | 5 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 97 | 0 |
| NONE | 0 | 0 | 0 | 0 | 0 | 731 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

### diagnosis_support

n = 1000 · Brier 0.011 · ECE 0.022

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 45 | 0.500 | 0.000 | -0.500 |  |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 955 | 1.000 | 1.000 | +0.000 |  |

### step_therapy

n = 1000 · Brier 0.125 · ECE 0.065

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 499 | 0.500 | 0.371 | -0.129 |  |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 501 | 1.000 | 1.000 | +0.000 |  |

### documentation_complete

n = 1000 · Brier 0.097 · ECE 0.143

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 387 | 0.500 | 0.871 | +0.371 |  |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 613 | 1.000 | 1.000 | +0.000 |  |

### material_contradiction

n = 1000 · Brier 0.026 · ECE 0.026

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 1000 | 1.000 | 0.974 | -0.026 |  |

### missing_evidence

n = 1000 · Brier 0.147 · ECE 0.143

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 0 | — | — | — | empty |
| [0.5, 0.6) | 387 | 0.500 | 0.871 | +0.371 |  |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 613 | 1.000 | 1.000 | +0.000 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 134 | 13.4% | 0/134 (0.0%) | 29.7% | 66.7% |  |
| 0.55 | 134 | 13.4% | 0/134 (0.0%) | 29.7% | 66.7% |  |
| 0.60 | 134 | 13.4% | 0/134 (0.0%) | 29.7% | 66.7% |  |
| 0.65 | 134 | 13.4% | 0/134 (0.0%) | 29.7% | 66.7% |  |
| 0.70 | 134 | 13.4% | 0/134 (0.0%) | 29.7% | 66.7% |  |
| 0.75 | 134 | 13.4% | 0/134 (0.0%) | 29.7% | 66.7% |  |
| 0.80 | 134 | 13.4% | 0/134 (0.0%) | 29.7% | 66.7% |  |
| 0.85 | 134 | 13.4% | 0/134 (0.0%) | 29.7% | 66.7% |  |
| 0.90 | 134 | 13.4% | 0/134 (0.0%) | 29.7% | 66.7% |  |
| 0.95 | 134 | 13.4% | 0/134 (0.0%) | 29.7% | 66.7% |  |
| 0.99 | 134 | 13.4% | 0/134 (0.0%) | 29.7% | 66.7% | selected, --at |

Selected operating point: auto_process >= 0.99 (automation 13.4%, UAR 0/134, correct action 66.7%; ceiling UAR <= 1.0%)
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
