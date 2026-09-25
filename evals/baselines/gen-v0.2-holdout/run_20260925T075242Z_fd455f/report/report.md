# Relay evaluation report — run_20260925T075242Z_fd455f

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Run identity

- Run: `run_20260925T075242Z_fd455f`
- Dataset: `gen-v0.2-holdout` (manifest hash `sha256:958fbfc3e42f7defe76e0a25bca4350e2b97083cc1470ea2e60bcd557c00c786`)
- Provider: `jev` · model `jev-1.13.0` · client `typesafe-sdk==0.7.1`
- Question set: `q-v0.2` (hash `sha256:89717c795a2dfea7efe30e038fb483c6d4ed72d343bfbfcefeabfc6483d7a4aa`)
- Policy version: `v0.1` · policy text hash `sha256:26f6c7aa37c587682cc11249a4001886064a445526954bc6ace1a7c4fd0f0f80`
- Thresholds version: `v0.1`
- Relay commit: `72caf624257a29d39d7be38bd3e5c190225df983`

## Action metrics

```text
Relay eval — run run_20260925T075242Z_fd455f
provider jev (jev-1.13.0) · policy v0.1 · dataset gen-v0.2-holdout · n=1000
  Correct action rate       815/1000 (81.5%)
  Automation rate           172/1000 (17.2%)
  Request-info rate         313/1000 (31.3%)
  Human escalation rate     515/1000 (51.5%)
  Unsafe automation rate    0/172 (0.0%)
  Invalid outputs           0
  Latency p50 / p95         163 ms / 210 ms
  Cost                      $0.1120360 total, $0.0001120 per case

Per-question accuracy (yes/no at p >= 0.5; choice by top answer):
  diagnosis_support         100.0%
  step_therapy              98.3%
  documentation_complete    94.1%
  material_contradiction    98.6%
  missing_evidence          82.1%
```

## Confusion matrices

Evaluation only: rows are the ground-truth answer, columns the provider's answer (yes/no at p_yes >= 0.5; the missing-evidence choice by its top answer). Invalid bundles excluded: 0.

### diagnosis_support

| truth / predicted | yes | no |
|---|---|---|
| yes | 910 | 0 |
| no | 0 | 90 |

### step_therapy

| truth / predicted | yes | no |
|---|---|---|
| yes | 352 | 0 |
| no | 17 | 631 |

### documentation_complete

| truth / predicted | yes | no |
|---|---|---|
| yes | 731 | 0 |
| no | 59 | 210 |

### material_contradiction

| truth / predicted | yes | no |
|---|---|---|
| yes | 115 | 4 |
| no | 10 | 871 |

### missing_evidence

| truth / predicted | DIAGNOSIS | TREATMENT_HISTORY | LAB_RESULT | DOSAGE | INSURANCE_INFORMATION | NONE |
|---|---|---|---|---|---|---|
| DIAGNOSIS | 90 | 0 | 0 | 0 | 0 | 0 |
| TREATMENT_HISTORY | 0 | 82 | 0 | 0 | 0 | 0 |
| LAB_RESULT | 0 | 0 | 0 | 0 | 0 | 0 |
| DOSAGE | 0 | 0 | 0 | 0 | 0 | 0 |
| INSURANCE_INFORMATION | 0 | 0 | 0 | 0 | 97 | 0 |
| NONE | 0 | 179 | 0 | 0 | 0 | 552 |

## Calibration

Confidence is max(p_yes, 1 − p_yes) for yes/no decisions and the probability of the chosen answer for missing evidence. Calibration only means something on data that was not used to tune anything (held-out data). Bins with fewer than 20 predictions are flagged: their accuracy is unreliable. Invalid bundles excluded: 0.

### diagnosis_support

n = 1000 · Brier 0.001 · ECE 0.029

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 0 | — | — | — | empty |
| [0.6, 0.7) | 0 | — | — | — | empty |
| [0.7, 0.8) | 1 | 0.760 | 1.000 | +0.240 | low n (< 20) |
| [0.8, 0.9) | 8 | 0.850 | 1.000 | +0.150 | low n (< 20) |
| [0.9, 1.0] | 991 | 0.972 | 1.000 | +0.028 |  |

### step_therapy

n = 1000 · Brier 0.011 · ECE 0.022

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 19 | 0.550 | 0.526 | -0.024 | low n (< 20) |
| [0.6, 0.7) | 17 | 0.643 | 0.588 | -0.055 | low n (< 20) |
| [0.7, 0.8) | 8 | 0.755 | 1.000 | +0.245 | low n (< 20) |
| [0.8, 0.9) | 19 | 0.863 | 0.947 | +0.084 | low n (< 20) |
| [0.9, 1.0] | 937 | 0.982 | 1.000 | +0.018 |  |

### documentation_complete

