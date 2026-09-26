# Phase 3A Replay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `relay replay CASE_ID` shows one stored trace beside a candidate outcome for the same case. The candidate comes from one of four sources: reproduce, policy replay, another run's trace, or a live provider call. The command labels every difference in judgment, confidence, threshold, policy, gate path and action, and its exit codes let scripts gate on engine drift and new unsafe automation.

**Architecture:** A pure diff core in `relay/evaluation/tracediff.py` holds `TraceDiff`, the crossed-threshold table, the labels, the exit-code rule, and `replay_trace`/`replay_run`. A text renderer goes in `relay/reporting.py`. A thin `replay` Typer command in `relay/cli.py` loads one trace, rebuilds the frozen case (verified by content hash), builds the candidate and prints the diff. Live candidates go through the existing `_execute` runner path, so every key and budget guard applies unchanged.

**Tech Stack:** Python 3.12, uv, Pydantic v2, Typer (tests use `typer.testing.CliRunner`), pytest (`asyncio_mode=auto`, `-m 'not live'` by default), ruff.

**Spec:** `docs/superpowers/specs/2026-09-26-phase3a-replay-design.md` (approved). Work in `/Users/joelbrook/Desktop/Code/Relay` on branch `feat/phase3`.

## Global Constraints

- Synthetic data only.
- Never open, print or source `.env`. Every CLI invocation in tests passes `--env-file <tmp>/missing.env`. Offline shell runs use `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env ...`.
- No paid API calls in any task. Tests use fakes (`tests/claude_fakes.py` and fake TypeSafe clients). The README examples run offline on committed traces.
- Stage files by explicit path. Never `git add -A` or `git add .`.
- Every commit uses two `-m` arguments, and the second is exactly `-m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.
- Don't push.
- `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q` must pass at the end of every task.
- Committed baselines (`evals/baselines/**`) and `evals/gold/**` are never modified.
- Exit codes for `relay replay`: 0 success; 2 usage or input error; 3 ENGINE DRIFT (reproduce mode only); 4 NEWLY UNSAFE (any mode). When both 3 and 4 apply, the higher code wins.

## Where the spec was silent or conflicted with the code

Each task below already builds these decisions in. They are listed here for reviewers.

1. **The README `--at` example uses 0.89, not 0.95.** Every committed gold trace was recorded at `auto_process=0.95`, so `--at 0.95` changes nothing. 0.89 is Jev's own dev-selected threshold (from `evals/baselines/gold-v0.1/compare-own-thresholds.txt`). At that value, GOLD-TMP-17 moves HUMAN_REVIEW → AUTO_PROCESS (NEWLY UNSAFE, exit 4).
2. **`--question-set` is an alias.** The spec says `--question-set`, but run and eval use `--questions`. Replay accepts both spellings and validates through the existing `_resolve_questions`.
3. **P5 needs the current policy text hash, and `diff_traces` stays pure.** The caller computes the hash and passes it as a required keyword, `current_policy_text_hash`. `TraceDiff` also stores `policy_text_hash_original` and `policy_text_hash_current`, so the renderer can print `<old8> → <new8>`.
4. **`crossed` has rows the engine never compares.** Two of the spec's auto_process comparisons have no engine counterpart: `material_contradiction` (1 − p_yes ≥ t) and `missing_evidence` (p(NONE) ≥ t). The table marks them `gate=None`. The engine-agreement test covers every row that has a gate, and a separate test pins the two reported-only rows.
5. **"Unchanged" versus "changed-both-wrong".** When both sides are wrong, the change is `changed-both-wrong` if the two actions differ and `unchanged` if they are the same. When both sides are correct, it is `unchanged`, even if the actions differ because each side has its own expected action.
6. **Default gate rendering.** By default, a gate row is shown only when its status (`passed` / `FIRED` / `not reached`) differs between the sides. Rows where only the detail text differs appear with `--all-gates`.
7. **Where the reproduce verdict goes.** In reproduce mode, `REPRODUCED` or `ENGINE DRIFT` is printed under the header and again as the last line. The `ACTION CHANGED` / `ACTION UNCHANGED` line always comes just before it, so `NEWLY UNSAFE` is never hidden.
8. **Candidate traces must be on the same inputs.** A candidate trace whose `case_content_hash` differs from the original's is exit 2.
9. **Live candidates with `--json`.** The run's own messages (budget, provider note, spend, run id) are redirected to stderr, so stdout is pure JSON. `--mode batch` is exit 2. The live run uses the original trace's `policy_version`. A new `--traces-dir` option (default `traces`) sets where its trace file goes.
10. **The git SHA is looked up once per run.** `replay_trace` gains `git_sha: str | None = None`, and None means `current_git_sha()`. `replay_run` looks up the SHA once and passes it to every trace. `replay_trace` also raises `ValueError` when given the wrong case or changed inputs.
11. **Case loading.** The case is loaded with `load_case(dataset / CASE_ID)`, not the whole dataset. A missing folder is exit 2.
12. **Threshold versions.** Replayed thresholds keep their `version` string (`v0.1`) when `--at` changes `auto_process`. This matches `compare --at` and the frontier sweep. `mode="simulated"` marks the trace as a replay.

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `relay/traces/models.py` | modify | `WorkflowTrace.replay_of: str \| None = None` |
| `relay/cases/policies.py` | modify | `latest_policy_for(policy_id) -> str` |
| `relay/evaluation/tracediff.py` | create | the diff models, crossed-threshold table, classification, labels, exit-code rule, `replay_trace`, `replay_run` |
| `relay/reporting.py` | modify | `render_trace_diff`, `replay_summary`, `REPRODUCED_LINE`, `DRIFT_LINE` |
| `relay/cli.py` | modify | the `replay` command and its helpers |
| `tests/unit/test_policies.py` | create | `latest_policy_for` |
| `tests/unit/test_trace_store.py` | modify | `replay_of` round trip; old traces still load |
| `tests/unit/test_tracediff.py` | create | the diff core, including the table-vs-engine agreement |
| `tests/unit/test_replay.py` | create | `replay_trace` / `replay_run` |
| `tests/unit/test_reporting_replay.py` | create | the renderer |
| `tests/integration/test_cli_replay.py` | create | offline CLI: every mode and exit code, keyless, fakes for live |
| `tests/integration/test_committed_baselines.py` | modify | the gold reproduce guard |
| `README.md` | modify | the "Replay" section with real output, a command line, and doc links |

---

### Task 1: `replay_of` on traces and `latest_policy_for`

**Files:**
- Modify: `relay/traces/models.py` (the end of `WorkflowTrace`)
- Modify: `relay/cases/policies.py` (append)
- Create: `tests/unit/test_policies.py`
- Modify: `tests/unit/test_trace_store.py` (append)

**Interfaces:**
- Consumes: the existing `relay.cases.policies._POLICIES: dict[str, dict[str, object]]` (each spec has `"version"` like `"v0.1"` and `"medication"` like `"Immunara"`). Also the existing `WorkflowTrace`, `TraceStore` and `read_traces`.
- Produces:
  - `WorkflowTrace.replay_of: str | None = None`. Old traces load with None.
  - `latest_policy_for(policy_id: str) -> str` in `relay/cases/policies.py`. It returns the id of the registered policy with the same `medication` and the highest version, with versions compared numerically after the leading `v` is stripped (`v0.10` > `v0.9`). It raises `KeyError("unknown policy '<id>'; known: [...]")` for an unknown id.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_policies.py`:

```python
"""latest_policy_for: the newest registered policy for the same medication."""

import pytest

import relay.cases.policies as policies_module
from relay.cases.policies import latest_policy_for


def spec(version: str, medication: str) -> dict[str, object]:
    return {
        "version": version,
        "medication": medication,
        "indication": "rheumatoid arthritis",
        "min_age": 18,
        "required_therapy": "methotrexate",
        "min_weeks": 12,
        "text_file": "unused.md",
    }


@pytest.fixture
def registry(monkeypatch):
    fake = {
        "immunara-v0.1": spec("v0.1", "Immunara"),
        "immunara-v0.9": spec("v0.9", "Immunara"),
        "immunara-v0.10": spec("v0.10", "Immunara"),
        "otheria-v2.0": spec("v2.0", "Otheria"),
    }
    monkeypatch.setattr(policies_module, "_POLICIES", fake)
    return fake


def test_the_real_registry_resolves_immunara_to_itself():
    assert latest_policy_for("immunara-v0.1") == "immunara-v0.1"


def test_versions_compare_numerically_not_as_text(registry):
    assert latest_policy_for("immunara-v0.1") == "immunara-v0.10"
    assert latest_policy_for("immunara-v0.9") == "immunara-v0.10"
    assert latest_policy_for("immunara-v0.10") == "immunara-v0.10"


def test_other_medications_are_never_candidates(registry):
    assert latest_policy_for("otheria-v2.0") == "otheria-v2.0"


def test_an_unknown_policy_is_a_key_error_naming_the_known_ones(registry):
    with pytest.raises(KeyError, match="unknown policy 'nope'"):
        latest_policy_for("nope")
```

Append to `tests/unit/test_trace_store.py`. It already imports `Path`, `TraceStore`, `read_traces`, `make_case` and `make_trace`.

```python
GOLD_JEV_TRACES = (
    Path(__file__).resolve().parents[2]
    / "evals"
    / "baselines"
    / "gold-v0.1"
    / "run_20260925T170857Z_b95be9"
    / "traces.jsonl.gz"
)


def test_replay_of_defaults_to_none_and_round_trips(tmp_path):
    trace = make_trace(make_case())
    assert trace.replay_of is None
    replayed = trace.model_copy(update={"replay_of": trace.trace_id, "mode": "simulated"})
    store = TraceStore.create(tmp_path, "run_x")
    store.append(replayed)
    assert read_traces(store.path) == [replayed]


def test_committed_traces_written_before_replay_of_still_load():
    traces = read_traces(GOLD_JEV_TRACES)
    assert len(traces) == 100
    assert all(t.replay_of is None for t in traces)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_policies.py tests/unit/test_trace_store.py -q`
Expected: FAIL. `ImportError: cannot import name 'latest_policy_for'` in test_policies, and `AttributeError: 'WorkflowTrace' object has no attribute 'replay_of'` in test_trace_store.

- [ ] **Step 3: Implement**

In `relay/traces/models.py`, replace the last two fields of `WorkflowTrace`:

```python
    mode: Literal["evaluate", "shadow", "simulated"] = "evaluate"
    relay_git_sha: str | None
```

with:

```python
    mode: Literal["evaluate", "shadow", "simulated"] = "evaluate"
    relay_git_sha: str | None
    # The trace_id this trace was replayed from (relay replay); None for ordinary runs and for
    # every trace written before Phase 3A.
    replay_of: str | None = None
```

Append to `relay/cases/policies.py`:

```python
def _version_key(version: str) -> tuple[int, ...]:
    """'v0.10' -> (0, 10): versions compare numerically, so v0.10 sorts after v0.9."""
    return tuple(int(part) for part in version.removeprefix("v").split("."))


def latest_policy_for(policy_id: str) -> str:
    """The id of the registered policy for the same medication with the highest version."""
    try:
        medication = _POLICIES[policy_id]["medication"]
    except KeyError:
        raise KeyError(f"unknown policy {policy_id!r}; known: {sorted(_POLICIES)}") from None
    same = [pid for pid, spec in _POLICIES.items() if spec["medication"] == medication]
    return max(same, key=lambda pid: _version_key(str(_POLICIES[pid]["version"])))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_policies.py tests/unit/test_trace_store.py -q`
Expected: PASS

- [ ] **Step 5: Full check**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass (the committed baselines still load and re-score unchanged).

- [ ] **Step 6: Commit**

```bash
git add relay/traces/models.py relay/cases/policies.py tests/unit/test_policies.py tests/unit/test_trace_store.py
git commit -m "feat: add replay_of to traces and latest_policy_for" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The trace diff core (`relay/evaluation/tracediff.py`)

**Files:**
- Create: `relay/evaluation/tracediff.py`
- Create: `tests/unit/test_tracediff.py`

**Interfaces:**
- Consumes these existing names:
  - `WorkflowTrace` (with `replay_of` from Task 1)
  - `DecisionBundle.get(question_id) -> Decision | None`
  - `Decision` (`kind`, `p_yes`, `answer`, `probabilities`, `.probability`)
  - `DecisionId` (five members, in order: diagnosis_support, step_therapy, documentation_complete, material_contradiction, missing_evidence)
  - `Thresholds` (fields `version`, `auto_process`, `contradiction_review`, `contradiction_auto_block`, `documentation_request_info`, `missing_evidence_request_info`)
  - `GateResult(gate, fired, detail)` and `WorkflowAction`
  - `MissingEvidence.NONE`
  - the tests also use `relay.evaluation.runner.policy_text_hash(policy) -> "sha256:<hex>"` and `tests.factories.make_bundle` / `make_case`
- Produces (all in `relay.evaluation.tracediff`):
  - `EXIT_ENGINE_DRIFT = 3` and `EXIT_NEWLY_UNSAFE = 4`
  - `GATE_ORDER: tuple[str, ...]` and `THRESHOLD_NAMES: tuple[str, ...]`
  - `REPRODUCE_LABEL: str`
  - `Crossing(compare, gate)` and `CROSSINGS: dict[tuple[DecisionId, str], Crossing]`
  - the models `DecisionDelta`, `GateDelta` and `TraceDiff` (fields exactly as in the code below)
  - `classify(action, expected) -> Literal["correct", "wrong-safe", "UNSAFE"]`
  - `render_decision(decision | None) -> str`
  - `crossed_thresholds(question_id, original, candidate, thresholds_original, thresholds_candidate) -> list[str]`
  - `diff_traces(original, candidate, *, expected_original, expected_candidate, original_label, candidate_label, current_policy_text_hash) -> TraceDiff`. It raises `ValueError` when the case ids differ.
  - `replay_exit_code(diff, *, reproduce: bool) -> int`
  - the label builders: `original_label(trace)`, `policy_replay_label(policy, auto_process: float | None)`, `candidate_trace_label(trace)` and `live_label(trace)`

Background for the crossed table (from `relay/workflow/engine.py::determine_action`). The gates run in this order: provider, age, contradiction (`p_yes(material_contradiction) >= contradiction_review` fires), documentation (`p_yes(documentation_complete) < documentation_request_info` fires), missing_evidence (`answer != NONE and probability >= missing_evidence_request_info` fires), auto_process (fires when diagnosis_support, step_therapy and documentation_complete are all `p_yes >= auto_process` and `p_yes(material_contradiction) < contradiction_auto_block`), and default_review. The spec also names two auto_process comparisons the engine never makes: material_contradiction `1 - p_yes >= t` and missing_evidence `p(NONE) >= t`. They are reported with `gate=None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tracediff.py`:

```python
"""The trace diff core: decision deltas, the crossed-threshold table, gates and classification."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from relay.cases.policies import load_policy
from relay.decisions.base import DecisionId
from relay.evaluation.runner import policy_text_hash
from relay.evaluation.tracediff import (
    CROSSINGS,
    EXIT_ENGINE_DRIFT,
    EXIT_NEWLY_UNSAFE,
    REPRODUCE_LABEL,
    THRESHOLD_NAMES,
    TraceDiff,
    candidate_trace_label,
    classify,
    diff_traces,
    live_label,
    original_label,
    policy_replay_label,
    replay_exit_code,
)
from relay.traces.models import WorkflowTrace
from relay.workflow.engine import determine_action
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1
from tests.factories import make_bundle, make_case

POLICY = load_policy("immunara-v0.1")
POLICY_V2 = POLICY.model_copy(update={"id": "immunara-v0.2", "version": "v0.2"})
CURRENT = policy_text_hash(POLICY)
T = THRESHOLDS_V0_1
CASE = make_case("T-01")
AUTO = WorkflowAction.AUTO_PROCESS
INFO = WorkflowAction.REQUEST_INFO
REVIEW = WorkflowAction.HUMAN_REVIEW
DIAG = DecisionId.DIAGNOSIS_SUPPORT
STEP = DecisionId.STEP_THERAPY
DOC = DecisionId.DOCUMENTATION_COMPLETE
CONTRA = DecisionId.MATERIAL_CONTRADICTION
MISSING = DecisionId.MISSING_EVIDENCE


def trace_for(
    bundle=None,
    *,
    thresholds=T,
    policy=POLICY,
    run_id="run_a",
    text_hash: str | None = "use-policy",
) -> WorkflowTrace:
    """A trace whose action, reasons and gate path come from the real engine."""
    bundle = bundle or make_bundle("T-01")
    outcome = determine_action(CASE.input, bundle, policy, thresholds)
    return WorkflowTrace(
        trace_id=f"tr_{run_id}",
        run_id=run_id,
        timestamp=datetime(2026, 9, 26, tzinfo=UTC),
        case_id="T-01",
        case_content_hash=CASE.input.content_hash(),
        dataset_id="test",
        provider=bundle.provider,
        provider_version=bundle.provider_version,
        question_set_version=bundle.question_set_version,
        question_set_hash=bundle.question_set_hash,
        policy_id=policy.id,
        policy_version=policy.version,
        policy_text_hash=policy_text_hash(policy) if text_hash == "use-policy" else text_hash,
        thresholds=thresholds,
        decisions=bundle,
        action=outcome.action,
        decision_reasons=outcome.reasons,
        gate_path=outcome.gate_path,
        relay_git_sha="abc123",
    )


def diff(
    original,
    candidate,
    *,
    expected_original=REVIEW,
    expected_candidate=REVIEW,
    current_hash: str | None = CURRENT,
):
    return diff_traces(
        original,
        candidate,
        expected_original=expected_original,
        expected_candidate=expected_candidate,
        original_label="orig",
        candidate_label="cand",
        current_policy_text_hash=current_hash,
    )


def row(d, question_id):
    return next(x for x in d.decisions if x.question_id == question_id)


def gate_fired(trace, gate):
    """True/False for a gate the engine reached, None if it never got there."""
    return next((g.fired for g in trace.gate_path if g.gate == gate), None)


# ---- the crossed-threshold table against the engine ----

# For each gated (decision, threshold) row: make_bundle kwargs putting that one decision just on
# the comparison's True side and just on its False side of threshold t. Every other decision
# stays at make_bundle's defaults, which pass every gate (AUTO_PROCESS).
ENGINE_CASES = {
    (DIAG, "auto_process"): lambda t: ({"diag": t + 0.01}, {"diag": t - 0.01}),
    (STEP, "auto_process"): lambda t: ({"step": t + 0.01}, {"step": t - 0.01}),
    (DOC, "auto_process"): lambda t: ({"doc": t + 0.01}, {"doc": t - 0.01}),
    (CONTRA, "contradiction_review"): lambda t: ({"contra": t + 0.01}, {"contra": t - 0.01}),
    (CONTRA, "contradiction_auto_block"): lambda t: (
        {"contra": t + 0.01},
        {"contra": t - 0.01},
    ),
    (DOC, "documentation_request_info"): lambda t: ({"doc": t + 0.01}, {"doc": t - 0.01}),
    (MISSING, "missing_evidence_request_info"): lambda t: (
        {"missing": "DOSAGE", "missing_p": t + 0.01},
        {"missing": "DOSAGE", "missing_p": t - 0.01},
    ),
}


def test_every_threshold_has_at_least_one_crossing_row():
    assert {name for _, name in CROSSINGS} == set(THRESHOLD_NAMES)
    assert set(THRESHOLD_NAMES) == {
        "auto_process",
        "contradiction_review",
        "contradiction_auto_block",
        "documentation_request_info",
        "missing_evidence_request_info",
    }


def test_every_gated_row_is_checked_against_the_engine():
    assert set(ENGINE_CASES) == {key for key, c in CROSSINGS.items() if c.gate is not None}


@pytest.mark.parametrize("key", list(ENGINE_CASES), ids=lambda k: f"{k[0]}-{k[1]}")
def test_crossing_a_threshold_flips_the_engine_gate_and_is_named(key):
    question_id, name = key
    true_side, false_side = ENGINE_CASES[key](getattr(T, name))
    a = trace_for(make_bundle("T-01", **true_side))
    b = trace_for(make_bundle("T-01", **false_side))
    gate = CROSSINGS[key].gate
    assert gate_fired(a, gate) is not None and gate_fired(b, gate) is not None
    assert gate_fired(a, gate) != gate_fired(b, gate)
    d = diff(a, b)
    assert row(d, question_id).crossed == [name]
    assert all(x.crossed == [] for x in d.decisions if x.question_id != question_id)


@pytest.mark.parametrize("key", list(ENGINE_CASES), ids=lambda k: f"{k[0]}-{k[1]}")
def test_a_move_that_stays_on_one_side_flips_nothing(key):
    question_id, name = key
    t = getattr(T, name)
    near, _ = ENGINE_CASES[key](t)
    far, _ = ENGINE_CASES[key](t + 0.01)
    a = trace_for(make_bundle("T-01", **near))
    b = trace_for(make_bundle("T-01", **far))
    gate = CROSSINGS[key].gate
    assert gate_fired(a, gate) == gate_fired(b, gate)
    assert all(x.crossed == [] for x in diff(a, b).decisions)


def test_reported_only_rows_are_named_but_do_not_move_the_engine():
    # material_contradiction vs auto_process compares 1 - p_yes: 0.96 vs 0.94 crosses 0.95,
    # but the engine only compares contradiction with contradiction_review/auto_block.
    a = trace_for(make_bundle("T-01", contra=0.04))
    b = trace_for(make_bundle("T-01", contra=0.06))
    assert (a.action, b.action) == (AUTO, AUTO)
    assert row(diff(a, b), CONTRA).crossed == ["auto_process"]
    # missing_evidence vs auto_process compares p(NONE).
    c = trace_for(make_bundle("T-01", missing="NONE", missing_p=0.96))
    e = trace_for(make_bundle("T-01", missing="NONE", missing_p=0.90))
    assert (c.action, e.action) == (AUTO, AUTO)
    assert row(diff(c, e), MISSING).crossed == ["auto_process"]


def test_a_pure_threshold_change_shows_as_crossed():
    bundle = make_bundle("T-01", step=0.93)
    a = trace_for(bundle)
    b = trace_for(bundle, thresholds=T.model_copy(update={"auto_process": 0.9}))
    d = diff(a, b)
    assert row(d, STEP).crossed == ["auto_process"]
    assert row(d, STEP).delta == 0.0
    assert row(d, DIAG).crossed == []
    assert d.thresholds == {"auto_process": (0.95, 0.9)}
    assert (d.action_original, d.action_candidate) == (REVIEW, AUTO)


# ---- decision deltas ----


def test_yes_no_delta_and_rendering():
    a = trace_for(make_bundle("T-01", step=0.93))
    b = trace_for(make_bundle("T-01", step=0.55))
    r = row(diff(a, b), STEP)
    assert (r.kind, r.original, r.candidate) == ("yes_no", "p_yes=0.930", "p_yes=0.550")
    assert r.delta == pytest.approx(-0.38)
    assert r.answer_changed is False


def test_yes_no_answer_changes_when_p_yes_crosses_one_half():
    a = trace_for(make_bundle("T-01", diag=0.6))
    b = trace_for(make_bundle("T-01", diag=0.4))
    assert row(diff(a, b), DIAG).answer_changed is True


def test_choice_delta_tracks_the_original_answers_probability():
    a = trace_for(make_bundle("T-01", missing="NONE", missing_p=0.9))
    b = trace_for(make_bundle("T-01", missing="DOSAGE", missing_p=0.8))
    r = row(diff(a, b), MISSING)
    assert (r.kind, r.original, r.candidate) == ("choice", "NONE (0.90)", "DOSAGE (0.80)")
    assert r.answer_changed is True
    assert r.delta == pytest.approx(-0.9)  # candidate gives NONE no probability at all


def test_a_decision_missing_on_one_side():
    a = trace_for(make_bundle("T-01"))
    b = trace_for(make_bundle("T-01", error="boom"))
    r = row(diff(a, b), STEP)
    assert (r.kind, r.original, r.candidate) == ("yes_no", "p_yes=0.990", "missing")
    assert (r.answer_changed, r.delta, r.crossed) == (True, None, [])


def test_a_decision_missing_on_both_sides():
    a = trace_for(make_bundle("T-01", error="boom"))
    b = trace_for(make_bundle("T-01", error="bang"))
    r = row(diff(a, b), MISSING)
    assert (r.kind, r.original, r.candidate) == (None, "missing", "missing")
    assert (r.answer_changed, r.delta, r.crossed) == (False, None, [])


def test_deltas_cover_all_five_decisions_in_order():
    d = diff(trace_for(), trace_for())
    assert [x.question_id for x in d.decisions] == list(DecisionId)


# ---- gates ----


def test_gate_rows_are_the_union_of_both_paths_in_engine_order():
    a = trace_for(make_bundle("T-01"))  # AUTO_PROCESS
    b = trace_for(make_bundle("T-01", contra=0.9))  # contradiction fires
    rows = {g.gate: g for g in diff(a, b).gates}
    assert list(rows) == [
        "provider",
        "age",
        "contradiction",
        "documentation",
        "missing_evidence",
        "auto_process",
    ]
    assert (rows["contradiction"].original, rows["contradiction"].candidate) == (
        "passed",
        "FIRED",
    )
    assert (rows["auto_process"].original, rows["auto_process"].candidate) == (
        "FIRED",
        "not reached",
    )
    assert rows["auto_process"].detail_candidate is None
    assert rows["contradiction"].detail_candidate.startswith("p_yes(material_contradiction)=0.900")


def test_default_review_appears_when_either_path_reaches_it():
    a = trace_for(make_bundle("T-01"))
    b = trace_for(make_bundle("T-01", step=0.5))
    rows = {g.gate: g for g in diff(a, b).gates}
    assert (rows["default_review"].original, rows["default_review"].candidate) == (
        "not reached",
        "FIRED",
    )


# ---- classification ----


def test_classify():
    assert classify(REVIEW, REVIEW) == "correct"
    assert classify(INFO, REVIEW) == "wrong-safe"
    assert classify(REVIEW, AUTO) == "wrong-safe"
    assert classify(AUTO, REVIEW) == "UNSAFE"


# (original action, candidate action) with expected HUMAN_REVIEW on both sides:
# REVIEW is correct, INFO is wrong-safe, AUTO is UNSAFE.
MATRIX = [
    (REVIEW, REVIEW, "unchanged", False, False),
    (REVIEW, INFO, "regressed", False, False),
    (REVIEW, AUTO, "regressed", True, False),
    (INFO, REVIEW, "improved", False, False),
    (INFO, INFO, "unchanged", False, False),
    (INFO, AUTO, "changed-both-wrong", True, False),
    (AUTO, REVIEW, "improved", False, True),
    (AUTO, INFO, "changed-both-wrong", False, True),
    (AUTO, AUTO, "unchanged", False, False),
]


@pytest.mark.parametrize("action_o,action_c,change,newly,resolved", MATRIX)
def test_change_classification_matrix(action_o, action_c, change, newly, resolved):
    base = trace_for()
    d = diff(
        base.model_copy(update={"action": action_o}),
        base.model_copy(update={"action": action_c}),
    )
    assert (d.change, d.newly_unsafe, d.unsafe_resolved) == (change, newly, resolved)


def test_two_different_wrong_safe_actions_are_changed_both_wrong():
    base = trace_for()
    d = diff(
        base.model_copy(update={"action": INFO}),
        base.model_copy(update={"action": REVIEW}),
        expected_original=AUTO,
        expected_candidate=AUTO,
    )
    assert (d.change, d.newly_unsafe) == ("changed-both-wrong", False)


def test_each_side_is_judged_against_its_own_expected_action():
    base = trace_for()
    d = diff(
        base.model_copy(update={"action": REVIEW}),
        base.model_copy(update={"action": AUTO}),
        expected_original=REVIEW,
        expected_candidate=AUTO,
    )
    assert (d.change, d.newly_unsafe, d.unsafe_resolved) == ("unchanged", False, False)
    assert (d.expected_original, d.expected_candidate) == (REVIEW, AUTO)


# ---- identical, policy and policy text ----


def test_identical_ignores_latency_cost_and_tokens():
    a = trace_for(make_bundle("T-01", latency_ms=100, cost=Decimal("0.00001")))
    slow = make_bundle("T-01", latency_ms=900, cost=Decimal("0.5"))
    b = trace_for(slow.model_copy(update={"input_tokens": 5}), run_id="run_b")
    assert diff(a, b).identical is True


def test_identical_is_false_when_anything_else_differs():
    a = trace_for(make_bundle("T-01"))
    assert diff(a, trace_for(make_bundle("T-01", derivations={"x": 1}))).identical is False
    assert diff(a, a.model_copy(update={"decision_reasons": ["other"]})).identical is False
    assert diff(a, a.model_copy(update={"gate_path": a.gate_path[:-1]})).identical is False
    assert diff(a, a.model_copy(update={"action": REVIEW})).identical is False


def test_policy_is_reported_only_when_it_differs():
    a = trace_for()
    assert diff(a, trace_for()).policy is None
    b = trace_for(policy=POLICY_V2)
    assert diff(a, b).policy == ("immunara-v0.1 v0.1", "immunara-v0.2 v0.2")


def test_policy_text_change_against_the_current_text_of_the_original_policy():
    current = CURRENT
    same = diff(trace_for(), trace_for(), current_hash=current)
    assert same.policy_text_changed is False
    old = trace_for(text_hash="sha256:" + "0" * 64)
    changed = diff(old, trace_for(), current_hash=current)
    assert changed.policy_text_changed is True
    assert changed.policy_text_hash_original == "sha256:" + "0" * 64
    assert changed.policy_text_hash_current == current
    unrecorded = diff(trace_for(text_hash=None), trace_for(), current_hash=current)
    assert unrecorded.policy_text_changed is None


def test_traces_of_different_cases_cannot_be_diffed():
    a = trace_for()
    with pytest.raises(ValueError, match="different cases"):
        diff(a, a.model_copy(update={"case_id": "T-02"}))


def test_diff_round_trips_through_json():
    d = diff(trace_for(), trace_for(thresholds=T.model_copy(update={"auto_process": 0.9})))
    assert TraceDiff.model_validate_json(d.model_dump_json()) == d


# ---- exit codes and labels ----


def test_replay_exit_codes():
    same = diff(trace_for(), trace_for())
    assert replay_exit_code(same, reproduce=True) == 0
    drift = same.model_copy(update={"identical": False})
    assert replay_exit_code(drift, reproduce=True) == EXIT_ENGINE_DRIFT == 3
    assert replay_exit_code(drift, reproduce=False) == 0
    unsafe = same.model_copy(update={"newly_unsafe": True})
    assert replay_exit_code(unsafe, reproduce=False) == EXIT_NEWLY_UNSAFE == 4
    both = drift.model_copy(update={"newly_unsafe": True})
    assert replay_exit_code(both, reproduce=True) == 4


def test_labels():
    t = trace_for(run_id="run_20260925T170857Z_b95be9")
    assert original_label(t) == (
        "run_20260925T170857Z_b95be9 · test q-test · policy immunara-v0.1 (v0.1) · "
        "thresholds auto_process=0.95"
    )
    assert REPRODUCE_LABEL == "reproduce: stored decisions, current engine, original policy"
    assert policy_replay_label(POLICY, None) == (
        "policy replay: STORED DECISIONS under policy immunara-v0.1 (v0.1) — judgments were "
        "made against the original policy's questions"
    )
    assert policy_replay_label(POLICY_V2, 0.89) == (
        "policy replay: STORED DECISIONS under policy immunara-v0.2 (v0.2), auto_process=0.89 "
        "— judgments were made against the original policy's questions"
    )
    assert candidate_trace_label(t) == "candidate trace run_20260925T170857Z_b95be9 · test q-test"
    assert live_label(t) == ("live run run_20260925T170857Z_b95be9 · test q-test on frozen inputs")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_tracediff.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'relay.evaluation.tracediff'`

- [ ] **Step 3: Implement**

Create `relay/evaluation/tracediff.py`:

```python
"""Compare two traces of the same case: judgments, thresholds, gate path and action.

The diff functions are pure (no I/O). replay_trace / replay_run re-run stored decisions through
today's engine. `relay replay` renders one TraceDiff; the Phase 3B regression gate builds on the
same functions over whole runs.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from relay.cases.models import MissingEvidence
from relay.cases.policies import AuthorizationPolicy
from relay.decisions.base import Decision, DecisionBundle, DecisionId
from relay.traces.models import WorkflowTrace
from relay.workflow.outcomes import GateResult, WorkflowAction
from relay.workflow.thresholds import Thresholds

EXIT_ENGINE_DRIFT = 3
EXIT_NEWLY_UNSAFE = 4

# The engine's gates in the order determine_action runs them.
GATE_ORDER: tuple[str, ...] = (
    "provider",
    "age",
    "contradiction",
    "documentation",
    "missing_evidence",
    "auto_process",
    "default_review",
)
THRESHOLD_NAMES: tuple[str, ...] = tuple(n for n in Thresholds.model_fields if n != "version")
# Bundle fields that vary between otherwise identical runs; ignored by `identical`.
VOLATILE_BUNDLE_FIELDS = frozenset({"latency_ms", "estimated_cost_usd", "input_tokens"})

REPRODUCE_LABEL = "reproduce: stored decisions, current engine, original policy"

Change = Literal["improved", "regressed", "unchanged", "changed-both-wrong"]
Verdict = Literal["correct", "wrong-safe", "UNSAFE"]
Comparison = Callable[[Decision, float], bool | None]


def _p_yes_at_least(decision: Decision, t: float) -> bool | None:
    return None if decision.p_yes is None else decision.p_yes >= t


def _p_no_at_least(decision: Decision, t: float) -> bool | None:
    return None if decision.p_yes is None else 1.0 - decision.p_yes >= t


def _p_none_at_least(decision: Decision, t: float) -> bool | None:
    if decision.kind != "choice":
        return None
    return decision.probabilities.get(MissingEvidence.NONE.value, 0.0) >= t


def _missing_requests_info(decision: Decision, t: float) -> bool | None:
    if decision.kind != "choice" or decision.answer is None:
        return None
    return decision.answer != MissingEvidence.NONE and decision.probability >= t


@dataclass(frozen=True)
class Crossing:
    """How one decision is compared with one threshold.

    `gate` is the engine gate whose outcome that comparison decides, or None for a comparison
    the spec reports but the engine never makes (tests/unit/test_tracediff.py checks every gated
    row against determine_action).
    """

    compare: Comparison
    gate: str | None


CROSSINGS: dict[tuple[DecisionId, str], Crossing] = {
    (DecisionId.DIAGNOSIS_SUPPORT, "auto_process"): Crossing(_p_yes_at_least, "auto_process"),
    (DecisionId.STEP_THERAPY, "auto_process"): Crossing(_p_yes_at_least, "auto_process"),
    (DecisionId.DOCUMENTATION_COMPLETE, "auto_process"): Crossing(_p_yes_at_least, "auto_process"),
    (DecisionId.MATERIAL_CONTRADICTION, "auto_process"): Crossing(_p_no_at_least, None),
    (DecisionId.MISSING_EVIDENCE, "auto_process"): Crossing(_p_none_at_least, None),
    (DecisionId.MATERIAL_CONTRADICTION, "contradiction_review"): Crossing(
        _p_yes_at_least, "contradiction"
    ),
    (DecisionId.MATERIAL_CONTRADICTION, "contradiction_auto_block"): Crossing(
        _p_yes_at_least, "auto_process"
    ),
    (DecisionId.DOCUMENTATION_COMPLETE, "documentation_request_info"): Crossing(
        _p_yes_at_least, "documentation"
    ),
    (DecisionId.MISSING_EVIDENCE, "missing_evidence_request_info"): Crossing(
        _missing_requests_info, "missing_evidence"
    ),
}


class DecisionDelta(BaseModel):
    question_id: DecisionId
    kind: Literal["yes_no", "choice"] | None  # None if missing on both sides
    original: str  # rendered: "p_yes=0.931", "NONE (0.62)" or "missing"
    candidate: str
    answer_changed: bool  # yes/no side of 0.5, choice label, or presence changed
    delta: float | None  # yes_no: p_yes change; choice: change in the ORIGINAL answer's probability
    crossed: list[str]  # threshold names whose comparison flipped for this decision


class GateDelta(BaseModel):
    gate: str
    original: str  # "passed" | "FIRED" | "not reached"
    candidate: str
    detail_original: str | None
    detail_candidate: str | None


class TraceDiff(BaseModel):
    case_id: str
    original_label: str
    candidate_label: str
    decisions: list[DecisionDelta]
    gates: list[GateDelta]  # union of both gate paths in engine order
    thresholds: dict[str, tuple[float, float]]  # only changed thresholds
    policy: tuple[str, str] | None  # ("id version", "id version") when different
    policy_text_changed: bool | None  # None when the original trace has no policy_text_hash
    policy_text_hash_original: str | None
    policy_text_hash_current: str | None
    action_original: WorkflowAction
    action_candidate: WorkflowAction
    reasons_original: list[str]
    reasons_candidate: list[str]
    expected_original: WorkflowAction  # under the original side's policy/thresholds
    expected_candidate: WorkflowAction  # under the candidate side's policy/thresholds
    change: Change
    newly_unsafe: bool
    unsafe_resolved: bool
    identical: bool  # same action, reasons, gate path and decisions (volatile fields ignored)


def classify(action: WorkflowAction, expected: WorkflowAction) -> Verdict:
    if action == expected:
        return "correct"
    if action == WorkflowAction.AUTO_PROCESS:
        return "UNSAFE"
    return "wrong-safe"


def _change(
    action_o: WorkflowAction,
    expected_o: WorkflowAction,
    action_c: WorkflowAction,
    expected_c: WorkflowAction,
) -> Change:
    ok_o, ok_c = action_o == expected_o, action_c == expected_c
    if ok_c and not ok_o:
        return "improved"
    if ok_o and not ok_c:
        return "regressed"
    if not ok_o and not ok_c and action_o != action_c:
        return "changed-both-wrong"
    return "unchanged"


def render_decision(decision: Decision | None) -> str:
    if decision is None:
        return "missing"
    if decision.kind == "yes_no":
        return f"p_yes={decision.p_yes:.3f}"
    return f"{decision.answer} ({decision.probability:.2f})"


def _answer_changed(o: Decision | None, c: Decision | None) -> bool:
    if o is None or c is None:
        return (o is None) != (c is None)
    if o.kind != c.kind:
        return True
    if o.kind == "yes_no":
        assert o.p_yes is not None and c.p_yes is not None
        return (o.p_yes >= 0.5) != (c.p_yes >= 0.5)
    return o.answer != c.answer


def _delta(o: Decision | None, c: Decision | None) -> float | None:
    if o is None or c is None or o.kind != c.kind:
        return None
    if o.kind == "yes_no":
        assert o.p_yes is not None and c.p_yes is not None
        return c.p_yes - o.p_yes
    assert o.answer is not None
    return c.probabilities.get(o.answer, 0.0) - o.probabilities.get(o.answer, 0.0)


def crossed_thresholds(
    question_id: DecisionId,
    original: Decision | None,
    candidate: Decision | None,
    thresholds_original: Thresholds,
    thresholds_candidate: Thresholds,
) -> list[str]:
    """Threshold names (in Thresholds field order) whose comparison for this decision differs
    between the two sides, each side judged against its own thresholds."""
    if original is None or candidate is None:
        return []
    crossed = []
    for name in THRESHOLD_NAMES:
        crossing = CROSSINGS.get((question_id, name))
        if crossing is None:
            continue
        before = crossing.compare(original, getattr(thresholds_original, name))
        after = crossing.compare(candidate, getattr(thresholds_candidate, name))
        if before is not None and after is not None and before != after:
            crossed.append(name)
    return crossed


def _decision_deltas(original: WorkflowTrace, candidate: WorkflowTrace) -> list[DecisionDelta]:
    deltas = []
    for question_id in DecisionId:
        o = original.decisions.get(question_id)
        c = candidate.decisions.get(question_id)
        kind = o.kind if o is not None else (c.kind if c is not None else None)
        deltas.append(
            DecisionDelta(
                question_id=question_id,
                kind=kind,
                original=render_decision(o),
                candidate=render_decision(c),
                answer_changed=_answer_changed(o, c),
                delta=_delta(o, c),
                crossed=crossed_thresholds(
                    question_id, o, c, original.thresholds, candidate.thresholds
                ),
            )
        )
    return deltas


def _gate_status(path: list[GateResult], gate: str) -> tuple[str, str | None]:
    for result in path:
        if result.gate == gate:
            return ("FIRED" if result.fired else "passed"), result.detail
    return "not reached", None


def _gate_deltas(original: WorkflowTrace, candidate: WorkflowTrace) -> list[GateDelta]:
    seen = {g.gate for g in original.gate_path} | {g.gate for g in candidate.gate_path}
    extra = [
        g.gate for g in [*original.gate_path, *candidate.gate_path] if g.gate not in GATE_ORDER
    ]
    order = [g for g in GATE_ORDER if g in seen] + list(dict.fromkeys(extra))
    rows = []
    for gate in order:
        status_o, detail_o = _gate_status(original.gate_path, gate)
        status_c, detail_c = _gate_status(candidate.gate_path, gate)
        rows.append(
            GateDelta(
                gate=gate,
                original=status_o,
                candidate=status_c,
                detail_original=detail_o,
                detail_candidate=detail_c,
            )
        )
    return rows


def _comparable(bundle: DecisionBundle) -> dict:
    return bundle.model_dump(exclude=set(VOLATILE_BUNDLE_FIELDS))


def diff_traces(
    original: WorkflowTrace,
    candidate: WorkflowTrace,
    *,
    expected_original: WorkflowAction,
    expected_candidate: WorkflowAction,
    original_label: str,
    candidate_label: str,
    current_policy_text_hash: str | None,
) -> TraceDiff:
    """Everything that differs between two traces of one case.

    `current_policy_text_hash` is the hash of the current text of the ORIGINAL trace's policy id
    (relay.evaluation.runner.policy_text_hash), computed by the caller to keep this function pure.
    """
    if original.case_id != candidate.case_id:
        raise ValueError(
            f"cannot diff traces of different cases: {original.case_id} vs {candidate.case_id}"
        )
    thresholds = {
        name: (getattr(original.thresholds, name), getattr(candidate.thresholds, name))
        for name in THRESHOLD_NAMES
        if getattr(original.thresholds, name) != getattr(candidate.thresholds, name)
    }
    policy_o = f"{original.policy_id} {original.policy_version}"
    policy_c = f"{candidate.policy_id} {candidate.policy_version}"
    text_hash = original.policy_text_hash
    unsafe_o = classify(original.action, expected_original) == "UNSAFE"
    unsafe_c = classify(candidate.action, expected_candidate) == "UNSAFE"
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
        change=_change(original.action, expected_original, candidate.action, expected_candidate),
        newly_unsafe=unsafe_c and not unsafe_o,
        unsafe_resolved=unsafe_o and not unsafe_c,
        identical=(
            original.action == candidate.action
            and original.decision_reasons == candidate.decision_reasons
            and original.gate_path == candidate.gate_path
            and _comparable(original.decisions) == _comparable(candidate.decisions)
        ),
    )


def replay_exit_code(diff: TraceDiff, *, reproduce: bool) -> int:
    """0, EXIT_ENGINE_DRIFT (reproduce mode only) or EXIT_NEWLY_UNSAFE; the higher code wins."""
    code = 0
    if reproduce and not diff.identical:
        code = EXIT_ENGINE_DRIFT
    if diff.newly_unsafe:
        code = max(code, EXIT_NEWLY_UNSAFE)
    return code


def original_label(trace: WorkflowTrace) -> str:
    return (
        f"{trace.run_id} · {trace.provider} {trace.question_set_version} · policy "
        f"{trace.policy_id} ({trace.policy_version}) · thresholds "
        f"auto_process={trace.thresholds.auto_process:g}"
    )


def policy_replay_label(policy: AuthorizationPolicy, auto_process: float | None) -> str:
    at = "" if auto_process is None else f", auto_process={auto_process:g}"
    return (
        f"policy replay: STORED DECISIONS under policy {policy.id} ({policy.version}){at} — "
        "judgments were made against the original policy's questions"
    )


def candidate_trace_label(trace: WorkflowTrace) -> str:
    return f"candidate trace {trace.run_id} · {trace.provider} {trace.question_set_version}"


def live_label(trace: WorkflowTrace) -> str:
    return (
        f"live run {trace.run_id} · {trace.provider} {trace.question_set_version} on frozen inputs"
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_tracediff.py -q`
Expected: PASS (46 tests)

- [ ] **Step 5: Full check**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add relay/evaluation/tracediff.py tests/unit/test_tracediff.py
git commit -m "feat: add the trace diff core with the crossed-threshold table" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `replay_trace` and `replay_run`

**Files:**
- Modify: `relay/evaluation/tracediff.py` (the import block, then append)
- Create: `tests/unit/test_replay.py`

**Interfaces:**
- Consumes:
  - from Task 2: the `relay/evaluation/tracediff.py` module (its import block is shown in Step 3)
  - existing names: `determine_action(case_input, bundle, policy, thresholds) -> PolicyOutcome(action, reasons, gate_path)`, `paired_cases(traces, cases) -> list[tuple[WorkflowTrace, PriorAuthCase]]` (raises `EvalError`), `load_policy(policy_id)`, `policy_text_hash(policy)`, `new_trace_id()`, `current_git_sha() -> str | None`, and `CaseInput.content_hash()`
- Produces:
  - `replay_trace(trace, case, *, policy, thresholds, now: datetime | None = None, git_sha: str | None = None) -> WorkflowTrace`. The new trace has a new `trace_id`, `run_id=f"replay-{trace.run_id}"`, `replay_of=trace.trace_id`, the candidate policy's id, version and `policy_text_hash`, the given thresholds, `mode="simulated"`, and `relay_git_sha=git_sha or current_git_sha()`. The decisions are unchanged. It raises `ValueError` for the wrong case or changed inputs.
  - `replay_run(traces, cases, *, policy_id: str | None, auto_process: float | None) -> list[WorkflowTrace]`. The result is in trace order, and every trace shares one run_id. It raises `EvalError` through `paired_cases`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_replay.py`:

```python
"""replay_trace / replay_run: stored decisions re-run through today's engine."""

from datetime import UTC, datetime

import pytest

import relay.evaluation.tracediff as tracediff
from relay.cases.policies import load_policy
from relay.evaluation.metrics import EvalError
from relay.evaluation.runner import policy_text_hash
from relay.evaluation.tracediff import replay_run, replay_trace
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1
from tests.factories import make_bundle, make_case, make_trace

POLICY = load_policy("immunara-v0.1")
POLICY_V2 = POLICY.model_copy(update={"id": "immunara-v0.2", "version": "v0.2", "text": "v2"})
NOW = datetime(2026, 9, 26, 12, tzinfo=UTC)


def test_replay_trace_marks_the_new_trace_as_a_simulated_replay():
    case = make_case("T-01")
    original = make_trace(case)
    replayed = replay_trace(
        original, case, policy=POLICY, thresholds=THRESHOLDS_V0_1, now=NOW, git_sha="deadbeef"
    )
    assert replayed.trace_id != original.trace_id
    assert replayed.trace_id.startswith("tr_")
    assert replayed.run_id == "replay-run_test"
    assert replayed.replay_of == original.trace_id
    assert replayed.mode == "simulated"
    assert replayed.timestamp == NOW
    assert replayed.relay_git_sha == "deadbeef"
    assert replayed.policy_text_hash == policy_text_hash(POLICY)
    assert replayed.decisions == original.decisions
    assert (replayed.action, replayed.decision_reasons, replayed.gate_path) == (
        original.action,
        original.decision_reasons,
        original.gate_path,
    )


def test_replay_trace_uses_the_candidate_policy_and_thresholds():
    case = make_case("T-01")
    original = make_trace(case, make_bundle("T-01", step=0.93))
    assert original.action == WorkflowAction.HUMAN_REVIEW
    lower = THRESHOLDS_V0_1.model_copy(update={"auto_process": 0.9})
    replayed = replay_trace(original, case, policy=POLICY_V2, thresholds=lower, git_sha="x")
    assert replayed.action == WorkflowAction.AUTO_PROCESS
    assert (replayed.policy_id, replayed.policy_version) == ("immunara-v0.2", "v0.2")
    assert replayed.policy_text_hash == policy_text_hash(POLICY_V2)
    assert replayed.thresholds.auto_process == 0.9


def test_replay_trace_defaults_git_sha_to_the_current_commit(monkeypatch):
    monkeypatch.setattr(tracediff, "current_git_sha", lambda: "cafef00d")
    case = make_case("T-01")
    replayed = replay_trace(make_trace(case), case, policy=POLICY, thresholds=THRESHOLDS_V0_1)
    assert replayed.relay_git_sha == "cafef00d"


def test_replay_trace_refuses_another_case_or_changed_inputs():
    case = make_case("T-01")
    trace = make_trace(case)
    with pytest.raises(ValueError, match="is not the trace's case"):
        replay_trace(trace, make_case("T-02"), policy=POLICY, thresholds=THRESHOLDS_V0_1)
    older = make_case("T-01", age=41)
    with pytest.raises(ValueError, match="content hash changed"):
        replay_trace(trace, older, policy=POLICY, thresholds=THRESHOLDS_V0_1)


def run_of(*case_ids, run_id="run_a"):
    cases = [make_case(i) for i in case_ids]
    return cases, [make_trace(c, make_bundle(c.input.id, step=0.93), run_id=run_id) for c in cases]


def test_replay_run_shares_one_run_id_and_applies_the_overrides():
    cases, traces = run_of("T-01", "T-02")
    replayed = replay_run(traces, cases, policy_id=None, auto_process=0.9)
    assert [t.case_id for t in replayed] == ["T-01", "T-02"]
    assert {t.run_id for t in replayed} == {"replay-run_a"}
    assert {t.action for t in replayed} == {WorkflowAction.AUTO_PROCESS}
    assert [t.replay_of for t in replayed] == [t.trace_id for t in traces]
    assert len({t.relay_git_sha for t in replayed}) == 1


def test_replay_run_with_no_overrides_keeps_each_traces_policy_and_threshold():
    cases, traces = run_of("T-01")
    [replayed] = replay_run(traces, cases, policy_id=None, auto_process=None)
    assert replayed.thresholds == traces[0].thresholds
    assert replayed.policy_id == traces[0].policy_id
    assert replayed.action == traces[0].action


def test_replay_run_loads_the_named_policy(monkeypatch):
    loaded = []

    def fake_load(policy_id):
        loaded.append(policy_id)
        return POLICY_V2

    monkeypatch.setattr(tracediff, "load_policy", fake_load)
    cases, traces = run_of("T-01", "T-02")
    replayed = replay_run(traces, cases, policy_id="immunara-v0.2", auto_process=None)
    assert loaded == ["immunara-v0.2"]  # loaded once per run, not once per trace
    assert {t.policy_id for t in replayed} == {"immunara-v0.2"}


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda cases, traces: (cases, traces[:1]), "do not cover every case"),
        (lambda cases, traces: (cases, [traces[0], traces[0]]), "duplicate case ids"),
        (
            lambda cases, traces: (
                cases,
                [traces[0], traces[1].model_copy(update={"run_id": "b"})],
            ),
            "multiple runs",
        ),
        (lambda cases, traces: ([make_case("T-01", age=41), cases[1]], traces), "hash changed"),
    ],
)
def test_replay_run_enforces_paired_cases(mutate, message):
    cases, traces = run_of("T-01", "T-02")
    cases, traces = mutate(cases, traces)
    with pytest.raises(EvalError, match=message):
        replay_run(traces, cases, policy_id=None, auto_process=None)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_replay.py -q`
Expected: FAIL with `ImportError: cannot import name 'replay_run' from 'relay.evaluation.tracediff'`

- [ ] **Step 3: Implement**

In `relay/evaluation/tracediff.py`, replace the import block:

```python
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from relay.cases.models import MissingEvidence
from relay.cases.policies import AuthorizationPolicy
from relay.decisions.base import Decision, DecisionBundle, DecisionId
from relay.traces.models import WorkflowTrace
from relay.workflow.outcomes import GateResult, WorkflowAction
from relay.workflow.thresholds import Thresholds
```

with:

```python
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

from relay.cases.models import MissingEvidence, PriorAuthCase
from relay.cases.policies import AuthorizationPolicy, load_policy
from relay.decisions.base import Decision, DecisionBundle, DecisionId
from relay.evaluation.metrics import paired_cases
from relay.evaluation.runner import policy_text_hash
from relay.traces.models import WorkflowTrace
from relay.traces.store import current_git_sha, new_trace_id
from relay.workflow.engine import determine_action
from relay.workflow.outcomes import GateResult, WorkflowAction
from relay.workflow.thresholds import Thresholds
```

Then append to the end of `relay/evaluation/tracediff.py`:

```python
def replay_trace(
    trace: WorkflowTrace,
    case: PriorAuthCase,
    *,
    policy: AuthorizationPolicy,
    thresholds: Thresholds,
    now: datetime | None = None,
    git_sha: str | None = None,
) -> WorkflowTrace:
    """The trace's stored decisions re-run through determine_action under `policy`/`thresholds`.

    Returns a new trace: new trace_id, run_id "replay-<original run_id>", replay_of the original
    trace_id, the given policy (and its current policy_text_hash) and thresholds,
    mode="simulated". `git_sha` defaults to current_git_sha(); replay_run passes it once for a
    whole run. Raises ValueError if `case` is not the trace's case or its inputs changed.
    """
    if case.input.id != trace.case_id:
        raise ValueError(f"case {case.input.id} is not the trace's case {trace.case_id}")
    if case.input.content_hash() != trace.case_content_hash:
        raise ValueError(f"{trace.case_id}: case content hash changed since run {trace.run_id}")
    outcome = determine_action(case.input, trace.decisions, policy, thresholds)
    return trace.model_copy(
        update={
            "trace_id": new_trace_id(),
            "run_id": f"replay-{trace.run_id}",
            "timestamp": now or datetime.now(UTC),
            "policy_id": policy.id,
            "policy_version": policy.version,
            "policy_text_hash": policy_text_hash(policy),
            "thresholds": thresholds,
            "action": outcome.action,
            "decision_reasons": outcome.reasons,
            "gate_path": outcome.gate_path,
            "mode": "simulated",
            "relay_git_sha": git_sha if git_sha is not None else current_git_sha(),
            "replay_of": trace.trace_id,
        }
    )


def replay_run(
    traces: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
    *,
    policy_id: str | None,
    auto_process: float | None,
) -> list[WorkflowTrace]:
    """Run-level policy replay (for Phase 3B), in trace order.

    Pairs traces with cases through paired_cases, so every check there applies (one run, no
    duplicates, no unknown or changed cases, full coverage; EvalError otherwise). None keeps each
    trace's own policy / auto_process. Every replayed trace shares run_id "replay-<run_id>".
    """
    pairs = paired_cases(traces, cases)
    now = datetime.now(UTC)
    git_sha = current_git_sha()
    policies: dict[str, AuthorizationPolicy] = {}
    replayed = []
    for trace, case in pairs:
        target = policy_id or trace.policy_id
        if target not in policies:
            policies[target] = load_policy(target)
        thresholds = (
            trace.thresholds
            if auto_process is None
            else trace.thresholds.model_copy(update={"auto_process": auto_process})
        )
        replayed.append(
            replay_trace(
                trace,
                case,
                policy=policies[target],
                thresholds=thresholds,
                now=now,
                git_sha=git_sha,
            )
        )
    return replayed
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_replay.py tests/unit/test_tracediff.py -q`
Expected: PASS

- [ ] **Step 5: Full check**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass. This introduces no import cycle: `relay.evaluation.runner` and `relay.evaluation.metrics` do not import tracediff.

- [ ] **Step 6: Commit**

```bash
git add relay/evaluation/tracediff.py tests/unit/test_replay.py
git commit -m "feat: add replay_trace and run-level replay_run" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The replay renderer (`render_trace_diff`)

**Files:**
- Modify: `relay/reporting.py` (the imports, then append)
- Create: `tests/unit/test_reporting_replay.py`

**Interfaces:**
- Consumes from Tasks 2 and 3: `TraceDiff`, `GateDelta`, `classify`, `diff_traces` and `replay_trace` in `relay.evaluation.tracediff`.
- Produces, in `relay.reporting`:
  - `REPRODUCED_LINE = "REPRODUCED: identical action, reasons and gate path"`
  - `DRIFT_LINE = "ENGINE DRIFT: today's policy engine no longer reproduces this trace"`
  - `replay_summary(diff) -> str`. This returns `ACTION UNCHANGED: <A>` or `ACTION CHANGED: <A> → <B> (<flag>)`, where the flag is `NEWLY UNSAFE`, `UNSAFE RESOLVED`, or else `diff.change`.
  - `render_trace_diff(diff: TraceDiff, all_gates: bool = False, *, reproduce: bool = False) -> str`

The output layout, in order:
1. the title
2. `ORIGINAL <label>` and `CANDIDATE <label>`
3. the reproduce verdict (reproduce mode only)
4. the policy-text line: `POLICY TEXT CHANGED since the original run (<old8> → <new8>)` or `policy text hash not recorded`, and nothing when the text is unchanged
5. the EXPECTED line
6. the decisions table (`*` marks a changed answer)
7. `THRESHOLDS CHANGED`, if any
8. `POLICY CHANGED`, if any
9. the gate rows (only changed statuses unless `all_gates` is set)
10. `ACTIONS` with each side's verdict and reasons
11. the summary line, then the reproduce verdict again in reproduce mode

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_reporting_replay.py`:

```python
"""render_trace_diff: the terminal output of `relay replay`."""

from relay.cases.policies import load_policy
from relay.evaluation.runner import policy_text_hash
from relay.evaluation.tracediff import diff_traces, replay_trace
from relay.reporting import DRIFT_LINE, REPRODUCED_LINE, render_trace_diff, replay_summary
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1
from tests.factories import make_bundle, make_case, make_trace

POLICY = load_policy("immunara-v0.1")
CURRENT = policy_text_hash(POLICY)
CASE = make_case("T-01")
AUTO = WorkflowAction.AUTO_PROCESS
INFO = WorkflowAction.REQUEST_INFO
REVIEW = WorkflowAction.HUMAN_REVIEW


def original(**bundle_kwargs):
    trace = make_trace(CASE, make_bundle("T-01", **bundle_kwargs))
    return trace.model_copy(update={"policy_text_hash": CURRENT})


def diff(a, b, *, expected=(REVIEW, REVIEW), current=CURRENT):
    return diff_traces(
        a,
        b,
        expected_original=expected[0],
        expected_candidate=expected[1],
        original_label="run_test · test q-test · policy immunara-v0.1 (v0.1) · thresholds "
        "auto_process=0.95",
        candidate_label="reproduce: stored decisions, current engine, original policy",
        current_policy_text_hash=current,
    )


def at(trace, auto_process):
    thresholds = THRESHOLDS_V0_1.model_copy(update={"auto_process": auto_process})
    return replay_trace(trace, CASE, policy=POLICY, thresholds=thresholds, git_sha="x")


def test_header_labels_both_sides_and_the_expected_action():
    a = original()
    text = render_trace_diff(diff(a, a, expected=(AUTO, AUTO)))
    lines = text.splitlines()
    assert lines[0] == "Relay replay — T-01"
    assert lines[1] == (
        "ORIGINAL run_test · test q-test · policy immunara-v0.1 (v0.1) · thresholds "
        "auto_process=0.95"
    )
    assert lines[2] == "CANDIDATE reproduce: stored decisions, current engine, original policy"
    assert "EXPECTED (evaluation-only): AUTO_PROCESS" in lines


def test_reproduce_verdict_is_printed_in_the_header_and_last():
    a = original()
    same = render_trace_diff(diff(a, a, expected=(AUTO, AUTO)), reproduce=True)
    assert same.splitlines()[3] == REPRODUCED_LINE
    assert same.splitlines()[-1] == REPRODUCED_LINE
    drifted = diff(a, a.model_copy(update={"decision_reasons": ["new"]}), expected=(AUTO, AUTO))
    text = render_trace_diff(drifted, reproduce=True)
    assert text.splitlines()[3] == DRIFT_LINE
    assert text.splitlines()[-1] == DRIFT_LINE
    assert REPRODUCED_LINE not in render_trace_diff(diff(a, a, expected=(AUTO, AUTO)))


def test_decisions_table_shows_values_delta_crossed_and_changed_answers():
    a = original(step=0.93, missing="NONE", missing_p=0.9)
    b = at(a, 0.9).model_copy(
        update={"decisions": make_bundle("T-01", step=0.93, missing="DOSAGE", missing_p=0.8)}
    )
    text = render_trace_diff(diff(a, b))
    step = next(line for line in text.splitlines() if "step_therapy" in line)
    assert "p_yes=0.930" in step and "+0.000" in step and step.rstrip().endswith("auto_process")
    missing = next(line for line in text.splitlines() if " missing_evidence " in line)
    assert missing.lstrip().startswith("*")
    assert "NONE (0.90)" in missing and "DOSAGE (0.80)" in missing and "-0.900" in missing
    assert "  (* = answer changed)" in text


def test_changed_thresholds_and_changed_gates_are_listed():
    a = original(step=0.93)
    b = at(a, 0.9)
    text = render_trace_diff(diff(a, b))
    assert "THRESHOLDS CHANGED" in text
    assert "  auto_process  0.95 → 0.9" in text
    assert "GATES (rows whose outcome differs; --all-gates shows every row)" in text
    assert "  auto_process      passed → FIRED" in text
    assert "  default_review    FIRED → not reached" in text
    assert "      original:  min(required p_yes)=0.930, auto at >= 0.95" in text
    assert "  provider " not in text  # unchanged rows are hidden by default


def test_all_gates_shows_every_row():
    a = original(step=0.93)
    text = render_trace_diff(diff(a, at(a, 0.9)), all_gates=True)
    assert "GATES (all rows)" in text
    assert "  provider          passed" in text
    assert "      all five decisions present and well-formed" in text


def test_no_gate_change_says_so():
    a = original()
    text = render_trace_diff(diff(a, a, expected=(AUTO, AUTO)))
    assert "GATES: same outcome at every gate (--all-gates shows every row)" in text
    assert "THRESHOLDS CHANGED" not in text


def test_actions_are_classified_and_the_summary_flags_new_unsafe_automation():
    a = original(step=0.93)
    b = at(a, 0.9)
    text = render_trace_diff(diff(a, b))
    assert "  ORIGINAL  HUMAN_REVIEW (correct)" in text
    assert "  CANDIDATE AUTO_PROCESS (UNSAFE)" in text
    assert "      - step_therapy p_yes=0.930 is below the 0.95 autonomous-action bar" in text
    assert text.splitlines()[-1] == "ACTION CHANGED: HUMAN_REVIEW → AUTO_PROCESS (NEWLY UNSAFE)"


def test_summary_line_variants():
    a = original(step=0.93)
    b = at(a, 0.9)
    assert replay_summary(diff(a, a)) == "ACTION UNCHANGED: HUMAN_REVIEW"
    assert replay_summary(diff(b, a)) == (
        "ACTION CHANGED: AUTO_PROCESS → HUMAN_REVIEW (UNSAFE RESOLVED)"
    )
    assert replay_summary(diff(a, b, expected=(AUTO, AUTO))) == (
        "ACTION CHANGED: HUMAN_REVIEW → AUTO_PROCESS (improved)"
    )
    info = a.model_copy(update={"action": INFO})
    assert replay_summary(diff(a, info)) == (
        "ACTION CHANGED: HUMAN_REVIEW → REQUEST_INFO (regressed)"
    )


def test_expected_actions_that_differ_are_both_printed():
    a = original(step=0.93)
    b = at(a, 0.9)
    text = render_trace_diff(diff(a, b, expected=(REVIEW, AUTO)))
    assert (
        "EXPECTED (evaluation-only) under original thresholds: HUMAN_REVIEW · "
        "under candidate thresholds: AUTO_PROCESS"
    ) in text
    other = b.model_copy(update={"policy_id": "immunara-v0.2", "policy_version": "v0.2"})
    text = render_trace_diff(diff(a, other, expected=(REVIEW, AUTO)))
    assert (
        "EXPECTED (evaluation-only) under immunara-v0.1 v0.1: HUMAN_REVIEW · "
        "under immunara-v0.2 v0.2: AUTO_PROCESS"
    ) in text
    assert "POLICY CHANGED: immunara-v0.1 v0.1 → immunara-v0.2 v0.2" in text


def test_policy_text_lines():
    a = original()
    assert "POLICY TEXT" not in render_trace_diff(diff(a, a))
    old = a.model_copy(update={"policy_text_hash": "sha256:0123456789abcdef"})
    text = render_trace_diff(diff(old, a))
    assert f"POLICY TEXT CHANGED since the original run (01234567 → {CURRENT[7:15]})" in text
    unrecorded = a.model_copy(update={"policy_text_hash": None})
    assert "policy text hash not recorded" in render_trace_diff(diff(unrecorded, a))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_reporting_replay.py -q`
Expected: FAIL with `ImportError: cannot import name 'DRIFT_LINE' from 'relay.reporting'`

- [ ] **Step 3: Implement**

In `relay/reporting.py`, replace:

```python
from relay.evaluation.metrics import EvalSummary, RunIdentity
from relay.traces.models import RunManifest, WorkflowTrace
```

with:

```python
from relay.evaluation.metrics import EvalSummary, RunIdentity
from relay.evaluation.tracediff import GateDelta, TraceDiff, classify
from relay.traces.models import RunManifest, WorkflowTrace
from relay.workflow.outcomes import WorkflowAction
```

Append to the end of `relay/reporting.py`:

```python
REPRODUCED_LINE = "REPRODUCED: identical action, reasons and gate path"
DRIFT_LINE = "ENGINE DRIFT: today's policy engine no longer reproduces this trace"


def _short_hash(value: str | None) -> str:
    return "unknown" if value is None else value.split(":", 1)[-1][:8]


def _expected_line(diff: TraceDiff) -> str:
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


def _table(rows: list[list[str]]) -> list[str]:
    widths = [max(len(r[i]) for r in rows) + 2 for i in range(len(rows[0]))]
    return [
        "".join(cell.ljust(w) for cell, w in zip(r, widths, strict=True)).rstrip() for r in rows
    ]


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
                ", ".join(d.crossed),
            ]
        )
    return [" " + line for line in _table(rows)] + ["  (* = answer changed)"]


def _gate_lines(gates: list[GateDelta], all_gates: bool) -> list[str]:
    shown = gates if all_gates else [g for g in gates if g.original != g.candidate]
    if not all_gates and not shown:
        return ["GATES: same outcome at every gate (--all-gates shows every row)"]
    title = "all rows" if all_gates else "rows whose outcome differs; --all-gates shows every row"
    lines = [f"GATES ({title})"]
    for g in shown:
        status = g.original if g.original == g.candidate else f"{g.original} → {g.candidate}"
        lines.append(f"  {g.gate:<18}{status}")
        if g.detail_original == g.detail_candidate:
            if g.detail_original is not None:
                lines.append(f"      {g.detail_original}")
            continue
        if g.detail_original is not None:
            lines.append(f"      original:  {g.detail_original}")
        if g.detail_candidate is not None:
            lines.append(f"      candidate: {g.detail_candidate}")
    return lines


def _action_lines(
    side: str, action: WorkflowAction, expected: WorkflowAction, reasons: list[str]
) -> list[str]:
    verdict = classify(action, expected)
    return [f"  {side:<10}{action} ({verdict})"] + [f"      - {reason}" for reason in reasons]


def replay_summary(diff: TraceDiff) -> str:
    """ACTION CHANGED: A → B (flag), or ACTION UNCHANGED: A."""
    if diff.action_original == diff.action_candidate:
        return f"ACTION UNCHANGED: {diff.action_original}"
    if diff.newly_unsafe:
        flag = "NEWLY UNSAFE"
    elif diff.unsafe_resolved:
        flag = "UNSAFE RESOLVED"
    else:
        flag = diff.change
    return f"ACTION CHANGED: {diff.action_original} → {diff.action_candidate} ({flag})"


def render_trace_diff(diff: TraceDiff, all_gates: bool = False, *, reproduce: bool = False) -> str:
    """Terminal output for `relay replay`: header, expected action, decisions, thresholds,
    gates, actions and a summary line. In reproduce mode the REPRODUCED / ENGINE DRIFT verdict
    is printed under the header and again as the last line."""
    verdict = (REPRODUCED_LINE if diff.identical else DRIFT_LINE) if reproduce else None
    lines = [
        f"Relay replay — {diff.case_id}",
        f"ORIGINAL {diff.original_label}",
        f"CANDIDATE {diff.candidate_label}",
    ]
    if verdict is not None:
        lines.append(verdict)
    if diff.policy_text_changed is None:
        lines.append("policy text hash not recorded")
    elif diff.policy_text_changed:
        lines.append(
            "POLICY TEXT CHANGED since the original run "
            f"({_short_hash(diff.policy_text_hash_original)} → "
            f"{_short_hash(diff.policy_text_hash_current)})"
        )
    lines += [_expected_line(diff), ""]
    lines += _decision_lines(diff)
    if diff.thresholds:
        lines += ["", "THRESHOLDS CHANGED"]
        lines += [
            f"  {name}  {before:g} → {after:g}" for name, (before, after) in diff.thresholds.items()
        ]
    if diff.policy is not None:
        lines += ["", f"POLICY CHANGED: {diff.policy[0]} → {diff.policy[1]}"]
    lines += [""] + _gate_lines(diff.gates, all_gates)
    lines += ["", "ACTIONS"]
    lines += _action_lines(
        "ORIGINAL", diff.action_original, diff.expected_original, diff.reasons_original
    )
    lines += _action_lines(
        "CANDIDATE", diff.action_candidate, diff.expected_candidate, diff.reasons_candidate
    )
    lines += ["", replay_summary(diff)]
    if verdict is not None:
        lines.append(verdict)
    return "\n".join(lines)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_reporting_replay.py -q`
Expected: PASS (10 tests)

- [ ] **Step 5: Full check**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add relay/reporting.py tests/unit/test_reporting_replay.py
git commit -m "feat: render trace diffs for relay replay" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The `relay replay` command

**Files:**
- Modify: `relay/cli.py` (the module docstring and imports, then append)
- Create: `tests/integration/test_cli_replay.py`

**Interfaces:**
- Consumes:
  - from Tasks 1–4: `latest_policy_for`, `REPRODUCE_LABEL`, `candidate_trace_label`, `diff_traces`, `live_label`, `original_label`, `policy_replay_label`, `replay_exit_code`, `replay_trace` and `TraceDiff`, plus `render_trace_diff`, `REPRODUCED_LINE` and `DRIFT_LINE`
  - existing names in `relay/cli.py`, all unchanged:
    - `_fail(message) -> typer.Exit` (exit 2)
    - `_read_trace_file(path)`
    - `_resolve_questions(provider, questions)`
    - `_resolve_claude(provider, mode, budget_usd, ledger, batch_id=None)`
    - `_preflight(cases, provider, policy)`, which runs the key check from `PROVIDER_KEYS`
    - `_claude_budget_check(claude, cases) -> Decimal`, which prints `Claude budget: ...`
    - `_execute(cases, provider_name, policy, concurrency, traces_dir, dataset, questions, sample=None, claude=None, projected=Decimal("0")) -> (RunManifest, list[WorkflowTrace])`
    - `PROVIDER_NOTES`, `ProviderName` and `ClaudeMode`
    - the annotated option types `TraceFile`, `Dataset`, `ModeOption`, `BudgetUsd` and `LedgerOption`
  - existing library functions: `load_case(case_dir)`, `CaseLoadError`, `load_policy`, `expected_action(case, policy, thresholds)` and `policy_text_hash(policy)`
- Produces:
  - the command `relay replay CASE_ID --traces FILE --dataset DIR [--policy ID | --latest-policy] [--at FLOAT] [--candidate-traces FILE] [--provider P [--questions|--question-set Q] [--mode sync] [--budget-usd N] [--ledger PATH] [--traces-dir DIR]] [--all-gates] [--json]`
  - the exit codes 0, 2, 3 and 4 as defined in Global Constraints

Behaviour notes:
- The candidate sources (policy replay, `--candidate-traces`, `--provider`) are mutually exclusive, and so are `--policy` and `--latest-policy`. Live-only flags without `--provider` are rejected. All of these are exit 2 and are checked before any file is read.
- Reproduce, policy replay and candidate traces never construct a network client and need no key.
- With `--json`, stdout carries only `TraceDiff.model_dump_json(indent=2)`. The live run's own messages go to stderr.

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_cli_replay.py`:

```python
"""relay replay, offline: smoke traces from the groundtruth and rules providers, plus fakes for
the live candidates. Never touches the network."""

import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner
from typesafe_sdk import SystemOneResponse

import relay.cli as cli_module
import relay.evaluation.tracediff as tracediff
from relay.cases.loader import load_case
from relay.cases.policies import load_policy
from relay.cli import app
from relay.evaluation.budget import load_ledger
from relay.evaluation.tracediff import TraceDiff, replay_trace
from relay.reporting import DRIFT_LINE, REPRODUCED_LINE
from relay.traces.store import read_traces
from tests.claude_fakes import FakeBatches, FakeMessages, message
from tests.factories import make_bundle

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
JEV_FIXTURE = REPO / "tests" / "fixtures" / "jev" / "auto01_response.json"
runner = CliRunner()


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--env-file", str(tmp_path / "missing.env"), *args])


@pytest.fixture(scope="module")
def smoke_runs(tmp_path_factory):
    """One groundtruth and one rules trace file over the smoke dataset, made once."""
    root = tmp_path_factory.mktemp("smoke-runs")
    files = {}
    for provider in ("groundtruth", "rules"):
        out = root / provider
        result = invoke(
            root,
            "run",
            "--dataset",
            str(SMOKE),
            "--provider",
            provider,
            "--traces-dir",
            str(out / "traces"),
            "--reports-dir",
            str(out / "reports"),
        )
        assert result.exit_code == 0, result.output
        [files[provider]] = (out / "traces").glob("*.jsonl")
    return files


def replay(tmp_path, case_id, traces, *extra, dataset=SMOKE):
    return invoke(
        tmp_path, "replay", case_id, "--traces", str(traces), "--dataset", str(dataset), *extra
    )


def as_diff(result) -> TraceDiff:
    return TraceDiff.model_validate_json(result.stdout)


def row(diff, question_id):
    return next(d for d in diff.decisions if d.question_id == question_id)


# ---- reproduce ----


def test_reproduce_is_the_default_and_reproduces(tmp_path, smoke_runs):
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"])
    assert result.exit_code == 0, result.output
    assert result.output.count(REPRODUCED_LINE) == 2
    assert "\nORIGINAL run_" in result.output
    assert "CANDIDATE reproduce: stored decisions, current engine, original policy" in result.output
    assert "EXPECTED (evaluation-only): AUTO_PROCESS" in result.output
    assert "ACTION UNCHANGED: AUTO_PROCESS" in result.output


def test_an_engine_change_is_engine_drift_with_exit_3(tmp_path, smoke_runs, monkeypatch):
    real = tracediff.determine_action

    def drifted(*args, **kwargs):
        outcome = real(*args, **kwargs)
        return outcome.model_copy(update={"reasons": [*outcome.reasons, "a new reason"]})

    monkeypatch.setattr(tracediff, "determine_action", drifted)
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"])
    assert result.exit_code == 3, result.output
    assert DRIFT_LINE in result.output
    assert REPRODUCED_LINE not in result.output
    json_result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], "--json")
    assert json_result.exit_code == 3
    assert as_diff(json_result).identical is False


# ---- policy replay ----


def test_at_shows_the_crossed_threshold(tmp_path, smoke_runs):
    # rules on AUTO-03: step_therapy and documentation_complete are 0.5, below 0.95.
    result = replay(tmp_path, "AUTO-03", smoke_runs["rules"], "--at", "0.5")
    assert result.exit_code == 0, result.output
    assert (
        "CANDIDATE policy replay: STORED DECISIONS under policy immunara-v0.1 (v0.1), "
        "auto_process=0.5 — judgments were made against the original policy's questions"
    ) in result.output
    assert "  auto_process  0.95 → 0.5" in result.output
    assert "ACTION UNCHANGED: REQUEST_INFO" in result.output  # the documentation gate still fires
    diff = as_diff(replay(tmp_path, "AUTO-03", smoke_runs["rules"], "--at", "0.5", "--json"))
    assert diff.thresholds == {"auto_process": (0.95, 0.5)}
    assert row(diff, "step_therapy").crossed == ["auto_process"]
    assert row(diff, "documentation_complete").crossed == ["auto_process"]
    assert row(diff, "diagnosis_support").crossed == []


def test_latest_policy_and_explicit_policy_resolve_today_to_immunara_v0_1(tmp_path, smoke_runs):
    for flags in (["--latest-policy"], ["--policy", "immunara-v0.1"]):
        result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], *flags)
        assert result.exit_code == 0, result.output
        assert "STORED DECISIONS under policy immunara-v0.1 (v0.1) — judgments" in result.output
        assert "ACTION UNCHANGED: AUTO_PROCESS" in result.output
        assert REPRODUCED_LINE not in result.output  # policy replay never claims reproduction


def test_an_unknown_policy_is_exit_2(tmp_path, smoke_runs):
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], "--policy", "nope-v1")
    assert result.exit_code == 2
    assert "unknown policy 'nope-v1'" in result.output


# ---- candidate traces ----


def test_candidate_traces_classify_the_change(tmp_path, smoke_runs):
    # AUTO-03: groundtruth AUTO_PROCESS (correct), rules REQUEST_INFO (wrong-safe).
    result = replay(
        tmp_path, "AUTO-03", smoke_runs["groundtruth"], "--candidate-traces", smoke_runs["rules"]
    )
    assert result.exit_code == 0, result.output
    assert "CANDIDATE candidate trace run_" in result.output
    assert "· rules rules-v0.1" in result.output
    assert "ACTION CHANGED: AUTO_PROCESS → REQUEST_INFO (regressed)" in result.output
    reverse = replay(
        tmp_path, "AUTO-03", smoke_runs["rules"], "--candidate-traces", smoke_runs["groundtruth"]
    )
    assert reverse.exit_code == 0, reverse.output
    assert "ACTION CHANGED: REQUEST_INFO → AUTO_PROCESS (improved)" in reverse.output


def test_a_newly_unsafe_candidate_exits_4_and_still_prints_everything(tmp_path, smoke_runs):
    # REV-02 is expected HUMAN_REVIEW; confident judgments on every question auto-process it.
    [original] = [t for t in read_traces(smoke_runs["groundtruth"]) if t.case_id == "REV-02"]
    case = load_case(SMOKE / "REV-02")
    confident = original.model_copy(
        update={"decisions": make_bundle("REV-02"), "run_id": "run_confident"}
    )
    unsafe = replay_trace(
        confident, case, policy=load_policy("immunara-v0.1"), thresholds=original.thresholds
    )
    candidate_file = tmp_path / "unsafe.jsonl"
    candidate_file.write_text(unsafe.model_dump_json() + "\n", encoding="utf-8")
    result = replay(
        tmp_path, "REV-02", smoke_runs["groundtruth"], "--candidate-traces", candidate_file
    )
    assert result.exit_code == 4, result.output
    assert "ACTION CHANGED: HUMAN_REVIEW → AUTO_PROCESS (NEWLY UNSAFE)" in result.output
    assert "  CANDIDATE AUTO_PROCESS (UNSAFE)" in result.output
    assert "DECISION" in result.output and "GATES" in result.output
    json_result = replay(
        tmp_path,
        "REV-02",
        smoke_runs["groundtruth"],
        "--candidate-traces",
        candidate_file,
        "--json",
    )
    assert json_result.exit_code == 4
    assert as_diff(json_result).newly_unsafe is True


def test_a_candidate_made_on_different_inputs_is_exit_2(tmp_path, smoke_runs):
    [trace] = [t for t in read_traces(smoke_runs["rules"]) if t.case_id == "AUTO-01"]
    other = tmp_path / "other.jsonl"
    other.write_text(
        trace.model_copy(update={"case_content_hash": "sha256:other"}).model_dump_json() + "\n",
        encoding="utf-8",
    )
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], "--candidate-traces", other)
    assert result.exit_code == 2
    assert "different case inputs" in result.output


# ---- input errors ----


def test_changed_case_inputs_are_refused_with_both_hashes(tmp_path, smoke_runs):
    edited = tmp_path / "smoke-edited"
    shutil.copytree(SMOKE, edited)
    note = edited / "AUTO-01" / "documents" / "physician_note.txt"
    note.write_text(note.read_text(encoding="utf-8") + "\nAn added line.\n", encoding="utf-8")
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], dataset=edited)
    assert result.exit_code == 2
    assert "the case inputs changed since run" in result.output
    [trace] = [t for t in read_traces(smoke_runs["groundtruth"]) if t.case_id == "AUTO-01"]
    assert trace.case_content_hash in result.output


def test_a_case_with_no_trace_or_two_traces_is_exit_2(tmp_path, smoke_runs):
    [trace] = [t for t in read_traces(smoke_runs["groundtruth"]) if t.case_id == "AUTO-01"]
    doubled = tmp_path / "doubled.jsonl"
    doubled.write_text((trace.model_dump_json() + "\n") * 2, encoding="utf-8")
    result = replay(tmp_path, "AUTO-01", doubled)
    assert result.exit_code == 2
    assert "expected exactly one trace for AUTO-01, found 2" in result.output
    result = replay(tmp_path, "NOPE-01", smoke_runs["groundtruth"])
    assert result.exit_code == 2
    assert "expected exactly one trace for NOPE-01, found 0" in result.output


@pytest.mark.parametrize(
    "flags,message",
    [
        (["--at", "0.9", "--candidate-traces", "RULES"], "choose one candidate source"),
        (["--policy", "immunara-v0.1", "--candidate-traces", "RULES"], "choose one"),
        (["--provider", "rules", "--at", "0.9"], "choose one candidate source"),
        (["--provider", "rules", "--candidate-traces", "RULES"], "choose one candidate source"),
        (["--policy", "immunara-v0.1", "--latest-policy"], "mutually exclusive"),
        (["--questions", "q-v0.2"], "applies only to a live candidate"),
        (["--mode", "sync"], "applies only to a live candidate"),
        (["--provider", "claude", "--mode", "batch"], "--mode batch is not supported"),
        (["--provider", "rules", "--budget-usd", "1"], "applies only to --provider claude"),
        (["--provider", "rules", "--questions", "q-v0.2"], "has no question set"),
    ],
)
def test_conflicting_flags_are_exit_2(tmp_path, smoke_runs, flags, message):
    flags = [str(smoke_runs["rules"]) if f == "RULES" else f for f in flags]
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], *flags)
    assert result.exit_code == 2, result.output
    assert message in result.output


# ---- JSON and keyless operation ----


def test_json_prints_only_the_trace_diff(tmp_path, smoke_runs):
    result = replay(tmp_path, "AUTO-03", smoke_runs["rules"], "--at", "0.5", "--json")
    assert result.exit_code == 0, result.output
    assert result.stdout.lstrip().startswith("{")
    diff = as_diff(result)
    assert diff.case_id == "AUTO-03"
    assert json.loads(result.stdout)["candidate_label"].startswith("policy replay: ")


class NoNetworkClient:
    def __init__(self, *args, **kwargs):
        raise AssertionError("replay constructed a network client")


@pytest.mark.parametrize(
    "flags",
    [[], ["--latest-policy"], ["--at", "0.9"], ["--candidate-traces", "RULES"]],
    ids=["reproduce", "latest-policy", "at", "candidate-traces"],
)
def test_offline_modes_need_no_key_and_build_no_client(tmp_path, smoke_runs, monkeypatch, flags):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", NoNetworkClient)
    monkeypatch.setattr(cli_module, "AsyncAnthropic", NoNetworkClient)
    flags = [str(smoke_runs["rules"]) if f == "RULES" else f for f in flags]
    result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], *flags)
    assert result.exit_code == 0, result.output


# ---- live candidates (fakes only) ----


class FakeTypeSafe:
    """Stands in for AsyncTypeSafeClient; answers with the AUTO-01 fixture."""

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def system_one(self, state, questions, *, model=None, **kwargs):
        return SystemOneResponse.model_validate(json.loads(JEV_FIXTURE.read_text()))


class FakeAnthropic:
    """Stands in for anthropic.AsyncAnthropic; one well-formed sync reply."""

    def __init__(self, **kwargs):
        self.messages = FakeMessages(message(), batches=FakeBatches([]))

    def with_options(self, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None


def live_trace(tmp_path):
    [trace_file] = (tmp_path / "live").glob("*.jsonl")
    [trace] = read_traces(trace_file)
    assert trace_file.with_suffix(".manifest.json").exists()
    return trace


def test_live_rules_candidate_is_an_ordinary_one_case_run(tmp_path, smoke_runs):
    result = replay(
        tmp_path,
        "AUTO-03",
        smoke_runs["groundtruth"],
        "--provider",
        "rules",
        "--traces-dir",
        str(tmp_path / "live"),
    )
    assert result.exit_code == 0, result.output
    trace = live_trace(tmp_path)
    assert f"Live candidate run {trace.run_id}: " in result.output
    assert f"CANDIDATE live run {trace.run_id} · rules rules-v0.1 on frozen inputs" in (
        result.output
    )
    assert "ACTION CHANGED: AUTO_PROCESS → REQUEST_INFO (regressed)" in result.output


def test_live_jev_candidate_uses_the_fake_client(tmp_path, smoke_runs, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", FakeTypeSafe)
    result = replay(
        tmp_path,
        "AUTO-01",
        smoke_runs["groundtruth"],
        "--provider",
        "jev",
        "--question-set",
        "q-v0.2",
        "--traces-dir",
        str(tmp_path / "live"),
    )
    assert result.exit_code == 0, result.output
    trace = live_trace(tmp_path)
    assert (trace.provider, trace.question_set_version) == ("jev", "q-v0.2")
    assert f"CANDIDATE live run {trace.run_id} · jev q-v0.2 on frozen inputs" in result.output


def test_live_jev_without_a_key_is_exit_2_before_any_run(tmp_path, smoke_runs, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", NoNetworkClient)
    result = replay(
        tmp_path,
        "AUTO-01",
        smoke_runs["groundtruth"],
        "--provider",
        "jev",
        "--traces-dir",
        str(tmp_path / "live"),
    )
    assert result.exit_code == 2
    assert "TYPESAFE_API_KEY is not set" in result.output
    assert not (tmp_path / "live").exists()


def test_live_claude_candidate_goes_through_the_budget_guard(tmp_path, smoke_runs, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncAnthropic", FakeAnthropic)
    ledger = tmp_path / "spend.json"
    result = replay(
        tmp_path,
        "AUTO-01",
        smoke_runs["groundtruth"],
        "--provider",
        "claude",
        "--ledger",
        str(ledger),
        "--traces-dir",
        str(tmp_path / "live"),
    )
    assert result.exit_code == 0, result.output
    assert "Claude budget: spent $0.0000, projected $0.2500 for 1 cases (sync)" in result.output
    trace = live_trace(tmp_path)
    assert trace.provider == "claude"
    [entry] = load_ledger(ledger).entries
    assert (entry.mode, entry.cases, entry.status) == ("sync", 1, "settled")
    assert entry.cost_usd == Decimal("0.0219")


def test_live_claude_over_budget_is_exit_2_and_writes_nothing(tmp_path, smoke_runs, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncAnthropic", FakeAnthropic)
    result = replay(
        tmp_path,
        "AUTO-01",
        smoke_runs["groundtruth"],
        "--provider",
        "claude",
        "--budget-usd",
        "0.1",
        "--ledger",
        str(tmp_path / "spend.json"),
        "--traces-dir",
        str(tmp_path / "live"),
    )
    assert result.exit_code == 2
    assert not (tmp_path / "live").exists()
    assert not (tmp_path / "spend.json").exists()


def test_live_json_keeps_stdout_pure(tmp_path, smoke_runs, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncAnthropic", FakeAnthropic)
    result = replay(
        tmp_path,
        "AUTO-01",
        smoke_runs["groundtruth"],
        "--provider",
        "claude",
        "--ledger",
        str(tmp_path / "spend.json"),
        "--traces-dir",
        str(tmp_path / "live"),
        "--json",
    )
    assert result.exit_code == 0, result.output
    diff = as_diff(result)
    assert diff.candidate_label.startswith("live run ")
    assert "Claude budget:" in result.stderr
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/integration/test_cli_replay.py -q`
Expected: FAIL. The replay invocations exit 2 with `No such command 'replay'`, so the exit-code and output assertions fail.

- [ ] **Step 3: Implement**

Make these exact replacements in `relay/cli.py`:

1. Replace:

```python
"""relay run / eval / generate, and the offline analyses sweep / report / compare."""
```

   with:

```python
"""relay run / eval / generate, and the offline analyses sweep / report / compare / replay."""
```

2. Replace:

```python
import asyncio
import os
```

   with:

```python
import asyncio
import contextlib
import os
import sys
```

3. Replace:

```python
from relay.cases.loader import CaseLoadError, load_dataset
from relay.cases.models import PriorAuthCase
```

   with:

```python
from relay.cases.loader import CaseLoadError, load_case, load_dataset
from relay.cases.models import PriorAuthCase
from relay.cases.policies import AuthorizationPolicy, latest_policy_for, load_policy
```

4. Replace:

```python
from relay.evaluation.frontier import DEFAULT_CEILING, frontier_csv, run_sweep
```

   with:

```python
from relay.evaluation.frontier import DEFAULT_CEILING, frontier_csv, run_sweep
from relay.evaluation.labels import expected_action
```

5. Replace:

```python
from relay.evaluation.runner import (
    RunConfigError,
    run_dataset,
    sample_cases,
    validate_run_config,
)
```

   with:

```python
from relay.evaluation.runner import (
    RunConfigError,
    policy_text_hash,
    run_dataset,
    sample_cases,
    validate_run_config,
)
from relay.evaluation.tracediff import (
    REPRODUCE_LABEL,
    candidate_trace_label,
    diff_traces,
    live_label,
    original_label,
    policy_replay_label,
    replay_exit_code,
    replay_trace,
)
```

6. Replace:

```python
    render_run_report,
    render_run_table,
)
```

   with:

```python
    render_run_report,
    render_run_table,
    render_trace_diff,
)
```

Then append to the end of `relay/cli.py`:

```python
ReplayQuestions = Annotated[
    str | None,
    typer.Option(
        "--questions",
        "--question-set",
        help="Live candidate only: the provider's question set (as for run/eval).",
    ),
]


def _one_trace(path: Path, case_id: str, flag: str) -> WorkflowTrace:
    """The single trace for case_id in a trace file; zero or several is a usage error."""
    matches = [t for t in _read_trace_file(path) if t.case_id == case_id]
    if len(matches) != 1:
        raise _fail(
            f"{flag} {path}: expected exactly one trace for {case_id}, found {len(matches)}"
        )
    return matches[0]


def _frozen_case(dataset: Path, trace: WorkflowTrace) -> PriorAuthCase:
    """The trace's case from the dataset, refused unless its inputs hash to the stored hash."""
    case_dir = dataset / trace.case_id
    if not case_dir.is_dir():
        raise _fail(f"{trace.case_id} is not a case folder in {dataset}")
    try:
        case = load_case(case_dir)
    except CaseLoadError as error:
        raise _fail(str(error)) from error
    actual = case.input.content_hash()
    if actual != trace.case_content_hash:
        raise _fail(
            f"{trace.case_id}: the case inputs changed since run {trace.run_id} (trace "
            f"{trace.case_content_hash}, dataset {actual}); replaying altered inputs is not replay"
        )
    return case


def _policy(policy_id: str) -> AuthorizationPolicy:
    try:
        return load_policy(policy_id)
    except KeyError as error:
        raise _fail(str(error.args[0])) from error


def _live_candidate(
    case: PriorAuthCase,
    original: WorkflowTrace,
    dataset: Path,
    provider: ProviderName,
    questions: str | None,
    mode: ClaudeMode | None,
    budget_usd: float | None,
    ledger: Path | None,
    traces_dir: Path,
    quiet: bool,
) -> WorkflowTrace:
    """A fresh provider call on the frozen input, written as an ordinary one-case run.

    With --json, the run's own messages (budget, notes, spend, run id) go to stderr so stdout
    stays pure JSON.
    """
    if mode is ClaudeMode.batch:
        raise _fail("replay decides one case; --mode batch is not supported (use --mode sync)")
    claude = _resolve_claude(provider, mode, budget_usd, ledger)
    resolved = _resolve_questions(provider, questions)
    cases = [case]
    _preflight(cases, provider, original.policy_version)
    chatter = contextlib.redirect_stdout(sys.stderr) if quiet else contextlib.nullcontext()
    with chatter:
        projected = _claude_budget_check(claude, cases) if claude is not None else Decimal("0")
        if provider in PROVIDER_NOTES:
            typer.echo(f"NOTE: {PROVIDER_NOTES[provider]}")
        manifest, traces = asyncio.run(
            _execute(
                cases,
                provider,
                original.policy_version,
                1,
                traces_dir,
                dataset,
                resolved,
                None,
                claude,
                projected,
            )
        )
        typer.echo(f"Live candidate run {manifest.run_id}: {manifest.trace_file}")
    return traces[0]


@app.command()
def replay(
    case_id: Annotated[str, typer.Argument(help="The case to replay, e.g. GOLD-TMP-17.")],
    traces: TraceFile,
    dataset: Dataset,
    policy_id: Annotated[
        str | None,
        typer.Option("--policy", help="Policy replay: the stored decisions under this policy id."),
    ] = None,
    latest_policy: Annotated[
        bool,
        typer.Option(
            "--latest-policy",
            help="Policy replay: under the newest registered policy for the same medication.",
        ),
    ] = False,
    at: Annotated[
        float | None,
        typer.Option(min=0.0, max=1.0, help="Policy replay: override the auto_process threshold."),
    ] = None,
    candidate_traces: Annotated[
        Path | None,
        typer.Option(
            exists=True, dir_okay=False, help="Candidate: this case's trace from another run."
        ),
    ] = None,
    provider: Annotated[
        ProviderName | None,
        typer.Option(help="Live candidate: a fresh call to this provider on the frozen inputs."),
    ] = None,
    questions: ReplayQuestions = None,
    mode: ModeOption = None,
    budget_usd: BudgetUsd = None,
    ledger: LedgerOption = None,
    traces_dir: Annotated[
        Path, typer.Option(help="Live candidate only: where its trace file is written.")
    ] = Path("traces"),
    all_gates: Annotated[
        bool, typer.Option("--all-gates", help="Show every gate row, not only changed ones.")
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Print the TraceDiff as JSON and nothing else.")
    ] = False,
) -> None:
    """Replay one stored trace beside a candidate and call out every difference.

    Exit codes: 0 ok; 2 usage/input error; 3 ENGINE DRIFT (reproduce only); 4 NEWLY UNSAFE.
    """
    policy_replay = policy_id is not None or latest_policy or at is not None
    sources = [
        name
        for name, used in (
            ("policy replay (--policy/--latest-policy/--at)", policy_replay),
            ("--candidate-traces", candidate_traces is not None),
            ("--provider", provider is not None),
        )
        if used
    ]
    if len(sources) > 1:
        raise _fail("choose one candidate source, not " + " and ".join(sources))
    if policy_id is not None and latest_policy:
        raise _fail("--policy and --latest-policy are mutually exclusive")
    if provider is None:
        live_only = {
            "--questions": questions,
            "--mode": mode,
            "--budget-usd": budget_usd,
            "--ledger": ledger,
        }
        given = [flag for flag, value in live_only.items() if value is not None]
        if given:
            raise _fail(f"{', '.join(given)} applies only to a live candidate (--provider)")

    original = _one_trace(traces, case_id, "--traces")
    case = _frozen_case(dataset, original)
    original_policy = _policy(original.policy_id)
    reproduce = False
    if candidate_traces is not None:
        candidate = _one_trace(candidate_traces, case_id, "--candidate-traces")
        if candidate.case_content_hash != original.case_content_hash:
            raise _fail(
                f"--candidate-traces {candidate_traces}: its {case_id} trace was made on "
                f"different case inputs ({candidate.case_content_hash}, original "
                f"{original.case_content_hash})"
            )
        label = candidate_trace_label(candidate)
    elif provider is not None:
        candidate = _live_candidate(
            case,
            original,
            dataset,
            provider,
            questions,
            mode,
            budget_usd,
            ledger,
            traces_dir,
            json_output,
        )
        label = live_label(candidate)
    elif policy_replay:
        if latest_policy:
            try:
                target_id = latest_policy_for(original.policy_id)
            except KeyError as error:
                raise _fail(str(error.args[0])) from error
        else:
            target_id = policy_id or original.policy_id
        target = _policy(target_id)
        thresholds = (
            original.thresholds
            if at is None
            else original.thresholds.model_copy(update={"auto_process": at})
        )
        candidate = replay_trace(original, case, policy=target, thresholds=thresholds)
        label = policy_replay_label(target, at)
    else:
        reproduce = True
        candidate = replay_trace(
            original, case, policy=original_policy, thresholds=original.thresholds
        )
        label = REPRODUCE_LABEL
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
    if json_output:
        typer.echo(diff.model_dump_json(indent=2))
    else:
        typer.echo(render_trace_diff(diff, all_gates, reproduce=reproduce))
    code = replay_exit_code(diff, reproduce=reproduce)
    if code:
        raise typer.Exit(code=code)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/integration/test_cli_replay.py -q`
Expected: PASS (31 tests)

- [ ] **Step 5: Manual offline smoke check (no keys, no .env)**

Run:
```bash
env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env replay GOLD-TMP-17 --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz --dataset evals/gold; echo "exit $?"
```
Expected: the output shows `REPRODUCED: identical action, reasons and gate path` twice and ends with `exit 0`.

- [ ] **Step 6: Full check**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add relay/cli.py tests/integration/test_cli_replay.py
git commit -m "feat: add the relay replay command" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The gold reproduce guard

**Files:**
- Modify: `tests/integration/test_committed_baselines.py` (the docstring and imports, then append)

**Interfaces:**
- Consumes:
  - from Tasks 2–5: `replay_trace`, `diff_traces`, `original_label`, `replay_exit_code`, `REPRODUCE_LABEL` and `relay.reporting.REPRODUCED_LINE`, plus the `relay replay` command
  - existing names in this test file: `BASELINES`, `DATASET_DIRS["gold-v0.1"]` (which is `REPO / "evals" / "gold"`), `load_dataset` and `read_traces`
- Produces: `drifted_cases(trace_path) -> list[str]` (a test helper), plus the tests described below. The four committed gold runs are `evals/baselines/gold-v0.1/run_*/traces.jsonl.gz`: groundtruth, rules, jev and claude, 100 traces each.

This task guards existing behaviour, so the new tests pass as soon as they are written. `test_the_reproduce_guard_detects_engine_drift` proves the guard is not vacuous: it patches the engine to drift on one case and asserts that the guard names exactly that case.

- [ ] **Step 1: Write the guard**

In `tests/integration/test_committed_baselines.py`, replace the last paragraph of the module docstring:

```python
Committed gold runs under evals/baselines/gold-v0.1/ are re-scored against the tracked evals/gold.
"""
```

with:

```python
Committed gold runs under evals/baselines/gold-v0.1/ are re-scored against the tracked evals/gold.

Phase 3A adds a reproduce guard beside it: every committed gold trace, for all four providers, must
replay through today's engine with the same action, reasons and gate path (`relay replay`'s
REPRODUCED). A failure there is ENGINE DRIFT: the engine now reinterprets stored decisions.
"""
```

Replace the imports:

```python
import pytest

