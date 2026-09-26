# Phase 2B Design: Evaluation Depth (Calibration, Threshold Sweep, Reports, Comparison)

- **Date:** 2026-09-25
- **Status:** Approved by controller. The user delegated Phase 2 design decisions.
- **Depends on:** 2A generated datasets `gen-v0.2-dev` and `gen-v0.2-holdout`
- **Parent:** handoff §"Evaluation plan", §"Calibration", §"Baselines and experiments"

## 1. Goal

Turn traces into credible evidence about whether confidence can be trusted, and about how much automation is safe:

- per-decision calibration (reliability bins, Brier score, ECE)
- confusion matrices
- an automation/safety frontier from sweeping the `auto_process` threshold
- a held-out tuning protocol
- provider/run comparison
- report files (Markdown, JSON and CSV) that the Phase 4 dashboard can later render

It also does the v0.1 carry-overs: a policy-text hash in traces, and question set `q-v0.2`.

All analysis is **offline over stored traces**. Sweeps re-run the deterministic engine on stored decision bundles, so they cost zero API calls. The only live API usage in B is the Jev runs listed in §8.

## 2. Settled decisions

| # | Decision |
|---|---|
| E1 | Pure Python, no numpy/pandas/sklearn. The math is small, and exactness matters more than speed at this scale. |
| E2 | Calibration for a yes/no decision: `confidence = max(p_yes, 1 - p_yes)` and `correct = (p_yes >= 0.5) == truth`. There are five equal-width bins over [0.5, 1.0]: [0.5,0.6), [0.6,0.7), [0.7,0.8), [0.8,0.9), [0.9,1.0], with 1.0 falling in the last bin. Brier score = mean of (p_yes − y)². ECE = Σ_b (n_b/N)·\|acc_b − conf_b\|. Bins with no predictions are still listed, with n=0. |
| E3 | Calibration for the `missing_evidence` choice: `confidence` is the probability of the chosen answer and `correct = answer == truth`. The same five bins are used, with a lower edge of 0.0 added as a sixth bin [0.0, 0.5) because choice confidence can drop below 0.5. Multiclass Brier = mean over cases of Σ_k (p_k − 1[k = truth])², over the six labels, with absent labels counted as 0. |
| E4 | Invalid bundles (where `bundle_problem` is not None) are excluded from calibration and confusion matrices and counted separately. |
| E5 | Sweep: vary only `auto_process` over 0.50…0.99 in steps of 0.01 (50 points), keeping every other v0.1 threshold fixed. For each point, re-run `determine_action` on each trace's stored bundle. Expected actions come from ground truth, and certain probabilities make them independent of `auto_process`. |
| E6 | Operating-point selection (on **dev only**): the maximum automation rate among points with ≥1 AUTO_PROCESS and UAR ≤ `ceiling` (default 0.01). Ties go to the higher threshold, because it's more conservative. If no point qualifies, report "no threshold meets the ceiling" and select nothing. Never fabricate a point. |
| E7 | Held-out protocol: choose the threshold on `gen-v0.2-dev` traces, then report its performance on `gen-v0.2-holdout` traces with `--at <t>`. Calibration is reported on holdout. Holdout results are never used to change anything. |
| E8 | Traces gain `policy_text_hash: str \| None = None`, the SHA-256 of `policy.text` filled by the runner. `DecisionBundle` gains `client_version: str \| None = None`: the Jev provider sets it to `typesafe-sdk==<version>`, and ground truth leaves it `None`. Both default to `None`, so the committed v0.1 baseline traces still load. |
| E9 | `read_traces` also accepts `.jsonl.gz`. Committed baseline traces for generated datasets are stored gzipped. |
| E10 | Question set `q-v0.2`: an explicit version that changes two criteria, described in §6. `build_questions(policy, years, version="q-v0.2")` keeps `q-v0.1` available. The Jev provider takes `question_set_version`, and the CLI takes `--questions` (default `q-v0.2` after B). Whether to adopt q-v0.2 is decided on **dev only** and recorded in the README with both results. |
| E11 | Comparing runs means comparing trace files over the same dataset. For each file it shows the action metrics, calibration summary, and chosen/at-threshold frontier point. It also lists the cases whose action differs between run pairs, flagging new unsafe automations first. Traces must cover the same case ids with matching case hashes, otherwise it's an error. |

