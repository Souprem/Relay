Relay regression — dataset gen-v0.3-holdout · n=1000
BASELINE  replay-run_20260927T072249Z_204814 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.97
CANDIDATE candidate trace run_20260927T072144Z_12e1e4 · jev q-v0.3 · re-decided at auto_process=0.81

METRIC                  BASELINE          CANDIDATE         Δ         BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     694/1000 (69.4%)  921/1000 (92.1%)  +22.7 pp  [66.4%, 72.2%]   [90.3%, 93.7%]
Automation rate         17/1000 (1.7%)    244/1000 (24.4%)  +22.7 pp  [1.0%, 2.7%]     [21.8%, 27.2%]
Request-info rate       323/1000 (32.3%)  327/1000 (32.7%)  +0.4 pp   [29.4%, 35.3%]   [29.8%, 35.7%]
Human escalation rate   660/1000 (66.0%)  429/1000 (42.9%)  -23.1 pp  [63.0%, 68.9%]   [39.8%, 46.0%]
Unsafe automation rate  1/17 (5.9%)       0/244 (0.0%)      -5.9 pp   [0.1%, 28.7%]    [0.0%, 1.5%]
Invalid outputs         0                 0                 +0

CHANGES: improved 237 · unchanged 753 · regressed 10 · changed-both-wrong 0 · not identical 1000

UNSAFE RESOLVED (1)
  GEN-04000653  expected HUMAN_REVIEW  AUTO_PROCESS → HUMAN_REVIEW
      answer changed: step_therapy · gated crossings: step_therapy: auto_process
      replay: relay replay GEN-04000653 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz

REGRESSED (10)
  GEN-04000114  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000114 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000195  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: diagnosis_support: auto_process; documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000195 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000459  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000459 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000479  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: diagnosis_support: auto_process; documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000479 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000556  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000556 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000583  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000583 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000771  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: diagnosis_support: auto_process; documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000771 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000839  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: diagnosis_support: auto_process; documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000839 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000847  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: documentation_complete: auto_process; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000847 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz
  GEN-04000999  expected HUMAN_REVIEW  HUMAN_REVIEW → REQUEST_INFO
      answer changed: none · gated crossings: documentation_complete: auto_process; material_contradiction: contradiction_auto_block; missing_evidence: missing_evidence_request_info
      replay: relay replay GEN-04000999 --traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/baseline.jsonl.gz --dataset evals/generated/gen-v0.3-holdout --candidate-traces evals/baselines/gen-v0.3-holdout/regression-q-v0.2-vs-q-v0.3/candidate.jsonl.gz

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.001 → 0.001        -0.000   0.029 → 0.029      -0.000
 step_therapy            0.045 → 0.014        -0.031   0.020 → 0.038      +0.018
 documentation_complete  0.036 → 0.036        +0.001   0.073 → 0.072      -0.001
 material_contradiction  0.032 → 0.032        -0.000   0.118 → 0.116      -0.002
 missing_evidence        0.192 → 0.196        +0.003   0.068 → 0.072      +0.003

REGRESSION GATE: PASS
