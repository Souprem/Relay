Relay regression — dataset gen-v0.3-holdout · n=1000
BASELINE  replay-run_20260927T072144Z_12e1e4 · jev q-v0.3 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.81
CANDIDATE candidate trace run_20260927T104806Z_bbab80 · jev q-v0.3 · ablate=contradiction

METRIC                  BASELINE          CANDIDATE         Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     921/1000 (92.1%)  922/1000 (92.2%)  +0.1 pp  [90.3%, 93.7%]   [90.4%, 93.8%]
Automation rate         244/1000 (24.4%)  261/1000 (26.1%)  +1.7 pp  [21.8%, 27.2%]   [23.4%, 28.9%]
Request-info rate       327/1000 (32.7%)  343/1000 (34.3%)  +1.6 pp  [29.8%, 35.7%]   [31.4%, 37.3%]
Human escalation rate   429/1000 (42.9%)  396/1000 (39.6%)  -3.3 pp  [39.8%, 46.0%]   [36.6%, 42.7%]
Unsafe automation rate  0/244 (0.0%)      0/261 (0.0%)      +0.0 pp  [0.0%, 1.5%]     [0.0%, 1.4%]
Invalid outputs         0                 0                 +0

CHANGES: improved 17 · unchanged 967 · regressed 16 · changed-both-wrong 0 · not identical 973

REGRESSED (16)
  GEN-04000074  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000074 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/traces.jsonl.gz
  GEN-04000106  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000106 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/traces.jsonl.gz
  GEN-04000222  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000222 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/traces.jsonl.gz
  GEN-04000302  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000302 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/traces.jsonl.gz
  GEN-04000550  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000550 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/traces.jsonl.gz
  GEN-04000587  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000587 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/traces.jsonl.gz
  GEN-04000594  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000594 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/traces.jsonl.gz
  GEN-04000629  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000629 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/traces.jsonl.gz
  GEN-04000729  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000729 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/traces.jsonl.gz
  GEN-04000738  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000738 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/traces.jsonl.gz
  GEN-04000762  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000762 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/traces.jsonl.gz
  GEN-04000782  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000782 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/traces.jsonl.gz
  GEN-04000891  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000891 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/traces.jsonl.gz
  GEN-04000922  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000922 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/traces.jsonl.gz
  GEN-04000954  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000954 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/traces.jsonl.gz
  GEN-04000998  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GEN-04000998 --traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/ablation/gen-v0.3-holdout/jev-q-v0.3/contradiction/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.001 → 0.001        +0.000   0.029 → 0.029      +0.000
 step_therapy            0.014 → 0.014        +0.000   0.038 → 0.038      +0.000
 documentation_complete  0.036 → 0.036        +0.000   0.072 → 0.072      +0.000
 material_contradiction  0.032 → 0.032        +0.000   0.116 → 0.116      +0.000
 missing_evidence        0.196 → 0.196        +0.000   0.072 → 0.072      +0.000

REGRESSION GATE: PASS
