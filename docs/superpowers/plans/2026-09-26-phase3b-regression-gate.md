# Phase 3B: Regression Gate and CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a run-level `relay regression` gate that fails loudly on unreviewed unsafe automation, run the committed offline gates in GitHub Actions CI, and add `relay budget show/release` for spend-ledger maintenance.

**Architecture:** First, four foundation fixes from the 3A final review land in `relay/evaluation/tracediff.py`: F1 thresholds follow the target policy version, F2 `diff_case`/`diff_runs`, F3 unlabelled diffs, and F4 `crossed_gated`. Then three new modules. `relay/evaluation/intervals.py` computes Clopper-Pearson intervals. `relay/evaluation/regression.py` holds the pure result model, waivers and verdict. `relay/evaluation/regression_run.py` does the I/O: it loads the runs, builds the candidate, pairs sampled runs and writes artifacts. `relay/reporting.py` renders the result, and `relay/cli.py` exposes `relay regression` (single-run and `--config` mode) and `relay budget`. CI runs lint, the tests, dataset regeneration with `--verify`, and `relay regression --config evals/regression/gates.json`.

**Tech Stack:** Python 3.12, uv, Pydantic v2, Typer, pytest (`asyncio_mode=auto`, `-m 'not live'` by default), ruff, and PyYAML (a new dev dependency, used only by the CI workflow test).

## Global Constraints

- Synthetic data only.
- Never open `.env` (read, cat, grep or edit it). No task needs it.
- No paid API calls anywhere. Every command in this plan is offline. Run offline CLI commands as `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env ...`.
- The real `results/claude-spend.json` is never read or written by tests or by this work. Budget tests use tmp ledgers only.
- Committed artifacts under `evals/baselines/`, `evals/gold/`, `evals/smoke/` and `evals/generated/manifests/` must not change. Never regenerate them.
- Stage files by explicit path. Never `git add -A` or `git add .`.
- Each commit uses two `-m` arguments. The second is exactly `-m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.
- Don't push.
- At the end of every task, `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q` must pass.
- Branch: `feat/phase3` (already checked out). Work from the repository root `/Users/joelbrook/Desktop/Code/Relay`.

## Verified facts this plan relies on (checked while planning, on a scratch copy)

- **Engine drift.** Every committed baseline run reproduces with 0 non-identical cases under today's engine: the 4 gold runs, the 3 holdout runs (including the 150-case Claude sample, seed 7), the 4 dev runs, and the smoke Jev run `evals/baselines/smoke-v0.1/run_20260925T042324Z_eee114`.
- **The smoke baseline.** It is jev, stored as an uncompressed `.jsonl`, and predates 2B (no `policy_text_hash`). Every case content hash still matches `evals/smoke`, and there is no dataset manifest for smoke. That is why `smoke-reproduce-jev` is included.
- **The gold demo.** Baseline Jev at 0.95, candidate `--candidate-at 0.89`: FAIL, exit 4, newly unsafe GOLD-TMP-17 only. The change counts are improved 10, unchanged 89, regressed 1.
- **`gold-jev-vs-claude`.** Jev re-decided at 0.89 against Claude re-decided at 0.55: PASS. There are 4 action differences: improved GOLD-MIS-17, GOLD-TMP-15 and GOLD-TRK-19, regressed GOLD-TMP-18. None is newly unsafe.
- **The threshold version string (`v0.1+at0.89`) causes no artifact churn.** The overridden `Thresholds` in frontier/compare/report are transient. They are only passed to `determine_action`, whose output never contains the version, and they are never serialized. Regenerating the three gold report bundles at their `--at` values (Jev 0.89, rules 0.99, Claude 0.55) gave byte-identical files. No test byte-compares regenerated output.
- **CI regeneration timing** (local, Apple Silicon):

  | Step | Time |
  |---|---|
  | `generate` dev (400) | 0.6 s |
  | `generate` holdout (1000) | 0.8 s |
  | `--verify` dev | 0.7 s |
  | `--verify` holdout | 1.2 s |
  | Total | about 3.3 s |

  The full workflow's regenerate step took 4.7 s in a fresh clone, and the gates step took 2.0 s. Both are far under the 3-minute concern. `relay generate` refuses to overwrite an existing manifest, so CI writes the regenerated manifests to `$RUNNER_TEMP/manifests` and then `--verify`s against the committed ones.

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `relay/workflow/thresholds.py` | modify | `override_auto_process` (one helper for every `--at` override) |
| `relay/evaluation/tracediff.py` | modify | F1 `replay_thresholds`; F2 `diff_case`, `diff_runs`; F3 optional expected; F4 `crossed_gated`, `gated_only` |
| `relay/evaluation/frontier.py`, `relay/evaluation/compare.py` | modify | use `override_auto_process` |
| `relay/evaluation/intervals.py` | create | pure-Python Clopper-Pearson |
| `relay/evaluation/regression.py` | create | `Waiver`, `RegressionResult`, `evaluate_gate`, `build_result` (pure) |
| `relay/evaluation/regression_run.py` | create | `CandidateSpec`, `GateSpec`, `RegressionRequest`, `run_regression`, `write_outputs`, gates/waiver loading |
| `relay/reporting.py` | modify | unlabelled and gated rendering for replay; `render_regression`, `render_gate_summary`, `GateRow`, `render_ledger` |
| `relay/cli.py` | modify | `replay` uses `replay_thresholds`/`diff_case`; new `regression` command; new `budget show/release` |
| `relay/evaluation/budget.py` | modify | `SpendEntry.note`, `LedgerRefusal`, `ledger_totals`, `release`, `backup_ledger` |
| `evals/regression/gates.json` | create | committed gates |
| `evals/regression/examples/waiver-tmp17.json` | create | example waiver (README demo only) |
| `.github/workflows/ci.yml` | create | CI |
| `pyproject.toml`, `uv.lock` | modify | `pyyaml` dev dependency |
| `README.md` | modify | CI badge, commands, budget recovery, Replay output refresh, "Regression gate" section |
| tests (see each task) | create/modify | |

## Resolved ambiguities (decisions this plan makes)

1. **Where `v0.1+at<X>` applies.** It applies at every call site the spec names: replay, replay_run, compare, frontier, and report (through frontier). This was verified to change no committed artifact (see above), so there is no need to limit it to the replay/regression paths.
2. **F1 touches two 3A tests beyond the label suffix.**
   - `tests/unit/test_replay.py::test_replay_run_loads_the_named_policy` monkeypatches a v0.2 policy. Under F1, that policy now needs v0.2 thresholds registered, so the test gains one `monkeypatch.setitem` line.
   - `tests/unit/test_tracediff.py::test_labels` must pass the new `thresholds` argument to `policy_replay_label`.

   Everything else is the label suffix only.
3. **The label format.** `policy replay: STORED DECISIONS under policy immunara-v0.1 (v0.1), auto_process=0.89, thresholds v0.1+at0.89 — judgments were made against the original policy's questions`. Without `--at`, it reads `…(v0.1), thresholds v0.1 — …`.
4. **The F3 API.** In `diff_traces`, both expected actions `None` means unlabelled; exactly one `None` is a `ValueError`. `diff_case` and `diff_runs` take `labelled: bool = True`.
5. **F4 rendering.** A reported-only crossing renders as `(name)`, and a legend line `  ((name) = reported-only comparison: no engine gate acts on it)` appears only when one is present.
6. **Waiver scoping.** A waiver applies when `gate == "*"` or `gate` equals the gate's name. A command-line run without `--config` has no gate name, so only `*` waivers apply there. Waivers for other gates are neither used nor reported as stale. The example waiver uses `"*"`.
7. **Replayed artifacts beyond the spec's policy-replay candidate.**
   - `--out` also writes `candidate.*` for `--candidate-traces … --candidate-at`, and `baseline.*` after `--baseline-at`, so that the printed `relay replay` commands can point at them.
   - Without `--out`, such cases print `replay: re-run with --out DIR for a replayable command`.
   - Reproduce candidates are not written.
8. **Config mode.**
   - Paths are relative to the working directory (run from the repository root).
   - `--out DIR` writes `DIR/<gate>/…` plus `DIR/summary.md`.
   - A gate whose inputs are bad becomes an `ERROR` row (exit 2), and the remaining gates still run.
   - `--json` and all single-run flags are rejected together with `--config`. `--gate` without `--config` is exit 2.
   - The skip note reads `SKIPPED (dataset not generated; run relay generate to create <dataset>)`.
   - Candidate keys are `traces`, `policy`, `latest_policy`, `at` and `reproduce` (`latest_policy` was added to match the CLI).
9. **PyYAML.** The spec's "YAML parse test" needs a parser, so PyYAML is added as a dev dependency (`uv add --dev pyyaml`, which needs network once).
10. **CI keys.** `TYPESAFE_API_KEY` and `ANTHROPIC_API_KEY` are never set in the workflow; they are not set to empty strings either. The test asserts there are no `env:` blocks and no `secrets.` reference.
11. **Metric output.** The Δ column is in percentage points. The terminal does not list IMPROVED cases (the JSON does), following G7's section order. The REGRESSED list includes newly unsafe cases whose baseline was correct.
12. **Budget.**
    - `--ledger` defaults to `results/claude-spend.json`, like every other command, but tests always pass a tmp ledger.
    - `release` requires `--yes`. A missing ledger file is exit 2. `show` on a missing file prints `no entries`.
    - The note reads `released by hand at $0 (was reserved at $X): <reason>`.
13. **`gold-jev-vs-claude` sets no `max_regressed`.** It has 1 legitimate regression (GOLD-TMP-18), and the spec gates it on newly unsafe cases only.
14. **README Replay outputs are refreshed** in the final task, because F1 and F4 change their CANDIDATE label and CROSSED column.

---

### Task 1: F1: thresholds follow the target policy version; `override_auto_process`

**Files:**
- Modify: `relay/workflow/thresholds.py` (append)
- Modify: `relay/evaluation/tracediff.py` (imports, `policy_replay_label`, new `replay_thresholds`, `replay_run`)
- Modify: `relay/evaluation/frontier.py:53`, `relay/evaluation/compare.py:71`
- Modify: `relay/cli.py` (`replay` command, policy-replay branch, around line 1224)
- Create: `tests/unit/test_thresholds.py`
- Modify: `tests/unit/test_replay.py`, `tests/unit/test_tracediff.py`, `tests/integration/test_cli_replay.py`

**Interfaces:**
- Produces:
  - `relay.workflow.thresholds.override_auto_process(thresholds: Thresholds, auto_process: float) -> Thresholds`, with version `"<base>+at<X:g>"`
  - `relay.evaluation.tracediff.replay_thresholds(trace: WorkflowTrace, target: AuthorizationPolicy, auto_process: float | None) -> Thresholds`, which raises `EvalError` for an unknown thresholds version
  - `policy_replay_label(policy: AuthorizationPolicy, thresholds: Thresholds, auto_process: float | None) -> str`
  - `replay_run(...)` now raises `EvalError` (not `KeyError`) for an unknown policy id

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_thresholds.py`:

```python
"""override_auto_process: one helper for every --at style override (F1 / 3A Minor 2)."""

from relay.workflow.thresholds import THRESHOLDS_V0_1, override_auto_process


def test_the_override_replaces_auto_process_and_records_it_in_the_version():
    overridden = override_auto_process(THRESHOLDS_V0_1, 0.89)
    assert overridden.auto_process == 0.89
    assert overridden.version == "v0.1+at0.89"
    assert overridden.model_dump(exclude={"auto_process", "version"}) == (
        THRESHOLDS_V0_1.model_dump(exclude={"auto_process", "version"})
    )
    assert THRESHOLDS_V0_1.version == "v0.1" and THRESHOLDS_V0_1.auto_process == 0.95


def test_a_second_override_replaces_the_first_rather_than_stacking():
    twice = override_auto_process(override_auto_process(THRESHOLDS_V0_1, 0.89), 0.9)
    assert twice.version == "v0.1+at0.9"
    assert twice.auto_process == 0.9


def test_an_override_to_the_same_value_is_still_labelled():
    assert override_auto_process(THRESHOLDS_V0_1, 0.95).version == "v0.1+at0.95"
```

In `tests/unit/test_replay.py`, replace the import block and constants at the top of the file (everything from `import pytest` down to the `NOW = …` line) with:

```python
import pytest

import relay.cases.policies as policies_module
import relay.evaluation.tracediff as tracediff
import relay.workflow.thresholds as thresholds_module
from relay.cases.policies import load_policy
from relay.evaluation.metrics import EvalError
from relay.evaluation.runner import policy_text_hash
from relay.evaluation.tracediff import replay_run, replay_thresholds, replay_trace
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1, override_auto_process
from tests.factories import make_bundle, make_case, make_trace

POLICY = load_policy("immunara-v0.1")
POLICY_V2 = POLICY.model_copy(update={"id": "immunara-v0.2", "version": "v0.2", "text": "v2"})
NOW = datetime(2026, 9, 26, 12, tzinfo=UTC)
THRESHOLDS_V2 = THRESHOLDS_V0_1.model_copy(update={"version": "v0.2", "auto_process": 0.9})
```

In the same file, in `test_replay_run_loads_the_named_policy`, insert these two lines as the first lines of the function body, before `loaded = []`:

```python
    # F1: a v0.2 target brings v0.2 thresholds, so they must be registered for this replay.
    monkeypatch.setitem(thresholds_module._BY_VERSION, "v0.2", THRESHOLDS_V2)
```

Append to the end of `tests/unit/test_replay.py`:

```python


# ---- F1: thresholds follow the target policy version ----


def register_v0_2(monkeypatch, *, with_thresholds: bool = True):
    """Register a second policy version (reusing the v0.1 text file) and, optionally, its
    thresholds, for the length of one test."""
    spec = dict(policies_module._POLICIES["immunara-v0.1"], version="v0.2")
    monkeypatch.setitem(policies_module._POLICIES, "immunara-v0.2", spec)
    if with_thresholds:
        monkeypatch.setitem(thresholds_module._BY_VERSION, "v0.2", THRESHOLDS_V2)


def test_same_version_keeps_the_traces_own_thresholds_even_when_overridden():
    case = make_case("T-01")
    trace = make_trace(case)
    assert replay_thresholds(trace, POLICY, None) is trace.thresholds
    earlier = trace.model_copy(update={"thresholds": override_auto_process(THRESHOLDS_V0_1, 0.9)})
    assert replay_thresholds(earlier, POLICY, None).version == "v0.1+at0.9"
    assert replay_thresholds(earlier, POLICY, 0.8).version == "v0.1+at0.8"


def test_another_version_brings_its_own_thresholds_then_the_override(monkeypatch):
    register_v0_2(monkeypatch)
    trace = make_trace(make_case("T-01"))
    v2 = load_policy("immunara-v0.2")
    assert replay_thresholds(trace, v2, None) == THRESHOLDS_V2
    at = replay_thresholds(trace, v2, 0.85)
    assert (at.version, at.auto_process) == ("v0.2+at0.85", 0.85)


def test_another_version_without_thresholds_is_an_eval_error(monkeypatch):
    register_v0_2(monkeypatch, with_thresholds=False)
    trace = make_trace(make_case("T-01"))
    with pytest.raises(EvalError, match="unknown thresholds version 'v0.2'"):
        replay_thresholds(trace, load_policy("immunara-v0.2"), None)


def test_replay_run_onto_another_version_uses_that_versions_thresholds(monkeypatch):
    register_v0_2(monkeypatch)
    cases, traces = run_of("T-01", "T-02")  # step=0.93: HUMAN_REVIEW at 0.95, AUTO at 0.9
    replayed = replay_run(traces, cases, policy_id="immunara-v0.2", auto_process=None)
    assert {t.thresholds.version for t in replayed} == {"v0.2"}
    assert {t.action for t in replayed} == {WorkflowAction.AUTO_PROCESS}


def test_replay_run_onto_an_unregistered_version_or_policy_is_an_eval_error(monkeypatch):
    register_v0_2(monkeypatch, with_thresholds=False)
    cases, traces = run_of("T-01")
    with pytest.raises(EvalError, match="unknown thresholds version 'v0.2'"):
        replay_run(traces, cases, policy_id="immunara-v0.2", auto_process=None)
    with pytest.raises(EvalError, match="unknown policy 'nope-v1'"):
        replay_run(traces, cases, policy_id="nope-v1", auto_process=None)


def test_replay_run_labels_an_auto_process_override_in_the_thresholds_version():
    cases, traces = run_of("T-01")
    [replayed] = replay_run(traces, cases, policy_id=None, auto_process=0.9)
    assert replayed.thresholds.version == "v0.1+at0.9"
```

In `tests/unit/test_tracediff.py`, change the import `from relay.workflow.thresholds import THRESHOLDS_V0_1` to:

```python
from relay.workflow.thresholds import THRESHOLDS_V0_1, override_auto_process
```

and in `test_labels`, replace the two `policy_replay_label` assertions with:

```python
    assert policy_replay_label(POLICY, T, None) == (
        "policy replay: STORED DECISIONS under policy immunara-v0.1 (v0.1), thresholds v0.1 — "
        "judgments were made against the original policy's questions"
    )
    assert policy_replay_label(POLICY_V2, override_auto_process(T, 0.89), 0.89) == (
        "policy replay: STORED DECISIONS under policy immunara-v0.2 (v0.2), auto_process=0.89, "
        "thresholds v0.1+at0.89 — judgments were made against the original policy's questions"
    )
```

In `tests/integration/test_cli_replay.py`, make four changes:

(a) Add these imports. Keep them sorted; ruff will fix the order.

```python
import relay.cases.policies as policies_module
import relay.workflow.thresholds as thresholds_module
from relay.workflow.thresholds import THRESHOLDS_V0_1
```

(b) In `test_at_shows_the_crossed_threshold`, the label assertion becomes:

```python
    assert (
        "CANDIDATE policy replay: STORED DECISIONS under policy immunara-v0.1 (v0.1), "
        "auto_process=0.5, thresholds v0.1+at0.5 — judgments were made against the original "
        "policy's questions"
    ) in result.output
```

(c) In `test_latest_policy_and_explicit_policy_resolve_today_to_immunara_v0_1`, the label assertion becomes:

```python
        assert (
            "STORED DECISIONS under policy immunara-v0.1 (v0.1), thresholds v0.1 — judgments"
        ) in result.output
```

(d) Append to the end of the file:

```python


# ---- F1: a policy replay onto another policy version brings that version's thresholds ----


def register_v0_2(monkeypatch, *, with_thresholds: bool = True):
    spec = dict(policies_module._POLICIES["immunara-v0.1"], version="v0.2")
    monkeypatch.setitem(policies_module._POLICIES, "immunara-v0.2", spec)
    if with_thresholds:
        v2 = THRESHOLDS_V0_1.model_copy(update={"version": "v0.2", "auto_process": 0.9})
        monkeypatch.setitem(thresholds_module._BY_VERSION, "v0.2", v2)


def test_policy_replay_onto_another_version_uses_its_thresholds(tmp_path, smoke_runs, monkeypatch):
    register_v0_2(monkeypatch)
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], "--latest-policy")
    assert result.exit_code == 0, result.output
    assert "under policy immunara-v0.2 (v0.2), thresholds v0.2 — judgments" in result.output
    assert "  auto_process  0.95 → 0.9" in result.output
    at = replay(
        tmp_path, "AUTO-01", smoke_runs["groundtruth"], "--policy", "immunara-v0.2", "--at", "0.8"
    )
    assert at.exit_code == 0, at.output
    assert "auto_process=0.8, thresholds v0.2+at0.8 — judgments" in at.output


def test_policy_replay_onto_a_version_without_thresholds_is_exit_2(
    tmp_path, smoke_runs, monkeypatch
):
    register_v0_2(monkeypatch, with_thresholds=False)
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], "--policy", "immunara-v0.2")
    assert result.exit_code == 2, result.output
    assert "unknown thresholds version 'v0.2'" in result.output
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/test_thresholds.py tests/unit/test_replay.py tests/unit/test_tracediff.py tests/integration/test_cli_replay.py`
Expected: FAIL. The failures include `ImportError: cannot import name 'override_auto_process'` and a `replay_thresholds` import error.

- [ ] **Step 3: Implement**

Append to `relay/workflow/thresholds.py`:

```python


def override_auto_process(thresholds: Thresholds, auto_process: float) -> Thresholds:
    """`thresholds` with auto_process replaced, and a version that records the override.

    v0.1 becomes v0.1+at0.89. An earlier override is replaced rather than stacked, so
    v0.1+at0.89 overridden to 0.9 becomes v0.1+at0.9. Every other threshold is unchanged.
    """
    base = thresholds.version.split("+at", 1)[0]
    return thresholds.model_copy(
        update={"auto_process": auto_process, "version": f"{base}+at{auto_process:g}"}
    )
```

In `relay/evaluation/frontier.py`, add the import `from relay.workflow.thresholds import override_auto_process` after `from relay.workflow.outcomes import WorkflowAction`. Then in `sweep` replace:

```python
            thresholds = trace.thresholds.model_copy(update={"auto_process": t})
```
with
```python
            thresholds = override_auto_process(trace.thresholds, t)
```

In `relay/evaluation/compare.py`, add the same import after `from relay.workflow.outcomes import WorkflowAction`. Then in `_actions_at` replace:

```python
        thresholds = trace.thresholds.model_copy(update={"auto_process": auto_process})
```
with
```python
        thresholds = override_auto_process(trace.thresholds, auto_process)
```

In `relay/evaluation/tracediff.py`:

1. Change `from relay.evaluation.metrics import paired_cases` to `from relay.evaluation.metrics import EvalError, paired_cases`.
2. Change `from relay.workflow.thresholds import Thresholds` to `from relay.workflow.thresholds import Thresholds, load_thresholds, override_auto_process`.
3. Replace the whole `policy_replay_label` function with the following, which also adds `replay_thresholds`:

```python
def policy_replay_label(
    policy: AuthorizationPolicy, thresholds: Thresholds, auto_process: float | None
) -> str:
    at = "" if auto_process is None else f", auto_process={auto_process:g}"
    return (
        f"policy replay: STORED DECISIONS under policy {policy.id} ({policy.version}){at}, "
        f"thresholds {thresholds.version} — judgments were made against the original policy's "
        "questions"
    )


def replay_thresholds(
    trace: WorkflowTrace, target: AuthorizationPolicy, auto_process: float | None
) -> Thresholds:
    """The thresholds a policy replay of `trace` onto `target` runs under (F1).

    Same policy version as the trace: the trace's own thresholds. A different version: the
    thresholds registered for `target.version` (an unknown version raises EvalError). An
    `auto_process` override is then applied with override_auto_process.
    """
    if target.version == trace.policy_version:
        base = trace.thresholds
    else:
        try:
            base = load_thresholds(target.version)
        except KeyError as error:
            raise EvalError(str(error.args[0])) from error
    return base if auto_process is None else override_auto_process(base, auto_process)
```

4. In `replay_run`, replace the docstring and loop body with:

```python
    """Run-level policy replay (for Phase 3B), in trace order.

    Pairs traces with cases through paired_cases, so every check there applies (one run, no
    duplicates, no unknown or changed cases, full coverage; EvalError otherwise). None keeps each
    trace's own policy / auto_process. Thresholds follow replay_thresholds: a target policy of
    another version brings that version's thresholds (EvalError if none are registered). Every
    replayed trace shares run_id "replay-<run_id>".
    """
    pairs = paired_cases(traces, cases)
    now = datetime.now(UTC)
    git_sha = current_git_sha()
    policies: dict[str, AuthorizationPolicy] = {}
    replayed = []
    for trace, case in pairs:
        target = policy_id or trace.policy_id
        if target not in policies:
            try:
                policies[target] = load_policy(target)
            except KeyError as error:
                raise EvalError(str(error.args[0])) from error
        replayed.append(
            replay_trace(
                trace,
                case,
                policy=policies[target],
                thresholds=replay_thresholds(trace, policies[target], auto_process),
                now=now,
                git_sha=git_sha,
            )
        )
    return replayed
