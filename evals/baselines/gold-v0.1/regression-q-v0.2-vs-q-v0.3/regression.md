Relay regression — dataset gold-v0.1 · n=100
BASELINE  replay-run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.97
CANDIDATE candidate trace run_20260927T072623Z_ad6f44 · jev q-v0.3 · re-decided at auto_process=0.81

METRIC                  BASELINE        CANDIDATE       Δ         BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     69/100 (69.0%)  94/100 (94.0%)  +25.0 pp  [59.0%, 77.9%]   [87.4%, 97.8%]
Automation rate         5/100 (5.0%)    31/100 (31.0%)  +26.0 pp  [1.6%, 11.3%]    [22.1%, 41.0%]
Request-info rate       32/100 (32.0%)  32/100 (32.0%)  +0.0 pp   [23.0%, 42.1%]   [23.0%, 42.1%]
Human escalation rate   63/100 (63.0%)  37/100 (37.0%)  -26.0 pp  [52.8%, 72.4%]   [27.6%, 47.2%]
Unsafe automation rate  0/5 (0.0%)      1/31 (3.2%)     +3.2 pp   [0.0%, 52.2%]    [0.1%, 16.7%]
Invalid outputs         0               0               +0

CHANGES: improved 25 · unchanged 74 · regressed 0 · changed-both-wrong 1 · not identical 100

NEWLY UNSAFE (1)
  GOLD-TMP-16  expected REQUEST_INFO  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: diagnosis_support: auto_process; step_therapy: auto_process; documentation_complete: auto_process
      replay: relay replay GOLD-TMP-16 --traces evals/baselines/gold-v0.1/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/gold-v0.1/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.011 → 0.010        -0.001   0.049 → 0.048      -0.001
 step_therapy            0.075 → 0.067        -0.008   0.049 → 0.044      -0.005
 documentation_complete  0.063 → 0.063        -0.000   0.035 → 0.037      +0.002
 material_contradiction  0.040 → 0.041        +0.002   0.086 → 0.094      +0.008
 missing_evidence        0.120 → 0.117        -0.003   0.067 → 0.090      +0.022

REGRESSION GATE: FAIL — 1 newly unsafe case(s) without a waiver: GOLD-TMP-16
