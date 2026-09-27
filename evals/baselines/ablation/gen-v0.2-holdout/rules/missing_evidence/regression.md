Relay regression — dataset gen-v0.2-holdout · n=1000
BASELINE  replay-run_20260925T092425Z_0aee97 · rules rules-v0.1 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.99
CANDIDATE candidate trace run_20260927T104759Z_38dd95 · rules rules-v0.1 · ablate=missing_evidence

METRIC                  BASELINE          CANDIDATE         Δ        BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     667/1000 (66.7%)  667/1000 (66.7%)  +0.0 pp  [63.7%, 69.6%]   [63.7%, 69.6%]
Automation rate         134/1000 (13.4%)  134/1000 (13.4%)  +0.0 pp  [11.3%, 15.7%]   [11.3%, 15.7%]
Request-info rate       569/1000 (56.9%)  569/1000 (56.9%)  +0.0 pp  [53.8%, 60.0%]   [53.8%, 60.0%]
Human escalation rate   297/1000 (29.7%)  297/1000 (29.7%)  +0.0 pp  [26.9%, 32.6%]   [26.9%, 32.6%]
Unsafe automation rate  0/134 (0.0%)      0/134 (0.0%)      +0.0 pp  [0.0%, 2.7%]     [0.0%, 2.7%]
Invalid outputs         0                 0                 +0

CHANGES: improved 0 · unchanged 1000 · regressed 0 · changed-both-wrong 0 · not identical 317

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.011 → 0.011        +0.000   0.022 → 0.022      +0.000
 step_therapy            0.125 → 0.125        +0.000   0.065 → 0.065      +0.000
 documentation_complete  0.097 → 0.097        +0.000   0.143 → 0.143      +0.000
 material_contradiction  0.026 → 0.026        +0.000   0.026 → 0.026      +0.000
 missing_evidence        0.147 → 0.147        +0.000   0.143 → 0.143      +0.000

REGRESSION GATE: PASS
