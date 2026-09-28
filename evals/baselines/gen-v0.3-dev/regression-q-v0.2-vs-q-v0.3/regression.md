Relay regression — dataset gen-v0.3-dev · n=400
BASELINE  replay-run_20260927T071846Z_e950c0 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.97
CANDIDATE candidate trace run_20260927T071912Z_cdaf0c · jev q-v0.3 · re-decided at auto_process=0.81

METRIC                  BASELINE         CANDIDATE        Δ         BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     268/400 (67.0%)  373/400 (93.2%)  +26.2 pp  [62.2%, 71.6%]   [90.3%, 95.5%]
Automation rate         10/400 (2.5%)    114/400 (28.5%)  +26.0 pp  [1.2%, 4.5%]     [24.1%, 33.2%]
Request-info rate       113/400 (28.2%)  112/400 (28.0%)  -0.2 pp   [23.9%, 32.9%]   [23.7%, 32.7%]
Human escalation rate   277/400 (69.2%)  174/400 (43.5%)  -25.8 pp  [64.5%, 73.7%]   [38.6%, 48.5%]
Unsafe automation rate  0/10 (0.0%)      0/114 (0.0%)     +0.0 pp   [0.0%, 30.8%]    [0.0%, 3.2%]
Invalid outputs         0                0                +0

CHANGES: improved 108 · unchanged 289 · regressed 3 · changed-both-wrong 0 · not identical 400

REGRESSED (3)
  GEN-03000014  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-03000014 --traces evals/baselines/gen-v0.3-dev/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-dev --candidate-traces evals/baselines/gen-v0.3-dev/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-03000279  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-03000279 --traces evals/baselines/gen-v0.3-dev/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-dev --candidate-traces evals/baselines/gen-v0.3-dev/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-03000379  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-03000379 --traces evals/baselines/gen-v0.3-dev/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-dev --candidate-traces evals/baselines/gen-v0.3-dev/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.001 → 0.001        +0.000   0.029 → 0.029      +0.000
 step_therapy            0.060 → 0.016        -0.044   0.037 → 0.048      +0.011
 documentation_complete  0.039 → 0.039        +0.000   0.081 → 0.084      +0.003
 material_contradiction  0.032 → 0.032        -0.001   0.120 → 0.118      -0.002
 missing_evidence        0.193 → 0.190        -0.003   0.072 → 0.078      +0.006

REGRESSION GATE: PASS
