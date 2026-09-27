Relay regression — dataset gold-v0.1 · n=100
BASELINE  replay-run_20260927T072623Z_ad6f44 · jev q-v0.3 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.81
CANDIDATE candidate trace run_20260927T104859Z_f140aa · jev q-v0.3 · ablate=contradiction

METRIC                  BASELINE        CANDIDATE       Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     94/100 (94.0%)  91/100 (91.0%)  -3.0 pp  [87.4%, 97.8%]   [83.6%, 95.8%]
Automation rate         31/100 (31.0%)  34/100 (34.0%)  +3.0 pp  [22.1%, 41.0%]   [24.8%, 44.2%]
Request-info rate       32/100 (32.0%)  34/100 (34.0%)  +2.0 pp  [23.0%, 42.1%]   [24.8%, 44.2%]
Human escalation rate   37/100 (37.0%)  32/100 (32.0%)  -5.0 pp  [27.6%, 47.2%]   [23.0%, 42.1%]
Unsafe automation rate  1/31 (3.2%)     3/34 (8.8%)     +5.6 pp  [0.1%, 16.7%]    [1.9%, 23.7%]
Invalid outputs         0               0               +0

CHANGES: improved 1 · unchanged 95 · regressed 4 · changed-both-wrong 0 · not identical 98

NEWLY UNSAFE (2)
  GOLD-CON-03  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-03 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/traces.jsonl.gz
  GOLD-CON-13  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-13 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/traces.jsonl.gz

STILL UNSAFE (1) — also unsafe in the baseline; not a gate failure
  GOLD-TMP-16  expected REQUEST_INFO  AUTO_PROCESS → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-TMP-16 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/traces.jsonl.gz

REGRESSED (4)
  GOLD-CON-03  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-03 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/traces.jsonl.gz
  GOLD-CON-05  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-05 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/traces.jsonl.gz
  GOLD-CON-12  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-12 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/traces.jsonl.gz
  GOLD-CON-13  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-CON-13 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/contradiction/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.010 → 0.010        +0.000   0.048 → 0.048      +0.000
 step_therapy            0.067 → 0.067        +0.000   0.044 → 0.044      +0.000
 documentation_complete  0.063 → 0.063        +0.000   0.037 → 0.037      +0.000
 material_contradiction  0.041 → 0.041        +0.000   0.094 → 0.094      +0.000
 missing_evidence        0.117 → 0.117        +0.000   0.090 → 0.090      +0.000

REGRESSION GATE: FAIL — 2 newly unsafe case(s) without a waiver: GOLD-CON-03, GOLD-CON-13
