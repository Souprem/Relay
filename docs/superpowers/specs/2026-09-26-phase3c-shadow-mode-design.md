# Phase 3C Design: Shadow Mode

- **Date:** 2026-09-26
- **Status:** Approved by controller (Phase 3 design is delegated by the user).
- **Depends on:** 3A replay (`tracediff`: `diff_runs(..., labelled=False)` from 3B F3), 3B regression (`run_regression`, gate verdicts)
- **Parent:** handoff §"Shadow mode":
  - "In shadow mode, Relay calculates a proposed action and saves the trace but never effects a simulated status transition."
  - The CLI and dashboard label it plainly: `SHADOW: Would auto-process CASE-3817; no action was taken.`
  - "shadow mode can compare a candidate provider/policy with a chosen baseline or gold action. Its purpose is to show safe progressive rollout, not to pretend the system has real production traffic."
  - Handoff command: `relay run --dataset evals/gold --mode shadow`.

## 1. Goal

Model a rollout ladder:
1. **Simulated live system (the incumbent).** The accepted configuration (provider, questions, policy, thresholds) processes cases. Its actions become simulated case-status transitions in a small local state store.
2. **Shadow candidate.** A new configuration runs on the same cases. Its proposed actions are recorded as `mode="shadow"` traces and compared with the incumbent. The state store is never touched.
3. **Promotion check.** The candidate's shadow run is judged against the incumbent with the 3B regression gate, using ground truth that is labelled evaluation-only. The result is `PROMOTE` or `HOLD`, with reasons.

This demonstrates the safety property: nothing a shadow candidate proposes can change case state. The evidence needed to decide on a rollout is still produced.

## 2. Settled decisions

| # | Decision |
|---|---|
| S1 | **A new `relay run` command.**<br>`relay run --dataset DIR --workflow simulated\|shadow [provider options as in eval] [--from-traces FILE [--at X]] [--state PATH] [--incumbent TRACES] [--out DIR]`.<br>`--workflow` is used, not `--mode`, because `--mode` already means Claude sync/batch. The README maps the handoff's `--mode shadow` to `--workflow shadow`.<br>The default `--state` is `state/case-status.json`, and `state/` is added to `.gitignore`. |
| S2 | **The simulated status store (`relay/workflow/status.py`).**<br>• Statuses: `RECEIVED` → one of `AUTO_APPROVED` (AUTO_PROCESS), `INFO_REQUESTED` (REQUEST_INFO), `IN_HUMAN_REVIEW` (HUMAN_REVIEW).<br>• The store is a JSON file of `{case_id: {status, history: [{from, to, action, trace_id, run_id, at}]}}`. Writes are atomic (temp file + `os.replace`).<br>• Only `apply_transition(store, trace)` changes it, and it requires `trace.mode == "simulated"`. A `mode == "shadow"` trace raises `ShadowWriteError`. That exception is the enforced guarantee, and it is tested.<br>• Re-applying a case that is already past RECEIVED is allowed only from the same run: it's idempotent by trace_id. A different run gives a `ConflictError` unless `--reset-state` is passed, which archives the old file to `<state>.bak-<ts>` first. |
| S3 | **Traces carry the workflow mode.** The runner gains `mode: Literal["evaluate","simulated","shadow"] = "evaluate"`, set on every trace, and `RunManifest` gains typed `mode` (default `"evaluate"`) and `source_run_id: str | None = None` fields, both backward compatible. The 3B simulated-run writer switches from extra keys to these fields (3B final-review seam). `relay eval` stays `evaluate`.<br>With `--from-traces`, no provider is called. A stored run's decisions are re-issued as new traces in the requested mode via `replay_trace` (with `--at` via `replay_run`), with `replay_of` set. This is the offline path used by tests and the README. A live provider run uses all the existing guards (Jev key, Claude budget ledger). |
| S4 | **Output for `--workflow simulated`.**<br>• One line per case: `SIMULATED: CASE-ID RECEIVED → AUTO_APPROVED (AUTO_PROCESS)`.<br>• A summary of counts per status.<br>• Paths to the traces, the manifest (mode simulated) and the state file. |
| S5 | **Output for `--workflow shadow`.**<br>• One line per case, in the handoff's exact form:<br>&nbsp;&nbsp;– `SHADOW: Would auto-process CASE-ID; no action was taken.`<br>&nbsp;&nbsp;– `SHADOW: Would request information for CASE-ID; no action was taken.`<br>&nbsp;&nbsp;– `SHADOW: Would send CASE-ID to human review; no action was taken.`<br>• If the state file exists, the line appends `(current status: <STATUS> by <run_id>)`. The state file is read-only here.<br>• A trailing line: `SHADOW RUN <run_id>: <n> proposals recorded; case state unchanged (verified).`<br>&nbsp;&nbsp;"(verified)" means the command hashed the state file before and after and the hashes are equal. If they differ, exit 3 with `SHADOW VIOLATION`. This can't happen through the API, but it's checked. |
| S6 | **Comparison against the incumbent** (`--incumbent TRACES`, a simulated or evaluate run on the same dataset):<br>• **Agreement section (unlabelled; what a real shadow deployment sees).** Uses `diff_runs(incumbent, shadow, labelled=False)` and shows:<br>&nbsp;&nbsp;– the agreement rate<br>&nbsp;&nbsp;– an action transition matrix (incumbent × candidate)<br>&nbsp;&nbsp;– counts of `would newly auto-process` and `would stop auto-processing`<br>&nbsp;&nbsp;– the case lists for the first two items<br>• **Promotion check (evaluation-only).** Uses `run_regression(baseline=incumbent, candidate=shadow run)` from 3B. It prints the regression summary, including 3B's STILL UNSAFE list as a warning that does not cause HOLD, and a final line `PROMOTION CHECK: PROMOTE` (gate PASS) or `PROMOTION CHECK: HOLD — <failures>` (gate FAIL), clearly headed `EVALUATION-ONLY (uses ground truth; not available in a real shadow deployment)`.<br>• `--waivers` passes through to the gate.<br>• Exit codes: 0 PROMOTE; 4 HOLD because of newly unsafe cases or too many regressions; 2 usage error. |
| S7 | **Artifacts.** `--out DIR` writes `shadow.json` (the `ShadowReport`: agreement block, transition matrix, promotion `RegressionResult`) and `shadow.md` (the terminal text). The shadow traces and manifest always go to `--traces-dir` (default `traces/`), like any run. |
| S8 | **No gold tuning.** The README demo uses committed gold traces only as frozen inputs, and nothing is tuned on them. Incumbent: Jev q-v0.2 at 0.89, via `--from-traces … --at 0.89 --workflow simulated`. Candidate: Claude at 0.55, via `--from-traces … --at 0.55 --workflow shadow --incumbent …`. On gold this gives PROMOTE (0 newly unsafe, per the committed `gold-jev-vs-claude` gate). A second demo shadows Jev at 0.89 against Jev at 0.95 and gives HOLD on GOLD-TMP-17, which mirrors the 3B FAIL demo in rollout terms. |

