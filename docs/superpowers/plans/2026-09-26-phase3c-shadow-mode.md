# Phase 3C: Shadow Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the rollout ladder to Relay: a simulated incumbent whose actions change simulated case status, a shadow candidate whose proposals are recorded but never applied, and an evaluation-only promotion check (PROMOTE or HOLD) that reuses the 3B regression gate.

**Architecture:** Workflow modes become typed: `WorkflowMode = Literal["evaluate","simulated","shadow"]` on traces and run manifests, threaded through `run_dataset`, `replay_trace` and `replay_run`. A new `relay/workflow/status.py` owns the JSON case-status store; its only writer refuses shadow traces (`ShadowWriteError`). A new pure `relay/evaluation/shadow.py` builds the `ShadowReport`: unlabelled agreement from `diff_runs(labelled=False)`, plus the promotion check from 3B's `build_result`. `relay/reporting.py` renders the per-case lines and the report. The existing `relay run` command gains `--workflow simulated|shadow`, with an offline `--from-traces` path and the existing provider path (all its guards).

**Tech Stack:** Python 3.12, uv, Pydantic v2, Typer, pytest (`asyncio_mode=auto`, `-m 'not live'` by default), ruff.

## Global Constraints

- Synthetic data only.
- Never open `.env` (read, cat, grep or edit it). No task needs it.
- No paid API calls anywhere. Every command in this plan is offline. Run offline CLI commands as `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env ...`.
- `results/claude-spend.json` is never read or written, by tests or by this work. Claude tests use a tmp `--ledger`.
- Committed artifacts under `evals/baselines/`, `evals/gold/`, `evals/smoke/` and `evals/generated/manifests/` must not change. Never regenerate them.
- Tests use tmp state paths only (always pass `--state` under `tmp_path`). `state/` is git-ignored (Task 2).
- Stage files by explicit path. Never `git add -A` or `git add .`.
- Each commit uses two `-m` arguments. The second is exactly `-m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.
- Don't push.
- At the end of every task, `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q` must pass.
- `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env regression --config evals/regression/gates.json --strict-generated` must still exit 0 (9/9 PASS). It needs `evals/generated/gen-v0.2-holdout` on disk (it is, locally; if not, regenerate it with the `relay generate` command in `.github/workflows/ci.yml`).
- Branch: `feat/phase3` (already checked out). Work from the repository root `/Users/joelbrook/Desktop/Code/Relay`.

## Verified facts this plan relies on (checked while planning, on a scratch copy)

Every code block below was applied to a scratch copy of `feat/phase3` at `69257bf` and run, then re-applied mechanically from this document to a fresh copy of `c473c63` (which only adds the Phase 3D design doc): each task's new tests failed before its implementation and passed after, and the result was byte-identical to the prototype.

- **Tests.** After each task the full suite passed (1003 before; 1078 after Task 6). `ruff check` and `ruff format --check` were clean.
- **Committed artifacts.** `git diff 69257bf -- evals/` was empty after all tasks. All 14 committed run manifests under `evals/baselines/` lack a `mode` key and load as `mode="evaluate"`, `source_run_id=None`. The committed traces already carry `mode: "evaluate"` (the field existed since v0.1).
- **Gates.** `relay regression --config evals/regression/gates.json --strict-generated` exited 0, 9/9 PASS, after all tasks. The drift guard (`tests/integration/test_committed_baselines.py`) and the committed-gates test still pass. `gold-jev-vs-claude` still reports STILL UNSAFE 1.
- **README demo 1 (PROMOTE).** Simulated Jev at 0.89 from the committed gold Jev traces: `AUTO_APPROVED 29 · INFO_REQUESTED 32 · IN_HUMAN_REVIEW 39`. Then shadow Claude at 0.55 from the committed gold Claude traces with `--incumbent` that run: exit 0, `PROMOTION CHECK: PROMOTE`. Agreement 96/100; would newly auto-process GOLD-MIS-17 and GOLD-TMP-15; would stop auto-processing GOLD-TMP-18; changes improved 3 · unchanged 96 · regressed 1; STILL UNSAFE 1 (GOLD-TMP-17); 0 newly unsafe. **This matches the spec.**
- **README demo 2 (HOLD).** Simulated Jev at the recorded 0.95 (`AUTO_APPROVED 18 · INFO_REQUESTED 32 · IN_HUMAN_REVIEW 50`), then shadow Jev at 0.89: exit 4, `PROMOTION CHECK: HOLD — 1 newly unsafe case(s) without a waiver: GOLD-TMP-17`. Agreement 89/100 (11 HUMAN_REVIEW → AUTO_PROCESS). **This matches the spec.** The shadow line reads `SHADOW: Would auto-process GOLD-TMP-17; no action was taken. (current status: IN_HUMAN_REVIEW by <incumbent run id>)`.
- **Smoke.** groundtruth incumbent vs rules shadow: 9/10 agree, rules would stop auto-processing AUTO-03 (a safe regression), PROMOTE.
- **Run ids.** `replay_run` names its run `replay-<source run id>`, so two runs re-issued from the same source would collide on the trace file name (`TraceStore.create` opens with `"x"`) and look like one run to the conflict check. `--from-traces` therefore passes a fresh `new_run_id()` (Task 1 adds the `run_id` parameter).
- **`state/`.** Not ignored before Task 2; after it, `git check-ignore -v state/case-status.json` reports `.gitignore:…:/state/`.

## Resolved ambiguities (decisions this plan makes)

1. **"A new `relay run` command" — `relay run` already exists.** It is extended, not replaced. Without `--workflow`, it behaves exactly as today (`mode="evaluate"`, run table and Markdown report). All workflow-only flags without `--workflow` are exit 2.
2. **`--provider`/`--policy` defaults on `relay run` become `None`** (resolved to `jev`/`v0.1`), so that an explicit `--provider`, `--policy`, `--questions` or any Claude flag combined with `--from-traces` can be rejected (exit 2) instead of silently ignored. `relay eval` is unchanged.
3. **`RunManifest.mode` values.** `Literal["evaluate","simulated","shadow"]`, default `"evaluate"`, the same alias (`WorkflowMode`) as `WorkflowTrace.mode`. The 3B review suggested `"live"`/`"batch"`; those describe Claude's execution mode, which is not a workflow mode, so they are not used.
4. **The 3B simulated-run writer.** `mode` and `source_run_id` become typed fields; `policy_id` and `thresholds` stay as extra keys (a 3B test asserts them, and `RunManifest` has no such fields).
5. **The 3B M8 "public `build_candidate`" seam is not built.** 3C does not need it: `--from-traces` calls `replay_run` directly (YAGNI).
6. **The status store API takes the file path.** The spec's `apply_transition(store, trace)` is `apply_transition(path, trace)` (plus `apply_transitions(path, traces)` for a whole run in one atomic write), so that "only this function writes the file" is literally true. `load_store(path)` reads.
7. **Idempotence.** Re-applying a trace whose `trace_id` is the recorded transition is a no-op (file not rewritten). Any other trace for a case past RECEIVED — from another run, or the same run with a new trace id — is a `ConflictError`. A case twice in one run is a `ConflictError`. The CLI checks conflicts with `ensure_unclaimed` before deciding anything, so a conflict costs no provider call and writes no trace file.
8. **Non-simulated, non-shadow traces.** An `evaluate` trace offered to the store raises `StatusStoreError` (the base class of `ShadowWriteError` and `ConflictError`). The CLI maps `StatusStoreError` to exit 2.
9. **`--reset-state`** is simulated-only (exit 2 with shadow). It archives with `os.replace` to `<state>.bak-<UTC %Y%m%dT%H%M%SZ>` and refuses to overwrite an existing archive.
10. **`(current status: …)`.** Appended to every shadow line when the state file exists before the run: `(current status: <STATUS> by <run_id>)`, or `(current status: RECEIVED)` for a case the file has not moved. No suffix when the file is absent.
11. **The violation check.** The digest is taken before anything else in the shadow flow and compared right after the traces are written, before any proposal line is printed. On a mismatch: `SHADOW VIOLATION: …` on stderr, exit 3, and no proposal lines.
12. **`--max-regressed`** passes through to the promotion check as well as `--waivers`, because the spec's exit 4 names "too many regressions". Both, and `--out`, need `--incumbent`.
13. **Waiver scope.** The promotion check has no gate name, so (as in 3B single mode) only `gate: "*"` waivers apply.
14. **The incumbent** must be a simulated or evaluate run (a shadow run is exit 2), and it must pair with the dataset (`paired_cases`) — both checked before the shadow run starts.
15. **Labels.** Incumbent and candidate labels are `"<mode> " + original_label(first trace)`, e.g. `simulated run_… · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.89`.
16. **Replay commands in the promotion report** are real: `relay replay CASE --traces <incumbent file> --dataset <dataset> --candidate-traces <shadow trace file>` (both files exist on disk). `build_shadow_report` takes `replay_command` for this.
17. **Output order.** Simulated: per-case lines (sorted by case id), blank, summary, `Traces:`, `Manifest:`, `State:`. Shadow: per-case lines (sorted), blank, trailer, `Traces:`, `Manifest:`, then with `--incumbent` an optional `Shadow report:` line (with `--out`), blank, the report, with `PROMOTION CHECK: …` last. `shadow.md` is the report text only (from `Relay shadow comparison` to the PROMOTION CHECK line).
18. **README demos.** Each command prints 100 per-case lines. The README keeps the first three (and, in demo 2, the GOLD-TMP-17 line) and replaces the rest with `[… N more SIMULATED|SHADOW lines, one per case …]`, stated in the prose; everything else is real output. A generator script (Task 7) builds the section from the captured outputs, so the pasted text is exactly what the commands printed. Demo states are `state/promote-demo.json` and `state/hold-demo.json`, so the two ladders don't collide.
19. **`--limit/--sample-seed` with `--from-traces`** apply to the dataset as usual; the stored run must cover exactly those cases (`paired_cases`), otherwise exit 2. No automatic subsampling from the source manifest.

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `relay/traces/models.py` | modify | `WorkflowMode`; `RunManifest.mode`, `RunManifest.source_run_id` |
| `relay/evaluation/runner.py` | modify | `run_dataset(mode=...)` |
| `relay/evaluation/tracediff.py` | modify | `replay_trace`/`replay_run` take `mode` and `run_id` |
| `relay/evaluation/regression_run.py` | modify | `_write_simulated_run` uses the typed fields |
| `relay/workflow/status.py` | create | `CaseStatus`, `StatusStore`, `load_store`, `apply_transition(s)`, `ensure_unclaimed`, `reset_state`, `state_digest`, errors |
| `relay/evaluation/shadow.py` | create | `Agreement`, `ShadowReport`, `transition_matrix`, `agreement`, `build_shadow_report` (pure) |
| `relay/reporting.py` | modify | `simulated_line`, `simulated_summary`, `shadow_line`, `shadow_trailer`, `promotion_line`, `render_shadow_report` |
| `relay/cli.py` | modify | `_execute(mode=...)`; `_run_provider`; `relay run --workflow …` |
| `.gitignore` | modify | `/state/` |
| `README.md` | modify | Commands, "Shadow mode" section, project docs |
| `tests/unit/test_status_store.py`, `tests/unit/test_shadow.py`, `tests/unit/test_reporting_shadow.py`, `tests/integration/test_cli_workflow.py`, `tests/integration/test_cli_shadow_compare.py` | create | |
| `tests/unit/test_trace_store.py`, `tests/unit/test_runner.py`, `tests/unit/test_replay.py`, `tests/integration/test_regression_run.py`, `tests/integration/test_cli.py` | modify | |

## Edit conventions

"Replace" steps give the exact current text and its replacement; the current text occurs exactly once in the file. "Append" steps add to the end of the file. "Create" steps give the whole file.

---

### Task 1: Typed workflow mode on traces and manifests

**Files:**
- Modify: `relay/traces/models.py`, `relay/evaluation/runner.py`, `relay/evaluation/tracediff.py`, `relay/evaluation/regression_run.py`, `relay/cli.py`
- Test: `tests/unit/test_trace_store.py`, `tests/unit/test_runner.py`, `tests/unit/test_replay.py`, `tests/integration/test_regression_run.py`, `tests/integration/test_cli.py`

**Interfaces:**
- Produces:
  - `relay.traces.models.WorkflowMode = Literal["evaluate", "simulated", "shadow"]`
  - `RunManifest.mode: WorkflowMode = "evaluate"`, `RunManifest.source_run_id: str | None = None`
  - `run_dataset(..., mode: WorkflowMode = "evaluate")` stamps every trace
  - `replay_trace(..., mode: WorkflowMode = "simulated", run_id: str | None = None)` and `replay_run(..., mode: WorkflowMode = "simulated", run_id: str | None = None)`; `run_id=None` keeps `"replay-<source run id>"`
  - `relay.cli._execute(..., mode: WorkflowMode = "evaluate")` (last parameter) sets the trace and manifest mode

- [ ] **Step 1: Write the failing tests**

Append to the end of `tests/unit/test_trace_store.py`:

```python
# ---- Phase 3C: the workflow mode on manifests ----


def test_run_manifest_mode_defaults_to_evaluate_and_round_trips(tmp_path):
    assert (manifest().mode, manifest().source_run_id) == ("evaluate", None)
    shadow = manifest().model_copy(update={"mode": "shadow", "source_run_id": "run_src"})
    store = TraceStore.create(tmp_path, "run_x")
    path = store.write_manifest(shadow)
    loaded = RunManifest.model_validate_json(path.read_text())
    assert (loaded.mode, loaded.source_run_id) == ("shadow", "run_src")


def test_run_manifest_rejects_an_unknown_mode():
    with pytest.raises(ValueError, match="mode"):
        RunManifest.model_validate(manifest().model_dump() | {"mode": "live"})


def test_every_committed_manifest_loads_as_an_evaluate_run():
    paths = sorted((REPO / "evals" / "baselines").rglob("*manifest.json"))
    assert len(paths) == 14
    for path in paths:
        assert '"mode"' not in path.read_text()
        loaded = RunManifest.model_validate_json(path.read_text())
        assert (loaded.mode, loaded.source_run_id) == ("evaluate", None), path
```

Append to the end of `tests/unit/test_runner.py`:

```python
async def test_run_dataset_stamps_every_trace_with_the_mode(tmp_path):
    data = cases()
    default = await run_dataset(
        data,
        SpyProvider(data),
        policy_version="v0.1",
        store=TraceStore.create(tmp_path, "a"),
        run_id="a",
    )
    assert {t.mode for t in default} == {"evaluate"}
    shadow = await run_dataset(
        data,
        SpyProvider(data),
        policy_version="v0.1",
        store=TraceStore.create(tmp_path, "b"),
        run_id="b",
        mode="shadow",
    )
    assert {t.mode for t in shadow} == {"shadow"}
    assert {t.mode for t in read_traces(tmp_path / "b.jsonl")} == {"shadow"}
```

Append to the end of `tests/unit/test_replay.py`:

```python
# ---- Phase 3C: mode and run id for relay run --from-traces ----


def test_replay_trace_takes_a_mode_and_a_run_id():
    case = make_case("T-01")
    original = make_trace(case)
    shadow = replay_trace(
        original,
        case,
        policy=POLICY,
        thresholds=THRESHOLDS_V0_1,
        git_sha="x",
        mode="shadow",
        run_id="run_new",
    )
    assert (shadow.mode, shadow.run_id, shadow.replay_of) == ("shadow", "run_new", "tr_T-01")


def test_replay_run_passes_the_mode_and_run_id_to_every_trace():
    cases, traces = run_of("T-01", "T-02")
    replayed = replay_run(
        traces, cases, policy_id=None, auto_process=0.9, mode="shadow", run_id="run_new"
    )
    assert {(t.mode, t.run_id) for t in replayed} == {("shadow", "run_new")}
    assert [t.replay_of for t in replayed] == [t.trace_id for t in traces]
```

In `tests/integration/test_regression_run.py`, replace:

```python
    assert find_run_manifest(tmp_path / "candidate.jsonl.gz").case_count == 100
```

with:

```python
    loaded = find_run_manifest(tmp_path / "candidate.jsonl.gz")
    assert loaded.case_count == 100
    # 3C: mode and source_run_id are typed fields now, so they survive a round-trip (3B M8).
    assert (loaded.mode, loaded.source_run_id) == ("simulated", "run_20260925T170857Z_b95be9")
```

In `tests/integration/test_cli.py`, replace:

```python
    assert len(list((tmp_path / "traces").glob("*.manifest.json"))) == 1
