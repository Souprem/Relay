# Relay evaluation report — run_20260925T131052Z_f328de

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260925T131052Z_f328de`
- Dataset: `smoke-v0.1` (no dataset manifest)
- Provider: `claude` · model `claude-opus-5` · client `anthropic==1.8.0`
- Question set: `q-v0.2+claude-prompt-v1` (hash `sha256:d24c74fa140ca4682e6202ea36a2bdc978085216c8b220fe413c4e09005cc9b6`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `b08461302f57c5645af4018a9a0114a59472907a`

## Action metrics

```text
Relay eval — run run_20260925T131052Z_f328de
provider claude (claude-opus-5) · policy v0.1 · dataset smoke-v0.1 · n=10
  Correct action rate       7/10 (70.0%)
  Automation rate           0/10 (0.0%)
  Request-info rate         3/10 (30.0%)
  Human escalation rate     7/10 (70.0%)
  Unsafe automation rate    n/a (no AUTO_PROCESS actions)
  Invalid outputs           0
  Refusals                  0
  Latency p50 / p95         5169 ms / 6781 ms  [low-sample: n=10 < 30]
  Cost                      $0.2546660 total, $0.0254666 per case
  Prompt cache reads        50.7% of prompt tokens

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         100.0%
  step_therapy              100.0%
  documentation_complete    90.0%
  material_contradiction    100.0%
  missing_evidence          90.0%
```

## Confusion matrices

Evaluation only: rows are the ground-truth answer, columns the provider's answer (yes/no at p_yes >= 0.5; the missing-evidence choice by its top answer). Invalid bundles excluded: 0.

### diagnosis_support

| truth / predicted | yes | no |
|---|---|---|
| yes | 9 | 0 |
| no | 0 | 1 |

### step_therapy

| truth / predicted | yes | no |
|---|---|---|
| yes | 6 | 0 |
| no | 0 | 4 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 7 | 0 |
| no | 1 | 2 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 1 | 0 |
| no | 0 | 9 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 1 | 0 | 0 | 0 | 0 | 0 |
| TREATMENT_HISTORY | 0 | 1 | 0 | 0 | 0 | 0 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 1 | 0 |
| NONE | 0 | 1 | 0 | 0 | 0 | 6 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

Partial missing_evidence distributions (probabilities summing to less than 1; the unassigned mass counts as 0 on every label in the Brier score): 0 of 10.

### diagnosis_support

n = 10 · Brier 0.001 · ECE 0.037

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 10 | 0.963 | 1.000 | +0.037 | low n (< 20) |

### step_therapy

n = 10 · Brier 0.054 · ECE 0.177

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 4 | 0.672 | 1.000 | +0.328 | low n (< 20) |
| [0.7, 0.8) | 1 | 0.736 | 1.000 | +0.264 | low n (< 20) |
| [0.8, 0.9) | 1 | 0.815 | 1.000 | +0.185 | low n (< 20) |
| [0.9, 1.0] | 4 | 0.997 | 1.000 | +0.003 | low n (< 20) |

### documentation_complete

n = 10 · Brier 0.061 · ECE 0.133

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 1 | 0.750 | 0.000 | -0.750 | low n (< 20) |
| [0.8, 0.9) | 1 | 0.850 | 1.000 | +0.150 | low n (< 20) |
| [0.9, 1.0] | 8 | 0.946 | 1.000 | +0.054 | low n (< 20) |

### material_contradiction

n = 10 · Brier 0.001 · ECE 0.032

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 0 | — | — | — | empty |
| [0.8, 0.9) | 0 | — | — | — | empty |
| [0.9, 1.0] | 10 | 0.968 | 1.000 | +0.032 | low n (< 20) |

### missing_evidence

n = 10 · Brier 0.084 · ECE 0.174

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 0 | — | — | — | empty |
| [0.5, 0.6) | 1 | 0.500 | 0.000 | -0.500 | low n (< 20) |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 1 | 0.750 | 1.000 | +0.250 | low n (< 20) |
| [0.8, 0.9) | 5 | 0.852 | 1.000 | +0.148 | low n (< 20) |
| [0.9, 1.0] | 3 | 0.917 | 1.000 | +0.083 | low n (< 20) |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 3 | 30.0% | 0/3 (0.0%) | 40.0% | 100.0% |  |
| 0.55 | 3 | 30.0% | 0/3 (0.0%) | 40.0% | 100.0% |  |
| 0.60 | 3 | 30.0% | 0/3 (0.0%) | 40.0% | 100.0% |  |
| 0.65 | 3 | 30.0% | 0/3 (0.0%) | 40.0% | 100.0% |  |
| 0.66 | 3 | 30.0% | 0/3 (0.0%) | 40.0% | 100.0% | selected |
| 0.70 | 2 | 20.0% | 0/2 (0.0%) | 50.0% | 90.0% |  |
| 0.75 | 1 | 10.0% | 0/1 (0.0%) | 60.0% | 80.0% |  |
| 0.80 | 1 | 10.0% | 0/1 (0.0%) | 60.0% | 80.0% |  |
| 0.85 | 0 | 0.0% | n/a (no AUTO) | 70.0% | 70.0% |  |
| 0.90 | 0 | 0.0% | n/a (no AUTO) | 70.0% | 70.0% |  |
| 0.95 | 0 | 0.0% | n/a (no AUTO) | 70.0% | 70.0% |  |

Selected operating point: auto_process >= 0.66 (automation 30.0%, UAR 0/3, correct action 100.0%; ceiling UAR <= 1.0%)
The UAR ceiling does not bind at any threshold.

The selection above is computed on this run's own data. For a held-out report, the threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample selection is shown for reference only.

## Latency and cost

- Latency: p50 5169 ms · p95 6781 ms (low sample: n=10)
- Estimated cost: $0.2546660 total · $0.0254666 per case

## Limitations

- Synthetic data only. Generated documents come from fixed templates and phrase banks, so they exercise the policy logic and pipeline, not real-world document variety.
- Expected actions are derived from the generator's ground-truth facts through the same engine; they are not independent expert labels.
- Step therapy is composed from date parts treated as independent, which is an approximation.
- Generator and pipeline conventions apply: month-only dates are judged conservatively, and the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).
- Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset must be confirmed on held-out data.
- gen-v0.2 has a residual contradiction tell: a day-precision, non-split MTX medication-history line predicts a contradiction roughly 81% of the time (never 100%), and the NEVER_TAKEN_OTHER_DMARD distractor wording has a weak base-rate skew of its own. Both bear on material_contradiction metrics and on any rule-based baseline built from surface phrasing.
