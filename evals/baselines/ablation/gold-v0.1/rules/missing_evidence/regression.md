Relay regression — dataset gold-v0.1 · n=100
BASELINE  replay-run_20260925T170839Z_d3b427 · rules rules-v0.1 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.99
CANDIDATE candidate trace run_20260927T104855Z_b08075 · rules rules-v0.1 · ablate=missing_evidence

METRIC                  BASELINE        CANDIDATE       Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     61/100 (61.0%)  61/100 (61.0%)  +0.0 pp  [50.7%, 70.6%]   [50.7%, 70.6%]
Automation rate         20/100 (20.0%)  20/100 (20.0%)  +0.0 pp  [12.7%, 29.2%]   [12.7%, 29.2%]
Request-info rate       66/100 (66.0%)  66/100 (66.0%)  +0.0 pp  [55.8%, 75.2%]   [55.8%, 75.2%]
Human escalation rate   14/100 (14.0%)  14/100 (14.0%)  +0.0 pp  [7.9%, 22.4%]    [7.9%, 22.4%]
Unsafe automation rate  6/20 (30.0%)    6/20 (30.0%)    +0.0 pp  [11.9%, 54.3%]   [11.9%, 54.3%]
Invalid outputs         0               0               +0

CHANGES: improved 0 · unchanged 100 · regressed 0 · changed-both-wrong 0 · not identical 29

STILL UNSAFE (6) — also unsafe in the baseline; not a gate failure
  GOLD-CON-01  expected HUMAN_REVIEW  AUTO_PROCESS → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-01 --traces evals/baselines/ablation/gold-v0.1/rules/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/rules/missing_evidence/traces.jsonl.gz
  GOLD-CON-03  expected HUMAN_REVIEW  AUTO_PROCESS → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-03 --traces evals/baselines/ablation/gold-v0.1/rules/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/rules/missing_evidence/traces.jsonl.gz
  GOLD-CON-04  expected HUMAN_REVIEW  AUTO_PROCESS → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-04 --traces evals/baselines/ablation/gold-v0.1/rules/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/rules/missing_evidence/traces.jsonl.gz
  GOLD-CON-05  expected HUMAN_REVIEW  AUTO_PROCESS → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-05 --traces evals/baselines/ablation/gold-v0.1/rules/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/rules/missing_evidence/traces.jsonl.gz
  GOLD-CON-07  expected HUMAN_REVIEW  AUTO_PROCESS → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-07 --traces evals/baselines/ablation/gold-v0.1/rules/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/rules/missing_evidence/traces.jsonl.gz
  GOLD-CON-10  expected HUMAN_REVIEW  AUTO_PROCESS → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-10 --traces evals/baselines/ablation/gold-v0.1/rules/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/rules/missing_evidence/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.065 → 0.065        +0.000   0.070 → 0.070      +0.000
 step_therapy            0.198 → 0.198        +0.000   0.115 → 0.115      +0.000
 documentation_complete  0.117 → 0.117        +0.000   0.125 → 0.125      +0.000
 material_contradiction  0.150 → 0.150        +0.000   0.150 → 0.150      +0.000
 missing_evidence        0.268 → 0.268        +0.000   0.145 → 0.145      +0.000

REGRESSION GATE: PASS