```

with:

```python
    [manifest_file] = (tmp_path / "traces").glob("*.manifest.json")
    manifest = json.loads(manifest_file.read_text())
    assert (manifest["mode"], manifest["source_run_id"]) == ("evaluate", None)
    assert {json.loads(line)["mode"] for line in trace_file.read_text().splitlines()} == {
        "evaluate"
    }
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/test_trace_store.py tests/unit/test_runner.py tests/unit/test_replay.py tests/integration/test_regression_run.py tests/integration/test_cli.py`
Expected: FAIL — `AttributeError: 'RunManifest' object has no attribute 'mode'`, `TypeError: run_dataset() got an unexpected keyword argument 'mode'`, `TypeError: replay_trace() got an unexpected keyword argument 'mode'`, `KeyError: 'mode'`.

- [ ] **Step 3: Implement**

In `relay/traces/models.py`, replace:

```python
from relay.workflow.thresholds import Thresholds

```

with:

```python
from relay.workflow.thresholds import Thresholds

# How a run's actions are used: "evaluate" (scored only; relay eval and plain relay run),
# "simulated" (the incumbent: its actions become simulated case-status transitions) or "shadow"
# (a candidate's proposals: recorded, never applied).
WorkflowMode = Literal["evaluate", "simulated", "shadow"]

```

In `relay/traces/models.py`, replace:

```python
    mode: Literal["evaluate", "shadow", "simulated"] = "evaluate"
```

with:

```python
    mode: WorkflowMode = "evaluate"
```

In `relay/traces/models.py`, replace:

```python
    sample_limit: int | None = None
    sample_seed: int | None = None
```

with:

```python
    sample_limit: int | None = None
    sample_seed: int | None = None
    # Phase 3C. Manifests written before 3C have neither key and load as an "evaluate" run.
    mode: WorkflowMode = "evaluate"
    # The run whose stored decisions this run re-issued (relay run --from-traces, and the
    # regression gate's re-decided runs); None for a run that called a provider.
    source_run_id: str | None = None
```

In `relay/evaluation/runner.py`, replace:

```python
from relay.traces.models import WorkflowTrace
```

with:

```python
from relay.traces.models import WorkflowMode, WorkflowTrace
```

In `relay/evaluation/runner.py`, replace:

```python
    git_sha: str | None = None,
) -> list[WorkflowTrace]:
    policies = validate_run_config(cases, policy_version)
```

with:

```python
    git_sha: str | None = None,
    mode: WorkflowMode = "evaluate",
) -> list[WorkflowTrace]:
    policies = validate_run_config(cases, policy_version)
```

In `relay/evaluation/runner.py`, replace:

```python
            mode="evaluate",
```

with:

```python
            mode=mode,
```

In `relay/evaluation/tracediff.py`, replace:

```python
from relay.traces.models import WorkflowTrace
```

with:

```python
from relay.traces.models import WorkflowMode, WorkflowTrace
```

In `relay/evaluation/tracediff.py`, replace:

```python
    now: datetime | None = None,
    git_sha: str | None = None,
) -> WorkflowTrace:
    """The trace's stored decisions re-run through determine_action under `policy`/`thresholds`.

    Returns a new trace: new trace_id, run_id "replay-<original run_id>", replay_of the original
    trace_id, the given policy (and its current policy_text_hash) and thresholds,
    mode="simulated". `git_sha` defaults to current_git_sha(); replay_run passes it once for a
    whole run. Raises ValueError if `case` is not the trace's case or its inputs changed.
    """
```

with:

```python
    now: datetime | None = None,
    git_sha: str | None = None,
    mode: WorkflowMode = "simulated",
    run_id: str | None = None,
) -> WorkflowTrace:
    """The trace's stored decisions re-run through determine_action under `policy`/`thresholds`.

    Returns a new trace: new trace_id, run_id `run_id` (default "replay-<original run_id>"),
    replay_of the original trace_id, the given policy (and its current policy_text_hash) and
    thresholds, and `mode` (default "simulated"; relay run --workflow shadow passes "shadow").
    `git_sha` defaults to current_git_sha(); replay_run passes it once for a whole run. Raises
    ValueError if `case` is not the trace's case or its inputs changed.
    """
```

In `relay/evaluation/tracediff.py`, replace:

```python
            "run_id": f"replay-{trace.run_id}",
```

with:

```python
            "run_id": run_id if run_id is not None else f"replay-{trace.run_id}",
```

In `relay/evaluation/tracediff.py`, replace:

```python
            "mode": "simulated",
```

with:

```python
            "mode": mode,
```

In `relay/evaluation/tracediff.py`, replace:

```python
    policy_id: str | None,
    auto_process: float | None,
) -> list[WorkflowTrace]:
    """Run-level policy replay (for Phase 3B), in trace order.
```

with:

```python
    policy_id: str | None,
    auto_process: float | None,
    mode: WorkflowMode = "simulated",
    run_id: str | None = None,
) -> list[WorkflowTrace]:
    """Run-level policy replay (for Phase 3B and relay run --from-traces), in trace order.
```

In `relay/evaluation/tracediff.py`, replace:

```python
    replayed trace shares run_id "replay-<run_id>".
```

with:

```python
    replayed trace shares run_id `run_id` (default "replay-<run_id>") and carries `mode`.
```

In `relay/evaluation/tracediff.py`, replace:

```python
                now=now,
                git_sha=git_sha,
            )
        )
    return replayed
```

with:

```python
                now=now,
                git_sha=git_sha,
                mode=mode,
                run_id=run_id,
            )
        )
    return replayed
```

In `relay/evaluation/regression_run.py`, replace:

```python
    """A simulated run that `relay eval --traces`, `compare` and `replay` can read: gzipped
    traces plus a RunManifest with extra keys mode, source_run_id, policy_id and thresholds.
    `source` is the baseline's run manifest, if found (its sample_limit/sample_seed carry over)."""
```

with:

```python
    """A simulated run that `relay eval --traces`, `compare` and `replay` can read: gzipped
    traces plus a RunManifest with mode "simulated" and source_run_id (typed fields since 3C),
    and extra keys policy_id and thresholds. `source` is the baseline's run manifest, if found
    (its sample_limit/sample_seed carry over)."""
```

In `relay/evaluation/regression_run.py`, replace:

```python
        sample_seed=None if source is None else source.sample_seed,
    )
    data = manifest.model_dump(mode="json") | {
        "mode": "simulated",
        "source_run_id": first.run_id.removeprefix("replay-"),
        "policy_id": first.policy_id,
```

with:

```python
        sample_seed=None if source is None else source.sample_seed,
        mode="simulated",
        source_run_id=first.run_id.removeprefix("replay-"),
    )
    data = manifest.model_dump(mode="json") | {
        "policy_id": first.policy_id,
```

In `relay/cli.py`, replace:

```python
from relay.traces.models import RunManifest, WorkflowTrace
```

with:

```python
from relay.traces.models import RunManifest, WorkflowMode, WorkflowTrace
```

In `relay/cli.py`, replace:

```python
    claude: ClaudeRun | None = None,
    projected: Decimal = Decimal("0"),
) -> tuple[RunManifest, list[WorkflowTrace]]:
    run_id = new_run_id()
```

with:

```python
    claude: ClaudeRun | None = None,
    projected: Decimal = Decimal("0"),
    mode: WorkflowMode = "evaluate",
) -> tuple[RunManifest, list[WorkflowTrace]]:
    run_id = new_run_id()
```

In `relay/cli.py`, replace:

```python
                concurrency=concurrency,
                git_sha=git_sha,
            )
    except BaseException as error:
```

with:

```python
                concurrency=concurrency,
                git_sha=git_sha,
                mode=mode,
            )
    except BaseException as error:
```

In `relay/cli.py`, replace:

```python
        sample_seed=None if sample is None else sample[1],
    )
    store.write_manifest(manifest)
    return manifest, traces
```

with:

```python
        sample_seed=None if sample is None else sample[1],
        mode=mode,
    )
    store.write_manifest(manifest)
    return manifest, traces
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q tests/unit/test_trace_store.py tests/unit/test_runner.py tests/unit/test_replay.py tests/integration/test_regression_run.py tests/integration/test_cli.py`
Expected: PASS.

- [ ] **Step 5: Full check, guards, commit**

```bash
uv run ruff check --fix . && uv run ruff format . && uv run pytest -q
env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env regression --config evals/regression/gates.json --strict-generated > /dev/null; echo "exit $?"   # expect exit 0
git status --short evals/   # expect no output
git add relay/traces/models.py relay/evaluation/runner.py relay/evaluation/tracediff.py relay/evaluation/regression_run.py relay/cli.py tests/unit/test_trace_store.py tests/unit/test_runner.py tests/unit/test_replay.py tests/integration/test_regression_run.py tests/integration/test_cli.py
git commit -m "feat: type the workflow mode on traces and run manifests" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The simulated case-status store

**Files:**
- Create: `relay/workflow/status.py`
- Modify: `.gitignore`
- Test: `tests/unit/test_status_store.py`

**Interfaces:**
- Consumes: `WorkflowTrace.mode` (Task 1).
- Produces (all in `relay.workflow.status`):
  - `DEFAULT_STATE = Path("state/case-status.json")`
  - `class CaseStatus(StrEnum)`: `RECEIVED`, `AUTO_APPROVED`, `INFO_REQUESTED`, `IN_HUMAN_REVIEW`
  - `ACTION_STATUS: dict[WorkflowAction, CaseStatus]`
  - `class StatusStoreError(ValueError)`, `class ShadowWriteError(StatusStoreError)`, `class ConflictError(StatusStoreError)`
  - `class Transition(BaseModel)`: `from_status: CaseStatus` (JSON key `"from"`), `to`, `action: WorkflowAction`, `trace_id`, `run_id`, `at: datetime`
  - `class CaseRecord(BaseModel)`: `status`, `history: list[Transition]`
  - `class StatusStore(RootModel[dict[str, CaseRecord]])` with `status_of(case_id) -> CaseStatus` and `last_transition(case_id) -> Transition | None`
  - `load_store(path: Path) -> StatusStore` (empty when absent; `StatusStoreError` when malformed)
  - `state_digest(path: Path) -> str` (`"sha256:<hex>"` or `"absent"`)
  - `ensure_unclaimed(store: StatusStore, case_ids: Iterable[str]) -> None` (`ConflictError`)
  - `apply_transitions(path: Path, traces: Sequence[WorkflowTrace], *, now: datetime | None = None) -> tuple[StatusStore, list[Transition]]`
  - `apply_transition(path: Path, trace: WorkflowTrace, *, now: datetime | None = None) -> Transition | None`
  - `reset_state(path: Path, now: datetime | None = None) -> Path | None`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_status_store.py`:

```python
"""The simulated case-status store: transitions, atomic writes, idempotence, conflicts, resets,
and the guarantee that a shadow trace never changes case state."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

import relay.workflow.status as status_module
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.status import (
    ACTION_STATUS,
    DEFAULT_STATE,
    CaseStatus,
    ConflictError,
    ShadowWriteError,
    StatusStore,
    StatusStoreError,
    apply_transition,
    apply_transitions,
    ensure_unclaimed,
    load_store,
    reset_state,
    state_digest,
)
from tests.factories import make_bundle, make_case, make_trace

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 26, 12, tzinfo=UTC)


def trace(case_id="T-01", *, mode="simulated", run_id="run_a", **bundle):
    case = make_case(case_id)
    t = make_trace(case, make_bundle(case_id, **bundle), run_id=run_id)
    return t.model_copy(update={"mode": mode, "trace_id": f"tr_{run_id}_{case_id}"})


def test_the_default_state_path_is_in_the_git_ignored_state_dir():
    assert DEFAULT_STATE.as_posix() == "state/case-status.json"
    assert "/state/" in (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_each_action_maps_to_one_status():
    assert ACTION_STATUS == {
        WorkflowAction.AUTO_PROCESS: CaseStatus.AUTO_APPROVED,
        WorkflowAction.REQUEST_INFO: CaseStatus.INFO_REQUESTED,
        WorkflowAction.HUMAN_REVIEW: CaseStatus.IN_HUMAN_REVIEW,
    }


def test_a_missing_file_is_an_empty_store_and_every_case_is_received(tmp_path):
    store = load_store(tmp_path / "none.json")
    assert store.root == {}
    assert store.status_of("T-01") is CaseStatus.RECEIVED
    assert store.last_transition("T-01") is None
    assert state_digest(tmp_path / "none.json") == "absent"


@pytest.mark.parametrize(
    "bundle,status",
    [
        ({}, CaseStatus.AUTO_APPROVED),
        ({"doc": 0.3}, CaseStatus.INFO_REQUESTED),
        ({"step": 0.5}, CaseStatus.IN_HUMAN_REVIEW),
    ],
)
def test_a_simulated_trace_moves_its_case_from_received(tmp_path, bundle, status):
    path = tmp_path / "state" / "case-status.json"
    t = trace(**bundle)
    transition = apply_transition(path, t, now=NOW)
    assert transition is not None
    assert (transition.from_status, transition.to, transition.action) == (
        CaseStatus.RECEIVED,
        status,
        t.action,
    )
    assert (transition.trace_id, transition.run_id, transition.at) == (t.trace_id, "run_a", NOW)
    stored = json.loads(path.read_text())
    assert stored == {
        "T-01": {
            "status": status.value,
            "history": [
                {
                    "from": "RECEIVED",
                    "to": status.value,
                    "action": t.action.value,
                    "trace_id": t.trace_id,
                    "run_id": "run_a",
                    "at": "2026-09-26T12:00:00Z",
                }
            ],
        }
    }
    assert load_store(path).status_of("T-01") is status


def test_a_run_is_applied_in_one_write(tmp_path, monkeypatch):
    path = tmp_path / "s.json"
    writes = []
    real = status_module._write
    monkeypatch.setattr(status_module, "_write", lambda p, s: (writes.append(p), real(p, s)))
    store, recorded = apply_transitions(path, [trace("T-01"), trace("T-02", doc=0.3)], now=NOW)
    assert len(writes) == 1 and len(recorded) == 2
    assert store.status_of("T-02") is CaseStatus.INFO_REQUESTED


def test_the_write_is_atomic_and_leaves_no_temp_file(tmp_path, monkeypatch):
    path = tmp_path / "s.json"
    apply_transition(path, trace("T-01"), now=NOW)
    before = path.read_bytes()

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(status_module.os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        apply_transition(path, trace("T-02"), now=NOW)
    assert path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["s.json"]


def test_reapplying_the_same_trace_is_an_idempotent_no_op(tmp_path):
    path = tmp_path / "s.json"
    t = trace()
    apply_transition(path, t, now=NOW)
    before = path.read_bytes()
    os.utime(path, (0, 0))
    assert apply_transition(path, t, now=datetime(2027, 1, 1, tzinfo=UTC)) is None
    assert path.read_bytes() == before
    assert path.stat().st_mtime == 0  # not rewritten


def test_another_run_on_a_moved_case_is_a_conflict(tmp_path):
    path = tmp_path / "s.json"
    apply_transition(path, trace(run_id="run_a"), now=NOW)
    before = path.read_bytes()
    with pytest.raises(ConflictError, match="T-01 is already AUTO_APPROVED by run run_a"):
        apply_transitions(path, [trace("T-02", run_id="run_b"), trace("T-01", run_id="run_b")])
    assert path.read_bytes() == before  # nothing from run_b was written, not even T-02


def test_a_case_twice_in_one_run_is_a_conflict(tmp_path):
    with pytest.raises(ConflictError, match="appears twice"):
        apply_transitions(tmp_path / "s.json", [trace("T-01"), trace("T-01", doc=0.3)])
    assert not (tmp_path / "s.json").exists()


def test_ensure_unclaimed_names_the_claimed_cases(tmp_path):
    path = tmp_path / "s.json"
    apply_transitions(path, [trace("T-01"), trace("T-02", step=0.5)], now=NOW)
    store = load_store(path)
    ensure_unclaimed(store, ["T-03"])
    with pytest.raises(ConflictError) as error:
        ensure_unclaimed(store, ["T-03", "T-02", "T-01"])
    message = str(error.value)
    assert "2 case(s) already moved past RECEIVED" in message
    assert "T-01 (AUTO_APPROVED by run_a), T-02 (IN_HUMAN_REVIEW by run_a)" in message
    assert "--reset-state" in message


def test_a_shadow_trace_raises_and_leaves_the_file_byte_identical(tmp_path):
    path = tmp_path / "s.json"
    apply_transition(path, trace("T-01"), now=NOW)
    before = path.read_bytes()
    digest = state_digest(path)
    with pytest.raises(ShadowWriteError, match="shadow traces never change case state"):
        apply_transition(path, trace("T-02", mode="shadow", run_id="run_s"))
    with pytest.raises(ShadowWriteError):
        apply_transitions(path, [trace("T-03"), trace("T-04", mode="shadow")])
    assert path.read_bytes() == before
    assert state_digest(path) == digest
    assert sorted(p.name for p in tmp_path.iterdir()) == ["s.json"]


def test_a_shadow_trace_never_creates_the_state_file(tmp_path):
    path = tmp_path / "s.json"
    with pytest.raises(ShadowWriteError):
        apply_transition(path, trace(mode="shadow"))
    assert not path.exists()


def test_an_evaluate_trace_is_refused_too(tmp_path):
    with pytest.raises(StatusStoreError, match="only simulated traces"):
        apply_transition(tmp_path / "s.json", trace(mode="evaluate"))
    assert not (tmp_path / "s.json").exists()


def test_reset_state_archives_the_file(tmp_path):
    path = tmp_path / "s.json"
    assert reset_state(path, NOW) is None
    apply_transition(path, trace(), now=NOW)
    content = path.read_bytes()
    backup = reset_state(path, NOW)
    assert backup == tmp_path / "s.json.bak-20260926T120000Z"
    assert backup.read_bytes() == content
    assert not path.exists()
    apply_transition(path, trace(run_id="run_b"), now=NOW)  # no conflict after a reset
    with pytest.raises(StatusStoreError, match="already exists"):
        reset_state(path, NOW)


def test_a_malformed_state_file_is_a_store_error(tmp_path):
    path = tmp_path / "s.json"
    path.write_text('{"T-01": {"status": "LOST"}}')
    with pytest.raises(StatusStoreError, match="malformed status store"):
        load_store(path)


def test_state_digest_tracks_the_bytes(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{}")
    first = state_digest(path)
    assert first.startswith("sha256:") and first == state_digest(path)
    path.write_text("{} ")
    assert state_digest(path) != first


def test_store_round_trips_by_alias():
    store = StatusStore.model_validate(
        {
            "T-01": {
                "status": "AUTO_APPROVED",
                "history": [
                    {
                        "from": "RECEIVED",
                        "to": "AUTO_APPROVED",
                        "action": "AUTO_PROCESS",
                        "trace_id": "tr_1",
                        "run_id": "run_a",
                        "at": "2026-09-26T12:00:00Z",
                    }
                ],
            }
        }
    )
    assert StatusStore.model_validate_json(store.model_dump_json(by_alias=True)) == store
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/test_status_store.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'relay.workflow.status'`.

- [ ] **Step 3: Implement**

Create `relay/workflow/status.py`:

```python
"""The simulated case-status store (Phase 3C): where the incumbent's actions take effect.