from relay.cases.loader import CaseLoadError, load_dataset
from relay.evaluation.metrics import score_run
from relay.evaluation.runner import sample_cases
from relay.traces.store import read_traces
```

with:

```python
import pytest
from typer.testing import CliRunner

import relay.evaluation.tracediff as tracediff
from relay.cases.loader import CaseLoadError, load_dataset
from relay.cases.policies import load_policy
from relay.cli import app
from relay.evaluation.labels import expected_action
from relay.evaluation.metrics import score_run
from relay.evaluation.runner import policy_text_hash, sample_cases
from relay.evaluation.tracediff import (
    REPRODUCE_LABEL,
    diff_traces,
    original_label,
    replay_exit_code,
    replay_trace,
)
from relay.reporting import REPRODUCED_LINE
from relay.traces.store import read_traces
```

Append to the end of the file:

```python
# ---- Phase 3A: committed gold traces must still reproduce under today's engine ----

GOLD_TRACE_FILES: list[Path] = sorted((BASELINES / "gold-v0.1").glob("run_*/traces.jsonl.gz"))
GOLD_JEV_TRACES = BASELINES / "gold-v0.1" / "run_20260925T170857Z_b95be9" / "traces.jsonl.gz"


def test_the_gold_reproduce_guard_covers_all_four_providers():
    providers = {read_traces(path)[0].provider for path in GOLD_TRACE_FILES}
    assert providers == {"groundtruth", "rules", "jev", "claude"}


