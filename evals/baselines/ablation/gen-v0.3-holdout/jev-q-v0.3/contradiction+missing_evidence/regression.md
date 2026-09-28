Relay regression — dataset gen-v0.3-holdout · n=1000
BASELINE  replay-run_20260927T072144Z_12e1e4 · jev q-v0.3 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.81
CANDIDATE candidate trace run_20260927T104810Z_0ec147 · jev q-v0.3 · ablate=contradiction+missing_evidence

METRIC                  BASELINE          CANDIDATE         Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     921/1000 (92.1%)  938/1000 (93.8%)  +1.7 pp  [90.3%, 93.7%]   [92.1%, 95.2%]
Automation rate         244/1000 (24.4%)  261/1000 (26.1%)  +1.7 pp  [21.8%, 27.2%]   [23.4%, 28.9%]
Request-info rate       327/1000 (32.7%)  247/1000 (24.7%)  -8.0 pp  [29.8%, 35.7%]   [22.1%, 27.5%]
Human escalation rate   429/1000 (42.9%)  492/1000 (49.2%)  +6.3 pp  [39.8%, 46.0%]   [46.1%, 52.3%]
Unsafe automation rate  0/244 (0.0%)      0/261 (0.0%)      +0.0 pp  [0.0%, 1.5%]     [0.0%, 1.4%]
Invalid outputs         0                 0                 +0

CHANGES: improved 70 · unchanged 877 · regressed 53 · changed-both-wrong 0 · not identical 973

REGRESSED (53) — showing 20; --all shows every case
  GEN-04000009  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000009 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000133  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000133 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000179  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000179 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000215  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000215 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000222  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000222 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000225  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000225 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000226  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000226 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000242  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000242 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000251  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000251 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000277  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000277 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000300  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000300 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000302  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000302 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000358  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000358 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000367  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000367 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000373  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000373 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000374  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000374 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000375  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000375 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000400  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000400 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000413  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000413 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GEN-04000446  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000446 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.001 → 0.001        +0.000   0.029 → 0.029      +0.000
 step_therapy            0.014 → 0.014        +0.000   0.038 → 0.038      +0.000
 documentation_complete  0.036 → 0.036        +0.000   0.072 → 0.072      +0.000
 material_contradiction  0.032 → 0.032        +0.000   0.116 → 0.116      +0.000
 missing_evidence        0.196 → 0.196        +0.000   0.072 → 0.072      +0.000

REGRESSION GATE: PASS
