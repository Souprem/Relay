Relay regression — dataset gold-v0.1 · n=100
BASELINE  run_20260925T170825Z_440df0 · groundtruth groundtruth · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE candidate trace run_20260927T104851Z_799fe7 · groundtruth groundtruth · ablate=contradiction+missing_evidence

METRIC                  BASELINE          CANDIDATE       Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     100/100 (100.0%)  99/100 (99.0%)  -1.0 pp  [96.4%, 100.0%]  [94.6%, 100.0%]
Automation rate         34/100 (34.0%)    34/100 (34.0%)  +0.0 pp  [24.8%, 44.2%]   [24.8%, 44.2%]
Request-info rate       34/100 (34.0%)    35/100 (35.0%)  +1.0 pp  [24.8%, 44.2%]   [25.7%, 45.2%]
Human escalation rate   32/100 (32.0%)    31/100 (31.0%)  -1.0 pp  [23.0%, 42.1%]   [22.1%, 41.0%]
Unsafe automation rate  0/34 (0.0%)       0/34 (0.0%)     +0.0 pp  [0.0%, 10.3%]    [0.0%, 10.3%]
Invalid outputs         0                 0               +0

CHANGES: improved 0 · unchanged 99 · regressed 1 · changed-both-wrong 0 · not identical 98

REGRESSED (1)
  GOLD-CON-12  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-12 --traces evals/baselines/gold-v0.1/run_20260925T170825Z_440df0/traces.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/groundtruth/contradiction+missing_evidence/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.000 → 0.000        +0.000   0.000 → 0.000      +0.000
 step_therapy            0.000 → 0.000        +0.000   0.000 → 0.000      +0.000
 documentation_complete  0.000 → 0.000        +0.000   0.000 → 0.000      +0.000
 material_contradiction  0.000 → 0.000        +0.000   0.000 → 0.000      +0.000
 missing_evidence        0.000 → 0.000        +0.000   0.000 → 0.000      +0.000

REGRESSION GATE: PASS
