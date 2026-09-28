Relay regression — dataset gold-v0.1 · n=100
BASELINE  replay-run_20260927T072623Z_ad6f44 · jev q-v0.3 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.81
CANDIDATE candidate trace run_20260927T104901Z_b19adf · jev q-v0.3 · ablate=contradiction+missing_evidence

METRIC                  BASELINE        CANDIDATE       Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     94/100 (94.0%)  88/100 (88.0%)  -6.0 pp  [87.4%, 97.8%]   [80.0%, 93.6%]
Automation rate         31/100 (31.0%)  34/100 (34.0%)  +3.0 pp  [22.1%, 41.0%]   [24.8%, 44.2%]
Request-info rate       32/100 (32.0%)  29/100 (29.0%)  -3.0 pp  [23.0%, 42.1%]   [20.4%, 38.9%]
Human escalation rate   37/100 (37.0%)  37/100 (37.0%)  +0.0 pp  [27.6%, 47.2%]   [27.6%, 47.2%]
Unsafe automation rate  1/31 (3.2%)     3/34 (8.8%)     +5.6 pp  [0.1%, 16.7%]    [1.9%, 23.7%]
Invalid outputs         0               0               +0

CHANGES: improved 1 · unchanged 92 · regressed 7 · changed-both-wrong 0 · not identical 98

NEWLY UNSAFE (2)
  GOLD-CON-03  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-03 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GOLD-CON-13  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-13 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz

STILL UNSAFE (1) — also unsafe in the baseline; not a gate failure
  GOLD-TMP-16  expected REQUEST_INFO  AUTO_PROCESS → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-TMP-16 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz

REGRESSED (7)
  GOLD-CON-03  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-03 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GOLD-CON-12  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-12 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GOLD-CON-13  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-13 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GOLD-MIS-01  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-MIS-01 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GOLD-MIS-06  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-MIS-06 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GOLD-STR-18  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-STR-18 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz
  GOLD-TRK-18  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-TRK-18 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction+missing_evidence/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.010 → 0.010        +0.000   0.048 → 0.048      +0.000
 step_therapy            0.067 → 0.067        +0.000   0.044 → 0.044      +0.000
 documentation_complete  0.063 → 0.063        +0.000   0.037 → 0.037      +0.000
 material_contradiction  0.041 → 0.041        +0.000   0.094 → 0.094      +0.000
 missing_evidence        0.117 → 0.117        +0.000   0.090 → 0.090      +0.000

REGRESSION GATE: FAIL — 2 newly unsafe case(s) without a waiver: GOLD-CON-03, GOLD-CON-13
