# Phase 3B Design: Regression Gate and CI

- **Date:** 2026-09-26
- **Status:** Approved by controller (Phase 3 design is delegated by the user).
- **Depends on:** 3A replay (`relay/evaluation/tracediff.py`, `relay replay`)
- **Parent:** handoff §"Regression evaluation". `relay regression` compares candidate and baseline traces over a fixed dataset and surfaces:
  - improved, unchanged and regressed actions
  - changes in UAR, automation rate and calibration
  - newly unsafe auto-actions, which are the highest-priority failures
  - case IDs and the diff data needed to investigate them

  Any candidate that increases unsafe automation without a deliberate, reviewed policy decision should fail the regression gate. Handoff Phase 3 also asks to "make unsafe-regression failures visible in CLI and CI."

## 1. Goal

Build a run-level regression command and a CI gate. A candidate change can be a new question set, provider, policy or threshold. It is compared against an accepted baseline on the same frozen dataset, and it fails loudly when it introduces unsafe automation that no one has reviewed. CI runs the offline gates on every push.

## 2. Foundation fixes carried over from the 3A final review (land first)

| # | Fix |
|---|---|
| F1 (3A I1) | **Thresholds follow the target policy version.** When a policy replay targets a policy whose version differs from the trace's `policy_version`, start from `load_thresholds(target.version)`, then apply `--at` / `auto_process`. An unknown thresholds version is an error: exit 2 in the CLI, `EvalError` in library code. Same-version replays keep the trace's own thresholds, as now. The P4 label gains `, thresholds <version>`. This also resolves 3A final-review Minor 2: after an `--at` override the thresholds `version` becomes `<base>+at<X>` (e.g. `v0.1+at0.89`), produced by one helper `override_auto_process(thresholds, x) -> Thresholds`, which is used at every call site: replay, replay_run, compare, frontier and report. |
| F2 (3A I2) | **Run-level diff helpers in `tracediff.py`:**<br>• `diff_case(original, candidate, case, *, original_label, candidate_label, policies: Mapping[str, AuthorizationPolicy] \| None = None) -> TraceDiff` computes both expected actions (each side's own policy and thresholds) and the current policy-text hash itself. `policies` is an optional cache.<br>• `diff_runs(originals, candidates, cases, *, original_label, candidate_label) -> list[TraceDiff]` pairs both runs through `paired_cases`. It requires identical case-id sets, raising `EvalError` that names the missing or extra ids, and one policy load per id.<br>• `cli.replay` and the gold `drifted_cases` guard are refactored to call `diff_case`. There is no behaviour change, and all existing tests still pass. |
| F3 (3A I2) | **Optional expected action.** `diff_traces`, `diff_case` and `diff_runs` accept `expected=None` via `labelled: bool = True`. In that mode:<br>• `expected_original`/`expected_candidate`, `change`, `newly_unsafe` and `unsafe_resolved` are `None`.<br>• The renderer prints `EXPECTED: not available (unlabelled)`.<br>3C shadow mode needs this. Datasets always carry ground truth, so regression always runs labelled. |
| F4 (3A I2) | **Gated crossings.** `DecisionDelta` gains `crossed_gated: list[str]`, the subset of `crossed` whose table row feeds a real engine gate. The renderer shows reported-only crossings in parentheses. Regression counts use `crossed_gated` only. |

## 3. `relay regression`

```
relay regression --dataset DIR --baseline TRACES
    ( --candidate-traces TRACES [--candidate-at X] | --candidate-policy ID [--candidate-at X]
      | --candidate-latest-policy [--candidate-at X] | --candidate-at X | --reproduce )
    [--baseline-at X] [--waivers FILE] [--max-regressed N] [--out DIR] [--json]
relay regression --config evals/regression/gates.json [--gate NAME ...] [--out DIR]
```

| # | Decision |
|---|---|
| G1 | **Offline only.** Candidates come from existing traces or from a policy replay of the baseline's stored decisions. A live provider candidate is produced first with `relay eval`, which applies its budget guards, and then passed in as `--candidate-traces`. `regression` never builds a network client and needs no keys. |
| G2 | **Candidate sources.** There are three: `--candidate-traces`, a policy replay of the baseline's stored decisions (`--candidate-policy`/`--candidate-latest-policy`), and `--reproduce`. They are mutually exclusive.<br>• `--candidate-at X` modifies the chosen source: with `--candidate-traces` it re-decides the candidate traces at auto_process X (via `replay_run`); with a candidate policy it sets that replay's auto_process; alone it means a policy replay of the baseline under its own policy at X.<br>• `--reproduce` means the stored decisions under the current engine with the baseline's own policy and thresholds. It is the engine-drift gate: any non-identical case fails, with exit 3. It cannot be combined with any `--candidate-*` or `--baseline-at` flag.<br>• `--baseline-at X` re-decides the baseline at auto_process X before comparing. Each provider is gated at its own dev-selected operating point, as in the README tables.<br>• `--baseline-at` and `--candidate-at` values outside (0, 1] give exit 2. |
| G3 | **Pairing.** Both runs must cover exactly the dataset's cases, with matching content hashes. The `paired_cases` checks apply to both. Traces with different providers or question sets may be compared; that is the point. |
| G4 | **The result model (`relay/evaluation/regression.py`).** `RegressionResult` contains:<br>• the dataset id and n<br>• the baseline and candidate labels and `RunIdentity`<br>• per-side `EvalSummary` numbers: correct, automation, request-info, human-review and UAR, each with a Clopper-Pearson 95% interval<br>• per-decision calibration (Brier and ECE) for both sides, plus the delta<br>• counts by `change` (improved / unchanged / regressed / changed-both-wrong)<br>• `newly_unsafe`, `unsafe_resolved`, `regressed` and `improved` case lists. Each entry holds the case id, the expected action, both actions, the decisions whose `answer_changed` flipped, and `crossed_gated`.<br>• waived cases with their reasons<br>• a `verdict` of `PASS` or `FAIL`, with `failures: list[str]` in plain English.<br>Only when the policies differ, the expected action is per side, as in 3A P7. |
| G5 | **The gate.** The verdict is FAIL if any of these holds:<br>• (a) a newly unsafe case is not covered by a waiver<br>• (b) `--max-regressed N` is given and the number of regressed cases exceeds N<br>• (c) in `--reproduce` mode, any case is not identical<br>Exit codes: 0 for PASS; 4 for FAIL(a/b); 3 for FAIL(c); 2 for usage or input errors. The highest applicable code wins. The UAR delta is reported, but it is not a separate criterion: case-level (a) is stricter and explains itself. |
| G6 | **Waivers are the "deliberate, reviewed policy decision".** The file is JSON: `{"waivers": [{"case_id": "...", "gate": "<gate name or *>", "reason": "...", "approved_by": "...", "date": "YYYY-MM-DD"}]}`. Every field is required and non-empty; a malformed file gives exit 2. The review is the commit and PR review of the waiver file itself. A waiver covers newly-unsafe only; regressions and engine drift cannot be waived. The report lists waived cases prominently. A waiver that matches no newly-unsafe case is reported as `stale waiver`, which is a warning, not a failure. |
| G7 | **Output.** The terminal shows a header with both labels and sides, then a metrics table (baseline, candidate, Δ, CI), then the change counts. NEWLY UNSAFE cases come first, each with a ready-to-run `relay replay …` command that reproduces the case diff. After them come UNSAFE RESOLVED, REGRESSED (up to 20, with `--all` for more) and the calibration deltas. The final line is `REGRESSION GATE: PASS` or `REGRESSION GATE: FAIL — <failures>`. `--json` prints only `RegressionResult` JSON. `--out DIR` writes `regression.json` and `regression.md` (the same content as the terminal output). For a policy-replay candidate it also writes `candidate.jsonl.gz` and `candidate.manifest.json` with `mode: "simulated"`, a `source_run_id` extra key, and the policy and threshold used, so that `eval --traces`, `compare` and `replay` can consume it. |
| G8 | **Config mode for CI.** `evals/regression/gates.json` holds `{"gates": [{"name", "dataset", "baseline", "candidate": {"traces"\|"policy"\|"at"\|"reproduce"}, "baseline_at"?, "max_regressed"?, "waivers"?}]}`. Paths are repo-relative. It runs every gate (or those named with `--gate`), prints each gate's report, then a summary table of name / verdict / newly unsafe / regressed. It exits with the highest code across gates. |

## 4. Initial committed gates (`evals/regression/gates.json`)

All gates use committed files only, so CI needs no generated datasets. The initial gates:

1. `gold-reproduce-<provider>` for each of the 4 gold runs (`--reproduce`): the engine-drift gate on gold.
2. `smoke-reproduce-jev`, on the v0.1 smoke baseline (`--reproduce`), if one is committed and its dataset hash still matches. Otherwise skip it and say so in the README.
3. `gold-jev-vs-claude`: baseline Jev at `--baseline-at 0.89`, candidate Claude traces with its own operating point applied. Claude's traces were recorded at 0.95, so the gate uses `--candidate-traces <claude> --candidate-at 0.55`. On the committed data this PASSes, with 4 differences and 0 newly unsafe, and documents that Claude is not an unsafe regression versus Jev on gold.

The demonstration of a failing gate is NOT committed as a gate, because CI must stay green. Instead, README and tests use gold Jev: baseline at 0.95, candidate `--candidate-at 0.89`. That gives newly unsafe GOLD-TMP-17 → `REGRESSION GATE: FAIL`, exit 4. A second example shows the same run passing with a committed example waiver file, `evals/regression/examples/waiver-tmp17.json`, labelled as an example.

Where the generated datasets exist locally (`evals/generated/…`), a gate can use the `gen-v0.2-*` baselines. The config supports `"requires_generated": true`: such a gate is skipped with the note `SKIPPED (dataset not generated; run relay generate …)` when the directory is missing. CI regenerates them: `relay generate` for gen-v0.2-dev and holdout, then `--verify` against the committed manifests. Add holdout reproduce gates for jev, rules and claude-150 with `requires_generated: true`. The Claude holdout run is a 150-case sample, so the gate must honour the run manifest's `sample_limit`/`sample_seed`, reusing `sample_cases`, as the drift guard does.

## 5. CI

`.github/workflows/ci.yml` runs on push and pull_request, on ubuntu-latest with `astral-sh/setup-uv` and Python 3.12. The job:

1. `uv sync --frozen`
2. `uv run ruff check .` and `uv run ruff format --check .`
3. `uv run pytest -q`, where `-m 'not live'` is the default
4. regenerate datasets: `uv run relay generate …` for dev and holdout, then `--verify`. Use the exact flags in the committed manifests.
5. `uv run relay --env-file .no-such.env regression --config evals/regression/gates.json --out regression-report`
6. upload `regression-report/` as an artifact, even on failure

No secrets are referenced anywhere in the workflow. `TYPESAFE_API_KEY` and `ANTHROPIC_API_KEY` are unset in CI, and a test asserts that the workflow file contains no `secrets.` reference. The README gets a CI badge line, pointing at the Souprem/Relay repo's workflow.

## 6. Add-on: spend-ledger maintenance (Phase 2 parked minors)

```
relay budget show --ledger PATH
relay budget release RUN_ID --ledger PATH --reason TEXT --yes
```

- `show` prints entries (run, dataset, mode, status, cost, batch id) and totals: settled, reserved and total against the default budget.
- `release` settles a **reserved** entry at $0. It refuses a settled entry, an unknown run and an entry with a batch id unless `--force-batch` is given; exit 2 on refusal. `--yes` is required. The reason is stored on the entry as a new optional `note` field in `SpendEntry`, which is backward compatible.
- `release` backs up the ledger file to `<ledger>.bak-<UTC timestamp>` before writing. The write is atomic, using the existing writer.
- The README Budget section documents the ambiguous-submission recovery procedure:
  1. check the Console Batches page
  2. if the batch exists, re-attach with `--batch-id`
  3. otherwise use `relay budget release`

Tests use a tmp ledger only. The real `results/claude-spend.json` is never touched by tests or by the implementation work.

## 7. Testing

- **F1–F4:** unit tests. F1 uses a monkeypatched second policy and thresholds version. F2 checks that diff_runs rejects mismatched case sets, and that refactored callers produce identical output. The 3A tests must still pass unchanged, except for the label's new `, thresholds <version>` suffix.
- **Regression:**
  - unit tests of the verdict logic over synthetic `TraceDiff` lists: waivers, stale waivers, max-regressed, and reproduce drift
  - CLI integration on the smoke dataset with the groundtruth and rules providers producing tmp traces
  - the gold FAIL demo, which must give exit 4 with GOLD-TMP-17 listed
  - the waiver PASS demo
  - the `--out` artifacts round-trip: the simulated candidate trace file is readable by `relay eval --traces`
  - config mode with a tmp gates file: highest exit code, `--gate` filter, and requires_generated skip
- **Committed gates:** an integration test runs `relay regression --config evals/regression/gates.json`, skipping requires_generated gates when the data is missing, and asserts PASS.
- **CI workflow:** a YAML parse test that checks the steps exist and that there are no secrets.
- **Budget:** show/release, with a backup file created and the refusals covered.

## 8. Definition of done

- Tests and ruff pass.
- The README gets a "Regression gate" section with:
  - the gold FAIL demo and the waiver PASS demo as real pasted output
  - the committed gates table
  - how to add a waiver
  - CI description
- The README Budget section gets the recovery procedure.
- The `.github/workflows/ci.yml` workflow is committed. It will run on the next push; pushing is the user's decision.
- No paid calls.
