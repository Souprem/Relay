Relay regression — dataset gen-v0.3-shift · n=400
BASELINE  run_20260927T072949Z_bd430c · jev q-v0.3 · policy immunara-v0.2 (v0.2) · thresholds auto_process=0.95
CANDIDATE candidate trace run_20260927T104847Z_a295a0 · jev q-v0.3 · ablate=missing_evidence

METRIC                  BASELINE         CANDIDATE        Δ         BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     297/400 (74.2%)  308/400 (77.0%)  +2.7 pp   [69.7%, 78.5%]   [72.6%, 81.0%]
Automation rate         13/400 (3.2%)    13/400 (3.2%)    +0.0 pp   [1.7%, 5.5%]     [1.7%, 5.5%]
Request-info rate       130/400 (32.5%)  89/400 (22.2%)   -10.2 pp  [27.9%, 37.3%]   [18.3%, 26.6%]
Human escalation rate   257/400 (64.2%)  298/400 (74.5%)  +10.3 pp  [59.3%, 69.0%]   [69.9%, 78.7%]
Unsafe automation rate  0/13 (0.0%)      0/13 (0.0%)      +0.0 pp   [0.0%, 24.7%]    [0.0%, 24.7%]
Invalid outputs         0                0                +0

CHANGES: improved 26 · unchanged 359 · regressed 15 · changed-both-wrong 0 · not identical 278

REGRESSED (15)
  GEN-05000008  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000008 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/missing_evidence/traces.jsonl.gz
  GEN-05000067  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000067 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/missing_evidence/traces.jsonl.gz
  GEN-05000091  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000091 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/missing_evidence/traces.jsonl.gz
  GEN-05000117  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000117 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/missing_evidence/traces.jsonl.gz
  GEN-05000163  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000163 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/missing_evidence/traces.jsonl.gz
  GEN-05000204  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000204 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/missing_evidence/traces.jsonl.gz
  GEN-05000208  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000208 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/missing_evidence/traces.jsonl.gz
  GEN-05000217  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000217 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/missing_evidence/traces.jsonl.gz
  GEN-05000238  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000238 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/missing_evidence/traces.jsonl.gz
  GEN-05000249  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000249 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/missing_evidence/traces.jsonl.gz
  GEN-05000267  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000267 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/missing_evidence/traces.jsonl.gz
  GEN-05000271  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000271 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/missing_evidence/traces.jsonl.gz
  GEN-05000295  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000295 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/missing_evidence/traces.jsonl.gz
  GEN-05000349  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000349 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/missing_evidence/traces.jsonl.gz
  GEN-05000351  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-05000351 --traces evals/baselines/gen-v0.3-shift/aware-immunara-v0.2/traces.jsonl.gz --dataset evals/generated/gen-v0.3-shift --candidate-traces evals/baselines/ablation/gen-v0.3-shift/jev-q-v0.3-aware/missing_evidence/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.001 → 0.001        +0.000   0.027 → 0.027      +0.000
 step_therapy            0.020 → 0.020        +0.000   0.033 → 0.033      +0.000
 documentation_complete  0.032 → 0.032        +0.000   0.081 → 0.081      +0.000
 material_contradiction  0.030 → 0.030        +0.000   0.120 → 0.120      +0.000
 missing_evidence        0.208 → 0.208        +0.000   0.104 → 0.104      +0.000

REGRESSION GATE: PASS
