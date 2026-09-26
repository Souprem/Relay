# Phase 3A Design: Replay

- **Date:** 2026-09-26
- **Status:** Approved by controller. The user delegated Phase 3 design decisions (A replay → B regression gate + CI → C shadow mode → D q-v0.3 + policy shift → E ablation).
- **Parent:** handoff §"Replay": "`relay replay CASE-0391` should show the original trace beside a candidate run and explicitly call out changed judgments, confidence deltas, policy deltas, and workflow-action changes. It should be possible to replay with either the original frozen inputs or the latest policy, clearly labeled."
- **Feeds:** 3B (regression), 3C (shadow) and 3D reuse the diff core and the run-level policy replay built here.

## 1. Goal

A single-case investigation tool. You give it a stored trace. Relay rebuilds the case from its frozen inputs, produces a candidate outcome from one of four sources, and prints the two side by side. Every difference in judgment, confidence, policy, gate path and action is called out and labelled. The same comparison is available as JSON.

## 2. Settled decisions

| # | Decision |
|---|---|
| P1 | **Frozen inputs come from the dataset, verified by hash.** Traces store `case_content_hash`, not the case, and this stays that way (the handoff allows "snapshot or content hash"). `replay` requires `--dataset`. It loads the case and refuses with exit code 2 if `case.input.content_hash() != trace.case_content_hash`. The error names both hashes and says the inputs changed since the run. There is no override flag: replaying altered inputs is not replay. |
| P2 | **Four candidate sources.** Exactly one is used; they are mutually exclusive, and the CLI rejects combinations with exit code 2.<br>1. **Reproduce** (the default when no source flag is given): the stored decisions re-run through today's engine under the trace's own policy and thresholds.<br>2. **Policy replay** (`--policy ID`, `--latest-policy`, `--at X`, alone or in combination): the stored decisions under a different policy and/or auto_process threshold.<br>3. **Candidate traces** (`--candidate-traces FILE`): the same case's trace from another run.<br>4. **Live candidate** (`--provider P [--question-set Q] [--mode sync]`): a fresh provider call on the frozen input. |
| P3 | **Reproduce is a replayability check.** If the recomputed action, reasons or gate path differ from the stored ones, the header reads `ENGINE DRIFT: today's policy engine no longer reproduces this trace`, and the command exits 3. This is how engine changes become visible. A reproduced trace that matches prints `REPRODUCED: identical action, reasons and gate path`. |
| P4 | **Labels are explicit.** Every replay prints a header naming both sides. The labels, in order:<br>1. `ORIGINAL <run_id> · <provider> <question_set_version> · policy <id> (<version>) · thresholds auto_process=<x>`<br>2. `CANDIDATE` followed by one of:<br>&nbsp;&nbsp;• `reproduce: stored decisions, current engine, original policy`<br>&nbsp;&nbsp;• `policy replay: STORED DECISIONS under policy <id> (<version>)[, auto_process=<x>] — judgments were made against the original policy's questions`<br>&nbsp;&nbsp;• `candidate trace <run_id> · <provider> <qs>`<br>&nbsp;&nbsp;• `live run <run_id> · <provider> <qs> on frozen inputs`<br>Policy replay always carries the "judgments were made against the original policy's questions" note. Re-deciding stale judgments under a new policy is exactly the naive behaviour 3D measures, so it must never look policy-aware. |
| P5 | **Policy text drift is reported.** If the trace has a `policy_text_hash`, and the current text of that same policy id hashes differently, both sides show `POLICY TEXT CHANGED since the original run (<old8> → <new8>)`. Traces from before 2B have no hash; they show `policy text hash not recorded`. |
| P6 | **`--latest-policy`** resolves to the policy in the registry with the same `medication` and the highest version, compared numerically after stripping the leading `v` (`v0.10` > `v0.9`). There is exactly one policy today, so `--latest-policy` resolves to `immunara-v0.1`. 3D adds a second. Resolution is a pure function, `latest_policy_for(policy_id) -> str`, in `relay/cases/policies.py`. |
| P7 | **Ground truth is always shown, and labelled.** Every dataset case carries ground truth (`PriorAuthCase.ground_truth` is required).<br>• Replay prints `EXPECTED (evaluation-only): <action>`, computed by `relay.evaluation.labels.expected_action` (the same derivation eval uses) under each side's own policy and thresholds.<br>• When the two sides use different policies and the expected actions differ, both are printed: `EXPECTED under <orig policy>: X · under <cand policy>: Y`.<br>• Each side is judged against its own expected action and classified as `correct`, `wrong-safe` or `UNSAFE` (AUTO_PROCESS where its expected action isn't).<br>• The change is classified as:<br>&nbsp;&nbsp;– `improved`: the candidate is correct and the original wasn't<br>&nbsp;&nbsp;– `regressed`: the original was correct and the candidate isn't<br>&nbsp;&nbsp;– `unchanged`<br>&nbsp;&nbsp;– `changed-both-wrong`<br>• `NEWLY UNSAFE` and `UNSAFE RESOLVED` are flagged prominently. |
| P8 | **Live candidates are ordinary runs.** A live replay writes a normal one-case trace file and manifest under `traces/` via the existing runner. Its run id is printed, and the replay can itself be replayed later. All existing guards apply unchanged: Jev needs `TYPESAFE_API_KEY`, and Claude goes through the budget ledger and `--budget-usd`/`--ledger`, with sync mode only, because a batch of one is pointless. Tests use fakes, and Phase 3 plans no live Claude calls. |
| P9 | **The diff core is shared.** It is a new module, `relay/evaluation/tracediff.py`, with pure functions and no I/O. 3B's regression is built from its run-level functions. |

