Relay regression — dataset gen-v0.2-holdout · n=150
BASELINE  replay-run_20260925T212034Z_bbee49 · claude q-v0.2+claude-prompt-v1 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.55
CANDIDATE candidate trace run_20260927T104802Z_5ac2f7 · claude q-v0.2+claude-prompt-v1 · ablate=contradiction

METRIC                  BASELINE         CANDIDATE        Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     147/150 (98.0%)  144/150 (96.0%)  -2.0 pp  [94.3%, 99.6%]   [91.5%, 98.5%]
Automation rate         37/150 (24.7%)   37/150 (24.7%)   +0.0 pp  [18.0%, 32.4%]   [18.0%, 32.4%]
Request-info rate       47/150 (31.3%)   50/150 (33.3%)   +2.0 pp  [24.0%, 39.4%]   [25.9%, 41.5%]
Human escalation rate   66/150 (44.0%)   63/150 (42.0%)   -2.0 pp  [35.9%, 52.3%]   [34.0%, 50.3%]
Unsafe automation rate  0/37 (0.0%)      0/37 (0.0%)      +0.0 pp  [0.0%, 9.5%]     [0.0%, 9.5%]
Invalid outputs         0                0                +0

CHANGES: improved 0 · unchanged 147 · regressed 3 · changed-both-wrong 0 · not identical 146

REGRESSED (3)
  GEN-02000294  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000294 --traces evals/baselines/ablation/gen-v0.2-holdout/claude-150/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/claude-150/contradiction/traces.jsonl.gz
  GEN-02000370  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000370 --traces evals/baselines/ablation/gen-v0.2-holdout/claude-150/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/claude-150/contradiction/traces.jsonl.gz
  GEN-02000970  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-02000970 --traces evals/baselines/ablation/gen-v0.2-holdout/claude-150/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.2-holdout --candidate-traces evals/baselines/ablation/gen-v0.2-holdout/claude-150/contradiction/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.002 → 0.002        +0.000   0.041 → 0.041      +0.000
 step_therapy            0.027 → 0.027        +0.000   0.101 → 0.101      +0.000
 documentation_complete  0.044 → 0.044        +0.000   0.029 → 0.029      +0.000
 material_contradiction  0.002 → 0.002        +0.000   0.041 → 0.041      +0.000
 missing_evidence        0.083 → 0.083        +0.000   0.137 → 0.137      +0.000

REGRESSION GATE: PASS
