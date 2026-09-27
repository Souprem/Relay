Relay regression — dataset gen-v0.2-holdout · n=1000
BASELINE  replay-run_20260925T092425Z_0aee97 · rules rules-v0.1 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.99
CANDIDATE candidate trace run_20260927T104801Z_9fd724 · rules rules-v0.1 · ablate=contradiction+missing_evidence

METRIC                  BASELINE          CANDIDATE         Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     667/1000 (66.7%)  650/1000 (65.0%)  -1.7 pp  [63.7%, 69.6%]   [62.0%, 68.0%]
Automation rate         134/1000 (13.4%)  134/1000 (13.4%)  +0.0 pp  [11.3%, 15.7%]   [11.3%, 15.7%]
Request-info rate       569/1000 (56.9%)  586/1000 (58.6%)  +1.7 pp  [53.8%, 60.0%]   [55.5%, 61.7%]
Human escalation rate   297/1000 (29.7%)  280/1000 (28.0%)  -1.7 pp  [26.9%, 32.6%]   [25.2%, 30.9%]
Unsafe automation rate  0/134 (0.0%)      0/134 (0.0%)      +0.0 pp  [0.0%, 2.7%]     [0.0%, 2.7%]
Invalid outputs         0                 0                 +0

CHANGES: improved 0 · unchanged 983 · regressed 17 · changed-both-wrong 0 · not identical 974

REGRESSED (17)
  GEN-02000091  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000091 --traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000110  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000110 --traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000170  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000170 --traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000203  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000203 --traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000294  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000294 --traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000346  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000346 --traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000370  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000370 --traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000474  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000474 --traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000530  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000530 --traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000543  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000543 --traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000730  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000730 --traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000762  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000762 --traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000774  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000774 --traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000778  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000778 --traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000886  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000886 --traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000970  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000970 --traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/traces.jsonl.gz
  GEN-02000991  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000991 --traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/rules/contradiction+missing_evidence/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.011 → 0.011        +0.000   0.022 → 0.022      +0.000
 step_therapy            0.125 → 0.125        +0.000   0.065 → 0.065      +0.000
 documentation_complete  0.097 → 0.097        +0.000   0.143 → 0.143      +0.000
 material_contradiction  0.026 → 0.026        +0.000   0.026 → 0.026      +0.000
 missing_evidence        0.147 → 0.147        +0.000   0.143 → 0.143      +0.000

REGRESSION GATE: PASS
