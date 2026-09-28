Relay regression — dataset gen-v0.3-shift · n=400
BASELINE  run_20260927T072948Z_e5915e · jev q-v0.3 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE candidate trace run_20260927T072949Z_bd430c · jev q-v0.3

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
      replay: relay replay GEN-05000118 --traces evals/baselines/gen-v0.3-shift/stale-immunara-v0.1/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz
  GEN-05000257  expected HUMAN_REVIEW  AUTO_PROCESS → HUMAN_REVIEW
      answer changed: step_therapy · gated crossings: step_therapy: auto_process
      replay: relay replay GEN-05000257 --traces evals/baselines/gen-v0.3-shift/stale-immunara-v0.1/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz
  GEN-05000289  expected HUMAN_REVIEW  AUTO_PROCESS → HUMAN_REVIEW
      answer changed: step_therapy · gated crossings: step_therapy: auto_process
      replay: relay replay GEN-05000289 --traces evals/baselines/gen-v0.3-shift/stale-immunara-v0.1/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.001 → 0.001        +0.000   0.027 → 0.027      +0.000
 step_therapy            0.072 → 0.020        -0.053   0.051 → 0.033      -0.018
 documentation_complete  0.032 → 0.032        +0.000   0.081 → 0.081      +0.000
 material_contradiction  0.030 → 0.030        +0.000   0.120 → 0.120      +0.000
 missing_evidence        0.208 → 0.208        +0.000   0.104 → 0.104      +0.000

REGRESSION GATE: PASS