```

(The block above runs from the docstring's first line to the end of the function; keep the `def replay_run(` signature unchanged.)

In `relay/cli.py`, add `replay_thresholds,` to the `from relay.evaluation.tracediff import (...)` list, between `replay_exit_code,` and `replay_trace,`. Then in `replay`, in the `elif policy_replay:` branch, replace:

```python
        target = _policy(target_id)
        thresholds = (
            original.thresholds
            if at is None
            else original.thresholds.model_copy(update={"auto_process": at})
        )
        candidate = replay_trace(original, case, policy=target, thresholds=thresholds)
        label = policy_replay_label(target, at)
```
with
```python
        target = _policy(target_id)
        try:
            thresholds = replay_thresholds(original, target, at)
        except EvalError as error:
            raise _fail(str(error)) from error
        candidate = replay_trace(original, case, policy=target, thresholds=thresholds)
        label = policy_replay_label(target, thresholds, at)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass (2 deselected).

- [ ] **Step 5: Confirm the committed artifacts are untouched**

Run: `git status --short evals/`
Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add relay/workflow/thresholds.py relay/evaluation/tracediff.py relay/evaluation/frontier.py relay/evaluation/compare.py relay/cli.py tests/unit/test_thresholds.py tests/unit/test_replay.py tests/unit/test_tracediff.py tests/integration/test_cli_replay.py
git commit -m "fix: thresholds follow the target policy version; label --at overrides (F1)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: F2: `diff_case` and `diff_runs`; refactor `relay replay` and the gold drift guard

**Files:**
- Modify: `relay/evaluation/tracediff.py` (imports; insert two functions before `replay_exit_code`)
- Modify: `relay/cli.py` (imports; the end of `replay`)
- Modify: `tests/integration/test_committed_baselines.py` (`drifted_cases`, imports)
- Create: `tests/unit/test_rundiff.py`
- Modify: `tests/integration/test_cli_replay.py` (imports; append one test)

**Interfaces:**
- Consumes: `override_auto_process` and `replay_thresholds` (Task 1).
- Produces:
  - `diff_case(original: WorkflowTrace, candidate: WorkflowTrace, case: PriorAuthCase, *, original_label: str, candidate_label: str, policies: Mapping[str, AuthorizationPolicy] | None = None) -> TraceDiff`
  - `diff_runs(originals: Sequence[WorkflowTrace], candidates: Sequence[WorkflowTrace], cases: Sequence[PriorAuthCase], *, original_label: str, candidate_label: str) -> list[TraceDiff]`, which raises `EvalError` for mismatched case sets (naming missing and extra ids), for any `paired_cases` failure on either run, and for an unknown policy

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_rundiff.py`:

```python
"""diff_case / diff_runs: the run-level diff helpers every replay, regression and shadow caller
shares (F2), so that pairing and expected actions are derived in exactly one place."""

import pytest

import relay.cases.policies as policies_module
import relay.evaluation.tracediff as tracediff
from relay.cases.policies import load_policy
from relay.evaluation.labels import expected_action
from relay.evaluation.metrics import EvalError
from relay.evaluation.runner import policy_text_hash
from relay.evaluation.tracediff import diff_case, diff_runs, diff_traces, replay_trace
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1, override_auto_process
from tests.factories import make_bundle, make_case, make_trace

POLICY = load_policy("immunara-v0.1")


def register_strict_v0_2(monkeypatch):
    """A second registered policy that differs where it matters: min_age 50, so a 40-year-old's
    expected action is HUMAN_REVIEW under it and AUTO_PROCESS under immunara-v0.1."""
    spec = dict(policies_module._POLICIES["immunara-v0.1"], version="v0.2", min_age=50)
    monkeypatch.setitem(policies_module._POLICIES, "immunara-v0.2", spec)
    return load_policy("immunara-v0.2")


def run_of(*case_ids, run_id="run_a", step=0.93):
    cases = [make_case(i) for i in case_ids]
    traces = [make_trace(c, make_bundle(c.input.id, step=step), run_id=run_id) for c in cases]
    return cases, traces


def at(traces, cases, auto_process, policy=POLICY):
    thresholds = override_auto_process(THRESHOLDS_V0_1, auto_process)
    return [
        replay_trace(t, c, policy=policy, thresholds=thresholds, git_sha="x")
        for t, c in zip(traces, cases, strict=True)
    ]


def test_diff_case_matches_a_hand_built_diff_traces():
    [case], [original] = run_of("T-01")
    [candidate] = at([original], [case], 0.9)
    by_hand = diff_traces(
        original,
        candidate,
        expected_original=expected_action(case, POLICY, original.thresholds),
        expected_candidate=expected_action(case, POLICY, candidate.thresholds),
        original_label="o",
        candidate_label="c",
        current_policy_text_hash=policy_text_hash(POLICY),
    )
    assert diff_case(original, candidate, case, original_label="o", candidate_label="c") == by_hand
    assert by_hand.newly_unsafe is False and by_hand.change == "improved"


def test_diff_case_judges_each_side_under_its_own_policy(monkeypatch):
    strict = register_strict_v0_2(monkeypatch)
    [case], [original] = run_of("T-01", step=0.99)
    [candidate] = at([original], [case], 0.95, policy=strict)
    d = diff_case(original, candidate, case, original_label="o", candidate_label="c")
    assert (d.expected_original, d.expected_candidate) == (
        WorkflowAction.AUTO_PROCESS,
        WorkflowAction.HUMAN_REVIEW,
    )
    assert d.policy == ("immunara-v0.1 v0.1", "immunara-v0.2 v0.2")
    assert d.policy_text_hash_current == policy_text_hash(POLICY)


def test_diff_case_uses_the_policy_cache(monkeypatch):
    def no_load(policy_id):
        raise AssertionError(f"loaded {policy_id} despite the cache")

    monkeypatch.setattr(tracediff, "load_policy", no_load)
    [case], [original] = run_of("T-01")
    d = diff_case(
        original,
        original,
        case,
        original_label="o",
        candidate_label="c",
        policies={POLICY.id: POLICY},
    )
    assert d.identical


def test_diff_runs_diffs_every_case_in_trace_order_and_loads_each_policy_once(monkeypatch):
    loaded = []
    real = tracediff.load_policy

    def counting(policy_id):
        loaded.append(policy_id)
        return real(policy_id)

    monkeypatch.setattr(tracediff, "load_policy", counting)
    cases, originals = run_of("T-02", "T-01", "T-03")
    candidates = list(reversed(at(originals, cases, 0.9)))
    diffs = diff_runs(originals, candidates, cases, original_label="o", candidate_label="c")
    assert [d.case_id for d in diffs] == ["T-02", "T-01", "T-03"]
    assert {d.action_candidate for d in diffs} == {WorkflowAction.AUTO_PROCESS}
    assert {(d.original_label, d.candidate_label) for d in diffs} == {("o", "c")}
    assert loaded == ["immunara-v0.1"]


def test_diff_runs_names_missing_and_extra_case_ids():
    cases, originals = run_of("T-01", "T-02")
    _, others = run_of("T-01", "T-03", run_id="run_b")
    with pytest.raises(EvalError, match=r"missing \['T-02'\], extra \['T-03'\]"):
        diff_runs(originals, others, cases, original_label="o", candidate_label="c")


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda c: [c[0], c[1].model_copy(update={"run_id": "run_z"})], "multiple runs"),
        (
            lambda c: [c[0], c[1].model_copy(update={"case_content_hash": "sha256:x"})],
            "hash changed",
        ),
    ],
)
def test_diff_runs_applies_paired_cases_to_the_candidate_run(mutate, message):
    cases, originals = run_of("T-01", "T-02")
    candidates = mutate(at(originals, cases, 0.9))
    with pytest.raises(EvalError, match=message):
        diff_runs(originals, candidates, cases, original_label="o", candidate_label="c")


def test_diff_runs_needs_every_dataset_case():
    cases, originals = run_of("T-01", "T-02")
    with pytest.raises(EvalError, match="do not cover every case"):
        diff_runs(
            originals[:1],
            at(originals, cases, 0.9)[:1],
            cases,
            original_label="o",
            candidate_label="c",
        )


def test_diff_runs_turns_an_unknown_policy_into_an_eval_error():
    cases, originals = run_of("T-01")
    ghost = [originals[0].model_copy(update={"policy_id": "nope-v1"})]
    with pytest.raises(EvalError, match="unknown policy 'nope-v1'"):
        diff_runs(originals, ghost, cases, original_label="o", candidate_label="c")
```

In `tests/integration/test_cli_replay.py`, replace `from relay.evaluation.tracediff import TraceDiff, replay_trace` with:

```python
from relay.evaluation.labels import expected_action
from relay.evaluation.runner import policy_text_hash
from relay.evaluation.tracediff import (
    TraceDiff,
    diff_traces,
    original_label,
    policy_replay_label,
    replay_trace,
)
```

and change `from relay.workflow.thresholds import THRESHOLDS_V0_1` to `from relay.workflow.thresholds import THRESHOLDS_V0_1, override_auto_process`. Append:

```python