## 3. Components

- `relay/workflow/status.py`: `CaseStatus` (StrEnum), `StatusStore`, `load_store`, `apply_transition`, `ShadowWriteError`, `ConflictError`, and `state_digest(path) -> str` (sha256 of the file bytes, or `"absent"`).
- `relay/evaluation/runner.py`: a `mode` parameter threaded into traces. `relay/traces/models.py`: `RunManifest.mode`.
- `relay/evaluation/shadow.py`: `ShadowReport`, `build_shadow_report(incumbent, shadow, cases, *, waivers, gate_name=None) -> ShadowReport`, and `transition_matrix(diffs)`. It is pure and reuses `diff_runs` and `run_regression` (or the pure core under it).
- `relay/reporting.py`: `shadow_line(trace, current_status)`, `simulated_line(...)`, `render_shadow_report(report)`.
- `relay/cli.py`: the `run` command.
- README: a "Shadow mode" section with both demos (real pasted output) and the rollout-ladder explanation. The `run` command goes in the command list.

## 4. Testing

- **Status store:**
  - the transitions per action
  - atomic write
  - idempotence by trace_id
  - ConflictError across runs
  - `--reset-state` archives the file
  - **`apply_transition` with a shadow trace raises `ShadowWriteError` and leaves the file byte-identical**
- **CLI:**
  - Simulated then shadow on the smoke dataset, using `--from-traces` with ground-truth/rules traces made in tmp. The state is unchanged by shadow (digest equal), and the shadow lines use the exact handoff strings.
  - `(current status: …)` appears when the state exists.
  - The manifest and traces have mode shadow.
  - `--incumbent` agreement numbers match a hand computation.
  - Promotion PROMOTE gives exit 0. HOLD gives exit 4, using the gold demo (GOLD-TMP-17).
  - A monkeypatch that makes the state file change during a shadow run gives SHADOW VIOLATION and exit 3.
- **Live provider path:** fakes only. The Jev and Claude guards are invoked. No paid calls.
- **Backward compatibility:** old manifests and traces without `mode` load. All committed-baseline tests and gates still pass.

## 5. Definition of done

- Tests and ruff pass.
- The README Shadow mode section contains real pasted output.
- No paid calls.
- `state/` is git-ignored.