def drifted_cases(trace_path: Path) -> list[str]:
    """Case ids whose committed trace today's engine no longer reproduces (reproduce mode:
    stored decisions, the trace's own policy and thresholds)."""
    cases = {c.input.id: c for c in load_dataset(DATASET_DIRS["gold-v0.1"])}
    drifted = []
    for trace in read_traces(trace_path):
        case = cases[trace.case_id]
        policy = load_policy(trace.policy_id)
        replayed = replay_trace(
            trace, case, policy=policy, thresholds=trace.thresholds, git_sha="guard"
        )
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
        if replay_exit_code(diff, reproduce=True) != 0:
            drifted.append(trace.case_id)
    return drifted


@pytest.mark.parametrize("trace_path", GOLD_TRACE_FILES, ids=lambda p: p.parent.name)
def test_every_committed_gold_trace_reproduces(trace_path):
    assert len(read_traces(trace_path)) == 100
    drifted = drifted_cases(trace_path)
    assert drifted == [], f"{trace_path.parent.name}: ENGINE DRIFT on {drifted}"


def test_the_reproduce_guard_detects_engine_drift(monkeypatch):
    real = tracediff.determine_action

    def drifted_engine(case, bundle, policy, thresholds):
        outcome = real(case, bundle, policy, thresholds)
        if case.id != "GOLD-TMP-17":
            return outcome
        return outcome.model_copy(update={"reasons": [*outcome.reasons, "a new reason"]})

    monkeypatch.setattr(tracediff, "determine_action", drifted_engine)
    assert drifted_cases(GOLD_JEV_TRACES) == ["GOLD-TMP-17"]