## 3. Components

```text
relay/evaluation/
├── calibration.py   # reliability bins, Brier, ECE (binary + multiclass), CalibrationReport
├── confusion.py     # per-decision confusion matrices (yes/no 2x2; choice label x label)
├── frontier.py      # threshold sweep over stored bundles, operating-point selection
├── compare.py       # multi-run comparison, action diffs
└── artifacts.py     # write Markdown/JSON/CSV report bundles
relay/reporting.py   # + render functions for the new sections (Markdown + terminal)
relay/cli.py         # + sweep, report, compare commands; eval/run gain --questions
relay/decisions/questions.py  # versioned question sets (q-v0.1, q-v0.2)
relay/decisions/jev.py        # question_set_version + client_version
relay/decisions/base.py       # DecisionBundle.client_version
relay/traces/models.py        # WorkflowTrace.policy_text_hash
relay/traces/store.py         # .jsonl.gz reading
relay/evaluation/runner.py    # fills policy_text_hash
```

### 3.1 Interfaces (key signatures)

- `calibration.binary_calibration(pairs: Sequence[tuple[float, bool]]) -> CalibrationReport`
- `calibration.choice_calibration(items: Sequence[tuple[Mapping[str, float], str, str]], labels: Sequence[str]) -> CalibrationReport`. Each item is (probabilities, predicted answer, truth).
- `CalibrationReport`: `n`, `brier`, `ece`, and `bins: list[CalibrationBin(lower, upper, n, mean_confidence, accuracy)]`. Fields are `None` when `n == 0`.
- `calibration.calibrate_run(traces, cases) -> dict[str, CalibrationReport]`, keyed by decision id, with `invalid_excluded: int` alongside.
- `confusion.confusion_matrices(traces, cases) -> dict[str, ConfusionMatrix]`
- `frontier.sweep(traces, cases, *, points=None) -> list[FrontierPoint]`. Each point records `auto_threshold, n, auto, request_info, human_review, unsafe, correct, automation_rate, uar (None if auto==0), human_review_rate, correct_action_rate`.
- `frontier.select_operating_point(points, ceiling=0.01) -> FrontierPoint | None`
- `compare.compare_runs(runs: Sequence[tuple[str, Sequence[WorkflowTrace]]], cases) -> Comparison`
- `artifacts.write_eval_bundle(out_dir, summary, calibration, confusion, frontier, selected, at_point) -> list[Path]` writes `summary.json`, `calibration.json`, `calibration.csv`, `frontier.csv`, `confusion.json` and `report.md`.

### 3.2 CLI

```bash
relay sweep   --dataset D --traces T [--ceiling 0.01] [--at 0.93] [--out results/]
relay report  --dataset D --traces T [--at 0.93] [--out reports/eval-<run_id>/]
relay compare --dataset D --traces A.jsonl --traces B.jsonl [...] [--labels jev,rules]
relay run/eval ... [--questions q-v0.1|q-v0.2]   # jev provider only
```

- `sweep` prints the frontier table (every 0.05, plus the selected point and the `--at` point) and the selected operating point, then writes JSON and CSV.
- `report` writes the full artifact bundle.
- `compare` prints the side-by-side table and diffs.
- All three commands make no provider calls and need no key. Errors (bad files, hash mismatch, incomplete coverage) exit 2 through the existing `_fail` path.

## 4. Report content (`report.md`)

1. The disclaimer and run identity: dataset id with its manifest hash if present, provider and model versions, question set, policy version and policy text hash, and git sha.
2. Action metrics, reusing `render_eval_summary`.
3. Confusion matrices for each decision.
4. Calibration table for each decision: bin, n, mean confidence, accuracy, gap, plus Brier and ECE. It gets a plain-language note that calibration needs held-out data and that low-n bins are unreliable. Any bin with n < 20 is flagged.
5. Frontier table (every 0.05, plus the selected and `--at` rows), with the ceiling stated and the selection rule described.
6. Latency and cost.
7. A limitations section: synthetic data, independence approximation in step therapy, and the generator's own conventions (for example, no-year dates are treated as unknown).

## 5. Carry-over: trace identity

