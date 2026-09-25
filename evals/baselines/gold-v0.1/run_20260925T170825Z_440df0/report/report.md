# Relay evaluation report — run_20260925T170825Z_440df0

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

**groundtruth provider: pipeline validation, not a model result.**

## Run identity

- Run: `run_20260925T170825Z_440df0`
- Dataset: `gold-v0.1` (no dataset manifest)
- Provider: `groundtruth` · model `groundtruth-v1` · client n/a
- Question set: `groundtruth` (hash `n/a`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `2dbcf2c9d24449c2faae54dda5467c69666aa63c`

## Action metrics

```text
Relay eval — run run_20260925T170825Z_440df0
provider groundtruth (groundtruth-v1) · policy v0.1 · dataset gold-v0.1 · n=100
NOTE: groundtruth provider: pipeline validation, not a model result.
  Correct action rate       100/100 (100.0%)
  Automation rate           34/100 (34.0%)
  Request-info rate         34/100 (34.0%)
  Human escalation rate     32/100 (32.0%)
  Unsafe automation rate    0/34 (0.0%)
  Invalid outputs           0
  Latency p50 / p95         unavailable
  Cost                      $0.0000000 total, $0.0000000 per case

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         100.0%
  step_therapy              100.0%
  documentation_complete    100.0%
  material_contradiction    100.0%
  missing_evidence          100.0%
```

## Confusion matrices

Evaluation only: rows are the ground-truth answer, columns the provider's answer (yes/no at p_yes >= 0.5; the missing-evidence choice by its top answer). Invalid bundles excluded: 0.

### diagnosis_support

| truth / predicted | yes | no |
|---|---|---|
| yes | 88 | 0 |
| no | 0 | 12 |

### step_therapy

| truth / predicted | yes | no |
|---|---|---|
| yes | 50 | 0 |
| no | 0 | 50 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 65 | 0 |
| no | 0 | 35 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 14 | 0 |
| no | 0 | 86 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 10 | 0 | 0 | 0 | 0 | 0 |
| TREATMENT_HISTORY | 0 | 13 | 0 | 0 | 0 | 0 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 12 | 0 |
| NONE | 0 | 0 | 0 | 0 | 0 | 65 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

Partial missing_evidence distributions (probabilities summing to less than 1; the unassigned mass counts as 0 on every label in the Brier score): 0 of 100.

### diagnosis_support

n = 100 · Brier 0.000 · ECE 0.000

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 100 | 1.000 | 1.000 | +0.000 |  |

### step_therapy

n = 100 · Brier 0.000 · ECE 0.000

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 100 | 1.000 | 1.000 | +0.000 |  |

### documentation_complete

n = 100 · Brier 0.000 · ECE 0.000

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 100 | 1.000 | 1.000 | +0.000 |  |

### material_contradiction

n = 100 · Brier 0.000 · ECE 0.000

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 100 | 1.000 | 1.000 | +0.000 |  |

### missing_evidence

n = 100 · Brier 0.000 · ECE 0.000

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 0 | — | — | — | empty |
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 100 | 1.000 | 1.000 | +0.000 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 34 | 34.0% | 0/34 (0.0%) | 32.0% | 100.0% |  |
| 0.55 | 34 | 34.0% | 0/34 (0.0%) | 32.0% | 100.0% |  |
| 0.60 | 34 | 34.0% | 0/34 (0.0%) | 32.0% | 100.0% |  |
| 0.65 | 34 | 34.0% | 0/34 (0.0%) | 32.0% | 100.0% |  |
| 0.70 | 34 | 34.0% | 0/34 (0.0%) | 32.0% | 100.0% |  |
| 0.75 | 34 | 34.0% | 0/34 (0.0%) | 32.0% | 100.0% |  |
| 0.80 | 34 | 34.0% | 0/34 (0.0%) | 32.0% | 100.0% |  |
| 0.85 | 34 | 34.0% | 0/34 (0.0%) | 32.0% | 100.0% |  |
| 0.90 | 34 | 34.0% | 0/34 (0.0%) | 32.0% | 100.0% |  |
| 0.95 | 34 | 34.0% | 0/34 (0.0%) | 32.0% | 100.0% |  |
| 0.99 | 34 | 34.0% | 0/34 (0.0%) | 32.0% | 100.0% | selected |

Selected operating point: auto_process >= 0.99 (automation 34.0%, UAR 0/34, correct action 100.0%; ceiling UAR <= 1.0%)
Frontier is flat across all thresholds.
The UAR ceiling does not bind at any threshold.

The selection above is computed on this run's own data. For a held-out report, the threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample selection is shown for reference only.

## Latency and cost

- Latency: unavailable
- Estimated cost: $0.0000000 total · $0.0000000 per case

## Limitations

- Synthetic data only. Generated documents come from fixed templates and phrase banks, so they exercise the policy logic and pipeline, not real-world document variety.
- Expected actions are derived from the generator's ground-truth facts through the same engine; they are not independent expert labels.
- Step therapy is composed from date parts treated as independent, which is an approximation.
- Generator and pipeline conventions apply: month-only dates are judged conservatively, and the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).
- Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset must be confirmed on held-out data.
- gen-v0.2 has a residual contradiction tell: a day-precision, non-split MTX medication-history line predicts a contradiction roughly 81% of the time (never 100%), and the NEVER_TAKEN_OTHER_DMARD distractor wording has a weak base-rate skew of its own. Both bear on material_contradiction metrics and on any rule-based baseline built from surface phrasing.