def test_relay_replay_reproduces_a_committed_gzipped_gold_trace(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "--env-file",
            str(tmp_path / "missing.env"),
            "replay",
            "GOLD-TMP-17",
            "--traces",
            str(GOLD_JEV_TRACES),
            "--dataset",
            str(DATASET_DIRS["gold-v0.1"]),
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.output.count(REPRODUCED_LINE) == 2
    assert "ORIGINAL run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1" in (
        result.output
    )
```

- [ ] **Step 2: Run the guard**

Run: `uv run pytest tests/integration/test_committed_baselines.py -q`
Expected: PASS. Four `test_every_committed_gold_trace_reproduces` cases pass, as do the drift-detection test and the gzipped CLI test. The gen-v0.2 rescoring cases skip if `evals/generated/` is absent, as they did before.

- [ ] **Step 3: Full check**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass. Confirm that `git status --short evals/` prints nothing.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_committed_baselines.py
git commit -m "test: guard committed gold traces against engine drift via replay" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: README "Replay" section with real output

**Files:**
- Modify: `README.md` (the Commands block, a new `## Replay` section just before `## Limitations`, and the Project docs list)

**Interfaces:**
- Consumes: the finished `relay replay` command (Tasks 1–6) and two committed gold trace files:
  - Jev: `evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz`
  - Claude: `evals/baselines/gold-v0.1/run_20260926T011730Z_f1852f/traces.jsonl.gz`
- Produces: README documentation only.

The two examples are real offline runs on committed traces. Both keys are unset and no `.env` is read. Run them yourself and paste exactly what they print.

- [ ] **Step 1: Generate the output**

Run each command from the repository root:

```bash
env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env replay GOLD-TMP-17 \
    --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz \
    --dataset evals/gold \
    --candidate-traces evals/baselines/gold-v0.1/run_20260926T011730Z_f1852f/traces.jsonl.gz; echo "exit $?"

env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env replay GOLD-TMP-17 \
    --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz \
    --dataset evals/gold \
    --at 0.89; echo "exit $?"
```

Expected: the first command ends `ACTION UNCHANGED: HUMAN_REVIEW` and then `exit 0`. The second ends `ACTION CHANGED: HUMAN_REVIEW → AUTO_PROCESS (NEWLY UNSAFE)` and then `exit 4`. The output was generated from this plan's code, and it should match the blocks in Step 2 byte for byte. If yours differs, paste what you actually got and report the difference; never hand-edit the output to match.

- [ ] **Step 2: Edit README.md**

(a) In the `## Commands` code block, replace:

```text
uv run relay compare --dataset <dir> --traces <a> --traces <b> [--labels a,b]    # side-by-side runs, no API calls
```

with:

```text
uv run relay compare --dataset <dir> --traces <a> --traces <b> [--labels a,b]    # side-by-side runs, no API calls
uv run relay replay CASE_ID --traces <file> --dataset <dir> [--at 0.9]           # one case beside a candidate (see "Replay")
```

(b) Insert this section immediately before the `## Limitations` heading (the pasted blocks are the Step 1 output, without the `exit` lines):

````markdown
## Replay

`relay replay` puts one stored trace beside a candidate outcome for the same case and labels every
difference: judgments, confidence, thresholds, policy, gate path and action. It rebuilds the case
from `--dataset` and checks it against the content hash stored in the trace. If the inputs changed
since the run, it refuses with exit code 2, because replaying altered inputs is not replay.

You pick one candidate source:

- **Reproduce** (the default). The stored decisions go back through today's engine under the
  trace's own policy and thresholds. `REPRODUCED` means today's engine gives the same action,
  reasons and gate path. `ENGINE DRIFT` (exit 3) means it doesn't.
- **Policy replay** (`--policy ID`, `--latest-policy`, `--at X`). The stored decisions under
  another policy or `auto_process` threshold. The label always says the judgments were made against
  the original policy's questions, so a policy replay never looks like a policy-aware re-run.
- **Candidate traces** (`--candidate-traces FILE`). The same case's trace from another run.
- **Live candidate** (`--provider P`). A fresh provider call on the frozen inputs, written as an
  ordinary one-case run under `traces/` so it can itself be replayed later. It needs that
  provider's key. Claude runs sync only and goes through the budget guard.

The expected action is always printed, marked evaluation-only, and derived from ground truth the
same way `relay eval` derives it. Each side is judged `correct`, `wrong-safe` or `UNSAFE`. A
candidate that newly automates a case unsafely is flagged `NEWLY UNSAFE`, and the command exits 4
so scripts can gate on it. `--json` prints the diff as JSON and nothing else. `--all-gates` also
shows the gate rows that didn't change. Only a live candidate calls a provider: the other three
sources need no keys and make no network calls, as the commands below show (run with both keys
unset and no `.env`).

Jev beside Claude on `GOLD-TMP-17`, the interrupted methotrexate course described under "Gold
set", from the committed gold traces:

```text
$ env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env replay GOLD-TMP-17 \
    --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz \
    --dataset evals/gold \
    --candidate-traces evals/baselines/gold-v0.1/run_20260926T011730Z_f1852f/traces.jsonl.gz
Relay replay — GOLD-TMP-17
ORIGINAL run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE candidate trace run_20260926T011730Z_f1852f · claude q-v0.2+claude-prompt-v1
EXPECTED (evaluation-only): HUMAN_REVIEW

   DECISION                ORIGINAL     CANDIDATE    Δ       CROSSED
   diagnosis_support       p_yes=0.980  p_yes=0.970  -0.010
   step_therapy            p_yes=0.932  p_yes=0.551  -0.380
   documentation_complete  p_yes=0.970  p_yes=0.950  -0.020
   material_contradiction  p_yes=0.100  p_yes=0.030  -0.070  auto_process
   missing_evidence        NONE (0.85)  NONE (0.88)  +0.030
  (* = answer changed)

GATES: same outcome at every gate (--all-gates shows every row)

ACTIONS
  ORIGINAL  HUMAN_REVIEW (correct)
      - step_therapy p_yes=0.932 is below the 0.95 autonomous-action bar
  CANDIDATE HUMAN_REVIEW (correct)
      - step_therapy p_yes=0.551 is below the 0.95 autonomous-action bar

ACTION UNCHANGED: HUMAN_REVIEW
```

Both providers escalate the case, which is correct, but Claude's composed `step_therapy`
probability is 0.380 lower than Jev's. The `auto_process` mark on `material_contradiction` is a
reported-only comparison (1 − p_yes against the bar), not an engine gate, so no gate changes.

The same Jev trace under Jev's own dev-selected threshold, 0.89 (from
[`compare-own-thresholds.txt`](evals/baselines/gold-v0.1/compare-own-thresholds.txt)):