The runner computes `policy_text_hash = "sha256:" + sha256(policy.text)`. The Jev provider fills `client_version` from `importlib.metadata.version("typesafe-sdk")`. The Markdown run report shows both. Tests check that the committed v0.1 baseline trace still loads, with `None` for both fields.

## 6. Carry-over: question set q-v0.2

Motivation: in the v0.1 smoke run, Jev read the missing-evidence `TREATMENT_HISTORY` criterion as applying when the patient never took MTX (ADV-02). That sent a case that clearly fails the policy to REQUEST_INFO instead of HUMAN_REVIEW.

The change keeps positive phrasing, per Jev's guidance:
- **`TREATMENT_HISTORY` option:** "The records do not say whether or when the patient took {drug}. A record stating that the patient never took {drug} counts as documented treatment history."
- **`documentation_complete` true-criterion:** adds "(a statement that the patient never took {drug} counts as treatment history)".

Everything else stays identical to q-v0.1. The question-set hash therefore differs.

Adoption rule (dev only): adopt q-v0.2 as the CLI default if, on `gen-v0.2-dev`, its correct-action rate is ≥ q-v0.1's and its unsafe count is ≤ q-v0.1's. Otherwise keep q-v0.1 as the default and document why. Both runs are committed either way.

## 7. Testing

- **Calibration:**
  - Hand-computed fixtures, for example four predictions with a known Brier score and ECE, worked out in comments.
  - Bin edges: 0.5 goes in the first bin, 1.0 in the last, and a p_yes of 0.2 gives a confidence of 0.8 in the [0.8,0.9) bin.
  - Empty input gives `None` metrics.
  - Multiclass Brier with absent labels.
- **Confusion:** a 2×2 matrix from fixtures, with invalid bundles excluded.
- **Frontier:**
  - A hand-built trace set where automation and UAR change at known thresholds.
  - The selection rule: the ceiling, the tie going to the higher threshold, no point qualifying, and a zero-auto point that doesn't qualify.
  - Expected actions don't change across thresholds.
- **Compare:** identical runs have no diffs. A new unsafe automation is flagged first. Coverage or hash mismatch is an error.
- **Artifacts:** files are written, the CSV headers are stable, and `report.md` contains every section header and no ground-truth field names beyond the clearly labelled evaluation tables.
- **Traces:** gz round-trip, the v0.1 baseline loads, and `policy_text_hash` is populated by the runner.
- **Questions:** q-v0.1's hash is unchanged from before B (pin the current value in a test), q-v0.2 differs, and the q-v0.2 text contains the new clause.
- **CLI integration (groundtruth provider only):**
  - `sweep` on a ground-truth run of a small generated dataset: with certain probabilities every threshold gives identical results, so the tie rule selects the highest threshold, 0.99. Assert exactly that.
  - `report` writes its bundle.
  - `compare` of two ground-truth runs reports no diffs.

## 8. Live runs (Jev) and committed artifacts

1. **q-v0.1 on dev:** `relay run --dataset evals/generated/gen-v0.2-dev --provider jev --questions q-v0.1`
2. **q-v0.2 on dev:** the same command with `--questions q-v0.2`. Apply the adoption rule in §6.
3. **Sweep on dev:** run `relay sweep` on the dev traces from the adopted question set. Record the selected threshold t\*, or "none".
4. **Holdout:** `relay run --dataset evals/generated/gen-v0.2-holdout --provider jev --questions <adopted>`
5. **Report on holdout:** `relay report` on the holdout traces with `--at t*` (or `--at 0.95` if nothing was selected).
6. **Commit:** `evals/baselines/<dataset_id>/<run_id>/` holds `traces.jsonl.gz`, the manifest, the results and sweep JSON, and the report bundle. Nothing is edited after seeing results.

Expected Jev cost is well under $1 in total (about 1,800 cases at roughly $0.0001 each). Concurrency stays at 4.

## 9. Definition of done

- `uv run pytest` passes and ruff is clean.
- The sweep, report and compare commands work offline.
- The q-v0.1 vs q-v0.2 dev comparison is documented, and the adopted set is justified by the rule.
- The dev-selected operating point is reported on holdout.
- The holdout calibration report is committed.
- The README gets an "Evaluation" section with the real numbers, including negative results.
