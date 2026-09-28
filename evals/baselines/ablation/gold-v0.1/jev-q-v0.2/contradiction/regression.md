Relay regression — dataset gold-v0.1 · n=100
BASELINE  replay-run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.89
CANDIDATE candidate trace run_20260927T104852Z_a1093c · jev q-v0.2 · ablate=contradiction

METRIC                  BASELINE        CANDIDATE       Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     91/100 (91.0%)  87/100 (87.0%)  -4.0 pp  [83.6%, 95.8%]   [78.8%, 92.9%]
Automation rate         29/100 (29.0%)  32/100 (32.0%)  +3.0 pp  [20.4%, 38.9%]   [23.0%, 42.1%]
Request-info rate       32/100 (32.0%)  35/100 (35.0%)  +3.0 pp  [23.0%, 42.1%]   [25.7%, 45.2%]
Human escalation rate   39/100 (39.0%)  33/100 (33.0%)  -6.0 pp  [29.4%, 49.3%]   [23.9%, 43.1%]
Unsafe automation rate  1/29 (3.4%)     3/32 (9.4%)     +5.9 pp  [0.1%, 17.8%]    [2.0%, 25.0%]
Invalid outputs         0               0               +0

CHANGES: improved 1 · unchanged 94 · regressed 5 · changed-both-wrong 0 · not identical 98

NEWLY UNSAFE (2)
  GOLD-CON-03  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-03 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/contradiction/traces.jsonl.gz
  GOLD-CON-13  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-13 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/contradiction/traces.jsonl.gz

STILL UNSAFE (1) — also unsafe in the baseline; not a gate failure
  GOLD-TMP-17  expected HUMAN_REVIEW  AUTO_PROCESS → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-TMP-17 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/contradiction/traces.jsonl.gz

REGRESSED (5)
  GOLD-CON-03  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-03 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/contradiction/traces.jsonl.gz
  GOLD-CON-05  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-05 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/contradiction/traces.jsonl.gz
  GOLD-CON-12  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-12 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/contradiction/traces.jsonl.gz
  GOLD-CON-13  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-13 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/contradiction/traces.jsonl.gz
  GOLD-CON-14  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-14 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/contradiction/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.2/contradiction/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.011 → 0.011        +0.000   0.049 → 0.049      +0.000
 step_therapy            0.075 → 0.075        +0.000   0.049 → 0.049      +0.000
 documentation_complete  0.063 → 0.063        +0.000   0.035 → 0.035      +0.000
 material_contradiction  0.040 → 0.040        +0.000   0.086 → 0.086      +0.000
 missing_evidence        0.120 → 0.120        +0.000   0.067 → 0.067      +0.000

REGRESSION GATE: FAIL — 2 newly unsafe case(s) without a waiver: GOLD-CON-03, GOLD-CON-13
