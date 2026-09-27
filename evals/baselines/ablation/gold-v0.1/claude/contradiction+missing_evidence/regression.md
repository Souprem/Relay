Relay regression — dataset gold-v0.1 · n=100
BASELINE  replay-run_20260926T011730Z_f1852f · claude q-v0.2+claude-prompt-v1 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.55
CANDIDATE candidate trace run_20260927T104858Z_46f6b1 · claude q-v0.2+claude-prompt-v1 · ablate=contradiction+missing_evidence

METRIC                  BASELINE        CANDIDATE       Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     93/100 (93.0%)  86/100 (86.0%)  -7.0 pp  [86.1%, 97.1%]   [77.6%, 92.1%]
Automation rate         30/100 (30.0%)  34/100 (34.0%)  +4.0 pp  [21.2%, 40.0%]   [24.8%, 44.2%]
Request-info rate       33/100 (33.0%)  28/100 (28.0%)  -5.0 pp  [23.9%, 43.1%]   [19.5%, 37.9%]
Human escalation rate   37/100 (37.0%)  38/100 (38.0%)  +1.0 pp  [27.6%, 47.2%]   [28.5%, 48.3%]
Unsafe automation rate  1/30 (3.3%)     3/34 (8.8%)     +5.5 pp  [0.1%, 17.2%]    [1.9%, 23.7%]
Invalid outputs         0               0               +0

CHANGES: improved 2 · unchanged 89 · regressed 9 · changed-both-wrong 0 · not identical 98

NEWLY UNSAFE (2)
  GOLD-CON-03  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-03 --traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/traces.jsonl.gz
  GOLD-CON-13  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-13 --traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/traces.jsonl.gz

STILL UNSAFE (1) — also unsafe in the baseline; not a gate failure
  GOLD-TMP-17  expected HUMAN_REVIEW  AUTO_PROCESS → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-TMP-17 --traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/traces.jsonl.gz

REGRESSED (9)
  GOLD-CON-03  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-03 --traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/traces.jsonl.gz
  GOLD-CON-12  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-12 --traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/traces.jsonl.gz
  GOLD-CON-13  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-13 --traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/traces.jsonl.gz
  GOLD-MIS-01  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-MIS-01 --traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/traces.jsonl.gz
  GOLD-MIS-06  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-MIS-06 --traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/traces.jsonl.gz
  GOLD-MIS-16  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-MIS-16 --traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/traces.jsonl.gz
  GOLD-STR-19  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-STR-19 --traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/traces.jsonl.gz
  GOLD-STR-20  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-STR-20 --traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/traces.jsonl.gz
  GOLD-TRK-18  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-TRK-18 --traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/contradiction+missing_evidence/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.008 → 0.008        +0.000   0.049 → 0.049      +0.000
 step_therapy            0.084 → 0.084        +0.000   0.152 → 0.152      +0.000
 documentation_complete  0.046 → 0.046        +0.000   0.098 → 0.098      +0.000
 material_contradiction  0.007 → 0.007        +0.000   0.054 → 0.054      +0.000
 missing_evidence        0.076 → 0.076        +0.000   0.133 → 0.133      +0.000

REGRESSION GATE: FAIL — 2 newly unsafe case(s) without a waiver: GOLD-CON-03, GOLD-CON-13
