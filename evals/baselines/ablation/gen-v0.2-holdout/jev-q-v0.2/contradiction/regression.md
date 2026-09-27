Relay regression — dataset gen-v0.2-holdout · n=1000
BASELINE  replay-run_20260925T075242Z_fd455f · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.89
CANDIDATE candidate trace run_20260927T104753Z_bce174 · jev q-v0.2 · ablate=contradiction

METRIC                  BASELINE          CANDIDATE         Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     895/1000 (89.5%)  908/1000 (90.8%)  +1.3 pp  [87.4%, 91.3%]   [88.8%, 92.5%]
Automation rate         252/1000 (25.2%)  277/1000 (27.7%)  +2.5 pp  [22.5%, 28.0%]   [24.9%, 30.6%]
Request-info rate       313/1000 (31.3%)  325/1000 (32.5%)  +1.2 pp  [28.4%, 34.3%]   [29.6%, 35.5%]
Human escalation rate   435/1000 (43.5%)  398/1000 (39.8%)  -3.7 pp  [40.4%, 46.6%]   [36.8%, 42.9%]
Unsafe automation rate  0/252 (0.0%)      0/277 (0.0%)      +0.0 pp  [0.0%, 1.5%]     [0.0%, 1.3%]
Invalid outputs         0                 0                 +0

CHANGES: improved 25 · unchanged 963 · regressed 12 · changed-both-wrong 0 · not identical 974

REGRESSED (12)
  GEN-02000054  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000054 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/traces.jsonl.gz
  GEN-02000091  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000091 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/traces.jsonl.gz
  GEN-02000118  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000118 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/traces.jsonl.gz
  GEN-02000447  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000447 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/traces.jsonl.gz
  GEN-02000474  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000474 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/traces.jsonl.gz
  GEN-02000543  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000543 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/traces.jsonl.gz
  GEN-02000730  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000730 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/traces.jsonl.gz
  GEN-02000766  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000766 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/traces.jsonl.gz
  GEN-02000778  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000778 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/traces.jsonl.gz
  GEN-02000814  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000814 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/traces.jsonl.gz
  GEN-02000862  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000862 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/traces.jsonl.gz
  GEN-02000991  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000991 --traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/jev-q-v0.2/contradiction/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.001 → 0.001        +0.000   0.029 → 0.029      +0.000
 step_therapy            0.011 → 0.011        +0.000   0.022 → 0.022      +0.000
 documentation_complete  0.032 → 0.032        +0.000   0.075 → 0.075      +0.000
 material_contradiction  0.030 → 0.030        +0.000   0.121 → 0.121      +0.000
 missing_evidence        0.212 → 0.212        +0.000   0.078 → 0.078      +0.000

REGRESSION GATE: PASS