## 3. Diff core (`relay/evaluation/tracediff.py`)

```python
class DecisionDelta(BaseModel):          # one per DecisionId, always all five
    question_id: DecisionId
    kind: Literal["yes_no", "choice"] | None   # None if missing on both sides
    original: str                         # rendered, e.g. "p_yes=0.931" or "NONE (0.62)" or "missing"
    candidate: str
    answer_changed: bool                  # yes/no side of 0.5 flipped, or choice label changed, or presence changed
    delta: float | None                   # yes_no: candidate.p_yes - original.p_yes; choice: change in the ORIGINAL answer's probability; None if either side missing
    crossed: list[str]                    # threshold names whose pass/fail flipped for this decision, e.g. ["auto_process"]

class GateDelta(BaseModel):
    gate: str
    original: str                         # "passed" | "FIRED" | "not reached"
    candidate: str
    detail_original: str | None
    detail_candidate: str | None

class TraceDiff(BaseModel):
    case_id: str
    original_label: str
    candidate_label: str
    decisions: list[DecisionDelta]
    gates: list[GateDelta]                # union of gates in path order; only rows that differ are rendered by default
    thresholds: dict[str, tuple[float, float]]   # only changed thresholds
    policy: tuple[str, str] | None        # (original "id version", candidate "id version") when different
    policy_text_changed: bool | None      # None when the original has no hash
    action_original: WorkflowAction
    action_candidate: WorkflowAction
    reasons_original: list[str]
    reasons_candidate: list[str]
    expected_original: WorkflowAction     # under the original side's policy/thresholds
    expected_candidate: WorkflowAction    # under the candidate side's policy/thresholds
    change: Literal["improved", "regressed", "unchanged", "changed-both-wrong"]
    newly_unsafe: bool
    unsafe_resolved: bool
    identical: bool                       # same action, reasons, gate path and all decisions equal

def diff_traces(original: WorkflowTrace, candidate: WorkflowTrace, *, expected_original: WorkflowAction,
                expected_candidate: WorkflowAction,
                original_label: str, candidate_label: str) -> TraceDiff: ...

def replay_trace(trace: WorkflowTrace, case: PriorAuthCase, *, policy: AuthorizationPolicy,
                 thresholds: Thresholds, now: datetime | None = None) -> WorkflowTrace:
    """Stored decisions re-run through determine_action. Returns a new trace with a new trace_id,
    run_id f"replay-{trace.run_id}", replay_of=trace.trace_id, the candidate policy/thresholds,
    policy_text_hash of the candidate policy, mode="simulated", relay_git_sha=current."""

def replay_run(traces: Sequence[WorkflowTrace], cases: Sequence[PriorAuthCase], *,
               policy_id: str | None, auto_process: float | None) -> list[WorkflowTrace]:
    """Run-level policy replay for 3B: pairs by case id with paired_cases (all its checks apply),
    replays each trace; None keeps each trace's own policy/threshold. One shared run_id."""
```

Details:

- **`crossed`.** A threshold is crossed for a decision when that decision's value sits on different sides of the threshold on the two sides of the diff.
  - auto_process: diagnosis_support, step_therapy and documentation_complete use `p_yes >= t`. material_contradiction uses `1 - p_yes >= t`. missing_evidence uses `p(NONE) >= t`. Each side uses its own trace's thresholds, so a pure threshold change shows as crossed.
  - The other four thresholds follow the engine's own comparisons for the gate they feed.
  - Implement this with a single table mapping `(decision, threshold name) → comparison`. Unit-test it against `relay/workflow/engine.py` on the fixtures, so the table cannot silently drift from the engine.
