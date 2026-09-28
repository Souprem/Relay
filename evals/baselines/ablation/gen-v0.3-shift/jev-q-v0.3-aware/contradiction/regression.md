Relay regression — dataset gen-v0.3-shift · n=400
BASELINE  run_20260927T072949Z_bd430c · jev q-v0.3 · policy immunara-v0.2 (v0.2) · thresholds auto_process=0.95
CANDIDATE candidate trace run_20260927T104846Z_0539d2 · jev q-v0.3 · ablate=contradiction

METRIC                  BASELINE         CANDIDATE        Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     297/400 (74.2%)  290/400 (72.5%)  -1.8 pp  [69.7%, 78.5%]   [67.8%, 76.8%]
Automation rate         13/400 (3.2%)    13/400 (3.2%)    +0.0 pp  [1.7%, 5.5%]     [1.7%, 5.5%]
Request-info rate       130/400 (32.5%)  137/400 (34.2%)  +1.8 pp  [27.9%, 37.3%]   [29.6%, 39.1%]
Human escalation rate   257/400 (64.2%)  250/400 (62.5%)  -1.7 pp  [59.3%, 69.0%]   [57.6%, 67.3%]
Unsafe automation rate  0/13 (0.0%)      0/13 (0.0%)      +0.0 pp  [0.0%, 24.7%]    [0.0%, 24.7%]
Invalid outputs         0                0                +0

CHANGES: improved 0 · unchanged 393 · regressed 7 · changed-both-wrong 0 · not identical 387

REGRESSED (7)
  GEN-05000065  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000065 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/contradiction/traces.jsonl.gz
  GEN-05000142  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000142 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/contradiction/traces.jsonl.gz
  GEN-05000231  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000231 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/contradiction/traces.jsonl.gz
  GEN-05000246  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000246 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/contradiction/traces.jsonl.gz
  GEN-05000274  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000274 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/contradiction/traces.jsonl.gz
  GEN-05000294  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000294 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/contradiction/traces.jsonl.gz
  GEN-05000398  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000398 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/contradiction/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.001 → 0.001        +0.000   0.027 → 0.027      +0.000
 step_therapy            0.020 → 0.020        +0.000   0.033 → 0.033      +0.000
 documentation_complete  0.032 → 0.032        +0.000   0.081 → 0.081      +0.000
 material_contradiction  0.030 → 0.030        +0.000   0.120 → 0.120      +0.000
 missing_evidence        0.208 → 0.208        +0.000   0.104 → 0.104      +0.000

REGRESSION GATE: PASS
