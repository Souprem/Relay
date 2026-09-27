Relay regression — dataset gen-v0.2-holdout · n=1000
BASELINE  replay-run_20260925T075242Z_fd455f · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.89
CANDIDATE candidate trace run_20260927T104756Z_037dae · jev q-v0.2 · ablate=contradiction+missing_evidence

METRIC                  BASELINE          CANDIDATE         Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     895/1000 (89.5%)  946/1000 (94.6%)  +5.1 pp  [87.4%, 91.3%]   [93.0%, 95.9%]
Automation rate         252/1000 (25.2%)  277/1000 (27.7%)  +2.5 pp  [22.5%, 28.0%]   [24.9%, 30.6%]
Request-info rate       313/1000 (31.3%)  222/1000 (22.2%)  -9.1 pp  [28.4%, 34.3%]   [19.7%, 24.9%]
Human escalation rate   435/1000 (43.5%)  501/1000 (50.1%)  +6.6 pp  [40.4%, 46.6%]   [47.0%, 53.2%]
Unsafe automation rate  0/252 (0.0%)      0/277 (0.0%)      +0.0 pp  [0.0%, 1.5%]     [0.0%, 1.3%]
Invalid outputs         0                 0                 +0

CHANGES: improved 92 · unchanged 866 · regressed 41 · changed-both-wrong 1 · not identical 974

REGRESSED (41) — showing 20; --all shows every case
  GEN-02000023  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000023 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000031  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000031 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000040  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000040 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000044  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000044 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000054  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000054 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000088  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000088 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000091  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000091 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000141  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000141 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000169  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000169 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000226  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000226 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000257  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000257 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000269  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000269 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000279  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000279 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000338  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000338 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000351  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000351 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000391  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000391 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000413  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000413 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000422  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000422 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000447  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000447 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000456  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000456 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction+missing_evidence/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.001 → 0.001        +0.000   0.029 → 0.029      +0.000
 step_therapy            0.011 → 0.011        +0.000   0.022 → 0.022      +0.000
 documentation_complete  0.032 → 0.032        +0.000   0.075 → 0.075      +0.000
 material_contradiction  0.030 → 0.030        +0.000   0.121 → 0.121      +0.000
 missing_evidence        0.212 → 0.212        +0.000   0.078 → 0.078      +0.000

REGRESSION GATE: PASS
