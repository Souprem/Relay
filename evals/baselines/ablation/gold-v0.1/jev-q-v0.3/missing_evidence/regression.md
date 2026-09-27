Relay regression — dataset gold-v0.1 · n=100
BASELINE  replay-run_20260927T072623Z_ad6f44 · jev q-v0.3 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.81
CANDIDATE candidate trace run_20260927T104900Z_b9b9ed · jev q-v0.3 · ablate=missing_evidence

METRIC                  BASELINE        CANDIDATE       Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     94/100 (94.0%)  90/100 (90.0%)  -4.0 pp  [87.4%, 97.8%]   [82.4%, 95.1%]
Automation rate         31/100 (31.0%)  31/100 (31.0%)  +0.0 pp  [22.1%, 41.0%]   [22.1%, 41.0%]
Request-info rate       32/100 (32.0%)  28/100 (28.0%)  -4.0 pp  [23.0%, 42.1%]   [19.5%, 37.9%]
Human escalation rate   37/100 (37.0%)  41/100 (41.0%)  +4.0 pp  [27.6%, 47.2%]   [31.3%, 51.3%]
Unsafe automation rate  1/31 (3.2%)     1/31 (3.2%)     +0.0 pp  [0.1%, 16.7%]    [0.1%, 16.7%]
Invalid outputs         0               0               +0

CHANGES: improved 0 · unchanged 96 · regressed 4 · changed-both-wrong 0 · not identical 60

STILL UNSAFE (1) — also unsafe in the baseline; not a gate failure
  GOLD-TMP-16  expected REQUEST_INFO  AUTO_PROCESS → AUTO_PROCESS
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-TMP-16 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/missing_evidence/traces.jsonl.gz

REGRESSED (4)
  GOLD-MIS-01  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-MIS-01 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/missing_evidence/traces.jsonl.gz
  GOLD-MIS-06  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-MIS-06 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/missing_evidence/traces.jsonl.gz
  GOLD-STR-18  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-STR-18 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/missing_evidence/traces.jsonl.gz
  GOLD-TRK-18  expected REQUEST_INFO  REQUEST_INFO → HUMAN_REVIEW
      answer changed: none · gated crossings: none
      replay: relay replay GOLD-TRK-18 --traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/missing_evidence/baseline.jsonl.gz --dataset evals/gold --candidate-traces evals/baselines/ablation/gold-v0.1/jev-q-v0.3/missing_evidence/traces.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.010 → 0.010        +0.000   0.048 → 0.048      +0.000
 step_therapy            0.067 → 0.067        +0.000   0.044 → 0.044      +0.000
 documentation_complete  0.063 → 0.063        +0.000   0.037 → 0.037      +0.000
 material_contradiction  0.041 → 0.041        +0.000   0.094 → 0.094      +0.000
 missing_evidence        0.117 → 0.117        +0.000   0.090 → 0.090      +0.000

REGRESSION GATE: PASS