```text
$ env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env replay GOLD-TMP-17 \
    --traces evals/baselines/gold-v0.1/run_20260925T170857Z_b95be9/traces.jsonl.gz \
    --dataset evals/gold \
    --at 0.89
Relay replay — GOLD-TMP-17
ORIGINAL run_20260925T170857Z_b95be9 · jev q-v0.2 · policy immunara-v0.1 (v0.1) · thresholds auto_process=0.95
CANDIDATE policy replay: STORED DECISIONS under policy immunara-v0.1 (v0.1), auto_process=0.89 — judgments were made against the original policy's questions
EXPECTED (evaluation-only): HUMAN_REVIEW

   DECISION                ORIGINAL     CANDIDATE    Δ       CROSSED
   diagnosis_support       p_yes=0.980  p_yes=0.980  +0.000
   step_therapy            p_yes=0.932  p_yes=0.932  +0.000  auto_process
   documentation_complete  p_yes=0.970  p_yes=0.970  +0.000
   material_contradiction  p_yes=0.100  p_yes=0.100  +0.000  auto_process
   missing_evidence        NONE (0.85)  NONE (0.85)  +0.000
  (* = answer changed)

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

This command exits 4. At 0.89, Jev's 0.932 `step_therapy` clears the bar and the case
auto-processes, but its expected action is `HUMAN_REVIEW`. This is the unsafe automation that
`compare-own-thresholds.txt` records for Jev on `GOLD-TMP-17`.

````

(c) In `## Project docs`, after the line:

```text
- [Phase 2E implementation plan](docs/superpowers/plans/2026-09-25-phase2e-gold-set.md)
```

add:

```text
- [Phase 3A replay design](docs/superpowers/specs/2026-09-26-phase3a-replay-design.md)
- [Phase 3A implementation plan](docs/superpowers/plans/2026-09-26-phase3a-replay.md)
```

- [ ] **Step 3: Verify the pasted output is still what the tool prints**

Run the two Step 1 commands again and compare each output with its README block. Expected: identical.

- [ ] **Step 4: Full check**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`
Expected: all pass. Confirm that `git status --short` shows only `README.md` modified.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add the Replay section with real offline output" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