n = 1000 · Brier 0.032 · ECE 0.075

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 37 | 0.539 | 0.405 | -0.134 |  |
| [0.6, 0.7) | 35 | 0.643 | 0.314 | -0.329 |  |
| [0.7, 0.8) | 18 | 0.735 | 0.333 | -0.402 | low n (< 20) |
| [0.8, 0.9) | 16 | 0.873 | 0.938 | +0.064 | low n (< 20) |
| [0.9, 1.0] | 894 | 0.943 | 1.000 | +0.057 |  |

### material_contradiction

n = 1000 · Brier 0.030 · ECE 0.121

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.5, 0.6) | 36 | 0.551 | 0.806 | +0.255 |  |
| [0.6, 0.7) | 40 | 0.633 | 0.875 | +0.242 |  |
| [0.7, 0.8) | 66 | 0.752 | 0.970 | +0.218 |  |
| [0.8, 0.9) | 384 | 0.862 | 1.000 | +0.138 |  |
| [0.9, 1.0] | 474 | 0.927 | 1.000 | +0.073 |  |

### missing_evidence

n = 1000 · Brier 0.212 · ECE 0.078

| Bin | n | Mean confidence | Accuracy | Gap (accuracy − confidence) | Flag |
|---|---|---|---|---|---|
| [0.0, 0.5) | 13 | 0.482 | 0.615 | +0.134 | low n (< 20) |
| [0.5, 0.6) | 88 | 0.552 | 0.386 | -0.166 |  |
| [0.6, 0.7) | 92 | 0.649 | 0.424 | -0.226 |  |
| [0.7, 0.8) | 121 | 0.743 | 0.636 | -0.107 |  |
| [0.8, 0.9) | 233 | 0.853 | 0.918 | +0.066 |  |
| [0.9, 1.0] | 453 | 0.963 | 0.991 | +0.028 |  |

## Automation/safety frontier

Only `auto_process` is swept (0.50–0.99 in steps of 0.01); every other threshold stays at the run's version. The engine is re-run on the stored decisions, so this costs no API calls. Ceiling: unsafe automation rate <= 1.0%. Selection rule: maximum automation rate among thresholds with at least one AUTO_PROCESS and an unsafe automation rate <= the ceiling; ties go to the higher threshold.

| auto_process >= | AUTO | Automation | Unsafe / auto (UAR) | Human review | Correct action | Note |
|---|---|---|---|---|---|---|
| 0.50 | 252 | 25.2% | 0/252 (0.0%) | 43.5% | 89.5% |  |
| 0.55 | 252 | 25.2% | 0/252 (0.0%) | 43.5% | 89.5% |  |
| 0.60 | 252 | 25.2% | 0/252 (0.0%) | 43.5% | 89.5% |  |
| 0.65 | 252 | 25.2% | 0/252 (0.0%) | 43.5% | 89.5% |  |
| 0.70 | 252 | 25.2% | 0/252 (0.0%) | 43.5% | 89.5% |  |
| 0.75 | 252 | 25.2% | 0/252 (0.0%) | 43.5% | 89.5% |  |
| 0.80 | 252 | 25.2% | 0/252 (0.0%) | 43.5% | 89.5% |  |
| 0.85 | 252 | 25.2% | 0/252 (0.0%) | 43.5% | 89.5% |  |
| 0.89 | 252 | 25.2% | 0/252 (0.0%) | 43.5% | 89.5% | --at |
| 0.90 | 252 | 25.2% | 0/252 (0.0%) | 43.5% | 89.5% |  |
| 0.91 | 252 | 25.2% | 0/252 (0.0%) | 43.5% | 89.5% | selected |
| 0.95 | 172 | 17.2% | 0/172 (0.0%) | 51.5% | 81.5% |  |

Selected operating point: auto_process >= 0.91 (automation 25.2%, UAR 0/252, correct action 89.5%; ceiling UAR <= 1.0%)

The selection above is computed on this run's own data. For a held-out report, the threshold to judge is the `--at` row, chosen beforehand on the dev set; the in-sample selection is shown for reference only.

## Latency and cost

- Latency: p50 163 ms · p95 210 ms
- Estimated cost: $0.1120360 total · $0.0001120 per case

## Limitations

- Synthetic data only. Generated documents come from fixed templates and phrase banks, so they exercise the policy logic and pipeline, not real-world document variety.
- Expected actions are derived from the generator's ground-truth facts through the same engine; they are not independent expert labels.
- Step therapy is composed from date parts treated as independent, which is an approximation.
- Generator and pipeline conventions apply: month-only dates are judged conservatively, and the pipeline treats a date without a stated year as unknown (gen-v0.2 does not emit them).
- Calibration bins with few predictions are unreliable, and thresholds chosen on one dataset must be confirmed on held-out data.
