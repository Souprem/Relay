Relay shadow comparison — dataset gen-v0.3-shift · n=400
INCUMBENT simulated run_20260927T073006Z_0b5a58 · jev q-v0.3 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE shadow run_20260927T073007Z_c1a0ba · jev q-v0.3 · policy immunara-v0.2 (v0.2) · thresholds auto_process=0.95

AGREEMENT (unlabelled; what a real shadow deployment sees)
  Action agreement: 397/400 (99.2%)  95% CI [97.8%, 99.8%]

  INCUMBENT \ CANDIDATE  AUTO_PROCESS  REQUEST_INFO  HUMAN_REVIEW
  AUTO_PROCESS           13            0             3
  REQUEST_INFO           0             130           0
  HUMAN_REVIEW           0             0             254

  Would newly auto-process (0): none
  Would stop auto-processing (3): GEN-05000118, GEN-05000257, GEN-05000289

EVALUATION-ONLY (uses ground truth; not available in a real shadow deployment)
Relay regression — dataset gen-v0.3-shift · n=400
BASELINE  simulated run_20260927T073006Z_0b5a58 · jev q-v0.3 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE shadow run_20260927T073007Z_c1a0ba · jev q-v0.3 · policy immunara-v0.2 (v0.2) · thresholds auto_process=0.95

METRIC                  BASELINE         CANDIDATE        Δ         BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     294/400 (73.5%)  297/400 (74.2%)  +0.8 pp   [68.9%, 77.8%]   [69.7%, 78.5%]
Automation rate         16/400 (4.0%)    13/400 (3.2%)    -0.8 pp   [2.3%, 6.4%]     [1.7%, 5.5%]
Request-info rate       130/400 (32.5%)  130/400 (32.5%)  +0.0 pp   [27.9%, 37.3%]   [27.9%, 37.3%]
Human escalation rate   254/400 (63.5%)  257/400 (64.2%)  +0.7 pp   [58.6%, 68.2%]   [59.3%, 69.0%]
Unsafe automation rate  3/16 (18.8%)     0/13 (0.0%)      -18.8 pp  [4.0%, 45.6%]    [0.0%, 24.7%]
Invalid outputs         0                0                +0

CHANGES: improved 3 · unchanged 397 · regressed 0 · changed-both-wrong 0 · not identical 400

UNSAFE RESOLVED (3)
  GEN-05000118  expected HUMAN_REVIEW  AUTO_PROCESS → HUMAN_REVIEW
      answer changed: step_therapy · gated crossings: step_therapy: auto_process
      replay: relay replay GEN-05000118 --traces traces/run_20260927T073006Z_0b5a58.jsonl --dataset evals/generated/gen-v0.3-shift --candidate-traces traces/run_20260927T073007Z_c1a0ba.jsonl
  GEN-05000257  expected HUMAN_REVIEW  AUTO_PROCESS → HUMAN_REVIEW
      answer changed: step_therapy · gated crossings: step_therapy: auto_process
      replay: relay replay GEN-05000257 --traces traces/run_20260927T073006Z_0b5a58.jsonl --dataset evals/generated/gen-v0.3-shift --candidate-traces traces/run_20260927T073007Z_c1a0ba.jsonl
  GEN-05000289  expected HUMAN_REVIEW  AUTO_PROCESS → HUMAN_REVIEW
      answer changed: step_therapy · gated crossings: step_therapy: auto_process
      replay: relay replay GEN-05000289 --traces traces/run_20260927T073006Z_0b5a58.jsonl --dataset evals/generated/gen-v0.3-shift --candidate-traces traces/run_20260927T073007Z_c1a0ba.jsonl

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.001 → 0.001        +0.000   0.027 → 0.027      +0.000
 step_therapy            0.072 → 0.020        -0.053   0.051 → 0.033      -0.018
 documentation_complete  0.032 → 0.032        +0.000   0.081 → 0.081      +0.000
 material_contradiction  0.030 → 0.030        +0.000   0.120 → 0.120      +0.000
 missing_evidence        0.208 → 0.208        +0.000   0.104 → 0.104      +0.000

REGRESSION GATE: PASS

PROMOTION CHECK: PROMOTE