- **The `WorkflowTrace` schema change.** It gains `replay_of: str | None = None`. This is backward compatible, because old traces load with None. `mode="simulated"` already exists in the Literal and is used for replayed traces. Committed baselines are not rewritten.
- **`identical`.** Compare the decisions by model equality after dropping `latency_ms`, `estimated_cost_usd` and `input_tokens` from the bundle. Those vary between otherwise identical runs.

## 4. CLI

```
relay replay CASE_ID --traces FILE --dataset DIR
    [--policy ID | --latest-policy] [--at FLOAT]
    [--candidate-traces FILE]
    [--provider jev|claude|rules|groundtruth [--question-set Q] [--mode sync] [--budget-usd N --ledger PATH]]
    [--all-gates] [--json]
```

- `--traces` accepts `.jsonl` and `.jsonl.gz`, through `read_traces`. The file must contain exactly one trace for CASE_ID; zero or several is exit 2. `--candidate-traces` has the same rule.
- `--at` alone means "original policy, new auto_process".
- **Terminal output:**
  1. the P4 header
  2. the P5 line, if applicable
  3. EXPECTED, if present
  4. a decisions table (question, original, candidate, Δ, crossed, `*` when answer_changed)
  5. the changed thresholds
  6. the gate-path rows that differ (all rows with `--all-gates`)
  7. the actions, with classification and reasons
  8. one summary line: `ACTION CHANGED: HUMAN_REVIEW → AUTO_PROCESS (NEWLY UNSAFE)`, `ACTION UNCHANGED`, or the P3 lines
- `--json` prints `TraceDiff.model_dump_json(indent=2)` and nothing else. It is still subject to the P3 exit code.
- **Exit codes:**
  - 0: success
  - 2: usage or input error, including a hash mismatch or a missing or duplicate trace
  - 3: ENGINE DRIFT, in reproduce mode only
  - 4: NEWLY UNSAFE, in any mode, so scripts can gate on it. The terminal output is still printed in full.

  Of 3 and 4, the higher code wins.
- The existing keyless / `--env-file` behaviour is unchanged. Reproduce, policy replay and candidate-traces make no network calls and need no keys. The CLI must not construct a network client for them.

## 5. Components

- `relay/evaluation/tracediff.py`: §3.
- `relay/cases/policies.py`: `latest_policy_for`.
- `relay/traces/models.py`: `replay_of`.
- `relay/cli.py`: a `replay` command. Rendering goes in `relay/reporting.py` (`render_trace_diff(diff, all_gates) -> str`), following the pattern of the existing renderers.
- README: a "Replay" section with two real, offline examples on committed gold traces:
  - `relay replay GOLD-TMP-17 --traces <jev gold> --dataset evals/gold --candidate-traces <claude gold>`
  - the same case with `--at 0.95` (policy replay showing the threshold effect)

  The output is pasted from real runs.

## 6. Testing

- **Unit tests for `tracediff`:**
  - `crossed` table vs engine agreement. For every fixture bundle and threshold, flipping one decision across one threshold changes the engine's gate outcome exactly when `crossed` names that threshold.
  - `delta` for yes_no and choice, and for missing decisions.
  - The change classification matrix, covering all combinations of correct / wrong-safe / unsafe.
  - `identical` ignores latency and cost.
  - `replay_trace` sets replay_of, mode, run_id and hash.
  - `replay_run` enforces paired_cases.
- **`latest_policy_for`:** with the registry monkeypatched to hold three versions, including v0.10 vs v0.9, and a different medication.
- **CLI integration, offline** (smoke dataset plus the ground-truth and rules providers to make trace files in tmp):
  - Reproduce gives REPRODUCED and exit 0.
  - A monkeypatched engine change gives ENGINE DRIFT and exit 3.
  - `--at` shows a crossed threshold.
  - `--candidate-traces` between rules and ground truth shows NEWLY UNSAFE and exit 4 where applicable.
  - A hash mismatch (edited case copy in tmp) gives exit 2.
  - Mutually exclusive flags give exit 2.
  - `--json` round-trips into `TraceDiff`.
  - No network client is constructed with the keys unset.
- **Live candidate:** covered with the fake Claude/Jev providers from the existing test fakes. A trace file is written, and the budget guard is invoked for Claude.
- **Committed gold traces:** replaying every gold trace for all four providers in reproduce mode gives REPRODUCED (no engine drift). This test guards committed baselines against engine changes, next to the drift guard.

## 7. Definition of done

- Tests and ruff pass.
- The README "Replay" section contains real pasted output.
- No paid calls are made in 3A.
