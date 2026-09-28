Relay regression — dataset gold-v0.1 · n=100
BASELINE  replay-run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.89
CANDIDATE candidate trace run_20260927T104853Z_fa7248 · jev q-v0.2 · ablate=missing_evidence

METRIC                  BASELINE        CANDIDATE       Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     91/100 (91.0%)  86/100 (86.0%)  -5.0 pp  [83.6%, 95.8%]   [77.6%, 92.1%]
Automation rate         29/100 (29.0%)  29/100 (29.0%)  +0.0 pp  [20.4%, 38.9%]   [20.4%, 38.9%]
Request-info rate       32/100 (32.0%)  27/100 (27.0%)  -5.0 pp  [23.0%, 42.1%]   [18.6%, 36.8%]
Human escalation rate   39/100 (39.0%)  44/100 (44.0%)  +5.0 pp  [29.4%, 49.3%]   [34.1%, 54.3%]
Unsafe automation rate  1/29 (3.4%)     1/29 (3.4%)     +0.0 pp  [0.1%, 17.8%]    [0.1%, 17.8%]
Invalid outputs         0               0               +0

CHANGES: improved 0 · unchanged 95 · regressed 5 · changed-both-wrong 0 · not identical 61

STILL UNSAFE (1) — also unsafe in the baseline; not a gate failure
  GOLD-TMP-17  expected HUMAN_REVIEW  AUTO_PROCESS → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-TMP-17 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/missing_evidence/traces.jsonl.gz

REGRESSED (5)
  GOLD-MIS-01  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-MIS-01 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/missing_evidence/traces.jsonl.gz
  GOLD-MIS-06  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-MIS-06 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/missing_evidence/traces.jsonl.gz
  GOLD-STR-18  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-STR-18 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/missing_evidence/traces.jsonl.gz
  GOLD-TRK-17  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-TRK-17 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/missing_evidence/traces.jsonl.gz
  GOLD-TRK-18  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-TRK-18 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/missing_evidence/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.011 → 0.011        +0.000   0.049 → 0.049      +0.000
 step_therapy            0.075 → 0.075        +0.000   0.049 → 0.049      +0.000
 documentation_complete  0.063 → 0.063        +0.000   0.035 → 0.035      +0.000
 material_contradiction  0.040 → 0.040        +0.000   0.086 → 0.086      +0.000
 missing_evidence        0.120 → 0.120        +0.000   0.067 → 0.067      +0.000

REGRESSION GATE: PASS