def test_replay_json_matches_a_hand_built_diff(tmp_path, smoke_runs):
    """F2: routing `relay replay` through diff_case changed nothing: its JSON equals the diff
    built by hand from diff_traces, as replay built it before."""
    [original] = [t for t in read_traces(smoke_runs["rules"]) if t.case_id == "AUTO-03"]
    case = load_case(SMOKE / "AUTO-03")
    policy = load_policy("immunara-v0.1")
    thresholds = override_auto_process(original.thresholds, 0.5)
    candidate = replay_trace(original, case, policy=policy, thresholds=thresholds)
    by_hand = diff_traces(
        original,
        candidate,
        expected_original=expected_action(case, policy, original.thresholds),
        expected_candidate=expected_action(case, policy, thresholds),
        original_label=original_label(original),
        candidate_label=policy_replay_label(policy, thresholds, 0.5),
        current_policy_text_hash=policy_text_hash(policy),
    )
    result = replay(tmp_path, "AUTO-03", smoke_runs["rules"], "--at", "0.5", "--json")
    assert result.exit_code == 0, result.output
    assert as_diff(result) == by_hand
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/test_rundiff.py`
Expected: FAIL with `ImportError: cannot import name 'diff_case'`.

- [ ] **Step 3: Implement**

In `relay/evaluation/tracediff.py`:

1. Change `from collections.abc import Callable, Sequence` to `from collections.abc import Callable, Mapping, Sequence`.
2. Add `from relay.evaluation.labels import expected_action` directly above `from relay.evaluation.metrics import EvalError, paired_cases`.
3. Insert immediately before `def replay_exit_code(`:

```python
def diff_case(
    original: WorkflowTrace,
    candidate: WorkflowTrace,
    case: PriorAuthCase,
    *,
    original_label: str,
    candidate_label: str,
    policies: Mapping[str, AuthorizationPolicy] | None = None,
) -> TraceDiff:
    """diff_traces with its inputs derived here rather than by every caller.

    Each side's expected action comes from ground truth under that side's own policy and
    thresholds; the current policy-text hash is that of the original trace's policy id.
    `policies` is an optional cache by policy id; an id missing from it is loaded with
    load_policy (KeyError for an unknown id).
    """

    def policy(policy_id: str) -> AuthorizationPolicy:
        if policies is not None and policy_id in policies:
            return policies[policy_id]
        return load_policy(policy_id)

    policy_o = policy(original.policy_id)
    policy_c = (
        policy_o if candidate.policy_id == original.policy_id else policy(candidate.policy_id)
    )
    return diff_traces(
        original,
        candidate,
        expected_original=expected_action(case, policy_o, original.thresholds),
        expected_candidate=expected_action(case, policy_c, candidate.thresholds),
        original_label=original_label,
        candidate_label=candidate_label,
        current_policy_text_hash=policy_text_hash(policy_o),
    )


def diff_runs(
    originals: Sequence[WorkflowTrace],
    candidates: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
    *,
    original_label: str,
    candidate_label: str,
) -> list[TraceDiff]:
    """One diff_case per case, in the original run's trace order.

    The two runs must cover the same case ids (EvalError naming the missing and extra ids), and
    each goes through paired_cases (one run, no duplicates, known cases with unchanged content
    hashes, the whole dataset; EvalError otherwise). Each policy id is loaded once.
    """
    original_ids = {t.case_id for t in originals}
    candidate_ids = {t.case_id for t in candidates}
    if original_ids != candidate_ids:
        missing = sorted(original_ids - candidate_ids)
        extra = sorted(candidate_ids - original_ids)
        raise EvalError(
            "the candidate run does not cover the same cases as the original run: "
            f"missing {missing}, extra {extra}"
        )
    pairs = paired_cases(originals, cases)
    candidate_by_id = {t.case_id: t for t, _ in paired_cases(candidates, cases)}
    policies: dict[str, AuthorizationPolicy] = {}
    for policy_id in sorted({t.policy_id for t in [*originals, *candidates]}):
        try:
            policies[policy_id] = load_policy(policy_id)
        except KeyError as error:
            raise EvalError(str(error.args[0])) from error
    return [
        diff_case(
            original,
            candidate_by_id[original.case_id],
            case,
            original_label=original_label,
            candidate_label=candidate_label,
            policies=policies,
        )
        for original, case in pairs
    ]
```

In `relay/cli.py`:

1. In the `from relay.evaluation.tracediff import (...)` list, replace `diff_traces,` with `diff_case,`.
2. Delete `from relay.evaluation.labels import expected_action`, and delete `policy_text_hash,` from the `from relay.evaluation.runner import (...)` list. Both are now unused; ruff flags them otherwise.
3. At the end of `replay`, replace:

```python
    candidate_policy = (
        original_policy
        if candidate.policy_id == original.policy_id
        else _policy(candidate.policy_id)
    )
    diff = diff_traces(
        original,
        candidate,
        expected_original=expected_action(case, original_policy, original.thresholds),
        expected_candidate=expected_action(case, candidate_policy, candidate.thresholds),
        original_label=original_label(original),
        candidate_label=label,
        current_policy_text_hash=policy_text_hash(original_policy),
    )
```
with
```python
    policies = {original_policy.id: original_policy}
    if candidate.policy_id not in policies:
        policies[candidate.policy_id] = _policy(candidate.policy_id)
    diff = diff_case(
        original,
        candidate,
        case,
        original_label=original_label(original),
        candidate_label=label,
        policies=policies,
    )
```

(An unknown candidate policy id still exits 2 through `_policy`.)

In `tests/integration/test_committed_baselines.py`:

1. Remove `from relay.evaluation.labels import expected_action`.
2. Change `from relay.evaluation.runner import policy_text_hash, sample_cases` to `from relay.evaluation.runner import sample_cases`.
3. In the `from relay.evaluation.tracediff import (...)` list, replace `diff_traces,` with `diff_case,`.
4. In `drifted_cases`, replace:

```python
        expected = expected_action(case, policy, trace.thresholds)
        diff = diff_traces(
            trace,
            replayed,
            expected_original=expected,
            expected_candidate=expected,
            original_label=original_label(trace),
            candidate_label=REPRODUCE_LABEL,
            current_policy_text_hash=policy_text_hash(policy),
        )
```
with
```python
        diff = diff_case(
            trace,
            replayed,
            case,
            original_label=original_label(trace),
            candidate_label=REPRODUCE_LABEL,
            policies={policy.id: policy},
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass. That includes every existing replay test and `test_the_reproduce_guard_detects_engine_drift`, both unchanged.

- [ ] **Step 5: Commit**

```bash
git add relay/evaluation/tracediff.py relay/cli.py tests/integration/test_committed_baselines.py tests/unit/test_rundiff.py tests/integration/test_cli_replay.py
git commit -m "refactor: add diff_case / diff_runs and route replay and the drift guard through them (F2)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: F3: unlabelled diffs (optional expected action)

**Files:**
- Modify: `relay/evaluation/tracediff.py` (`TraceDiff` fields, `diff_traces`, `diff_case`, `diff_runs`)
- Modify: `relay/reporting.py` (`_expected_line`, `_action_lines`, `replay_summary`)
- Modify: `tests/unit/test_rundiff.py` (imports; append tests), `tests/unit/test_reporting_replay.py` (append a test)

**Interfaces:**
- Consumes: `diff_case` and `diff_runs` (Task 2).
- Produces:
  - `diff_traces(..., expected_original: WorkflowAction | None, expected_candidate: WorkflowAction | None, ...)`. Both `None` gives an unlabelled diff; exactly one is a `ValueError`.
  - `diff_case(..., labelled: bool = True)` and `diff_runs(..., labelled: bool = True)`.
  - `TraceDiff.expected_original`, `expected_candidate`, `change`, `newly_unsafe` and `unsafe_resolved` are now Optional.
  - `relay.reporting.UNLABELLED_LINE == "EXPECTED: not available (unlabelled)"`.

- [ ] **Step 1: Write the failing tests**

In `tests/unit/test_rundiff.py`, replace `from relay.evaluation.tracediff import diff_case, diff_runs, diff_traces, replay_trace` with:

```python
from relay.evaluation.tracediff import (
    TraceDiff,
    diff_case,
    diff_runs,
    diff_traces,
    replay_exit_code,
    replay_trace,
)
```

Append to `tests/unit/test_rundiff.py`:

```python


# ---- F3: unlabelled diffs (no expected action) ----


def test_an_unlabelled_diff_has_no_expected_change_or_unsafe_flags():
    [case], [original] = run_of("T-01")
    [candidate] = at([original], [case], 0.9)
    d = diff_traces(
        original,
        candidate,
        expected_original=None,
        expected_candidate=None,
        original_label="o",
        candidate_label="c",
        current_policy_text_hash=policy_text_hash(POLICY),
    )
    assert (d.expected_original, d.expected_candidate) == (None, None)
    assert (d.change, d.newly_unsafe, d.unsafe_resolved) == (None, None, None)
    assert (d.action_original, d.action_candidate) == (
        WorkflowAction.HUMAN_REVIEW,
        WorkflowAction.AUTO_PROCESS,
    )
    assert d.identical is False
    assert d.thresholds == {"auto_process": (0.95, 0.9)}
    assert replay_exit_code(d, reproduce=False) == 0
    assert TraceDiff.model_validate_json(d.model_dump_json()) == d


def test_exactly_one_expected_action_is_a_value_error():
    [case], [original] = run_of("T-01")
    with pytest.raises(ValueError, match="both expected actions, or neither"):
        diff_traces(
            original,
            original,
            expected_original=WorkflowAction.HUMAN_REVIEW,
            expected_candidate=None,
            original_label="o",
            candidate_label="c",
            current_policy_text_hash=None,
        )


def test_unlabelled_diff_case_and_diff_runs_never_derive_an_expected_action(monkeypatch):
    def no_labels(*args):
        raise AssertionError("an unlabelled diff derived an expected action")

    monkeypatch.setattr(tracediff, "expected_action", no_labels)
    cases, originals = run_of("T-01", "T-02")
    candidates = at(originals, cases, 0.9)
    one = diff_case(
        originals[0],
        candidates[0],
        cases[0],
        original_label="o",
        candidate_label="c",
        labelled=False,
    )
    assert one.change is None and one.policy_text_hash_current == policy_text_hash(POLICY)
    many = diff_runs(
        originals, candidates, cases, original_label="o", candidate_label="c", labelled=False
    )
    assert [d.newly_unsafe for d in many] == [None, None]
```

Append to `tests/unit/test_reporting_replay.py`:

```python


def test_an_unlabelled_diff_renders_without_expected_actions_or_verdicts():  # F3
    a = original(step=0.93)
    b = at(a, 0.9)
    text = render_trace_diff(diff(a, b, expected=(None, None)))
    lines = text.splitlines()
    assert "EXPECTED: not available (unlabelled)" in lines
    assert "  ORIGINAL  HUMAN_REVIEW" in lines
    assert "  CANDIDATE AUTO_PROCESS" in lines
    assert lines[-1] == "ACTION CHANGED: HUMAN_REVIEW → AUTO_PROCESS"
    assert "(correct)" not in text and "(UNSAFE)" not in text
    assert replay_summary(diff(a, a, expected=(None, None))) == "ACTION UNCHANGED: HUMAN_REVIEW"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/test_rundiff.py tests/unit/test_reporting_replay.py`
Expected: FAIL. `TraceDiff` rejects `None` for `expected_original` with a ValidationError, and `diff_case` has no `labelled` keyword.

- [ ] **Step 3: Implement**

In `relay/evaluation/tracediff.py`, replace these `TraceDiff` fields:

```python
    expected_original: WorkflowAction  # under the original side's policy/thresholds
    expected_candidate: WorkflowAction  # under the candidate side's policy/thresholds
    change: Change
    newly_unsafe: bool
    unsafe_resolved: bool
```
with
```python
    # Under each side's own policy/thresholds. These four and the next three are None for an
    # unlabelled diff (no ground truth, e.g. 3C shadow traffic).
    expected_original: WorkflowAction | None
    expected_candidate: WorkflowAction | None
    change: Change | None
    newly_unsafe: bool | None
    unsafe_resolved: bool | None
```

Then replace everything from `def diff_traces(` up to, but not including, `def replay_exit_code(`. That region currently holds `diff_traces`, `diff_case` and `diff_runs`. Replace it with:

```python
def diff_traces(
    original: WorkflowTrace,
    candidate: WorkflowTrace,
    *,
    expected_original: WorkflowAction | None,
    expected_candidate: WorkflowAction | None,
    original_label: str,
    candidate_label: str,
    current_policy_text_hash: str | None,
) -> TraceDiff:
    """Everything that differs between two traces of one case.

    `current_policy_text_hash` is the hash of the current text of the ORIGINAL trace's policy id
    (relay.evaluation.runner.policy_text_hash), computed by the caller to keep this function pure.
    Both expected actions None makes an unlabelled diff: expected_*, change, newly_unsafe and
    unsafe_resolved are then None. Exactly one None is a ValueError.
    """
    if original.case_id != candidate.case_id:
        raise ValueError(
            f"cannot diff traces of different cases: {original.case_id} vs {candidate.case_id}"
        )
    if (expected_original is None) != (expected_candidate is None):
        raise ValueError("give both expected actions, or neither for an unlabelled diff")
    thresholds = {
        name: (getattr(original.thresholds, name), getattr(candidate.thresholds, name))
        for name in THRESHOLD_NAMES
        if getattr(original.thresholds, name) != getattr(candidate.thresholds, name)
    }
    policy_o = f"{original.policy_id} {original.policy_version}"
    policy_c = f"{candidate.policy_id} {candidate.policy_version}"
    text_hash = original.policy_text_hash
    change: Change | None = None
    newly_unsafe: bool | None = None
    unsafe_resolved: bool | None = None
    if expected_original is not None and expected_candidate is not None:
        unsafe_o = classify(original.action, expected_original) == "UNSAFE"
        unsafe_c = classify(candidate.action, expected_candidate) == "UNSAFE"
        change = _change(original.action, expected_original, candidate.action, expected_candidate)
        newly_unsafe = unsafe_c and not unsafe_o
        unsafe_resolved = unsafe_o and not unsafe_c
    return TraceDiff(
        case_id=original.case_id,
        original_label=original_label,
        candidate_label=candidate_label,
        decisions=_decision_deltas(original, candidate),
        gates=_gate_deltas(original, candidate),
        thresholds=thresholds,
        policy=None if policy_o == policy_c else (policy_o, policy_c),
        policy_text_changed=None if text_hash is None else text_hash != current_policy_text_hash,
        policy_text_hash_original=text_hash,
        policy_text_hash_current=current_policy_text_hash,
        action_original=original.action,
        action_candidate=candidate.action,
        reasons_original=list(original.decision_reasons),
        reasons_candidate=list(candidate.decision_reasons),
        expected_original=expected_original,
        expected_candidate=expected_candidate,
        change=change,
        newly_unsafe=newly_unsafe,
        unsafe_resolved=unsafe_resolved,
        identical=(
            original.action == candidate.action
            and original.decision_reasons == candidate.decision_reasons
            and original.gate_path == candidate.gate_path
            and _comparable(original.decisions) == _comparable(candidate.decisions)
        ),
    )


def diff_case(
    original: WorkflowTrace,
    candidate: WorkflowTrace,
    case: PriorAuthCase,
    *,
    original_label: str,
    candidate_label: str,
    policies: Mapping[str, AuthorizationPolicy] | None = None,
    labelled: bool = True,
) -> TraceDiff:
    """diff_traces with its inputs derived here rather than by every caller.

    Each side's expected action comes from ground truth under that side's own policy and
    thresholds; the current policy-text hash is that of the original trace's policy id.
    `policies` is an optional cache by policy id; an id missing from it is loaded with
    load_policy (KeyError for an unknown id). labelled=False makes an unlabelled diff (no
    expected actions; see diff_traces).
    """

    def policy(policy_id: str) -> AuthorizationPolicy:
        if policies is not None and policy_id in policies:
            return policies[policy_id]
        return load_policy(policy_id)

    policy_o = policy(original.policy_id)
    policy_c = (
        policy_o if candidate.policy_id == original.policy_id else policy(candidate.policy_id)
    )
    return diff_traces(
        original,
        candidate,
        expected_original=(
            expected_action(case, policy_o, original.thresholds) if labelled else None
        ),
        expected_candidate=(
            expected_action(case, policy_c, candidate.thresholds) if labelled else None
        ),
        original_label=original_label,
        candidate_label=candidate_label,
        current_policy_text_hash=policy_text_hash(policy_o),
    )


def diff_runs(
    originals: Sequence[WorkflowTrace],
    candidates: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
    *,
    original_label: str,
    candidate_label: str,
    labelled: bool = True,
) -> list[TraceDiff]:
    """One diff_case per case, in the original run's trace order (labelled as diff_case).

    The two runs must cover the same case ids (EvalError naming the missing and extra ids), and
    each goes through paired_cases (one run, no duplicates, known cases with unchanged content
    hashes, the whole dataset; EvalError otherwise). Each policy id is loaded once.
    """
    original_ids = {t.case_id for t in originals}
    candidate_ids = {t.case_id for t in candidates}
    if original_ids != candidate_ids:
        missing = sorted(original_ids - candidate_ids)
        extra = sorted(candidate_ids - original_ids)
        raise EvalError(
            "the candidate run does not cover the same cases as the original run: "
            f"missing {missing}, extra {extra}"
        )
    pairs = paired_cases(originals, cases)
    candidate_by_id = {t.case_id: t for t, _ in paired_cases(candidates, cases)}
    policies: dict[str, AuthorizationPolicy] = {}
    for policy_id in sorted({t.policy_id for t in [*originals, *candidates]}):
        try:
            policies[policy_id] = load_policy(policy_id)
        except KeyError as error:
            raise EvalError(str(error.args[0])) from error
    return [
        diff_case(
            original,
            candidate_by_id[original.case_id],
            case,
            original_label=original_label,
            candidate_label=candidate_label,
            policies=policies,
            labelled=labelled,
        )
        for original, case in pairs
    ]
```

In `relay/reporting.py`, replace `def _expected_line` (the whole function) with:

```python
UNLABELLED_LINE = "EXPECTED: not available (unlabelled)"


def _expected_line(diff: TraceDiff) -> str:
    if diff.expected_original is None:
        return UNLABELLED_LINE
    if diff.expected_original == diff.expected_candidate:
        return f"EXPECTED (evaluation-only): {diff.expected_original}"
    if diff.policy is not None:
        before, after = diff.policy
    else:
        before, after = "original thresholds", "candidate thresholds"
    return (
        f"EXPECTED (evaluation-only) under {before}: {diff.expected_original} · "
        f"under {after}: {diff.expected_candidate}"
    )
```

and replace the whole `_action_lines` and `replay_summary` functions with:

```python
def _action_lines(
    side: str, action: WorkflowAction, expected: WorkflowAction | None, reasons: list[str]
) -> list[str]:
    verdict = "" if expected is None else f" ({classify(action, expected)})"
    return [f"  {side:<10}{action}{verdict}"] + [f"      - {reason}" for reason in reasons]


def replay_summary(diff: TraceDiff) -> str:
    """ACTION CHANGED: A → B (flag), or ACTION UNCHANGED: A (flag).

    NEWLY UNSAFE / UNSAFE RESOLVED can happen even when the action itself is unchanged (for
    example different policies on the two sides), so both forms carry the flag rather than only
    the changed one (Minor 1). "(unchanged)" is never shown for two differing actions that are
    each correct under their own side's expectation; that prints "(both correct)" instead.
    """
    unchanged = diff.action_original == diff.action_candidate
    if diff.newly_unsafe:
        flag = "NEWLY UNSAFE"
    elif diff.unsafe_resolved:
        flag = "UNSAFE RESOLVED"
    elif unchanged or diff.change is None:
        flag = None
    elif diff.change == "unchanged":
        flag = "both correct"
    else:
        flag = diff.change
    if unchanged:
        base = f"ACTION UNCHANGED: {diff.action_original}"
    else:
        base = f"ACTION CHANGED: {diff.action_original} → {diff.action_candidate}"
    return base if flag is None else f"{base} ({flag})"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add relay/evaluation/tracediff.py relay/reporting.py tests/unit/test_rundiff.py tests/unit/test_reporting_replay.py
git commit -m "feat: allow unlabelled trace diffs with no expected action (F3)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: F4: gated crossings (`crossed_gated`)

**Files:**
- Modify: `relay/evaluation/tracediff.py` (`DecisionDelta`, new `gated_only`, `_decision_deltas`)
- Modify: `relay/reporting.py` (`_decision_lines`)
- Modify: `tests/unit/test_tracediff.py` (import; append), `tests/unit/test_reporting_replay.py` (append)

**Interfaces:**
- Produces:
  - `DecisionDelta.crossed_gated: list[str]`, the subset of `crossed` whose `CROSSINGS` row has a non-None `gate`
  - `tracediff.gated_only(question_id: DecisionId, crossed: Sequence[str]) -> list[str]`
  - `relay.reporting.REPORTED_ONLY_LEGEND`

- [ ] **Step 1: Write the failing tests**

In `tests/unit/test_tracediff.py`, add `gated_only,` to the `from relay.evaluation.tracediff import (...)` list after `diff_traces,`. Append:

```python


# ---- F4: gated crossings ----


@pytest.mark.parametrize("key", list(ENGINE_CASES), ids=lambda k: f"{k[0]}-{k[1]}")
def test_a_gated_crossing_is_in_crossed_gated(key):
    question_id, name = key
    true_side, false_side = ENGINE_CASES[key](getattr(T, name))
    d = diff(
        trace_for(make_bundle("T-01", **true_side)), trace_for(make_bundle("T-01", **false_side))
    )
    assert row(d, question_id).crossed_gated == [name]


def test_a_reported_only_crossing_is_not_in_crossed_gated():
    d = diff(
        trace_for(make_bundle("T-01", contra=0.04)), trace_for(make_bundle("T-01", contra=0.06))
    )
    assert row(d, CONTRA).crossed == ["auto_process"]
    assert row(d, CONTRA).crossed_gated == []
    e = diff(
        trace_for(make_bundle("T-01", missing="NONE", missing_p=0.96)),
        trace_for(make_bundle("T-01", missing="NONE", missing_p=0.90)),
    )
    assert row(e, MISSING).crossed == ["auto_process"]
    assert row(e, MISSING).crossed_gated == []


def test_gated_only_follows_the_crossings_table():
    for (question_id, name), crossing in CROSSINGS.items():
        assert gated_only(question_id, [name]) == ([name] if crossing.gate else [])
```

Append to `tests/unit/test_reporting_replay.py`:

```python


def test_reported_only_crossings_are_parenthesised_with_a_legend():  # F4
    # material_contradiction vs auto_process (1 - p_yes against the bar) is reported only;
    # step_therapy vs auto_process feeds the auto_process gate.
    a = original(step=0.96, contra=0.04)
    b = original(step=0.94, contra=0.06)
    text = render_trace_diff(diff(a, b))
    contra = next(line for line in text.splitlines() if "material_contradiction" in line)
    step = next(line for line in text.splitlines() if "step_therapy" in line)
    assert contra.rstrip().endswith("(auto_process)")
    assert step.rstrip().endswith("auto_process") and "(auto_process)" not in step
    assert "  ((name) = reported-only comparison: no engine gate acts on it)" in text


def test_no_legend_without_a_reported_only_crossing():
    text = render_trace_diff(diff(original(step=0.96), original(step=0.94)))
    assert re.search(r"step_therapy.*auto_process", text) and "reported-only" not in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/test_tracediff.py tests/unit/test_reporting_replay.py`
Expected: FAIL with `ImportError: cannot import name 'gated_only'`.

- [ ] **Step 3: Implement**

In `relay/evaluation/tracediff.py`, add a field to `DecisionDelta` after `crossed: list[str] …`:

```python
    # The subset of `crossed` whose CROSSINGS row feeds a real engine gate (F4); the rest are
    # reported-only comparisons. Regression counts use this, never raw `crossed`.
    crossed_gated: list[str]
```

Replace the whole `_decision_deltas` function with the following, which also adds `gated_only`:

```python
def gated_only(question_id: DecisionId, crossed: Sequence[str]) -> list[str]:
    """The names in `crossed` whose (question_id, name) CROSSINGS row has an engine gate."""
    return [name for name in crossed if CROSSINGS[(question_id, name)].gate is not None]


def _decision_deltas(original: WorkflowTrace, candidate: WorkflowTrace) -> list[DecisionDelta]:
    deltas = []
    for question_id in DecisionId:
        o = original.decisions.get(question_id)
        c = candidate.decisions.get(question_id)
        kind = o.kind if o is not None else (c.kind if c is not None else None)
        crossed = crossed_thresholds(question_id, o, c, original.thresholds, candidate.thresholds)
        deltas.append(
            DecisionDelta(
                question_id=question_id,
                kind=kind,
                original=render_decision(o),
                candidate=render_decision(c),
                answer_changed=_answer_changed(o, c),
                delta=_delta(o, c),
                crossed=crossed,
                crossed_gated=gated_only(question_id, crossed),
            )
        )
    return deltas
```

In `relay/reporting.py`, replace the whole `_decision_lines` function with the following, which also adds the legend constant above it:

```python
REPORTED_ONLY_LEGEND = "  ((name) = reported-only comparison: no engine gate acts on it)"


def _decision_lines(diff: TraceDiff) -> list[str]:
    rows = [["", "DECISION", "ORIGINAL", "CANDIDATE", "Δ", "CROSSED"]]
    for d in diff.decisions:
        rows.append(
            [
                "*" if d.answer_changed else "",
                d.question_id.value,
                d.original,
                d.candidate,
                "—" if d.delta is None else f"{d.delta:+.3f}",
                ", ".join(n if n in d.crossed_gated else f"({n})" for n in d.crossed),
            ]
        )
    legend = []
    if any(d.answer_changed for d in diff.decisions):
        legend.append("  (* = answer changed)")
    if any(set(d.crossed) - set(d.crossed_gated) for d in diff.decisions):
        legend.append(REPORTED_ONLY_LEGEND)
    return [" " + line for line in _table(rows)] + legend
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add relay/evaluation/tracediff.py relay/reporting.py tests/unit/test_tracediff.py tests/unit/test_reporting_replay.py
git commit -m "feat: mark which threshold crossings feed an engine gate (F4)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Clopper-Pearson intervals

**Files:**
- Create: `relay/evaluation/intervals.py`
- Create: `tests/unit/test_intervals.py`

**Interfaces:**
- Produces:
  - `clopper_pearson(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]`, which raises `ValueError` for `n <= 0`, for `k` outside `[0, n]`, and for confidence outside `(0, 1)`
  - `regularized_beta(x, a, b) -> float`
  - `beta_quantile(p, a, b) -> float`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_intervals.py`:

```python
"""Clopper-Pearson intervals, checked against their definition (binomial tails) and closed forms."""

import math

import pytest

from relay.evaluation.intervals import clopper_pearson, regularized_beta


def upper_tail(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p), summed directly."""
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))


def lower_tail(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p), summed directly."""
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(0, k + 1))


@pytest.mark.parametrize(
    "k,n", [(1, 10), (5, 10), (9, 10), (1, 29), (29, 100), (1, 100), (7, 1000)]
)
def test_the_bounds_invert_the_binomial_tails(k, n):
    lower, upper = clopper_pearson(k, n)
    assert upper_tail(k, n, lower) == pytest.approx(0.025, abs=1e-9)
    assert lower_tail(k, n, upper) == pytest.approx(0.025, abs=1e-9)
    assert lower < k / n < upper


def test_zero_and_all_successes_have_closed_forms():
    assert clopper_pearson(0, 10) == pytest.approx((0.0, 1 - 0.025 ** (1 / 10)), abs=1e-12)
    assert clopper_pearson(10, 10) == pytest.approx((0.025 ** (1 / 10), 1.0), abs=1e-12)


def test_the_interval_is_symmetric_under_k_to_n_minus_k():
    lower, upper = clopper_pearson(3, 17)
    mirror_lower, mirror_upper = clopper_pearson(14, 17)
    assert lower == pytest.approx(1 - mirror_upper, abs=1e-12)
    assert upper == pytest.approx(1 - mirror_lower, abs=1e-12)


def test_a_published_value():
    # 5 of 10: the textbook exact 95% interval (0.1871, 0.8129).
    assert clopper_pearson(5, 10) == pytest.approx((0.187086, 0.812914), abs=1e-6)


def test_regularized_beta_edges_and_a_known_value():
    assert regularized_beta(0.0, 2, 3) == 0.0
    assert regularized_beta(1.0, 2, 3) == 1.0
    assert regularized_beta(0.5, 1, 1) == pytest.approx(0.5)  # Beta(1, 1) is uniform
    assert regularized_beta(0.3, 2, 2) == pytest.approx(3 * 0.3**2 - 2 * 0.3**3)


@pytest.mark.parametrize("k,n", [(0, 0), (-1, 5), (6, 5)])
def test_impossible_counts_are_rejected(k, n):
    with pytest.raises(ValueError):
        clopper_pearson(k, n)


def test_confidence_must_be_a_probability():
    with pytest.raises(ValueError):
        clopper_pearson(1, 2, confidence=1.0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/test_intervals.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'relay.evaluation.intervals'`.

- [ ] **Step 3: Implement**

Create `relay/evaluation/intervals.py`:

```python
"""Exact (Clopper-Pearson) binomial confidence intervals, in pure Python.

The interval for k successes in n trials inverts the binomial tails: the lower bound is the
alpha/2 quantile of Beta(k, n - k + 1) (0 when k == 0), the upper bound the 1 - alpha/2 quantile
of Beta(k + 1, n - k) (1 when k == n). Quantiles come from bisection on the regularized
incomplete beta function, evaluated by its continued fraction.
"""

import math

_EPS = 1e-15
_TINY = 1e-300
_MAX_TERMS = 500
_BISECTIONS = 100


def _beta_cf(a: float, b: float, x: float) -> float:
    """The continued fraction for the incomplete beta function (modified Lentz)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > _TINY else _TINY)
    h = d
    for m in range(1, _MAX_TERMS + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > _TINY else _TINY)
        c = 1.0 + aa / c
        c = c if abs(c) > _TINY else _TINY
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > _TINY else _TINY)
        c = 1.0 + aa / c
        c = c if abs(c) > _TINY else _TINY
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _EPS:
            return h
    raise ArithmeticError(f"incomplete beta did not converge for a={a}, b={b}, x={x}")


def regularized_beta(x: float, a: float, b: float) -> float:
    """I_x(a, b), the Beta(a, b) cumulative distribution function at x."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    front = math.exp(log_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_cf(a, b, x) / a
    return 1.0 - front * _beta_cf(b, a, 1.0 - x) / b


def beta_quantile(p: float, a: float, b: float) -> float:
    """The x in [0, 1] with I_x(a, b) == p, by bisection."""
    low, high = 0.0, 1.0
    for _ in range(_BISECTIONS):
        mid = (low + high) / 2.0
        if regularized_beta(mid, a, b) < p:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def clopper_pearson(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """The exact two-sided `confidence` interval for a binomial proportion k / n."""
    if n <= 0 or not 0 <= k <= n:
        raise ValueError(f"need 0 <= k <= n and n > 0, got k={k}, n={n}")
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")
    alpha = 1.0 - confidence
    lower = 0.0 if k == 0 else beta_quantile(alpha / 2.0, k, n - k + 1)
    upper = 1.0 if k == n else beta_quantile(1.0 - alpha / 2.0, k + 1, n - k)
    return lower, upper
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add relay/evaluation/intervals.py tests/unit/test_intervals.py
git commit -m "feat: add pure-Python Clopper-Pearson binomial intervals" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Regression core: waivers, result model, verdict (pure)

**Files:**
- Create: `relay/evaluation/regression.py`
- Create: `tests/unit/test_regression.py`

**Interfaces:**
- Consumes:
  - `TraceDiff` with `crossed_gated` (Task 4) and Optional `change` (Task 3)
  - `diff_case` and `diff_runs` (Task 2)
  - `replay_run` (Task 1)
  - `clopper_pearson` (Task 5)
  - `EXIT_ENGINE_DRIFT = 3` and `EXIT_NEWLY_UNSAFE = 4` from `tracediff`
- Produces (all in `relay.evaluation.regression`):
  - `CHANGE_ORDER`
  - `Waiver` (fields `case_id`, `gate`, `reason`, `approved_by`, `date`; method `applies_to(gate: str | None) -> bool`)
  - `WaiverFile`
  - `Interval`, `Rate`, `SideMetrics`, `CalibrationDelta`, `CaseEntry`, `WaivedCase`, `RegressionResult`
  - `GateOutcome`
  - `evaluate_gate(diffs, *, reproduce: bool, waivers, gate: str | None, max_regressed: int | None) -> GateOutcome`
  - `rate(count, n) -> Rate`
  - `build_result(diffs, baseline, candidate, cases, *, baseline_label, candidate_label, gate, reproduce, waivers, max_regressed, dataset_hash=None, replay_command=None) -> RegressionResult`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_regression.py`:

```python
"""The regression gate's verdict, waivers and result model (pure; no files)."""

import pytest
from pydantic import ValidationError

from relay.evaluation.intervals import clopper_pearson
from relay.evaluation.regression import (
    Waiver,
    WaiverFile,
    build_result,
    evaluate_gate,
    rate,
)
from relay.evaluation.tracediff import diff_case, diff_runs, replay_run
from relay.workflow.outcomes import WorkflowAction
from tests.factories import make_bundle, make_case, make_trace, make_truth

AUTO = WorkflowAction.AUTO_PROCESS
REVIEW = WorkflowAction.HUMAN_REVIEW


def base_diff():
    case = make_case("T-01")
    trace = make_trace(case)
    return diff_case(trace, trace, case, original_label="b", candidate_label="c")


BASE = base_diff()


def synthetic(case_id, *, change="unchanged", newly_unsafe=False, identical=True):
    """A TraceDiff with only the fields the verdict reads set."""
    return BASE.model_copy(
        update={
            "case_id": case_id,
            "change": change,
            "newly_unsafe": newly_unsafe,
            "unsafe_resolved": False,
            "identical": identical,
        }
    )


def waiver(case_id, gate="*", **overrides):
    values = {
        "case_id": case_id,
        "gate": gate,
        "reason": "accepted after review",
        "approved_by": "reviewer",
        "date": "2026-09-26",
    }
    values.update(overrides)
    return Waiver.model_validate(values)


def gate(diffs, *, reproduce=False, waivers=(), name=None, max_regressed=None):
    return evaluate_gate(
        diffs, reproduce=reproduce, waivers=list(waivers), gate=name, max_regressed=max_regressed
    )


# ---- the verdict ----


def test_no_differences_pass_with_exit_0():
    outcome = gate([synthetic("A"), synthetic("B")])
    assert (outcome.verdict, outcome.exit_code, outcome.failures) == ("PASS", 0, [])


def test_a_newly_unsafe_case_fails_with_exit_4_and_is_named():
    outcome = gate([synthetic("A"), synthetic("B", change="regressed", newly_unsafe=True)])
    assert (outcome.verdict, outcome.exit_code) == ("FAIL", 4)
    assert outcome.failures == ["1 newly unsafe case(s) without a waiver: B"]
    assert [d.case_id for d in outcome.newly_unsafe] == ["B"]


def test_a_waiver_covers_its_newly_unsafe_case():
    diffs = [synthetic("B", change="regressed", newly_unsafe=True)]
    outcome = gate(diffs, waivers=[waiver("B")])
    assert (outcome.verdict, outcome.exit_code) == ("PASS", 0)
    assert [(d.case_id, w.case_id) for d, w in outcome.waived] == [("B", "B")]
    assert outcome.newly_unsafe == [] and outcome.stale_waivers == []


def test_a_waiver_applies_to_its_own_gate_or_to_every_gate():
    diffs = [synthetic("B", change="regressed", newly_unsafe=True)]
    assert gate(diffs, waivers=[waiver("B", gate="g1")], name="g1").verdict == "PASS"
    other = gate(diffs, waivers=[waiver("B", gate="g2")], name="g1")
    assert other.verdict == "FAIL"
    assert other.stale_waivers == []  # a waiver for another gate is out of scope, not stale
    assert gate(diffs, waivers=[waiver("B", gate="g2")], name=None).verdict == "FAIL"


def test_a_waiver_matching_no_newly_unsafe_case_is_stale_but_not_a_failure():
    outcome = gate([synthetic("A")], waivers=[waiver("GONE")])
    assert (outcome.verdict, outcome.exit_code) == ("PASS", 0)
    assert [w.case_id for w in outcome.stale_waivers] == ["GONE"]


def test_regressions_fail_only_above_max_regressed():
    diffs = [synthetic("A", change="regressed"), synthetic("B", change="regressed")]
    assert gate(diffs).verdict == "PASS"
    assert gate(diffs, max_regressed=2).verdict == "PASS"
    over = gate(diffs, max_regressed=1)
    assert (over.verdict, over.exit_code) == ("FAIL", 4)
    assert over.failures == ["2 regressed case(s), more than --max-regressed 1"]


def test_a_waiver_never_covers_a_regression():
    diffs = [synthetic("A", change="regressed")]
    outcome = gate(diffs, waivers=[waiver("A")], max_regressed=0)
    assert outcome.verdict == "FAIL"
    assert [w.case_id for w in outcome.stale_waivers] == ["A"]


def test_reproduce_fails_any_non_identical_case_with_exit_3():
    diffs = [synthetic("A"), synthetic("B", identical=False)]
    outcome = gate(diffs, reproduce=True)
    assert (outcome.verdict, outcome.exit_code) == ("FAIL", 3)
    assert outcome.failures == ["ENGINE DRIFT: 1 case(s) not reproduced: B"]
    assert gate(diffs, reproduce=False).verdict == "PASS"  # only reproduce checks identity


def test_engine_drift_cannot_be_waived_and_the_higher_exit_code_wins():
    drift = synthetic("B", change="regressed", newly_unsafe=True, identical=False)
    waived = gate([drift], reproduce=True, waivers=[waiver("B")])
    assert (waived.verdict, waived.exit_code) == ("FAIL", 3)
    both = gate([drift], reproduce=True)
    assert both.exit_code == 4
    assert len(both.failures) == 2


def test_long_id_lists_are_shortened():
    diffs = [synthetic(f"C{i:02d}", change="regressed", newly_unsafe=True) for i in range(12)]
    [failure] = gate(diffs).failures
    assert failure.endswith("C09 and 2 more")


def test_the_verdict_needs_labelled_diffs():
    with pytest.raises(ValueError, match="labelled"):
        gate([BASE.model_copy(update={"change": None})])


# ---- waivers ----


def test_a_waiver_file_parses():
    parsed = WaiverFile.model_validate({"waivers": [waiver("B").model_dump()]})
    assert parsed.waivers == [waiver("B")]


@pytest.mark.parametrize(
    "overrides",
    [
        {"reason": ""},
        {"reason": "   "},
        {"approved_by": None},
        {"gate": 3},
        {"date": "26/09/2026"},
        {"date": "2026-13-40"},
        {"extra": "field"},
    ],
)
def test_a_malformed_waiver_is_rejected(overrides):
    with pytest.raises(ValidationError):
        waiver("B", **overrides)


def test_every_waiver_field_is_required():
    values = waiver("B").model_dump()
    for field in values:
        partial = {k: v for k, v in values.items() if k != field}
        with pytest.raises(ValidationError):
            Waiver.model_validate(partial)


# ---- the result model ----


def test_rate_carries_a_clopper_pearson_interval_and_none_for_no_trials():
    r = rate(3, 10)
    assert (r.count, r.n, r.rate) == (3, 10, 0.3)
    assert (r.ci95.low, r.ci95.high) == clopper_pearson(3, 10)
    empty = rate(0, 0)
    assert (empty.rate, empty.ci95) == (None, None)


def three_case_run():
    """T-01 expected AUTO_PROCESS, T-02 and T-03 expected HUMAN_REVIEW (step therapy not met);
    every bundle has step_therapy 0.93, so all three are HUMAN_REVIEW at 0.95."""
    cases = [
        make_case("T-01"),
        make_case("T-02", truth=make_truth(step_therapy_satisfied=False)),
        make_case("T-03", truth=make_truth(step_therapy_satisfied=False)),
    ]
    traces = [make_trace(c, make_bundle(c.input.id, step=0.93)) for c in cases]
    return cases, traces


def test_build_result_at_a_lower_threshold():
    cases, baseline = three_case_run()
    candidate = replay_run(baseline, cases, policy_id=None, auto_process=0.9)
    diffs = diff_runs(baseline, candidate, cases, original_label="base", candidate_label="cand")
    result = build_result(
        diffs,
        baseline,
        candidate,
        cases,
        baseline_label="base",
        candidate_label="cand",
        gate="g",
        reproduce=False,
        waivers=[waiver("T-03", reason="reviewed")],
        max_regressed=None,
        dataset_hash="sha256:d",
        replay_command=lambda case_id: f"relay replay {case_id}",
    )
    assert (result.gate, result.dataset_id, result.n) == ("g", "test", 3)
    assert result.change_counts == {
        "improved": 1,
        "unchanged": 0,
        "regressed": 2,
        "changed-both-wrong": 0,
    }
    assert result.not_identical == 3
    assert [e.case_id for e in result.newly_unsafe] == ["T-02"]
    assert [w.entry.case_id for w in result.waived] == ["T-03"]
    assert [e.case_id for e in result.improved] == ["T-01"]
    assert [e.case_id for e in result.regressed] == ["T-02", "T-03"]
    entry = result.newly_unsafe[0]
    assert (entry.expected, entry.expected_candidate) == (REVIEW, None)
    assert (entry.action_baseline, entry.action_candidate) == (REVIEW, AUTO)
    assert entry.answer_changed == []
    assert entry.crossed_gated == {"step_therapy": ["auto_process"]}
    assert entry.replay_command == "relay replay T-02"
    assert (result.verdict, result.exit_code) == ("FAIL", 4)
    assert result.failures == ["1 newly unsafe case(s) without a waiver: T-02"]
    assert result.baseline.automation.count == 0 and result.candidate.automation.count == 3
    assert result.baseline.uar.rate is None
    assert (result.candidate.uar.count, result.candidate.uar.n) == (2, 3)
    assert result.candidate.identity.dataset_hash == "sha256:d"
    assert result.candidate.identity.thresholds_versions == ["v0.1+at0.9"]
    # the same stored decisions on both sides: calibration cannot move
    assert {c.brier_delta for c in result.calibration} == {0.0}
    assert [c.decision for c in result.calibration][0] == "diagnosis_support"
    assert type(result).model_validate_json(result.model_dump_json()) == result
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/test_regression.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'relay.evaluation.regression'`.

- [ ] **Step 3: Implement**

Create `relay/evaluation/regression.py`:

```python
"""The regression gate: result model, waivers and verdict (Phase 3B spec §3, G4-G6).

Pure: no file or network I/O. relay.evaluation.regression_run loads the runs, builds the
candidate and calls build_result; relay.reporting renders the result.

The verdict is FAIL when (a) a newly unsafe case has no waiver, (b) max_regressed is set and more
cases regressed than that, or (c) in reproduce mode any case is not identical. Exit codes: 0 PASS,
4 for (a)/(b), 3 for (c); the highest applicable code wins. Waivers cover newly unsafe cases only.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from relay.cases.models import PriorAuthCase
from relay.evaluation.calibration import calibrate_run
from relay.evaluation.intervals import clopper_pearson
from relay.evaluation.metrics import RunIdentity, run_identity, score_run
from relay.evaluation.tracediff import EXIT_ENGINE_DRIFT, EXIT_NEWLY_UNSAFE, TraceDiff
from relay.traces.models import WorkflowTrace
from relay.workflow.outcomes import WorkflowAction

CHANGE_ORDER: tuple[str, ...] = ("improved", "unchanged", "regressed", "changed-both-wrong")
LISTED_IDS = 10  # case ids spelled out in one failure sentence before "and N more"

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Waiver(BaseModel):
    """A reviewed decision to accept one newly unsafe case in one gate ("*" for every gate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: NonEmpty
    gate: NonEmpty
    reason: NonEmpty
    approved_by: NonEmpty
    date: NonEmpty

    @field_validator("date")
    @classmethod
    def _iso_date(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("date must be YYYY-MM-DD")
        date.fromisoformat(value)  # rejects 2026-13-40
        return value

    def applies_to(self, gate: str | None) -> bool:
        return self.gate == "*" or self.gate == gate


class WaiverFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    waivers: list[Waiver]


class Interval(BaseModel):
    low: float
    high: float


class Rate(BaseModel):
    count: int
    n: int
    rate: float | None  # None when n == 0
    ci95: Interval | None  # Clopper-Pearson; None when n == 0


class SideMetrics(BaseModel):
    label: str
    identity: RunIdentity
    n: int
    correct: Rate
    automation: Rate
    request_info: Rate
    human_review: Rate
    uar: Rate  # unsafe / AUTO_PROCESS count
    invalid_outputs: int


class CalibrationDelta(BaseModel):
    decision: str
    brier_baseline: float | None
    brier_candidate: float | None
    brier_delta: float | None
    ece_baseline: float | None
    ece_candidate: float | None
    ece_delta: float | None


class CaseEntry(BaseModel):
    case_id: str
    expected: WorkflowAction  # under the baseline's policy and thresholds
    expected_candidate: WorkflowAction | None  # only when it differs from `expected`
    action_baseline: WorkflowAction
    action_candidate: WorkflowAction
    answer_changed: list[str]  # decision ids whose answer flipped
    crossed_gated: dict[str, list[str]]  # decision id -> gated thresholds crossed
    replay_command: str | None


class WaivedCase(BaseModel):
    entry: CaseEntry
    waiver: Waiver


class RegressionResult(BaseModel):
    gate: str | None
    reproduce: bool
    dataset_id: str
    n: int
    baseline: SideMetrics
    candidate: SideMetrics
    calibration: list[CalibrationDelta]
    change_counts: dict[str, int]  # CHANGE_ORDER keys
    not_identical: int
    newly_unsafe: list[CaseEntry]  # without a waiver
    waived: list[WaivedCase]
    unsafe_resolved: list[CaseEntry]
    regressed: list[CaseEntry]
    improved: list[CaseEntry]
    drifted: list[CaseEntry]  # reproduce mode only: cases that are not identical
    stale_waivers: list[Waiver]
    max_regressed: int | None
    verdict: Literal["PASS", "FAIL"]
    failures: list[str]
    exit_code: int


@dataclass(frozen=True)
class GateOutcome:
    newly_unsafe: list[TraceDiff]  # without a waiver
    waived: list[tuple[TraceDiff, Waiver]]
    stale_waivers: list[Waiver]
    regressed: list[TraceDiff]
    drifted: list[TraceDiff]
    failures: list[str]
    exit_code: int

    @property
    def verdict(self) -> Literal["PASS", "FAIL"]:
        return "FAIL" if self.failures else "PASS"


def _ids(case_ids: Sequence[str]) -> str:
    shown = ", ".join(case_ids[:LISTED_IDS])
    more = len(case_ids) - LISTED_IDS
    return shown if more <= 0 else f"{shown} and {more} more"


def evaluate_gate(
    diffs: Sequence[TraceDiff],
    *,
    reproduce: bool,
    waivers: Sequence[Waiver],
    gate: str | None,
    max_regressed: int | None,
) -> GateOutcome:
    """The verdict over labelled diffs. Only waivers that apply to `gate` are considered; one of
    those matching no newly unsafe case is stale (a warning, never a failure)."""
    if any(d.change is None for d in diffs):
        raise ValueError("the regression gate needs labelled diffs (expected actions)")
    ordered = sorted(diffs, key=lambda d: d.case_id)
    applicable = [w for w in waivers if w.applies_to(gate)]
    newly_unsafe: list[TraceDiff] = []
    waived: list[tuple[TraceDiff, Waiver]] = []
    for d in (d for d in ordered if d.newly_unsafe):
        waiver = next((w for w in applicable if w.case_id == d.case_id), None)
        if waiver is None:
            newly_unsafe.append(d)
        else:
            waived.append((d, waiver))
    unsafe_ids = {d.case_id for d in ordered if d.newly_unsafe}
    stale = [w for w in applicable if w.case_id not in unsafe_ids]
    regressed = [d for d in ordered if d.change == "regressed"]
    drifted = [d for d in ordered if not d.identical] if reproduce else []

    failures: list[str] = []
    code = 0
    if drifted:
        failures.append(
            f"ENGINE DRIFT: {len(drifted)} case(s) not reproduced: "
            f"{_ids([d.case_id for d in drifted])}"
        )
        code = max(code, EXIT_ENGINE_DRIFT)
    if newly_unsafe:
        failures.append(
            f"{len(newly_unsafe)} newly unsafe case(s) without a waiver: "
            f"{_ids([d.case_id for d in newly_unsafe])}"
        )
        code = max(code, EXIT_NEWLY_UNSAFE)
    if max_regressed is not None and len(regressed) > max_regressed:
        failures.append(
            f"{len(regressed)} regressed case(s), more than --max-regressed {max_regressed}"
        )
        code = max(code, EXIT_NEWLY_UNSAFE)
    return GateOutcome(
        newly_unsafe=newly_unsafe,
        waived=waived,
        stale_waivers=stale,
        regressed=regressed,
        drifted=drifted,
        failures=failures,
        exit_code=code,
    )


def rate(count: int, n: int) -> Rate:
    if n == 0:
        return Rate(count=count, n=n, rate=None, ci95=None)
    low, high = clopper_pearson(count, n)
    return Rate(count=count, n=n, rate=count / n, ci95=Interval(low=low, high=high))


def side_metrics(
    label: str,
    traces: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
    *,
    dataset_hash: str | None,
) -> SideMetrics:
    s = score_run(traces, cases)
    return SideMetrics(
        label=label,
        identity=run_identity(traces, dataset_hash=dataset_hash),
        n=s.n_cases,
        correct=rate(s.correct_actions, s.n_cases),
        automation=rate(s.auto_process_count, s.n_cases),
        request_info=rate(s.request_info_count, s.n_cases),
        human_review=rate(s.human_review_count, s.n_cases),
        uar=rate(s.unsafe_automation_count, s.auto_process_count),
        invalid_outputs=s.invalid_outputs,
    )


def _delta(before: float | None, after: float | None) -> float | None:
    return None if before is None or after is None else after - before


def calibration_deltas(
    baseline: Sequence[WorkflowTrace],
    candidate: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
) -> list[CalibrationDelta]:
    before = calibrate_run(baseline, cases).decisions
    after = calibrate_run(candidate, cases).decisions
    return [
        CalibrationDelta(
            decision=decision,
            brier_baseline=before[decision].brier,
            brier_candidate=after[decision].brier,
            brier_delta=_delta(before[decision].brier, after[decision].brier),
            ece_baseline=before[decision].ece,
            ece_candidate=after[decision].ece,
            ece_delta=_delta(before[decision].ece, after[decision].ece),
        )
        for decision in before
    ]


def case_entry(diff: TraceDiff, replay_command: str | None) -> CaseEntry:
    assert diff.expected_original is not None and diff.expected_candidate is not None
    return CaseEntry(
        case_id=diff.case_id,
        expected=diff.expected_original,
        expected_candidate=(
            None if diff.expected_candidate == diff.expected_original else diff.expected_candidate
        ),
        action_baseline=diff.action_original,
        action_candidate=diff.action_candidate,
        answer_changed=[d.question_id.value for d in diff.decisions if d.answer_changed],
        crossed_gated={
            d.question_id.value: d.crossed_gated for d in diff.decisions if d.crossed_gated
        },
        replay_command=replay_command,
    )


def build_result(
    diffs: Sequence[TraceDiff],
    baseline: Sequence[WorkflowTrace],
    candidate: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
    *,
    baseline_label: str,
    candidate_label: str,
    gate: str | None,
    reproduce: bool,
    waivers: Sequence[Waiver],
    max_regressed: int | None,
    dataset_hash: str | None = None,
    replay_command: Callable[[str], str | None] | None = None,
) -> RegressionResult:
    """The full RegressionResult for one baseline/candidate pair already diffed by diff_runs.

    score_run / calibrate_run pair each side with `cases`, so EvalError propagates for traces
    that do not cover the dataset.
    """
    outcome = evaluate_gate(
        diffs, reproduce=reproduce, waivers=waivers, gate=gate, max_regressed=max_regressed
    )
    command = replay_command or (lambda _case_id: None)

    def entries(selected: Sequence[TraceDiff]) -> list[CaseEntry]:
        return [case_entry(d, command(d.case_id)) for d in selected]

    ordered = sorted(diffs, key=lambda d: d.case_id)
    return RegressionResult(
        gate=gate,
        reproduce=reproduce,
        dataset_id=baseline[0].dataset_id,
        n=len(diffs),
        baseline=side_metrics(baseline_label, baseline, cases, dataset_hash=dataset_hash),
        candidate=side_metrics(candidate_label, candidate, cases, dataset_hash=dataset_hash),
        calibration=calibration_deltas(baseline, candidate, cases),
        change_counts={c: sum(d.change == c for d in diffs) for c in CHANGE_ORDER},
        not_identical=sum(not d.identical for d in diffs),
        newly_unsafe=entries(outcome.newly_unsafe),
        waived=[
            WaivedCase(entry=case_entry(d, command(d.case_id)), waiver=w) for d, w in outcome.waived
        ],
        unsafe_resolved=entries([d for d in ordered if d.unsafe_resolved]),
        regressed=entries(outcome.regressed),
        improved=entries([d for d in ordered if d.change == "improved"]),
        drifted=entries(outcome.drifted),
        stale_waivers=outcome.stale_waivers,
        max_regressed=max_regressed,
        verdict=outcome.verdict,
        failures=outcome.failures,
        exit_code=outcome.exit_code,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add relay/evaluation/regression.py tests/unit/test_regression.py
git commit -m "feat: add the regression gate's result model, waivers and verdict" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Running a gate: loading, candidates, sampling, artifacts

**Files:**
- Create: `relay/evaluation/regression_run.py`
- Create: `tests/integration/test_regression_run.py`

**Interfaces:**
- Consumes:
  - `build_result`, `RegressionResult`, `Waiver` and `WaiverFile` (Task 6)
  - `diff_runs` and `replay_run` from `tracediff`
  - the labels `original_label`, `candidate_trace_label`, `policy_replay_label(policy, thresholds, at)` and `REPRODUCE_LABEL`
- Produces (in `relay.evaluation.regression_run`):
  - `RegressionInputError(ValueError)`
  - `CandidateSpec(traces: str | None, policy: str | None, latest_policy: bool, at: float | None, reproduce: bool)`, with property `is_policy_replay`
  - `GateSpec(name, dataset, baseline, candidate: CandidateSpec, baseline_at, max_regressed, waivers, requires_generated)`
  - `GatesConfig(gates: list[GateSpec])`
  - `RegressionRequest` (a frozen dataclass: `dataset: Path`, `baseline: Path`, `candidate: CandidateSpec`, `baseline_at`, `waivers: Path | None`, `max_regressed`, `gate: str | None`; classmethod `from_gate(spec)`)
  - `RegressionRun(result, baseline, candidate, source_manifest, dataset)`
  - `validate_request(candidate, baseline_at) -> None`
  - `find_run_manifest(trace_file: Path) -> RunManifest | None`
  - `load_waivers(path) -> list[Waiver]`
  - `load_gates(path) -> GatesConfig`
  - `replay_command_for(request, out) -> Callable[[str], str | None]`
  - `run_regression(request, *, out: Path | None = None) -> RegressionRun`
  - `write_outputs(out, run, request, rendered) -> list[Path]`
  - the constants `CANDIDATE_TRACES = "candidate.jsonl.gz"`, `CANDIDATE_MANIFEST`, `BASELINE_TRACES` and `BASELINE_MANIFEST`

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_regression_run.py`:

```python
"""run_regression over real committed traces and fresh offline smoke runs (no network)."""

import gzip
import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from relay.cli import app
from relay.evaluation.regression_run import (
    CandidateSpec,
    RegressionInputError,
    RegressionRequest,
    find_run_manifest,
    load_gates,
    load_waivers,
    replay_command_for,
    run_regression,
    validate_request,
    write_outputs,
)
from relay.traces.store import read_traces

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
GOLD = REPO / "evals" / "gold"
GOLD_RUNS = REPO / "evals" / "baselines" / "gold-v0.1"
GOLD_JEV = GOLD_RUNS / "run_20260925T170857Z_b95be9" / "traces.jsonl.gz"
GOLD_CLAUDE = GOLD_RUNS / "run_20260926T011730Z_f1852f" / "traces.jsonl.gz"


def smoke_run(root: Path, provider: str, *extra: str) -> Path:
    result = CliRunner().invoke(
        app,
        [
            "--env-file",
            str(root / "missing.env"),
            "run",
            "--dataset",
            str(SMOKE),
            "--provider",
            provider,
            "--traces-dir",
            str(root / provider / "traces"),
            "--reports-dir",
            str(root / provider / "reports"),
            *extra,
        ],
    )
    assert result.exit_code == 0, result.output
    [path] = (root / provider / "traces").glob("*.jsonl")
    return path


@pytest.fixture(scope="module")
def smoke(tmp_path_factory):
    root = tmp_path_factory.mktemp("regression-smoke")
    return {p: smoke_run(root, p) for p in ("groundtruth", "rules")}


# ---- request validation (spec G2) ----


@pytest.mark.parametrize(
    "candidate,baseline_at,message",
    [
        (CandidateSpec(traces="t", policy="p"), None, "choose one candidate source"),
        (CandidateSpec(policy="p", latest_policy=True), None, "choose one candidate source"),
        (CandidateSpec(traces="t", reproduce=True), None, "choose one candidate source"),
        (CandidateSpec(reproduce=True, at=0.9), None, "cannot be combined"),
        (CandidateSpec(reproduce=True), 0.9, "cannot be combined"),
        (CandidateSpec(), None, "no candidate"),
        (CandidateSpec(at=0.0), None, "--candidate-at must be in (0, 1]"),
        (CandidateSpec(at=1.5), None, "--candidate-at must be in (0, 1]"),
        (CandidateSpec(at=0.9), -0.1, "--baseline-at must be in (0, 1]"),
    ],
)
def test_invalid_candidate_sources_are_input_errors(candidate, baseline_at, message):
    with pytest.raises(RegressionInputError, match=re.escape(message)):
        validate_request(candidate, baseline_at)


@pytest.mark.parametrize(
    "candidate",
    [
        CandidateSpec(traces="t"),
        CandidateSpec(traces="t", at=0.5),
        CandidateSpec(policy="p", at=0.5),
        CandidateSpec(latest_policy=True),
        CandidateSpec(at=1.0),
        CandidateSpec(reproduce=True),
    ],
)
def test_valid_candidate_sources(candidate):
    validate_request(candidate, None)


# ---- run manifests and sampling ----


def test_run_manifests_are_found_for_every_trace_file_layout(smoke, tmp_path):
    assert find_run_manifest(GOLD_JEV).run_id == "run_20260925T170857Z_b95be9"
    assert find_run_manifest(smoke["rules"]).run_id == smoke["rules"].stem
    assert find_run_manifest(tmp_path / "loose.jsonl") is None


def test_a_sampled_baseline_is_paired_with_its_sample(tmp_path):
    sampled = smoke_run(tmp_path, "groundtruth", "--limit", "4", "--sample-seed", "3")
    run = run_regression(
        RegressionRequest(dataset=SMOKE, baseline=sampled, candidate=CandidateSpec(reproduce=True))
    )
    assert run.result.n == 4
    assert run.result.verdict == "PASS"


# ---- the gold demonstration and a committed-provider comparison ----


def test_gold_jev_at_its_dev_threshold_is_newly_unsafe_on_gold_tmp_17():
    run = run_regression(
        RegressionRequest(dataset=GOLD, baseline=GOLD_JEV, candidate=CandidateSpec(at=0.89))
    )
    result = run.result
    assert (result.verdict, result.exit_code) == ("FAIL", 4)
    assert [e.case_id for e in result.newly_unsafe] == ["GOLD-TMP-17"]
    assert result.failures == ["1 newly unsafe case(s) without a waiver: GOLD-TMP-17"]
    assert result.newly_unsafe[0].replay_command == (
        f"relay replay GOLD-TMP-17 --traces {GOLD_JEV} --dataset {GOLD} --at 0.89"
    )
    assert result.candidate.identity.thresholds_versions == ["v0.1+at0.89"]


def test_claude_is_not_an_unsafe_regression_versus_jev_on_gold():
    run = run_regression(
        RegressionRequest(
            dataset=GOLD,
            baseline=GOLD_JEV,
            baseline_at=0.89,
            candidate=CandidateSpec(traces=str(GOLD_CLAUDE), at=0.55),
            gate="gold-jev-vs-claude",
        )
    )
    result = run.result
    assert (result.verdict, result.exit_code) == ("PASS", 0)
    assert result.change_counts == {
        "improved": 3,
        "unchanged": 96,
        "regressed": 1,
        "changed-both-wrong": 0,
    }
    assert result.newly_unsafe == [] and result.waived == []
    assert result.baseline.label.startswith("replay-run_20260925T170857Z_b95be9 · jev")
    assert result.candidate.label.endswith("· re-decided at auto_process=0.55")
    # the re-decided baseline exists only with --out, so no replay command without it
    assert result.regressed[0].replay_command is None


def test_a_mismatched_candidate_run_is_an_input_error(smoke, tmp_path):
    *kept, dropped = read_traces(smoke["rules"])
    short = tmp_path / "short.jsonl"
    short.write_text("".join(t.model_dump_json() + "\n" for t in kept), encoding="utf-8")
    with pytest.raises(RegressionInputError, match=re.escape(f"missing ['{dropped.case_id}']")):
        run_regression(
            RegressionRequest(
                dataset=SMOKE,
                baseline=smoke["groundtruth"],
                candidate=CandidateSpec(traces=str(short)),
            )
        )


def test_an_unknown_candidate_policy_is_an_input_error(smoke):
    with pytest.raises(RegressionInputError, match="unknown policy 'nope-v1'"):
        run_regression(
            RegressionRequest(
                dataset=SMOKE, baseline=smoke["rules"], candidate=CandidateSpec(policy="nope-v1")
            )
        )


# ---- replay commands ----


def test_replay_commands_need_out_only_for_re_decided_runs(tmp_path):
    def command(candidate, baseline_at=None, out=None):
        request = RegressionRequest(
            dataset=Path("ds"),
            baseline=Path("b.jsonl"),
            candidate=candidate,
            baseline_at=baseline_at,
        )
        return replay_command_for(request, out)("C-1")

    head = "relay replay C-1 --traces b.jsonl --dataset ds"
    assert command(CandidateSpec(reproduce=True)) == head
    assert command(CandidateSpec(traces="c.jsonl")) == f"{head} --candidate-traces c.jsonl"
    assert command(CandidateSpec(policy="p", at=0.9)) == f"{head} --policy p --at 0.9"
    assert command(CandidateSpec(latest_policy=True)) == f"{head} --latest-policy"
    assert command(CandidateSpec(traces="c.jsonl", at=0.5)) is None
    assert command(CandidateSpec(traces="c.jsonl", at=0.5), out=tmp_path) == (
        f"{head} --candidate-traces {tmp_path / 'candidate.jsonl.gz'}"
    )
    assert command(CandidateSpec(at=0.9), baseline_at=0.8) is None
    assert command(CandidateSpec(at=0.9), baseline_at=0.8, out=tmp_path) == (
        f"relay replay C-1 --traces {tmp_path / 'baseline.jsonl.gz'} --dataset ds "
        f"--candidate-traces {tmp_path / 'candidate.jsonl.gz'}"
    )


# ---- artifacts ----


def test_write_outputs_writes_the_result_and_the_simulated_runs(tmp_path):
    request = RegressionRequest(
        dataset=GOLD,
        baseline=GOLD_JEV,
        baseline_at=0.95,
        candidate=CandidateSpec(at=0.89),
    )
    run = run_regression(request, out=tmp_path)
    paths = write_outputs(tmp_path, run, request, "rendered text")
    assert sorted(p.name for p in paths) == [
        "baseline.jsonl.gz",
        "baseline.manifest.json",
        "candidate.jsonl.gz",
        "candidate.manifest.json",
        "regression.json",
        "regression.md",
    ]
    assert (tmp_path / "regression.md").read_text() == "rendered text\n"
    assert json.loads((tmp_path / "regression.json").read_text())["verdict"] == "FAIL"
    candidate = read_traces(tmp_path / "candidate.jsonl.gz")
    assert len(candidate) == 100 and {t.mode for t in candidate} == {"simulated"}
    manifest = json.loads((tmp_path / "candidate.manifest.json").read_text())
    assert manifest["mode"] == "simulated"
    assert manifest["source_run_id"] == "run_20260925T170857Z_b95be9"
    assert manifest["policy_id"] == "immunara-v0.1"
    assert manifest["thresholds"]["version"] == "v0.1+at0.89"
    assert find_run_manifest(tmp_path / "candidate.jsonl.gz").case_count == 100
    with gzip.open(tmp_path / "baseline.jsonl.gz", "rt") as handle:
        assert len(handle.read().splitlines()) == 100


def test_a_reproduce_or_recorded_candidate_writes_no_trace_files(smoke, tmp_path):
    request = RegressionRequest(
        dataset=SMOKE, baseline=smoke["rules"], candidate=CandidateSpec(reproduce=True)
    )
    paths = write_outputs(tmp_path, run_regression(request), request, "x")
    assert sorted(p.name for p in paths) == ["regression.json", "regression.md"]


# ---- waiver and gates files ----


def test_a_malformed_waiver_file_is_an_input_error(tmp_path):
    path = tmp_path / "w.json"
    path.write_text('{"waivers": [{"case_id": "A"}]}')
    with pytest.raises(RegressionInputError, match="malformed waiver file"):
        load_waivers(path)
    path.write_text("not json")
    with pytest.raises(RegressionInputError, match="malformed waiver file"):
        load_waivers(path)


def test_a_gates_file_is_validated(tmp_path):
    path = tmp_path / "gates.json"
    gate = {"name": "g", "dataset": "d", "baseline": "b", "candidate": {"reproduce": True}}
    path.write_text(json.dumps({"gates": [gate]}))
    assert load_gates(path).gates[0].candidate.reproduce is True
    path.write_text(json.dumps({"gates": [gate, gate]}))
    with pytest.raises(RegressionInputError, match="duplicate gate names"):
        load_gates(path)
    bad = dict(gate, candidate={"reproduce": True, "at": 0.9})
    path.write_text(json.dumps({"gates": [bad]}))
    with pytest.raises(RegressionInputError, match="gate g: --reproduce"):
        load_gates(path)
    path.write_text(json.dumps({"gates": [dict(gate, surprise=1)]}))
    with pytest.raises(RegressionInputError, match="malformed gates file"):
        load_gates(path)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/integration/test_regression_run.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'relay.evaluation.regression_run'`.

- [ ] **Step 3: Implement**

Create `relay/evaluation/regression_run.py`:

```python
"""Running one regression gate: load the runs, build the candidate, diff, judge, write artifacts.

Offline only (spec G1): a candidate is an existing trace file or a policy replay of the
baseline's stored decisions, so nothing here builds a network client or needs a key. Every
problem with the inputs raises RegressionInputError, which the CLI maps to exit 2.
"""

import gzip
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from relay.cases.loader import CaseLoadError, load_dataset
from relay.cases.models import PriorAuthCase
from relay.cases.policies import latest_policy_for, load_policy
from relay.evaluation.metrics import EvalError
from relay.evaluation.regression import RegressionResult, Waiver, WaiverFile, build_result
from relay.evaluation.runner import sample_cases
from relay.evaluation.tracediff import (
    REPRODUCE_LABEL,
    candidate_trace_label,
    diff_runs,
    original_label,
    policy_replay_label,
    replay_run,
)
from relay.generation.manifest import dataset_hash, read_manifest
from relay.traces.models import RunManifest, WorkflowTrace
from relay.traces.store import read_traces

CANDIDATE_TRACES = "candidate.jsonl.gz"
CANDIDATE_MANIFEST = "candidate.manifest.json"
BASELINE_TRACES = "baseline.jsonl.gz"
BASELINE_MANIFEST = "baseline.manifest.json"


class RegressionInputError(ValueError):
    """The gate cannot run on these inputs (a usage or input error: exit 2)."""


class CandidateSpec(BaseModel):
    """Where the candidate comes from (spec G2). Exactly one of traces / policy / latest_policy /
    reproduce, or `at` alone (a policy replay of the baseline under its own policy at `at`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    traces: str | None = None
    policy: str | None = None
    latest_policy: bool = False
    at: float | None = None
    reproduce: bool = False

    @property
    def is_policy_replay(self) -> bool:
        return self.traces is None and not self.reproduce


class GateSpec(BaseModel):
    """One entry of evals/regression/gates.json. Paths are relative to the working directory
    (run from the repository root, as for `relay generate`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    dataset: str
    baseline: str
    candidate: CandidateSpec
    baseline_at: float | None = None
    max_regressed: int | None = Field(default=None, ge=0)
    waivers: str | None = None
    requires_generated: bool = False


class GatesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gates: list[GateSpec]


@dataclass(frozen=True)
class RegressionRequest:
    dataset: Path
    baseline: Path
    candidate: CandidateSpec
    baseline_at: float | None = None
    waivers: Path | None = None
    max_regressed: int | None = None
    gate: str | None = None

    @classmethod
    def from_gate(cls, spec: GateSpec) -> "RegressionRequest":
        return cls(
            dataset=Path(spec.dataset),
            baseline=Path(spec.baseline),
            candidate=spec.candidate,
            baseline_at=spec.baseline_at,
            waivers=None if spec.waivers is None else Path(spec.waivers),
            max_regressed=spec.max_regressed,
            gate=spec.name,
        )


@dataclass(frozen=True)
class RegressionRun:
    result: RegressionResult
    baseline: list[WorkflowTrace]  # after --baseline-at, if given
    candidate: list[WorkflowTrace]
    source_manifest: RunManifest | None  # the baseline's run manifest, if found
    dataset: Path


def validate_request(candidate: CandidateSpec, baseline_at: float | None) -> None:
    """The candidate-source rules of spec G2; RegressionInputError on a violation."""
    sources = [
        name
        for name, used in (
            ("--candidate-traces", candidate.traces is not None),
            ("--candidate-policy", candidate.policy is not None),
            ("--candidate-latest-policy", candidate.latest_policy),
            ("--reproduce", candidate.reproduce),
        )
        if used
    ]
    if len(sources) > 1:
        raise RegressionInputError("choose one candidate source, not " + " and ".join(sources))
    if candidate.reproduce and (candidate.at is not None or baseline_at is not None):
        raise RegressionInputError(
            "--reproduce replays the baseline as recorded; it cannot be combined with "
            "--candidate-at or --baseline-at"
        )
    if not sources and candidate.at is None:
        raise RegressionInputError(
            "no candidate: give --candidate-traces, --candidate-policy, "
            "--candidate-latest-policy, --candidate-at or --reproduce"
        )
    for flag, value in (("--candidate-at", candidate.at), ("--baseline-at", baseline_at)):
        if value is not None and not 0.0 < value <= 1.0:
            raise RegressionInputError(f"{flag} must be in (0, 1], got {value:g}")


def find_run_manifest(trace_file: Path) -> RunManifest | None:
    """The run manifest beside a trace file: <stem>.manifest.json (fresh runs, regression
    candidates) or run-manifest.json (committed baselines). None if neither exists."""
    stem = trace_file.name.removesuffix(".gz").removesuffix(".jsonl")
    for path in (
        trace_file.parent / f"{stem}.manifest.json",
        trace_file.parent / "run-manifest.json",
    ):
        if path.exists():
            try:
                return RunManifest.model_validate_json(path.read_text(encoding="utf-8"))
            except (ValidationError, OSError) as error:
                raise RegressionInputError(f"{path}: {error}") from error
    return None


def load_waivers(path: Path) -> list[Waiver]:
    try:
        return WaiverFile.model_validate_json(path.read_text(encoding="utf-8")).waivers
    except (ValidationError, OSError) as error:
        raise RegressionInputError(f"{path}: malformed waiver file: {error}") from error


def load_gates(path: Path) -> GatesConfig:
    try:
        config = GatesConfig.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValidationError, OSError) as error:
        raise RegressionInputError(f"{path}: malformed gates file: {error}") from error
    names = [g.name for g in config.gates]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise RegressionInputError(f"{path}: duplicate gate names {duplicates}")
    for spec in config.gates:
        try:
            validate_request(spec.candidate, spec.baseline_at)
        except RegressionInputError as error:
            raise RegressionInputError(f"{path}: gate {spec.name}: {error}") from error
    return config


def _dataset_hash(dataset: Path, cases: Sequence[PriorAuthCase]) -> str | None:
    """The committed manifest hash for a generated dataset (<dataset>/../manifests/<id>.json),
    checked against the cases on disk; None when there is no manifest."""
    path = dataset.parent / "manifests" / f"{cases[0].input.dataset_id}.json"
    if not path.exists():
        return None
    try:
        manifest = read_manifest(path)
    except (ValueError, OSError) as error:
        raise RegressionInputError(f"{path}: {error}") from error
    if manifest.dataset_hash != dataset_hash(cases):
        raise RegressionInputError(f"{dataset} does not match its manifest {path}")
    return manifest.dataset_hash


def _read(path: Path) -> list[WorkflowTrace]:
    try:
        traces = read_traces(path)
    except (ValueError, KeyError, OSError) as error:
        raise RegressionInputError(f"{path}: {error}") from error
    if not traces:
        raise RegressionInputError(f"{path}: no traces")
    return traces


def _load_cases(dataset: Path) -> list[PriorAuthCase]:
    try:
        cases = load_dataset(dataset)
    except CaseLoadError as error:
        raise RegressionInputError(str(error)) from error
    if not cases:
        raise RegressionInputError(f"{dataset}: no cases")
    return cases


def _candidate(
    request: RegressionRequest, baseline: list[WorkflowTrace], cases: list[PriorAuthCase]
) -> tuple[list[WorkflowTrace], str]:
    spec = request.candidate
    if spec.reproduce:
        return replay_run(baseline, cases, policy_id=None, auto_process=None), REPRODUCE_LABEL
    if spec.traces is not None:
        recorded = _read(Path(spec.traces))
        label = candidate_trace_label(recorded[0])
        if spec.at is None:
            return recorded, label
        replayed = replay_run(recorded, cases, policy_id=None, auto_process=spec.at)
        return replayed, f"{label} · re-decided at auto_process={spec.at:g}"
    if spec.latest_policy:
        try:
            target = latest_policy_for(baseline[0].policy_id)
        except KeyError as error:
            raise RegressionInputError(str(error.args[0])) from error
    else:
        target = spec.policy or baseline[0].policy_id
    replayed = replay_run(baseline, cases, policy_id=target, auto_process=spec.at)
    return replayed, policy_replay_label(load_policy(target), replayed[0].thresholds, spec.at)


def replay_command_for(request: RegressionRequest, out: Path | None) -> Callable[[str], str | None]:
    """A `relay replay` command that reproduces one case's diff, or None when it would need
    files that exist only with --out (a re-decided baseline or candidate)."""
    spec = request.candidate
    if request.baseline_at is None:
        traces: Path | None = request.baseline
    else:
        traces = None if out is None else out / BASELINE_TRACES
    if spec.reproduce:
        extra: str | None = ""
    elif spec.traces is not None and spec.at is None:
        extra = f" --candidate-traces {spec.traces}"
    elif spec.is_policy_replay and request.baseline_at is None:
        extra = (
            (f" --policy {spec.policy}" if spec.policy else "")
            + (" --latest-policy" if spec.latest_policy else "")
            + (f" --at {spec.at:g}" if spec.at is not None else "")
        )
    else:
        extra = None if out is None else f" --candidate-traces {out / CANDIDATE_TRACES}"
    if traces is None or extra is None:
        return lambda _case_id: None
    return lambda case_id: (
        f"relay replay {case_id} --traces {traces} --dataset {request.dataset}{extra}"
    )


def run_regression(request: RegressionRequest, *, out: Path | None = None) -> RegressionRun:
    """One gate, start to finish (writing nothing; see write_outputs)."""
    validate_request(request.candidate, request.baseline_at)
    cases = _load_cases(request.dataset)
    hash_ = _dataset_hash(request.dataset, cases)
    recorded = _read(request.baseline)
    source = find_run_manifest(request.baseline)
    if source is not None and source.sample_limit is not None:
        if source.sample_seed is None:
            raise RegressionInputError(f"{request.baseline}: run manifest has no sample_seed")
        cases = sample_cases(cases, source.sample_limit, source.sample_seed)
    waivers = [] if request.waivers is None else load_waivers(request.waivers)
    try:
        baseline = (
            recorded
            if request.baseline_at is None
            else replay_run(recorded, cases, policy_id=None, auto_process=request.baseline_at)
        )
        candidate, candidate_label = _candidate(request, recorded, cases)
        baseline_label = original_label(baseline[0])
        diffs = diff_runs(
            baseline,
            candidate,
            cases,
            original_label=baseline_label,
            candidate_label=candidate_label,
        )
        result = build_result(
            diffs,
            baseline,
            candidate,
            cases,
            baseline_label=baseline_label,
            candidate_label=candidate_label,
            gate=request.gate,
            reproduce=request.candidate.reproduce,
            waivers=waivers,
            max_regressed=request.max_regressed,
            dataset_hash=hash_,
            replay_command=replay_command_for(request, out),
        )
    except EvalError as error:
        raise RegressionInputError(str(error)) from error
    return RegressionRun(
        result=result,
        baseline=baseline,
        candidate=candidate,
        source_manifest=source,
        dataset=request.dataset,
    )


def _write_traces(path: Path, traces: Sequence[WorkflowTrace]) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for trace in traces:
            handle.write(trace.model_dump_json() + "\n")


def _write_simulated_run(
    run: RegressionRun, traces: Sequence[WorkflowTrace], trace_path: Path, manifest_path: Path
) -> None:
    """A simulated run that `relay eval --traces`, `compare` and `replay` can read: gzipped
    traces plus a RunManifest with extra keys mode, source_run_id, policy_id and thresholds."""
    _write_traces(trace_path, traces)
    first = traces[0]
    source = run.source_manifest
    manifest = RunManifest(
        run_id=first.run_id,
        created_at=datetime.now(UTC),
        dataset_id=first.dataset_id,
        dataset_path=str(run.dataset),
        provider=first.provider,
        policy_version=first.policy_version,
        question_set_version=first.question_set_version,
        case_count=len(traces),
        trace_file=str(trace_path),
        relay_git_sha=first.relay_git_sha,
        sample_limit=None if source is None else source.sample_limit,
        sample_seed=None if source is None else source.sample_seed,
    )
    data = manifest.model_dump(mode="json") | {
        "mode": "simulated",
        "source_run_id": first.run_id.removeprefix("replay-"),
        "policy_id": first.policy_id,
        "thresholds": first.thresholds.model_dump(mode="json"),
    }
    manifest_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_outputs(
    out: Path, run: RegressionRun, request: RegressionRequest, rendered: str
) -> list[Path]:
    """regression.json and regression.md (the terminal text), plus the simulated runs the
    replay commands point at: candidate.* for a replayed candidate, baseline.* after
    --baseline-at. Returns the paths written."""
    out.mkdir(parents=True, exist_ok=True)
    paths = [out / "regression.json", out / "regression.md"]
    paths[0].write_text(run.result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    paths[1].write_text(rendered + "\n", encoding="utf-8")
    spec = request.candidate
    if spec.is_policy_replay or (spec.traces is not None and spec.at is not None):
        pair = (out / CANDIDATE_TRACES, out / CANDIDATE_MANIFEST)
        _write_simulated_run(run, run.candidate, *pair)
        paths += pair
    if request.baseline_at is not None:
        pair = (out / BASELINE_TRACES, out / BASELINE_MANIFEST)
        _write_simulated_run(run, run.baseline, *pair)
        paths += pair
    return paths
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add relay/evaluation/regression_run.py tests/integration/test_regression_run.py
git commit -m "feat: run a regression gate offline: candidates, sampling, artifacts" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Rendering the regression report and the gate summary

**Files:**
- Modify: `relay/reporting.py` (imports; append)
- Create: `tests/unit/test_reporting_regression.py`

**Interfaces:**
- Consumes: `RegressionResult`, `CaseEntry`, `Rate` and `CHANGE_ORDER` (Task 6).
- Produces (in `relay.reporting`):
  - `render_regression(result: RegressionResult, *, show_all: bool = False) -> str`
  - `gate_line(result) -> str`
  - `GateRow(name, verdict, newly_unsafe, regressed, exit_code, note=None)` (a frozen dataclass)
  - `render_gate_summary(rows) -> str`
  - `PASS_LINE`, `REGRESSED_SHOWN = 20`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_reporting_regression.py`:

```python
"""render_regression and render_gate_summary: the terminal output of `relay regression`."""

import re

from relay.evaluation.regression import Waiver, build_result
from relay.evaluation.tracediff import diff_runs, replay_run
from relay.reporting import GateRow, render_gate_summary, render_regression
from tests.factories import make_bundle, make_case, make_trace, make_truth


def result_for(*, waivers=(), reproduce=False, auto_process=0.9, replay=True):
    """T-01 improves, T-02 and T-03 become newly unsafe at `auto_process` (see test_regression)."""
    cases = [
        make_case("T-01"),
        make_case("T-02", truth=make_truth(step_therapy_satisfied=False)),
        make_case("T-03", truth=make_truth(step_therapy_satisfied=False)),
    ]
    baseline = [make_trace(c, make_bundle(c.input.id, step=0.93)) for c in cases]
    candidate = replay_run(
        baseline, cases, policy_id=None, auto_process=None if reproduce else auto_process
    )
    diffs = diff_runs(baseline, candidate, cases, original_label="base", candidate_label="cand")
    return build_result(
        diffs,
        baseline,
        candidate,
        cases,
        baseline_label="base run",
        candidate_label="cand run",
        gate="g1",
        reproduce=reproduce,
        waivers=list(waivers),
        max_regressed=None,
        replay_command=(lambda case_id: f"relay replay {case_id} --at 0.9") if replay else None,
    )


def waiver(case_id):
    return Waiver(
        case_id=case_id, gate="*", reason="reviewed", approved_by="rev", date="2026-09-26"
    )


def test_header_metrics_and_counts():
    text = render_regression(result_for())
    lines = text.splitlines()
    assert lines[:3] == [
        "Relay regression — gate g1 · dataset test · n=3",
        "BASELINE  base run",
        "CANDIDATE cand run",
    ]
    assert re.search(r"Automation rate\s+0/3 \(0\.0%\)\s+3/3 \(100\.0%\)\s+\+100\.0 pp", text)
    assert re.search(r"Unsafe automation rate\s+n/a\s+2/3 \(66\.7%\)\s+n/a\s+n/a\s+\[", text)
    assert (
        "CHANGES: improved 1 · unchanged 0 · regressed 2 · changed-both-wrong 0 · not identical 3"
    ) in lines


def test_newly_unsafe_comes_first_with_a_replay_command_and_the_gate_line_is_last():
    text = render_regression(result_for())
    lines = text.splitlines()
    assert lines.index("NEWLY UNSAFE (2)") < lines.index("REGRESSED (2)")
    assert "  T-02  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS" in lines
    assert "      answer changed: none · gated crossings: step_therapy: auto_process" in lines
    assert "      replay: relay replay T-02 --at 0.9" in lines
    assert (
        lines[-1] == "REGRESSION GATE: FAIL — 2 newly unsafe case(s) without a waiver: T-02, T-03"
    )
    assert "CALIBRATION (Δ = candidate − baseline)" in lines


def test_a_case_without_a_replay_command_says_how_to_get_one():
    text = render_regression(result_for(replay=False))
    assert "      replay: re-run with --out DIR for a replayable command" in text


def test_waived_and_stale_waivers_are_listed():
    text = render_regression(result_for(waivers=[waiver("T-02"), waiver("T-03"), waiver("OLD")]))
    lines = text.splitlines()
    assert "NEWLY UNSAFE" not in text.replace("WAIVED NEWLY UNSAFE", "")
    assert "WAIVED NEWLY UNSAFE (2) — reviewed, not failures" in lines
    assert "      waiver: reviewed (approved by rev, 2026-09-26, gate *)" in lines
    assert "STALE WAIVERS (1) — warning: no newly unsafe case" in lines
    assert "  OLD (gate *, approved by rev, 2026-09-26)" in lines
    assert lines[-1] == "REGRESSION GATE: PASS"


def test_reproduce_prints_its_note_and_passes_when_identical():
    text = render_regression(result_for(reproduce=True))
    assert "REPRODUCE: the baseline's stored decisions under the current engine" in text
    assert "ENGINE DRIFT" in text  # only in the note
    assert "ENGINE DRIFT (" not in text
    assert text.splitlines()[-1] == "REGRESSION GATE: PASS"


def test_regressed_cases_are_capped_at_20_unless_all():
    result = result_for()
    many = [result.regressed[0].model_copy(update={"case_id": f"R-{i:02d}"}) for i in range(25)]
    result = result.model_copy(update={"regressed": many})
    text = render_regression(result)
    assert "REGRESSED (25) — showing 20; --all shows every case" in text
    assert "  R-19  " in text and "  R-20  " not in text
    full = render_regression(result, show_all=True)
    assert "REGRESSED (25)" in full.splitlines() and "  R-24  " in full


def test_gate_summary_table():
    text = render_gate_summary(
        [
            GateRow("gold-reproduce-jev", "PASS", 0, 0, 0),
            GateRow(
                "holdout-reproduce-jev", "SKIPPED", None, None, 0, note="dataset not generated"
            ),
        ]
    )
    lines = text.splitlines()
    assert lines[0] == "REGRESSION GATES"
    assert re.match(r"GATE\s+VERDICT\s+NEWLY UNSAFE\s+REGRESSED\s+EXIT", lines[1])
    assert re.match(r"gold-reproduce-jev\s+PASS\s+0\s+0\s+0", lines[2])
    assert re.match(
        r"holdout-reproduce-jev\s+SKIPPED \(dataset not generated\)\s+—\s+—\s+0", lines[3]
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/test_reporting_regression.py`
Expected: FAIL with `ImportError: cannot import name 'GateRow' from 'relay.reporting'`.

- [ ] **Step 3: Implement**

In `relay/reporting.py`:

1. Add `from dataclasses import dataclass` after `from collections.abc import Iterable, Mapping, Sequence`.
2. Add `from relay.evaluation.regression import CHANGE_ORDER, CaseEntry, Rate, RegressionResult` after `from relay.evaluation.metrics import EvalSummary, RunIdentity`.
3. Append to the end of the file:

```python


# ---- relay regression ----

REGRESSED_SHOWN = 20
PASS_LINE = "REGRESSION GATE: PASS"
REPRODUCE_NOTE = (
    "REPRODUCE: the baseline's stored decisions under the current engine, policy and "
    "thresholds; any case that is not identical is ENGINE DRIFT"
)


def _rate_cell(r: Rate) -> str:
    return "n/a" if r.rate is None else f"{r.count}/{r.n} ({r.rate:.1%})"


def _ci_cell(r: Rate) -> str:
    return "n/a" if r.ci95 is None else f"[{r.ci95.low:.1%}, {r.ci95.high:.1%}]"


def _pp(before: Rate, after: Rate) -> str:
    if before.rate is None or after.rate is None:
        return "n/a"
    return f"{(after.rate - before.rate) * 100:+.1f} pp"


def _signed(value: float | None) -> str:
    return "—" if value is None else f"{value:+.3f}"


def _metrics_lines(result: RegressionResult) -> list[str]:
    b, c = result.baseline, result.candidate
    rows = [["METRIC", "BASELINE", "CANDIDATE", "Δ", "BASELINE 95% CI", "CANDIDATE 95% CI"]]
    for name, before, after in (
        ("Correct action rate", b.correct, c.correct),
        ("Automation rate", b.automation, c.automation),
        ("Request-info rate", b.request_info, c.request_info),
        ("Human escalation rate", b.human_review, c.human_review),
        ("Unsafe automation rate", b.uar, c.uar),
    ):
        rows.append(
            [
                name,
                _rate_cell(before),
                _rate_cell(after),
                _pp(before, after),
                _ci_cell(before),
                _ci_cell(after),
            ]
        )
    rows.append(
        [
            "Invalid outputs",
            str(b.invalid_outputs),
            str(c.invalid_outputs),
            f"{c.invalid_outputs - b.invalid_outputs:+d}",
            "",
            "",
        ]
    )
    return _table(rows)


def _entry_lines(entry: CaseEntry) -> list[str]:
    expected = f"expected {entry.expected}"
    if entry.expected_candidate is not None:
        expected += f" (candidate policy: {entry.expected_candidate})"
    crossed = "; ".join(f"{q}: {', '.join(names)}" for q, names in entry.crossed_gated.items())
    lines = [
        f"  {entry.case_id}  {expected}  {entry.action_baseline} → {entry.action_candidate}",
        f"      answer changed: {', '.join(entry.answer_changed) or 'none'}"
        f" · gated crossings: {crossed or 'none'}",
    ]
    if entry.replay_command is not None:
        lines.append(f"      replay: {entry.replay_command}")
    else:
        lines.append("      replay: re-run with --out DIR for a replayable command")
    return lines


def _section(title: str, entries: Sequence[CaseEntry], limit: int | None = None) -> list[str]:
    if not entries:
        return []
    shown = entries if limit is None else entries[:limit]
    header = f"{title} ({len(entries)})"
    if len(shown) < len(entries):
        header += f" — showing {len(shown)}; --all shows every case"
    lines = ["", header]
    for entry in shown:
        lines += _entry_lines(entry)
    return lines


def _calibration_lines(result: RegressionResult) -> list[str]:
    rows = [["DECISION", "BRIER (BASE → CAND)", "Δ BRIER", "ECE (BASE → CAND)", "Δ ECE"]]
    for c in result.calibration:
        rows.append(
            [
                c.decision,
                f"{_num(c.brier_baseline)} → {_num(c.brier_candidate)}",
                _signed(c.brier_delta),
                f"{_num(c.ece_baseline)} → {_num(c.ece_candidate)}",
                _signed(c.ece_delta),
            ]
        )
    return ["", "CALIBRATION (Δ = candidate − baseline)"] + [" " + line for line in _table(rows)]


def gate_line(result: RegressionResult) -> str:
    if result.verdict == "PASS":
        return PASS_LINE
    return "REGRESSION GATE: FAIL — " + "; ".join(result.failures)


def render_regression(result: RegressionResult, *, show_all: bool = False) -> str:
    """Terminal output for `relay regression` (and regression.md): header, metrics with 95%
    Clopper-Pearson intervals, change counts, then NEWLY UNSAFE first, each with a replay
    command, waived and stale waivers, UNSAFE RESOLVED, REGRESSED (20 unless show_all),
    calibration deltas and the gate line last."""
    title = f"Relay regression — dataset {result.dataset_id} · n={result.n}"
    if result.gate is not None:
        title = (
            f"Relay regression — gate {result.gate} · dataset {result.dataset_id} · n={result.n}"
        )
    lines = [title, f"BASELINE  {result.baseline.label}", f"CANDIDATE {result.candidate.label}"]
    if result.reproduce:
        lines.append(REPRODUCE_NOTE)
    lines += [""] + _metrics_lines(result)
    counts = " · ".join(f"{name} {result.change_counts[name]}" for name in CHANGE_ORDER)
    lines += ["", f"CHANGES: {counts} · not identical {result.not_identical}"]
    limit = None if show_all else REGRESSED_SHOWN
    lines += _section("ENGINE DRIFT", result.drifted, limit)
    lines += _section("NEWLY UNSAFE", result.newly_unsafe)
    if result.waived:
        lines += ["", f"WAIVED NEWLY UNSAFE ({len(result.waived)}) — reviewed, not failures"]
        for waived in result.waived:
            w = waived.waiver
            lines += _entry_lines(waived.entry)
            lines.append(
                f"      waiver: {w.reason} (approved by {w.approved_by}, {w.date}, gate {w.gate})"
            )
    if result.stale_waivers:
        lines += [
            "",
            f"STALE WAIVERS ({len(result.stale_waivers)}) — warning: no newly unsafe case",
        ]
        lines += [
            f"  {w.case_id} (gate {w.gate}, approved by {w.approved_by}, {w.date})"
            for w in result.stale_waivers
        ]
    lines += _section("UNSAFE RESOLVED", result.unsafe_resolved)
    lines += _section("REGRESSED", result.regressed, limit)
    lines += _calibration_lines(result)
    lines += ["", gate_line(result)]
    return "\n".join(lines)


@dataclass(frozen=True)
class GateRow:
    """One row of the `relay regression --config` summary."""

    name: str
    verdict: str  # PASS, FAIL, SKIPPED or ERROR
    newly_unsafe: int | None
    regressed: int | None
    exit_code: int
    note: str | None = None


def render_gate_summary(rows: Sequence[GateRow]) -> str:
    table = [["GATE", "VERDICT", "NEWLY UNSAFE", "REGRESSED", "EXIT"]]
    for r in rows:
        table.append(
            [
                r.name,
                r.verdict if r.note is None else f"{r.verdict} ({r.note})",
                "—" if r.newly_unsafe is None else str(r.newly_unsafe),
                "—" if r.regressed is None else str(r.regressed),
                str(r.exit_code),
            ]
        )
    return "\n".join(["REGRESSION GATES", *_table(table)])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add relay/reporting.py tests/unit/test_reporting_regression.py
git commit -m "feat: render the regression report and the gate summary" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: The `relay regression` command (single-run and `--config` modes)

**Files:**
- Modify: `relay/cli.py` (module docstring, imports; append the command)
- Create: `tests/integration/test_cli_regression.py`

**Interfaces:**
- Consumes:
  - `CandidateSpec`, `RegressionInputError`, `RegressionRequest`, `load_gates`, `run_regression` and `write_outputs` (Task 7)
  - `RegressionResult` (Task 6)
  - `GateRow`, `render_gate_summary` and `render_regression` (Task 8)
- Produces the CLI:
  - `relay regression --dataset DIR --baseline FILE (--candidate-traces FILE | --candidate-policy ID | --candidate-latest-policy | --candidate-at X | --reproduce) [--baseline-at X] [--waivers FILE] [--max-regressed N] [--out DIR] [--json] [--all]`
  - `relay regression --config FILE [--gate NAME ...] [--out DIR] [--all]`
- Exit codes: 0 PASS, 2 input or usage error, 3 engine drift, 4 FAIL. Config mode exits with the highest code across gates.

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_cli_regression.py`:

```python
"""relay regression, offline: smoke runs from the groundtruth and rules providers and the
committed gold traces. Never builds a network client."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import relay.cli as cli_module
import relay.evaluation.tracediff as tracediff
from relay.cli import app
from relay.evaluation.regression import RegressionResult

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
GOLD = REPO / "evals" / "gold"
GOLD_RUNS = REPO / "evals" / "baselines" / "gold-v0.1"
GOLD_JEV = GOLD_RUNS / "run_20260925T170857Z_b95be9" / "traces.jsonl.gz"
GOLD_CLAUDE = GOLD_RUNS / "run_20260926T011730Z_f1852f" / "traces.jsonl.gz"
runner = CliRunner()


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--env-file", str(tmp_path / "missing.env"), *map(str, args)])


def regression(tmp_path, *args):
    return invoke(tmp_path, "regression", *args)


@pytest.fixture(scope="module")
def smoke_runs(tmp_path_factory):
    root = tmp_path_factory.mktemp("regression-cli")
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


def waiver_file(tmp_path, case_id="GOLD-TMP-17", gate="*"):
    path = tmp_path / "waivers.json"
    waiver = {
        "case_id": case_id,
        "gate": gate,
        "reason": "accepted after review",
        "approved_by": "reviewer",
        "date": "2026-09-26",
    }
    path.write_text(json.dumps({"waivers": [waiver]}), encoding="utf-8")
    return path


GOLD_DEMO = ["--dataset", GOLD, "--baseline", GOLD_JEV, "--candidate-at", "0.89"]


# ---- the gold demonstration ----


def test_the_gold_demo_fails_with_exit_4_and_names_gold_tmp_17(tmp_path):
    result = regression(tmp_path, *GOLD_DEMO)
    assert result.exit_code == 4, result.output
    lines = result.output.splitlines()
    assert "NEWLY UNSAFE (1)" in lines
    assert "  GOLD-TMP-17  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS" in lines
    assert (
        f"      replay: relay replay GOLD-TMP-17 --traces {GOLD_JEV} --dataset {GOLD} --at 0.89"
        in lines
    )
    assert lines[-1] == (
        "REGRESSION GATE: FAIL — 1 newly unsafe case(s) without a waiver: GOLD-TMP-17"
    )


def test_the_gold_demo_passes_with_a_waiver(tmp_path):
    result = regression(tmp_path, *GOLD_DEMO, "--waivers", waiver_file(tmp_path))
    assert result.exit_code == 0, result.output
    assert "WAIVED NEWLY UNSAFE (1) — reviewed, not failures" in result.output
    assert result.output.splitlines()[-1] == "REGRESSION GATE: PASS"


def test_a_stale_waiver_is_a_warning_not_a_failure(tmp_path):
    result = regression(
        tmp_path,
        "--dataset",
        GOLD,
        "--baseline",
        GOLD_JEV,
        "--reproduce",
        "--waivers",
        waiver_file(tmp_path),
    )
    assert result.exit_code == 0, result.output
    assert "STALE WAIVERS (1) — warning: no newly unsafe case" in result.output


def test_claude_versus_jev_on_gold_at_each_operating_point_passes(tmp_path):
    result = regression(
        tmp_path,
        "--dataset",
        GOLD,
        "--baseline",
        GOLD_JEV,
        "--baseline-at",
        "0.89",
        "--candidate-traces",
        GOLD_CLAUDE,
        "--candidate-at",
        "0.55",
    )
    assert result.exit_code == 0, result.output
    assert (
        "CHANGES: improved 3 · unchanged 96 · regressed 1 · changed-both-wrong 0" in result.output
    )
    assert "NEWLY UNSAFE" not in result.output


def test_max_regressed(tmp_path):
    over = regression(
        tmp_path, *GOLD_DEMO, "--waivers", waiver_file(tmp_path), "--max-regressed", "0"
    )
    assert over.exit_code == 4, over.output
    assert over.output.splitlines()[-1] == (
        "REGRESSION GATE: FAIL — 1 regressed case(s), more than --max-regressed 0"
    )
    ok = regression(
        tmp_path, *GOLD_DEMO, "--waivers", waiver_file(tmp_path), "--max-regressed", "1"
    )
    assert ok.exit_code == 0, ok.output


# ---- smoke runs ----


def test_candidate_traces_on_smoke(tmp_path, smoke_runs):
    result = regression(
        tmp_path,
        "--dataset",
        SMOKE,
        "--baseline",
        smoke_runs["groundtruth"],
        "--candidate-traces",
        smoke_runs["rules"],
    )
    assert result.exit_code == 0, result.output
    assert "REGRESSED (1)" in result.output
    assert "  AUTO-03  expected AUTO_PROCESS  AUTO_PROCESS → REQUEST_INFO" in result.output
    assert f"--candidate-traces {smoke_runs['rules']}" in result.output


def test_reproduce_passes_and_engine_drift_exits_3(tmp_path, smoke_runs, monkeypatch):
    args = ["--dataset", SMOKE, "--baseline", smoke_runs["groundtruth"], "--reproduce"]
    ok = regression(tmp_path, *args)
    assert ok.exit_code == 0, ok.output
    real = tracediff.determine_action

    def drifted(case, bundle, policy, thresholds):
        outcome = real(case, bundle, policy, thresholds)
        if case.id != "AUTO-01":
            return outcome
        return outcome.model_copy(update={"reasons": [*outcome.reasons, "a new reason"]})

    monkeypatch.setattr(tracediff, "determine_action", drifted)
    drift = regression(tmp_path, *args)
    assert drift.exit_code == 3, drift.output
    assert "ENGINE DRIFT (1)" in drift.output
    assert drift.output.splitlines()[-1] == (
        "REGRESSION GATE: FAIL — ENGINE DRIFT: 1 case(s) not reproduced: AUTO-01"
    )


def test_json_prints_only_the_result(tmp_path):
    result = regression(tmp_path, *GOLD_DEMO, "--json")
    assert result.exit_code == 4
    parsed = RegressionResult.model_validate_json(result.stdout)
    assert [e.case_id for e in parsed.newly_unsafe] == ["GOLD-TMP-17"]
    assert parsed.verdict == "FAIL"


def test_out_writes_artifacts_that_relay_eval_can_read(tmp_path, smoke_runs):
    out = tmp_path / "report"
    result = regression(
        tmp_path,
        "--dataset",
        SMOKE,
        "--baseline",
        smoke_runs["rules"],
        "--candidate-at",
        "0.5",
        "--out",
        out,
    )
    assert result.exit_code == 0, result.output
    assert (out / "regression.md").read_text(encoding="utf-8") == result.output
    assert json.loads((out / "regression.json").read_text())["dataset_id"] == "smoke-v0.1"
    manifest = json.loads((out / "candidate.manifest.json").read_text())
    assert (manifest["mode"], manifest["source_run_id"]) == ("simulated", smoke_runs["rules"].stem)
    rescored = invoke(
        tmp_path,
        "eval",
        "--dataset",
        SMOKE,
        "--traces",
        out / "candidate.jsonl.gz",
        "--results-dir",
        tmp_path / "results",
    )
    assert rescored.exit_code == 0, rescored.output
    assert "policy v0.1 · dataset smoke-v0.1 · n=10" in rescored.output


# ---- usage errors ----


@pytest.mark.parametrize(
    "flags,message",
    [
        (["--reproduce", "--candidate-at", "0.9"], "cannot be combined"),
        (["--reproduce", "--baseline-at", "0.9"], "cannot be combined"),
        (["--candidate-traces", "BASE", "--candidate-policy", "p"], "choose one candidate source"),
        (["--candidate-policy", "p", "--candidate-latest-policy"], "choose one candidate source"),
        ([], "no candidate"),
        (["--candidate-at", "0"], "--candidate-at must be in (0, 1]"),
        (["--candidate-at", "1.5"], "--candidate-at must be in (0, 1]"),
        (["--reproduce", "--gate", "g"], "--gate needs --config"),
    ],
)
def test_bad_flag_combinations_are_exit_2(tmp_path, smoke_runs, flags, message):
    flags = [str(smoke_runs["rules"]) if f == "BASE" else f for f in flags]
    result = regression(
        tmp_path, "--dataset", SMOKE, "--baseline", smoke_runs["groundtruth"], *flags
    )
    assert result.exit_code == 2, result.output
    assert message in result.output


def test_dataset_and_baseline_are_required_without_config(tmp_path):
    result = regression(tmp_path, "--reproduce")
    assert result.exit_code == 2
    assert "give --dataset and --baseline, or --config" in result.output


def test_a_malformed_waiver_file_is_exit_2(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"waivers": [{"case_id": "GOLD-TMP-17", "gate": "*"}]}')
    result = regression(tmp_path, *GOLD_DEMO, "--waivers", bad)
    assert result.exit_code == 2
    assert "malformed waiver file" in result.output


class NoNetworkClient:
    def __init__(self, *args, **kwargs):
        raise AssertionError("regression constructed a network client")


def test_regression_needs_no_key_and_builds_no_client(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", NoNetworkClient)
    monkeypatch.setattr(cli_module, "AsyncAnthropic", NoNetworkClient)
    assert regression(tmp_path, *GOLD_DEMO).exit_code == 4


# ---- config mode ----


def gates_file(tmp_path, *gates):
    path = tmp_path / "gates.json"
    path.write_text(json.dumps({"gates": list(gates)}), encoding="utf-8")
    return path


def gate(name, baseline, candidate, dataset=SMOKE, **extra):
    return {
        "name": name,
        "dataset": str(dataset),
        "baseline": str(baseline),
        "candidate": candidate,
        **extra,
    }


@pytest.fixture
def three_gates(tmp_path, smoke_runs):
    return gates_file(
        tmp_path,
        gate("smoke-reproduce", smoke_runs["rules"], {"reproduce": True}),
        gate("gold-demo", GOLD_JEV, {"at": 0.89}, dataset=GOLD),
        gate(
            "not-generated",
            smoke_runs["rules"],
            {"reproduce": True},
            dataset=tmp_path / "evals" / "generated" / "nope",
            requires_generated=True,
        ),
    )


def test_config_runs_every_gate_and_exits_with_the_highest_code(tmp_path, three_gates):
    result = regression(tmp_path, "--config", three_gates)
    assert result.exit_code == 4, result.output
    assert "Relay regression — gate smoke-reproduce · dataset smoke-v0.1 · n=10" in result.output
    assert "Relay regression — gate gold-demo · dataset gold-v0.1 · n=100" in result.output
    assert "gate not-generated: SKIPPED (dataset not generated; run relay generate" in result.output
    summary = result.output[result.output.index("REGRESSION GATES") :]
    assert "smoke-reproduce" in summary and "gold-demo" in summary and "SKIPPED" in summary


def test_config_gate_filter(tmp_path, three_gates):
    result = regression(tmp_path, "--config", three_gates, "--gate", "smoke-reproduce")
    assert result.exit_code == 0, result.output
    assert "gold-demo" not in result.output
    unknown = regression(tmp_path, "--config", three_gates, "--gate", "nope")
    assert unknown.exit_code == 2
    assert "no gate named nope" in unknown.output


def test_config_out_writes_one_directory_per_gate_and_a_summary(tmp_path, three_gates):
    out = tmp_path / "regression-report"
    regression(tmp_path, "--config", three_gates, "--out", out)
    assert (out / "smoke-reproduce" / "regression.json").exists()
    assert (out / "gold-demo" / "candidate.jsonl.gz").exists()
    assert not (out / "not-generated").exists()
    assert (out / "summary.md").read_text().startswith("REGRESSION GATES")


def test_a_gate_with_bad_inputs_is_an_error_row_and_the_rest_still_run(tmp_path, smoke_runs):
    path = gates_file(
        tmp_path,
        gate("broken", tmp_path / "missing.jsonl", {"reproduce": True}),
        gate("fine", smoke_runs["rules"], {"reproduce": True}),
    )
    result = regression(tmp_path, "--config", path)
    assert result.exit_code == 2
    assert "Relay regression — gate fine · dataset smoke-v0.1" in result.output
    assert "gate broken: ERROR:" in result.output


def test_config_rejects_single_run_flags(tmp_path, three_gates):
    result = regression(tmp_path, "--config", three_gates, "--dataset", SMOKE)
    assert result.exit_code == 2
    assert "--dataset cannot be combined with --config" in result.output
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/integration/test_cli_regression.py`
Expected: FAIL. Typer reports `No such command 'regression'` (exit code 2) and the assertions fail.

- [ ] **Step 3: Implement**

In `relay/cli.py`:

1. Change the module docstring's first line to:

```python
"""relay run / eval / generate, and the offline analyses sweep / report / compare / replay /
regression."""
```

2. After `from relay.evaluation.metrics import EvalError, run_identity, score_run`, add:

```python
from relay.evaluation.regression import RegressionResult
from relay.evaluation.regression_run import (
    CandidateSpec,
    RegressionInputError,
    RegressionRequest,
    load_gates,
    run_regression,
    write_outputs,
)
```

3. In the `from relay.reporting import (...)` list, add `GateRow,` after `RULES_NOTE,`. Add `render_gate_summary,` and `render_regression,` after `render_frontier_table,`.

4. Append to the end of the file:

```python


GatesFile = Annotated[
    Path | None,
    typer.Option(
        "--config",
        exists=True,
        dir_okay=False,
        help="Run every gate in this gates file (e.g. evals/regression/gates.json).",
    ),
]


def _gate_row(name: str, result: RegressionResult) -> GateRow:
    return GateRow(
        name=name,
        verdict=result.verdict,
        newly_unsafe=len(result.newly_unsafe),
        regressed=len(result.regressed),
        exit_code=result.exit_code,
    )


def _run_gate(
    request: RegressionRequest, out: Path | None, show_all: bool
) -> tuple[RegressionResult, str]:
    """Run one gate, write its --out files, return the result and its rendered report."""
    run = run_regression(request, out=out)
    rendered = render_regression(run.result, show_all=show_all)
    if out is not None:
        write_outputs(out, run, request, rendered)
    return run.result, rendered


def _regression_config(config: Path, names: list[str], out: Path | None, show_all: bool) -> int:
    """Config mode: every gate (or the --gate ones), each report, then a summary. Returns the
    highest exit code. A gate with requires_generated whose dataset is missing is SKIPPED; any
    other input error is that gate's ERROR (exit 2) and the remaining gates still run."""
    try:
        gates = load_gates(config).gates
    except RegressionInputError as error:
        raise _fail(str(error)) from error
    unknown = sorted(set(names) - {g.name for g in gates})
    if unknown:
        raise _fail(f"no gate named {', '.join(unknown)} in {config}")
    selected = [g for g in gates if not names or g.name in names]
    rows: list[GateRow] = []
    for spec in selected:
        if spec.requires_generated and not Path(spec.dataset).is_dir():
            note = f"dataset not generated; run relay generate to create {spec.dataset}"
            typer.echo(f"Relay regression — gate {spec.name}: SKIPPED ({note})\n")
            rows.append(GateRow(spec.name, "SKIPPED", None, None, 0, note=note))
            continue
        gate_out = None if out is None else out / spec.name
        try:
            result, rendered = _run_gate(RegressionRequest.from_gate(spec), gate_out, show_all)
        except RegressionInputError as error:
            typer.echo(f"Relay regression — gate {spec.name}: ERROR: {error}\n", err=True)
            rows.append(GateRow(spec.name, "ERROR", None, None, 2, note=str(error)[:80]))
            continue
        typer.echo(rendered + "\n")
        rows.append(_gate_row(spec.name, result))
    summary = render_gate_summary(rows)
    typer.echo(summary)
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        (out / "summary.md").write_text(summary + "\n", encoding="utf-8")
    return max((r.exit_code for r in rows), default=0)


@app.command()
def regression(
    dataset: Annotated[
        Path | None, typer.Option(file_okay=False, help="Directory of case folders.")
    ] = None,
    baseline: Annotated[
        Path | None, typer.Option(dir_okay=False, help="The accepted baseline's trace file.")
    ] = None,
    candidate_traces: Annotated[
        Path | None, typer.Option(dir_okay=False, help="Candidate: another run's trace file.")
    ] = None,
    candidate_policy: Annotated[
        str | None,
        typer.Option(help="Candidate: the baseline's stored decisions under this policy id."),
    ] = None,
    candidate_latest_policy: Annotated[
        bool,
        typer.Option(
            "--candidate-latest-policy",
            help="Candidate: the stored decisions under the newest policy for the medication.",
        ),
    ] = False,
    candidate_at: Annotated[
        float | None,
        typer.Option(
            help="Candidate auto_process threshold, in (0, 1]. Alone: a policy replay of the "
            "baseline under its own policy at this threshold."
        ),
    ] = None,
    reproduce: Annotated[
        bool,
        typer.Option(
            "--reproduce",
            help="Engine-drift gate: the stored decisions under today's engine; any "
            "difference fails with exit 3.",
        ),
    ] = False,
    baseline_at: Annotated[
        float | None,
        typer.Option(help="Re-decide the baseline at this auto_process threshold, in (0, 1]."),
    ] = None,
    waivers: Annotated[
        Path | None,
        typer.Option(exists=True, dir_okay=False, help="Waiver file for newly unsafe cases."),
    ] = None,
    max_regressed: Annotated[
        int | None, typer.Option(min=0, help="Fail when more cases than this regress.")
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option(help="Write regression.json, regression.md and any replayed runs here."),
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Print the RegressionResult as JSON and nothing else.")
    ] = False,
    show_all: Annotated[
        bool, typer.Option("--all", help="List every regressed case, not only the first 20.")
    ] = False,
    config: GatesFile = None,
    gate: Annotated[
        list[str] | None,
        typer.Option("--gate", help="Config mode: run only this gate (repeatable)."),
    ] = None,
) -> None:
    """Gate a candidate against an accepted baseline on the same frozen dataset (offline).

    Exit codes: 0 PASS; 2 usage/input error; 3 ENGINE DRIFT (--reproduce); 4 FAIL (a newly
    unsafe case without a waiver, or more regressions than --max-regressed).
    """
    if config is not None:
        single = {
            "--dataset": dataset,
            "--baseline": baseline,
            "--candidate-traces": candidate_traces,
            "--candidate-policy": candidate_policy,
            "--candidate-latest-policy": candidate_latest_policy or None,
            "--candidate-at": candidate_at,
            "--reproduce": reproduce or None,
            "--baseline-at": baseline_at,
            "--waivers": waivers,
            "--max-regressed": max_regressed,
            "--json": json_output or None,
        }
        given = [flag for flag, value in single.items() if value is not None]
        if given:
            raise _fail(f"{', '.join(given)} cannot be combined with --config")
        code = _regression_config(config, gate or [], out, show_all)
        if code:
            raise typer.Exit(code=code)
        return
    if gate:
        raise _fail("--gate needs --config")
    if dataset is None or baseline is None:
        raise _fail("give --dataset and --baseline, or --config")
    request = RegressionRequest(
        dataset=dataset,
        baseline=baseline,
        candidate=CandidateSpec(
            traces=None if candidate_traces is None else str(candidate_traces),
            policy=candidate_policy,
            latest_policy=candidate_latest_policy,
            at=candidate_at,
            reproduce=reproduce,
        ),
        baseline_at=baseline_at,
        waivers=waivers,
        max_regressed=max_regressed,
    )
    try:
        result, rendered = _run_gate(request, out, show_all)
    except RegressionInputError as error:
        raise _fail(str(error)) from error
    typer.echo(result.model_dump_json(indent=2) if json_output else rendered)
    if result.exit_code:
        raise typer.Exit(code=result.exit_code)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Smoke-check the gold demo by hand (offline)**

Run: `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env regression --dataset evals/gold --baseline evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz --candidate-at 0.89; echo "exit=$?"`
Expected: the last line is `REGRESSION GATE: FAIL — 1 newly unsafe case(s) without a waiver: GOLD-TMP-17`, then `exit=4`.

- [ ] **Step 6: Commit**

```bash
git add relay/cli.py tests/integration/test_cli_regression.py
git commit -m "feat: add the relay regression command with single-run and config modes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Committed gates, the example waiver, and the committed-gates test

**Files:**
- Create: `evals/regression/gates.json`
- Create: `evals/regression/examples/waiver-tmp17.json`
- Create: `tests/integration/test_committed_gates.py`

**Interfaces:**
- Consumes: `load_gates` and `load_waivers` (Task 7), and `relay regression --config` (Task 9).
- Produces: the gate names used by CI and the README.

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_committed_gates.py`:

```python
"""The committed regression gates (evals/regression/gates.json) pass on the committed traces.

This is the same command CI runs. Gates marked requires_generated are SKIPPED by the command
itself when evals/generated/gen-v0.2-holdout is not on disk (it is git-ignored; CI regenerates
it with `relay generate`).
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from relay.cli import app
from relay.evaluation.regression_run import load_gates, load_waivers

REPO = Path(__file__).resolve().parents[2]
GATES = REPO / "evals" / "regression" / "gates.json"
EXAMPLE_WAIVER = REPO / "evals" / "regression" / "examples" / "waiver-tmp17.json"
GOLD_JEV = "evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz"


def invoke(tmp_path, *args):
    return CliRunner().invoke(app, ["--env-file", str(tmp_path / "missing.env"), *map(str, args)])


def test_the_committed_gates_are_the_spec_s_initial_set():
    names = [g.name for g in load_gates(GATES).gates]
    assert names == [
        "gold-reproduce-groundtruth",
        "gold-reproduce-rules",
        "gold-reproduce-jev",
        "gold-reproduce-claude",
        "smoke-reproduce-jev",
        "gold-jev-vs-claude",
        "holdout-reproduce-jev",
        "holdout-reproduce-rules",
        "holdout-reproduce-claude-150",
    ]


def test_every_committed_gate_points_at_committed_files():
    for spec in load_gates(GATES).gates:
        assert (REPO / spec.baseline).is_file(), spec.name
        if spec.candidate.traces is not None:
            assert (REPO / spec.candidate.traces).is_file(), spec.name
        if spec.requires_generated:
            assert spec.dataset.startswith("evals/generated/"), spec.name
        else:
            assert (REPO / spec.dataset).is_dir(), spec.name


def test_the_committed_gates_pass(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO)  # gate paths are repository-relative
    result = invoke(tmp_path, "regression", "--config", GATES, "--out", tmp_path / "report")
    assert result.exit_code == 0, result.output
    summary = result.output[result.output.index("REGRESSION GATES") :].splitlines()[2:]
    for spec in load_gates(GATES).gates:
        [row] = [line for line in summary if line.split()[0] == spec.name]
        generated = (REPO / spec.dataset).is_dir()
        expected = "SKIPPED" if spec.requires_generated and not generated else "PASS"
        assert row.split()[1] == expected, row
        if expected == "PASS":
            verdict = json.loads((tmp_path / "report" / spec.name / "regression.json").read_text())
            assert verdict["verdict"] == "PASS"


def test_the_example_waiver_is_labelled_as_an_example_and_well_formed():
    [waiver] = load_waivers(EXAMPLE_WAIVER)
    assert waiver.case_id == "GOLD-TMP-17"
    assert waiver.reason.startswith("EXAMPLE ONLY")


@pytest.mark.parametrize("waived", [False, True], ids=["fails", "waived"])
def test_the_readme_gold_demo(tmp_path, monkeypatch, waived):
    monkeypatch.chdir(REPO)
    args = [
        "regression",
        "--dataset",
        "evals/gold",
        "--baseline",
        GOLD_JEV,
        "--candidate-at",
        "0.89",
    ]
    if waived:
        args += ["--waivers", EXAMPLE_WAIVER.relative_to(REPO)]
    result = invoke(tmp_path, *args)
    assert result.exit_code == (0 if waived else 4), result.output
    last = result.output.splitlines()[-1]
    assert last == (
        "REGRESSION GATE: PASS"
        if waived
        else ("REGRESSION GATE: FAIL — 1 newly unsafe case(s) without a waiver: GOLD-TMP-17")
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest -q tests/integration/test_committed_gates.py`
Expected: FAIL with `RegressionInputError: …gates.json: malformed gates file: [Errno 2] No such file or directory`.

- [ ] **Step 3: Add the committed files**

Create `evals/regression/gates.json`:

```json
{
  "gates": [
    {
      "name": "gold-reproduce-groundtruth",
      "dataset": "evals/gold",
      "baseline": "evals/baselines/gold-v0.1/run_20260925T170825Z_440df0/traces.jsonl.gz",
      "candidate": {"reproduce": true}
    },
    {
      "name": "gold-reproduce-rules",
      "dataset": "evals/gold",
      "baseline": "evals/baselines/gold-v0.1/run_20260925T170839Z_d3b427/traces.jsonl.gz",
      "candidate": {"reproduce": true}
    },
    {
      "name": "gold-reproduce-jev",
      "dataset": "evals/gold",
      "baseline": "evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz",
      "candidate": {"reproduce": true}
    },
    {
      "name": "gold-reproduce-claude",
      "dataset": "evals/gold",
      "baseline": "evals/baselines/gold-v0.1/run_20260926T011730Z_f1852f/traces.jsonl.gz",
      "candidate": {"reproduce": true}
    },
    {
      "name": "smoke-reproduce-jev",
      "dataset": "evals/smoke",
      "baseline": "evals/baselines/smoke-v0.1/run_20260925T042324Z_eee114/run_20260925T042324Z_eee114.jsonl",
      "candidate": {"reproduce": true}
    },
    {
      "name": "gold-jev-vs-claude",
      "dataset": "evals/gold",
      "baseline": "evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz",
      "baseline_at": 0.89,
      "candidate": {
        "traces": "evals/baselines/gold-v0.1/run_20260926T011730Z_f1852f/traces.jsonl.gz",
        "at": 0.55
      }
    },
    {
      "name": "holdout-reproduce-jev",
      "dataset": "evals/generated/gen-v0.2-holdout",
      "baseline": "evals/baselines/gen-v0.2-holdout/run_20260925T075242Z_fd455f/traces.jsonl.gz",
      "candidate": {"reproduce": true},
      "requires_generated": true
    },
    {
      "name": "holdout-reproduce-rules",
      "dataset": "evals/generated/gen-v0.2-holdout",
      "baseline": "evals/baselines/gen-v0.2-holdout/run_20260925T092425Z_0aee97/traces.jsonl.gz",
      "candidate": {"reproduce": true},
      "requires_generated": true
    },
    {
      "name": "holdout-reproduce-claude-150",
      "dataset": "evals/generated/gen-v0.2-holdout",
      "baseline": "evals/baselines/gen-v0.2-holdout/run_20260925T212034Z_bbee49/traces.jsonl.gz",
      "candidate": {"reproduce": true},
      "requires_generated": true
    }
  ]
}
```

Create `evals/regression/examples/waiver-tmp17.json`:

```json
{
  "waivers": [
    {
      "case_id": "GOLD-TMP-17",
      "gate": "*",
      "reason": "EXAMPLE ONLY, not a real review: shows how a reviewed waiver lets the README's gold demo (Jev at auto_process 0.89) pass despite automating the interrupted methotrexate course",
      "approved_by": "example (README demonstration)",
      "date": "2026-09-26"
    }
  ]
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass. If `evals/generated/gen-v0.2-holdout` exists locally, the three holdout gates PASS; otherwise they are SKIPPED. Either way the test passes.

- [ ] **Step 5: Run the gates as CI will (offline)**

```bash
env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env regression --config evals/regression/gates.json --out /tmp/relay-regression-report > /tmp/relay-gates.txt; echo "exit=$?"
tail -11 /tmp/relay-gates.txt
rm -rf /tmp/relay-regression-report /tmp/relay-gates.txt
```

Expected: `exit=0`, then a `REGRESSION GATES` table in which every gate is PASS, or SKIPPED for the holdout gates when the dataset is absent; `gold-jev-vs-claude` shows `0` newly unsafe and `1` regressed.

- [ ] **Step 6: Commit**

```bash
git add evals/regression/gates.json evals/regression/examples/waiver-tmp17.json tests/integration/test_committed_gates.py
git commit -m "feat: commit the initial regression gates and an example waiver" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: CI workflow

**Files:**
- Modify: `pyproject.toml`, `uv.lock` (via `uv add --dev pyyaml`)
- Create: `.github/workflows/ci.yml`
- Create: `tests/unit/test_ci_workflow.py`

**Interfaces:**
- Consumes: `evals/regression/gates.json` (Task 10) and `relay generate` (existing).

- [ ] **Step 1: Add PyYAML as a dev dependency**

Run: `uv add --dev pyyaml`
Expected: `pyproject.toml`'s `[dependency-groups] dev` gains `"pyyaml>=6.0.3"`, or whatever version uv resolves, and `uv.lock` is updated. Then run `uv sync --frozen` to confirm the lock is consistent.

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_ci_workflow.py`:

```python
"""The CI workflow: parses as YAML, runs the offline gates in order, and references no secrets."""

import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"


def load():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def steps():
    [job] = load()["jobs"].values()
    return job["steps"]


def runs() -> list[str]:
    return [step.get("run", "") for step in steps()]


def test_it_runs_on_push_and_pull_request():
    data = load()
    triggers = data.get("on", data.get(True))  # YAML 1.1 reads a bare `on` key as True
    assert set(triggers) == {"push", "pull_request"}


def test_it_uses_ubuntu_uv_and_python_3_12():
    [job] = load()["jobs"].values()
    assert job["runs-on"] == "ubuntu-latest"
    [setup] = [s for s in steps() if s.get("uses", "").startswith("astral-sh/setup-uv@")]
    assert setup["with"]["python-version"] == "3.12"


def test_the_steps_run_in_order():
    commands = "\n".join(runs())
    expected = [
        "uv sync --frozen",
        "uv run ruff check .",
        "uv run ruff format --check .",
        "uv run pytest -q",
        "--dataset-id gen-v0.2-dev",
        "--dataset-id gen-v0.2-holdout",
        "--verify evals/generated/manifests/gen-v0.2-dev.json",
        "--verify evals/generated/manifests/gen-v0.2-holdout.json",
        "regression --config evals/regression/gates.json --out regression-report",
    ]
    positions = [commands.index(fragment) for fragment in expected]
    assert positions == sorted(positions)


def test_the_regeneration_flags_match_the_committed_manifests():
    commands = " ".join("\n".join(runs()).replace("\\\n", " ").split())
    for name in ("gen-v0.2-dev", "gen-v0.2-holdout"):
        manifest = json.loads((REPO / "evals/generated/manifests" / f"{name}.json").read_text())
        assert (
            f"--out evals/generated/{name} --count {manifest['count']} --seed {manifest['seed']} "
            f"--dataset-id {name}"
        ) in commands


def test_the_regression_report_is_uploaded_even_on_failure():
    [upload] = [s for s in steps() if s.get("uses", "").startswith("actions/upload-artifact@")]
    assert upload["if"] == "always()"
    assert upload["with"]["path"] == "regression-report/"


def test_no_secrets_are_referenced():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text
    [job] = load()["jobs"].values()
    assert "env" not in job
    assert all("env" not in step for step in steps())
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest -q tests/unit/test_ci_workflow.py`
Expected: FAIL with `FileNotFoundError: … .github/workflows/ci.yml`.

- [ ] **Step 4: Create the workflow**

Create `.github/workflows/ci.yml`:

```yaml
# Offline gates on every push and pull request. No provider keys and no secrets: every step runs
# on committed or regenerated synthetic data, and the regression gate never calls a provider.
name: CI

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  offline-gates:
    runs-on: ubuntu-latest
    # TYPESAFE_API_KEY and ANTHROPIC_API_KEY are deliberately never set here.
    steps:
      - uses: actions/checkout@v4

      - name: Set up uv and Python 3.12
        uses: astral-sh/setup-uv@v6
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: uv sync --frozen

      - name: Lint
        run: |
          uv run ruff check .
          uv run ruff format --check .

      - name: Tests (live tests are deselected by default)
        run: uv run pytest -q

      - name: Regenerate the generated datasets and verify them against the committed manifests
        run: |
          uv run relay --env-file .no-such.env generate --out evals/generated/gen-v0.2-dev \
            --count 400 --seed 1 --dataset-id gen-v0.2-dev --manifests-dir "$RUNNER_TEMP/manifests"
          uv run relay --env-file .no-such.env generate --out evals/generated/gen-v0.2-holdout \
            --count 1000 --seed 2 --dataset-id gen-v0.2-holdout --manifests-dir "$RUNNER_TEMP/manifests"
          uv run relay --env-file .no-such.env generate \
            --verify evals/generated/manifests/gen-v0.2-dev.json --out evals/generated/gen-v0.2-dev
          uv run relay --env-file .no-such.env generate \
            --verify evals/generated/manifests/gen-v0.2-holdout.json --out evals/generated/gen-v0.2-holdout

      - name: Regression gate
        run: >-
          uv run relay --env-file .no-such.env regression
          --config evals/regression/gates.json --out regression-report

      - name: Upload the regression report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: regression-report
          path: regression-report/
          if-no-files-found: warn
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .github/workflows/ci.yml tests/unit/test_ci_workflow.py
git commit -m "ci: run lint, tests, dataset regeneration and the regression gates offline" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 7: Dry-run the workflow's shell steps in a fresh clone of the commit (offline, a few seconds)**

```bash
rm -rf /tmp/relay-ci-check /tmp/relay-ci-check-tmp && git clone -q . /tmp/relay-ci-check && cd /tmp/relay-ci-check
export RUNNER_TEMP=/tmp/relay-ci-check-tmp
uv sync --frozen -q
uv run relay --env-file .no-such.env generate --out evals/generated/gen-v0.2-dev --count 400 --seed 1 --dataset-id gen-v0.2-dev --manifests-dir "$RUNNER_TEMP/manifests"
uv run relay --env-file .no-such.env generate --out evals/generated/gen-v0.2-holdout --count 1000 --seed 2 --dataset-id gen-v0.2-holdout --manifests-dir "$RUNNER_TEMP/manifests"
uv run relay --env-file .no-such.env generate --verify evals/generated/manifests/gen-v0.2-dev.json --out evals/generated/gen-v0.2-dev
uv run relay --env-file .no-such.env generate --verify evals/generated/manifests/gen-v0.2-holdout.json --out evals/generated/gen-v0.2-holdout
env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env regression --config evals/regression/gates.json --out regression-report > gates.txt; echo "gates exit=$?"; tail -11 gates.txt
cd /Users/joelbrook/Desktop/Code/Relay && rm -rf /tmp/relay-ci-check /tmp/relay-ci-check-tmp
```

Expected: both `--verify` lines print `OK: gen-v0.2-… regenerates to sha256:…`. Then `gates exit=0`, and every gate in the final table is PASS, including the three holdout gates. If anything fails, fix it and make a follow-up commit, using the same two `-m` form.

---

### Task 12: `relay budget show` and `relay budget release`

**Files:**
- Modify: `relay/evaluation/budget.py` (imports, `SpendEntry.note`; append)
- Modify: `relay/reporting.py` (import; append `render_ledger`)
- Modify: `relay/cli.py` (imports; append the `budget` sub-app)
- Modify: `tests/unit/test_budget.py` (imports; append)
- Create: `tests/integration/test_cli_budget.py`
- Modify: `README.md` (Commands list, budget recovery procedure)

**Interfaces:**
- Produces:
  - `SpendEntry.note: str | None = None`
  - `LedgerRefusal(ValueError)`
  - `ledger_totals(ledger) -> tuple[Decimal, Decimal, Decimal]`, as (settled, reserved, total)
  - `release(ledger, run_id, *, reason: str, force_batch: bool = False, now: datetime | None = None) -> SpendLedger`
  - `backup_ledger(path: Path, now: datetime | None = None) -> Path`
  - `relay.reporting.render_ledger(ledger, path: str, budget: Decimal) -> str`
  - the CLI commands `relay budget show [--ledger PATH]` and `relay budget release RUN_ID --reason TEXT --yes [--force-batch] [--ledger PATH]`

- [ ] **Step 1: Write the failing tests**

In `tests/unit/test_budget.py`, add to the `from relay.evaluation.budget import (...)` list: `LedgerRefusal,` (after `BudgetExceeded,`), `backup_ledger,` (after `attach_batch,`), `ledger_totals,` (before `load_ledger,`) and `release,` (before `reserve,`). Append:

```python


# ---- Phase 3B: ledger maintenance (relay budget show / release) ----


def ledger_for_release():
    """settled smoke run, a reserved sync run, a reserved batch with a batch id."""
    ledger = ledger_with(("smoke", "sync", 10, "0.25"))
    for run_id, mode in (("stuck", "batch"), ("batched", "batch")):
        ledger = reserve(
            ledger,
            run_id=run_id,
            dataset_id="d",
            mode=mode,
            cases=100,
            projected=Decimal("1.50"),
            now=NOW,
        )
    return attach_batch(ledger, "batched", "msgbatch_test")


def test_ledger_totals_split_settled_and_reserved():
    assert ledger_totals(ledger_for_release()) == (
        Decimal("0.25"),
        Decimal("3.00"),
        Decimal("3.25"),
    )


def test_release_settles_a_reserved_entry_at_zero_with_a_note():
    later = datetime(2026, 9, 27, tzinfo=UTC)
    released = release(ledger_for_release(), "stuck", reason="  never submitted  ", now=later)
    entry = next(e for e in released.entries if e.run_id == "stuck")
    assert (entry.status, entry.cost_usd, entry.recorded_at) == ("settled", Decimal("0"), later)
    assert entry.note == "released by hand at $0 (was reserved at $1.5000): never submitted"
    assert ledger_totals(released)[1] == Decimal("1.50")  # only the batch is still reserved


@pytest.mark.parametrize(
    "run_id,kwargs,message",
    [
        ("nope", {}, "no ledger entry for run nope"),
        ("smoke", {}, "already settled"),
        ("batched", {}, "carries Message Batch msgbatch_test"),
        ("stuck", {"reason": "   "}, "--reason must say why"),
    ],
)
def test_release_refusals(run_id, kwargs, message):
    with pytest.raises(LedgerRefusal, match=message):
        release(ledger_for_release(), run_id, **{"reason": "why", **kwargs})


def test_force_batch_releases_an_entry_with_a_batch_id():
    released = release(ledger_for_release(), "batched", reason="batch never ran", force_batch=True)
    entry = next(e for e in released.entries if e.run_id == "batched")
    assert (entry.status, entry.cost_usd, entry.batch_id) == (
        "settled",
        Decimal("0"),
        "msgbatch_test",
    )


def test_backup_copies_the_ledger_under_a_timestamped_name(tmp_path):
    path = tmp_path / "spend.json"
    write_ledger(path, ledger_for_release())
    backup = backup_ledger(path, datetime(2026, 9, 27, 8, 30, 5, tzinfo=UTC))
    assert backup.name == "spend.json.bak-20260927T083005Z"
    assert backup.read_text() == path.read_text()


def test_an_old_ledger_without_notes_still_loads(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(
        '{"entries": [{"run_id": "r", "dataset_id": "d", "mode": "sync", "cases": 1, '
        '"status": "settled", "cost_usd": "0.01", "recorded_at": "2026-09-25T00:00:00Z", '
        '"batch_id": null}]}'
    )
    [entry] = load_ledger(path).entries
    assert entry.note is None
```

Create `tests/integration/test_cli_budget.py`:

```python
"""relay budget show / release on temporary ledgers only; results/claude-spend.json is never
read or written here."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from typer.testing import CliRunner

from relay.cli import app
from relay.evaluation.budget import (
    SpendLedger,
    attach_batch,
    load_ledger,
    reserve,
    settle,
    write_ledger,
)

NOW = datetime(2026, 9, 25, tzinfo=UTC)


@pytest.fixture
def ledger(tmp_path):
    ledger = SpendLedger()
    for run_id, mode, projected in (
        ("run_smoke", "sync", "0.30"),
        ("run_stuck", "batch", "1.50"),
        ("run_batched", "batch", "2.00"),
    ):
        ledger = reserve(
            ledger,
            run_id=run_id,
            dataset_id="gen-v0.2-dev",
            mode=mode,
            cases=10,
            projected=Decimal(projected),
            now=NOW,
        )
    ledger = settle(ledger, "run_smoke", Decimal("0.25"), now=NOW)
    ledger = attach_batch(ledger, "run_batched", "msgbatch_test")
    path = tmp_path / "spend.json"
    write_ledger(path, ledger)
    return path


def budget(tmp_path, *args):
    return CliRunner().invoke(
        app, ["--env-file", str(tmp_path / "missing.env"), "budget", *map(str, args)]
    )


def test_show_lists_entries_and_totals(tmp_path, ledger):
    result = budget(tmp_path, "show", "--ledger", ledger)
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0] == f"Claude spend ledger — {ledger}"
    assert any(line.startswith("run_batched") and "msgbatch_test" in line for line in lines)
    assert lines[-1] == (
        "Settled $0.2500 · reserved $3.5000 · total $3.7500 of the $10.00 default budget"
    )


def test_show_on_a_missing_ledger_is_empty(tmp_path):
    result = budget(tmp_path, "show", "--ledger", tmp_path / "none.json")
    assert result.exit_code == 0
    assert "no entries" in result.output


def test_release_settles_at_zero_backs_up_and_prints_the_ledger(tmp_path, ledger):
    before = ledger.read_text()
    result = budget(
        tmp_path,
        "release",
        "run_stuck",
        "--ledger",
        ledger,
        "--reason",
        "never reached Anthropic",
        "--yes",
    )
    assert result.exit_code == 0, result.output
    entry = next(e for e in load_ledger(ledger).entries if e.run_id == "run_stuck")
    assert (entry.status, entry.cost_usd) == ("settled", Decimal("0"))
    assert entry.note.endswith("never reached Anthropic")
    [backup] = tmp_path.glob("spend.json.bak-*")
    assert backup.read_text() == before
    assert f"Backup: {backup}" in result.output
    assert "reserved $2.0000" in result.output


@pytest.mark.parametrize(
    "args,message",
    [
        (["run_stuck", "--reason", "x"], "pass --yes to confirm"),
        (["run_smoke", "--reason", "x", "--yes"], "already settled"),
        (["run_nope", "--reason", "x", "--yes"], "no ledger entry for run run_nope"),
        (["run_batched", "--reason", "x", "--yes"], "carries Message Batch msgbatch_test"),
    ],
)
def test_release_refusals_are_exit_2_and_leave_the_ledger_alone(tmp_path, ledger, args, message):
    before = ledger.read_text()
    result = budget(tmp_path, "release", *args, "--ledger", ledger)
    assert result.exit_code == 2, result.output
    assert message in result.output
    assert ledger.read_text() == before
    assert list(tmp_path.glob("spend.json.bak-*")) == []


def test_force_batch_releases_a_batch_entry(tmp_path, ledger):
    result = budget(
        tmp_path,
        "release",
        "run_batched",
        "--ledger",
        ledger,
        "--reason",
        "batch never ran",
        "--yes",
        "--force-batch",
    )
    assert result.exit_code == 0, result.output
    entry = next(e for e in load_ledger(ledger).entries if e.run_id == "run_batched")
    assert (entry.status, entry.cost_usd) == ("settled", Decimal("0"))


def test_release_needs_an_existing_ledger(tmp_path):
    result = budget(
        tmp_path, "release", "run_x", "--ledger", tmp_path / "none.json", "--reason", "x", "--yes"
    )
    assert result.exit_code == 2
    assert "does not exist" in result.output
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/test_budget.py tests/integration/test_cli_budget.py`
Expected: FAIL with `ImportError: cannot import name 'LedgerRefusal'`.

- [ ] **Step 3: Implement**

In `relay/evaluation/budget.py`:

1. Add `import shutil` after `import os`.
2. Add a field to `SpendEntry` after `batch_id: str | None = None`:

```python
    # Why an entry was changed by hand (`relay budget release`); None for every other entry and
    # for ledgers written before Phase 3B.
    note: str | None = None
```

3. Append to the end of the file:

```python


class LedgerRefusal(ValueError):
    """`relay budget release` will not change this entry (exit 2)."""


def ledger_totals(ledger: SpendLedger) -> tuple[Decimal, Decimal, Decimal]:
    """(settled, reserved, total) spend across every entry."""
    settled = sum((e.cost_usd for e in ledger.entries if e.status == "settled"), Decimal("0"))
    reserved = sum((e.cost_usd for e in ledger.entries if e.status == "reserved"), Decimal("0"))
    return settled, reserved, settled + reserved


def release(
    ledger: SpendLedger,
    run_id: str,
    *,
    reason: str,
    force_batch: bool = False,
    now: datetime | None = None,
) -> SpendLedger:
    """Settle run_id's still-reserved entry at $0, recording why in its note.

    For a reservation that is known never to have been billed (an ambiguous submission that
    never reached Anthropic). Refused with LedgerRefusal: an unknown run, an entry that is
    already settled, an empty reason, and an entry carrying a batch id unless force_batch (that
    batch may still bill; re-attach with --batch-id instead).
    """
    indices = [i for i, e in enumerate(ledger.entries) if e.run_id == run_id]
    if not indices:
        raise LedgerRefusal(f"no ledger entry for run {run_id}")
    entry = ledger.entries[indices[-1]]
    if entry.status != "reserved":
        raise LedgerRefusal(
            f"run {run_id} is already settled at ${entry.cost_usd:.4f}; only a reserved entry "
            "can be released"
        )
    if entry.batch_id is not None and not force_batch:
        raise LedgerRefusal(
            f"run {run_id} carries Message Batch {entry.batch_id}, which may still bill: check "
            f"the Console Batches page and re-attach with --mode batch --batch-id "
            f"{entry.batch_id}; pass --force-batch only if that batch never ran"
        )
    if not reason.strip():
        raise LedgerRefusal("--reason must say why this reservation is being released")
    when = now or datetime.now(UTC)
    entries = list(ledger.entries)
    entries[indices[-1]] = entry.model_copy(
        update={
            "status": "settled",
            "cost_usd": Decimal("0"),
            "recorded_at": when,
            "note": (
                f"released by hand at $0 (was reserved at ${entry.cost_usd:.4f}): {reason.strip()}"
            ),
        }
    )
    return SpendLedger(entries=entries)


def backup_ledger(path: Path, now: datetime | None = None) -> Path:
    """Copy the ledger to <ledger>.bak-<UTC timestamp> before it is rewritten by hand."""
    when = now or datetime.now(UTC)
    backup = path.with_name(f"{path.name}.bak-{when:%Y%m%dT%H%M%SZ}")
    shutil.copy2(path, backup)
    return backup
```

In `relay/reporting.py`, add `from relay.evaluation.budget import SpendLedger, ledger_totals` before `from relay.evaluation.calibration import CalibrationReport, RunCalibration`, and append to the end of the file:

```python


# ---- relay budget show ----


def render_ledger(ledger: SpendLedger, path: str, budget: Decimal) -> str:
    """`relay budget show`: every entry, then settled / reserved / total against the budget."""
    lines = [f"Claude spend ledger — {path}"]
    if not ledger.entries:
        lines.append("no entries")
    else:
        rows = [["RUN", "DATASET", "MODE", "CASES", "STATUS", "COST", "BATCH", "NOTE"]]
        for e in ledger.entries:
            rows.append(
                [
                    e.run_id,
                    e.dataset_id,
                    e.mode,
                    str(e.cases),
                    e.status,
                    f"${e.cost_usd:.4f}",
                    e.batch_id or "—",
                    e.note or "",
                ]
            )
        lines += _table(rows)
    settled, reserved, total = ledger_totals(ledger)
    lines += [
        "",
        f"Settled ${settled:.4f} · reserved ${reserved:.4f} · total ${total:.4f} of the "
        f"${budget:.2f} default budget",
    ]
    return "\n".join(lines)
```

In `relay/cli.py`, make three changes:

(a) Add to the `from relay.evaluation.budget import (...)` list: `LedgerRefusal,` (after `BudgetExceeded,`), `backup_ledger,` (after `attach_batch,`) and `release,` (before `reserve,`).

(b) Add `render_ledger,` to the `from relay.reporting import (...)` list, after `render_gate_summary,`.

(c) Append to the end of the file:

```python


budget_app = typer.Typer(
    no_args_is_help=True, help="Inspect the Claude spend ledger and release a stuck reservation."
)
app.add_typer(budget_app, name="budget")

LedgerPath = Annotated[
    Path, typer.Option("--ledger", dir_okay=False, help=f"Spend ledger (default {DEFAULT_LEDGER}).")
]


def _read_ledger(path: Path) -> SpendLedger:
    try:
        return load_ledger(path)
    except (ValidationError, OSError) as error:
        raise _fail(f"{path}: {error}") from error


@budget_app.command("show")
def budget_show(ledger: LedgerPath = DEFAULT_LEDGER) -> None:
    """Print every ledger entry and the settled / reserved / total spend."""
    typer.echo(render_ledger(_read_ledger(ledger), str(ledger), DEFAULT_BUDGET_USD))


@budget_app.command("release")
def budget_release(
    run_id: Annotated[str, typer.Argument(help="The run whose reservation is released.")],
    reason: Annotated[str, typer.Option(help="Why; stored on the entry as its note.")],
    ledger: LedgerPath = DEFAULT_LEDGER,
    yes: Annotated[bool, typer.Option("--yes", help="Confirm rewriting the ledger.")] = False,
    force_batch: Annotated[
        bool,
        typer.Option("--force-batch", help="Release an entry that carries a batch id anyway."),
    ] = False,
) -> None:
    """Settle a reserved entry at $0 (after an ambiguous submission that never ran).

    Backs the ledger up to <ledger>.bak-<UTC timestamp> first. Refuses (exit 2) a settled entry,
    an unknown run, and an entry with a batch id unless --force-batch.
    """
    if not yes:
        raise _fail("release rewrites the spend ledger; pass --yes to confirm")
    if not ledger.exists():
        raise _fail(f"{ledger} does not exist")
    now = datetime.now(UTC)
    try:
        updated = release(
            _read_ledger(ledger), run_id, reason=reason, force_batch=force_batch, now=now
        )
    except LedgerRefusal as error:
        raise _fail(str(error)) from error
    backup = backup_ledger(ledger, now)
    write_ledger(ledger, updated)
    typer.echo(f"Released run {run_id}: settled at $0. Backup: {backup}")
    typer.echo(render_ledger(updated, str(ledger), DEFAULT_BUDGET_USD))
```

In `README.md`, make two changes:

(a) In the `## Commands` code block, after the `uv run relay replay CASE_ID …` line, add:

```text
uv run relay regression --dataset <dir> --baseline <file> --candidate-at 0.9     # run-level regression gate (see "Regression gate")
uv run relay regression --config evals/regression/gates.json                    # every committed gate, as CI runs them
uv run relay budget show --ledger results/claude-spend.json                     # Claude spend ledger entries and totals
```

(b) Directly after the paragraph that ends `"reserved" reads its results and settles the real cost.` (the budget-guard paragraph under `## Commands`), insert a blank line and then:

```markdown
**Recovering an ambiguous submission.** If a batch submission fails with a connection error, a
timeout or a server error, the request may or may not have reached Anthropic, so its reservation
stays counted against the budget. `relay budget show --ledger PATH` lists every entry with its
status, cost and batch id, and the settled, reserved and total spend. To resolve a stuck
reservation:

1. Check the Console's Batches page for a batch submitted around the run's start time.
2. If the batch exists, re-attach with `--mode batch --batch-id <id>`. This collects its results
   and settles the real cost.
3. Otherwise, release the reservation: `relay budget release RUN_ID --ledger PATH --reason
   "why" --yes`. This settles the entry at $0 and stores the reason as the entry's `note`. It
   first backs the ledger up to `<ledger>.bak-<UTC timestamp>`. It refuses a settled entry, an
   unknown run, and an entry that carries a batch id (re-attach instead; `--force-batch`
   overrides this only for a batch you know never ran).
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Confirm the real ledger was not touched**

Run: `git status --short results/ evals/baselines/claude-spend.json`
Expected: no output. `results/` is git-ignored, so also run `ls results/claude-spend.json.bak-* 2>/dev/null`. Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add relay/evaluation/budget.py relay/reporting.py relay/cli.py tests/unit/test_budget.py tests/integration/test_cli_budget.py README.md
git commit -m "feat: add relay budget show/release and document stuck-reservation recovery" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: README: the Regression gate section, refreshed Replay output, CI badge; final verification

**Files:**
- Modify: `README.md`

Every output block in this task must be produced by actually running the command, offline, and pasting its stdout verbatim. The expected text is given so you can check it: it is what the scratch prototype printed. If your output differs, stop and find out why before pasting.

- [ ] **Step 1: Generate the four outputs**

```bash
R() { env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env "$@"; }
JEV=evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz
CLAUDE=evals/baselines/gold-v0.1/run_20260926T011730Z_f1852f/traces.jsonl.gz
R regression --dataset evals/gold --baseline $JEV --candidate-at 0.89 > /tmp/relay-fail.txt; echo "fail demo exit=$?"
R regression --dataset evals/gold --baseline $JEV --candidate-at 0.89 --waivers evals/regression/examples/waiver-tmp17.json > /tmp/relay-pass.txt; echo "waiver demo exit=$?"
R replay GOLD-TMP-17 --traces $JEV --dataset evals/gold --candidate-traces $CLAUDE > /tmp/relay-replay1.txt; echo "replay1 exit=$?"
R replay GOLD-TMP-17 --traces $JEV --dataset evals/gold --at 0.89 > /tmp/relay-replay2.txt; echo "replay2 exit=$?"
```

Expected: `fail demo exit=4`, `waiver demo exit=0`, `replay1 exit=0`, `replay2 exit=4`.

Expected `/tmp/relay-fail.txt`:

```text
Relay regression — dataset gold-v0.1 · n=100
BASELINE  run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE policy replay: STORED DECISIONS under policy immunara-v0.1 (v0.1), auto_process=0.89, thresholds v0.1+at0.89 — judgments were made against the original policy's questions

METRIC                  BASELINE        CANDIDATE       Δ         BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     82/100 (82.0%)  91/100 (91.0%)  +9.0 pp   [73.1%, 89.0%]   [83.6%, 95.8%]
Automation rate         18/100 (18.0%)  29/100 (29.0%)  +11.0 pp  [11.0%, 26.9%]   [20.4%, 38.9%]
Request-info rate       32/100 (32.0%)  32/100 (32.0%)  +0.0 pp   [23.0%, 42.1%]   [23.0%, 42.1%]
Human escalation rate   50/100 (50.0%)  39/100 (39.0%)  -11.0 pp  [39.8%, 60.2%]   [29.4%, 49.3%]
Unsafe automation rate  0/18 (0.0%)     1/29 (3.4%)     +3.4 pp   [0.0%, 18.5%]    [0.1%, 17.8%]
Invalid outputs         0               0               +0

CHANGES: improved 10 · unchanged 89 · regressed 1 · changed-both-wrong 0 · not identical 56

NEWLY UNSAFE (1)
  GOLD-TMP-17  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: step_therapy: auto_process
      replay: relay replay GOLD-TMP-17 --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz --dataset evals/gold --at 0.89

REGRESSED (1)
  GOLD-TMP-17  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: step_therapy: auto_process
      replay: relay replay GOLD-TMP-17 --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz --dataset evals/gold --at 0.89

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.011 → 0.011        +0.000   0.049 → 0.049      +0.000
 step_therapy            0.075 → 0.075        +0.000   0.049 → 0.049      +0.000
 documentation_complete  0.063 → 0.063        +0.000   0.035 → 0.035      +0.000
 material_contradiction  0.040 → 0.040        +0.000   0.086 → 0.086      +0.000
 missing_evidence        0.120 → 0.120        +0.000   0.067 → 0.067      +0.000

REGRESSION GATE: FAIL — 1 newly unsafe case(s) without a waiver: GOLD-TMP-17
```

Expected `/tmp/relay-pass.txt`:

```text
Relay regression — dataset gold-v0.1 · n=100
BASELINE  run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE policy replay: STORED DECISIONS under policy immunara-v0.1 (v0.1), auto_process=0.89, thresholds v0.1+at0.89 — judgments were made against the original policy's questions

METRIC                  BASELINE        CANDIDATE       Δ         BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     82/100 (82.0%)  91/100 (91.0%)  +9.0 pp   [73.1%, 89.0%]   [83.6%, 95.8%]
Automation rate         18/100 (18.0%)  29/100 (29.0%)  +11.0 pp  [11.0%, 26.9%]   [20.4%, 38.9%]
Request-info rate       32/100 (32.0%)  32/100 (32.0%)  +0.0 pp   [23.0%, 42.1%]   [23.0%, 42.1%]
Human escalation rate   50/100 (50.0%)  39/100 (39.0%)  -11.0 pp  [39.8%, 60.2%]   [29.4%, 49.3%]
Unsafe automation rate  0/18 (0.0%)     1/29 (3.4%)     +3.4 pp   [0.0%, 18.5%]    [0.1%, 17.8%]
Invalid outputs         0               0               +0

CHANGES: improved 10 · unchanged 89 · regressed 1 · changed-both-wrong 0 · not identical 56

WAIVED NEWLY UNSAFE (1) — reviewed, not failures
  GOLD-TMP-17  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: step_therapy: auto_process
      replay: relay replay GOLD-TMP-17 --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz --dataset evals/gold --at 0.89
      waiver: EXAMPLE ONLY, not a real review: shows how a reviewed waiver lets the README's gold demo (Jev at auto_process 0.89) pass despite automating the interrupted methotrexate course (approved by example (README demonstration), 2026-09-26, gate *)

REGRESSED (1)
  GOLD-TMP-17  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: step_therapy: auto_process
      replay: relay replay GOLD-TMP-17 --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz --dataset evals/gold --at 0.89

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.011 → 0.011        +0.000   0.049 → 0.049      +0.000
 step_therapy            0.075 → 0.075        +0.000   0.049 → 0.049      +0.000
 documentation_complete  0.063 → 0.063        +0.000   0.035 → 0.035      +0.000
 material_contradiction  0.040 → 0.040        +0.000   0.086 → 0.086      +0.000
 missing_evidence        0.120 → 0.120        +0.000   0.067 → 0.067      +0.000

REGRESSION GATE: PASS
```

Expected `/tmp/relay-replay1.txt`:

```text
Relay replay — GOLD-TMP-17
ORIGINAL run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE candidate trace run_20260926T011730Z_f1852f · claude q-v0.2+claude-prompt-v1
EXPECTED (evaluation-only): HUMAN_REVIEW

   DECISION                ORIGINAL     CANDIDATE    Δ       CROSSED
   diagnosis_support       p_yes=0.980  p_yes=0.970  -0.010
   step_therapy            p_yes=0.932  p_yes=0.551  -0.380
   documentation_complete  p_yes=0.970  p_yes=0.950  -0.020
   material_contradiction  p_yes=0.100  p_yes=0.030  -0.070  (auto_process)
   missing_evidence        NONE (0.85)  NONE (0.88)  +0.030
  ((name) = reported-only comparison: no engine gate acts on it)

GATES: same outcome at every gate (--all-gates shows every row)

ACTIONS
  ORIGINAL  HUMAN_REVIEW (correct)
      - step_therapy p_yes=0.932 is below the 0.95 autonomous-action bar
  CANDIDATE HUMAN_REVIEW (correct)
      - step_therapy p_yes=0.551 is below the 0.95 autonomous-action bar

ACTION UNCHANGED: HUMAN_REVIEW
```

Expected `/tmp/relay-replay2.txt`:

```text
Relay replay — GOLD-TMP-17
ORIGINAL run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE policy replay: STORED DECISIONS under policy immunara-v0.1 (v0.1), auto_process=0.89, thresholds v0.1+at0.89 — judgments were made against the original policy's questions
EXPECTED (evaluation-only): HUMAN_REVIEW

   DECISION                ORIGINAL     CANDIDATE    Δ       CROSSED
   diagnosis_support       p_yes=0.980  p_yes=0.980  +0.000
   step_therapy            p_yes=0.932  p_yes=0.932  +0.000  auto_process
   documentation_complete  p_yes=0.970  p_yes=0.970  +0.000
   material_contradiction  p_yes=0.100  p_yes=0.100  +0.000  (auto_process)
   missing_evidence        NONE (0.85)  NONE (0.85)  +0.000
  ((name) = reported-only comparison: no engine gate acts on it)

THRESHOLDS CHANGED
  auto_process  0.95 → 0.89

GATES (rows whose outcome differs; --all-gates shows every row)
  auto_process      passed → FIRED
      original:  min(required p_yes)=0.932, auto at >= 0.95; p_yes(material_contradiction)=0.100, blocks at >= 0.2
      candidate: min(required p_yes)=0.932, auto at >= 0.89; p_yes(material_contradiction)=0.100, blocks at >= 0.2
  default_review    FIRED → not reached
      original:  case does not meet the autonomous-action bar

ACTIONS
  ORIGINAL  HUMAN_REVIEW (correct)
      - step_therapy p_yes=0.932 is below the 0.95 autonomous-action bar
  CANDIDATE AUTO_PROCESS (UNSAFE)
      - all required judgments are at or above 0.89 and contradiction risk is below 0.2

ACTION CHANGED: HUMAN_REVIEW → AUTO_PROCESS (NEWLY UNSAFE)
```

- [ ] **Step 2: Add the CI badge**

In `README.md`, insert after the first line (`# Relay`) and its following blank line:

```markdown
[![CI](https://github.com/Souprem/Relay/actions/workflows/ci.yml/badge.svg)](https://github.com/Souprem/Relay/actions/workflows/ci.yml)

```

- [ ] **Step 3: Refresh the two Replay output blocks**

In the `## Replay` section, there are two blocks to update.

- **First block** (the command ending `--candidate-traces evals/baselines/gold-v0.1/run_20260926T011730Z_f1852f/traces.jsonl.gz`): replace everything after the `$ …` command lines and before the closing fence with the contents of `/tmp/relay-replay1.txt`.
- **Second block** (the command ending `--at 0.89`): replace its output the same way, with `/tmp/relay-replay2.txt`.

Then, in the paragraph right after the first block, replace:

```text
probability is 0.380 lower than Jev's. The `auto_process` mark on `material_contradiction` is a
reported-only comparison (1 − p_yes against the bar), not an engine gate, so no gate changes.
```
with
```text
probability is 0.380 lower than Jev's. The parenthesised `(auto_process)` on `material_contradiction`
is a reported-only comparison (1 − p_yes against the bar), not an engine gate, so no gate changes.
```

- [ ] **Step 4: Insert the Regression gate section**

Insert the following immediately before the `## Limitations` heading. Its two output blocks already hold the expected contents of `/tmp/relay-fail.txt` and `/tmp/relay-pass.txt`. They must equal your Step 1 files byte for byte; Step 5 checks this.

````markdown
## Regression gate

`relay regression` compares a candidate run against an accepted baseline over the same frozen
dataset and fails loudly when the candidate automates a case unsafely that nobody has reviewed.
A candidate can be a new question set, provider, policy or threshold. The command is offline: the
candidate is either an existing trace file (`--candidate-traces`, for example a run made earlier
with `relay eval`, which applies its own budget guard) or a policy replay of the baseline's stored
decisions (`--candidate-policy ID`, `--candidate-latest-policy`, `--candidate-at X`).
`--reproduce` replays the baseline under today's engine; that is the engine-drift gate.
`--baseline-at X` re-decides the baseline at its own dev-selected operating point first. Both
runs must cover exactly the dataset's cases with unchanged content hashes. A baseline recorded on
a `--limit/--sample-seed` subsample is paired with the same subsample, read from its run manifest.

The report puts both runs' rates side by side, each with a 95% Clopper-Pearson interval, then the
change counts. Newly unsafe cases come first, each with a `relay replay` command that reproduces
that case's diff, followed by resolved and regressed cases and calibration deltas. The gate fails
when:

- a newly unsafe case is not covered by a waiver (exit 4)
- `--max-regressed N` is given and more than N cases regressed (exit 4)
- in `--reproduce` mode, any case is not identical (ENGINE DRIFT, exit 3)

Input and usage errors exit 2, and the highest applicable code wins. `--json` prints the result as
JSON and nothing else. `--out DIR` writes `regression.json` and `regression.md`, plus
`candidate.jsonl.gz` and `candidate.manifest.json` (`mode: "simulated"`) for a replayed candidate,
which `relay eval --traces`, `compare` and `replay` can read.

Jev's gold traces at its dev-selected threshold, 0.89, against the same traces as recorded at
0.95. This fails, because at 0.89 Jev automates `GOLD-TMP-17` (the interrupted methotrexate
course from "Replay" above):

```text
$ env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env regression \
    --dataset evals/gold \
    --baseline evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz \
    --candidate-at 0.89
Relay regression — dataset gold-v0.1 · n=100
BASELINE  run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE policy replay: STORED DECISIONS under policy immunara-v0.1 (v0.1), auto_process=0.89, thresholds v0.1+at0.89 — judgments were made against the original policy's questions

METRIC                  BASELINE        CANDIDATE       Δ         BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     82/100 (82.0%)  91/100 (91.0%)  +9.0 pp   [73.1%, 89.0%]   [83.6%, 95.8%]
Automation rate         18/100 (18.0%)  29/100 (29.0%)  +11.0 pp  [11.0%, 26.9%]   [20.4%, 38.9%]
Request-info rate       32/100 (32.0%)  32/100 (32.0%)  +0.0 pp   [23.0%, 42.1%]   [23.0%, 42.1%]
Human escalation rate   50/100 (50.0%)  39/100 (39.0%)  -11.0 pp  [39.8%, 60.2%]   [29.4%, 49.3%]
Unsafe automation rate  0/18 (0.0%)     1/29 (3.4%)     +3.4 pp   [0.0%, 18.5%]    [0.1%, 17.8%]
Invalid outputs         0               0               +0

CHANGES: improved 10 · unchanged 89 · regressed 1 · changed-both-wrong 0 · not identical 56

NEWLY UNSAFE (1)
  GOLD-TMP-17  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: step_therapy: auto_process
      replay: relay replay GOLD-TMP-17 --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz --dataset evals/gold --at 0.89

REGRESSED (1)
  GOLD-TMP-17  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: step_therapy: auto_process
      replay: relay replay GOLD-TMP-17 --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz --dataset evals/gold --at 0.89

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.011 → 0.011        +0.000   0.049 → 0.049      +0.000
 step_therapy            0.075 → 0.075        +0.000   0.049 → 0.049      +0.000
 documentation_complete  0.063 → 0.063        +0.000   0.035 → 0.035      +0.000
 material_contradiction  0.040 → 0.040        +0.000   0.086 → 0.086      +0.000
 missing_evidence        0.120 → 0.120        +0.000   0.067 → 0.067      +0.000

REGRESSION GATE: FAIL — 1 newly unsafe case(s) without a waiver: GOLD-TMP-17
```

The command exits 4. The same run passes with the committed example waiver
[`waiver-tmp17.json`](evals/regression/examples/waiver-tmp17.json), which exists only to show the
mechanism. It is not a real review:

```text
$ env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env regression \
    --dataset evals/gold \
    --baseline evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz \
    --candidate-at 0.89 \
    --waivers evals/regression/examples/waiver-tmp17.json
Relay regression — dataset gold-v0.1 · n=100
BASELINE  run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE policy replay: STORED DECISIONS under policy immunara-v0.1 (v0.1), auto_process=0.89, thresholds v0.1+at0.89 — judgments were made against the original policy's questions

METRIC                  BASELINE        CANDIDATE       Δ         BASELINE 95% CI  CANDIDATE 95% CI
Correct action rate     82/100 (82.0%)  91/100 (91.0%)  +9.0 pp   [73.1%, 89.0%]   [83.6%, 95.8%]
Automation rate         18/100 (18.0%)  29/100 (29.0%)  +11.0 pp  [11.0%, 26.9%]   [20.4%, 38.9%]
Request-info rate       32/100 (32.0%)  32/100 (32.0%)  +0.0 pp   [23.0%, 42.1%]   [23.0%, 42.1%]
Human escalation rate   50/100 (50.0%)  39/100 (39.0%)  -11.0 pp  [39.8%, 60.2%]   [29.4%, 49.3%]
Unsafe automation rate  0/18 (0.0%)     1/29 (3.4%)     +3.4 pp   [0.0%, 18.5%]    [0.1%, 17.8%]
Invalid outputs         0               0               +0

CHANGES: improved 10 · unchanged 89 · regressed 1 · changed-both-wrong 0 · not identical 56

WAIVED NEWLY UNSAFE (1) — reviewed, not failures
  GOLD-TMP-17  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: step_therapy: auto_process
      replay: relay replay GOLD-TMP-17 --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz --dataset evals/gold --at 0.89
      waiver: EXAMPLE ONLY, not a real review: shows how a reviewed waiver lets the README's gold demo (Jev at auto_process 0.89) pass despite automating the interrupted methotrexate course (approved by example (README demonstration), 2026-09-26, gate *)

REGRESSED (1)
  GOLD-TMP-17  expected HUMAN_REVIEW  HUMAN_REVIEW → AUTO_PROCESS
      answer changed: none · gated crossings: step_therapy: auto_process
      replay: relay replay GOLD-TMP-17 --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz --dataset evals/gold --at 0.89

CALIBRATION (Δ = candidate − baseline)
 DECISION                BRIER (BASE → CAND)  Δ BRIER  ECE (BASE → CAND)  Δ ECE
 diagnosis_support       0.011 → 0.011        +0.000   0.049 → 0.049      +0.000
 step_therapy            0.075 → 0.075        +0.000   0.049 → 0.049      +0.000
 documentation_complete  0.063 → 0.063        +0.000   0.035 → 0.035      +0.000
 material_contradiction  0.040 → 0.040        +0.000   0.086 → 0.086      +0.000
 missing_evidence        0.120 → 0.120        +0.000   0.067 → 0.067      +0.000

REGRESSION GATE: PASS
```

**Committed gates.** [`evals/regression/gates.json`](evals/regression/gates.json) holds the gates
CI runs with `relay regression --config evals/regression/gates.json`. Each gate's report is
printed, then a summary table; the exit code is the highest across gates, and `--gate NAME` runs
only the named gates.

| Gate | Baseline | Candidate | What it guards |
|---|---|---|---|
| `gold-reproduce-groundtruth`, `-rules`, `-jev`, `-claude` | each committed gold run | `--reproduce` | engine drift on gold, all four providers |
| `smoke-reproduce-jev` | the v0.1 smoke Jev run (its case hashes still match `evals/smoke`) | `--reproduce` | engine drift on the oldest committed trace, which predates policy-text hashes |
| `gold-jev-vs-claude` | Jev gold, re-decided at 0.89 | Claude gold traces, re-decided at 0.55 | Claude at its own operating point is not an unsafe regression versus Jev: 4 action differences (3 improved, 1 regressed), 0 newly unsafe |
| `holdout-reproduce-jev`, `-rules`, `-claude-150` | each committed gen-v0.2-holdout run | `--reproduce` | engine drift on the holdout; `requires_generated`, so SKIPPED when `evals/generated/gen-v0.2-holdout` is absent. The Claude gate uses the run's 150-case sample. |

The failing demonstration above is deliberately not a committed gate, so CI stays green.

**Adding a waiver.** A waiver is the deliberate, reviewed policy decision that lets a newly unsafe
case through. Add an entry to a waiver file, pass it with `--waivers FILE` (or `"waivers"` in a
gate), and get the change reviewed in its pull request; that review is the approval:

```json
{"waivers": [{"case_id": "GOLD-TMP-17", "gate": "gold-jev-vs-claude",
              "reason": "why this automation is acceptable", "approved_by": "reviewer",
              "date": "2026-09-26"}]}
```

Every field is required and non-empty, `date` is `YYYY-MM-DD`, and `gate` is a gate name or `*`
for every gate (a command-line run without `--config` has no gate name, so only `*` waivers apply
there). A malformed file exits 2. Waivers cover newly unsafe cases only: regressions and engine
drift cannot be waived. The report lists waived cases in their own section, and a waiver that
matches no newly unsafe case is reported as a stale waiver, which is a warning, not a failure.

**CI.** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every push and pull request
on ubuntu-latest with uv and Python 3.12. It installs with `uv sync --frozen`, runs `ruff check`,
`ruff format --check` and `pytest -q` (live tests are deselected by default), regenerates
gen-v0.2-dev and gen-v0.2-holdout with `relay generate` and checks both against the committed
manifests with `--verify` (a few seconds locally), then runs the committed gates and uploads
`regression-report/` as an artifact, even when a step fails. The workflow references no secrets
and sets no provider keys, and a test checks that it contains no `secrets.` reference.
````

- [ ] **Step 5: Check the README against the real outputs**

```bash
python3 - <<'EOF'
text = open("README.md", encoding="utf-8").read()
for path in ("/tmp/relay-fail.txt", "/tmp/relay-pass.txt", "/tmp/relay-replay1.txt", "/tmp/relay-replay2.txt"):
    out = open(path, encoding="utf-8").read().rstrip("\n")
    assert out in text, f"{path} is not pasted verbatim in README.md"
print("README outputs match")
EOF
rm -f /tmp/relay-fail.txt /tmp/relay-pass.txt /tmp/relay-replay1.txt /tmp/relay-replay2.txt
```

Expected: `README outputs match`.

- [ ] **Step 6: Final verification**

```bash
uv run ruff check --fix . && uv run ruff format . && uv run pytest -q
git status --short evals/baselines evals/gold evals/smoke evals/generated/manifests
grep -n "secrets\." .github/workflows/ci.yml
```

Expected: every check passes and every test passes (about 988 passed, 2 deselected). Both `git status` and `grep` print nothing.

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: add the Regression gate section, CI badge and refreshed replay output" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Self-review against the spec

| Spec item | Task |
|---|---|
| F1: thresholds follow the target version; exit 2 or `EvalError`; `override_auto_process` at replay, replay_run, compare, frontier, report | 1 |
| F2: `diff_case`/`diff_runs`; id-set check naming missing and extra ids; one policy load per id; refactored replay and `drifted_cases` | 2 |
| F3: `labelled`, `None` fields, `EXPECTED: not available (unlabelled)` | 3 |
| F4: `crossed_gated`; reported-only in parentheses | 4 |
| G1: offline only | 7, 9 (no-client test) |
| G2: candidate sources, `--reproduce` rules, `--baseline-at`, (0, 1] | 7, 9 |
| G3: pairing, full coverage, content hashes, `sample_limit` | 7 |
| G4: `RegressionResult` with CP 95% intervals, calibration deltas, counts, case lists, waived, verdict | 5, 6 |
| G5: gate criteria (a), (b), (c) and exit codes | 6, 9 |
| G6: waiver schema, stale warning, waivers cover newly unsafe only | 6, 7 |
| G7: output order, replay commands, `--json`, `--out` artifacts, `--all` | 7, 8, 9 |
| G8: config mode, `--gate`, summary, highest exit code, `requires_generated` skip | 7, 9 |
| §4: gold reproduce ×4, smoke reproduce, `gold-jev-vs-claude`, holdout ×3; example waiver | 10 |
| §5: CI steps, no secrets, badge | 11, 13 |
| §6: budget show/release, note, backup, refusals, README recovery | 12 |
| §8: README section with real pasted output | 13 |