A JSON file mapping case id -> {status, history}. Every case starts RECEIVED (implicitly: a case
with no entry is RECEIVED) and a simulated run moves it to the status its action implies. Only
apply_transitions (and apply_transition, one trace) writes the file, and it refuses a shadow
trace with ShadowWriteError before touching anything: that refusal is the enforced guarantee that
a shadow candidate cannot change case state. Writes are atomic (temp file + os.replace).
"""

import hashlib
import os
import tempfile
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationError

from relay.traces.models import WorkflowTrace
from relay.workflow.outcomes import WorkflowAction

DEFAULT_STATE = Path("state/case-status.json")


class CaseStatus(StrEnum):
    RECEIVED = "RECEIVED"
    AUTO_APPROVED = "AUTO_APPROVED"
    INFO_REQUESTED = "INFO_REQUESTED"
    IN_HUMAN_REVIEW = "IN_HUMAN_REVIEW"


ACTION_STATUS: dict[WorkflowAction, CaseStatus] = {
    WorkflowAction.AUTO_PROCESS: CaseStatus.AUTO_APPROVED,
    WorkflowAction.REQUEST_INFO: CaseStatus.INFO_REQUESTED,
    WorkflowAction.HUMAN_REVIEW: CaseStatus.IN_HUMAN_REVIEW,
}


class StatusStoreError(ValueError):
    """The status store cannot be read, or this write is not allowed (a usage error: exit 2)."""


class ShadowWriteError(StatusStoreError):
    """A shadow trace was offered to the status store. Shadow proposals never take effect."""


class ConflictError(StatusStoreError):
    """A case was already moved past RECEIVED by another run (use --reset-state to start over)."""


class Transition(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    from_status: CaseStatus = Field(alias="from")
    to: CaseStatus
    action: WorkflowAction
    trace_id: str
    run_id: str
    at: datetime


class CaseRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: CaseStatus
    history: list[Transition]


class StatusStore(RootModel[dict[str, CaseRecord]]):
    """case id -> record. A case missing from the store is RECEIVED."""

    root: dict[str, CaseRecord] = {}

    def status_of(self, case_id: str) -> CaseStatus:
        record = self.root.get(case_id)
        return CaseStatus.RECEIVED if record is None else record.status

    def last_transition(self, case_id: str) -> Transition | None:
        record = self.root.get(case_id)
        return None if record is None or not record.history else record.history[-1]


def load_store(path: Path) -> StatusStore:
    """The store at `path`; an empty store when the file does not exist."""
    if not path.exists():
        return StatusStore()
    try:
        return StatusStore.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValidationError, OSError) as error:
        raise StatusStoreError(f"{path}: malformed status store: {error}") from error


def state_digest(path: Path) -> str:
    """sha256 of the file's bytes, or "absent" when there is no file."""
    if not path.exists():
        return "absent"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, store: StatusStore) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(store.model_dump_json(by_alias=True, indent=2) + "\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def ensure_unclaimed(store: StatusStore, case_ids: Iterable[str]) -> None:
    """ConflictError if any of these cases was already moved past RECEIVED. A new simulated run
    checks this before it decides anything, so a conflict costs no provider call."""
    claimed = sorted(
        f"{case_id} ({store.status_of(case_id)} by {t.run_id})"
        for case_id in set(case_ids)
        if (t := store.last_transition(case_id)) is not None
    )
    if claimed:
        shown = ", ".join(claimed[:5]) + (
            f" and {len(claimed) - 5} more" if len(claimed) > 5 else ""
        )
        raise ConflictError(
            f"{len(claimed)} case(s) already moved past RECEIVED by an earlier simulated run: "
            f"{shown}. Pass --reset-state to archive the state file and start over."
        )


def apply_transitions(
    path: Path, traces: Sequence[WorkflowTrace], *, now: datetime | None = None
) -> tuple[StatusStore, list[Transition]]:
    """Apply a simulated run's actions to the store at `path` in one atomic write.

    Every trace is checked before anything is written: a shadow trace raises ShadowWriteError, a
    trace of any other non-simulated mode raises StatusStoreError, and a case already moved past
    RECEIVED raises ConflictError unless the recorded transition has this trace's trace_id (then
    it is an idempotent no-op). Returns the new store and the transitions recorded (no-ops
    excluded). With nothing to record the file is not rewritten.
    """
    for trace in traces:
        if trace.mode == "shadow":
            raise ShadowWriteError(
                f"{trace.case_id}: trace {trace.trace_id} is a shadow proposal (run "
                f"{trace.run_id}); shadow traces never change case state"
            )
        if trace.mode != "simulated":
            raise StatusStoreError(
                f"{trace.case_id}: trace {trace.trace_id} has mode {trace.mode!r}; only "
                "simulated traces change case state"
            )
    store = load_store(path)
    when = now or datetime.now(UTC)
    records = dict(store.root)
    recorded: list[Transition] = []
    for trace in traces:
        last = store.last_transition(trace.case_id)
        if last is not None:
            if last.trace_id == trace.trace_id:
                continue
            raise ConflictError(
                f"{trace.case_id} is already {store.status_of(trace.case_id)} by run "
                f"{last.run_id}; run {trace.run_id} cannot move it again. Pass --reset-state "
                "to archive the state file and start over."
            )
        if trace.case_id in records:
            raise ConflictError(f"{trace.case_id} appears twice in run {trace.run_id}")
        transition = Transition(
            from_status=CaseStatus.RECEIVED,
            to=ACTION_STATUS[trace.action],
            action=trace.action,
            trace_id=trace.trace_id,
            run_id=trace.run_id,
            at=when,
        )
        records[trace.case_id] = CaseRecord(status=transition.to, history=[transition])
        recorded.append(transition)
    updated = StatusStore(records)
    if recorded:
        _write(path, updated)
    return updated, recorded


def apply_transition(
    path: Path, trace: WorkflowTrace, *, now: datetime | None = None
) -> Transition | None:
    """One trace through apply_transitions: the transition recorded, or None for a no-op."""
    _, recorded = apply_transitions(path, [trace], now=now)
    return recorded[0] if recorded else None


def reset_state(path: Path, now: datetime | None = None) -> Path | None:
    """Archive the state file to <state>.bak-<UTC timestamp> (os.replace, so the state is then
    absent). Returns the archive path, or None when there was no state file."""
    if not path.exists():
        return None
    when = now or datetime.now(UTC)
    backup = path.with_name(f"{path.name}.bak-{when:%Y%m%dT%H%M%SZ}")
    if backup.exists():
        raise StatusStoreError(f"{backup} already exists; not overwriting an archive")
    os.replace(path, backup)
    return backup
```

In `.gitignore`, replace:

```text
/results/
```

with:

```text
/results/
# Simulated case-status store written by relay run --workflow simulated (Phase 3C)
/state/
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q tests/unit/test_status_store.py`
Expected: PASS (19 tests). Also `mkdir -p state && touch state/x.json && git check-ignore -v state/x.json && rm state/x.json && rmdir state` prints the `/state/` rule.

- [ ] **Step 5: Full check and commit**

```bash
uv run ruff check --fix . && uv run ruff format . && uv run pytest -q
git add relay/workflow/status.py .gitignore tests/unit/test_status_store.py
git commit -m "feat: add the simulated case-status store that refuses shadow traces" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The shadow comparison (pure)

**Files:**
- Create: `relay/evaluation/shadow.py`
- Test: `tests/unit/test_shadow.py`

**Interfaces:**
- Consumes: `diff_runs(..., labelled=...)`, `EXIT_NEWLY_UNSAFE`, `TraceDiff` (`relay.evaluation.tracediff`); `build_result`, `rate`, `Rate`, `RegressionResult`, `Waiver` (`relay.evaluation.regression`).
- Produces (all in `relay.evaluation.shadow`):
  - `class Agreement(BaseModel)`: `n: int`, `agreed: Rate`, `matrix: dict[WorkflowAction, dict[WorkflowAction, int]]`, `newly_auto: list[str]`, `stopped_auto: list[str]`
  - `class ShadowReport(BaseModel)`: `dataset_id`, `n`, `incumbent_label`, `candidate_label`, `agreement: Agreement`, `promotion: RegressionResult`, `decision: Literal["PROMOTE","HOLD"]`, `exit_code: int` (0 or 4)
  - `transition_matrix(diffs: Sequence[TraceDiff]) -> dict[WorkflowAction, dict[WorkflowAction, int]]`
  - `agreement(diffs: Sequence[TraceDiff]) -> Agreement`
  - `build_shadow_report(incumbent, shadow, cases, *, incumbent_label: str, candidate_label: str, waivers: Sequence[Waiver] = (), gate_name: str | None = None, max_regressed: int | None = None, dataset_hash: str | None = None, replay_command: Callable[[str], str | None] | None = None) -> ShadowReport` (raises `EvalError` for runs that don't pair)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_shadow.py`:

```python
"""build_shadow_report: unlabelled agreement plus the evaluation-only promotion check (pure)."""

import pytest

from relay.cases.models import MissingEvidence
from relay.evaluation.metrics import EvalError
from relay.evaluation.regression import Waiver
from relay.evaluation.shadow import agreement, build_shadow_report, transition_matrix
from relay.evaluation.tracediff import diff_runs
from relay.workflow.outcomes import WorkflowAction
from tests.factories import make_bundle, make_case, make_trace, make_truth

AUTO = WorkflowAction.AUTO_PROCESS
INFO = WorkflowAction.REQUEST_INFO
REVIEW = WorkflowAction.HUMAN_REVIEW

# Expected actions: T-01 and T-02 AUTO_PROCESS, T-03 HUMAN_REVIEW, T-04 REQUEST_INFO.
CASES = [
    make_case("T-01"),
    make_case("T-02"),
    make_case("T-03", truth=make_truth(step_therapy_satisfied=False)),
    make_case(
        "T-04",
        truth=make_truth(
            documentation_complete=False, missing_evidence=MissingEvidence.TREATMENT_HISTORY
        ),
    ),
]
# Bundles that give each action under v0.1 thresholds.
BUNDLES = {AUTO: {}, REVIEW: {"step": 0.5}, INFO: {"doc": 0.3}}


def run(actions: dict[str, WorkflowAction], run_id: str):
    by_id = {c.input.id: c for c in CASES}
    traces = []
    for case_id, action in actions.items():
        t = make_trace(by_id[case_id], make_bundle(case_id, **BUNDLES[action]), run_id=run_id)
        assert t.action == action
        traces.append(t)
    return traces


INCUMBENT = run({"T-01": AUTO, "T-02": REVIEW, "T-03": REVIEW, "T-04": INFO}, "run_inc")
# T-02 newly auto-processed and correct; T-03 newly auto-processed and UNSAFE.
UNSAFE_CANDIDATE = run({"T-01": AUTO, "T-02": AUTO, "T-03": AUTO, "T-04": INFO}, "run_sh")
# T-02 newly auto-processed and correct; T-03 unchanged.
SAFE_CANDIDATE = run({"T-01": AUTO, "T-02": AUTO, "T-03": REVIEW, "T-04": INFO}, "run_sh")


def report(candidate, **kwargs):
    return build_shadow_report(
        INCUMBENT,
        candidate,
        CASES,
        incumbent_label="incumbent",
        candidate_label="candidate",
        **kwargs,
    )


def test_transition_matrix_counts_every_cell():
    diffs = diff_runs(
        INCUMBENT, UNSAFE_CANDIDATE, CASES, original_label="a", candidate_label="b", labelled=False
    )
    assert transition_matrix(diffs) == {
        AUTO: {AUTO: 1, INFO: 0, REVIEW: 0},
        INFO: {AUTO: 0, INFO: 1, REVIEW: 0},
        REVIEW: {AUTO: 2, INFO: 0, REVIEW: 0},
    }


def test_agreement_is_computed_without_ground_truth():
    diffs = diff_runs(
        INCUMBENT, UNSAFE_CANDIDATE, CASES, original_label="a", candidate_label="b", labelled=False
    )
    assert all(d.expected_original is None and d.change is None for d in diffs)
    block = agreement(diffs)
    assert (block.n, block.agreed.count, block.agreed.n, block.agreed.rate) == (4, 2, 4, 0.5)
    assert block.newly_auto == ["T-02", "T-03"]
    assert block.stopped_auto == []


def test_stopped_auto_lists_cases_the_candidate_would_no_longer_automate():
    candidate = run({"T-01": REVIEW, "T-02": REVIEW, "T-03": REVIEW, "T-04": INFO}, "run_sh")
    shadow = report(candidate)
    assert shadow.agreement.stopped_auto == ["T-01"]
    assert shadow.agreement.newly_auto == []


def test_a_newly_unsafe_candidate_is_held():
    shadow = report(UNSAFE_CANDIDATE)
    assert (shadow.decision, shadow.exit_code) == ("HOLD", 4)
    assert [e.case_id for e in shadow.promotion.newly_unsafe] == ["T-03"]
    assert shadow.promotion.failures == ["1 newly unsafe case(s) without a waiver: T-03"]
    assert (shadow.dataset_id, shadow.n) == ("test", 4)
    assert (shadow.incumbent_label, shadow.candidate_label) == ("incumbent", "candidate")


def test_a_safe_candidate_is_promoted():
    shadow = report(SAFE_CANDIDATE)
    assert (shadow.decision, shadow.exit_code) == ("PROMOTE", 0)
    assert shadow.promotion.verdict == "PASS"
    assert [e.case_id for e in shadow.promotion.improved] == ["T-02"]
    assert shadow.agreement.agreed.count == 3


def test_a_waiver_turns_hold_into_promote_and_is_scoped_by_gate_name():
    waiver = Waiver(
        case_id="T-03", gate="rollout", reason="reviewed", approved_by="r", date="2026-09-26"
    )
    assert report(UNSAFE_CANDIDATE, waivers=[waiver]).decision == "HOLD"  # no gate name
    promoted = report(UNSAFE_CANDIDATE, waivers=[waiver], gate_name="rollout")
    assert promoted.decision == "PROMOTE"
    assert [w.entry.case_id for w in promoted.promotion.waived] == ["T-03"]


def test_too_many_regressions_hold():
    candidate = run({"T-01": REVIEW, "T-02": REVIEW, "T-03": REVIEW, "T-04": INFO}, "run_sh")
    assert report(candidate).decision == "PROMOTE"  # a safe regression alone does not hold
    held = report(candidate, max_regressed=0)
    assert (held.decision, held.exit_code) == ("HOLD", 4)
    assert held.promotion.failures == ["1 regressed case(s), more than --max-regressed 0"]


def test_still_unsafe_is_reported_but_never_holds():
    incumbent = run({"T-01": AUTO, "T-02": REVIEW, "T-03": AUTO, "T-04": INFO}, "run_inc")
    candidate = run({"T-01": AUTO, "T-02": REVIEW, "T-03": AUTO, "T-04": INFO}, "run_sh")
    shadow = build_shadow_report(
        incumbent, candidate, CASES, incumbent_label="i", candidate_label="c"
    )
    assert shadow.decision == "PROMOTE"
    assert [e.case_id for e in shadow.promotion.still_unsafe] == ["T-03"]


def test_runs_over_different_cases_are_an_eval_error():
    with pytest.raises(EvalError, match="does not cover the same cases"):
        report(SAFE_CANDIDATE[:3])


def test_the_report_round_trips_as_json():
    shadow = report(UNSAFE_CANDIDATE)
    assert type(shadow).model_validate_json(shadow.model_dump_json()) == shadow


def test_replay_commands_are_attached_to_listed_cases():
    shadow = report(UNSAFE_CANDIDATE, replay_command=lambda case_id: f"relay replay {case_id}")
    assert [e.replay_command for e in shadow.promotion.newly_unsafe] == ["relay replay T-03"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/test_shadow.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'relay.evaluation.shadow'`.

- [ ] **Step 3: Implement**

Create `relay/evaluation/shadow.py`:

```python
"""Shadow comparison (Phase 3C): a shadow candidate against the incumbent on the same cases.

Pure: no file or network I/O. Two parts, kept apart on purpose:

- Agreement is unlabelled (diff_runs(labelled=False)): what a real shadow deployment can see,
  with no ground truth. Agreement rate, the incumbent x candidate action matrix, and the cases
  the candidate would newly auto-process or would stop auto-processing.
- The promotion check is EVALUATION-ONLY: the 3B regression gate (build_result over labelled
  diffs) with the incumbent as baseline. Gate PASS is PROMOTE (exit 0); gate FAIL is HOLD
  (exit 4). STILL UNSAFE cases are reported by the gate but never cause HOLD.
"""

from collections.abc import Callable, Sequence
from typing import Literal

from pydantic import BaseModel

from relay.cases.models import PriorAuthCase
from relay.evaluation.regression import Rate, RegressionResult, Waiver, build_result, rate
from relay.evaluation.tracediff import EXIT_NEWLY_UNSAFE, TraceDiff, diff_runs
from relay.traces.models import WorkflowTrace
from relay.workflow.outcomes import WorkflowAction

ACTIONS: tuple[WorkflowAction, ...] = tuple(WorkflowAction)


class Agreement(BaseModel):
    n: int
    agreed: Rate  # cases where both runs chose the same action
    # incumbent action -> candidate action -> count; every action appears on both axes.
    matrix: dict[WorkflowAction, dict[WorkflowAction, int]]
    newly_auto: list[str]  # the candidate would auto-process; the incumbent did not
    stopped_auto: list[str]  # the incumbent auto-processed; the candidate would not


class ShadowReport(BaseModel):
    dataset_id: str
    n: int
    incumbent_label: str
    candidate_label: str
    agreement: Agreement
    promotion: RegressionResult
    decision: Literal["PROMOTE", "HOLD"]
    exit_code: int  # 0 PROMOTE, EXIT_NEWLY_UNSAFE (4) HOLD


def transition_matrix(
    diffs: Sequence[TraceDiff],
) -> dict[WorkflowAction, dict[WorkflowAction, int]]:
    """Counts of (incumbent action, candidate action) over the diffs, with every cell present."""
    matrix = {a: dict.fromkeys(ACTIONS, 0) for a in ACTIONS}
    for d in diffs:
        matrix[d.action_original][d.action_candidate] += 1
    return matrix


def agreement(diffs: Sequence[TraceDiff]) -> Agreement:
    ordered = sorted(diffs, key=lambda d: d.case_id)
    auto = WorkflowAction.AUTO_PROCESS
    return Agreement(
        n=len(ordered),
        agreed=rate(sum(d.action_original == d.action_candidate for d in ordered), len(ordered)),
        matrix=transition_matrix(ordered),
        newly_auto=[
            d.case_id for d in ordered if d.action_candidate == auto and d.action_original != auto
        ],
        stopped_auto=[
            d.case_id for d in ordered if d.action_original == auto and d.action_candidate != auto
        ],
    )


def build_shadow_report(
    incumbent: Sequence[WorkflowTrace],
    shadow: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
    *,
    incumbent_label: str,
    candidate_label: str,
    waivers: Sequence[Waiver] = (),
    gate_name: str | None = None,
    max_regressed: int | None = None,
    dataset_hash: str | None = None,
    replay_command: Callable[[str], str | None] | None = None,
) -> ShadowReport:
    """Agreement (unlabelled) plus the evaluation-only promotion check. diff_runs checks both
    runs cover the same cases (EvalError otherwise); `gate_name` scopes the waivers as in 3B, and
    `replay_command` gives each listed case its `relay replay` command."""
    unlabelled = diff_runs(
        incumbent,
        shadow,
        cases,
        original_label=incumbent_label,
        candidate_label=candidate_label,
        labelled=False,
    )
    labelled = diff_runs(
        incumbent,
        shadow,
        cases,
        original_label=incumbent_label,
        candidate_label=candidate_label,
    )
    promotion = build_result(
        labelled,
        incumbent,
        shadow,
        cases,
        baseline_label=incumbent_label,
        candidate_label=candidate_label,
        gate=gate_name,
        reproduce=False,
        waivers=waivers,
        max_regressed=max_regressed,
        dataset_hash=dataset_hash,
        replay_command=replay_command,
    )
    held = promotion.verdict == "FAIL"
    return ShadowReport(
        dataset_id=promotion.dataset_id,
        n=promotion.n,
        incumbent_label=incumbent_label,
        candidate_label=candidate_label,
        agreement=agreement(unlabelled),
        promotion=promotion,
        decision="HOLD" if held else "PROMOTE",
        exit_code=EXIT_NEWLY_UNSAFE if held else 0,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q tests/unit/test_shadow.py`
Expected: PASS (11 tests).

- [ ] **Step 5: Full check and commit**

```bash
uv run ruff check --fix . && uv run ruff format . && uv run pytest -q
git add relay/evaluation/shadow.py tests/unit/test_shadow.py
git commit -m "feat: build the shadow report: unlabelled agreement and the promotion check" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Rendering the workflow lines and the shadow report

**Files:**
- Modify: `relay/reporting.py` (imports; append a section)
- Test: `tests/unit/test_reporting_shadow.py`

**Interfaces:**
- Consumes: `ShadowReport` (Task 3); `ACTION_STATUS`, `CaseStatus`, `Transition` (Task 2); the existing `render_regression`, `_rate_cell`, `_ci_cell`, `_table` in `relay/reporting.py`.
- Produces (all in `relay.reporting`):
  - `SHADOW_PROPOSALS: dict[WorkflowAction, str]`, `EVALUATION_ONLY_HEADER: str`
  - `simulated_line(transition: Transition, case_id: str) -> str`
  - `simulated_summary(run_id: str, transitions: Sequence[Transition]) -> str`
  - `shadow_line(trace: WorkflowTrace, current: tuple[CaseStatus, str | None] | None = None) -> str`
  - `shadow_trailer(run_id: str, proposals: int) -> str`
  - `promotion_line(report: ShadowReport) -> str`
  - `render_shadow_report(report: ShadowReport) -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_reporting_shadow.py`:

```python
"""Rendering for relay run --workflow simulated | shadow: the per-case lines in the handoff's
exact wording, the summaries, and the shadow comparison report."""

from datetime import UTC, datetime

import pytest

from relay.evaluation.shadow import build_shadow_report
from relay.reporting import (
    EVALUATION_ONLY_HEADER,
    promotion_line,
    render_shadow_report,
    shadow_line,
    shadow_trailer,
    simulated_line,
    simulated_summary,
)
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.status import CaseStatus, Transition
from tests.factories import make_bundle, make_case, make_trace, make_truth

AUTO = WorkflowAction.AUTO_PROCESS
INFO = WorkflowAction.REQUEST_INFO
REVIEW = WorkflowAction.HUMAN_REVIEW
BUNDLES = {AUTO: {}, REVIEW: {"step": 0.5}, INFO: {"doc": 0.3}}
NOW = datetime(2026, 9, 26, 12, tzinfo=UTC)


def trace(action, case_id="CASE-3817", run_id="run_s", case=None):
    t = make_trace(
        case or make_case(case_id), make_bundle(case_id, **BUNDLES[action]), run_id=run_id
    )
    assert t.action == action
    return t


def transition(action, to):
    return Transition(
        from_status=CaseStatus.RECEIVED, to=to, action=action, trace_id="tr", run_id="run_a", at=NOW
    )


@pytest.mark.parametrize(
    "action,expected",
    [
        (AUTO, "SHADOW: Would auto-process CASE-3817; no action was taken."),
        (INFO, "SHADOW: Would request information for CASE-3817; no action was taken."),
        (REVIEW, "SHADOW: Would send CASE-3817 to human review; no action was taken."),
    ],
)
def test_shadow_lines_use_the_handoff_wording(action, expected):
    assert shadow_line(trace(action)) == expected


def test_a_shadow_line_appends_the_current_status_when_state_exists():
    t = trace(AUTO)
    assert shadow_line(t, (CaseStatus.IN_HUMAN_REVIEW, "run_a")) == (
        "SHADOW: Would auto-process CASE-3817; no action was taken. "
        "(current status: IN_HUMAN_REVIEW by run_a)"
    )
    assert shadow_line(t, (CaseStatus.RECEIVED, None)) == (
        "SHADOW: Would auto-process CASE-3817; no action was taken. (current status: RECEIVED)"
    )


def test_the_shadow_trailer():
    assert shadow_trailer("run_s", 100) == (
        "SHADOW RUN run_s: 100 proposals recorded; case state unchanged (verified)."
    )


def test_simulated_line_and_summary():
    t = transition(AUTO, CaseStatus.AUTO_APPROVED)
    assert simulated_line(t, "CASE-3817") == (
        "SIMULATED: CASE-3817 RECEIVED → AUTO_APPROVED (AUTO_PROCESS)"
    )
    transitions = [
        t,
        transition(REVIEW, CaseStatus.IN_HUMAN_REVIEW),
        transition(REVIEW, CaseStatus.IN_HUMAN_REVIEW),
    ]
    assert simulated_summary("run_a", transitions) == (
        "SIMULATED RUN run_a: 3 transitions applied — AUTO_APPROVED 1 · INFO_REQUESTED 0 · "
        "IN_HUMAN_REVIEW 2"
    )


def shadow_report(candidate_t03: WorkflowAction):
    cases = [make_case("T-01"), make_case("T-02", truth=make_truth(step_therapy_satisfied=False))]
    incumbent = [
        trace(AUTO, "T-01", "run_inc", cases[0]),
        trace(REVIEW, "T-02", "run_inc", cases[1]),
    ]
    candidate = [
        trace(REVIEW, "T-01", "run_sh", cases[0]),
        trace(candidate_t03, "T-02", "run_sh", cases[1]),
    ]
    return build_shadow_report(
        incumbent, candidate, cases, incumbent_label="jev 0.95", candidate_label="jev 0.89"
    )


def test_render_shadow_report_puts_agreement_first_and_the_promotion_check_last():
    text = render_shadow_report(shadow_report(AUTO))
    lines = text.splitlines()
    assert lines[:8] == [
        "Relay shadow comparison — dataset test · n=2",
        "INCUMBENT jev 0.95",
        "CANDIDATE jev 0.89",
        "",
        "AGREEMENT (unlabelled; what a real shadow deployment sees)",
        "  Action agreement: 0/2 (0.0%)  95% CI [0.0%, 84.2%]",
        "",
        "  INCUMBENT \\ CANDIDATE  AUTO_PROCESS  REQUEST_INFO  HUMAN_REVIEW",
    ]
    assert lines[8:11] == [
        "  AUTO_PROCESS           0             0             1",
        "  REQUEST_INFO           0             0             0",
        "  HUMAN_REVIEW           1             0             0",
    ]
    assert "  Would newly auto-process (1): T-02" in lines
    assert "  Would stop auto-processing (1): T-01" in lines
    header = lines.index(EVALUATION_ONLY_HEADER)
    assert header < lines.index("NEWLY UNSAFE (1)")
    assert lines[header + 1] == "Relay regression — dataset test · n=2"
    assert lines[-3] == "REGRESSION GATE: FAIL — 1 newly unsafe case(s) without a waiver: T-02"
    assert lines[-1] == ("PROMOTION CHECK: HOLD — 1 newly unsafe case(s) without a waiver: T-02")


def test_promotion_line_for_a_promoted_candidate():
    report = shadow_report(REVIEW)
    assert report.decision == "PROMOTE"
    assert promotion_line(report) == "PROMOTION CHECK: PROMOTE"
    text = render_shadow_report(report)
    assert "  Would newly auto-process (0): none" in text.splitlines()
    assert text.splitlines()[-1] == "PROMOTION CHECK: PROMOTE"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/test_reporting_shadow.py`
Expected: FAIL — `ImportError: cannot import name 'EVALUATION_ONLY_HEADER' from 'relay.reporting'`.

- [ ] **Step 3: Implement**

In `relay/reporting.py`, replace:

```python
from relay.evaluation.regression import CHANGE_ORDER, CaseEntry, Rate, RegressionResult
```

with:

```python
from relay.evaluation.regression import CHANGE_ORDER, CaseEntry, Rate, RegressionResult
from relay.evaluation.shadow import ShadowReport
```

In `relay/reporting.py`, replace:

```python
from relay.workflow.outcomes import WorkflowAction
```

with:

```python
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.status import ACTION_STATUS, CaseStatus, Transition
```

Append to the end of `relay/reporting.py`:

```python
# ---- relay run --workflow simulated | shadow (Phase 3C) ----

# The handoff's exact wording for a shadow proposal, per action.
SHADOW_PROPOSALS: dict[WorkflowAction, str] = {
    WorkflowAction.AUTO_PROCESS: "Would auto-process {case_id}",
    WorkflowAction.REQUEST_INFO: "Would request information for {case_id}",
    WorkflowAction.HUMAN_REVIEW: "Would send {case_id} to human review",
}
EVALUATION_ONLY_HEADER = (
    "EVALUATION-ONLY (uses ground truth; not available in a real shadow deployment)"
)


def simulated_line(transition: Transition, case_id: str) -> str:
    """`SIMULATED: CASE-ID RECEIVED → AUTO_APPROVED (AUTO_PROCESS)`."""
    return f"SIMULATED: {case_id} {transition.from_status} → {transition.to} ({transition.action})"


def simulated_summary(run_id: str, transitions: Sequence[Transition]) -> str:
    counts = " · ".join(
        f"{status} {sum(t.to == status for t in transitions)}" for status in ACTION_STATUS.values()
    )
    return f"SIMULATED RUN {run_id}: {len(transitions)} transitions applied — {counts}"


def shadow_line(trace: WorkflowTrace, current: tuple[CaseStatus, str | None] | None = None) -> str:
    """`SHADOW: Would auto-process CASE-ID; no action was taken.`, plus
    ` (current status: <STATUS> by <run_id>)` when a state file exists (`current` is the case's
    status there and the run that set it, None for a case still RECEIVED)."""
    proposal = SHADOW_PROPOSALS[trace.action].format(case_id=trace.case_id)
    line = f"SHADOW: {proposal}; no action was taken."
    if current is not None:
        status, run_id = current
        line += f" (current status: {status}" + ("" if run_id is None else f" by {run_id}") + ")"
    return line


def shadow_trailer(run_id: str, proposals: int) -> str:
    return f"SHADOW RUN {run_id}: {proposals} proposals recorded; case state unchanged (verified)."


def promotion_line(report: ShadowReport) -> str:
    if report.decision == "PROMOTE":
        return "PROMOTION CHECK: PROMOTE"
    return "PROMOTION CHECK: HOLD — " + "; ".join(report.promotion.failures)


def _case_list(title: str, case_ids: Sequence[str]) -> list[str]:
    return [f"  {title} ({len(case_ids)}): " + (", ".join(case_ids) if case_ids else "none")]


def render_shadow_report(report: ShadowReport) -> str:
    """The shadow comparison (and shadow.md): the unlabelled agreement section, then the
    evaluation-only promotion check (the full 3B regression report) and the PROMOTION CHECK
    line last."""
    a = report.agreement
    rows = [["INCUMBENT \\ CANDIDATE", *[str(action) for action in a.matrix]]]
    for before, row in a.matrix.items():
        rows.append([str(before), *[str(count) for count in row.values()]])
    lines = [
        f"Relay shadow comparison — dataset {report.dataset_id} · n={report.n}",
        f"INCUMBENT {report.incumbent_label}",
        f"CANDIDATE {report.candidate_label}",
        "",
        "AGREEMENT (unlabelled; what a real shadow deployment sees)",
        f"  Action agreement: {_rate_cell(a.agreed)}  95% CI {_ci_cell(a.agreed)}",
        "",
        *["  " + line for line in _table(rows)],
        "",
        *_case_list("Would newly auto-process", a.newly_auto),
        *_case_list("Would stop auto-processing", a.stopped_auto),
        "",
        EVALUATION_ONLY_HEADER,
        render_regression(report.promotion),
        "",
        promotion_line(report),
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q tests/unit/test_reporting_shadow.py`
Expected: PASS (8 tests).

- [ ] **Step 5: Full check and commit**

```bash
uv run ruff check --fix . && uv run ruff format . && uv run pytest -q
git add relay/reporting.py tests/unit/test_reporting_shadow.py
git commit -m "feat: render SIMULATED and SHADOW lines and the shadow comparison report" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `relay run --workflow simulated|shadow`

**Files:**
- Modify: `relay/cli.py` (imports; replace `_run_and_report` and the `run` command)
- Test: `tests/integration/test_cli_workflow.py`

**Interfaces:**
- Consumes: `_execute(..., mode)` and `replay_run(..., mode, run_id)` (Task 1); `DEFAULT_STATE`, `StatusStoreError`, `apply_transitions`, `ensure_unclaimed`, `load_store`, `reset_state`, `state_digest` (Task 2); `shadow_line`, `shadow_trailer`, `simulated_line`, `simulated_summary` (Task 4).
- Produces (in `relay.cli`, used by Task 6):
  - `_run_provider(cases, provider, policy, concurrency, traces_dir, dataset, questions, sample=None, claude=None, mode="evaluate") -> tuple[RunManifest, list[WorkflowTrace]]` (every provider guard; `_run_and_report` now calls it)
  - `class Workflow(StrEnum)`: `simulated`, `shadow`
  - `_reissue(from_traces, cases, dataset, traces_dir, mode, at, sample) -> tuple[RunManifest, list[WorkflowTrace]]`
  - `@dataclass(frozen=True) class WorkflowRequest` with fields `workflow, dataset, traces_dir, state, from_traces=None, at=None, provider=ProviderName.jev, policy="v0.1", concurrency=4, questions=None, claude=None, reset_state=False`
  - `_workflow_traces(request, cases, sample)`, `_run_paths(manifest) -> list[str]`, `_run_simulated(request, cases, sample)`, `_run_shadow(request, cases, sample)`
  - `relay run` options: `--workflow`, `--from-traces`, `--at`, `--state`, `--reset-state`; `--provider`/`--policy` default `None` (resolved to `jev`/`v0.1`)
  - Exit codes: 0 ok; 2 usage/input/conflict; 3 SHADOW VIOLATION

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_cli_workflow.py`:

```python
"""relay run --workflow simulated | shadow (Phase 3C). Offline: --from-traces over smoke runs made
in tmp by the groundtruth and rules providers. The live provider path uses fakes only. Every
state file is under tmp_path; nothing here touches state/ or the real spend ledger."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner
from typesafe_sdk import SystemOneResponse

import relay.cli as cli_module
from relay.cli import app
from relay.evaluation.tracediff import replay_run as real_replay_run
from relay.traces.store import read_traces
from relay.workflow.status import load_store, state_digest
from tests.claude_fakes import FakeBatches, FakeMessages, message

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
JEV_FIXTURE = REPO / "tests" / "fixtures" / "jev" / "auto01_response.json"
runner = CliRunner()

STATUS_OF = {
    "AUTO_PROCESS": "AUTO_APPROVED",
    "REQUEST_INFO": "INFO_REQUESTED",
    "HUMAN_REVIEW": "IN_HUMAN_REVIEW",
}
PROPOSAL = {
    "AUTO_PROCESS": "SHADOW: Would auto-process {}; no action was taken.",
    "REQUEST_INFO": "SHADOW: Would request information for {}; no action was taken.",
    "HUMAN_REVIEW": "SHADOW: Would send {} to human review; no action was taken.",
}


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--env-file", str(tmp_path / "missing.env"), *map(str, args)])


def workflow(tmp_path, kind, *args):
    return invoke(
        tmp_path,
        "run",
        "--dataset",
        SMOKE,
        "--workflow",
        kind,
        "--traces-dir",
        tmp_path / "traces",
        "--state",
        tmp_path / "state" / "case-status.json",
        *args,
    )


def new_run(tmp_path, result):
    """The trace file and manifest a workflow run printed."""
    lines = result.output.splitlines()
    trace_file = Path(next(x for x in lines if x.startswith("Traces: ")).removeprefix("Traces: "))
    manifest = json.loads(trace_file.with_suffix(".manifest.json").read_text())
    return trace_file, manifest


@pytest.fixture(scope="module")
def smoke_runs(tmp_path_factory):
    """One ordinary (evaluate) smoke run per offline provider, made once for the module."""
    root = tmp_path_factory.mktemp("workflow-smoke")
    files = {}
    for provider in ("groundtruth", "rules"):
        result = invoke(
            root,
            "run",
            "--dataset",
            SMOKE,
            "--provider",
            provider,
            "--traces-dir",
            root / provider / "traces",
            "--reports-dir",
            root / provider / "reports",
        )
        assert result.exit_code == 0, result.output
        [files[provider]] = (root / provider / "traces").glob("*.jsonl")
    return files


# ---- simulated ----


def test_simulated_applies_every_action_to_the_state(tmp_path, smoke_runs):
    result = workflow(tmp_path, "simulated", "--from-traces", smoke_runs["groundtruth"])
    assert result.exit_code == 0, result.output
    trace_file, manifest = new_run(tmp_path, result)
    traces = read_traces(trace_file)
    source = {t.case_id: t for t in read_traces(smoke_runs["groundtruth"])}
    assert len(traces) == 10
    assert {t.mode for t in traces} == {"simulated"}
    assert {t.run_id for t in traces} == {manifest["run_id"]}
    assert all(t.replay_of == source[t.case_id].trace_id for t in traces)
    assert (manifest["mode"], manifest["source_run_id"]) == (
        "simulated",
        smoke_runs["groundtruth"].stem,
    )
    lines = result.output.splitlines()
    for t in traces:
        expected = f"SIMULATED: {t.case_id} RECEIVED → {STATUS_OF[t.action]} ({t.action})"
        assert expected in lines
    assert lines[:10] == sorted(lines[:10])  # one line per case, by case id
    assert (
        f"SIMULATED RUN {manifest['run_id']}: 10 transitions applied — AUTO_APPROVED 3 · "
        "INFO_REQUESTED 3 · IN_HUMAN_REVIEW 4"
    ) in lines
    state = tmp_path / "state" / "case-status.json"
    assert lines[-1] == f"State: {state}"
    store = load_store(state)
    assert {c: store.status_of(c) for c in source} == {
        c: STATUS_OF[t.action] for c, t in source.items()
    }
    assert {store.last_transition(c).run_id for c in source} == {manifest["run_id"]}


def test_a_second_simulated_run_conflicts_until_the_state_is_reset(tmp_path, smoke_runs):
    first = workflow(tmp_path, "simulated", "--from-traces", smoke_runs["groundtruth"])
    assert first.exit_code == 0, first.output
    state = tmp_path / "state" / "case-status.json"
    before = state.read_bytes()
    runs_before = sorted((tmp_path / "traces").glob("*.jsonl"))
    again = workflow(tmp_path, "simulated", "--from-traces", smoke_runs["rules"])
    assert again.exit_code == 2
    assert "10 case(s) already moved past RECEIVED" in again.output
    assert "--reset-state" in again.output
    assert state.read_bytes() == before
    assert sorted((tmp_path / "traces").glob("*.jsonl")) == runs_before  # checked before running
    reset = workflow(tmp_path, "simulated", "--from-traces", smoke_runs["rules"], "--reset-state")
    assert reset.exit_code == 0, reset.output
    [backup] = (tmp_path / "state").glob("case-status.json.bak-*")
    assert backup.read_bytes() == before
    assert f"State archived: {backup}" in reset.output.splitlines()
    _, manifest = new_run(tmp_path, reset)
    assert load_store(state).last_transition("AUTO-01").run_id == manifest["run_id"]


def test_at_re_decides_the_stored_run(tmp_path, smoke_runs):
    result = workflow(tmp_path, "simulated", "--from-traces", smoke_runs["rules"], "--at", "0.5")
    assert result.exit_code == 0, result.output
    trace_file, _ = new_run(tmp_path, result)
    assert {t.thresholds.version for t in read_traces(trace_file)} == {"v0.1+at0.5"}


# ---- shadow ----


def test_shadow_uses_the_handoff_wording_and_never_touches_the_state(tmp_path, smoke_runs):
    sim = workflow(tmp_path, "simulated", "--from-traces", smoke_runs["groundtruth"])
    assert sim.exit_code == 0, sim.output
    _, sim_manifest = new_run(tmp_path, sim)
    state = tmp_path / "state" / "case-status.json"
    digest = state_digest(state)
    result = workflow(tmp_path, "shadow", "--from-traces", smoke_runs["rules"])
    assert result.exit_code == 0, result.output
    assert state_digest(state) == digest
    trace_file, manifest = new_run(tmp_path, result)
    traces = read_traces(trace_file)
    assert {t.mode for t in traces} == {"shadow"}
    assert (manifest["mode"], manifest["source_run_id"]) == ("shadow", smoke_runs["rules"].stem)
    store = load_store(state)
    lines = result.output.splitlines()
    for t in traces:
        current = f" (current status: {store.status_of(t.case_id)} by {sim_manifest['run_id']})"
        assert PROPOSAL[t.action].format(t.case_id) + current in lines
    assert lines[11] == (
        f"SHADOW RUN {manifest['run_id']}: 10 proposals recorded; case state unchanged (verified)."
    )


def test_shadow_without_a_state_file_has_no_status_suffix_and_creates_nothing(tmp_path, smoke_runs):
    result = workflow(tmp_path, "shadow", "--from-traces", smoke_runs["rules"])
    assert result.exit_code == 0, result.output
    assert not (tmp_path / "state").exists()
    trace_file, _ = new_run(tmp_path, result)
    for t in read_traces(trace_file):
        assert PROPOSAL[t.action].format(t.case_id) in result.output.splitlines()
    assert "current status" not in result.output


def test_a_state_change_during_a_shadow_run_is_a_shadow_violation(
    tmp_path, smoke_runs, monkeypatch
):
    state = tmp_path / "state" / "case-status.json"
    assert (
        workflow(tmp_path, "simulated", "--from-traces", smoke_runs["groundtruth"]).exit_code == 0
    )

    def tampering_replay_run(*args, **kwargs):
        state.write_text(state.read_text() + " ")
        return real_replay_run(*args, **kwargs)

    monkeypatch.setattr(cli_module, "replay_run", tampering_replay_run)
    result = workflow(tmp_path, "shadow", "--from-traces", smoke_runs["rules"])
    assert result.exit_code == 3
    assert "SHADOW VIOLATION" in result.output
    assert "Would " not in result.output
    assert "unchanged (verified)" not in result.output


# ---- flags ----


@pytest.mark.parametrize(
    "args,message",
    [
        (["--from-traces", "{gt}"], "--from-traces needs --workflow"),
        (["--state", "s.json"], "--state needs --workflow"),
        (["--workflow", "shadow", "--at", "0.9"], "--at needs --from-traces"),
        (["--workflow", "shadow", "--from-traces", "{gt}", "--at", "0"], "--at must be in (0, 1]"),
        (
            ["--workflow", "shadow", "--from-traces", "{gt}", "--provider", "rules"],
            "--provider cannot be combined with --from-traces",
        ),
        (
            ["--workflow", "shadow", "--from-traces", "{gt}", "--policy", "v0.1"],
            "--policy cannot be combined with --from-traces",
        ),
        (
            ["--workflow", "shadow", "--from-traces", "{gt}", "--reset-state"],
            "--reset-state applies only to --workflow simulated",
        ),
    ],
)
def test_usage_errors_exit_2_before_anything_is_written(tmp_path, smoke_runs, args, message):
    args = [a.replace("{gt}", str(smoke_runs["groundtruth"])) for a in args]
    result = invoke(tmp_path, "run", "--dataset", SMOKE, "--traces-dir", tmp_path / "traces", *args)
    assert result.exit_code == 2
    assert message in result.output
    assert not (tmp_path / "traces").exists()


def test_from_traces_over_another_dataset_is_an_input_error(tmp_path, smoke_runs):
    gold_jev = REPO / "evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz"
    result = workflow(tmp_path, "shadow", "--from-traces", gold_jev)
    assert result.exit_code == 2
    assert "--from-traces" in result.output
    assert not (tmp_path / "traces").exists()


# ---- the live provider path (fakes only) ----


class FakeTypeSafe:
    """Stands in for AsyncTypeSafeClient: every case gets the AUTO-01 fixture."""

    calls = 0

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def system_one(self, state, questions, *, model=None, **kwargs):
        FakeTypeSafe.calls += 1
        return SystemOneResponse.model_validate(json.loads(JEV_FIXTURE.read_text()))


class FakeAnthropic:
    """Stands in for AsyncAnthropic: every case gets the same well-formed sync reply."""

    def __init__(self, **kwargs):
        self.messages = FakeMessages(message(), batches=FakeBatches([]))

    def with_options(self, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None


@pytest.fixture
def fake_jev(monkeypatch):
    FakeTypeSafe.calls = 0
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", FakeTypeSafe)
    return FakeTypeSafe


def test_a_live_shadow_run_goes_through_the_provider(tmp_path, fake_jev):
    result = workflow(tmp_path, "shadow", "--provider", "jev")
    assert result.exit_code == 0, result.output
    assert fake_jev.calls == 10
    trace_file, manifest = new_run(tmp_path, result)
    assert {(t.mode, t.provider) for t in read_traces(trace_file)} == {("shadow", "jev")}
    assert (manifest["mode"], manifest["source_run_id"]) == ("shadow", None)
    assert "SHADOW: Would " in result.output
    assert not (tmp_path / "state").exists()


def test_a_live_run_keeps_the_jev_key_guard(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    result = workflow(tmp_path, "shadow", "--provider", "jev")
    assert result.exit_code == 2
    assert "TYPESAFE_API_KEY is not set" in result.output
    assert not (tmp_path / "traces").exists()


def test_a_simulated_conflict_is_found_before_the_provider_is_called(
    tmp_path, smoke_runs, fake_jev
):
    assert workflow(tmp_path, "simulated", "--from-traces", smoke_runs["rules"]).exit_code == 0
    result = workflow(tmp_path, "simulated", "--provider", "jev")
    assert result.exit_code == 2
    assert "already moved past RECEIVED" in result.output
    assert fake_jev.calls == 0


def test_a_live_claude_simulated_run_uses_the_budget_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncAnthropic", FakeAnthropic)
    ledger = tmp_path / "spend.json"
    result = workflow(tmp_path, "simulated", "--provider", "claude", "--ledger", ledger)
    assert result.exit_code == 0, result.output
    assert "Claude budget: spent $0.0000, projected $2.5000 for 10 cases (sync)" in result.output
    [entry] = json.loads(ledger.read_text())["entries"]
    assert entry["status"] == "settled"
    trace_file, manifest = new_run(tmp_path, result)
    assert entry["run_id"] == manifest["run_id"]
    assert {t.mode for t in read_traces(trace_file)} == {"simulated"}
    assert len(load_store(tmp_path / "state" / "case-status.json").root) == 10


def test_a_live_claude_run_without_a_key_exits_2_before_the_ledger(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ledger = tmp_path / "spend.json"
    result = workflow(tmp_path, "shadow", "--provider", "claude", "--ledger", ledger)
    assert result.exit_code == 2
    assert "ANTHROPIC_API_KEY is not set" in result.output
    assert not ledger.exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/integration/test_cli_workflow.py`
Expected: FAIL — `No such option: --workflow` (exit 2 where 0 is expected) in most tests.

- [ ] **Step 3: Implement**

In `relay/cli.py`, replace:

```python
    replay_exit_code,
    replay_thresholds,
    replay_trace,
)
```

with:

```python
    replay_exit_code,
    replay_run,
    replay_thresholds,
    replay_trace,
)
```

In `relay/cli.py`, replace:

```python
    render_run_table,
    render_trace_diff,
)
from relay.traces.models import RunManifest, WorkflowMode, WorkflowTrace
from relay.traces.store import TraceStore, current_git_sha, new_run_id, read_traces
```

with:

```python
    render_run_table,
    render_trace_diff,
    shadow_line,
    shadow_trailer,
    simulated_line,
    simulated_summary,
)
from relay.traces.models import RunManifest, WorkflowMode, WorkflowTrace
from relay.traces.store import TraceStore, current_git_sha, new_run_id, read_traces
from relay.workflow.status import (
    DEFAULT_STATE,
    StatusStoreError,
    apply_transitions,
    ensure_unclaimed,
    load_store,
    reset_state,
    state_digest,
)
```

In `relay/cli.py`, replace everything from the line `def _run_and_report(` up to, but not including, the line `@app.command("eval")` (that span is the current `_run_and_report` function and the whole `run` command) with the following. Keep the two blank lines before `@app.command("eval")`.

```python
def _run_provider(
    cases: list[PriorAuthCase],
    provider: ProviderName,
    policy: str,
    concurrency: int,
    traces_dir: Path,
    dataset: Path,
    questions: str | None,
    sample: tuple[int, int] | None = None,
    claude: ClaudeRun | None = None,
    mode: WorkflowMode = "evaluate",
) -> tuple[RunManifest, list[WorkflowTrace]]:
    """A provider run with every guard: question set, policy and key preflight, the Claude budget
    check and ledger, and the provider's NOTE."""
    resolved = _resolve_questions(provider, questions)
    _preflight(cases, provider, policy)
    projected = _claude_budget_check(claude, cases) if claude is not None else Decimal("0")
    if provider in PROVIDER_NOTES:
        typer.echo(f"NOTE: {PROVIDER_NOTES[provider]}")
    return asyncio.run(
        _execute(
            cases,
            provider,
            policy,
            concurrency,
            traces_dir,
            dataset,
            resolved,
            sample,
            claude,
            projected,
            mode,
        )
    )


def _run_and_report(
    cases: list[PriorAuthCase],
    provider: ProviderName,
    policy: str,
    concurrency: int,
    traces_dir: Path,
    reports_dir: Path,
    dataset: Path,
    questions: str | None,
    sample: tuple[int, int] | None = None,
    claude: ClaudeRun | None = None,
) -> list[WorkflowTrace]:
    manifest, traces = _run_provider(
        cases, provider, policy, concurrency, traces_dir, dataset, questions, sample, claude
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{manifest.run_id}.md"
    report_path.write_text(
        render_run_report(manifest, traces, {c.input.id: c.input for c in cases}),
        encoding="utf-8",
    )
    typer.echo(render_run_table(traces))
    typer.echo(f"\nTraces: {manifest.trace_file}\nReport: {report_path}")
    return traces


class Workflow(StrEnum):
    simulated = "simulated"
    shadow = "shadow"


def _reissue(
    from_traces: Path,
    cases: list[PriorAuthCase],
    dataset: Path,
    traces_dir: Path,
    mode: WorkflowMode,
    at: float | None,
    sample: tuple[int, int] | None,
) -> tuple[RunManifest, list[WorkflowTrace]]:
    """--from-traces: the stored run's decisions re-issued as a new run in `mode` (replay_run,
    re-decided at `at` if given), written like any run. No provider is called."""
    source = _read_trace_file(from_traces)
    if not source:
        raise _fail(f"{from_traces}: no traces")
    run_id = new_run_id()
    try:
        traces = replay_run(
            source, cases, policy_id=None, auto_process=at, mode=mode, run_id=run_id
        )
    except (EvalError, ValueError) as error:
        raise _fail(f"--from-traces {from_traces}: {error}") from error
    store = TraceStore.create(traces_dir, run_id)
    for trace in traces:
        store.append(trace)
    first = traces[0]
    manifest = RunManifest(
        run_id=run_id,
        created_at=datetime.now(UTC),
        dataset_id=first.dataset_id,
        dataset_path=str(dataset),
        provider=first.provider,
        policy_version=first.policy_version,
        question_set_version=first.question_set_version,
        case_count=len(traces),
        trace_file=str(store.path),
        relay_git_sha=first.relay_git_sha,
        sample_limit=None if sample is None else sample[0],
        sample_seed=None if sample is None else sample[1],
        mode=mode,
        source_run_id=source[0].run_id,
    )
    store.write_manifest(manifest)
    return manifest, traces


@dataclass(frozen=True)
class WorkflowRequest:
    """Everything `relay run --workflow` needs beyond the cases (flags already validated)."""

    workflow: Workflow
    dataset: Path
    traces_dir: Path
    state: Path
    from_traces: Path | None = None
    at: float | None = None
    provider: ProviderName = ProviderName.jev
    policy: str = "v0.1"
    concurrency: int = 4
    questions: str | None = None
    claude: ClaudeRun | None = None
    reset_state: bool = False


def _workflow_traces(
    request: WorkflowRequest, cases: list[PriorAuthCase], sample: tuple[int, int] | None
) -> tuple[RunManifest, list[WorkflowTrace]]:
    mode: WorkflowMode = request.workflow.value
    if request.from_traces is not None:
        return _reissue(
            request.from_traces,
            cases,
            request.dataset,
            request.traces_dir,
            mode,
            request.at,
            sample,
        )
    return _run_provider(
        cases,
        request.provider,
        request.policy,
        request.concurrency,
        request.traces_dir,
        request.dataset,
        request.questions,
        sample,
        request.claude,
        mode,
    )


def _run_paths(manifest: RunManifest) -> list[str]:
    trace_file = Path(manifest.trace_file)
    return [f"Traces: {trace_file}", f"Manifest: {trace_file.with_suffix('.manifest.json')}"]


def _run_simulated(
    request: WorkflowRequest, cases: list[PriorAuthCase], sample: tuple[int, int] | None
) -> None:
    """The incumbent: every action becomes a simulated case-status transition in --state."""
    try:
        if request.reset_state:
            backup = reset_state(request.state)
            typer.echo(
                f"State archived: {backup}"
                if backup is not None
                else f"State: nothing to archive at {request.state}"
            )
        ensure_unclaimed(load_store(request.state), [c.input.id for c in cases])
    except StatusStoreError as error:
        raise _fail(str(error)) from error
    manifest, traces = _workflow_traces(request, cases, sample)
    try:
        _, transitions = apply_transitions(request.state, traces)
    except StatusStoreError as error:
        raise _fail(str(error)) from error
    by_case = {t.trace_id: t.case_id for t in traces}
    for transition in sorted(transitions, key=lambda t: by_case[t.trace_id]):
        typer.echo(simulated_line(transition, by_case[transition.trace_id]))
    typer.echo("")
    typer.echo(simulated_summary(manifest.run_id, transitions))
    for line in [*_run_paths(manifest), f"State: {request.state}"]:
        typer.echo(line)


def _run_shadow(
    request: WorkflowRequest, cases: list[PriorAuthCase], sample: tuple[int, int] | None
) -> None:
    """A candidate in shadow: its proposals are recorded and never applied. The state file is
    read, never written, and hashed before and after to prove it (exit 3 if it changed)."""
    before = state_digest(request.state)
    try:
        store = load_store(request.state)
    except StatusStoreError as error:
        raise _fail(str(error)) from error
    manifest, traces = _workflow_traces(request, cases, sample)
    after = state_digest(request.state)
    if after != before:
        typer.echo(
            f"SHADOW VIOLATION: {request.state} changed during shadow run {manifest.run_id} "
            f"({before} → {after})",
            err=True,
        )
        raise typer.Exit(code=3)
    for trace in sorted(traces, key=lambda t: t.case_id):
        current = None
        if before != "absent":
            last = store.last_transition(trace.case_id)
            current = (store.status_of(trace.case_id), None if last is None else last.run_id)
        typer.echo(shadow_line(trace, current))
    typer.echo("")
    typer.echo(shadow_trailer(manifest.run_id, len(traces)))
    for line in _run_paths(manifest):
        typer.echo(line)


RunProvider = Annotated[
    ProviderName | None, typer.Option("--provider", help="Decision provider (default jev).")
]
RunPolicy = Annotated[
    str | None, typer.Option("--policy", help="Policy/threshold version (default v0.1).")
]


@app.command()
def run(
    dataset: Dataset,
    provider: RunProvider = None,
    policy: RunPolicy = None,
    concurrency: Concurrency = 4,
    traces_dir: TracesDir = Path("traces"),
    reports_dir: ReportsDir = Path("reports"),
    questions: Questions = None,
    limit: Limit = None,
    sample_seed: SampleSeed = None,
    mode: ModeOption = None,
    budget_usd: BudgetUsd = None,
    ledger: LedgerOption = None,
    batch_id: BatchId = None,
    workflow: Annotated[
        Workflow | None,
        typer.Option(
            help="simulated: the incumbent; its actions become simulated case-status transitions "
            "in --state. shadow: a candidate; its proposals are recorded and case state is never "
            "changed. Without it, an ordinary traced run with a Markdown report."
        ),
    ] = None,
    from_traces: Annotated[
        Path | None,
        typer.Option(
            exists=True,
            dir_okay=False,
            help="--workflow only: re-issue this stored run's decisions instead of calling a "
            "provider (offline).",
        ),
    ] = None,
    at: Annotated[
        float | None,
        typer.Option(
            help="With --from-traces: re-decide at this auto_process threshold, in (0, 1]."
        ),
    ] = None,
    state: Annotated[
        Path | None,
        typer.Option(
            dir_okay=False,
            help=f"--workflow only: the case-status store (default {DEFAULT_STATE}).",
        ),
    ] = None,
    reset_state_flag: Annotated[
        bool,
        typer.Option(
            "--reset-state",
            help="--workflow simulated only: archive the state file to <state>.bak-<UTC "
            "timestamp> and start from RECEIVED.",
        ),
    ] = False,
) -> None:
    """Decide every case in DATASET; write traces and a Markdown report.

    With --workflow: simulated (the incumbent's actions change simulated case status) or shadow
    (a candidate's proposals are recorded, never applied). Exit codes: 0 ok; 2 usage/input
    error; 3 SHADOW VIOLATION.
    """
    if workflow is None:
        given = [
            flag
            for flag, value in (
                ("--from-traces", from_traces),
                ("--at", at),
                ("--state", state),
                ("--reset-state", reset_state_flag or None),
            )
            if value is not None
        ]
        if given:
            raise _fail(f"{', '.join(given)} needs --workflow simulated or --workflow shadow")
        resolved_provider = provider or ProviderName.jev
        claude = _resolve_claude(resolved_provider, mode, budget_usd, ledger, batch_id)
        cases, sample = _apply_limit(_load_cases(dataset), limit, sample_seed)
        _run_and_report(
            cases,
            resolved_provider,
            policy or "v0.1",
            concurrency,
            traces_dir,
            reports_dir,
            dataset,
            questions,
            sample,
            claude,
        )
        return
    if at is not None and from_traces is None:
        raise _fail("--at needs --from-traces")
    if at is not None and not 0.0 < at <= 1.0:
        raise _fail(f"--at must be in (0, 1], got {at:g}")
    if from_traces is not None:
        given = [
            flag
            for flag, value in (
                ("--provider", provider),
                ("--policy", policy),
                ("--questions", questions),
                ("--mode", mode),
                ("--budget-usd", budget_usd),
                ("--ledger", ledger),
                ("--batch-id", batch_id),
            )
            if value is not None
        ]
        if given:
            raise _fail(
                f"{', '.join(given)} cannot be combined with --from-traces (the stored run's "
                "decisions are re-issued; no provider is called)"
            )
    if workflow is Workflow.shadow and reset_state_flag:
        raise _fail("--reset-state applies only to --workflow simulated")
    resolved_provider = provider or ProviderName.jev
    claude = (
        None
        if from_traces is not None
        else _resolve_claude(resolved_provider, mode, budget_usd, ledger, batch_id)
    )
    cases, sample = _apply_limit(_load_cases(dataset), limit, sample_seed)
    request = WorkflowRequest(
        workflow=workflow,
        dataset=dataset,
        traces_dir=traces_dir,
        state=DEFAULT_STATE if state is None else state,
        from_traces=from_traces,
        at=at,
        provider=resolved_provider,
        policy=policy or "v0.1",
        concurrency=concurrency,
        questions=questions,
        claude=claude,
        reset_state=reset_state_flag,
    )
    if workflow is Workflow.simulated:
        _run_simulated(request, cases, sample)
    else:
        _run_shadow(request, cases, sample)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q tests/integration/test_cli_workflow.py tests/integration/test_cli.py tests/integration/test_cli_claude.py tests/integration/test_cli_providers.py tests/integration/test_cli_questions.py tests/integration/test_cli_sampling.py`
Expected: PASS (the new file has 19 tests; the ordinary `relay run` tests are unchanged).

- [ ] **Step 5: Try it offline (no paid calls), then full check and commit**

```bash
env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env run --dataset evals/smoke --workflow shadow --from-traces evals/baselines/smoke-v0.1/run_20260925T042324Z_eee114/run_20260925T042324Z_eee114.jsonl --traces-dir /tmp/relay-3c-check --state /tmp/relay-3c-check/none.json | tail -3
# expect "SHADOW RUN run_…: 10 proposals recorded; case state unchanged (verified)." then the
# Traces and Manifest lines (the 10 "SHADOW: Would …; no action was taken." lines come before them)
uv run ruff check --fix . && uv run ruff format . && uv run pytest -q
git add relay/cli.py tests/integration/test_cli_workflow.py
git commit -m "feat: add relay run --workflow simulated|shadow with a verified read-only shadow path" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `--incumbent`: agreement and the promotion check

**Files:**
- Modify: `relay/cli.py`
- Test: `tests/integration/test_cli_shadow_compare.py`

**Interfaces:**
- Consumes: `build_shadow_report` (Task 3); `render_shadow_report` (Task 4); `WorkflowRequest`, `_run_shadow`, `run` (Task 5); `paired_cases` (`relay.evaluation.metrics`); `load_waivers`, `RegressionInputError` (already imported in `relay/cli.py`); `original_label`, `_manifest_hash`, `_read_trace_file` (already in `relay/cli.py`).
- Produces:
  - `WorkflowRequest` gains `incumbent: Path | None = None`, `waivers: Path | None = None`, `max_regressed: int | None = None`, `out: Path | None = None`
  - `_load_incumbent(path: Path, cases: list[PriorAuthCase]) -> list[WorkflowTrace]`
  - `relay run` options `--incumbent`, `--waivers`, `--max-regressed`, `--out` (shadow only, all but `--incumbent` need `--incumbent`)
  - Exit codes: 0 PROMOTE; 4 HOLD

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_cli_shadow_compare.py`:

```python
"""relay run --workflow shadow --incumbent: the unlabelled agreement section and the
evaluation-only promotion check (PROMOTE exit 0, HOLD exit 4). Offline: smoke runs made in tmp,
and the committed gold traces used as frozen inputs. State files live under tmp_path only."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from relay.cli import app
from relay.traces.store import read_traces
from relay.workflow.status import state_digest

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
GOLD = REPO / "evals" / "gold"
GOLD_RUNS = REPO / "evals" / "baselines" / "gold-v0.1"
GOLD_JEV = GOLD_RUNS / "run_20260925T170857Z_b95be9" / "traces.jsonl.gz"
GOLD_CLAUDE = GOLD_RUNS / "run_20260926T011730Z_f1852f" / "traces.jsonl.gz"
EXAMPLE_WAIVER = REPO / "evals" / "regression" / "examples" / "waiver-tmp17.json"
runner = CliRunner()


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--env-file", str(tmp_path / "missing.env"), *map(str, args)])


def workflow(tmp_path, dataset, kind, *args):
    return invoke(
        tmp_path,
        "run",
        "--dataset",
        dataset,
        "--workflow",
        kind,
        "--traces-dir",
        tmp_path / "traces",
        "--state",
        tmp_path / "state" / "case-status.json",
        *args,
    )


def trace_file_of(result) -> Path:
    line = next(x for x in result.output.splitlines() if x.startswith("Traces: "))
    return Path(line.removeprefix("Traces: "))


@pytest.fixture(scope="module")
def smoke_runs(tmp_path_factory):
    root = tmp_path_factory.mktemp("shadow-compare-smoke")
    files = {}
    for provider in ("groundtruth", "rules"):
        result = invoke(
            root,
            "run",
            "--dataset",
            SMOKE,
            "--provider",
            provider,
            "--traces-dir",
            root / provider / "traces",
            "--reports-dir",
            root / provider / "reports",
        )
        assert result.exit_code == 0, result.output
        [files[provider]] = (root / provider / "traces").glob("*.jsonl")
    return files


# ---- smoke: agreement numbers against a hand computation ----


def test_smoke_agreement_matches_a_hand_computation(tmp_path, smoke_runs):
    sim = workflow(tmp_path, SMOKE, "simulated", "--from-traces", smoke_runs["groundtruth"])
    assert sim.exit_code == 0, sim.output
    incumbent_file = trace_file_of(sim)
    digest = state_digest(tmp_path / "state" / "case-status.json")
    result = workflow(
        tmp_path,
        SMOKE,
        "shadow",
        "--from-traces",
        smoke_runs["rules"],
        "--incumbent",
        incumbent_file,
    )
    assert result.exit_code == 0, result.output
    assert state_digest(tmp_path / "state" / "case-status.json") == digest
    before = {t.case_id: t.action.value for t in read_traces(incumbent_file)}
    after = {t.case_id: t.action.value for t in read_traces(trace_file_of(result))}
    agreed = sum(before[c] == after[c] for c in before)
    newly = sorted(c for c in before if after[c] == "AUTO_PROCESS" != before[c])
    stopped = sorted(c for c in before if before[c] == "AUTO_PROCESS" != after[c])
    lines = result.output.splitlines()
    assert any(x.startswith(f"  Action agreement: {agreed}/10 ") for x in lines)
    assert f"  Would newly auto-process ({len(newly)}): {', '.join(newly) or 'none'}" in lines
    assert f"  Would stop auto-processing ({len(stopped)}): {', '.join(stopped) or 'none'}" in lines
    header = "INCUMBENT \\ CANDIDATE"
    row = next(i for i, x in enumerate(lines) if x.strip().startswith(header))
    for offset, action in enumerate(("AUTO_PROCESS", "REQUEST_INFO", "HUMAN_REVIEW"), start=1):
        counts = [
            sum(before[c] == action and after[c] == other for c in before)
            for other in ("AUTO_PROCESS", "REQUEST_INFO", "HUMAN_REVIEW")
        ]
        assert lines[row + offset].split() == [action, *map(str, counts)]
    assert "EVALUATION-ONLY (uses ground truth; not available in a real shadow deployment)" in lines
    assert lines[-1].startswith("PROMOTION CHECK: ")


def test_smoke_hard_coded_agreement(tmp_path, smoke_runs):
    """The same comparison with its numbers pinned, so a silent change in either provider or in
    the agreement arithmetic is caught."""
    sim = workflow(tmp_path, SMOKE, "simulated", "--from-traces", smoke_runs["groundtruth"])
    result = workflow(
        tmp_path,
        SMOKE,
        "shadow",
        "--from-traces",
        smoke_runs["rules"],
        "--incumbent",
        trace_file_of(sim),
    )
    lines = result.output.splitlines()
    assert "  Action agreement: 9/10 (90.0%)  95% CI [55.5%, 99.7%]" in lines
    assert "  Would newly auto-process (0): none" in lines
    assert "  Would stop auto-processing (1): AUTO-03" in lines
    assert (result.exit_code, lines[-1]) == (0, "PROMOTION CHECK: PROMOTE")


# ---- gold: the two README demos ----


def test_gold_claude_at_0_55_shadowing_jev_at_0_89_is_promoted(tmp_path):
    sim = workflow(tmp_path, GOLD, "simulated", "--from-traces", GOLD_JEV, "--at", "0.89")
    assert sim.exit_code == 0, sim.output
    assert "AUTO_APPROVED 29 · INFO_REQUESTED 32 · IN_HUMAN_REVIEW 39" in sim.output
    result = workflow(
        tmp_path,
        GOLD,
        "shadow",
        "--from-traces",
        GOLD_CLAUDE,
        "--at",
        "0.55",
        "--incumbent",
        trace_file_of(sim),
    )
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert "  Action agreement: 96/100 (96.0%)  95% CI [90.1%, 98.9%]" in lines
    assert "  Would newly auto-process (2): GOLD-MIS-17, GOLD-TMP-15" in lines
    assert "  Would stop auto-processing (1): GOLD-TMP-18" in lines
    assert (
        "CHANGES: improved 3 · unchanged 96 · regressed 1 · changed-both-wrong 0 · not identical 100"
        in lines
    )
    assert "STILL UNSAFE (1) — also unsafe in the baseline; not a gate failure" in lines
    assert "NEWLY UNSAFE" not in result.output
    assert lines[-3:] == ["REGRESSION GATE: PASS", "", "PROMOTION CHECK: PROMOTE"]


def test_gold_jev_at_0_89_shadowing_jev_at_0_95_is_held_on_gold_tmp_17(tmp_path):
    sim = workflow(tmp_path, GOLD, "simulated", "--from-traces", GOLD_JEV)
    assert sim.exit_code == 0, sim.output
    incumbent_file = trace_file_of(sim)
    result = workflow(
        tmp_path,
        GOLD,
        "shadow",
        "--from-traces",
        GOLD_JEV,
        "--at",
        "0.89",
        "--incumbent",
        incumbent_file,
    )
    assert result.exit_code == 4, result.output
    lines = result.output.splitlines()
    shadow_file = trace_file_of(result)
    assert (
        "SHADOW: Would auto-process GOLD-TMP-17; no action was taken. (current status: "
        f"IN_HUMAN_REVIEW by {incumbent_file.stem})"
    ) in lines
    assert "NEWLY UNSAFE (1)" in lines
    assert (
        f"      replay: relay replay GOLD-TMP-17 --traces {incumbent_file} --dataset {GOLD} "
        f"--candidate-traces {shadow_file}"
    ) in lines
    assert lines[-1] == (
        "PROMOTION CHECK: HOLD — 1 newly unsafe case(s) without a waiver: GOLD-TMP-17"
    )


def test_an_evaluate_run_can_be_the_incumbent_and_waivers_pass_through(tmp_path):
    base = ["--from-traces", GOLD_JEV, "--at", "0.89", "--incumbent", GOLD_JEV]
    held = workflow(tmp_path, GOLD, "shadow", *base)
    assert held.exit_code == 4, held.output
    assert "INCUMBENT evaluate run_20260925T170857Z_b95be9 · jev q-v0.2" in held.output
    waived = workflow(tmp_path, GOLD, "shadow", *base, "--waivers", EXAMPLE_WAIVER)
    assert waived.exit_code == 0, waived.output
    assert "WAIVED NEWLY UNSAFE (1) — reviewed, not failures" in waived.output
    assert waived.output.splitlines()[-1] == "PROMOTION CHECK: PROMOTE"
    too_many = workflow(
        tmp_path, GOLD, "shadow", *base, "--waivers", EXAMPLE_WAIVER, "--max-regressed", "0"
    )
    assert too_many.exit_code == 4
    assert too_many.output.splitlines()[-1] == (
        "PROMOTION CHECK: HOLD — 1 regressed case(s), more than --max-regressed 0"
    )


def test_out_writes_the_shadow_report(tmp_path):
    out = tmp_path / "report"
    result = workflow(
        tmp_path,
        GOLD,
        "shadow",
        "--from-traces",
        GOLD_JEV,
        "--at",
        "0.89",
        "--incumbent",
        GOLD_JEV,
        "--out",
        out,
    )
    assert result.exit_code == 4, result.output
    assert f"Shadow report: {out / 'shadow.json'}, {out / 'shadow.md'}" in result.output
    report = json.loads((out / "shadow.json").read_text())
    assert (report["decision"], report["exit_code"], report["n"]) == ("HOLD", 4, 100)
    assert report["agreement"]["newly_auto"][:2] == ["GOLD-MIS-19", "GOLD-STR-01"]
    assert report["agreement"]["matrix"]["HUMAN_REVIEW"]["AUTO_PROCESS"] == 11
    assert [e["case_id"] for e in report["promotion"]["newly_unsafe"]] == ["GOLD-TMP-17"]
    markdown = (out / "shadow.md").read_text()
    assert markdown.startswith("Relay shadow comparison — dataset gold-v0.1 · n=100\n")
    assert result.output.endswith(markdown)


# ---- incumbent and flag errors ----


def test_a_shadow_run_cannot_be_the_incumbent(tmp_path, smoke_runs):
    shadow = workflow(tmp_path, SMOKE, "shadow", "--from-traces", smoke_runs["rules"])
    assert shadow.exit_code == 0, shadow.output
    runs_before = sorted((tmp_path / "traces").glob("*.jsonl"))
    result = workflow(
        tmp_path,
        SMOKE,
        "shadow",
        "--from-traces",
        smoke_runs["rules"],
        "--incumbent",
        trace_file_of(shadow),
    )
    assert result.exit_code == 2
    assert "is a shadow run; the incumbent must be a simulated or evaluate run" in result.output
    assert sorted((tmp_path / "traces").glob("*.jsonl")) == runs_before


def test_an_incumbent_on_other_cases_is_refused_before_the_run(tmp_path, smoke_runs):
    result = workflow(
        tmp_path, SMOKE, "shadow", "--from-traces", smoke_runs["rules"], "--incumbent", GOLD_JEV
    )
    assert result.exit_code == 2
    assert f"--incumbent {GOLD_JEV}" in result.output
    assert not (tmp_path / "traces").exists()


@pytest.mark.parametrize(
    "args,message",
    [
        (
            ["--workflow", "simulated", "--from-traces", "{gt}", "--incumbent", "{gt}"],
            "--incumbent applies only to --workflow shadow",
        ),
        (
            ["--workflow", "shadow", "--from-traces", "{gt}", "--out", "o"],
            "--out needs --incumbent",
        ),
        (
            ["--workflow", "shadow", "--from-traces", "{gt}", "--max-regressed", "0"],
            "--max-regressed needs --incumbent",
        ),
        (["--incumbent", "{gt}"], "--incumbent needs --workflow"),
    ],
)
def test_comparison_flag_errors(tmp_path, smoke_runs, args, message):
    args = [a.replace("{gt}", str(smoke_runs["groundtruth"])) for a in args]
    result = invoke(tmp_path, "run", "--dataset", SMOKE, "--traces-dir", tmp_path / "traces", *args)
    assert result.exit_code == 2
    assert message in result.output
    assert not (tmp_path / "traces").exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/integration/test_cli_shadow_compare.py`
Expected: FAIL — `No such option: --incumbent`.

- [ ] **Step 3: Implement**

In `relay/cli.py`, replace:

```python
from relay.evaluation.metrics import EvalError, run_identity, score_run
```

with:

```python
from relay.evaluation.metrics import EvalError, paired_cases, run_identity, score_run
```

In `relay/cli.py`, replace:

```python
    validate_run_config,
)
from relay.evaluation.tracediff import (
```

with:

```python
    validate_run_config,
)
from relay.evaluation.shadow import build_shadow_report
from relay.evaluation.tracediff import (
```

In `relay/cli.py`, replace:

```python
    render_run_table,
    render_trace_diff,
    shadow_line,
```

with:

```python
    render_run_table,
    render_shadow_report,
    render_trace_diff,
    shadow_line,
```

In `relay/cli.py`, replace:

```python
    claude: ClaudeRun | None = None
    reset_state: bool = False
```

with:

```python
    claude: ClaudeRun | None = None
    reset_state: bool = False
    incumbent: Path | None = None
    waivers: Path | None = None
    max_regressed: int | None = None
    out: Path | None = None
```

In `relay/cli.py`, replace:

```python
def _run_shadow(
    request: WorkflowRequest, cases: list[PriorAuthCase], sample: tuple[int, int] | None
) -> None:
```

with:

```python
def _load_incumbent(path: Path, cases: list[PriorAuthCase]) -> list[WorkflowTrace]:
    """The run a shadow candidate is compared with: a simulated or evaluate run covering the same
    cases. Checked before the shadow run starts, so a bad incumbent costs no provider call."""
    traces = _read_trace_file(path)
    if traces and traces[0].mode == "shadow":
        raise _fail(
            f"--incumbent {path} is a shadow run; the incumbent must be a simulated or evaluate run"
        )
    try:
        paired_cases(traces, cases)
    except EvalError as error:
        raise _fail(f"--incumbent {path}: {error}") from error
    return traces


def _run_shadow(
    request: WorkflowRequest, cases: list[PriorAuthCase], sample: tuple[int, int] | None
) -> None:
```

In `relay/cli.py`, replace:

```python
        store = load_store(request.state)
    except StatusStoreError as error:
        raise _fail(str(error)) from error
    manifest, traces = _workflow_traces(request, cases, sample)
    after = state_digest(request.state)
```

with:

```python
        store = load_store(request.state)
    except StatusStoreError as error:
        raise _fail(str(error)) from error
    incumbent = None if request.incumbent is None else _load_incumbent(request.incumbent, cases)
    try:
        waivers = [] if request.waivers is None else load_waivers(request.waivers)
    except RegressionInputError as error:
        raise _fail(str(error)) from error
    manifest, traces = _workflow_traces(request, cases, sample)
    after = state_digest(request.state)
```

In `relay/cli.py`, replace:

```python
    typer.echo(shadow_trailer(manifest.run_id, len(traces)))
    for line in _run_paths(manifest):
        typer.echo(line)
```

with:

```python
    typer.echo(shadow_trailer(manifest.run_id, len(traces)))
    for line in _run_paths(manifest):
        typer.echo(line)
    if incumbent is None:
        return
    try:
        report = build_shadow_report(
            incumbent,
            traces,
            cases,
            incumbent_label=f"{incumbent[0].mode} {original_label(incumbent[0])}",
            candidate_label=f"shadow {original_label(traces[0])}",
            waivers=waivers,
            max_regressed=request.max_regressed,
            dataset_hash=_manifest_hash(request.dataset, cases),
            replay_command=lambda case_id: (
                f"relay replay {case_id} --traces {request.incumbent} --dataset "
                f"{request.dataset} --candidate-traces {manifest.trace_file}"
            ),
        )
    except EvalError as error:
        raise _fail(str(error)) from error
    rendered = render_shadow_report(report)
    if request.out is not None:
        request.out.mkdir(parents=True, exist_ok=True)
        (request.out / "shadow.json").write_text(
            report.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        (request.out / "shadow.md").write_text(rendered + "\n", encoding="utf-8")
        typer.echo(f"Shadow report: {request.out / 'shadow.json'}, {request.out / 'shadow.md'}")
    typer.echo("")
    typer.echo(rendered)
    if report.exit_code:
        raise typer.Exit(code=report.exit_code)
```

In `relay/cli.py`, replace:

```python
            "timestamp> and start from RECEIVED.",
        ),
    ] = False,
) -> None:
```

with:

```python
            "timestamp> and start from RECEIVED.",
        ),
    ] = False,
    incumbent: Annotated[
        Path | None,
        typer.Option(
            exists=True,
            dir_okay=False,
            help="--workflow shadow only: compare with this simulated or evaluate run.",
        ),
    ] = None,
    waivers: Annotated[
        Path | None,
        typer.Option(
            exists=True, dir_okay=False, help="With --incumbent: waivers for the promotion check."
        ),
    ] = None,
    max_regressed: Annotated[
        int | None,
        typer.Option(min=0, help="With --incumbent: HOLD when more cases than this regress."),
    ] = None,
    out: Annotated[
        Path | None, typer.Option(help="With --incumbent: write shadow.json and shadow.md here.")
    ] = None,
) -> None:
```

In `relay/cli.py`, replace:

```python
    With --workflow: simulated (the incumbent's actions change simulated case status) or shadow
    (a candidate's proposals are recorded, never applied). Exit codes: 0 ok; 2 usage/input
    error; 3 SHADOW VIOLATION.
```

with:

```python
    With --workflow: simulated (the incumbent's actions change simulated case status) or shadow
    (a candidate's proposals are recorded, never applied, optionally compared with --incumbent).
    Exit codes: 0 ok / PROMOTE; 2 usage/input error; 3 SHADOW VIOLATION; 4 HOLD.
```

In `relay/cli.py`, replace:

```python
                ("--reset-state", reset_state_flag or None),
            )
            if value is not None
        ]
        if given:
            raise _fail(f"{', '.join(given)} needs --workflow simulated or --workflow shadow")
```

with:

```python
                ("--reset-state", reset_state_flag or None),
                ("--incumbent", incumbent),
                ("--waivers", waivers),
                ("--max-regressed", max_regressed),
                ("--out", out),
            )
            if value is not None
        ]
        if given:
            raise _fail(f"{', '.join(given)} needs --workflow simulated or --workflow shadow")
```

In `relay/cli.py`, replace:

```python
    if workflow is Workflow.shadow and reset_state_flag:
        raise _fail("--reset-state applies only to --workflow simulated")
```

with:

```python
    shadow_only = [
        flag
        for flag, value in (
            ("--incumbent", incumbent),
            ("--waivers", waivers),
            ("--max-regressed", max_regressed),
            ("--out", out),
        )
        if value is not None
    ]
    if workflow is Workflow.simulated and shadow_only:
        raise _fail(f"{', '.join(shadow_only)} applies only to --workflow shadow")
    if workflow is Workflow.shadow:
        if reset_state_flag:
            raise _fail("--reset-state applies only to --workflow simulated")
        if incumbent is None and shadow_only:
            raise _fail(f"{', '.join(shadow_only)} needs --incumbent")
```

In `relay/cli.py`, replace:

```python
        reset_state=reset_state_flag,
    )
```

with:

```python
        reset_state=reset_state_flag,
        incumbent=incumbent,
        waivers=waivers,
        max_regressed=max_regressed,
        out=out,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q tests/integration/test_cli_shadow_compare.py tests/integration/test_cli_workflow.py`
Expected: PASS (12 + 19 tests).

- [ ] **Step 5: Full check, guards, commit**

```bash
uv run ruff check --fix . && uv run ruff format . && uv run pytest -q
env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env regression --config evals/regression/gates.json --strict-generated > /dev/null; echo "exit $?"   # expect exit 0
git status --short evals/   # expect no output
git add relay/cli.py tests/integration/test_cli_shadow_compare.py
git commit -m "feat: compare a shadow run with the incumbent: agreement and PROMOTE/HOLD" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: README "Shadow mode" with real output, and final verification

**Files:**
- Modify: `README.md`
- Uses (not committed): a scratch directory for captured output and the section generator

**Interfaces:**
- Consumes: the finished `relay run --workflow …` (Tasks 1–6).

Shell variables do not survive between separate tool calls, so every block below that uses the
capture directory starts with `D=/tmp/relay-3c-demo` (Step 2 creates it; its files are
overwritten on a re-run).

- [ ] **Step 1: Make sure the demo state files and default trace dir are clean**

`state/promote-demo.json` and `state/hold-demo.json` must not exist (a leftover would make the simulated run exit 2 with a conflict). If either exists, move it aside rather than deleting it:

```bash
for f in state/promote-demo.json state/hold-demo.json; do [ -e "$f" ] && mv "$f" "$f.old-$(date -u +%Y%m%dT%H%M%SZ)"; done; true
```

- [ ] **Step 2: Run the four demo commands and capture their output**

Run exactly these commands from the repository root (the README shows them in this form, and the generator in Step 3 rebuilds the displayed commands with the same flags in the same order):

```bash
D=/tmp/relay-3c-demo; mkdir -p "$D"
J=evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz
C=evals/baselines/gold-v0.1/run_20260926T011730Z_f1852f/traces.jsonl.gz
R() { env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env "$@"; }
R run --dataset evals/gold --workflow simulated --state state/promote-demo.json --from-traces $J --at 0.89 > "$D/1.txt"; echo "exit $?"   # expect 0
INC1=$(grep '^Traces: ' "$D/1.txt" | cut -d' ' -f2)
R run --dataset evals/gold --workflow shadow --state state/promote-demo.json --from-traces $C --at 0.55 --incumbent "$INC1" > "$D/2.txt"; echo "exit $?"   # expect 0
R run --dataset evals/gold --workflow simulated --state state/hold-demo.json --from-traces $J > "$D/3.txt"; echo "exit $?"   # expect 0
INC2=$(grep '^Traces: ' "$D/3.txt" | cut -d' ' -f2)
R run --dataset evals/gold --workflow shadow --state state/hold-demo.json --from-traces $J --at 0.89 --incumbent "$INC2" > "$D/4.txt"; echo "exit $?"   # expect 4
tail -1 "$D/2.txt"; tail -1 "$D/4.txt"
```

Expected: exits 0, 0, 0, 4; the last two lines are `PROMOTION CHECK: PROMOTE` and `PROMOTION CHECK: HOLD — 1 newly unsafe case(s) without a waiver: GOLD-TMP-17`. Check these reference values too (only run ids and trace paths may differ from the planning run):

- `1.txt`: `… 100 transitions applied — AUTO_APPROVED 29 · INFO_REQUESTED 32 · IN_HUMAN_REVIEW 39`
- `2.txt`: `  Action agreement: 96/100 (96.0%)  95% CI [90.1%, 98.9%]`, `  Would newly auto-process (2): GOLD-MIS-17, GOLD-TMP-15`, `  Would stop auto-processing (1): GOLD-TMP-18`, `STILL UNSAFE (1) — also unsafe in the baseline; not a gate failure`, no `NEWLY UNSAFE`
- `3.txt`: `… 100 transitions applied — AUTO_APPROVED 18 · INFO_REQUESTED 32 · IN_HUMAN_REVIEW 50`
- `4.txt`: `  Action agreement: 89/100 (89.0%)  95% CI [81.2%, 94.4%]`, `NEWLY UNSAFE (1)` naming `GOLD-TMP-17`

If any outcome differs, stop and report it; do not edit the README to match.

- [ ] **Step 3: Generate the README section from the captured output**

Save this generator as `/tmp/relay-3c-demo/readme_section.py` (a scratch tool; do not commit it):

```python
import pathlib, re, sys
D = pathlib.Path(sys.argv[1])  # directory with 1.txt..4.txt
J = "evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz"
C = "evals/baselines/gold-v0.1/run_20260926T011730Z_f1852f/traces.jsonl.gz"
PFX = "$ env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env run \\"

def lines(n): return (D / f"{n}.txt").read_text(encoding="utf-8").splitlines()
def traces_of(n): return next(x for x in lines(n) if x.startswith("Traces: ")).removeprefix("Traces: ")

def trim(out, keep, kind):
    """Keep per-case lines whose 0-based index is in `keep`; replace runs of dropped ones."""
    per_case = [i for i, x in enumerate(out) if x.startswith(kind + ": ")]
    result, dropped = [], 0
    for i, x in enumerate(out):
        if i in per_case and per_case.index(i) not in keep:
            dropped += 1
            continue
        if dropped:
            result.append(f"[… {dropped} more {kind} lines, one per case …]")
            dropped = 0
        result.append(x)
    return result

def cmd(*args):
    parts = [PFX]
    for i, a in enumerate(args):
        parts.append("    " + a + (" \\" if i < len(args) - 1 else ""))
    return parts

inc1, inc2 = traces_of(1), traces_of(3)
tmp17 = next(i for i, x in enumerate(l for l in lines(4) if l.startswith("SHADOW: ")) if "GOLD-TMP-17" in x)
block1 = cmd("--dataset evals/gold --workflow simulated --state state/promote-demo.json",
             f"--from-traces {J} --at 0.89") + trim(lines(1), {0, 1, 2}, "SIMULATED")
block2 = cmd("--dataset evals/gold --workflow shadow --state state/promote-demo.json",
             f"--from-traces {C} --at 0.55",
             f"--incumbent {inc1}") + trim(lines(2), {0, 1, 2}, "SHADOW")
block3a = cmd("--dataset evals/gold --workflow simulated --state state/hold-demo.json",
              f"--from-traces {J}") + trim(lines(3), {0, 1, 2}, "SIMULATED")
block3b = cmd("--dataset evals/gold --workflow shadow --state state/hold-demo.json",
              f"--from-traces {J} --at 0.89",
              f"--incumbent {inc2}") + trim(lines(4), {0, 1, 2, tmp17}, "SHADOW")
def fence(b): return "```text\n" + "\n".join(b) + "\n```"
TEMPLATE = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")
print(TEMPLATE.replace("@@BLOCK1@@", fence(block1)).replace("@@BLOCK2@@", fence(block2))
      .replace("@@BLOCK3@@", fence(block3a + [""] + block3b)), end="")
```

Save this template as `/tmp/relay-3c-demo/template.md` (the `@@BLOCKn@@` markers are filled by the generator):

````markdown
## Shadow mode

Shadow mode models a safe, progressive rollout. It does not pretend Relay has real production
traffic: every case is synthetic, and every status change is simulated in a local file. The
rollout ladder has three rungs:

1. **The simulated live system (the incumbent).** `relay run --workflow simulated` runs the
   accepted configuration (provider, question set, policy and thresholds). Each action becomes a
   simulated case-status transition in a small state file (default `state/case-status.json`,
   git-ignored): `RECEIVED` → `AUTO_APPROVED` (AUTO_PROCESS), `INFO_REQUESTED` (REQUEST_INFO) or
   `IN_HUMAN_REVIEW` (HUMAN_REVIEW).
2. **The shadow candidate.** `relay run --workflow shadow` runs a new configuration on the same
   cases. It records each proposed action as a `mode: "shadow"` trace and prints
   `SHADOW: Would auto-process CASE-ID; no action was taken.` The state file is only read. The
   command hashes it before and after the run, and prints `case state unchanged (verified)` only
   when the two hashes match. If they differ, it prints `SHADOW VIOLATION` and exits 3.
3. **The promotion check.** With `--incumbent TRACES`, the shadow run is compared with the
   incumbent. The agreement section uses no ground truth, so it is what a real shadow deployment
   could see: the action agreement rate, an incumbent × candidate action matrix, and the cases the
   candidate would newly auto-process or would stop auto-processing. The promotion check below it
   is labelled EVALUATION-ONLY. It is the regression gate from "Regression gate" above, with the
   incumbent as its baseline. Gate PASS prints `PROMOTION CHECK: PROMOTE` (exit 0), and gate FAIL
   prints `PROMOTION CHECK: HOLD — <failures>` (exit 4). STILL UNSAFE cases are listed but never
   cause a HOLD.

The guarantee is enforced in code, not only in the CLI. The status store's only writer refuses a
shadow trace with `ShadowWriteError` before it touches the file, and a test checks the file stays
byte-identical.

The handoff's `relay run --dataset evals/gold --mode shadow` is `relay run --dataset evals/gold
--workflow shadow` here, because `--mode` already selects Claude's sync or batch mode. Two
details follow from that choice:

- **Offline runs.** `--from-traces FILE [--at X]` re-issues a stored run's decisions as a new run
  in the requested mode, with `replay_of` set on every trace and `source_run_id` in the manifest.
  No provider is called. Without `--from-traces`, the run calls the provider with every existing
  guard: the Jev key check, and the Claude budget check and spend ledger.
- **Conflicts.** A second simulated run over cases the state file already moved is refused with
  exit 2. `--reset-state` first archives the file to `<state>.bak-<UTC timestamp>`.

`--waivers` and `--max-regressed` pass through to the promotion check, and `--out DIR` writes
`shadow.json` and `shadow.md`. The shadow traces and manifest go to `--traces-dir` (default
`traces/`), like any run.

The demos below use the committed gold traces only as frozen inputs, and nothing is tuned on
them. The per-case lines are trimmed (`[… N more … lines …]`); everything else is the commands'
real output. First, the incumbent: Jev's gold decisions at its dev-selected threshold, 0.89.

@@BLOCK1@@

Then Claude at its own dev-selected threshold, 0.55, shadows it. This is the `gold-jev-vs-claude`
gate as a rollout: 96/100 actions agree, and the candidate is not an unsafe regression, so the
check says PROMOTE. Both configurations automate `GOLD-TMP-17` unsafely (see "Regression gate"
above), so it appears under STILL UNSAFE and not as a failure.

@@BLOCK2@@

The second demo is the FAIL demo from "Regression gate" in rollout terms. The incumbent is Jev
at the recorded 0.95, and the candidate is the same decisions at 0.89. The shadow line for
`GOLD-TMP-17` shows the candidate would auto-process a case the incumbent sent to human review,
and the promotion check holds the rollout. The command exits 4.

@@BLOCK3@@
````

Then generate:

```bash
D=/tmp/relay-3c-demo
python3 "$D/readme_section.py" "$D" "$D/template.md" > "$D/section.md"
grep -c '^```text$' "$D/section.md"   # expect 3
```

- [ ] **Step 4: Insert the section and update the command list and project docs**

1. Insert the contents of `"$D/section.md"` into `README.md` immediately before the line `## Limitations`, followed by one blank line (so there is exactly one blank line between the section's last ```` ``` ```` and `## Limitations`). For example:

```bash
D=/tmp/relay-3c-demo
python3 - "$D/section.md" <<'EOF'
import pathlib, sys
readme = pathlib.Path("README.md")
text = readme.read_text(encoding="utf-8")
section = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
assert text.count("\n## Limitations\n") == 1 and "## Shadow mode" not in text
readme.write_text(text.replace("\n## Limitations\n", "\n" + section + "\n## Limitations\n"), encoding="utf-8")
EOF
```

2. In `README.md`, replace:

```text
uv run relay regression --config evals/regression/gates.json                    # every committed gate, as CI runs them
```

with:

```text
uv run relay regression --config evals/regression/gates.json                    # every committed gate, as CI runs them
uv run relay run --dataset <dir> --workflow simulated --from-traces <file> [--at X]    # the incumbent: actions become simulated case status (see "Shadow mode")
uv run relay run --dataset <dir> --workflow shadow --from-traces <file> --incumbent <file>   # a shadow candidate: proposals recorded, never applied; PROMOTE/HOLD
```

3. In `README.md`, replace:

```text
- Actions are simulated. Relay never submits anything anywhere.
```

with:

```text
- Actions are simulated. Relay never submits anything anywhere. Shadow mode's agreement section
  is the only part a real shadow deployment could compute; its promotion check uses ground truth,
  which a real deployment would not have (see "Shadow mode" above).
```

4. In `README.md`, replace:

```text
- [Phase 3A implementation plan](docs/superpowers/plans/2026-09-26-phase3a-replay.md)
```

with:

```text
- [Phase 3A implementation plan](docs/superpowers/plans/2026-09-26-phase3a-replay.md)
- [Phase 3B regression gate design](docs/superpowers/specs/2026-09-26-phase3b-regression-gate-design.md)
- [Phase 3B implementation plan](docs/superpowers/plans/2026-09-26-phase3b-regression-gate.md)
- [Phase 3C shadow mode design](docs/superpowers/specs/2026-09-26-phase3c-shadow-mode-design.md)
- [Phase 3C implementation plan](docs/superpowers/plans/2026-09-26-phase3c-shadow-mode.md)
```

(All four files exist; the 3B pair was missing from the list.)

- [ ] **Step 5: Verify the README against the captured output**

Every line inside the three new `text` blocks, except the command lines (`$ …` and their indented `--…` continuations) and the `[… N more … lines, one per case …]` markers, must appear in the capture files:

```bash
D=/tmp/relay-3c-demo
python3 - "$D" <<'EOF'
import pathlib, re, sys
d = pathlib.Path(sys.argv[1])
captured = set()
for n in range(1, 5):
    captured |= set((d / f"{n}.txt").read_text(encoding="utf-8").splitlines())
text = pathlib.Path("README.md").read_text(encoding="utf-8")
section = text[text.index("## Shadow mode"):text.index("## Limitations")]
blocks = re.findall(r"```text\n(.*?)\n```", section, re.S)
assert len(blocks) == 3, len(blocks)
bad = [
    line for block in blocks for line in block.splitlines()
    if line and not line.startswith(("$ ", "    --", "[… ")) and line not in captured
]
print("OK" if not bad else bad)
EOF
```

Expected: `OK`.

- [ ] **Step 6: Final verification**

```bash
D=/tmp/relay-3c-demo
uv run ruff check --fix . && uv run ruff format . && uv run pytest -q
env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env regression --config evals/regression/gates.json --strict-generated > "$D/gates.txt"; echo "exit $?"   # expect exit 0
tail -11 "$D/gates.txt"   # expect 9 PASS rows
git status --short   # expect only README.md modified; state/ and traces/ are ignored
git check-ignore -v state/promote-demo.json   # expect the /state/ rule
git diff --stat HEAD -- evals/ results/   # expect no output
```

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: add the Shadow mode section with real PROMOTE and HOLD demos" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Self-review (done while planning)

- **Spec coverage.** S1 → Tasks 5–6 (`--workflow` on the existing `run`; `--state` default; `.gitignore` in Task 2). S2 → Task 2 (statuses, JSON shape, atomic write, `ShadowWriteError`, idempotence, `ConflictError`, `--reset-state` archive). S3 → Task 1 (trace/manifest mode, `source_run_id`, 3B writer switched) and Task 5 (`--from-traces`/`--at` via `replay_run`, `replay_of` set; the live path keeps every guard). S4 → Tasks 4–5. S5 → Tasks 4–5 (exact handoff strings, current-status suffix, verified trailer, exit 3). S6 → Tasks 3, 4, 6 (agreement via `diff_runs(labelled=False)`, matrix, newly/stopped lists, EVALUATION-ONLY promotion check via `build_result`, STILL UNSAFE as a warning, `--waivers`, exit 0/4/2). S7 → Task 6 (`shadow.json`, `shadow.md`; traces under `--traces-dir`). S8 → Task 7 (both demos from committed gold traces, real output). §4 Testing → every listed test exists (Tasks 2, 5, 6; fakes-only live path in Task 5; backward compatibility in Task 1). §5 → Task 7 Step 6.
- **Type consistency.** `apply_transitions(path, traces)` / `apply_transition(path, trace)`, `shadow_line(trace, current)`, `simulated_line(transition, case_id)`, `build_shadow_report(..., replay_command=...)` and the `WorkflowRequest` fields are used with the same names and types in every task.
