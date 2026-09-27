Relay regression — dataset gold-v0.1 · n=100
BASELINE  replay-run_20260926T011730Z_f1852f · claude q-v0.2+claude-prompt-v1 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.55
CANDIDATE candidate trace run_20260927T104858Z_6883ec · claude q-v0.2+claude-prompt-v1 · ablate=missing_evidence

METRIC                  BASELINE        CANDIDATE       Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     93/100 (93.0%)  87/100 (87.0%)  -6.0 pp  [86.1%, 97.1%]   [78.8%, 92.9%]
Automation rate         30/100 (30.0%)  30/100 (30.0%)  +0.0 pp  [21.2%, 40.0%]   [21.2%, 40.0%]
Request-info rate       33/100 (33.0%)  27/100 (27.0%)  -6.0 pp  [23.9%, 43.1%]   [18.6%, 36.8%]
Human escalation rate   37/100 (37.0%)  43/100 (43.0%)  +6.0 pp  [27.6%, 47.2%]   [33.1%, 53.3%]
Unsafe automation rate  1/30 (3.3%)     1/30 (3.3%)     +0.0 pp  [0.1%, 17.2%]    [0.1%, 17.2%]
Invalid outputs         0               0               +0

CHANGES: improved 0 · unchanged 94 · regressed 6 · changed-both-wrong 0 · not identical 58

STILL UNSAFE (1) — also unsafe in the baseline; not a gate failure
  GOLD-TMP-17  expected HUMAN_REVIEW  AUTO_PROCESS → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-TMP-17 --traces evals/baselines/ablation/gold-v0.1/claude/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/missing_evidence/traces.jsonl.gz

REGRESSED (6)
  GOLD-MIS-01  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-MIS-01 --traces evals/baselines/ablation/gold-v0.1/claude/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/missing_evidence/traces.jsonl.gz
  GOLD-MIS-06  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-MIS-06 --traces evals/baselines/ablation/gold-v0.1/claude/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/missing_evidence/traces.jsonl.gz
  GOLD-MIS-16  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-MIS-16 --traces evals/baselines/ablation/gold-v0.1/claude/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/missing_evidence/traces.jsonl.gz
  GOLD-STR-19  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-STR-19 --traces evals/baselines/ablation/gold-v0.1/claude/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/missing_evidence/traces.jsonl.gz
  GOLD-STR-20  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-STR-20 --traces evals/baselines/ablation/gold-v0.1/claude/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/missing_evidence/traces.jsonl.gz
  GOLD-TRK-18  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-TRK-18 --traces evals/baselines/ablation/gold-v0.1/claude/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/claude/missing_evidence/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.008 → 0.008        +0.000   0.049 → 0.049      +0.000
 step_therapy            0.084 → 0.084        +0.000   0.152 → 0.152      +0.000
 documentation_complete  0.046 → 0.046        +0.000   0.098 → 0.098      +0.000
 material_contradiction  0.007 → 0.007        +0.000   0.054 → 0.054      +0.000
 missing_evidence        0.076 → 0.076        +0.000   0.133 → 0.133      +0.000

REGRESSION GATE: PASS
