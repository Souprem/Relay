# Phase 3D1: Generator gen-v0.3, Policy immunara-v0.2, Question Set q-v0.3 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build every offline piece of Phase 3D: generator gen-v0.3 (interrupted and old methotrexate courses, policy-aware labels), policy immunara-v0.2 (recency), question set q-v0.3 and its composition, `recompose`, the Jev spend counter, `relay bench` (tested with fakes), and the CLI flags. This makes the paid experiments in plan 3D2 single commands.

**Architecture:** Recency and interruption both live in step-therapy composition, in code (`relay/decisions/step_therapy.py`). The question-set version selects the path in `compose_decisions`: q-v0.2 is unchanged, and q-v0.3 composes P(some consecutive segment ≥ N). `recompose()` rebuilds a Jev bundle from its stored raw answers under any policy, so one paid run yields both a stale (immunara-v0.1) and an aware (immunara-v0.2) run. The generator gains a `generator_version` parameter; gen-v0.2 output stays byte-identical because gen-v0.3 draws happen only on its own branch. A Jev spend counter reuses the Claude ledger machinery on its own file.

**Tech Stack:** Python 3.12, uv, Pydantic v2, Typer, typesafe-sdk 0.7.x, pytest (`asyncio_mode=auto`, `-m 'not live'` by default), ruff.

**Spec:** `docs/superpowers/specs/2026-09-26-phase3d-questions-and-policy-shift-design.md` (approved). The paid experiments, committed artifacts, gates, CI regeneration and README are plan 3D2, `docs/superpowers/plans/2026-09-26-phase3d2-experiments.md`. It starts after this plan is done.

## Global Constraints

- Synthetic data only.
- Never open `.env` (read, cat, grep or edit it). No task needs it.
- No Claude calls. No paid Jev call anywhere in this plan: every test uses a fake client.
- Jev spend for all of 3D is ≤ $1.00 (spent in plan 3D2 only; this plan spends $0).
- Run offline CLI commands as `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env ...`.
- `results/claude-spend.json` is never read or written, by tests or by this work. Tests use tmp ledgers.
- Stage files by explicit path. Never `git add -A` or `git add .`.
- Each commit uses two `-m` arguments. The second is exactly `-m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.
- Don't push.
- At the end of every task, `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q` must pass.
- The committed gates must pass: `env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env regression --config evals/regression/gates.json --strict-generated` exits 0. It needs `evals/generated/gen-v0.2-holdout` on disk; if it is missing, regenerate it with the `relay generate` commands in `.github/workflows/ci.yml`.
- gold-v0.1 (`evals/gold/`) is never edited. Nothing under `evals/` changes in this plan.
- gen-v0.2 output stays byte-identical: `relay generate --verify` against both committed gen-v0.2 manifests must print `OK:` after every generator task.
- Branch: `feat/phase3` at or after `f75a89f` (Phase 3C complete, including its README and final-review fixes). Work from the repository root `/Users/joelbrook/Desktop/Code/Relay`.

## Verified facts this plan relies on (checked while planning, on a scratch copy)

Every block below was prototyped on a scratch clone of `feat/phase3` with Phase 3C Tasks 1–6 applied (identical to `86aeb82`). The blocks were then re-applied mechanically from this document to a fresh clone of `f75a89f` (3C complete). For every task, the new tests failed before its implementation and passed after, and the full suite and ruff passed.

- **Tests.** 1085 before (at `f75a89f`); 1207 after Task 11. The per-task counts below assume `evals/generated/gen-v0.2-{dev,holdout}` are on disk; without them, a few tests skip instead.
- **gen-v0.2 is byte-identical.** After Tasks 6, 7 and 8, `relay generate --verify` printed `OK:` for both committed manifests (`sha256:3eec030b…` dev, `sha256:958fbfc3…` holdout), and both committed manifest files round-trip through `read_manifest`/`write_manifest` byte for byte (Task 8 adds a test).
- **The q-v0.2 composition path is unchanged (golden).** Recomposing every committed Jev trace under its own policy (immunara-v0.1) and question set reproduced the stored step_therapy exactly (max |Δp| = 0) and matched the stored decisions and derivations, on 1,910 traces: gold-v0.1 q-v0.2 (100), gen-v0.2-dev q-v0.1 (400) and q-v0.2 (400), gen-v0.2-holdout q-v0.2 (1000), and smoke q-v0.1 (10). Task 5 commits this as a test (gold always; gen-v0.2 when generated).
- **Hashes.** q-v0.1 `sha256:b3955316…` and q-v0.2 `sha256:89717c79…` are unchanged by q-v0.3. q-v0.3 is `sha256:4589d78b40d2be56216766beec111882b7f96c761be99d1f6ba218e3bfd2979c` under both immunara policies (the question text uses only the drug and the indication).
- **TypeSafe client.** `system_one` sends all questions of a call in one HTTP request and returns one `usage` and no per-question timing (details in Task 11).
- **Jev cost from committed traces (`estimated_cost_usd`).** gen-v0.2-dev q-v0.1: $0.044233 / 400 = $0.000111 per case; q-v0.2: $0.044771 / 400 = $0.000112; gen-v0.2-holdout q-v0.2: $0.112036 / 1000 = $0.000112; gold q-v0.2: $0.011513 / 100 = $0.000115 (max $0.000126882). About 2,665 input tokens per case at $0.042/M. Question text is billed once per call: q-v0.1 → q-v0.2 added 168 characters of instructions and exactly 32.0 mean tokens. The counter's rate ($0.000013 per question, at least 12 per call) is derived from these numbers in Task 9.
- **gen-v0.3 datasets (for plan 3D2).** With this plan's code: `gen-v0.3-dev` (seed 3, 400) `sha256:ae3dc2f8…`, `gen-v0.3-holdout` (seed 4, 1000) `sha256:2aefa63d…`, and `gen-v0.3-shift` (seed 5, 400, policy v0.2) `sha256:3f5a9c1c…`. All three verify. The groundtruth provider scores 400/400 on dev and shift. On shift, 18 cases would be auto-processed under v0.1 labels but not under v0.2, which is the room for stale-only unsafe automations.
- **Committed gates** still pass 9/9 with `--strict-generated` after Task 11, and `git status --short evals/` is empty.

## Resolved ambiguities (decisions this plan makes)

1. **`recompose` signature.** The spec's `recompose(bundle, *, policy, question_set_version)` cannot compute durations without the case's `as_of_date`, which a `DecisionBundle` doesn't carry. So it is `recompose(bundle, *, case, policy, question_set_version)`. `question_set_version` must equal the bundle's own (ValueError otherwise), and only Jev bundles are accepted (only they store raw typed answers).
2. **Recency on the q-v0.2 path.** The spec says q-v0.2 composition is unchanged, and that a policy with `max_days_since_therapy` requires a recent qualifying segment. Both hold: `p_duration_at_least` gains `max_days_since=None`, so under immunara-v0.1 the q-v0.2 path is identical (golden test), and under immunara-v0.2 recency applies on either path.
3. **Recency is conservative.** A candidate end counts from its earliest possible date (month-only → first of the month); an ongoing course ends at as_of. The generator's labels use the same rule (conservative end).
4. **q-v0.3's two text edits.** "(the first time, if it was restarted)" is appended after "taking methotrexate" in the three `mtx_start_*` instructions. "(the last time, if it was restarted)" is appended in the three `mtx_end_*` instructions and after "(not a relative's)" in `mtx_end_status`. Every other q-v0.2 question is byte-identical.
5. **Pause and restart wording.** `mtx_pause_*` asks when the patient "first stop[ped] taking methotrexate before restarting it (a hold or pause counts as a stop)", and `mtx_restart_*` when they "restart[ed] taking methotrexate after a hold, pause or stop". Each "Answer 'none' if …" clause adds ", or if the course was never stopped and restarted", and their `none` option says so.
6. **Default question set stays q-v0.2.** Adoption is decided in plan 3D2 on dev data. The CLI default isn't changed after the fact; runs pass `--questions q-v0.3` explicitly.
7. **Interrupted segments are day-precision** (like dates_conflict cases), with split-across-documents off. Month ranges would make the D8 labels ambiguous at the 84-day line. Short segments are ≤ 77 days and long ones ≥ 98, so no interrupted segment is a near miss.
8. **The outcome for D8.** Following the spec's label rule, a qualifying segment plus a documented inadequate response or intolerance anywhere in the course satisfies step therapy. The rendered outcome is always the final stop reason. The hold reason is never a response or an intolerance: the drug was resumed afterwards. The lab hold is worded as a recheck that came back normal, so it cannot be read as intolerance.
9. **Proportions.** About 20% of taken courses are interrupted (eligible courses: taken and not contradicted, at probability 0.24), and about 25% of taken courses ended more than 365 days before as_of (ended courses at probability 0.3125, since ongoing courses can't be old). Old courses land 380–720 days back. The audit checks both at ±5 pp over 2,000 seeds.
10. **`relay generate --policy v0.1|v0.2`** is added beside `--generator`, because `gen-v0.3-shift` must be generated, labelled and verified under immunara-v0.2. The manifest records `policy_version`, but writes it only when it isn't v0.1, so gen-v0.2 manifests stay byte-identical. `--verify` reads both versions from the manifest; giving `--generator`/`--policy` with `--verify` is exit 2.
11. **Reusing budget.py for Jev.** The Jev counter is a thin module (`relay/evaluation/jev_spend.py`) over `SpendLedger`/`reserve`/`settle`/`check_budget` on its own ledger file, with mode "sync". `BudgetExceeded` and `check_budget` gain a `label` (default "Claude", so every Claude message is unchanged).
12. **Estimate formula.** cases × max(questions, 12) × $0.000013 (rate derivation in Task 9). The 12-question floor prices a call's state (policy and documents), which matters for the bench's 1- and 5-question calls. The spend cap check counts settled costs plus open reservations.
13. **Where the counter applies.** It applies to `relay eval --provider jev` (flags `--jev-budget-usd` and `--jev-ledger`, default ledger `results/jev-spend-3d.json`) and to `relay bench`, where `--jev-budget-usd` is required. It is exit 2 with another provider, with `--traces` re-scoring, or as `--jev-ledger` without `--jev-budget-usd`. Plain `relay eval --provider jev` without the flags behaves as before; plan 3D2 always passes them.
14. **`relay recompose` output.** It writes the committed-bundle format directly (`traces.jsonl.gz` and `run-manifest.json`), with `mode="simulated"`, `source_run_id`, and the extra keys `policy_id` and `thresholds` (as in 3B's simulated runs). Thresholds follow `replay_thresholds`: the trace's own for the same policy version, the registered ones for another.
15. **Bench design.** One request per (case, k), strictly sequential. k = prefixes of `QUESTION_IDS_V0_3` (1 = diagnosis_support; 5 adds documentation_complete, material_contradiction, missing_evidence, mtx_start_month; 10 adds mtx_start_day, mtx_start_year, mtx_end_status, mtx_end_month, mtx_end_day). 20 = the 19 plus `diagnosis_support_padding`. Percentiles are nearest-rank. Cost per case is the mean estimated cost of that size's calls.

## Edit conventions

"Replace" steps give the exact current text and its replacement; the current text occurs exactly once in the file. "Append" steps add the block to the end of the file after two blank lines. "Create" steps give the whole file. Apply the blocks of a step in the order shown.

---


### Task 1: Policy immunara-v0.2 and thresholds v0.2

**Files:**
- Create: `policies/immunara-v0.2.md`
- Modify: `relay/cases/policies.py`
- Modify: `relay/workflow/thresholds.py`
- Test (modify): `tests/integration/test_cli_replay.py`
- Test (modify): `tests/unit/test_policies.py`
- Test (modify): `tests/unit/test_replay.py`
- Test (modify): `tests/unit/test_thresholds.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `policies/immunara-v0.2.md`: v0.1's text plus the recency sentence in requirement 3.
  - `AuthorizationPolicy.max_days_since_therapy: int | None = None` (`relay/cases/policies.py`); `load_policy("immunara-v0.2").max_days_since_therapy == 365`, same medication, indication, min_age, required_therapy and min_weeks as v0.1.
  - `latest_policy_for("immunara-v0.1") == "immunara-v0.2"`.
  - `relay.workflow.thresholds.THRESHOLDS_V0_2` (v0.1 values, `version="v0.2"`); `load_thresholds("v0.2")` returns it.

Registering v0.2 changes two existing expectations: `--latest-policy` now resolves to immunara-v0.2, and the tests that simulate "a v0.2 policy without thresholds" must now remove the real v0.2 thresholds for the test's duration (`monkeypatch.delitem`). The engine is unchanged: recency lives in step-therapy composition (Tasks 2 and 4).

- [ ] **Step 1: Write the failing tests**

In `tests/integration/test_cli_replay.py`, replace:

```python
    assert row(diff, "diagnosis_support").crossed == []


def test_latest_policy_and_explicit_policy_resolve_today_to_immunara_v0_1(tmp_path, smoke_runs):
    for flags in (["--latest-policy"], ["--policy", "immunara-v0.1"]):
        result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], *flags)
        assert result.exit_code == 0, result.output
        assert (
            "STORED DECISIONS under policy immunara-v0.1 (v0.1), thresholds v0.1 — judgments"
        ) in result.output
        assert "ACTION UNCHANGED: AUTO_PROCESS" in result.output
        assert REPRODUCED_LINE not in result.output  # policy replay never claims reproduction
```

with:

```python
    assert row(diff, "diagnosis_support").crossed == []


def test_explicit_policy_is_v0_1_and_latest_policy_resolves_to_immunara_v0_2(tmp_path, smoke_runs):
    for flags, policy in (
        (["--policy", "immunara-v0.1"], "immunara-v0.1 (v0.1), thresholds v0.1"),
        (["--latest-policy"], "immunara-v0.2 (v0.2), thresholds v0.2"),
    ):
        result = replay(tmp_path, "AUTO-01", smoke_runs["groundtruth"], *flags)
        assert result.exit_code == 0, result.output
        assert f"STORED DECISIONS under policy {policy} — judgments" in result.output
        assert "ACTION UNCHANGED: AUTO_PROCESS" in result.output
        assert REPRODUCED_LINE not in result.output  # policy replay never claims reproduction
```

In `tests/integration/test_cli_replay.py`, replace:

```python
    if with_thresholds:
        v2 = THRESHOLDS_V0_1.model_copy(update={"version": "v0.2", "auto_process": 0.9})
        monkeypatch.setitem(thresholds_module._BY_VERSION, "v0.2", v2)


def test_policy_replay_onto_another_version_uses_its_thresholds(tmp_path, smoke_runs, monkeypatch):
```

with:

```python
    if with_thresholds:
        v2 = THRESHOLDS_V0_1.model_copy(update={"version": "v0.2", "auto_process": 0.9})
        monkeypatch.setitem(thresholds_module._BY_VERSION, "v0.2", v2)
    else:
        monkeypatch.delitem(thresholds_module._BY_VERSION, "v0.2")


def test_policy_replay_onto_another_version_uses_its_thresholds(tmp_path, smoke_runs, monkeypatch):
```

In `tests/unit/test_policies.py`, replace:

```python
import pytest

import relay.cases.policies as policies_module
from relay.cases.policies import latest_policy_for


def spec(version: str, medication: str) -> dict[str, object]:
```

with:

```python
import pytest

import relay.cases.policies as policies_module
from relay.cases.policies import latest_policy_for, load_policy


def spec(version: str, medication: str) -> dict[str, object]:
```

In `tests/unit/test_policies.py`, replace:

```python
    return fake


def test_the_real_registry_resolves_immunara_to_itself():
    assert latest_policy_for("immunara-v0.1") == "immunara-v0.1"


def test_versions_compare_numerically_not_as_text(registry):
```

with:

```python
    return fake


def test_the_real_registry_resolves_immunara_to_v0_2():
    assert latest_policy_for("immunara-v0.1") == "immunara-v0.2"
    assert latest_policy_for("immunara-v0.2") == "immunara-v0.2"


def test_versions_compare_numerically_not_as_text(registry):
```

Append to the end of `tests/unit/test_policies.py`:

```python
# ---- Phase 3D: immunara-v0.2 adds a recency requirement ----


def test_immunara_v0_2_is_v0_1_plus_the_recency_requirement():
    v1, v2 = load_policy("immunara-v0.1"), load_policy("immunara-v0.2")
    assert (v1.max_days_since_therapy, v2.max_days_since_therapy) == (None, 365)
    same = {"medication", "indication", "min_age", "required_therapy", "min_weeks"}
    assert v1.model_dump(include=same) == v2.model_dump(include=same)
    assert (v1.version, v2.version) == ("v0.1", "v0.2")
    added = (
        "The\n   qualifying methotrexate course must have been ongoing, or have ended, within the "
        "12 months\n   (365 days) before the request date."
    )
    assert added in v2.text and added not in v1.text
    assert v2.text.replace(" " + added, "").replace("immunara-v0.2", "immunara-v0.1") == v1.text
```

In `tests/unit/test_replay.py`, replace:

```python
    monkeypatch.setitem(policies_module._POLICIES, "immunara-v0.2", spec)
    if with_thresholds:
        monkeypatch.setitem(thresholds_module._BY_VERSION, "v0.2", THRESHOLDS_V2)


def test_same_version_keeps_the_traces_own_thresholds_even_when_overridden():
```

with:

```python
    monkeypatch.setitem(policies_module._POLICIES, "immunara-v0.2", spec)
    if with_thresholds:
        monkeypatch.setitem(thresholds_module._BY_VERSION, "v0.2", THRESHOLDS_V2)
    else:
        monkeypatch.delitem(thresholds_module._BY_VERSION, "v0.2")


def test_same_version_keeps_the_traces_own_thresholds_even_when_overridden():
```

In `tests/unit/test_thresholds.py`, replace:

```python
"""override_auto_process: one helper for every --at style override (F1 / 3A Minor 2)."""

from relay.workflow.thresholds import THRESHOLDS_V0_1, override_auto_process


def test_the_override_replaces_auto_process_and_records_it_in_the_version():
```

with:

```python
"""override_auto_process: one helper for every --at style override (F1 / 3A Minor 2)."""

from relay.workflow.thresholds import (
    THRESHOLDS_V0_1,
    THRESHOLDS_V0_2,
    load_thresholds,
    override_auto_process,
)


def test_the_override_replaces_auto_process_and_records_it_in_the_version():
```

Append to the end of `tests/unit/test_thresholds.py`:

```python
def test_v0_2_thresholds_are_v0_1_values_under_their_own_version():
    assert load_thresholds("v0.2") is THRESHOLDS_V0_2
    assert THRESHOLDS_V0_2.version == "v0.2"
    assert THRESHOLDS_V0_2.model_dump(exclude={"version"}) == THRESHOLDS_V0_1.model_dump(
        exclude={"version"}
    )
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run: `uv run pytest -q tests/integration/test_cli_replay.py tests/unit/test_policies.py tests/unit/test_replay.py tests/unit/test_thresholds.py`

Expected: FAIL. `test_immunara_v0_2_is_v0_1_plus_the_recency_requirement` fails with `KeyError: "unknown policy 'immunara-v0.2'"`, the latest-policy tests expect v0.2, and `THRESHOLDS_V0_2` cannot be imported.

- [ ] **Step 3: Implement**

Create `policies/immunara-v0.2.md`:

```markdown
# ExampleHealth Specialty Drug Policy — Immunara (policy immunara-v0.2)

SYNTHETIC POLICY FOR ENGINEERING EVALUATION ONLY. Immunara is a fictional medication and this is
not a real coverage policy.

Immunara is covered for rheumatoid arthritis only when ALL of the following are documented:

1. Age: the patient is 18 years of age or older.
2. Diagnosis: a clinician documents an established diagnosis of rheumatoid arthritis for this
   patient. Suspected diagnoses or diagnoses pending workup do not qualify.
3. Prior treatment: the patient has taken methotrexate for at least 12 consecutive weeks. The
   qualifying methotrexate course must have been ongoing, or have ended, within the 12 months
   (365 days) before the request date.
4. Response: the clinician documents that methotrexate was ineffective (inadequate response) or was
   stopped because of intolerance or a contraindication.
5. Submission documentation: the request includes the patient's insurance member ID, a clinician
   note supporting the diagnosis, and the patient's treatment history, including whether and when
   methotrexate was taken.

Information about relatives or other people does not count as evidence about the patient.
```

In `relay/cases/policies.py`, replace:

```python
    required_therapy: str
    min_weeks: int
    text: str


_POLICIES: dict[str, dict[str, object]] = {
```

with:

```python
    required_therapy: str
    min_weeks: int
    text: str
    # Recency (immunara-v0.2): the qualifying course must be ongoing or have ended at most this
    # many days before the request's as_of_date. None (immunara-v0.1) means no recency rule.
    max_days_since_therapy: int | None = None


_POLICIES: dict[str, dict[str, object]] = {
```

In `relay/cases/policies.py`, replace:

```python
        "required_therapy": "methotrexate",
        "min_weeks": 12,
        "text_file": "immunara-v0.1.md",
    },
}
```

with:

```python
        "required_therapy": "methotrexate",
        "min_weeks": 12,
        "text_file": "immunara-v0.1.md",
    },
    "immunara-v0.2": {
        "version": "v0.2",
        "medication": "Immunara",
        "indication": "rheumatoid arthritis",
        "min_age": 18,
        "required_therapy": "methotrexate",
        "min_weeks": 12,
        "max_days_since_therapy": 365,
        "text_file": "immunara-v0.2.md",
    },
}
```

In `relay/workflow/thresholds.py`, replace:

```python
    missing_evidence_request_info=0.70,
)

_BY_VERSION = {THRESHOLDS_V0_1.version: THRESHOLDS_V0_1}


def load_thresholds(version: str) -> Thresholds:
```

with:

```python
    missing_evidence_request_info=0.70,
)

# immunara-v0.2 changes only the step-therapy rule (recency), which is composed in code, so its
# thresholds are v0.1's values under the v0.2 version: nothing was tuned.
THRESHOLDS_V0_2 = THRESHOLDS_V0_1.model_copy(update={"version": "v0.2"})

_BY_VERSION = {t.version: t for t in (THRESHOLDS_V0_1, THRESHOLDS_V0_2)}


def load_thresholds(version: str) -> Thresholds:
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run pytest -q tests/integration/test_cli_replay.py tests/unit/test_policies.py tests/unit/test_replay.py tests/unit/test_thresholds.py`

Expected: PASS.

- [ ] **Step 5: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`

Expected: all pass (about 1087 passed).

- [ ] **Step 6: Commit**

```bash
git add policies/immunara-v0.2.md relay/cases/policies.py relay/workflow/thresholds.py tests/integration/test_cli_replay.py tests/unit/test_policies.py tests/unit/test_replay.py tests/unit/test_thresholds.py
git commit -m "feat: add policy immunara-v0.2 (recency requirement) and thresholds v0.2" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 2: Step-therapy composition: recency and consecutive segments

**Files:**
- Modify: `relay/decisions/step_therapy.py`
- Test (modify): `tests/unit/test_step_therapy.py`

**Interfaces:**
- Consumes: nothing new (pure functions over `DateParts`).
- Produces (all in `relay/decisions/step_therapy.py`):
  - `p_duration_at_least(*, start, end_status, end, as_of, min_days, max_days_since: int | None = None) -> DurationResult`. With `max_days_since=None` the arithmetic and `DurationResult.to_dict()` are exactly as before (the dict gains `"max_days_since_therapy"` only when it is set).
  - `end_candidates(end_status, end, as_of) -> list[DateCandidate]`
  - `qualifies(start, end, *, as_of, min_days, max_days_since) -> bool`
  - `p_pairs(starts, ends, *, as_of, min_days, max_days_since) -> float`
  - `SegmentResult` (fields `p_duration, min_days, max_days_since, p_interrupted, p_continuous, p_first_segment, p_second_segment, p_either_segment, start_candidates, pause_candidates, restart_candidates, end_candidates`; `to_dict()`)
  - `p_consecutive_at_least(*, start, pause, restart, end_status, end, p_interrupted, as_of, min_days, max_days_since=None) -> SegmentResult` computing `(1 - p_int) * P(start -> end) + p_int * (P(A) + P(B) - P(A) * P(B))`, A = start -> pause, B = restart -> end.

- [ ] **Step 1: Write the failing tests**

In `tests/unit/test_step_therapy.py`, replace:

```python
from relay.decisions.step_therapy import (
    DateParts,
    date_candidates,
    p_duration_at_least,
    prune,
)
```

with:

```python
from relay.decisions.step_therapy import (
    DateParts,
    date_candidates,
    p_consecutive_at_least,
    p_duration_at_least,
    prune,
)
```

Append to the end of `tests/unit/test_step_therapy.py`:

```python
# ---- Phase 3D: recency (immunara-v0.2) and interrupted courses (q-v0.3) ----

NOT_STATED = DateParts(month={"none": 1.0}, day={"none": 1.0}, year={"none": 1.0})


def consecutive(start, pause, restart, end, *, p_int, status=None, as_of=AS_OF, recency=None):
    return p_consecutive_at_least(
        start=start,
        pause=pause,
        restart=restart,
        end_status=status or certain("ended"),
        end=end,
        p_interrupted=p_int,
        as_of=as_of,
        min_days=MIN_DAYS,
        max_days_since=recency,
    )


def test_recency_none_leaves_the_duration_and_its_derivation_unchanged():
    plain = duration(parts("January", "12", "2026"), parts("June", "1", "2026"))
    assert plain.p_duration == 1.0
    assert plain.max_days_since is None
    assert "max_days_since_therapy" not in plain.to_dict()


def test_recency_drops_a_course_that_ended_more_than_365_days_before_as_of():
    start, end = parts("January", "12", "2025"), parts("June", "1", "2025")  # 140 days
    as_of = date(2026, 6, 2)  # 366 days after the end
    old = p_duration_at_least(
        start=start,
        end_status=certain("ended"),
        end=end,
        as_of=as_of,
        min_days=MIN_DAYS,
        max_days_since=365,
    )
    assert old.p_duration == 0.0
    assert old.to_dict()["max_days_since_therapy"] == 365
    on_the_day = p_duration_at_least(
        start=start,
        end_status=certain("ended"),
        end=end,
        as_of=date(2026, 6, 1),  # exactly 365 days after the end
        min_days=MIN_DAYS,
        max_days_since=365,
    )
    assert on_the_day.p_duration == 1.0


def test_recency_uses_the_earliest_possible_end_of_a_month_only_date():
    # Ended "June 2025": the earliest end is 2025-06-01, 366 days before 2026-06-02.
    result = p_duration_at_least(
        start=parts("January", "12", "2025"),
        end_status=certain("ended"),
        end=parts("June", "none", "2025"),
        as_of=date(2026, 6, 2),
        min_days=MIN_DAYS,
        max_days_since=365,
    )
    assert result.p_duration == 0.0


def test_an_ongoing_course_is_always_recent():
    result = p_duration_at_least(
        start=parts("January", "12", "2024"),
        end_status=certain("ongoing"),
        end=UNKNOWN,
        as_of=AS_OF,
        min_days=MIN_DAYS,
        max_days_since=365,
    )
    assert result.p_duration == 1.0


def test_gold_tmp_17_pattern_neither_segment_reaches_twelve_weeks():
    # 2026-01-05 -> held 2026-02-23 (49 d), restarted 2026-03-23 -> 2026-05-18 (56 d).
    start, end = parts("January", "5", "2026"), parts("May", "18", "2026")
    pause, restart = parts("February", "23", "2026"), parts("March", "23", "2026")
    result = consecutive(start, pause, restart, end, p_int=1.0, as_of=date(2026, 6, 10))
    assert (result.p_continuous, result.p_first_segment, result.p_second_segment) == (
        1.0,
        0.0,
        0.0,
    )
    assert result.p_duration == 0.0
    # Read as one continuous course (the q-v0.2 reading) it would pass: 133 days.
    unread = consecutive(start, pause, restart, end, p_int=0.0, as_of=date(2026, 6, 10))
    assert unread.p_duration == 1.0


def test_gold_tmp_18_pattern_the_later_segment_qualifies():
    # 2025-10-06 -> stopped 2025-11-03 (28 d), restarted 2026-01-12 -> 2026-05-04 (112 d).
    result = consecutive(
        parts("October", "6", "2025"),
        parts("November", "3", "2025"),
        parts("January", "12", "2026"),
        parts("May", "4", "2026"),
        p_int=1.0,
        as_of=date(2026, 6, 15),
    )
    assert (result.p_first_segment, result.p_second_segment) == (0.0, 1.0)
    assert result.p_duration == 1.0


def test_the_earlier_segment_can_qualify_and_an_ongoing_restart_ends_at_as_of():
    result = consecutive(
        parts("January", "5", "2026"),
        parts("May", "4", "2026"),  # 119 days
        parts("August", "31", "2026"),
        UNKNOWN,
        p_int=1.0,
        status=certain("ongoing"),  # restart -> as_of 2026-09-15 = 15 days
    )
    assert (result.p_first_segment, result.p_second_segment) == (1.0, 0.0)
    assert result.p_duration == 1.0


def test_segments_combine_by_inclusion_exclusion_and_mix_by_p_interrupted():
    # Start and pause each certain; restart split 50/50 between a qualifying and a short one.
    result = consecutive(
        parts("January", "5", "2026"),
        DateParts(month={"May": 0.6, "February": 0.4}, day=certain("4"), year=certain("2026")),
        DateParts(month={"March": 0.5, "July": 0.5}, day=certain("1"), year=certain("2026")),
        parts("August", "1", "2026"),
        p_int=0.8,
    )
    # A: Jan 5 -> May 4 (119 d) qualifies, -> Feb 4 (30 d) does not: P(A) = 0.6.
    # B: Mar 1 -> Aug 1 (153 d) qualifies, Jul 1 -> Aug 1 (31 d) does not: P(B) = 0.5.
    assert result.p_first_segment == pytest.approx(0.6)
    assert result.p_second_segment == pytest.approx(0.5)
    assert result.p_either_segment == pytest.approx(0.6 + 0.5 - 0.3)
    assert result.p_continuous == 1.0  # Jan 5 -> Aug 1 = 208 days
    assert result.p_duration == pytest.approx(0.2 * 1.0 + 0.8 * 0.8)


def test_an_interruption_with_unknown_pause_and_restart_contributes_nothing():
    result = consecutive(
        parts("January", "5", "2026"),
        NOT_STATED,
        NOT_STATED,
        parts("August", "1", "2026"),
        p_int=0.3,
    )
    assert (result.p_first_segment, result.p_second_segment) == (0.0, 0.0)
    assert result.p_duration == pytest.approx(0.7)
    assert result.pause_candidates == () and result.restart_candidates == ()


def test_recency_applies_to_each_segment_end():
    # The earlier segment qualifies on length but ended 400 days before as_of; the later one
    # is short. Under a 365-day rule nothing qualifies.
    as_of = date(2026, 9, 15)
    start, pause = parts("January", "5", "2025"), parts("August", "11", "2025")
    restart, end = parts("August", "1", "2026"), parts("September", "1", "2026")
    assert (as_of - date(2025, 8, 11)).days == 400
    loose = consecutive(start, pause, restart, end, p_int=1.0, as_of=as_of)
    strict = consecutive(start, pause, restart, end, p_int=1.0, as_of=as_of, recency=365)
    assert (loose.p_duration, strict.p_duration) == (1.0, 0.0)


def test_segment_derivation_records_every_term():
    result = consecutive(
        parts("January", "5", "2026"),
        parts("February", "23", "2026"),
        parts("March", "23", "2026"),
        parts("May", "18", "2026"),
        p_int=0.9,
        recency=365,
    )
    record = result.to_dict()
    assert set(record) == {
        "min_days",
        "max_days_since_therapy",
        "p_duration",
        "p_interrupted",
        "p_continuous",
        "p_first_segment",
        "p_second_segment",
        "p_either_segment",
        "start_candidates",
        "pause_candidates",
        "restart_candidates",
        "end_candidates",
    }
    assert record["max_days_since_therapy"] == 365
    assert record["p_interrupted"] == 0.9
    assert record["pause_candidates"] == [
        {"earliest": "2026-02-23", "latest": "2026-02-23", "probability": 1.0}
    ]
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run: `uv run pytest -q tests/unit/test_step_therapy.py`

Expected: FAIL. `ImportError: cannot import name 'p_consecutive_at_least'` (the whole module fails to collect).

- [ ] **Step 3: Implement**

In `relay/decisions/step_therapy.py`, replace:

```python
earliest possible end. Any unknown part ("none", invalid date, end not stated) contributes no
probability mass toward "satisfied". Date parts are treated as independent -- an approximation
that Phase 2 calibration must test.
"""

import calendar
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any
```

with:

```python
earliest possible end. Any unknown part ("none", invalid date, end not stated) contributes no
probability mass toward "satisfied". Date parts are treated as independent -- an approximation
that Phase 2 calibration must test.

A policy with a recency rule (immunara-v0.2's max_days_since_therapy) also needs the qualifying
course to end, conservatively at its earliest possible end, no more than that many days before
as_of (an ongoing course ends at as_of). The rule is applied per (start, end) candidate pair.

q-v0.3 reads an interrupted course as two segments (first start -> pause, restart -> final end);
p_consecutive_at_least composes P(some single segment is long enough) from them.
"""

import calendar
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any
```

In `relay/decisions/step_therapy.py`, replace:

```python
    min_days: int
    start_candidates: tuple[DateCandidate, ...]
    end_candidates: tuple[DateCandidate, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_days": self.min_days,
            "p_duration": round(self.p_duration, 6),
            "start_candidates": [c.to_dict() for c in self.start_candidates],
            "end_candidates": [c.to_dict() for c in self.end_candidates],
        }


def p_duration_at_least(
    *,
    start: DateParts,
    end_status: Mapping[str, float],
    end: DateParts,
    as_of: date,
    min_days: int,
) -> DurationResult:
    starts = date_candidates(start)
    status = prune(end_status)
    p_ended = status.get("ended", 0.0)
    p_ongoing = status.get("ongoing", 0.0)
```

with:

```python
    min_days: int
    start_candidates: tuple[DateCandidate, ...]
    end_candidates: tuple[DateCandidate, ...]
    max_days_since: int | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "min_days": self.min_days,
            "p_duration": round(self.p_duration, 6),
            "start_candidates": [c.to_dict() for c in self.start_candidates],
            "end_candidates": [c.to_dict() for c in self.end_candidates],
        }
        if self.max_days_since is not None:  # absent for a policy without a recency rule
            out["max_days_since_therapy"] = self.max_days_since
        return out


def end_candidates(
    end_status: Mapping[str, float], end: DateParts, as_of: date
) -> list[DateCandidate]:
    """Final-end candidates: stated end dates weighted by P(ended), plus as_of for P(ongoing)."""
    status = prune(end_status)
    p_ended = status.get("ended", 0.0)
    p_ongoing = status.get("ongoing", 0.0)
```

In `relay/decisions/step_therapy.py`, replace:

```python
        ]
    if p_ongoing:
        ends.append(DateCandidate(as_of, as_of, p_ongoing))
    p = sum(
        s.probability * e.probability
        for s in starts
        for e in ends
        if (e.earliest - s.latest).days >= min_days
    )
    return DurationResult(
        p_duration=min(p, 1.0),
        min_days=min_days,
        start_candidates=tuple(starts),
        end_candidates=tuple(ends),
    )
```

with:

```python
        ]
    if p_ongoing:
        ends.append(DateCandidate(as_of, as_of, p_ongoing))
    return ends


def qualifies(
    start: DateCandidate,
    end: DateCandidate,
    *,
    as_of: date,
    min_days: int,
    max_days_since: int | None,
) -> bool:
    """Latest start to earliest end is at least min_days and, under a recency rule, the earliest
    end is no more than max_days_since days before as_of."""
    if (end.earliest - start.latest).days < min_days:
        return False
    return max_days_since is None or (as_of - end.earliest).days <= max_days_since


def p_pairs(
    starts: Sequence[DateCandidate],
    ends: Sequence[DateCandidate],
    *,
    as_of: date,
    min_days: int,
    max_days_since: int | None,
) -> float:
    """P(a start/end pair qualifies), capped at 1.0."""
    p = sum(
        s.probability * e.probability
        for s in starts
        for e in ends
        if qualifies(s, e, as_of=as_of, min_days=min_days, max_days_since=max_days_since)
    )
    return min(p, 1.0)


def p_duration_at_least(
    *,
    start: DateParts,
    end_status: Mapping[str, float],
    end: DateParts,
    as_of: date,
    min_days: int,
    max_days_since: int | None = None,
) -> DurationResult:
    starts = date_candidates(start)
    ends = end_candidates(end_status, end, as_of)
    return DurationResult(
        p_duration=p_pairs(
            starts, ends, as_of=as_of, min_days=min_days, max_days_since=max_days_since
        ),
        min_days=min_days,
        start_candidates=tuple(starts),
        end_candidates=tuple(ends),
        max_days_since=max_days_since,
    )


@dataclass(frozen=True)
class SegmentResult:
    """P(consecutive segment >= min_days) for q-v0.3, with every term of the formula."""

    p_duration: float
    min_days: int
    max_days_since: int | None
    p_interrupted: float
    p_continuous: float
    p_first_segment: float
    p_second_segment: float
    p_either_segment: float
    start_candidates: tuple[DateCandidate, ...]
    pause_candidates: tuple[DateCandidate, ...]
    restart_candidates: tuple[DateCandidate, ...]
    end_candidates: tuple[DateCandidate, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_days": self.min_days,
            "max_days_since_therapy": self.max_days_since,
            "p_duration": round(self.p_duration, 6),
            "p_interrupted": round(self.p_interrupted, 6),
            "p_continuous": round(self.p_continuous, 6),
            "p_first_segment": round(self.p_first_segment, 6),
            "p_second_segment": round(self.p_second_segment, 6),
            "p_either_segment": round(self.p_either_segment, 6),
            "start_candidates": [c.to_dict() for c in self.start_candidates],
            "pause_candidates": [c.to_dict() for c in self.pause_candidates],
            "restart_candidates": [c.to_dict() for c in self.restart_candidates],
            "end_candidates": [c.to_dict() for c in self.end_candidates],
        }


def p_consecutive_at_least(
    *,
    start: DateParts,
    pause: DateParts,
    restart: DateParts,
    end_status: Mapping[str, float],
    end: DateParts,
    p_interrupted: float,
    as_of: date,
    min_days: int,
    max_days_since: int | None = None,
) -> SegmentResult:
    """p = (1 - p_int) * P(first start -> final end qualifies)
    + p_int * P(first start -> pause qualifies OR restart -> final end qualifies).

    The two segment events are combined by inclusion-exclusion, P(A) + P(B) - P(A) * P(B),
    under the same independence approximation as the date parts themselves: A reads only the
    start and pause answers and B only the restart and end answers. An unknown pause or restart
    contributes no candidate, so an interruption with unreadable dates adds nothing.
    """
    starts = date_candidates(start)
    pauses = date_candidates(pause)
    restarts = date_candidates(restart)
    ends = end_candidates(end_status, end, as_of)
    p_continuous = p_pairs(
        starts, ends, as_of=as_of, min_days=min_days, max_days_since=max_days_since
    )
    p_first = p_pairs(starts, pauses, as_of=as_of, min_days=min_days, max_days_since=max_days_since)
    p_second = p_pairs(
        restarts, ends, as_of=as_of, min_days=min_days, max_days_since=max_days_since
    )
    p_either = p_first + p_second - p_first * p_second
    p = (1.0 - p_interrupted) * p_continuous + p_interrupted * p_either
    return SegmentResult(
        p_duration=min(p, 1.0),
        min_days=min_days,
        max_days_since=max_days_since,
        p_interrupted=p_interrupted,
        p_continuous=p_continuous,
        p_first_segment=p_first,
        p_second_segment=p_second,
        p_either_segment=p_either,
        start_candidates=tuple(starts),
        pause_candidates=tuple(pauses),
        restart_candidates=tuple(restarts),
        end_candidates=tuple(ends),
    )
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run pytest -q tests/unit/test_step_therapy.py`

Expected: PASS.

- [ ] **Step 5: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`

Expected: all pass (about 1098 passed).

- [ ] **Step 6: Commit**

```bash
git add relay/decisions/step_therapy.py tests/unit/test_step_therapy.py
git commit -m "feat: compose step therapy with a recency rule and consecutive segments" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 3: Question set q-v0.3

**Files:**
- Modify: `relay/decisions/questions.py`
- Test (modify): `tests/unit/test_questions.py`

**Interfaces:**
- Consumes: nothing new.
- Produces (all in `relay/decisions/questions.py`):
  - `Q_V0_3 = "q-v0.3"`; `QUESTION_SET_VERSIONS == ("q-v0.1", "q-v0.2", "q-v0.3")`; `DEFAULT_QUESTION_SET_VERSION` stays `"q-v0.2"`.
  - `INTERRUPTION_QUESTION_IDS` (7 ids: `mtx_interrupted`, `mtx_pause_{month,day,year}`, `mtx_restart_{month,day,year}`), `QUESTION_IDS_V0_3 = QUESTION_IDS + INTERRUPTION_QUESTION_IDS` (19).
  - `question_ids(version: str) -> tuple[str, ...]`.
  - `build_questions(policy, years, "q-v0.3")` returns the 19 questions in that order. The q-v0.1 and q-v0.2 JSON (and hashes) are unchanged: q-v0.2 is pinned at `sha256:89717c795a2dfea7efe30e038fb483c6d4ed72d343bfbfcefeabfc6483d7a4aa`, the hash every committed q-v0.2 Jev trace carries.

- [ ] **Step 1: Write the failing tests**

In `tests/unit/test_questions.py`, replace:

```python
from relay.cases.policies import load_policy
from relay.decisions.questions import (
    DEFAULT_QUESTION_SET_VERSION,
    QUESTION_IDS,
    QUESTION_SET_VERSIONS,
    build_questions,
    candidate_years,
    question_set_hash,
)
from tests.factories import make_case_input
```

with:

```python
from relay.cases.policies import load_policy
from relay.decisions.questions import (
    DEFAULT_QUESTION_SET_VERSION,
    INTERRUPTION_QUESTION_IDS,
    QUESTION_IDS,
    QUESTION_IDS_V0_3,
    QUESTION_SET_VERSIONS,
    build_questions,
    candidate_years,
    question_ids,
    question_set_hash,
)
from tests.factories import make_case_input
```

In `tests/unit/test_questions.py`, replace:

```python


def test_known_versions_and_default():
    assert QUESTION_SET_VERSIONS == ("q-v0.1", "q-v0.2")
    # Adopted by the dev-only rule (spec §6); see evals/baselines/gen-v0.2-dev/adoption.txt.
    assert DEFAULT_QUESTION_SET_VERSION == "q-v0.2"
```

with:

```python


def test_known_versions_and_default():
    assert QUESTION_SET_VERSIONS == ("q-v0.1", "q-v0.2", "q-v0.3")
    # Adopted by the dev-only rule (spec §6); see evals/baselines/gen-v0.2-dev/adoption.txt.
    assert DEFAULT_QUESTION_SET_VERSION == "q-v0.2"
```

Append to the end of `tests/unit/test_questions.py`:

```python
# ---- Phase 3D: q-v0.3 (interrupted courses) ----

# The committed gold-v0.1 and gen-v0.2 q-v0.2 Jev traces carry exactly this hash.
Q_V0_2_HASH = "sha256:89717c795a2dfea7efe30e038fb483c6d4ed72d343bfbfcefeabfc6483d7a4aa"


def test_q_v0_2_hash_is_unchanged_by_q_v0_3():
    assert question_set_hash(POLICY, "q-v0.2") == Q_V0_2_HASH
    assert question_set_hash(POLICY, "q-v0.1") == Q_V0_1_HASH


def test_q_v0_3_has_nineteen_questions_in_a_fixed_order():
    questions = build_questions(POLICY, ["2026"], "q-v0.3")
    assert tuple(questions) == QUESTION_IDS_V0_3 == QUESTION_IDS + INTERRUPTION_QUESTION_IDS
    assert len(questions) == 19
    assert question_ids("q-v0.3") == QUESTION_IDS_V0_3
    assert question_ids("q-v0.2") == question_ids("q-v0.1") == QUESTION_IDS
    assert isinstance(questions["mtx_interrupted"], Noul)
    assert all(isinstance(questions[q], Choice) for q in INTERRUPTION_QUESTION_IDS[1:])


def test_question_ids_rejects_an_unknown_set():
    with pytest.raises(ValueError, match="unknown question set 'q-v9'"):
        question_ids("q-v9")


def test_q_v0_3_keeps_every_q_v0_2_question_except_the_first_and_last_time_wording():
    v2 = build_questions(POLICY, ["2025", "2026"], "q-v0.2")
    v3 = build_questions(POLICY, ["2025", "2026"], "q-v0.3")
    reworded = {
        "mtx_start_month",
        "mtx_start_day",
        "mtx_start_year",
        "mtx_end_status",
        "mtx_end_month",
        "mtx_end_day",
        "mtx_end_year",
    }
    for qid in QUESTION_IDS:
        if qid in reworded:
            assert v3[qid].criteria == v2[qid].criteria, qid
            assert v3[qid].instructions != v2[qid].instructions, qid
        else:
            assert v3[qid] == v2[qid], qid
    first = " (the first time, if it was restarted)"
    last = " (the last time, if it was restarted)"
    for qid in ("mtx_start_month", "mtx_start_day", "mtx_start_year"):
        assert v3[qid].instructions == v2[qid].instructions.replace(
            "taking methotrexate?", f"taking methotrexate{first}?"
        )
    for qid in ("mtx_end_month", "mtx_end_day", "mtx_end_year"):
        assert v3[qid].instructions == v2[qid].instructions.replace(
            "taking methotrexate?", f"taking methotrexate{last}?"
        )
    assert v3["mtx_end_status"].instructions == (
        f"What is the status of the patient's own methotrexate treatment (not a relative's){last}?"
    )


def test_q_v0_3_interruption_questions():
    q = build_questions(POLICY, ["2025", "2026"], "q-v0.3")
    assert q["mtx_interrupted"].instructions == (
        "Do the documents describe the patient's own methotrexate being held, paused or stopped "
        "and later restarted?"
    )
    criteria = q["mtx_interrupted"].criteria
    assert "resumed or restarted" in criteria["true"]
    assert "one continuous course" in criteria["false"] and "relative" in criteria["false"]
    assert q["mtx_pause_month"].instructions == (
        "In which month did the patient (not a relative or other person) first stop taking "
        "methotrexate before restarting it (a hold or pause counts as a stop)? Answer 'none' if "
        "the documents do not state the month, or if the course was never stopped and restarted."
    )
    assert q["mtx_restart_day"].instructions == (
        "On which day of the month (1-31) did the patient (not a relative or other person) "
        "restart taking methotrexate after a hold, pause or stop? Answer 'none' if the day is not "
        "stated, for example when only a month is given, or if the course was never stopped and "
        "restarted."
    )
    assert list(q["mtx_restart_year"].criteria) == ["2025", "2026", "none"]
    assert len(q["mtx_pause_day"].criteria) == 32
    assert "never held, paused or stopped" in q["mtx_pause_month"].criteria["none"]


def test_q_v0_3_hash_is_new_and_the_same_under_either_immunara_policy():
    v3 = question_set_hash(POLICY, "q-v0.3")
    assert v3 not in (Q_V0_1_HASH, Q_V0_2_HASH)
    assert question_set_hash(load_policy("immunara-v0.2"), "q-v0.3") == v3
    assert question_set_hash(load_policy("immunara-v0.2"), "q-v0.2") == Q_V0_2_HASH
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run: `uv run pytest -q tests/unit/test_questions.py`

Expected: FAIL. `ImportError: cannot import name 'INTERRUPTION_QUESTION_IDS'`.

- [ ] **Step 3: Implement**

In `relay/decisions/questions.py`, replace:

```python

q-v0.1 is the v0.1 milestone set. q-v0.2 changes only two criteria so that a record stating that
the patient never took the required drug counts as documented treatment history.
"""

import hashlib
```

with:

```python

q-v0.1 is the v0.1 milestone set. q-v0.2 changes only two criteria so that a record stating that
the patient never took the required drug counts as documented treatment history.

q-v0.3 (Phase 3D) keeps every q-v0.2 question and adds seven for an interrupted course: a Noul
(was the patient's own methotrexate held, paused or stopped and later restarted?) and the date
parts of the first stop (pause) and of the restart. Its start and end questions gain "(the first
time, if it was restarted)" and "(the last time, if it was restarted)": 19 questions.
"""

import hashlib
```

In `relay/decisions/questions.py`, replace:

```python

Q_V0_1 = "q-v0.1"
Q_V0_2 = "q-v0.2"
QUESTION_SET_VERSIONS: tuple[str, ...] = (Q_V0_1, Q_V0_2)
DEFAULT_QUESTION_SET_VERSION = Q_V0_2
QUESTION_IDS: tuple[str, ...] = (
    "diagnosis_support",
```

with:

```python

Q_V0_1 = "q-v0.1"
Q_V0_2 = "q-v0.2"
Q_V0_3 = "q-v0.3"
QUESTION_SET_VERSIONS: tuple[str, ...] = (Q_V0_1, Q_V0_2, Q_V0_3)
DEFAULT_QUESTION_SET_VERSION = Q_V0_2
QUESTION_IDS: tuple[str, ...] = (
    "diagnosis_support",
```

In `relay/decisions/questions.py`, replace:

```python
    "mtx_end_year",
    "mtx_inadequate_response",
)
_YEAR_PLACEHOLDER = "<case-specific years>"
_YEAR_RE = re.compile(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)")
_ABSENT = "The documents do not state this, or the patient never took the medication."


def candidate_years(case: CaseInput) -> list[str]:
```

with:

```python
    "mtx_end_year",
    "mtx_inadequate_response",
)
INTERRUPTION_QUESTION_IDS: tuple[str, ...] = (
    "mtx_interrupted",
    "mtx_pause_month",
    "mtx_pause_day",
    "mtx_pause_year",
    "mtx_restart_month",
    "mtx_restart_day",
    "mtx_restart_year",
)
QUESTION_IDS_V0_3: tuple[str, ...] = QUESTION_IDS + INTERRUPTION_QUESTION_IDS
_YEAR_PLACEHOLDER = "<case-specific years>"
_YEAR_RE = re.compile(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)")
_ABSENT = "The documents do not state this, or the patient never took the medication."
_NOT_INTERRUPTED = (
    "The documents do not state this, or the patient's course was never held, paused or stopped "
    "and then restarted."
)
_FIRST_TIME = " (the first time, if it was restarted)"
_LAST_TIME = " (the last time, if it was restarted)"


def candidate_years(case: CaseInput) -> list[str]:
```

In `relay/decisions/questions.py`, replace:

```python


def _date_part_questions(
    prefix: str, event: str, drug: str, years: Sequence[str]
) -> dict[str, Choice]:
    who = f"the patient (not a relative or other person) {event} taking {drug}"
    return {
        f"{prefix}_month": Choice(
            instructions=(
                f"In which month did {who}? Answer 'none' if the documents do not state the month."
            ),
            criteria={m: None for m in MONTHS} | {"none": _ABSENT},
        ),
        f"{prefix}_day": Choice(
            instructions=(
                f"On which day of the month (1-31) did {who}? Answer 'none' if the day is not "
                "stated, for example when only a month is given."
            ),
            criteria={str(d): None for d in range(1, 32)} | {"none": _ABSENT},
        ),
        f"{prefix}_year": Choice(
            instructions=(
                f"In which year did {who}? Answer 'none' if no year is stated for this event."
            ),
            criteria={y: None for y in years} | {"none": _ABSENT},
        ),
    }
```

with:

```python


def _date_part_questions(
    prefix: str,
    event: str,
    drug: str,
    years: Sequence[str],
    *,
    qualifier: str = "",
    none_also: str = "",
    absent: str = _ABSENT,
) -> dict[str, Choice]:
    """Month, day and year questions for one event. `qualifier` follows the drug name,
    `none_also` extends each "Answer 'none' if ..." clause; both are empty up to q-v0.2."""
    who = f"the patient (not a relative or other person) {event} taking {drug}{qualifier}"
    return {
        f"{prefix}_month": Choice(
            instructions=(
                f"In which month did {who}? Answer 'none' if the documents do not state the "
                f"month{none_also}."
            ),
            criteria={m: None for m in MONTHS} | {"none": absent},
        ),
        f"{prefix}_day": Choice(
            instructions=(
                f"On which day of the month (1-31) did {who}? Answer 'none' if the day is not "
                f"stated, for example when only a month is given{none_also}."
            ),
            criteria={str(d): None for d in range(1, 32)} | {"none": absent},
        ),
        f"{prefix}_year": Choice(
            instructions=(
                f"In which year did {who}? Answer 'none' if no year is stated for this "
                f"event{none_also}."
            ),
            criteria={y: None for y in years} | {"none": absent},
        ),
    }
```

In `relay/decisions/questions.py`, replace:

```python
        raise ValueError(f"unknown question set {version!r}; known: {list(QUESTION_SET_VERSIONS)}")


def _documentation_complete_true(drug: str, version: str) -> str:
    text = (
        "The insurance member ID, a clinician note supporting the diagnosis, and the patient's "
        f"treatment history (including whether and when {drug} was taken) are all present"
    )
    if version == Q_V0_2:
        text += f" (a statement that the patient never took {drug} counts as treatment history)"
    return text + "."


def _treatment_history_option(drug: str, version: str) -> str:
    if version == Q_V0_2:
        return (
            f"The records do not say whether or when the patient took {drug}. A record stating "
            f"that the patient never took {drug} counts as documented treatment history."
```

with:

```python
        raise ValueError(f"unknown question set {version!r}; known: {list(QUESTION_SET_VERSIONS)}")


def question_ids(version: str) -> tuple[str, ...]:
    """The question ids of a question set, in the order they are sent."""
    validate_question_set_version(version)
    return QUESTION_IDS_V0_3 if version == Q_V0_3 else QUESTION_IDS


def _never_taken_counts(version: str) -> bool:
    """From q-v0.2 on, a record that the patient never took the drug is treatment history."""
    return version in (Q_V0_2, Q_V0_3)


def _documentation_complete_true(drug: str, version: str) -> str:
    text = (
        "The insurance member ID, a clinician note supporting the diagnosis, and the patient's "
        f"treatment history (including whether and when {drug} was taken) are all present"
    )
    if _never_taken_counts(version):
        text += f" (a statement that the patient never took {drug} counts as treatment history)"
    return text + "."


def _treatment_history_option(drug: str, version: str) -> str:
    if _never_taken_counts(version):
        return (
            f"The records do not say whether or when the patient took {drug}. A record stating "
            f"that the patient never took {drug} counts as documented treatment history."
```

In `relay/decisions/questions.py`, replace:

```python
            },
        ),
    }
    questions |= _date_part_questions("mtx_start", "start", drug, years)
    questions["mtx_end_status"] = Choice(
        instructions=(
            f"What is the status of the patient's own {drug} treatment (not a relative's)?"
        ),
        criteria={
            "ended": f"The documents say the patient stopped taking {drug}.",
```

with:

```python
            },
        ),
    }
    v0_3 = version == Q_V0_3
    questions |= _date_part_questions(
        "mtx_start", "start", drug, years, qualifier=_FIRST_TIME if v0_3 else ""
    )
    questions["mtx_end_status"] = Choice(
        instructions=(
            f"What is the status of the patient's own {drug} treatment (not a relative's)"
            f"{_LAST_TIME if v0_3 else ''}?"
        ),
        criteria={
            "ended": f"The documents say the patient stopped taking {drug}.",
```

In `relay/decisions/questions.py`, replace:

```python
            "not_stated": f"The documents do not say, or the patient never took {drug}.",
        },
    )
    questions |= _date_part_questions("mtx_end", "stop", drug, years)
    questions["mtx_inadequate_response"] = Noul(
        instructions=(
            f"Is it documented that the patient's own {drug} treatment was ineffective "
```

with:

```python
            "not_stated": f"The documents do not say, or the patient never took {drug}.",
        },
    )
    questions |= _date_part_questions(
        "mtx_end", "stop", drug, years, qualifier=_LAST_TIME if v0_3 else ""
    )
    questions["mtx_inadequate_response"] = Noul(
        instructions=(
            f"Is it documented that the patient's own {drug} treatment was ineffective "
```

In `relay/decisions/questions.py`, replace:

```python
            "relatives or other people do not count, and neither does a different medication.",
        ),
    )
    return questions
```

with:

```python
            "relatives or other people do not count, and neither does a different medication.",
        ),
    )
    if v0_3:
        questions |= _interruption_questions(drug, years)
    return questions


def _interruption_questions(drug: str, years: Sequence[str]) -> dict[str, Noul | Choice]:
    """q-v0.3's seven additions: was the course interrupted, and when was it stopped and resumed."""
    questions: dict[str, Noul | Choice] = {
        "mtx_interrupted": Noul(
            instructions=(
                f"Do the documents describe the patient's own {drug} being held, paused or "
                "stopped and later restarted?"
            ),
            criteria=NoulCriteria(
                true=f"A clinical record states that the patient's own {drug} was held, paused "
                "or stopped, and that the patient later resumed or restarted it.",
                false=f"The patient took one continuous course, never took {drug}, or the hold "
                "and restart describe a relative or another person.",
            ),
        )
    }
    never_restarted = ", or if the course was never stopped and restarted"
    questions |= _date_part_questions(
        "mtx_pause",
        "first stop",
        drug,
        years,
        qualifier=" before restarting it (a hold or pause counts as a stop)",
        none_also=never_restarted,
        absent=_NOT_INTERRUPTED,
    )
    questions |= _date_part_questions(
        "mtx_restart",
        "restart",
        drug,
        years,
        qualifier=" after a hold, pause or stop",
        none_also=never_restarted,
        absent=_NOT_INTERRUPTED,
    )
    return questions
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run pytest -q tests/unit/test_questions.py`

Expected: PASS.

- [ ] **Step 5: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`

Expected: all pass (about 1104 passed).

- [ ] **Step 6: Commit**

```bash
git add relay/decisions/questions.py tests/unit/test_questions.py
git commit -m "feat: add question set q-v0.3 for interrupted methotrexate courses" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 4: Composition by question set, and Jev q-v0.3

**Files:**
- Modify: `relay/decisions/composition.py`
- Modify: `relay/decisions/jev.py`
- Test (create): `tests/jev_fakes.py`
- Test (modify): `tests/unit/test_composition.py`
- Test (modify): `tests/unit/test_jev_provider.py`

**Interfaces:**
- Consumes: `Q_V0_2`, `Q_V0_3`, `validate_question_set_version`, `QUESTION_IDS_V0_3` (Task 3); `p_consecutive_at_least`, `p_duration_at_least(..., max_days_since=...)` (Task 2); `AuthorizationPolicy.max_days_since_therapy` (Task 1).
- Produces:
  - `relay/decisions/composition.py`: `YES_NO_QUESTIONS_V0_3`, `CHOICE_QUESTIONS_V0_3`, `question_groups(version) -> tuple[tuple[str, ...], tuple[str, ...]]`, and `compose_decisions(answers, case, policy, provider, question_set_version: str = Q_V0_2)`. q-v0.1/q-v0.2 compose one course (with the policy's recency rule, None for v0.1); q-v0.3 composes consecutive segments. Claude's call site is unchanged (default q-v0.2).
  - `relay/decisions/jev.py`: `answer_set_from_raw(raw_answers: Mapping[str, Any], version: str) -> AnswerSet` (raises `MalformedAnswers`); `JevProvider(question_set_version="q-v0.3")` sends 19 questions and composes on the q-v0.3 path.
  - `tests/jev_fakes.py`: `raw_noul`, `raw_choice`, `raw_date`, `NOT_INTERRUPTED`, `q_v0_3_payload(**answers)`, `generic_answers(questions)`, `GenericSystemOneClient(base_tokens=1000, tokens_per_question=50, on_call=None)` (used by Tasks 5, 10 and 11).

- [ ] **Step 1: Write the failing tests**

Create `tests/jev_fakes.py`:

```python
"""Shared Jev test doubles: raw answer builders, q-v0.3 payloads and a generic fake client.

No network and no real key. Every value is synthetic.
"""

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from typesafe_sdk import Noul, SystemOneResponse

REPO = Path(__file__).resolve().parents[1]
AUTO01_FIXTURE = REPO / "tests" / "fixtures" / "jev" / "auto01_response.json"
DATE_PARTS = ("month", "day", "year")


def raw_noul(p_yes: float) -> dict[str, Any]:
    return {"type": "noul", "noul": p_yes}


def raw_choice(answer: str, probability: float = 1.0) -> dict[str, Any]:
    return {
        "type": "choice",
        "choice": answer,
        "confidence": probability,
        "probabilities": {answer: probability},
    }


def raw_date(prefix: str, month: str, day: str, year: str) -> dict[str, dict[str, Any]]:
    """Certain date-part answers, e.g. raw_date("mtx_pause", "February", "23", "2026")."""
    values = dict(zip(DATE_PARTS, (month, day, year), strict=True))
    return {f"{prefix}_{part}": raw_choice(values[part]) for part in DATE_PARTS}


# q-v0.3's seven extra answers for a course that was never interrupted.
NOT_INTERRUPTED: dict[str, dict[str, Any]] = {
    "mtx_interrupted": raw_noul(0.02),
    **raw_date("mtx_pause", "none", "none", "none"),
    **raw_date("mtx_restart", "none", "none", "none"),
}


def q_v0_3_payload(**answers: dict[str, Any]) -> dict[str, Any]:
    """The AUTO-01 fixture response (methotrexate 2026-01-12 -> 2026-06-01, ended, inadequate
    response) plus q-v0.3's interruption answers; keyword answers replace any answer by id."""
    payload = json.loads(AUTO01_FIXTURE.read_text())
    payload["answers"] = payload["answers"] | NOT_INTERRUPTED | answers
    return payload


def generic_answers(questions: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """A well-formed answer for any question set: 0.5 for a Noul, the first option otherwise."""
    return {
        qid: raw_noul(0.5) if isinstance(q, Noul) else raw_choice(next(iter(q.criteria)))
        for qid, q in questions.items()
    }


class GenericSystemOneClient:
    """Answers whatever questions it is sent. input_tokens = base + per_question * len(questions),
    so cost grows with the question count. `on_call(questions)` runs before each answer (a test
    uses it to advance a fake clock). Every call is recorded in `calls`."""

    def __init__(
        self,
        *,
        base_tokens: int = 1000,
        tokens_per_question: int = 50,
        on_call: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> None:
        self.base_tokens = base_tokens
        self.tokens_per_question = tokens_per_question
        self.on_call = on_call
        self.calls: list[dict[str, Any]] = []

    async def system_one(
        self, state: Any, questions: Mapping[str, Any], *, model: str | None = None, **kwargs: Any
    ) -> SystemOneResponse:
        self.calls.append({"state": state, "questions": dict(questions), "model": model})
        if self.on_call is not None:
            self.on_call(questions)
        tokens = self.base_tokens + self.tokens_per_question * len(questions)
        return SystemOneResponse.model_validate(
            {
                "model": model or "jev-1.13.0",
                "answers": generic_answers(questions),
                "usage": {"input_tokens": tokens, "output_tokens": 10},
            }
        )
```

In `tests/unit/test_composition.py`, replace:

```python
from relay.decisions.base import DecisionId
from relay.decisions.composition import (
    CHOICE_QUESTIONS,
    UNASSIGNED,
    YES_NO_QUESTIONS,
    AnswerSet,
    ChoiceResult,
    MalformedAnswers,
    compose_decisions,
    single_answer_distribution,
)
from relay.decisions.questions import QUESTION_IDS
from tests.factories import make_case_input

POLICY = load_policy("immunara-v0.1")
```

with:

```python
from relay.decisions.base import DecisionId
from relay.decisions.composition import (
    CHOICE_QUESTIONS,
    CHOICE_QUESTIONS_V0_3,
    UNASSIGNED,
    YES_NO_QUESTIONS,
    YES_NO_QUESTIONS_V0_3,
    AnswerSet,
    ChoiceResult,
    MalformedAnswers,
    compose_decisions,
    question_groups,
    single_answer_distribution,
)
from relay.decisions.questions import QUESTION_IDS, QUESTION_IDS_V0_3
from tests.factories import make_case_input

POLICY = load_policy("immunara-v0.1")
```

Append to the end of `tests/unit/test_composition.py`:

```python
# ---- Phase 3D: the q-v0.3 path, question groups and recency ----

POLICY_V2 = load_policy("immunara-v0.2")


def interrupted_answers(p_int, pause, restart, **overrides):
    """answers() plus q-v0.3's seven: pause and restart are (month, day, year) or None."""
    base = answers(**overrides)
    choices = dict(base.choices)
    for prefix, value in (("mtx_pause", pause), ("mtx_restart", restart)):
        for part, answer in zip(("month", "day", "year"), value or ("none",) * 3, strict=True):
            choices[f"{prefix}_{part}"] = certain(answer)
    return AnswerSet(yes_no=dict(base.yes_no) | {"mtx_interrupted": p_int}, choices=choices)


def compose_v3(answer_set, policy=POLICY):
    return compose_decisions(answer_set, CASE, policy, "test-provider", "q-v0.3")


def step_p(decisions):
    return next(d for d in decisions if d.question_id == DecisionId.STEP_THERAPY).p_yes


def test_question_groups_per_question_set():
    assert question_groups("q-v0.2") == question_groups("q-v0.1")
    assert question_groups("q-v0.2") == (YES_NO_QUESTIONS, CHOICE_QUESTIONS)
    yes_no, choices = question_groups("q-v0.3")
    assert sorted(yes_no + choices) == sorted(QUESTION_IDS_V0_3)
    assert (yes_no, choices) == (YES_NO_QUESTIONS_V0_3, CHOICE_QUESTIONS_V0_3)
    with pytest.raises(ValueError, match="unknown question set"):
        question_groups("q-v9")


def test_q_v0_3_path_reads_an_interruption_where_q_v0_2_cannot():
    # Jan 12 -> held Feb 23 (42 d), restarted Mar 23 -> Jun 1 (70 d): no segment reaches 84.
    answer_set = interrupted_answers(0.95, ("February", "23", "2026"), ("March", "23", "2026"))
    decisions, derivations = compose_v3(answer_set)
    step = derivations["step_therapy"]
    assert (step["p_continuous"], step["p_first_segment"], step["p_second_segment"]) == (
        1.0,
        0.0,
        0.0,
    )
    assert step["p_duration"] == pytest.approx(0.05)
    assert step_p(decisions) == pytest.approx(0.05 * 0.9)
    assert step["p_inadequate_response"] == 0.9
    # The q-v0.2 path ignores the extra answers and reads one 140-day course.
    q2_decisions, _ = compose(answer_set)
    assert step_p(q2_decisions) == pytest.approx(0.9)


def test_q_v0_3_path_equals_q_v0_2_when_certainly_not_interrupted():
    decisions, derivations = compose_v3(interrupted_answers(0.0, None, None))
    assert step_p(decisions) == pytest.approx(step_p(compose(answers())[0]))
    assert derivations["step_therapy"]["pause_candidates"] == []


@pytest.mark.parametrize("qid", YES_NO_QUESTIONS_V0_3 + CHOICE_QUESTIONS_V0_3)
def test_a_missing_q_v0_3_answer_is_malformed(qid):
    full = interrupted_answers(0.1, None, None)
    yes_no = {k: v for k, v in full.yes_no.items() if k != qid}
    choices = {k: v for k, v in full.choices.items() if k != qid}
    with pytest.raises(MalformedAnswers, match=qid):
        compose_v3(AnswerSet(yes_no=yes_no, choices=choices))


def test_an_unknown_question_set_is_rejected():
    with pytest.raises(ValueError, match="unknown question set"):
        compose_decisions(answers(), CASE, POLICY, "test-provider", "q-v9")


def old_course(**overrides):
    """Methotrexate 2025-01-13 -> 2025-06-02 (140 days), ended 470 days before 2026-09-15."""
    return {
        "mtx_start_year": certain("2025"),
        "mtx_start_day": certain("13"),
        "mtx_end_year": certain("2025"),
        "mtx_end_day": certain("2"),
        **overrides,
    }


def test_recency_applies_on_the_q_v0_2_path_under_immunara_v0_2():
    stale, stale_derivations = compose(answers(**old_course()))
    aware, aware_derivations = compose_decisions(
        answers(**old_course()), CASE, POLICY_V2, "test-provider"
    )
    assert step_p(stale) == pytest.approx(0.9)
    assert step_p(aware) == 0.0
    assert "max_days_since_therapy" not in stale_derivations["step_therapy"]
    assert aware_derivations["step_therapy"]["max_days_since_therapy"] == 365


def test_recency_applies_on_the_q_v0_3_path_under_immunara_v0_2():
    answer_set = interrupted_answers(0.02, None, None, **old_course())
    stale, stale_derivations = compose_v3(answer_set)
    aware, _ = compose_v3(answer_set, POLICY_V2)
    assert step_p(stale) == pytest.approx(0.98 * 0.9)
    assert step_p(aware) == 0.0
    assert stale_derivations["step_therapy"]["max_days_since_therapy"] is None
```

In `tests/unit/test_jev_provider.py`, replace:

```python
from relay.cases.loader import load_case
from relay.cases.policies import load_policy
from relay.decisions.base import DecisionId
from relay.decisions.jev import CLIENT_VERSION, JEV_MODEL, JevProvider, build_state
from relay.decisions.questions import (
    DEFAULT_QUESTION_SET_VERSION,
    QUESTION_IDS,
    question_set_hash,
)
from relay.workflow.engine import bundle_problem, determine_action
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1

REPO = Path(__file__).resolve().parents[2]
AUTO01 = load_case(REPO / "evals" / "smoke" / "AUTO-01")
```

with:

```python
from relay.cases.loader import load_case
from relay.cases.policies import load_policy
from relay.decisions.base import DecisionId
from relay.decisions.composition import MalformedAnswers
from relay.decisions.jev import (
    CLIENT_VERSION,
    JEV_MODEL,
    JevProvider,
    answer_set_from_raw,
    build_state,
)
from relay.decisions.questions import (
    DEFAULT_QUESTION_SET_VERSION,
    QUESTION_IDS,
    QUESTION_IDS_V0_3,
    question_set_hash,
)
from relay.workflow.engine import bundle_problem, determine_action
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1
from tests.jev_fakes import q_v0_3_payload, raw_date, raw_noul

REPO = Path(__file__).resolve().parents[2]
AUTO01 = load_case(REPO / "evals" / "smoke" / "AUTO-01")
```

Append to the end of `tests/unit/test_jev_provider.py`:

```python
# ---- Phase 3D: q-v0.3 over the wire, and rebuilding answers from a trace ----


async def decide_v3(payload):
    client = FakeClient(result=response(payload))
    bundle = await JevProvider(client, question_set_version="q-v0.3").decide(AUTO01.input)
    return bundle, client


async def test_q_v0_3_sends_nineteen_questions_and_records_the_version():
    bundle, client = await decide_v3(q_v0_3_payload())
    [call] = client.calls
    assert tuple(call["questions"]) == QUESTION_IDS_V0_3
    assert bundle.question_set_version == "q-v0.3"
    assert bundle.question_set_hash == question_set_hash(load_policy("immunara-v0.1"), "q-v0.3")
    assert set(bundle.raw_answers) == set(QUESTION_IDS_V0_3)
    assert bundle_problem(bundle) is None


async def test_q_v0_3_composes_the_interruption():
    # AUTO-01 fixture: 2026-01-12 -> 2026-06-01. Held 2026-02-23 (42 d), restarted 2026-03-23
    # (70 d to the end): certainly interrupted, so no segment reaches 12 weeks.
    payload = q_v0_3_payload(
        mtx_interrupted=raw_noul(1.0),
        **raw_date("mtx_pause", "February", "23", "2026"),
        **raw_date("mtx_restart", "March", "23", "2026"),
    )
    bundle, _ = await decide_v3(payload)
    assert bundle.get(DecisionId.STEP_THERAPY).p_yes == 0.0
    step = bundle.derivations["step_therapy"]
    # The fixture's start month is January at 0.99 (0.01 "none"), so the continuous reading
    # would be 0.99; the certain interruption replaces it with the two short segments.
    assert step["p_continuous"] == pytest.approx(0.99)
    assert (step["p_either_segment"], step["p_interrupted"]) == (0.0, 1.0)


async def test_a_q_v0_3_response_missing_an_interruption_answer_is_malformed():
    payload = q_v0_3_payload()
    del payload["answers"]["mtx_restart_day"]
    bundle, _ = await decide_v3(payload)
    assert bundle.error is not None and "mtx_restart_day" in bundle.error
    assert bundle.decisions == []


def test_answer_set_from_raw_rebuilds_what_decide_composed():
    raw = fixture_payload()["answers"]
    answers = answer_set_from_raw(raw, "q-v0.2")
    assert answers.yes_no["mtx_inadequate_response"] == 0.97
    start = answers.choices["mtx_start_month"]
    assert (start.answer, start.probabilities, start.confidence) == (
        "January",
        {"January": 0.99, "none": 0.01},
        0.98,
    )


def test_answer_set_from_raw_refuses_missing_or_garbled_answers():
    raw = fixture_payload()["answers"]
    with pytest.raises(MalformedAnswers, match="mtx_pause_month"):
        answer_set_from_raw(raw, "q-v0.3")
    garbled = raw | {"diagnosis_support": {"type": "noul", "noul": "high"}}
    with pytest.raises(MalformedAnswers):
        answer_set_from_raw(garbled, "q-v0.2")
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run: `uv run pytest -q tests/unit/test_composition.py tests/unit/test_jev_provider.py`

Expected: FAIL. `ImportError: cannot import name 'CHOICE_QUESTIONS_V0_3'` in `test_composition.py` and `cannot import name 'answer_set_from_raw'` in `test_jev_provider.py`.

- [ ] **Step 3: Implement**

In `relay/decisions/composition.py`, replace:

```python
"""Provider-neutral composition: 12 narrow answers -> the five decisions the policy engine reads.

Jev and Claude answer the same questions. Each adapter maps its own response into an AnswerSet;
compose_decisions validates it, composes step therapy from the date parts in code
(step_therapy.py), and builds the decisions. Only the judgment source differs between providers.
"""

import math
```

with:

```python
"""Provider-neutral composition: narrow answers -> the five decisions the policy engine reads.

Jev and Claude answer the same questions. Each adapter maps its own response into an AnswerSet;
compose_decisions validates it, composes step therapy from the date parts in code
(step_therapy.py), and builds the decisions. Only the judgment source differs between providers.

The question set selects the step-therapy path: q-v0.1/q-v0.2 (12 answers) compose one course,
first start -> final end; q-v0.3 (19 answers) composes P(some consecutive segment >= N) from the
interruption answers as well. A policy recency rule (immunara-v0.2) applies on both paths.
"""

import math
```

In `relay/decisions/composition.py`, replace:

```python
from relay.cases.models import CaseInput, MissingEvidence
from relay.cases.policies import AuthorizationPolicy
from relay.decisions.base import Decision, DecisionId
from relay.decisions.step_therapy import DateParts, p_duration_at_least

YES_NO_QUESTIONS: tuple[str, ...] = (
    "diagnosis_support",
```

with:

```python
from relay.cases.models import CaseInput, MissingEvidence
from relay.cases.policies import AuthorizationPolicy
from relay.decisions.base import Decision, DecisionId
from relay.decisions.questions import Q_V0_2, Q_V0_3, validate_question_set_version
from relay.decisions.step_therapy import DateParts, p_consecutive_at_least, p_duration_at_least

YES_NO_QUESTIONS: tuple[str, ...] = (
    "diagnosis_support",
```

In `relay/decisions/composition.py`, replace:

```python
    "mtx_end_month",
    "mtx_end_day",
    "mtx_end_year",
)
MISSING_EVIDENCE_LABELS: tuple[str, ...] = tuple(m.value for m in MissingEvidence)
# Probability mass a provider assigned to no option (2D spec L4). It is not a month, day, year or
```

with:

```python
    "mtx_end_month",
    "mtx_end_day",
    "mtx_end_year",
)
YES_NO_QUESTIONS_V0_3: tuple[str, ...] = (*YES_NO_QUESTIONS, "mtx_interrupted")
CHOICE_QUESTIONS_V0_3: tuple[str, ...] = (
    *CHOICE_QUESTIONS,
    "mtx_pause_month",
    "mtx_pause_day",
    "mtx_pause_year",
    "mtx_restart_month",
    "mtx_restart_day",
    "mtx_restart_year",
)
MISSING_EVIDENCE_LABELS: tuple[str, ...] = tuple(m.value for m in MissingEvidence)
# Probability mass a provider assigned to no option (2D spec L4). It is not a month, day, year or
```

In `relay/decisions/composition.py`, replace:

```python
    return result


def _date_parts(answers: AnswerSet, prefix: str) -> DateParts:
    return DateParts(
        month=_choice(answers, f"{prefix}_month").probabilities,
```

with:

```python
    return result


def question_groups(version: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(yes/no question ids, choice question ids) that a question set's AnswerSet must hold."""
    validate_question_set_version(version)
    if version == Q_V0_3:
        return YES_NO_QUESTIONS_V0_3, CHOICE_QUESTIONS_V0_3
    return YES_NO_QUESTIONS, CHOICE_QUESTIONS


def _date_parts(answers: AnswerSet, prefix: str) -> DateParts:
    return DateParts(
        month=_choice(answers, f"{prefix}_month").probabilities,
```

In `relay/decisions/composition.py`, replace:

```python
    )


def compose_decisions(
    answers: AnswerSet, case: CaseInput, policy: AuthorizationPolicy, provider: str
) -> tuple[list[Decision], dict[str, Any]]:
    """The five decisions plus derivations["step_therapy"]. Raises MalformedAnswers."""
    missing = _choice(answers, "missing_evidence")
    if missing.answer not in MISSING_EVIDENCE_LABELS:
        raise MalformedAnswers(f"missing_evidence: unknown label {missing.answer!r}")
    if missing.answer not in missing.probabilities:
        raise MalformedAnswers(f"missing_evidence: answer {missing.answer!r} has no probability")
    duration = p_duration_at_least(
        start=_date_parts(answers, "mtx_start"),
        end_status=_choice(answers, "mtx_end_status").probabilities,
        end=_date_parts(answers, "mtx_end"),
        as_of=case.as_of_date,
        min_days=policy.min_weeks * 7,
    )
    p_inadequate = _p_yes(answers, "mtx_inadequate_response")
    p_step = duration.p_duration * p_inadequate
    decisions = [
        Decision.yes_no(
            DecisionId.DIAGNOSIS_SUPPORT, _p_yes(answers, "diagnosis_support"), provider
```

with:

```python
    )


def _duration(
    answers: AnswerSet, case: CaseInput, policy: AuthorizationPolicy, version: str
) -> tuple[float, dict[str, Any]]:
    """P(duration requirement met) and its derivation, on the question set's path."""
    common: dict[str, Any] = {
        "start": _date_parts(answers, "mtx_start"),
        "end_status": _choice(answers, "mtx_end_status").probabilities,
        "end": _date_parts(answers, "mtx_end"),
        "as_of": case.as_of_date,
        "min_days": policy.min_weeks * 7,
        "max_days_since": policy.max_days_since_therapy,
    }
    if version == Q_V0_3:
        segments = p_consecutive_at_least(
            pause=_date_parts(answers, "mtx_pause"),
            restart=_date_parts(answers, "mtx_restart"),
            p_interrupted=_p_yes(answers, "mtx_interrupted"),
            **common,
        )
        return segments.p_duration, segments.to_dict()
    duration = p_duration_at_least(**common)
    return duration.p_duration, duration.to_dict()


def compose_decisions(
    answers: AnswerSet,
    case: CaseInput,
    policy: AuthorizationPolicy,
    provider: str,
    question_set_version: str = Q_V0_2,
) -> tuple[list[Decision], dict[str, Any]]:
    """The five decisions plus derivations["step_therapy"]. Raises MalformedAnswers."""
    validate_question_set_version(question_set_version)
    missing = _choice(answers, "missing_evidence")
    if missing.answer not in MISSING_EVIDENCE_LABELS:
        raise MalformedAnswers(f"missing_evidence: unknown label {missing.answer!r}")
    if missing.answer not in missing.probabilities:
        raise MalformedAnswers(f"missing_evidence: answer {missing.answer!r} has no probability")
    p_duration, duration = _duration(answers, case, policy, question_set_version)
    p_inadequate = _p_yes(answers, "mtx_inadequate_response")
    p_step = p_duration * p_inadequate
    decisions = [
        Decision.yes_no(
            DecisionId.DIAGNOSIS_SUPPORT, _p_yes(answers, "diagnosis_support"), provider
```

In `relay/decisions/composition.py`, replace:

```python
    ]
    derivations = {
        "step_therapy": {
            **duration.to_dict(),
            "p_inadequate_response": p_inadequate,
            "p_yes": p_step,
        }
```

with:

```python
    ]
    derivations = {
        "step_therapy": {
            **duration,
            "p_inadequate_response": p_inadequate,
            "p_yes": p_step,
        }
```

In `relay/decisions/jev.py`, replace:

```python
"""Jev decision provider: one TypeSafe System One call per case, 12 typed questions.

Jev answers narrow questions; this adapter maps them into an AnswerSet, and composition.py turns
that into the five decisions the policy engine consumes (step_therapy is composed in code from
the date-part answers, see step_therapy.py).
"""

import math
```

with:

```python
"""Jev decision provider: one TypeSafe System One call per case, 12 or 19 typed questions.

Jev answers narrow questions; this adapter maps them into an AnswerSet, and composition.py turns
that into the five decisions the policy engine consumes (step_therapy is composed in code from
the date-part answers, see step_therapy.py). answer_set_from_raw rebuilds the same AnswerSet from
a trace's stored raw_answers, for recomposition without a call.
"""

import math
```

In `relay/decisions/jev.py`, replace:

```python
from importlib.metadata import version
from typing import Any, Protocol

from pydantic import ValidationError
from typesafe_sdk import ChoiceAnswer, NoulAnswer, SystemOneResponse, TypeSafeError

from relay.cases.models import CaseInput
from relay.cases.policies import AuthorizationPolicy, load_policy
from relay.decisions.base import DecisionBundle
from relay.decisions.composition import (
    CHOICE_QUESTIONS,
    YES_NO_QUESTIONS,
    AnswerSet,
    ChoiceResult,
    MalformedAnswers,
    compose_decisions,
)
from relay.decisions.questions import (
    DEFAULT_QUESTION_SET_VERSION,
```

with:

```python
from importlib.metadata import version
from typing import Any, Protocol

from pydantic import TypeAdapter, ValidationError
from typesafe_sdk import Answer, ChoiceAnswer, NoulAnswer, SystemOneResponse, TypeSafeError

from relay.cases.models import CaseInput
from relay.cases.policies import AuthorizationPolicy, load_policy
from relay.decisions.base import DecisionBundle
from relay.decisions.composition import (
    AnswerSet,
    ChoiceResult,
    MalformedAnswers,
    compose_decisions,
    question_groups,
)
from relay.decisions.questions import (
    DEFAULT_QUESTION_SET_VERSION,
```

In `relay/decisions/jev.py`, replace:

```python
    pass


def build_state(case: CaseInput, policy: AuthorizationPolicy) -> dict[str, Any]:
    return {
        "policy": policy.text,
```

with:

```python
    pass


_ANSWER = TypeAdapter(Answer)


def build_state(case: CaseInput, policy: AuthorizationPolicy) -> dict[str, Any]:
    return {
        "policy": policy.text,
```

In `relay/decisions/jev.py`, replace:

```python
    }


def _noul(response: SystemOneResponse, qid: str) -> float:
    answer = response.answers.get(qid)
    if not isinstance(answer, NoulAnswer):
        raise _MalformedResponse(f"{qid}: expected noul answer, got {type(answer).__name__}")
    value = answer.noul
```

with:

```python
    }


def _noul(answers: Mapping[str, Any], qid: str) -> float:
    answer = answers.get(qid)
    if not isinstance(answer, NoulAnswer):
        raise _MalformedResponse(f"{qid}: expected noul answer, got {type(answer).__name__}")
    value = answer.noul
```

In `relay/decisions/jev.py`, replace:

```python
    return value


def _choice(response: SystemOneResponse, qid: str) -> ChoiceAnswer:
    answer = response.answers.get(qid)
    if not isinstance(answer, ChoiceAnswer):
        raise _MalformedResponse(f"{qid}: expected choice answer, got {type(answer).__name__}")
    for label, probability in answer.probabilities.items():
```

with:

```python
    return value


def _choice(answers: Mapping[str, Any], qid: str) -> ChoiceAnswer:
    answer = answers.get(qid)
    if not isinstance(answer, ChoiceAnswer):
        raise _MalformedResponse(f"{qid}: expected choice answer, got {type(answer).__name__}")
    for label, probability in answer.probabilities.items():
```

In `relay/decisions/jev.py`, replace:

```python
    return answer


def _answer_set(response: SystemOneResponse) -> AnswerSet:
    choices = {}
    for qid in CHOICE_QUESTIONS:
        answer = _choice(response, qid)
        choices[qid] = ChoiceResult(answer.choice, answer.probabilities, answer.confidence)
    return AnswerSet(
        yes_no={qid: _noul(response, qid) for qid in YES_NO_QUESTIONS}, choices=choices
    )


class JevProvider:
```

with:

```python
    return answer


def _answer_set(answers: Mapping[str, Any], version: str) -> AnswerSet:
    yes_no_ids, choice_ids = question_groups(version)
    choices = {}
    for qid in choice_ids:
        answer = _choice(answers, qid)
        choices[qid] = ChoiceResult(answer.choice, answer.probabilities, answer.confidence)
    return AnswerSet(yes_no={qid: _noul(answers, qid) for qid in yes_no_ids}, choices=choices)


def answer_set_from_raw(raw_answers: Mapping[str, Any], version: str) -> AnswerSet:
    """The AnswerSet a Jev call's stored raw_answers held (the same one decide() composed).

    Raises MalformedAnswers if an answer is missing, unparseable or out of range.
    """
    try:
        parsed = {qid: _ANSWER.validate_python(raw) for qid, raw in raw_answers.items()}
        return _answer_set(parsed, version)
    except (ValidationError, _MalformedResponse) as error:
        raise MalformedAnswers(str(error)) from error


class JevProvider:
```

In `relay/decisions/jev.py`, replace:

```python
        }
        try:
            decisions, derivations = compose_decisions(
                _answer_set(response), case, policy, PROVIDER_NAME
            )
        except (_MalformedResponse, MalformedAnswers, ValidationError) as error:
            return DecisionBundle(**common, error=f"malformed response: {error}")
```

with:

```python
        }
        try:
            decisions, derivations = compose_decisions(
                _answer_set(response.answers, version), case, policy, PROVIDER_NAME, version
            )
        except (_MalformedResponse, MalformedAnswers, ValidationError) as error:
            return DecisionBundle(**common, error=f"malformed response: {error}")
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run pytest -q tests/unit/test_composition.py tests/unit/test_jev_provider.py`

Expected: PASS.

- [ ] **Step 5: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`

Expected: all pass (about 1134 passed).

- [ ] **Step 6: Commit**

```bash
git add relay/decisions/composition.py relay/decisions/jev.py tests/jev_fakes.py tests/unit/test_composition.py tests/unit/test_jev_provider.py
git commit -m "feat: compose step therapy by question set and run Jev with q-v0.3" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 5: `recompose()` and the q-v0.2 golden test

**Files:**
- Create: `relay/decisions/recompose.py`
- Test (create): `tests/unit/test_recompose.py`

**Interfaces:**
- Consumes: `answer_set_from_raw`, `PROVIDER_NAME` (`relay.decisions.jev`), `compose_decisions(..., question_set_version)` (Task 4); `q_v0_3_payload`, `raw_date` (`tests/jev_fakes.py`, Task 4).
- Produces: `relay.decisions.recompose.recompose(bundle: DecisionBundle, *, case: CaseInput, policy: AuthorizationPolicy, question_set_version: str) -> DecisionBundle`. Only `decisions` and `derivations` change. Error bundles are returned unchanged. ValueError for a non-Jev bundle, another case, or a question set that is not the bundle's own.

The golden test is the guard that the q-v0.2 path is unchanged: every committed q-v0.2 (and q-v0.1) Jev trace, recomposed under its own policy (immunara-v0.1) and question set, must equal its stored decisions and derivations, with step_therapy `p_yes` equal to 1e-9. The gold run is always on disk. The three gen-v0.2 runs are checked when `evals/generated/gen-v0.2-{dev,holdout}` exist (they do in this checkout; the test skips otherwise). During planning this held for all 1,910 committed Jev traces (max |Δp| = 0, zero mismatches).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_recompose.py`:

```python
"""recompose: a Jev bundle's step_therapy rebuilt from its stored raw answers under a policy."""

from decimal import Decimal
from pathlib import Path

import pytest
from typesafe_sdk import SystemOneResponse

from relay.cases.loader import load_dataset
from relay.cases.policies import load_policy
from relay.decisions.base import DecisionId
from relay.decisions.composition import MalformedAnswers
from relay.decisions.jev import JevProvider
from relay.decisions.recompose import recompose
from relay.traces.store import read_traces
from tests.factories import make_bundle, make_case_input
from tests.jev_fakes import q_v0_3_payload, raw_date

REPO = Path(__file__).resolve().parents[2]
GOLD = REPO / "evals" / "gold"
GOLD_JEV = REPO / "evals" / "baselines" / "gold-v0.1" / "run_20260925T170857Z_b95be9"
GENERATED = REPO / "evals" / "generated"
GEN_V0_2_JEV_RUNS = [
    ("gen-v0.2-dev", "run_20260925T071157Z_d6b218"),  # q-v0.1
    ("gen-v0.2-dev", "run_20260925T071231Z_6f0b73"),  # q-v0.2
    ("gen-v0.2-holdout", "run_20260925T075242Z_fd455f"),  # q-v0.2
]
V1, V2 = load_policy("immunara-v0.1"), load_policy("immunara-v0.2")


class OneAnswerClient:
    def __init__(self, payload):
        self.payload = payload

    async def system_one(self, state, questions, *, model=None, **kwargs):
        return SystemOneResponse.model_validate(self.payload)


def old_course_payload():
    """Methotrexate 2025-01-13 -> 2025-06-02 (140 days), ended 470 days before the 2026-09-15
    as-of date; inadequate response 0.97; not interrupted."""
    return q_v0_3_payload(
        **raw_date("mtx_start", "January", "13", "2025"),
        **raw_date("mtx_end", "June", "2", "2025"),
    )


async def jev_bundle(payload, version="q-v0.3"):
    case = make_case_input(documents=None)
    provider = JevProvider(OneAnswerClient(payload), question_set_version=version)
    return case, await provider.decide(case)


def step(bundle):
    return bundle.get(DecisionId.STEP_THERAPY).p_yes


async def test_stale_and_aware_from_the_same_bundle():
    case, bundle = await jev_bundle(old_course_payload())
    stale = recompose(bundle, case=case, policy=V1, question_set_version="q-v0.3")
    aware = recompose(bundle, case=case, policy=V2, question_set_version="q-v0.3")
    assert step(stale) == pytest.approx(0.98 * 0.97)
    assert step(aware) == 0.0
    assert aware.derivations["step_therapy"]["max_days_since_therapy"] == 365
    assert stale.derivations["step_therapy"]["max_days_since_therapy"] is None
    for other in (DecisionId.DIAGNOSIS_SUPPORT, DecisionId.MISSING_EVIDENCE):
        assert stale.get(other) == aware.get(other) == bundle.get(other)
    # Only decisions and derivations change; the call's record is kept.
    keep = {"raw_answers", "latency_ms", "input_tokens", "estimated_cost_usd", "question_set_hash"}
    assert stale.model_dump(include=keep) == aware.model_dump(include=keep)
    assert stale.model_dump(include=keep) == bundle.model_dump(include=keep)


async def test_recompose_under_the_bundles_own_policy_is_the_identity():
    case, bundle = await jev_bundle(old_course_payload())
    assert recompose(bundle, case=case, policy=V1, question_set_version="q-v0.3") == bundle


async def test_a_mismatched_question_set_or_case_is_refused():
    case, bundle = await jev_bundle(old_course_payload())
    with pytest.raises(ValueError, match="answered with q-v0.3, not q-v0.2"):
        recompose(bundle, case=case, policy=V1, question_set_version="q-v0.2")
    with pytest.raises(ValueError, match="bundle is for case T-01, not T-02"):
        recompose(bundle, case=make_case_input("T-02"), policy=V1, question_set_version="q-v0.3")


def test_only_jev_bundles_can_be_recomposed():
    bundle = make_bundle(provider="rules")
    with pytest.raises(ValueError, match="only Jev bundles"):
        recompose(bundle, case=make_case_input(), policy=V1, question_set_version="q-v0.2")


def test_an_error_bundle_is_returned_unchanged():
    bundle = make_bundle(provider="jev", error="TypeSafeAPIError: boom").model_copy(
        update={"question_set_version": "q-v0.2", "decisions": []}
    )
    assert (
        recompose(bundle, case=make_case_input(), policy=V2, question_set_version="q-v0.2")
        is bundle
    )


def test_unusable_raw_answers_are_malformed():
    bundle = make_bundle(provider="jev", cost=Decimal("0")).model_copy(
        update={"question_set_version": "q-v0.2", "raw_answers": {}}
    )
    with pytest.raises(MalformedAnswers):
        recompose(bundle, case=make_case_input(), policy=V1, question_set_version="q-v0.2")


def assert_recomposes_to_itself(trace_file, cases):
    """Golden: every committed Jev trace, recomposed under its own policy and question set,
    equals its stored decisions and derivations (step_therapy p_yes to 1e-9)."""
    by_id = {c.input.id: c.input for c in cases}
    traces = read_traces(trace_file)
    assert traces and {t.provider for t in traces} == {"jev"}
    for trace in traces:
        stored = trace.decisions
        again = recompose(
            stored,
            case=by_id[trace.case_id],
            policy=load_policy(trace.policy_id),
            question_set_version=stored.question_set_version,
        )
        assert step(again) == pytest.approx(step(stored), abs=1e-9), trace.case_id
        assert again.decisions == stored.decisions, trace.case_id
        assert again.derivations == stored.derivations, trace.case_id


def test_golden_committed_gold_q_v0_2_jev_traces_recompose_unchanged():
    assert_recomposes_to_itself(GOLD_JEV / "traces.jsonl.gz", load_dataset(GOLD))


@pytest.mark.parametrize("dataset_id,run", GEN_V0_2_JEV_RUNS, ids=[r for _, r in GEN_V0_2_JEV_RUNS])
def test_golden_committed_gen_v0_2_jev_traces_recompose_unchanged(dataset_id, run):
    dataset = GENERATED / dataset_id
    if not dataset.is_dir():
        pytest.skip(f"{dataset} is not generated; run relay generate to create it")
    trace_file = REPO / "evals" / "baselines" / dataset_id / run / "traces.jsonl.gz"
    assert_recomposes_to_itself(trace_file, load_dataset(dataset))
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run: `uv run pytest -q tests/unit/test_recompose.py`

Expected: FAIL. `ModuleNotFoundError: No module named 'relay.decisions.recompose'`.

- [ ] **Step 3: Implement**

Create `relay/decisions/recompose.py`:

```python
"""Recompose a Jev bundle's step_therapy from its stored raw answers, under another policy.

No provider is called. The raw answers a Jev call returned are parsed back into the AnswerSet
decide() composed, then composed again under `policy`. The policy-shift experiment uses this to
build its stale (immunara-v0.1) and aware (immunara-v0.2) runs from one paid run.
"""

from relay.cases.models import CaseInput
from relay.cases.policies import AuthorizationPolicy
from relay.decisions.base import DecisionBundle
from relay.decisions.composition import compose_decisions
from relay.decisions.jev import PROVIDER_NAME, answer_set_from_raw


def recompose(
    bundle: DecisionBundle,
    *,
    case: CaseInput,
    policy: AuthorizationPolicy,
    question_set_version: str,
) -> DecisionBundle:
    """`bundle` with its decisions and derivations recomposed under `policy`.

    `question_set_version` must be the bundle's own: it names the composition path, and a
    mismatch is a ValueError rather than a silent reinterpretation of the answers. A bundle that
    carries a provider error is returned unchanged: there is nothing to recompose, and the engine
    still routes it to human review. Everything else (raw answers, latency, tokens, cost) is kept,
    because it describes the one Jev call whose answers are reused. Raises ValueError for a
    non-Jev bundle or another case, and MalformedAnswers if the stored answers are unusable.
    """
    if bundle.provider != PROVIDER_NAME:
        raise ValueError(f"only Jev bundles can be recomposed, not provider {bundle.provider!r}")
    if bundle.case_id != case.id:
        raise ValueError(f"bundle is for case {bundle.case_id}, not {case.id}")
    if question_set_version != bundle.question_set_version:
        raise ValueError(
            f"{case.id}: bundle was answered with {bundle.question_set_version}, "
            f"not {question_set_version}"
        )
    if bundle.error is not None:
        return bundle
    answers = answer_set_from_raw(bundle.raw_answers, question_set_version)
    decisions, derivations = compose_decisions(
        answers, case, policy, PROVIDER_NAME, question_set_version
    )
    return bundle.model_copy(update={"decisions": decisions, "derivations": derivations})
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run pytest -q tests/unit/test_recompose.py`

Expected: PASS.

- [ ] **Step 5: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`

Expected: all pass (about 1144 passed).

- [ ] **Step 6: Commit**

```bash
git add relay/decisions/recompose.py tests/unit/test_recompose.py
git commit -m "feat: recompose a Jev bundle's step therapy from its stored raw answers" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 6: Generator facts and policy-aware labels (rule D8, recency)

**Files:**
- Modify: `relay/generation/facts.py`
- Modify: `relay/generation/labels.py`
- Test (modify): `tests/unit/test_generation_labels.py`

**Interfaces:**
- Consumes: `load_policy`, `AuthorizationPolicy.max_days_since_therapy` (Task 1).
- Produces:
  - `relay/generation/facts.py`: `GEN_V0_2 = GENERATOR_VERSION = "gen-v0.2"` (unchanged default), `GEN_V0_3 = "gen-v0.3"`, `GENERATOR_VERSIONS`, `InterruptionVariant = Literal["a","b","c"]`, `InterruptionReason = Literal["infection","surgery","travel","lab"]`, and four defaulted `CaseFacts` fields: `generator_version`, `mtx_segments: tuple[tuple[date, date | None], ...] | None`, `interruption_variant`, `interruption_reason`.
  - `relay/generation/labels.py`: `label_case(facts, policy: AuthorizationPolicy | None = None)` (default immunara-v0.1), `segment_days(facts) -> tuple[int, ...]`, `days_since_end(facts) -> int | None`, `duration_satisfied(facts, policy) -> bool`.

Every new `CaseFacts` field has a default, so gen-v0.2 facts (and the `make_facts()` test factory) are unchanged. For gen-v0.2 facts `label_case(facts)` gives exactly the old ground truth, including `notes`, so gen-v0.2 datasets stay byte-identical (checked in Step 5).

- [ ] **Step 1: Write the failing tests**

In `tests/unit/test_generation_labels.py`, replace:

```python
from relay.cases.models import MissingEvidence
from relay.cases.policies import load_policy
from relay.evaluation.labels import expected_action
from relay.generation.labels import MIN_DAYS, conservative_days, label_case
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1
from tests.factories import make_case, make_facts
```

with:

```python
from relay.cases.models import MissingEvidence
from relay.cases.policies import load_policy
from relay.evaluation.labels import expected_action
from relay.generation.labels import (
    MIN_DAYS,
    conservative_days,
    days_since_end,
    label_case,
    segment_days,
)
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1
from tests.factories import make_case, make_facts
```

Append to the end of `tests/unit/test_generation_labels.py`:

```python
# ---- Phase 3D: rule D8 (interrupted courses) and immunara-v0.2 recency ----

V1, V2 = load_policy("immunara-v0.1"), load_policy("immunara-v0.2")


def interrupted(first, second, variant, **overrides):
    """A gen-v0.3 interrupted course; `first`/`second` are (start, end) with end None = ongoing."""
    values = {
        "generator_version": "gen-v0.3",
        "mtx_segments": (first, second),
        "mtx_start": first[0],
        "mtx_end": second[1],
        "end_precision": None if second[1] is None else "day",
        "interruption_variant": variant,
        "interruption_reason": "infection",
    }
    return make_facts(**(values | overrides))


# GOLD-TMP-17 shape: 2026-01-05 -> 2026-02-23 (49 d), held, 2026-03-23 -> 2026-05-18 (56 d).
TMP_17 = interrupted(
    (date(2026, 1, 5), date(2026, 2, 23)), (date(2026, 3, 23), date(2026, 5, 18)), "a"
)
# GOLD-TMP-18 shape: 2025-10-06 -> 2025-11-03 (28 d), 2026-01-12 -> 2026-05-04 (112 d).
TMP_18 = interrupted(
    (date(2025, 10, 6), date(2025, 11, 3)), (date(2026, 1, 12), date(2026, 5, 4)), "b"
)
# Pattern (c): 2026-01-05 -> 2026-05-04 (119 d), 2026-06-01 -> 2026-07-06 (35 d).
EARLIER = interrupted(
    (date(2026, 1, 5), date(2026, 5, 4)), (date(2026, 6, 1), date(2026, 7, 6)), "c"
)


def test_d8_tmp_17_pattern_is_not_satisfied_although_the_span_is_133_days():
    assert segment_days(TMP_17) == (49, 56)
    assert conservative_days(TMP_17) == 133
    assert not label_case(TMP_17).step_therapy_satisfied
    assert action_for(TMP_17) is WorkflowAction.HUMAN_REVIEW


def test_d8_a_single_qualifying_segment_satisfies_either_way_round():
    assert segment_days(TMP_18) == (28, 112)
    assert segment_days(EARLIER) == (119, 35)
    for facts in (TMP_18, EARLIER):
        assert label_case(facts).step_therapy_satisfied
        assert action_for(facts) is WorkflowAction.AUTO_PROCESS


def test_d8_still_needs_a_qualifying_outcome():
    assert not label_case(
        interrupted(TMP_18.mtx_segments[0], TMP_18.mtx_segments[1], "b", mtx_outcome="not_stated")
    ).step_therapy_satisfied


def test_d8_an_ongoing_later_segment_counts_to_as_of():
    facts = interrupted(
        (date(2026, 1, 5), date(2026, 2, 2)), (date(2026, 5, 4), None), "b"
    )  # 28 d, then 2026-05-04 -> 2026-09-15 = 134 d
    assert segment_days(facts) == (28, 134)
    assert label_case(facts).step_therapy_satisfied


def test_interrupted_notes_name_the_segments_and_pattern():
    notes = label_case(TMP_17).notes
    assert notes.startswith("gen-v0.3 easy: mtx taken interrupted (infection, pattern a):")
    assert "segments 49d and 56d, inadequate_response" in notes


def test_v0_1_and_v0_2_labels_agree_for_a_recent_course():
    facts = make_facts()  # ended 2026-06-01, 106 days before 2026-09-15
    assert days_since_end(facts) == 106
    assert label_case(facts, V1) == label_case(facts, V2) == label_case(facts)


def test_recency_fails_a_course_that_ended_more_than_365_days_before_as_of():
    old = make_facts(mtx_start=date(2025, 1, 13), mtx_end=date(2025, 6, 2))  # 140 d
    assert days_since_end(old) == 470
    assert label_case(old, V1).step_therapy_satisfied
    assert not label_case(old, V2).step_therapy_satisfied
    edge = make_facts(mtx_start=date(2025, 4, 1), mtx_end=date(2025, 9, 15))
    assert days_since_end(edge) == 365
    assert label_case(edge, V2).step_therapy_satisfied


def test_recency_uses_the_conservative_end_of_a_month_only_date():
    # "September 2025" ends at the earliest 2025-09-01: 379 days before 2026-09-15.
    facts = make_facts(mtx_start=date(2025, 3, 3), mtx_end=date(2025, 9, 20), end_precision="month")
    assert days_since_end(facts) == 379
    assert label_case(facts, V1).step_therapy_satisfied
    assert not label_case(facts, V2).step_therapy_satisfied


def test_recency_applies_to_the_qualifying_segment_not_the_last_one():
    # The earlier segment qualifies (119 d) but ended 2025-05-04, 499 days before as_of; the
    # later, recent segment is short (35 d).
    facts = interrupted(
        (date(2025, 1, 5), date(2025, 5, 4)), (date(2026, 6, 1), date(2026, 7, 6)), "c"
    )
    assert label_case(facts, V1).step_therapy_satisfied
    assert not label_case(facts, V2).step_therapy_satisfied


def test_an_ongoing_course_is_always_recent():
    facts = make_facts(mtx_start=date(2024, 1, 8), mtx_end=None, end_precision=None)
    assert days_since_end(facts) == 0
    assert label_case(facts, V2).step_therapy_satisfied


def test_gen_v0_3_notes_record_how_long_ago_the_course_ended():
    facts = make_facts(generator_version="gen-v0.3")
    assert label_case(facts).notes.endswith("ended 106d before as-of")
    assert "before as-of" not in label_case(make_facts()).notes  # gen-v0.2 notes unchanged
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run: `uv run pytest -q tests/unit/test_generation_labels.py`

Expected: FAIL. `ImportError: cannot import name 'days_since_end'`.

- [ ] **Step 3: Implement**

In `relay/generation/facts.py`, replace:

```python
from datetime import date
from typing import Literal

GENERATOR_VERSION = "gen-v0.2"

Difficulty = Literal["easy", "medium", "hard", "adversarial"]
DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard", "adversarial")
```

with:

```python
from datetime import date
from typing import Literal

# GENERATOR_VERSION names the frozen gen-v0.2 manifests and stays the default. gen-v0.3 (Phase 3D)
# adds interrupted courses and old courses; generate with generator_version=GEN_V0_3.
GENERATOR_VERSION = "gen-v0.2"
GEN_V0_2 = GENERATOR_VERSION
GEN_V0_3 = "gen-v0.3"
GENERATOR_VERSIONS: tuple[str, ...] = (GEN_V0_2, GEN_V0_3)

Difficulty = Literal["easy", "medium", "hard", "adversarial"]
DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard", "adversarial")
```

In `relay/generation/facts.py`, replace:

```python
MtxStatus = Literal["taken", "never", "undocumented", "relative_only"]
MtxOutcome = Literal["inadequate_response", "intolerance", "not_stated"]
ContradictionKind = Literal["history_vs_note", "dates_conflict"]


@dataclass(frozen=True)
```

with:

```python
MtxStatus = Literal["taken", "never", "undocumented", "relative_only"]
MtxOutcome = Literal["inadequate_response", "intolerance", "not_stated"]
ContradictionKind = Literal["history_vs_note", "dates_conflict"]
# gen-v0.3 interrupted courses (gold guide rule D8): (a) no segment reaches the minimum although
# the total span does (the GOLD-TMP-17 pattern); (b) the later segment qualifies (GOLD-TMP-18);
# (c) the earlier segment qualifies.
InterruptionVariant = Literal["a", "b", "c"]
InterruptionReason = Literal["infection", "surgery", "travel", "lab"]


@dataclass(frozen=True)
```

In `relay/generation/facts.py`, replace:

```python
    - start_precision and end_precision are never "no_year" from sample_facts (gen-v0.2); the
      value remains valid for hand-built facts.
    - stale_note_date is set exactly when stale_note is true.
    """

    case_id: str
```

with:

```python
    - start_precision and end_precision are never "no_year" from sample_facts (gen-v0.2); the
      value remains valid for hand-built facts.
    - stale_note_date is set exactly when stale_note is true.
    - (gen-v0.3) mtx_segments is set only when mtx_status == "taken" and contradiction is None:
      two (start, end) segments, the second end None when ongoing. Then mtx_start is the first
      start, mtx_end the final end, both precisions are "day", split_across_documents is False,
      and interruption_variant and interruption_reason are set (they are None otherwise).
    """

    case_id: str
```

Append to the end of `relay/generation/facts.py`:

```python
    # gen-v0.3 only; the defaults are every gen-v0.2 case.
    generator_version: str = GEN_V0_2
    mtx_segments: tuple[tuple[date, date | None], ...] | None = None
    interruption_variant: InterruptionVariant | None = None
    interruption_reason: InterruptionReason | None = None
```

In `relay/generation/labels.py`, replace:

```python
"""CaseFacts -> GroundTruth: what the rendered documents establish under policy immunara-v0.1.

Rules are applied in a fixed order (spec section 3.4). The generator never writes an action;
expected actions are derived from these facts by the policy engine.
"""

from relay.cases.models import GroundTruth, MissingEvidence
from relay.generation.dates import conservative_end, conservative_start
from relay.generation.facts import GENERATOR_VERSION, CaseFacts

MIN_DAYS = 84  # immunara-v0.1 requires 12 weeks of methotrexate: 12 * 7 = 84 days
_OUTCOMES_THAT_COUNT = frozenset({"inadequate_response", "intolerance"})


def conservative_days(facts: CaseFacts) -> int | None:
```

with:

```python
"""CaseFacts -> GroundTruth: what the rendered documents establish under a policy.

Rules are applied in a fixed order (spec section 3.4). The generator never writes an action;
expected actions are derived from these facts by the policy engine. The policy defaults to
immunara-v0.1; gen-v0.3 labels each case under its own policy_id, so the same facts can be
labelled under immunara-v0.1 and immunara-v0.2 (which adds a recency rule).

Interrupted courses follow the gold guide's rule D8: each segment is measured on its own and
only a single segment of at least min_weeks * 7 days counts. Under a recency rule, that segment
must also end (an ongoing one ends at as_of) no more than max_days_since_therapy days before
as_of, measured from its conservative end.
"""

from datetime import date

from relay.cases.models import GroundTruth, MissingEvidence
from relay.cases.policies import AuthorizationPolicy, load_policy
from relay.generation.dates import conservative_end, conservative_start
from relay.generation.facts import CaseFacts

MIN_DAYS = 84  # immunara-v0.1 requires 12 weeks of methotrexate: 12 * 7 = 84 days
_OUTCOMES_THAT_COUNT = frozenset({"inadequate_response", "intolerance"})
_DEFAULT_POLICY = "immunara-v0.1"


def conservative_days(facts: CaseFacts) -> int | None:
```

In `relay/generation/labels.py`, replace:

```python
    if start is None or end is None:
        return None
    return (end - start).days


def _date_lacks_year(facts: CaseFacts) -> bool:
```

with:

```python
    if start is None or end is None:
        return None
    return (end - start).days


def segment_days(facts: CaseFacts) -> tuple[int, ...]:
    """Each segment's length in days (day precision), an ongoing one counted to as_of."""
    assert facts.mtx_segments is not None
    return tuple(((end or facts.as_of_date) - start).days for start, end in facts.mtx_segments)


def days_since_end(facts: CaseFacts) -> int | None:
    """Days from the course's conservative final end to as_of (0 when ongoing), or None."""
    if facts.mtx_status != "taken":
        return None
    if facts.mtx_end is None:
        return 0
    assert facts.end_precision is not None
    end = conservative_end(facts.mtx_end, facts.end_precision)
    return None if end is None else (facts.as_of_date - end).days


def _qualifying_ends(facts: CaseFacts, min_days: int) -> list[date]:
    """The conservative end (as_of if ongoing) of every course or segment long enough."""
    if facts.mtx_segments is not None:
        return [
            end or facts.as_of_date
            for (start, end), days in zip(facts.mtx_segments, segment_days(facts), strict=True)
            if days >= min_days
        ]
    days = conservative_days(facts)
    if days is None or days < min_days:
        return []
    if facts.mtx_end is None:
        return [facts.as_of_date]
    assert facts.end_precision is not None
    end = conservative_end(facts.mtx_end, facts.end_precision)
    assert end is not None  # conservative_days would be None otherwise
    return [end]


def duration_satisfied(facts: CaseFacts, policy: AuthorizationPolicy) -> bool:
    """A single course or segment is long enough and, under a recency rule, recent enough."""
    if facts.contradiction is not None:
        return False
    limit = policy.max_days_since_therapy
    return any(
        limit is None or (facts.as_of_date - end).days <= limit
        for end in _qualifying_ends(facts, policy.min_weeks * 7)
    )


def _date_lacks_year(facts: CaseFacts) -> bool:
```

In `relay/generation/labels.py`, replace:

```python

def _notes(facts: CaseFacts, days: int | None) -> str:
    """A machine-written summary that mentions only what the rendered documents show."""
    head = f"{GENERATOR_VERSION} {facts.difficulty}: mtx {facts.mtx_status}"
    if facts.mtx_status == "taken":
        assert facts.mtx_start is not None
        actual_end = facts.mtx_end or facts.as_of_date
        end_precision = facts.end_precision or "ongoing"
```

with:

```python

def _notes(facts: CaseFacts, days: int | None) -> str:
    """A machine-written summary that mentions only what the rendered documents show."""
    head = f"{facts.generator_version} {facts.difficulty}: mtx {facts.mtx_status}"
    if facts.mtx_segments is not None:
        first, second = segment_days(facts)
        head += (
            f" interrupted ({facts.interruption_reason}, pattern {facts.interruption_variant}): "
            f"segments {first}d and {second}d, {facts.mtx_outcome}"
        )
    elif facts.mtx_status == "taken":
        assert facts.mtx_start is not None
        actual_end = facts.mtx_end or facts.as_of_date
        end_precision = facts.end_precision or "ongoing"
```

In `relay/generation/labels.py`, replace:

```python
        flags.append("injection")
    if facts.stale_note:
        flags.append("stale note")
    near_miss_course = facts.mtx_status == "taken" and facts.contradiction != "dates_conflict"
    if facts.difficulty == "hard" and near_miss_course:
        flags.append("near-miss")
    return head + "; " + ", ".join(flags)


def label_case(facts: CaseFacts) -> GroundTruth:
    days = conservative_days(facts)
    duration_ok = facts.contradiction is None and days is not None and days >= MIN_DAYS
    missing = _missing_evidence(facts)
    return GroundTruth(
        diagnosis_supported=facts.diagnosis_status == "established",
        step_therapy_satisfied=duration_ok and facts.mtx_outcome in _OUTCOMES_THAT_COUNT,
        documentation_complete=missing is MissingEvidence.NONE,
        contradiction_present=facts.contradiction is not None,
        missing_evidence=missing,
```

with:

```python
        flags.append("injection")
    if facts.stale_note:
        flags.append("stale note")
    near_miss_course = (
        facts.mtx_status == "taken"
        and facts.contradiction != "dates_conflict"
        and facts.mtx_segments is None
    )
    if facts.difficulty == "hard" and near_miss_course:
        flags.append("near-miss")
    since = days_since_end(facts)
    if facts.generator_version != "gen-v0.2" and since is not None and facts.mtx_end is not None:
        flags.append(f"ended {since}d before as-of")
    return head + "; " + ", ".join(flags)


def label_case(facts: CaseFacts, policy: AuthorizationPolicy | None = None) -> GroundTruth:
    """Ground truth under `policy` (default immunara-v0.1)."""
    policy = policy or load_policy(_DEFAULT_POLICY)
    days = conservative_days(facts)
    missing = _missing_evidence(facts)
    return GroundTruth(
        diagnosis_supported=facts.diagnosis_status == "established",
        step_therapy_satisfied=duration_satisfied(facts, policy)
        and facts.mtx_outcome in _OUTCOMES_THAT_COUNT,
        documentation_complete=missing is MissingEvidence.NONE,
        contradiction_present=facts.contradiction is not None,
        missing_evidence=missing,
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run pytest -q tests/unit/test_generation_labels.py`

Expected: PASS.

- [ ] **Step 5: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`

Expected: all pass (about 1155 passed).

Then confirm gen-v0.2 output is still byte-identical (both must print `OK:`):

```bash
env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env generate --verify evals/generated/manifests/gen-v0.2-dev.json --out evals/generated/gen-v0.2-dev
env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env generate --verify evals/generated/manifests/gen-v0.2-holdout.json --out evals/generated/gen-v0.2-holdout
```

- [ ] **Step 6: Commit**

```bash
git add relay/generation/facts.py relay/generation/labels.py tests/unit/test_generation_labels.py
git commit -m "feat: label generated cases under a given policy, with rule D8 and recency" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 7: gen-v0.3 scenarios and rendering (interrupted and old courses)

**Files:**
- Modify: `relay/generation/render.py`
- Modify: `relay/generation/scenarios.py`
- Test (modify): `tests/unit/test_generation_audit.py`

**Interfaces:**
- Consumes: the Task 6 facts fields and `label_case`, `days_since_end`.
- Produces:
  - `sample_facts(rng, *, case_id, difficulty, ..., generator_version: str = GEN_V0_2)` in `relay/generation/scenarios.py`. For gen-v0.3 only, a step 5b makes about 20% of taken courses interrupted (variants a/b/c equally likely, day-precision segments, hold 14-56 days) and moves about 25% of taken courses back so they ended 380-720 days before as_of. gen-v0.2 draws nothing new.
  - `relay/generation/render.py` renders an interrupted course (note sentence with start, hold and reason, restart, final stop or "continues today"; two medication-history rows, the first `- reason: held for <reason>`). Constants `HOLD_REASONS`, `HOLD_REASONS_SHORT`, `TAKEN_INTERRUPTED_ENDED`, `TAKEN_INTERRUPTED_ONGOING`.

The audit (`tests/unit/test_generation_audit.py`) gains a gen-v0.3 section over the same 2,000 seeds: no label or scenario word in any document, the interrupted share of taken courses is 20% ± 5 pp and each variant is 1/3 ± 5 pp of them, the old-course share is 25% ± 5 pp, labels agree with rule D8 when the segment lengths are read back from the rendered dates, and v0.2 labels differ from v0.1 only by recency. Planning measured 19.7% interrupted (a 34.0%, b 35.2%, c 30.8%) and 25.5% old.

- [ ] **Step 1: Write the failing tests**

In `tests/unit/test_generation_audit.py`, replace:

```python

import re
from dataclasses import dataclass
from datetime import date
from random import Random

import pytest

from relay.cases.models import Document, GroundTruth
from relay.generation.dates import MONTH_NAMES
from relay.generation.facts import DIFFICULTIES, CaseFacts
from relay.generation.generator import generate_case
from relay.generation.labels import MIN_DAYS, label_case
from relay.generation.render import NEVER_TAKEN, NEVER_TAKEN_OTHER_DMARD, render_documents
from relay.generation.scenarios import sample_facts
```

with:

```python

import re
from dataclasses import dataclass
from datetime import date, timedelta
from random import Random

import pytest

from relay.cases.models import Document, GroundTruth
from relay.cases.policies import load_policy
from relay.generation.dates import MONTH_NAMES
from relay.generation.facts import DIFFICULTIES, CaseFacts
from relay.generation.generator import generate_case
from relay.generation.labels import MIN_DAYS, days_since_end, label_case
from relay.generation.render import NEVER_TAKEN, NEVER_TAKEN_OTHER_DMARD, render_documents
from relay.generation.scenarios import sample_facts
```

Append to the end of `tests/unit/test_generation_audit.py`:

```python
# ---- Phase 3D: gen-v0.3 (interrupted courses, old courses) ----

V3_FORBIDDEN_SUBSTRINGS = (*FORBIDDEN_SUBSTRINGS, "interrupt", "pattern", "segment", "variant")


def render_v3(seed: int) -> Rendered:
    rng = Random(seed)
    facts = sample_facts(
        rng,
        case_id=f"GEN-{seed:08d}",
        difficulty=DIFFICULTIES[seed % 4],
        generator_version="gen-v0.3",
    )
    documents = render_documents(facts, rng)
    return Rendered(seed, facts, {d.id: d for d in documents}, label_case(facts))


@pytest.fixture(scope="module")
def rendered_v3() -> list[Rendered]:
    return [render_v3(seed) for seed in SEEDS]


def taken(rendered: list[Rendered]) -> list[Rendered]:
    return [r for r in rendered if r.facts.mtx_status == "taken"]


def test_v3_documents_name_no_label_or_scenario(rendered_v3):
    for r in rendered_v3:
        assert set(r.documents) <= ALLOWED_DOCUMENT_IDS, (r.seed, list(r.documents))
        for doc_id, document in r.documents.items():
            lowered = document.text.lower()
            for word in V3_FORBIDDEN_SUBSTRINGS:
                assert word not in lowered, (r.seed, doc_id, word)
            assert "around" not in lowered, (r.seed, doc_id)


def test_v3_no_yearless_treatment_dates(rendered_v3):
    for r in rendered_v3:
        for text in (r.treatment_paragraph, r.history_mtx_line or ""):
            assert YEARLESS_MONTH.search(text) is None, (r.seed, text)


def test_about_a_fifth_of_taken_courses_are_interrupted(rendered_v3):
    courses = taken(rendered_v3)
    interrupted = [r for r in courses if r.facts.mtx_segments is not None]
    assert abs(len(interrupted) / len(courses) - 0.20) <= 0.05, len(interrupted) / len(courses)
    for variant in ("a", "b", "c"):
        share = sum(r.facts.interruption_variant == variant for r in interrupted) / len(interrupted)
        assert abs(share - 1 / 3) <= 0.05, (variant, share)


def test_about_a_quarter_of_taken_courses_ended_over_a_year_before_as_of(rendered_v3):
    courses = taken(rendered_v3)
    old = [r for r in courses if (days_since_end(r.facts) or 0) > 365]
    assert abs(len(old) / len(courses) - 0.25) <= 0.05, len(old) / len(courses)


def rendered_segments(r: Rendered) -> tuple[int, int]:
    """Segment lengths read back from the note's day-precision dates (start, pause, restart,
    end, or as_of when ongoing)."""
    dates = [parse_day_date(m) for m in DAY_DATE.findall(r.treatment_paragraph)]
    ongoing = r.facts.mtx_end is None
    assert len(dates) == (3 if ongoing else 4), (r.seed, r.treatment_paragraph)
    start, pause, restart = dates[:3]
    end = r.facts.as_of_date if ongoing else dates[3]
    assert start < pause < restart <= end, r.seed
    return (pause - start).days, (end - restart).days


def test_v3_interrupted_labels_follow_rule_d8_from_the_rendered_dates(rendered_v3):
    interrupted = [r for r in rendered_v3 if r.facts.mtx_segments is not None]
    assert len(interrupted) > 200
    for r in interrupted:
        first, second = rendered_segments(r)
        long_enough = max(first, second) >= MIN_DAYS
        outcome = r.facts.mtx_outcome in ("inadequate_response", "intolerance")
        assert r.truth.step_therapy_satisfied == (long_enough and outcome), r.seed
        expected_variant = "a" if not long_enough else ("b" if second >= MIN_DAYS else "c")
        assert r.facts.interruption_variant == expected_variant, r.seed
        if expected_variant == "a":
            assert (r.facts.mtx_end or r.facts.as_of_date) - r.facts.mtx_start >= timedelta(
                days=MIN_DAYS
            ), r.seed  # the TMP-17 trap: the whole span would pass


def test_v3_medication_history_shows_both_segments(rendered_v3):
    with_history = [
        r
        for r in rendered_v3
        if r.facts.mtx_segments is not None and "medication_history" in r.documents
    ]
    assert with_history
    for r in with_history:
        rows = [
            line
            for line in r.documents["medication_history"].text.splitlines()
            if line.startswith("METHOTREXATE")
        ]
        assert len(rows) == 2, r.seed
        assert "reason: held for " in rows[0], r.seed
        assert ("status: active" in rows[1]) == (r.facts.mtx_end is None), r.seed


def test_v3_labels_under_v0_2_differ_only_by_recency(rendered_v3):
    v1, v2 = load_policy("immunara-v0.1"), load_policy("immunara-v0.2")
    changed = 0
    for r in rendered_v3:
        a, b = label_case(r.facts, v1), label_case(r.facts, v2)
        if a != b:
            changed += 1
            assert a.model_dump(exclude={"step_therapy_satisfied"}) == b.model_dump(
                exclude={"step_therapy_satisfied"}
            ), r.seed
            assert a.step_therapy_satisfied and not b.step_therapy_satisfied, r.seed
            assert (days_since_end(r.facts) or 0) > 365 or r.facts.mtx_segments, r.seed
    assert changed > 100
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run: `uv run pytest -q tests/unit/test_generation_audit.py`

Expected: FAIL. `TypeError: sample_facts() got an unexpected keyword argument 'generator_version'` in the new gen-v0.3 audit tests.

- [ ] **Step 3: Implement**

In `relay/generation/render.py`, replace:

```python
TAKEN_ONGOING_SPLIT: tuple[str, ...] = (
    "The patient continues {mtx} {dose} at this time.",
    "{Mtx} {dose} is ongoing and the patient continues to take it.",
)
OUTCOME_ENDED: dict[str, tuple[str, ...]] = {
    "inadequate_response": (
```

with:

```python
TAKEN_ONGOING_SPLIT: tuple[str, ...] = (
    "The patient continues {mtx} {dose} at this time.",
    "{Mtx} {dose} is ongoing and the patient continues to take it.",
)
# gen-v0.3 interrupted courses (rule D8). The hold reason is never a response or an intolerance:
# the drug was resumed afterwards, so the hold says nothing about whether it worked.
HOLD_REASONS: dict[str, tuple[str, ...]] = {
    "infection": ("a respiratory infection", "a urinary tract infection"),
    "surgery": ("a planned knee surgery", "a scheduled dental surgery"),
    "travel": ("several weeks of travel abroad", "an extended work trip"),
    "lab": (
        "a routine lab result that needed rechecking, which came back normal",
        "a repeat of routine monitoring labs, which were normal",
    ),
}
HOLD_REASONS_SHORT: dict[str, str] = {
    "infection": "infection",
    "surgery": "surgery",
    "travel": "travel",
    "lab": "lab recheck",
}
TAKEN_INTERRUPTED_ENDED: tuple[str, ...] = (
    "{Mtx} {dose} was started {start} and held {pause} because of {reason}. It was restarted "
    "{restart} and stopped {end}{outcome}.",
    "The patient began {mtx} {dose} {start}; it was paused {pause} for {reason}, resumed "
    "{restart}, and discontinued {end}{outcome}.",
)
TAKEN_INTERRUPTED_ONGOING: tuple[str, ...] = (
    "The patient started {mtx} {dose} {start}; it was held {pause} because of {reason} and "
    "restarted {restart}, and the patient continues it today.",
    "{Mtx} {dose} was begun {start}, paused {pause} for {reason}, and resumed {restart}; the "
    "patient remains on it.",
)
OUTCOME_ENDED: dict[str, tuple[str, ...]] = {
    "inadequate_response": (
```

In `relay/generation/render.py`, replace:

```python
        return [rng.choice(NEVER_TAKEN).format(mtx=mtx)]
    assert facts.mtx_start is not None and facts.start_precision is not None
    score = rng.randint(22, 38)
    if facts.mtx_end is None:
        outcome = rng.choice(OUTCOME_ONGOING[facts.mtx_outcome]).format(mtx=mtx, score=score)
        if facts.split_across_documents:
            sentence = rng.choice(TAKEN_ONGOING_SPLIT)
```

with:

```python
        return [rng.choice(NEVER_TAKEN).format(mtx=mtx)]
    assert facts.mtx_start is not None and facts.start_precision is not None
    score = rng.randint(22, 38)
    if facts.mtx_segments is not None:
        narrative = [_interrupted_sentence(facts, rng, mtx, dose, score)]
    elif facts.mtx_end is None:
        outcome = rng.choice(OUTCOME_ONGOING[facts.mtx_outcome]).format(mtx=mtx, score=score)
        if facts.split_across_documents:
            sentence = rng.choice(TAKEN_ONGOING_SPLIT)
```

In `relay/generation/render.py`, replace:

```python
    if facts.other_dmards:
        narrative.append(rng.choice(CO_DMARD).format(dmard=facts.other_dmards[0]))
    return narrative


def _physician_note(facts: CaseFacts, rng: Random, dose: str) -> Document:
```

with:

```python
    if facts.other_dmards:
        narrative.append(rng.choice(CO_DMARD).format(dmard=facts.other_dmards[0]))
    return narrative


def _interrupted_sentence(facts: CaseFacts, rng: Random, mtx: str, dose: str, score: int) -> str:
    """The note's account of an interrupted course: start, hold (with its reason), restart, and
    the final stop or 'continues today'. Every date is at day precision."""
    assert facts.mtx_segments is not None and facts.interruption_reason is not None
    (start, pause), (restart, end) = facts.mtx_segments
    reason = rng.choice(HOLD_REASONS[facts.interruption_reason])
    dates = {
        "start": date_phrase(start, "day", rng, bound="start"),
        "pause": date_phrase(pause, "day", rng, bound="end"),
        "restart": date_phrase(restart, "day", rng, bound="start"),
    }
    if end is None:
        template = rng.choice(TAKEN_INTERRUPTED_ONGOING)
        outcome = rng.choice(OUTCOME_ONGOING[facts.mtx_outcome]).format(mtx=mtx, score=score)
        return template.format(mtx=mtx, Mtx=_cap(mtx), dose=dose, reason=reason, **dates) + outcome
    outcome = rng.choice(OUTCOME_ENDED[facts.mtx_outcome]).format(score=score)
    return rng.choice(TAKEN_INTERRUPTED_ENDED).format(
        mtx=mtx,
        Mtx=_cap(mtx),
        dose=dose,
        reason=reason,
        end=date_phrase(end, "day", rng, bound="end"),
        outcome=outcome,
        **dates,
    )


def _interrupted_history_lines(facts: CaseFacts, rng: Random, dose_upper: str) -> list[str]:
    """Two medication-history rows: the held first segment and the restarted one."""
    assert facts.mtx_segments is not None and facts.interruption_reason is not None
    (start, pause), (restart, end) = facts.mtx_segments
    held = HOLD_REASONS_SHORT[facts.interruption_reason]
    first = (
        f"METHOTREXATE {dose_upper} - status: inactive - start "
        f"{format_date(start, 'day', rng, bound='start')} - end "
        f"{format_date(pause, 'day', rng, bound='end')} - reason: held for {held}"
    )
    restarted = format_date(restart, "day", rng, bound="start")
    if end is None:
        second = f"METHOTREXATE {dose_upper} - status: active - start {restarted}"
    else:
        second = (
            f"METHOTREXATE {dose_upper} - status: inactive - start {restarted} - end "
            f"{format_date(end, 'day', rng, bound='end')}"
        )
    return [first, second]


def _physician_note(facts: CaseFacts, rng: Random, dose: str) -> Document:
```

In `relay/generation/render.py`, replace:

```python

def _medication_history(facts: CaseFacts, rng: Random, dose_upper: str) -> Document:
    lines = [f"{SYNTHETIC_PREFIX}MEDICATION HISTORY"]
    if facts.mtx_status == "taken":
        assert facts.mtx_start is not None and facts.start_precision is not None
        start_date = facts.history_start or facts.mtx_start
        start = format_date(start_date, facts.start_precision, rng, bound="start")
```

with:

```python

def _medication_history(facts: CaseFacts, rng: Random, dose_upper: str) -> Document:
    lines = [f"{SYNTHETIC_PREFIX}MEDICATION HISTORY"]
    if facts.mtx_segments is not None:
        lines += _interrupted_history_lines(facts, rng, dose_upper)
    elif facts.mtx_status == "taken":
        assert facts.mtx_start is not None and facts.start_precision is not None
        start_date = facts.history_start or facts.mtx_start
        start = format_date(start_date, facts.start_precision, rng, bound="start")
```

In `relay/generation/scenarios.py`, replace:

```python

from relay.generation.facts import (
    DIFFICULTIES,
    CaseFacts,
    ContradictionKind,
    DiagnosisStatus,
    Difficulty,
    MtxOutcome,
    MtxStatus,
    Precision,
```

with:

```python

from relay.generation.facts import (
    DIFFICULTIES,
    GEN_V0_2,
    GEN_V0_3,
    GENERATOR_VERSIONS,
    CaseFacts,
    ContradictionKind,
    DiagnosisStatus,
    Difficulty,
    InterruptionReason,
    InterruptionVariant,
    MtxOutcome,
    MtxStatus,
    Precision,
```

In `relay/generation/scenarios.py`, replace:

```python
OUTCOME_WEIGHTS_ENDED: tuple[float, ...] = (0.6, 0.25, 0.15)
OUTCOMES_ONGOING: tuple[MtxOutcome, ...] = ("inadequate_response", "not_stated")
OUTCOME_WEIGHTS_ONGOING: tuple[float, ...] = (0.8, 0.2)


@dataclass(frozen=True)
```

with:

```python
OUTCOME_WEIGHTS_ENDED: tuple[float, ...] = (0.6, 0.25, 0.15)
OUTCOMES_ONGOING: tuple[MtxOutcome, ...] = ("inadequate_response", "not_stated")
OUTCOME_WEIGHTS_ONGOING: tuple[float, ...] = (0.8, 0.2)

# gen-v0.3 (Phase 3D). About 20% of taken-methotrexate courses are interrupted: eligible courses
# (taken, no contradiction) are interrupted with INTERRUPTED_PROBABILITY; the audit checks the
# share over all taken courses against 20% +/- 5 pp. Variants are equally likely.
INTERRUPTED_PROBABILITY = 0.24
INTERRUPTION_VARIANTS: tuple[InterruptionVariant, ...] = ("a", "b", "c")
INTERRUPTION_REASONS: tuple[InterruptionReason, ...] = ("infection", "surgery", "travel", "lab")
HOLD_DAYS = (14, 56)  # the gap between the pause and the restart
# Segment lengths in days, (first, second), per variant. Short segments stay at least 7 days
# under the 84-day minimum and long ones 14 days over it, so no segment is a near miss;
# pattern (a)'s total span (first + hold + second) always reaches 84.
SEGMENT_DAYS: dict[InterruptionVariant, tuple[tuple[int, int], tuple[int, int]]] = {
    "a": ((42, 77), (28, 77)),
    "b": ((21, 70), (98, 180)),
    "c": ((98, 180), (21, 70)),
}
# About 25% of taken courses ended more than 365 days before as_of. Only ended courses can be
# old, and ongoing courses are 20% of taken ones, so an ended course is moved back with
# probability 0.25 / 0.8. Its final end then lands 380-720 days before as_of.
OLD_COURSE_PROBABILITY = 0.3125
OLD_COURSE_GAP_DAYS = (380, 720)


@dataclass(frozen=True)
```

In `relay/generation/scenarios.py`, replace:

```python
    contradiction_probability: float | None = None,
    missing_data_probability: float | None = None,
    note_noise: float | None = None,
) -> CaseFacts:
    if difficulty not in PROFILES:
        raise ValueError(f"unknown difficulty {difficulty!r}; allowed: {list(DIFFICULTIES)}")
    profile = PROFILES[difficulty]
```

with:

```python
    contradiction_probability: float | None = None,
    missing_data_probability: float | None = None,
    note_noise: float | None = None,
    generator_version: str = GEN_V0_2,
) -> CaseFacts:
    if generator_version not in GENERATOR_VERSIONS:
        raise ValueError(
            f"unknown generator version {generator_version!r}; allowed: {list(GENERATOR_VERSIONS)}"
        )
    if difficulty not in PROFILES:
        raise ValueError(f"unknown difficulty {difficulty!r}; allowed: {list(DIFFICULTIES)}")
    profile = PROFILES[difficulty]
```

In `relay/generation/scenarios.py`, replace:

```python
            history_start = mtx_start - _days(rng, *CONFLICT_EXTRA_DAYS)
            diagnosis_year = min(diagnosis_year, history_start.year)

    # 6. Normalize fields that only apply to a documented methotrexate course.
    if mtx_status != "taken":
        mtx_start = mtx_end = None
```

with:

```python
            history_start = mtx_start - _days(rng, *CONFLICT_EXTRA_DAYS)
            diagnosis_year = min(diagnosis_year, history_start.year)

    # 5b. gen-v0.3 only: interrupted courses, then old courses. gen-v0.2 draws nothing here, so
    # its facts (and every later draw) are unchanged.
    mtx_segments: tuple[tuple[date, date | None], ...] | None = None
    variant: InterruptionVariant | None = None
    reason: InterruptionReason | None = None
    if generator_version == GEN_V0_3 and mtx_status == "taken":
        if contradiction is None and rng.random() < INTERRUPTED_PROBABILITY:
            variant = rng.choice(INTERRUPTION_VARIANTS)
            reason = rng.choice(INTERRUPTION_REASONS)
            (first_low, first_high), (second_low, second_high) = SEGMENT_DAYS[variant]
            first = rng.randint(first_low, first_high)
            hold = rng.randint(*HOLD_DAYS)
            second = rng.randint(second_low, second_high)
            restart = (mtx_end or as_of) - timedelta(days=second)
            pause = restart - timedelta(days=hold)
            mtx_start = pause - timedelta(days=first)
            mtx_segments = ((mtx_start, pause), (restart, mtx_end))
            start_precision = "day"
            end_precision = None if ongoing else "day"
            split = False
        if mtx_end is not None and rng.random() < OLD_COURSE_PROBABILITY:
            shift = timedelta(days=rng.randint(*OLD_COURSE_GAP_DAYS) - (as_of - mtx_end).days)
            mtx_end -= shift
            assert mtx_start is not None
            mtx_start -= shift
            if history_start is not None:
                history_start -= shift
            if mtx_segments is not None:
                (s1, p1), (r2, e2) = mtx_segments
                assert e2 is not None
                mtx_segments = ((s1 - shift, p1 - shift), (r2 - shift, e2 - shift))
        assert mtx_start is not None
        diagnosis_year = min(diagnosis_year, (history_start or mtx_start).year)

    # 6. Normalize fields that only apply to a documented methotrexate course.
    if mtx_status != "taken":
        mtx_start = mtx_end = None
```

In `relay/generation/scenarios.py`, replace:

```python
        stale_note=stale_note,
        stale_note_date=stale_note_date,
        noise=noise,
    )
```

with:

```python
        stale_note=stale_note,
        stale_note_date=stale_note_date,
        noise=noise,
        generator_version=generator_version,
        mtx_segments=mtx_segments,
        interruption_variant=variant,
        interruption_reason=reason,
    )
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run pytest -q tests/unit/test_generation_audit.py`

Expected: PASS.

- [ ] **Step 5: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`

Expected: all pass (about 1162 passed).

Re-run the two gen-v0.2 `--verify` commands from Task 6 Step 5; both must still print `OK:`.

- [ ] **Step 6: Commit**

```bash
git add relay/generation/render.py relay/generation/scenarios.py tests/unit/test_generation_audit.py
git commit -m "feat: generate interrupted and old methotrexate courses in gen-v0.3" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 8: Versioned generation, manifests and `relay generate --generator/--policy`

**Files:**
- Modify: `relay/cli.py`
- Modify: `relay/generation/generator.py`
- Modify: `relay/generation/manifest.py`
- Test (modify): `tests/integration/test_cli_generate.py`
- Test (modify): `tests/unit/test_generation_audit.py`
- Test (modify): `tests/unit/test_generator.py`

**Interfaces:**
- Consumes: `sample_facts(..., generator_version)` (Task 7), `label_case(facts, policy)` (Task 6), `load_thresholds("v0.2")` (Task 1).
- Produces:
  - `generate_case(..., generator_version: str = GEN_V0_2)`; `POLICY_IDS` gains `"v0.2": "immunara-v0.2"`; each case is labelled under its own policy.
  - `generate_dataset(count, seed, dataset_id, out_dir, *, generator_version=GEN_V0_2, policy_version="v0.1")`.
  - `DatasetManifest.policy_version: str = "v0.1"`, written by `write_manifest` only when it is not v0.1, so the committed gen-v0.2 manifests round-trip byte for byte. `build_manifest(..., generator_version=GEN_V0_2, policy_version="v0.1")`.
  - `verify_dataset` accepts any version in `GENERATOR_VERSIONS` and regenerates with the manifest's generator and policy versions.
  - CLI: `relay generate --generator gen-v0.2|gen-v0.3` (default gen-v0.2) and `--policy v0.1|v0.2` (default v0.1). Both are exit 2 with `--verify`, which reads them from the manifest.

- [ ] **Step 1: Write the failing tests**

Append to the end of `tests/integration/test_cli_generate.py`:

```python
# ---- Phase 3D: --generator and --policy ----


def test_generate_gen_v0_3_with_policy_v0_2_writes_and_verifies(tmp_path):
    result = generate(tmp_path, 8, 5, "gen-shift", "--generator", "gen-v0.3", "--policy", "v0.2")
    assert result.exit_code == 0, result.output
    manifest = json.loads((tmp_path / "manifests" / "gen-shift.json").read_text())
    assert (manifest["generator_version"], manifest["policy_version"]) == ("gen-v0.3", "v0.2")
    case = json.loads((tmp_path / "gen-shift" / "GEN-05000000" / "case.json").read_text())
    assert case["policy_id"] == "immunara-v0.2"
    checked = verify(tmp_path, "gen-shift")
    assert checked.exit_code == 0, checked.output
    assert checked.output.startswith("OK: gen-shift regenerates to ")


def test_default_generator_is_gen_v0_2_and_writes_no_policy_version(tmp_path):
    assert generate(tmp_path).exit_code == 0
    manifest = json.loads((tmp_path / "manifests" / "gen-test.json").read_text())
    assert manifest["generator_version"] == "gen-v0.2"
    assert "policy_version" not in manifest


def test_unknown_generator_or_policy_is_exit_2(tmp_path):
    result = generate(tmp_path, 4, 3, "gen-a", "--generator", "gen-v9")
    assert result.exit_code == 2
    assert "unknown generator version 'gen-v9'" in result.output
    result = generate(tmp_path, 4, 3, "gen-b", "--policy", "v9")
    assert result.exit_code == 2
    assert "unknown policy version 'v9'" in result.output


def test_verify_rejects_generator_and_policy_flags(tmp_path):
    generate(tmp_path)
    for flag, value in (("--generator", "gen-v0.3"), ("--policy", "v0.2")):
        result = verify(tmp_path, "gen-test", flag, value)
        assert result.exit_code == 2
        assert "read from the manifest" in result.output
```

In `tests/unit/test_generation_audit.py`, replace:

```python
    return [r for r in rendered if r.facts.mtx_status == "taken"]


def test_v3_documents_name_no_label_or_scenario(rendered_v3):
    for r in rendered_v3:
        assert set(r.documents) <= ALLOWED_DOCUMENT_IDS, (r.seed, list(r.documents))
```

with:

```python
    return [r for r in rendered if r.facts.mtx_status == "taken"]


def test_v3_draws_match_generate_case(rendered_v3):
    for r in rendered_v3[:40]:
        case = generate_case(r.seed, r.facts.difficulty, generator_version="gen-v0.3")
        assert {d.id: d for d in case.input.documents} == r.documents
        assert case.ground_truth == r.truth


def test_v3_documents_name_no_label_or_scenario(rendered_v3):
    for r in rendered_v3:
        assert set(r.documents) <= ALLOWED_DOCUMENT_IDS, (r.seed, list(r.documents))
```

In `tests/unit/test_generator.py`, replace:

```python
        "expected_action_counts",
        "missing_evidence_counts",
        "dataset_hash",
    }
    path = tmp_path / "manifests" / "gen-test.json"
    write_manifest(manifest, path)
```

with:

```python
        "expected_action_counts",
        "missing_evidence_counts",
        "dataset_hash",
        "policy_version",
    }
    path = tmp_path / "manifests" / "gen-test.json"
    write_manifest(manifest, path)
```

Append to the end of `tests/unit/test_generator.py`:

```python
# ---- Phase 3D: gen-v0.3 and policy-labelled datasets ----

REPO = Path(__file__).resolve().parents[2]
COMMITTED_MANIFESTS = REPO / "evals" / "generated" / "manifests"


def test_gen_v0_2_stays_the_default_and_is_unchanged_by_the_version_parameter():
    assert GENERATOR_VERSION == "gen-v0.2"
    assert generate_case(42, "hard") == generate_case(42, "hard", generator_version="gen-v0.2")


def test_gen_v0_3_cases_are_labelled_and_noted_as_gen_v0_3():
    case = generate_case(42, "easy", generator_version="gen-v0.3")
    assert case.ground_truth.notes.startswith("gen-v0.3 easy:")
    assert case != generate_case(42, "easy")


def test_policy_v0_2_cases_carry_and_are_labelled_under_immunara_v0_2():
    for seed in range(400):
        v1 = generate_case(seed, "easy", generator_version="gen-v0.3")
        v2 = generate_case(seed, "easy", generator_version="gen-v0.3", policy_version="v0.2")
        assert v2.input.policy_id == "immunara-v0.2"
        assert v1.input.model_copy(update={"policy_id": "immunara-v0.2"}) == v2.input
        if v1.ground_truth != v2.ground_truth:
            assert v1.ground_truth.step_therapy_satisfied
            assert not v2.ground_truth.step_therapy_satisfied
            return
    raise AssertionError("no easy case in 400 seeds was old enough to change its label")


def test_unknown_generator_version_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="unknown generator version 'gen-v9'"):
        generate_case(1, "easy", generator_version="gen-v9")
    with pytest.raises(ValueError, match="unknown generator version 'gen-v9'"):
        generate_dataset(4, 1, "gen-test", tmp_path / "ds", generator_version="gen-v9")
    with pytest.raises(ValueError, match="unknown policy version 'v9'"):
        generate_dataset(4, 1, "gen-test", tmp_path / "ds", policy_version="v9")


def test_gen_v0_3_manifest_records_generator_and_policy_and_verifies(tmp_path):
    manifest = generate_dataset(
        8, 5, "gen-test", tmp_path / "ds", generator_version="gen-v0.3", policy_version="v0.2"
    )
    assert (manifest.generator_version, manifest.policy_version) == ("gen-v0.3", "v0.2")
    assert {c.input.policy_id for c in load_dataset(tmp_path / "ds")} == {"immunara-v0.2"}
    path = tmp_path / "gen-test.json"
    write_manifest(manifest, path)
    assert json.loads(path.read_text())["policy_version"] == "v0.2"
    assert read_manifest(path) == manifest
    assert verify_dataset(manifest, tmp_path / "ds") == []


def test_a_v0_1_manifest_does_not_write_policy_version(tmp_path):
    manifest = generate_dataset(4, 5, "gen-test", tmp_path / "ds", generator_version="gen-v0.3")
    path = tmp_path / "gen-test.json"
    write_manifest(manifest, path)
    assert "policy_version" not in json.loads(path.read_text())
    assert read_manifest(path).policy_version == "v0.1"


@pytest.mark.parametrize("name", ["gen-v0.2-dev.json", "gen-v0.2-holdout.json"])
def test_committed_gen_v0_2_manifests_round_trip_byte_identically(tmp_path, name):
    committed = COMMITTED_MANIFESTS / name
    path = tmp_path / name
    write_manifest(read_manifest(committed), path)
    assert path.read_bytes() == committed.read_bytes()
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run: `uv run pytest -q tests/integration/test_cli_generate.py tests/unit/test_generation_audit.py tests/unit/test_generator.py`

Expected: FAIL. `TypeError: generate_case() got an unexpected keyword argument 'generator_version'`, the manifest field-set test sees no `policy_version`, and the CLI rejects `--generator`.

- [ ] **Step 3: Implement**

In `relay/cli.py`, replace:

```python
    replay_thresholds,
    replay_trace,
)
from relay.generation.generator import generate_dataset, verify_dataset
from relay.generation.manifest import MANIFEST_DIR, dataset_hash, read_manifest, write_manifest
from relay.reporting import (
```

with:

```python
    replay_thresholds,
    replay_trace,
)
from relay.generation.facts import GEN_V0_2, GENERATOR_VERSIONS
from relay.generation.generator import generate_dataset, verify_dataset
from relay.generation.manifest import MANIFEST_DIR, dataset_hash, read_manifest, write_manifest
from relay.reporting import (
```

In `relay/cli.py`, replace:

```python
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite an existing manifest for this dataset id.")
    ] = False,
) -> None:
    """Generate a seeded synthetic dataset, or verify one against its manifest."""
    if verify is not None:
        if count is not None or seed is not None or dataset_id is not None:
            raise _fail("--verify cannot be combined with --count, --seed or --dataset-id")
        if out is not None and not out.exists():
            raise _fail(f"--out path does not exist: {out}")
        try:
```

with:

```python
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite an existing manifest for this dataset id.")
    ] = False,
    generator: Annotated[
        str | None,
        typer.Option(
            "--generator",
            help=f"Generator version: {', '.join(GENERATOR_VERSIONS)} (default {GEN_V0_2}).",
        ),
    ] = None,
    policy: Annotated[
        str | None,
        typer.Option(
            "--policy",
            help="Policy version every case uses and is labelled under: v0.1 (default) or v0.2.",
        ),
    ] = None,
) -> None:
    """Generate a seeded synthetic dataset, or verify one against its manifest."""
    if verify is not None:
        given = {
            "--count": count,
            "--seed": seed,
            "--dataset-id": dataset_id,
            "--generator": generator,
            "--policy": policy,
        }
        if any(value is not None for value in given.values()):
            raise _fail(
                "--verify cannot be combined with --count, --seed, --dataset-id, --generator or "
                "--policy (they are read from the manifest)"
            )
        if out is not None and not out.exists():
            raise _fail(f"--out path does not exist: {out}")
        try:
```

In `relay/cli.py`, replace:

```python
    if manifest_path.exists() and not force:
        raise _fail(f"manifest {manifest_path} already exists; pass --force to overwrite it")
    try:
        manifest = generate_dataset(count, seed, dataset_id, out)
    except (FileExistsError, ValueError) as error:
        raise _fail(str(error)) from error
    write_manifest(manifest, manifest_path)
```

with:

```python
    if manifest_path.exists() and not force:
        raise _fail(f"manifest {manifest_path} already exists; pass --force to overwrite it")
    try:
        manifest = generate_dataset(
            count,
            seed,
            dataset_id,
            out,
            generator_version=generator or GEN_V0_2,
            policy_version=policy or "v0.1",
        )
    except (FileExistsError, ValueError) as error:
        raise _fail(str(error)) from error
    write_manifest(manifest, manifest_path)
```

In `relay/generation/generator.py`, replace:

```python
from relay.cases.loader import CaseLoadError, load_dataset
from relay.cases.models import CaseInput, Insurance, MedicationRequest, Patient, PriorAuthCase
from relay.cases.policies import load_policy
from relay.generation.facts import DIFFICULTIES, GENERATOR_VERSION, Difficulty
from relay.generation.labels import label_case
from relay.generation.manifest import DatasetManifest, build_manifest, dataset_hash
from relay.generation.render import render_documents
from relay.generation.scenarios import sample_facts
from relay.workflow.thresholds import load_thresholds

POLICY_IDS: dict[str, str] = {"v0.1": "immunara-v0.1"}
SEED_STRIDE = 1_000_000
```

with:

```python
from relay.cases.loader import CaseLoadError, load_dataset
from relay.cases.models import CaseInput, Insurance, MedicationRequest, Patient, PriorAuthCase
from relay.cases.policies import load_policy
from relay.generation.facts import DIFFICULTIES, GEN_V0_2, GENERATOR_VERSIONS, Difficulty
from relay.generation.labels import label_case
from relay.generation.manifest import DatasetManifest, build_manifest, dataset_hash
from relay.generation.render import render_documents
from relay.generation.scenarios import sample_facts
from relay.workflow.thresholds import load_thresholds

POLICY_IDS: dict[str, str] = {"v0.1": "immunara-v0.1", "v0.2": "immunara-v0.2"}
SEED_STRIDE = 1_000_000
```

In `relay/generation/generator.py`, replace:

```python
    note_noise: float | None = None,
    policy_version: str = "v0.1",
    dataset_id: str = "gen-adhoc",
) -> PriorAuthCase:
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"unknown difficulty {difficulty!r}; allowed: {list(DIFFICULTIES)}")
```

with:

```python
    note_noise: float | None = None,
    policy_version: str = "v0.1",
    dataset_id: str = "gen-adhoc",
    generator_version: str = GEN_V0_2,
) -> PriorAuthCase:
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"unknown difficulty {difficulty!r}; allowed: {list(DIFFICULTIES)}")
```

In `relay/generation/generator.py`, replace:

```python
        contradiction_probability=contradiction_probability,
        missing_data_probability=missing_data_probability,
        note_noise=note_noise,
    )
    documents = render_documents(facts, rng)
    case_input = CaseInput(
```

with:

```python
        contradiction_probability=contradiction_probability,
        missing_data_probability=missing_data_probability,
        note_noise=note_noise,
        generator_version=generator_version,
    )
    documents = render_documents(facts, rng)
    case_input = CaseInput(
```

In `relay/generation/generator.py`, replace:

```python
        documents=documents,
        policy_id=policy.id,
    )
    return PriorAuthCase(input=case_input, ground_truth=label_case(facts))


def _write(path: Path, text: str) -> None:
```

with:

```python
        documents=documents,
        policy_id=policy.id,
    )
    return PriorAuthCase(input=case_input, ground_truth=label_case(facts, policy))


def _write(path: Path, text: str) -> None:
```

In `relay/generation/generator.py`, replace:

```python
    return case_dir


def generate_dataset(count: int, seed: int, dataset_id: str, out_dir: Path) -> DatasetManifest:
    if count < 1:
        raise ValueError(f"count must be at least 1, got {count}")
    if seed < 0:
```

with:

```python
    return case_dir


def generate_dataset(
    count: int,
    seed: int,
    dataset_id: str,
    out_dir: Path,
    *,
    generator_version: str = GEN_V0_2,
    policy_version: str = "v0.1",
) -> DatasetManifest:
    """Generate `count` cases into out_dir. Every case uses the policy for `policy_version` and is
    labelled under it; gen-v0.2 datasets are always v0.1."""
    if generator_version not in GENERATOR_VERSIONS:
        raise ValueError(
            f"unknown generator version {generator_version!r}; allowed: {list(GENERATOR_VERSIONS)}"
        )
    if policy_version not in POLICY_IDS:
        raise ValueError(
            f"unknown policy version {policy_version!r}; allowed: {sorted(POLICY_IDS)}"
        )
    if count < 1:
        raise ValueError(f"count must be at least 1, got {count}")
    if seed < 0:
```

In `relay/generation/generator.py`, replace:

```python
    difficulties: list[str] = []
    for i in range(count):
        difficulty = DIFFICULTIES[i % len(DIFFICULTIES)]
        case = generate_case(seed * SEED_STRIDE + i, difficulty, dataset_id=dataset_id)
        write_case(case, out_dir)
        cases.append(case)
        difficulties.append(difficulty)
```

with:

```python
    difficulties: list[str] = []
    for i in range(count):
        difficulty = DIFFICULTIES[i % len(DIFFICULTIES)]
        case = generate_case(
            seed * SEED_STRIDE + i,
            difficulty,
            policy_version=policy_version,
            dataset_id=dataset_id,
            generator_version=generator_version,
        )
        write_case(case, out_dir)
        cases.append(case)
        difficulties.append(difficulty)
```

In `relay/generation/generator.py`, replace:

```python
        seed=seed,
        cases=cases,
        difficulties=difficulties,
        thresholds=load_thresholds("v0.1"),
    )
```

with:

```python
        seed=seed,
        cases=cases,
        difficulties=difficulties,
        thresholds=load_thresholds(policy_version),
        generator_version=generator_version,
        policy_version=policy_version,
    )
```

In `relay/generation/generator.py`, replace:

```python

    Returns a list of problems; an empty list means the dataset verifies.
    """
    if manifest.generator_version != GENERATOR_VERSION:
        return [
            f"manifest was produced by {manifest.generator_version}, "
            f"but this code is {GENERATOR_VERSION}"
        ]
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        regenerated = generate_dataset(
            manifest.count, manifest.seed, manifest.dataset_id, Path(tmp) / manifest.dataset_id
        )
    if regenerated != manifest:
        problems.append(
```

with:

```python

    Returns a list of problems; an empty list means the dataset verifies.
    """
    if manifest.generator_version not in GENERATOR_VERSIONS:
        return [
            f"manifest was produced by {manifest.generator_version}, "
            f"but this code generates {', '.join(GENERATOR_VERSIONS)}"
        ]
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        regenerated = generate_dataset(
            manifest.count,
            manifest.seed,
            manifest.dataset_id,
            Path(tmp) / manifest.dataset_id,
            generator_version=manifest.generator_version,
            policy_version=manifest.policy_version,
        )
    if regenerated != manifest:
        problems.append(
```

In `relay/generation/manifest.py`, replace:

```python
from relay.cases.models import PriorAuthCase
from relay.cases.policies import load_policy
from relay.evaluation.labels import expected_action
from relay.generation.facts import GENERATOR_VERSION
from relay.workflow.thresholds import Thresholds

MANIFEST_DIR = Path("evals/generated/manifests")
```

with:

```python
from relay.cases.models import PriorAuthCase
from relay.cases.policies import load_policy
from relay.evaluation.labels import expected_action
from relay.generation.facts import GEN_V0_2
from relay.workflow.thresholds import Thresholds

MANIFEST_DIR = Path("evals/generated/manifests")
```

In `relay/generation/manifest.py`, replace:

```python
    expected_action_counts: dict[str, int]
    missing_evidence_counts: dict[str, int]
    dataset_hash: str


def dataset_hash(cases: Sequence[PriorAuthCase]) -> str:
```

with:

```python
    expected_action_counts: dict[str, int]
    missing_evidence_counts: dict[str, int]
    dataset_hash: str
    # Phase 3D: the policy version every case uses (gen-v0.3-shift is v0.2). Written only when it
    # is not v0.1, so the committed gen-v0.2 manifests stay byte-identical.
    policy_version: str = "v0.1"


def dataset_hash(cases: Sequence[PriorAuthCase]) -> str:
```

In `relay/generation/manifest.py`, replace:

```python
    cases: Sequence[PriorAuthCase],
    difficulties: Sequence[str],
    thresholds: Thresholds,
) -> DatasetManifest:
    actions = [expected_action(c, load_policy(c.input.policy_id), thresholds).value for c in cases]
    return DatasetManifest(
        dataset_id=dataset_id,
        generator_version=GENERATOR_VERSION,
        seed=seed,
        count=len(cases),
        difficulty_counts=_sorted_counts(difficulties),
```

with:

```python
    cases: Sequence[PriorAuthCase],
    difficulties: Sequence[str],
    thresholds: Thresholds,
    generator_version: str = GEN_V0_2,
    policy_version: str = "v0.1",
) -> DatasetManifest:
    actions = [expected_action(c, load_policy(c.input.policy_id), thresholds).value for c in cases]
    return DatasetManifest(
        dataset_id=dataset_id,
        generator_version=generator_version,
        seed=seed,
        count=len(cases),
        difficulty_counts=_sorted_counts(difficulties),
```

In `relay/generation/manifest.py`, replace:

```python
            [c.ground_truth.missing_evidence.value for c in cases]
        ),
        dataset_hash=dataset_hash(cases),
    )


def write_manifest(manifest: DatasetManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")


def read_manifest(path: Path) -> DatasetManifest:
```

with:

```python
            [c.ground_truth.missing_evidence.value for c in cases]
        ),
        dataset_hash=dataset_hash(cases),
        policy_version=policy_version,
    )


def write_manifest(manifest: DatasetManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exclude = {"policy_version"} if manifest.policy_version == "v0.1" else None
    text = manifest.model_dump_json(indent=2, exclude=exclude)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def read_manifest(path: Path) -> DatasetManifest:
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run pytest -q tests/integration/test_cli_generate.py tests/unit/test_generation_audit.py tests/unit/test_generator.py`

Expected: PASS.

- [ ] **Step 5: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`

Expected: all pass (about 1175 passed).

Re-run the two gen-v0.2 `--verify` commands from Task 6 Step 5 (both `OK:`). Then generate the three gen-v0.3 datasets into a scratch directory, to check that the generator runs end to end and matches the planning hashes. Don't commit anything here: the committed manifests are written in plan 3D2, Task 1.

```bash
S=$(mktemp -d)
R() { env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env "$@"; }
R generate --generator gen-v0.3 --count 400 --seed 3 --dataset-id gen-v0.3-dev --out "$S/gen-v0.3-dev" --manifests-dir "$S/m"
R generate --generator gen-v0.3 --count 1000 --seed 4 --dataset-id gen-v0.3-holdout --out "$S/gen-v0.3-holdout" --manifests-dir "$S/m"
R generate --generator gen-v0.3 --policy v0.2 --count 400 --seed 5 --dataset-id gen-v0.3-shift --out "$S/gen-v0.3-shift" --manifests-dir "$S/m"
```

Expected dataset hashes and expected actions (auto / request info / review), from planning:
- `gen-v0.3-dev`: `sha256:ae3dc2f88e0966889aee2193dc822bee3389ade3ffce85641a9f59495557d5ad`, 122 / 93 / 185
- `gen-v0.3-holdout`: `sha256:2aefa63d082a957ea035a9b21ae9ca283ba5e47eb3ceeedc342250118c1d99e5`, 265 / 269 / 466
- `gen-v0.3-shift`: `sha256:3f5a9c1cad24cf0ddd8c446999bc4c5e382503c65f1a6d8c54a8a2daf9710e53`, 85 / 99 / 216

A different hash means the generator code differs from this plan somewhere; find the difference before continuing. Remove the scratch directory afterwards (`rm -r "$S"`: it is a temp dir you created, holding nothing else).

- [ ] **Step 6: Commit**

```bash
git add relay/cli.py relay/generation/generator.py relay/generation/manifest.py tests/integration/test_cli_generate.py tests/unit/test_generation_audit.py tests/unit/test_generator.py
git commit -m "feat: generate gen-v0.3 and policy-v0.2 datasets with relay generate --generator/--policy" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 9: The Jev spend counter and `relay eval --jev-budget-usd/--jev-ledger`

**Files:**
- Create: `relay/evaluation/jev_spend.py`
- Modify: `relay/cli.py`
- Modify: `relay/evaluation/budget.py`
- Test (create): `tests/integration/test_cli_jev_spend.py`
- Test (create): `tests/unit/test_jev_spend.py`

**Interfaces:**
- Consumes: `question_ids(version)` (Task 3); `SpendLedger`, `reserve`, `settle`, `check_budget`, `load_ledger`, `write_ledger`, `BudgetExceeded` (`relay/evaluation/budget.py`); the post-3C `_run_provider(..., mode)` / `_execute(..., mode)` in `relay/cli.py`.
- Produces:
  - `relay/evaluation/budget.py`: `BudgetExceeded(spent, projected, budget, label="Claude")` and `check_budget(ledger, projected, budget, *, label="Claude")`. Claude messages are unchanged.
  - `relay/evaluation/jev_spend.py`: `DEFAULT_JEV_LEDGER = Path("results/jev-spend-3d.json")`, `JEV_ESTIMATE_PER_QUESTION_USD = Decimal("0.000013")`, `JEV_MIN_BILLED_QUESTIONS = 12`, `JevBudget(budget_usd: Decimal, ledger: Path)`, `estimate_jev_cost(cases, questions_per_case) -> Decimal`, `estimate_line(cases, questions, estimate) -> str`, `check_jev_budget`, `reserve_jev`, `settle_jev`.
  - `relay/cli.py`: `_resolve_jev(provider, budget_usd, ledger) -> JevBudget | None`, `_load_jev_ledger`, `_jev_budget_check(jev, cases, questions, estimate)`, `_jev_reserve(jev, run_id, dataset_id, cases, estimate)`, `_jev_settle(jev, run_id, traces | None)`; `_execute(..., mode, jev=None, jev_estimate=Decimal("0"))`, `_run_provider(..., mode, jev=None)`, `_run_and_report(..., claude, jev=None)`. `relay eval` gains `--jev-budget-usd` and `--jev-ledger`.

Before any call, a counted run prints `jev estimate: N cases × Q questions ≈ $X` and `Jev budget: spent $S of the $C cap (LEDGER)`. It refuses with exit 2 (`Jev budget exceeded: …`) when S + X > C, and S includes open reservations. It then reserves X under the run id and settles at the traces' summed `estimated_cost_usd`: at the end of a normal run, or on failure from the partial trace file, as for a Claude sync run. The estimate rate is the largest measured per-case cost among the committed Jev runs ($0.000126882 for 12 questions, gold-v0.1) divided by 12, × 1.25, rounded up to $0.000013 per question. Each call is priced as at least 12 questions, because a call pays for its state however few questions it asks. `results/claude-spend.json` is never read or written: tests use tmp ledgers, and the Jev default is its own file.

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_cli_jev_spend.py`:

```python
"""relay eval --jev-budget-usd / --jev-ledger: the Phase 3D Jev spend counter (fake client)."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner
from typesafe_sdk import SystemOneResponse

import relay.cli as cli_module
from relay.cli import app
from relay.evaluation.budget import load_ledger, reserve, write_ledger

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
FIXTURE = REPO / "tests" / "fixtures" / "jev" / "auto01_response.json"
runner = CliRunner()


class FakeAsyncClient:
    """Answers every case with the AUTO-01 fixture (1,800 input tokens: $0.0000756 a case)."""

    calls = 0

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def system_one(self, state, questions, *, model=None, **kwargs):
        FakeAsyncClient.calls += 1
        return SystemOneResponse.model_validate(json.loads(FIXTURE.read_text()))


@pytest.fixture
def fake_jev(monkeypatch):
    FakeAsyncClient.calls = 0
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", FakeAsyncClient)
    return FakeAsyncClient


def eval_jev(tmp_path, *extra, provider="jev"):
    return runner.invoke(
        app,
        [
            "--env-file",
            str(tmp_path / "missing.env"),
            "eval",
            "--dataset",
            str(SMOKE),
            "--provider",
            provider,
            "--traces-dir",
            str(tmp_path / "traces"),
            "--reports-dir",
            str(tmp_path / "reports"),
            "--results-dir",
            str(tmp_path / "results"),
            *extra,
        ],
    )


def test_a_counted_run_prints_the_estimate_reserves_and_settles(tmp_path, fake_jev):
    ledger = tmp_path / "jev-spend.json"
    result = eval_jev(tmp_path, "--jev-budget-usd", "1.00", "--jev-ledger", str(ledger))
    assert result.exit_code == 0, result.output
    # 10 smoke cases x 12 questions x $0.000013
    assert "jev estimate: 10 cases × 12 questions ≈ $0.0016" in result.output
    assert "Jev budget: spent $0.0000 of the $1.00 cap" in result.output
    [entry] = load_ledger(ledger).entries
    assert (entry.status, entry.mode, entry.cases, entry.dataset_id) == (
        "settled",
        "sync",
        10,
        "smoke-v0.1",
    )
    assert entry.cost_usd == Decimal("0.000756")  # 10 x 1,800 tokens x $0.042 / 1M
    assert "Jev spend: this run $0.0008; total $0.0008 of the $1.00 cap" in result.output


def test_q_v0_3_estimates_nineteen_questions(tmp_path, fake_jev):
    result = eval_jev(
        tmp_path,
        "--questions",
        "q-v0.3",
        "--jev-budget-usd",
        "1.00",
        "--jev-ledger",
        str(tmp_path / "l.json"),
    )
    # The fake answers only the 12 q-v0.2 questions, so every bundle is malformed; the counter
    # still prints the estimate first and settles what the calls cost.
    assert "jev estimate: 10 cases × 19 questions ≈ $0.0025" in result.output


def test_the_counter_refuses_a_run_over_the_cap_before_any_call(tmp_path, fake_jev):
    ledger = tmp_path / "jev-spend.json"
    earlier = reserve(
        load_ledger(ledger),
        run_id="run_earlier",
        dataset_id="gen-v0.3-dev",
        mode="sync",
        cases=400,
        projected=Decimal("0.9990"),
    )
    write_ledger(ledger, earlier)
    result = eval_jev(tmp_path, "--jev-budget-usd", "1.00", "--jev-ledger", str(ledger))
    assert result.exit_code == 2
    assert "jev estimate: 10 cases × 12 questions ≈ $0.0016" in result.output
    assert (
        "Jev budget exceeded: spent $0.9990 + projected $0.0016 = $1.0006, over the $1.00 budget"
    ) in result.output
    assert fake_jev.calls == 0
    assert len(load_ledger(ledger).entries) == 1
    assert not (tmp_path / "traces").exists() or not list((tmp_path / "traces").iterdir())


def test_the_default_ledger_is_results_jev_spend_3d(tmp_path, fake_jev, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = eval_jev(tmp_path, "--jev-budget-usd", "1.00")
    assert result.exit_code == 0, result.output
    assert (tmp_path / "results" / "jev-spend-3d.json").exists()
    assert not (tmp_path / "results" / "claude-spend.json").exists()


def test_a_failed_run_settles_what_was_written(tmp_path, fake_jev, monkeypatch):
    ledger = tmp_path / "jev-spend.json"

    async def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(cli_module, "run_dataset", boom)
    result = eval_jev(tmp_path, "--jev-budget-usd", "1.00", "--jev-ledger", str(ledger))
    assert result.exit_code != 0
    [entry] = load_ledger(ledger).entries
    assert (entry.status, entry.cost_usd) == ("settled", Decimal("0"))


@pytest.mark.parametrize(
    "extra,provider,message",
    [
        (["--jev-budget-usd", "1"], "rules", "--jev-budget-usd applies only to --provider jev"),
        (["--jev-ledger", "x.json"], "groundtruth", "--jev-ledger applies only to --provider jev"),
        (["--jev-ledger", "x.json"], "jev", "--jev-ledger needs --jev-budget-usd"),
    ],
)
def test_misused_flags_are_exit_2(tmp_path, fake_jev, extra, provider, message):
    result = eval_jev(tmp_path, *extra, provider=provider)
    assert result.exit_code == 2
    assert message in result.output
    assert fake_jev.calls == 0


def test_the_counter_does_not_apply_to_re_scoring(tmp_path, fake_jev):
    assert eval_jev(tmp_path).exit_code == 0
    [trace_file] = (tmp_path / "traces").glob("*.jsonl")
    result = eval_jev(tmp_path, "--traces", str(trace_file), "--jev-budget-usd", "1")
    assert result.exit_code == 2
    assert "need a run, not --traces" in result.output
```

Create `tests/unit/test_jev_spend.py`:

```python
"""The Jev spend counter: estimate, cap check, reserve and settle on a tmp ledger."""

from decimal import Decimal

import pytest

from relay.evaluation.budget import BudgetExceeded, load_ledger, write_ledger
from relay.evaluation.jev_spend import (
    DEFAULT_JEV_LEDGER,
    JEV_ESTIMATE_PER_QUESTION_USD,
    check_jev_budget,
    estimate_jev_cost,
    estimate_line,
    reserve_jev,
    settle_jev,
)


def test_default_ledger_is_its_own_file_never_the_claude_ledger():
    assert DEFAULT_JEV_LEDGER.as_posix() == "results/jev-spend-3d.json"


def test_estimate_is_cases_times_questions_with_a_twelve_question_floor():
    assert JEV_ESTIMATE_PER_QUESTION_USD == Decimal("0.000013")
    assert estimate_jev_cost(400, 19) == Decimal("0.098800")
    assert estimate_jev_cost(1000, 12) == Decimal("0.156000")
    assert estimate_jev_cost(40, 1) == estimate_jev_cost(40, 12) == Decimal("0.006240")
    assert estimate_jev_cost(40, 20) == Decimal("0.010400")


def test_estimate_line_format():
    assert estimate_line(400, 19, Decimal("0.0988")) == (
        "jev estimate: 400 cases × 19 questions ≈ $0.0988"
    )


def test_reserve_check_and_settle_on_a_tmp_ledger(tmp_path):
    path = tmp_path / "jev-spend.json"
    ledger = load_ledger(path)  # a missing file is an empty ledger
    check_jev_budget(ledger, Decimal("0.5"), Decimal("1.00"))
    ledger = reserve_jev(
        ledger, run_id="run_a", dataset_id="gen-v0.3-dev", cases=400, estimate=Decimal("0.0988")
    )
    write_ledger(path, ledger)
    [entry] = load_ledger(path).entries
    assert (entry.status, entry.mode, entry.cost_usd) == ("reserved", "sync", Decimal("0.0988"))
    ledger = settle_jev(load_ledger(path), "run_a", Decimal("0.0712"))
    write_ledger(path, ledger)
    assert load_ledger(path).spent_usd == Decimal("0.0712")


def test_the_cap_counts_reservations_and_names_jev(tmp_path):
    ledger = reserve_jev(
        load_ledger(tmp_path / "none.json"),
        run_id="run_a",
        dataset_id="d",
        cases=1,
        estimate=Decimal("0.95"),
    )
    with pytest.raises(BudgetExceeded) as caught:
        check_jev_budget(ledger, Decimal("0.06"), Decimal("1.00"))
    assert str(caught.value) == (
        "Jev budget exceeded: spent $0.9500 + projected $0.0600 = $1.0100, over the $1.00 budget"
    )
    check_jev_budget(ledger, Decimal("0.05"), Decimal("1.00"))  # exactly at the cap is allowed
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run: `uv run pytest -q tests/integration/test_cli_jev_spend.py tests/unit/test_jev_spend.py`

Expected: FAIL. `ModuleNotFoundError: No module named 'relay.evaluation.jev_spend'`, and the CLI rejects `--jev-budget-usd`.

- [ ] **Step 3: Implement**

In `relay/cli.py`, replace:

```python
from relay.decisions.claude_prompt import CLAUDE_QUESTION_SETS
from relay.decisions.ground_truth import GroundTruthProvider
from relay.decisions.jev import JevProvider
from relay.decisions.questions import DEFAULT_QUESTION_SET_VERSION, Q_V0_2, QUESTION_SET_VERSIONS
from relay.decisions.rules_baseline import RulesBaselineProvider
from relay.evaluation.artifacts import write_eval_bundle
from relay.evaluation.budget import (
```

with:

```python
from relay.decisions.claude_prompt import CLAUDE_QUESTION_SETS
from relay.decisions.ground_truth import GroundTruthProvider
from relay.decisions.jev import JevProvider
from relay.decisions.questions import (
    DEFAULT_QUESTION_SET_VERSION,
    Q_V0_2,
    QUESTION_SET_VERSIONS,
    question_ids,
)
from relay.decisions.rules_baseline import RulesBaselineProvider
from relay.evaluation.artifacts import write_eval_bundle
from relay.evaluation.budget import (
```

In `relay/cli.py`, replace:

```python
from relay.evaluation.compare import compare_runs
from relay.evaluation.confusion import confusion_matrices
from relay.evaluation.frontier import DEFAULT_CEILING, frontier_csv, run_sweep
from relay.evaluation.metrics import EvalError, paired_cases, run_identity, score_run
from relay.evaluation.regression import RegressionResult
from relay.evaluation.regression_run import (
```

with:

```python
from relay.evaluation.compare import compare_runs
from relay.evaluation.confusion import confusion_matrices
from relay.evaluation.frontier import DEFAULT_CEILING, frontier_csv, run_sweep
from relay.evaluation.jev_spend import (
    DEFAULT_JEV_LEDGER,
    JevBudget,
    check_jev_budget,
    estimate_jev_cost,
    estimate_line,
    reserve_jev,
    settle_jev,
)
from relay.evaluation.metrics import EvalError, paired_cases, run_identity, score_run
from relay.evaluation.regression import RegressionResult
from relay.evaluation.regression_run import (
```

In `relay/cli.py`, replace:

```python
BatchId = Annotated[
    str | None,
    typer.Option(help="claude --mode batch only: re-attach to this submitted Message Batch."),
]

TraceFile = Annotated[
```

with:

```python
BatchId = Annotated[
    str | None,
    typer.Option(help="claude --mode batch only: re-attach to this submitted Message Batch."),
]

JevBudgetUsd = Annotated[
    float | None,
    typer.Option(
        min=0.0,
        help="jev only: the Jev spend counter. Print the estimate and refuse to start if the "
        "ledger's Jev spend + the estimate exceeds this cap.",
    ),
]
JevLedgerOption = Annotated[
    Path | None,
    typer.Option(help=f"jev only: Jev spend ledger (default {DEFAULT_JEV_LEDGER})."),
]

TraceFile = Annotated[
```

In `relay/cli.py`, replace:

```python
    return False


def _preflight(cases: list[PriorAuthCase], provider: ProviderName, policy: str) -> None:
    try:
        validate_run_config(cases, policy)
```

with:

```python
    return False


def _resolve_jev(
    provider: ProviderName, budget_usd: float | None, ledger: Path | None
) -> JevBudget | None:
    """The Jev spend counter's settings, or None when --jev-budget-usd is not given.

    Both flags need --provider jev, and --jev-ledger needs --jev-budget-usd.
    """
    given = [
        flag
        for flag, value in (("--jev-budget-usd", budget_usd), ("--jev-ledger", ledger))
        if value is not None
    ]
    if given and provider is not ProviderName.jev:
        raise _fail(f"{', '.join(given)} applies only to --provider jev")
    if budget_usd is None:
        if ledger is not None:
            raise _fail("--jev-ledger needs --jev-budget-usd")
        return None
    return JevBudget(
        budget_usd=Decimal(str(budget_usd)),
        ledger=DEFAULT_JEV_LEDGER if ledger is None else ledger,
    )


def _load_jev_ledger(jev: JevBudget) -> SpendLedger:
    try:
        return load_ledger(jev.ledger)
    except (ValidationError, OSError) as error:
        raise _fail(f"{jev.ledger}: {error}") from error


def _jev_budget_check(jev: JevBudget, cases: int, questions: int | str, estimate: Decimal) -> None:
    """Print the estimate and the ledger's spend; exit 2 if the run could break the cap."""
    ledger = _load_jev_ledger(jev)
    typer.echo(estimate_line(cases, questions, estimate))
    typer.echo(
        f"Jev budget: spent ${ledger.spent_usd:.4f} of the ${jev.budget_usd:.2f} cap ({jev.ledger})"
    )
    try:
        check_jev_budget(ledger, estimate, jev.budget_usd)
    except BudgetExceeded as error:
        raise _fail(str(error)) from error


def _jev_reserve(
    jev: JevBudget, run_id: str, dataset_id: str, cases: int, estimate: Decimal
) -> None:
    ledger = reserve_jev(
        _load_jev_ledger(jev),
        run_id=run_id,
        dataset_id=dataset_id,
        cases=cases,
        estimate=estimate,
    )
    write_ledger(jev.ledger, ledger)


def _jev_settle(jev: JevBudget, run_id: str, traces: list[WorkflowTrace] | None) -> None:
    """Settle at the traces' summed estimated cost. None (an unreadable partial trace file)
    leaves the reservation counted, as for a Claude sync run."""
    if traces is None:
        typer.echo(
            f"error: Jev run {run_id}'s trace file could not be parsed; its reservation stays "
            f"counted in {jev.ledger} until this is resolved by hand.",
            err=True,
        )
        return
    actual = sum((t.decisions.estimated_cost_usd or Decimal("0") for t in traces), Decimal("0"))
    ledger = settle_jev(_load_jev_ledger(jev), run_id, actual)
    write_ledger(jev.ledger, ledger)
    typer.echo(
        f"Jev spend: this run ${actual:.4f}; total ${ledger.spent_usd:.4f} of the "
        f"${jev.budget_usd:.2f} cap ({jev.ledger})"
    )


def _preflight(cases: list[PriorAuthCase], provider: ProviderName, policy: str) -> None:
    try:
        validate_run_config(cases, policy)
```

In `relay/cli.py`, replace:

```python
    claude: ClaudeRun | None = None,
    projected: Decimal = Decimal("0"),
    mode: WorkflowMode = "evaluate",
) -> tuple[RunManifest, list[WorkflowTrace]]:
    run_id = new_run_id()
    store = TraceStore.create(traces_dir, run_id)
    git_sha = current_git_sha()
    on_submitted = None
    if claude is not None:
        _reserve(claude, run_id, cases, projected)
```

with:

```python
    claude: ClaudeRun | None = None,
    projected: Decimal = Decimal("0"),
    mode: WorkflowMode = "evaluate",
    jev: JevBudget | None = None,
    jev_estimate: Decimal = Decimal("0"),
) -> tuple[RunManifest, list[WorkflowTrace]]:
    run_id = new_run_id()
    store = TraceStore.create(traces_dir, run_id)
    git_sha = current_git_sha()
    on_submitted = None
    if jev is not None:
        _jev_reserve(jev, run_id, cases[0].input.dataset_id, len(cases), jev_estimate)
    if claude is not None:
        _reserve(claude, run_id, cases, projected)
```

In `relay/cli.py`, replace:

```python
                and _is_ambiguous_submission_error(error)
            )
            _settle_interrupted(claude, run_id, store, batch_id, ambiguous_submission=ambiguous)
        if store.path.exists() and store.path.stat().st_size == 0:
            store.path.unlink()
        raise
    if claude is not None:
        batch_id = getattr(provider, "batch_id", None) or claude.batch_id
        _settle(claude, run_id, traces, batch_id, collected=True)
    manifest = RunManifest(
        run_id=run_id,
        created_at=datetime.now(UTC),
```

with:

```python
                and _is_ambiguous_submission_error(error)
            )
            _settle_interrupted(claude, run_id, store, batch_id, ambiguous_submission=ambiguous)
        if jev is not None:
            _jev_settle(jev, run_id, _partial_traces(store))
        if store.path.exists() and store.path.stat().st_size == 0:
            store.path.unlink()
        raise
    if claude is not None:
        batch_id = getattr(provider, "batch_id", None) or claude.batch_id
        _settle(claude, run_id, traces, batch_id, collected=True)
    if jev is not None:
        _jev_settle(jev, run_id, traces)
    manifest = RunManifest(
        run_id=run_id,
        created_at=datetime.now(UTC),
```

In `relay/cli.py`, replace:

```python
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
```

with:

```python
    sample: tuple[int, int] | None = None,
    claude: ClaudeRun | None = None,
    mode: WorkflowMode = "evaluate",
    jev: JevBudget | None = None,
) -> tuple[RunManifest, list[WorkflowTrace]]:
    """A provider run with every guard: question set, policy and key preflight, the Claude budget
    check and ledger, the Jev spend counter (with jev), and the provider's NOTE."""
    resolved = _resolve_questions(provider, questions)
    _preflight(cases, provider, policy)
    projected = _claude_budget_check(claude, cases) if claude is not None else Decimal("0")
    jev_estimate = Decimal("0")
    if jev is not None:
        assert resolved is not None  # _resolve_jev allows the counter only for --provider jev
        per_case = len(question_ids(resolved))
        jev_estimate = estimate_jev_cost(len(cases), per_case)
        _jev_budget_check(jev, len(cases), per_case, jev_estimate)
    if provider in PROVIDER_NOTES:
        typer.echo(f"NOTE: {PROVIDER_NOTES[provider]}")
    return asyncio.run(
```

In `relay/cli.py`, replace:

```python
            claude,
            projected,
            mode,
        )
    )
```

with:

```python
            claude,
            projected,
            mode,
            jev,
            jev_estimate,
        )
    )
```

In `relay/cli.py`, replace:

```python
    questions: str | None,
    sample: tuple[int, int] | None = None,
    claude: ClaudeRun | None = None,
) -> list[WorkflowTrace]:
    manifest, traces = _run_provider(
        cases, provider, policy, concurrency, traces_dir, dataset, questions, sample, claude
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{manifest.run_id}.md"
```

with:

```python
    questions: str | None,
    sample: tuple[int, int] | None = None,
    claude: ClaudeRun | None = None,
    jev: JevBudget | None = None,
) -> list[WorkflowTrace]:
    manifest, traces = _run_provider(
        cases,
        provider,
        policy,
        concurrency,
        traces_dir,
        dataset,
        questions,
        sample,
        claude,
        jev=jev,
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{manifest.run_id}.md"
```

In `relay/cli.py`, replace:

```python
    budget_usd: BudgetUsd = None,
    ledger: LedgerOption = None,
    batch_id: BatchId = None,
) -> None:
    """Run (or re-score) DATASET and print action-level and decision-level metrics."""
    cases, sample = _apply_limit(_load_cases(dataset), limit, sample_seed)
    if traces is None:
        claude = _resolve_claude(provider, mode, budget_usd, ledger, batch_id)
        trace_list = _run_and_report(
            cases,
            provider,
```

with:

```python
    budget_usd: BudgetUsd = None,
    ledger: LedgerOption = None,
    batch_id: BatchId = None,
    jev_budget_usd: JevBudgetUsd = None,
    jev_ledger: JevLedgerOption = None,
) -> None:
    """Run (or re-score) DATASET and print action-level and decision-level metrics."""
    cases, sample = _apply_limit(_load_cases(dataset), limit, sample_seed)
    if traces is None:
        claude = _resolve_claude(provider, mode, budget_usd, ledger, batch_id)
        jev = _resolve_jev(provider, jev_budget_usd, jev_ledger)
        trace_list = _run_and_report(
            cases,
            provider,
```

In `relay/cli.py`, replace:

```python
            questions,
            sample,
            claude,
        )
    else:
        trace_list = _read_trace_file(traces)
    try:
        summary = score_run(trace_list, cases)
```

with:

```python
            questions,
            sample,
            claude,
            jev,
        )
    else:
        if jev_budget_usd is not None or jev_ledger is not None:
            raise _fail("--jev-budget-usd and --jev-ledger need a run, not --traces")
        trace_list = _read_trace_file(traces)
    try:
        summary = score_run(trace_list, cases)
```

In `relay/evaluation/budget.py`, replace:

```python


class BudgetExceeded(Exception):
    def __init__(self, spent: Decimal, projected: Decimal, budget: Decimal) -> None:
        self.spent, self.projected, self.budget = spent, projected, budget
        super().__init__(
            f"Claude budget exceeded: spent ${spent:.4f} + projected ${projected:.4f} "
            f"= ${spent + projected:.4f}, over the ${budget:.2f} budget"
        )
```

with:

```python


class BudgetExceeded(Exception):
    def __init__(
        self, spent: Decimal, projected: Decimal, budget: Decimal, label: str = "Claude"
    ) -> None:
        self.spent, self.projected, self.budget = spent, projected, budget
        super().__init__(
            f"{label} budget exceeded: spent ${spent:.4f} + projected ${projected:.4f} "
            f"= ${spent + projected:.4f}, over the ${budget:.2f} budget"
        )
```

In `relay/evaluation/budget.py`, replace:

```python
    return cost * BATCH_DISCOUNT if mode == "batch" else cost


def check_budget(ledger: SpendLedger, projected: Decimal, budget: Decimal) -> None:
    if ledger.spent_usd + projected > budget:
        raise BudgetExceeded(ledger.spent_usd, projected, budget)


def reserve(
```

with:

```python
    return cost * BATCH_DISCOUNT if mode == "batch" else cost


def check_budget(
    ledger: SpendLedger, projected: Decimal, budget: Decimal, *, label: str = "Claude"
) -> None:
    """BudgetExceeded (its message names `label`) if spend plus `projected` exceeds `budget`."""
    if ledger.spent_usd + projected > budget:
        raise BudgetExceeded(ledger.spent_usd, projected, budget, label)


def reserve(
```

Create `relay/evaluation/jev_spend.py`:

```python
"""The Phase 3D Jev spend counter: an estimate before every paid Jev run, and a small ledger.

It reuses the Claude ledger machinery in relay.evaluation.budget (SpendLedger, reserve, settle,
check_budget) on its own file, results/jev-spend-3d.json by default, so Jev spend is never mixed
with results/claude-spend.json. Jev calls are synchronous, so every entry has mode "sync".

Estimate: cases x questions per case x JEV_ESTIMATE_PER_QUESTION_USD, with every call priced as
at least JEV_MIN_BILLED_QUESTIONS questions. The rate is the largest measured per-case cost of the
committed Jev runs ($0.000127 for 12 questions, gold-v0.1), divided by 12, times 1.25 and rounded
up. The floor exists because a call pays for its state (policy and documents) however few
questions it asks, which matters for relay bench's 1- and 5-question calls.
"""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from relay.evaluation.budget import SpendLedger, check_budget, reserve, settle

DEFAULT_JEV_LEDGER = Path("results/jev-spend-3d.json")
JEV_ESTIMATE_PER_QUESTION_USD = Decimal("0.000013")
JEV_MIN_BILLED_QUESTIONS = 12
JEV_LABEL = "Jev"


@dataclass(frozen=True)
class JevBudget:
    """--jev-budget-usd and --jev-ledger: the cap on the ledger's total Jev spend."""

    budget_usd: Decimal
    ledger: Path


def estimate_jev_cost(cases: int, questions_per_case: int) -> Decimal:
    """The pre-run estimate for `cases` calls of `questions_per_case` questions each."""
    billed = max(questions_per_case, JEV_MIN_BILLED_QUESTIONS)
    return JEV_ESTIMATE_PER_QUESTION_USD * cases * billed


def estimate_line(cases: int, questions: int | str, estimate: Decimal) -> str:
    """'jev estimate: 400 cases × 19 questions ≈ $0.0988' (printed before every paid run)."""
    return f"jev estimate: {cases} cases × {questions} questions ≈ ${estimate:.4f}"


def check_jev_budget(ledger: SpendLedger, estimate: Decimal, budget: Decimal) -> None:
    """BudgetExceeded ("Jev budget exceeded: ...") if the ledger's spend (settled costs plus open
    reservations) plus `estimate` would exceed `budget`."""
    check_budget(ledger, estimate, budget, label=JEV_LABEL)


def reserve_jev(
    ledger: SpendLedger, *, run_id: str, dataset_id: str, cases: int, estimate: Decimal
) -> SpendLedger:
    return reserve(
        ledger, run_id=run_id, dataset_id=dataset_id, mode="sync", cases=cases, projected=estimate
    )


def settle_jev(ledger: SpendLedger, run_id: str, actual: Decimal) -> SpendLedger:
    return settle(ledger, run_id, actual)
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run pytest -q tests/integration/test_cli_jev_spend.py tests/unit/test_jev_spend.py`

Expected: PASS.

- [ ] **Step 5: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`

Expected: all pass (about 1189 passed).

- [ ] **Step 6: Commit**

```bash
git add relay/cli.py relay/evaluation/budget.py relay/evaluation/jev_spend.py tests/integration/test_cli_jev_spend.py tests/unit/test_jev_spend.py
git commit -m "feat: add the Jev spend counter and relay eval --jev-budget-usd/--jev-ledger" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 10: `relay recompose`

**Files:**
- Create: `relay/evaluation/recompose_run.py`
- Modify: `relay/cli.py`
- Test (create): `tests/integration/test_cli_recompose.py`

**Interfaces:**
- Consumes: `recompose` (Task 5); `paired_cases` (`relay.evaluation.metrics`); `policy_text_hash` (`relay.evaluation.runner`); `replay_thresholds` (`relay.evaluation.tracediff`); `find_run_manifest`, `RegressionInputError` (`relay.evaluation.regression_run`); `MalformedAnswers` (`relay.decisions.composition`); `_policy`, `_load_cases`, `_read_trace_file`, `_fail` (`relay/cli.py`).
- Produces:
  - `relay/evaluation/recompose_run.py`: `recompose_run(traces, cases, *, policy, run_id=None, now=None, git_sha=None) -> list[WorkflowTrace]` (mode "simulated", one new run id, `replay_of` = source trace id, thresholds from `replay_thresholds`), `changed_counts(source, recomposed) -> tuple[int, int]`, `write_simulated_bundle(out, traces, *, dataset, source, source_manifest=None) -> tuple[Path, Path]` writing `out/traces.jsonl.gz` and `out/run-manifest.json` (`mode="simulated"`, `source_run_id`, extra keys `policy_id` and `thresholds`), refusing a non-empty `out`.
  - CLI: `relay recompose --traces FILE --dataset DIR --policy ID --out DIR`. It prints `Recomposed N traces of run R (jev q-v0.3) under policy P (vX), thresholds T: step_therapy changed on K case(s), action changed on M case(s).`, then `Simulated run: …`, `Traces: …`, `Manifest: …`. Exit 2 on any input problem.

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_cli_recompose.py`:

```python
"""relay recompose: stale and aware simulated runs from one stored Jev run (fake client)."""

import json

import pytest
from typer.testing import CliRunner
from typesafe_sdk import SystemOneResponse

import relay.cli as cli_module
from relay.cli import app
from relay.decisions.base import DecisionId
from relay.generation.generator import generate_dataset
from relay.traces.models import RunManifest
from relay.traces.store import read_traces
from tests.jev_fakes import q_v0_3_payload, raw_date

runner = CliRunner()


def old_course_payload():
    """Methotrexate 2025-01-13 -> 2025-06-02 (140 days, ended well over a year before every
    gen-v0.3 as-of date), inadequate response 0.97, not interrupted."""
    return q_v0_3_payload(
        **raw_date("mtx_start", "January", "13", "2025"),
        **raw_date("mtx_end", "June", "2", "2025"),
    )


class FakeAsyncClient:
    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def system_one(self, state, questions, *, model=None, **kwargs):
        return SystemOneResponse.model_validate(old_course_payload())


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--env-file", str(tmp_path / "missing.env"), *args])


@pytest.fixture
def shift_run(tmp_path, monkeypatch):
    """An 8-case gen-v0.3 dataset under immunara-v0.2 and one fake q-v0.3 Jev run on it."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", FakeAsyncClient)
    dataset = tmp_path / "shift"
    generate_dataset(
        8, 5, "gen-shift", dataset, generator_version="gen-v0.3", policy_version="v0.2"
    )
    result = invoke(
        tmp_path,
        "eval",
        "--dataset",
        str(dataset),
        "--provider",
        "jev",
        "--questions",
        "q-v0.3",
        "--policy",
        "v0.2",
        "--traces-dir",
        str(tmp_path / "traces"),
        "--reports-dir",
        str(tmp_path / "reports"),
        "--results-dir",
        str(tmp_path / "results"),
    )
    assert result.exit_code == 0, result.output
    [trace_file] = (tmp_path / "traces").glob("*.jsonl")
    return dataset, trace_file


def recompose(tmp_path, dataset, trace_file, policy, name):
    return invoke(
        tmp_path,
        "recompose",
        "--traces",
        str(trace_file),
        "--dataset",
        str(dataset),
        "--policy",
        policy,
        "--out",
        str(tmp_path / name),
    )


def step(trace):
    return trace.decisions.get(DecisionId.STEP_THERAPY).p_yes


def test_stale_and_aware_from_one_run(tmp_path, shift_run):
    dataset, trace_file = shift_run
    source = read_traces(trace_file)
    stale_result = recompose(tmp_path, dataset, trace_file, "immunara-v0.1", "stale")
    aware_result = recompose(tmp_path, dataset, trace_file, "immunara-v0.2", "aware")
    assert stale_result.exit_code == 0, stale_result.output
    assert aware_result.exit_code == 0, aware_result.output
    assert "under policy immunara-v0.1 (v0.1), thresholds v0.1: step_therapy changed on 8" in (
        stale_result.output
    )
    assert "step_therapy changed on 0 case(s), action changed on 0 case(s)" in (aware_result.output)
    stale = read_traces(tmp_path / "stale" / "traces.jsonl.gz")
    aware = read_traces(tmp_path / "aware" / "traces.jsonl.gz")
    assert [t.case_id for t in stale] == [t.case_id for t in source]
    assert {step(t) for t in aware} == {0.0}
    assert all(step(t) == pytest.approx(0.98 * 0.97) for t in stale)
    assert [t.decisions for t in aware] == [t.decisions for t in source]
    assert {(t.policy_id, t.thresholds.version, t.mode) for t in stale} == {
        ("immunara-v0.1", "v0.1", "simulated")
    }
    assert {(t.policy_id, t.thresholds.version) for t in aware} == {("immunara-v0.2", "v0.2")}
    assert {t.replay_of for t in stale} == {t.trace_id for t in source}
    assert len({t.run_id for t in stale}) == 1 and stale[0].run_id != source[0].run_id


def test_the_manifest_records_mode_source_and_policy(tmp_path, shift_run):
    dataset, trace_file = shift_run
    assert recompose(tmp_path, dataset, trace_file, "immunara-v0.1", "stale").exit_code == 0
    raw = json.loads((tmp_path / "stale" / "run-manifest.json").read_text())
    manifest = RunManifest.model_validate(raw)
    source = read_traces(trace_file)
    assert (manifest.mode, manifest.source_run_id) == ("simulated", source[0].run_id)
    assert (manifest.policy_version, manifest.question_set_version) == ("v0.1", "q-v0.3")
    assert raw["policy_id"] == "immunara-v0.1"
    assert raw["thresholds"]["version"] == "v0.1"
    assert manifest.trace_file == str(tmp_path / "stale" / "traces.jsonl.gz")


def test_recomposed_runs_score_and_gate_offline(tmp_path, shift_run):
    dataset, trace_file = shift_run
    recompose(tmp_path, dataset, trace_file, "immunara-v0.1", "stale")
    recompose(tmp_path, dataset, trace_file, "immunara-v0.2", "aware")
    scored = invoke(
        tmp_path,
        "eval",
        "--dataset",
        str(dataset),
        "--traces",
        str(tmp_path / "stale" / "traces.jsonl.gz"),
        "--results-dir",
        str(tmp_path / "results"),
    )
    assert scored.exit_code == 0, scored.output
    gate = invoke(
        tmp_path,
        "regression",
        "--dataset",
        str(dataset),
        "--baseline",
        str(tmp_path / "stale" / "traces.jsonl.gz"),
        "--candidate-traces",
        str(tmp_path / "aware" / "traces.jsonl.gz"),
    )
    assert gate.exit_code == 0, gate.output  # aware never automates: nothing newly unsafe


def test_refusals_are_exit_2(tmp_path, shift_run):
    dataset, trace_file = shift_run
    unknown = recompose(tmp_path, dataset, trace_file, "nope-v1", "x")
    assert unknown.exit_code == 2 and "unknown policy 'nope-v1'" in unknown.output
    assert recompose(tmp_path, dataset, trace_file, "immunara-v0.1", "stale").exit_code == 0
    again = recompose(tmp_path, dataset, trace_file, "immunara-v0.1", "stale")
    assert again.exit_code == 2 and "is not empty" in again.output
    rules = invoke(
        tmp_path,
        "eval",
        "--dataset",
        str(dataset),
        "--provider",
        "rules",
        "--policy",
        "v0.2",
        "--traces-dir",
        str(tmp_path / "rules"),
        "--reports-dir",
        str(tmp_path / "reports"),
        "--results-dir",
        str(tmp_path / "results"),
    )
    assert rules.exit_code == 0, rules.output
    [rules_file] = (tmp_path / "rules").glob("*.jsonl")
    refused = recompose(tmp_path, dataset, rules_file, "immunara-v0.1", "rules-out")
    assert refused.exit_code == 2 and "only Jev bundles can be recomposed" in refused.output
    assert not (tmp_path / "rules-out").exists()


def test_a_dataset_that_does_not_match_the_run_is_exit_2(tmp_path, shift_run):
    _, trace_file = shift_run
    other = tmp_path / "other"
    generate_dataset(4, 6, "gen-other", other, generator_version="gen-v0.3", policy_version="v0.2")
    result = recompose(tmp_path, other, trace_file, "immunara-v0.1", "x")
    assert result.exit_code == 2
    assert "trace for unknown case" in result.output
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run: `uv run pytest -q tests/integration/test_cli_recompose.py`

Expected: FAIL. the CLI has no `recompose` command (exit 2, `No such command 'recompose'`).

- [ ] **Step 3: Implement**

In `relay/cli.py`, replace:

```python
from relay.decisions.claude import ClaudeProvider, Mode
from relay.decisions.claude_batch import ClaudeBatchProvider
from relay.decisions.claude_prompt import CLAUDE_QUESTION_SETS
from relay.decisions.ground_truth import GroundTruthProvider
from relay.decisions.jev import JevProvider
from relay.decisions.questions import (
```

with:

```python
from relay.decisions.claude import ClaudeProvider, Mode
from relay.decisions.claude_batch import ClaudeBatchProvider
from relay.decisions.claude_prompt import CLAUDE_QUESTION_SETS
from relay.decisions.composition import MalformedAnswers
from relay.decisions.ground_truth import GroundTruthProvider
from relay.decisions.jev import JevProvider
from relay.decisions.questions import (
```

In `relay/cli.py`, replace:

```python
    settle_jev,
)
from relay.evaluation.metrics import EvalError, paired_cases, run_identity, score_run
from relay.evaluation.regression import RegressionResult
from relay.evaluation.regression_run import (
    CandidateSpec,
    RegressionInputError,
    RegressionRequest,
    load_gates,
    load_waivers,
    run_regression,
```

with:

```python
    settle_jev,
)
from relay.evaluation.metrics import EvalError, paired_cases, run_identity, score_run
from relay.evaluation.recompose_run import changed_counts, recompose_run, write_simulated_bundle
from relay.evaluation.regression import RegressionResult
from relay.evaluation.regression_run import (
    CandidateSpec,
    RegressionInputError,
    RegressionRequest,
    find_run_manifest,
    load_gates,
    load_waivers,
    run_regression,
```

In `relay/cli.py`, replace:

```python
        raise typer.Exit(code=code)


GatesFile = Annotated[
    Path | None,
    typer.Option(
```

with:

```python
        raise typer.Exit(code=code)


@app.command()
def recompose(
    traces: TraceFile,
    dataset: Dataset,
    policy_id: Annotated[
        str, typer.Option("--policy", help="Policy id to recompose under, e.g. immunara-v0.1.")
    ],
    out: Annotated[
        Path, typer.Option(help="Directory for traces.jsonl.gz and run-manifest.json (new).")
    ],
) -> None:
    """Recompose a stored Jev run's raw answers under POLICY as a simulated run (offline).

    step_therapy is composed again from the stored date-part answers; nothing is called. Exit 2
    on any input problem (not a Jev run, cases changed, unknown policy, non-empty --out).
    """
    cases = _load_cases(dataset)
    source = _read_trace_file(traces)
    if not source:
        raise _fail(f"{traces}: no traces")
    target = _policy(policy_id)
    try:
        manifest = find_run_manifest(traces)
        recomposed = recompose_run(source, cases, policy=target)
    except (EvalError, RegressionInputError, MalformedAnswers, ValueError) as error:
        raise _fail(f"--traces {traces}: {error}") from error
    if manifest is not None and manifest.run_id != source[0].run_id:
        manifest = None  # a manifest left over from another run: carry nothing over
    try:
        trace_path, manifest_path = write_simulated_bundle(
            out, recomposed, dataset=dataset, source=source, source_manifest=manifest
        )
    except FileExistsError as error:
        raise _fail(str(error)) from error
    step_changed, action_changed = changed_counts(source, recomposed)
    first = recomposed[0]
    typer.echo(
        f"Recomposed {len(recomposed)} traces of run {source[0].run_id} "
        f"({first.provider} {first.question_set_version}) under policy {target.id} "
        f"({target.version}), thresholds {first.thresholds.version}: step_therapy changed on "
        f"{step_changed} case(s), action changed on {action_changed} case(s)."
    )
    typer.echo(f"Simulated run: {first.run_id}")
    typer.echo(f"Traces: {trace_path}\nManifest: {manifest_path}")


GatesFile = Annotated[
    Path | None,
    typer.Option(
```

Create `relay/evaluation/recompose_run.py`:

```python
"""relay recompose: a stored Jev run's raw answers recomposed under a policy, as a simulated run.

Offline. Each trace's decisions are rebuilt by relay.decisions.recompose.recompose (step_therapy
composed again from the stored date-part answers under `policy`), then re-decided by the engine
under that policy's thresholds (replay_thresholds: the trace's own for the same version, the
registered ones for another). The result is written in the committed-bundle format:
traces.jsonl.gz plus run-manifest.json with mode "simulated", source_run_id, and the extra keys
policy_id and thresholds.
"""

import gzip
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from relay.cases.models import PriorAuthCase
from relay.cases.policies import AuthorizationPolicy
from relay.decisions.base import DecisionId
from relay.decisions.recompose import recompose
from relay.evaluation.metrics import paired_cases
from relay.evaluation.runner import policy_text_hash
from relay.evaluation.tracediff import replay_thresholds
from relay.traces.models import RunManifest, WorkflowTrace
from relay.traces.store import current_git_sha, new_run_id, new_trace_id
from relay.workflow.engine import determine_action

TRACES_NAME = "traces.jsonl.gz"
MANIFEST_NAME = "run-manifest.json"


def recompose_run(
    traces: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
    *,
    policy: AuthorizationPolicy,
    run_id: str | None = None,
    now: datetime | None = None,
    git_sha: str | None = None,
) -> list[WorkflowTrace]:
    """Every trace recomposed under `policy`, in trace order, as one new simulated run.

    Pairs traces with cases (paired_cases: one run, full coverage, unchanged inputs; EvalError
    otherwise). Raises ValueError for a non-Jev trace, EvalError for a policy version without
    thresholds, and MalformedAnswers for unusable stored answers.
    """
    pairs = paired_cases(traces, cases)
    run_id = run_id or new_run_id()
    now = now or datetime.now(UTC)
    git_sha = git_sha if git_sha is not None else current_git_sha()
    text_hash = policy_text_hash(policy)
    out: list[WorkflowTrace] = []
    for trace, case in pairs:
        bundle = recompose(
            trace.decisions,
            case=case.input,
            policy=policy,
            question_set_version=trace.question_set_version,
        )
        thresholds = replay_thresholds(trace, policy, None)
        outcome = determine_action(case.input, bundle, policy, thresholds)
        out.append(
            trace.model_copy(
                update={
                    "trace_id": new_trace_id(),
                    "run_id": run_id,
                    "timestamp": now,
                    "policy_id": policy.id,
                    "policy_version": policy.version,
                    "policy_text_hash": text_hash,
                    "thresholds": thresholds,
                    "decisions": bundle,
                    "action": outcome.action,
                    "decision_reasons": outcome.reasons,
                    "gate_path": outcome.gate_path,
                    "mode": "simulated",
                    "relay_git_sha": git_sha,
                    "replay_of": trace.trace_id,
                }
            )
        )
    return out


def changed_counts(
    source: Sequence[WorkflowTrace], recomposed: Sequence[WorkflowTrace]
) -> tuple[int, int]:
    """(cases whose step_therapy p_yes changed, cases whose action changed), paired by case id."""
    before = {t.case_id: t for t in source}
    step_changed = action_changed = 0
    for trace in recomposed:
        old = before[trace.case_id]
        old_step = old.decisions.get(DecisionId.STEP_THERAPY)
        new_step = trace.decisions.get(DecisionId.STEP_THERAPY)
        if (old_step and old_step.p_yes) != (new_step and new_step.p_yes):
            step_changed += 1
        if old.action != trace.action:
            action_changed += 1
    return step_changed, action_changed


def write_simulated_bundle(
    out: Path,
    traces: Sequence[WorkflowTrace],
    *,
    dataset: Path,
    source: Sequence[WorkflowTrace],
    source_manifest: RunManifest | None = None,
) -> tuple[Path, Path]:
    """Write out/traces.jsonl.gz and out/run-manifest.json. Refuses a non-empty `out`
    (FileExistsError). The source run's sample_limit/sample_seed carry over when its manifest is
    given."""
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"{out} is not empty; refusing to overwrite")
    out.mkdir(parents=True, exist_ok=True)
    trace_path, manifest_path = out / TRACES_NAME, out / MANIFEST_NAME
    with gzip.open(trace_path, "wt", encoding="utf-8") as handle:
        for trace in traces:
            handle.write(trace.model_dump_json() + "\n")
    first = traces[0]
    manifest = RunManifest(
        run_id=first.run_id,
        created_at=datetime.now(UTC),
        dataset_id=first.dataset_id,
        dataset_path=str(dataset),
        provider=first.provider,
        policy_version=first.policy_version,
        question_set_version=first.question_set_version,
        case_count=len(traces),
        trace_file=str(trace_path),
        relay_git_sha=first.relay_git_sha,
        sample_limit=None if source_manifest is None else source_manifest.sample_limit,
        sample_seed=None if source_manifest is None else source_manifest.sample_seed,
        mode="simulated",
        source_run_id=source[0].run_id,
    )
    data = manifest.model_dump(mode="json") | {
        "policy_id": first.policy_id,
        "thresholds": first.thresholds.model_dump(mode="json"),
    }
    manifest_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return trace_path, manifest_path
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run pytest -q tests/integration/test_cli_recompose.py`

Expected: PASS.

- [ ] **Step 5: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`

Expected: all pass (about 1194 passed).

- [ ] **Step 6: Commit**

```bash
git add relay/cli.py relay/evaluation/recompose_run.py tests/integration/test_cli_recompose.py
git commit -m "feat: add relay recompose (stored Jev answers recomposed under a policy)" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 11: `relay bench` (latency vs narrow decisions per call)

**Files:**
- Create: `relay/evaluation/bench.py`
- Modify: `relay/cli.py`
- Test (create): `tests/integration/test_cli_bench.py`
- Test (create): `tests/unit/test_bench.py`

**Interfaces:**
- Consumes: `QUESTION_IDS_V0_3`, `Q_V0_3`, `build_questions`, `candidate_years` (Task 3); `build_state`, `CLIENT_VERSION`, `JEV_MODEL`, `PRICE_PER_INPUT_TOKEN_USD`, `SystemOneClient` (`relay.decisions.jev`); `_resolve_jev`, `_jev_budget_check`, `_jev_reserve`, `_load_jev_ledger`, `estimate_jev_cost`, `settle_jev` (Task 9); `GenericSystemOneClient` (`tests/jev_fakes.py`).
- Produces:
  - `relay/evaluation/bench.py`: `PADDING_QUESTION = "diagnosis_support_padding"`, `MAX_SIZE = 20`, `DEFAULT_SIZES = (1, 5, 10, 20)`, `bench_question_ids(size)`, `bench_questions(policy, years, size)`, `parse_sizes(text)`, `BenchCall`, `BenchSize`, `BenchResult`, `nearest_rank(values, q)`, `summarize_size(size, calls, case_count)`, `async run_bench(cases, client, *, sizes, model=JEV_MODEL, clock=time.perf_counter, policy_loader=load_policy, on_call=None) -> list[BenchCall]`, `build_bench_result(...)`, `render_bench(result) -> str`.
  - CLI: `relay bench --dataset DIR --jev-budget-usd N [--limit 40 --sample-seed 11] [--sizes 1,5,10,20] [--jev-ledger PATH] [--out evals/baselines/bench]` writes `parallelism.json` and `parallelism.md`, refusing to overwrite either.

**What the SDK does (checked in `.venv/lib/python3.12/site-packages/typesafe_sdk`, typesafe-sdk 0.7.x).** `AsyncTypeSafeClient.system_one(state, questions, *, model, …)` takes a nonempty mapping of any number of questions and sends them all in one `POST` (`prepare_system_one` puts them in one body). It returns one `SystemOneResponse` with `answers` keyed by question name and a single `usage` (input and output tokens). The client does not split, parallelize or time questions individually, and the response carries no per-question timing. So the bench times one request per (case, k), and reports per-question latency as not exposed. The spec's fallback (k sequential calls vs one batched call) is not needed. Retries, at most 2 by default on 429/5xx/connection errors, are inside the measured wall time; the Markdown says so. Question names must be unique, so size 20 duplicates `diagnosis_support` under the id `diagnosis_support_padding`, disclosed in both outputs. Calls run strictly one at a time, and decisions are not scored.

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_cli_bench.py`:

```python
"""relay bench with a fake TypeSafe client: estimate, counter, outputs (no network)."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

import relay.cli as cli_module
from relay.cli import app
from relay.evaluation.budget import load_ledger
from tests.jev_fakes import GenericSystemOneClient

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
runner = CliRunner()


class FakeAsyncClient(GenericSystemOneClient):
    instances: list["FakeAsyncClient"] = []

    def __init__(self, **kwargs):
        super().__init__()
        FakeAsyncClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None


@pytest.fixture
def fake_jev(monkeypatch):
    FakeAsyncClient.instances = []
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-placeholder-not-a-key")
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", FakeAsyncClient)
    return FakeAsyncClient


def bench(tmp_path, *extra):
    return runner.invoke(
        app,
        [
            "--env-file",
            str(tmp_path / "missing.env"),
            "bench",
            "--dataset",
            str(SMOKE),
            "--jev-ledger",
            str(tmp_path / "jev-spend.json"),
            "--out",
            str(tmp_path / "bench"),
            *extra,
        ],
    )


def test_bench_prints_the_estimate_runs_every_size_and_writes_both_files(tmp_path, fake_jev):
    result = bench(tmp_path, "--jev-budget-usd", "1.00", "--limit", "4", "--sample-seed", "11")
    assert result.exit_code == 0, result.output
    # 4 cases x (12 + 12 + 12 + 20) billed questions x $0.000013
    assert "jev estimate: 4 cases × (1+5+10+20) questions ≈ $0.0029" in result.output
    [client] = fake_jev.instances
    assert [len(c["questions"]) for c in client.calls] == [1, 5, 10, 20] * 4
    data = json.loads((tmp_path / "bench" / "parallelism.json").read_text())
    assert [s["size"] for s in data["sizes"]] == [1, 5, 10, 20]
    assert (data["sample_limit"], data["sample_seed"], data["case_count"]) == (4, 11, 4)
    assert data["question_set_version"] == "q-v0.3"
    md = (tmp_path / "bench" / "parallelism.md").read_text()
    assert md.startswith("# Relay bench: narrow decisions per call vs latency")
    [entry] = load_ledger(tmp_path / "jev-spend.json").entries
    # 16 calls; tokens 1000 + 50k: 4 x (1050 + 1250 + 1500 + 2000) = 23,200 tokens
    assert (entry.status, entry.cost_usd) == ("settled", Decimal("0.000974"))
    assert "Jev spend: this bench $0.0010; total $0.0010 of the $1.00 cap" in result.output


def test_bench_requires_the_counter(tmp_path, fake_jev):
    result = bench(tmp_path)
    assert result.exit_code == 2
    assert "--jev-budget-usd" in result.output
    assert fake_jev.instances == []


def test_bench_refuses_over_the_cap_before_any_call(tmp_path, fake_jev):
    result = bench(tmp_path, "--jev-budget-usd", "0.001")
    assert result.exit_code == 2
    assert "Jev budget exceeded" in result.output
    assert fake_jev.instances == []


def test_bench_refuses_bad_sizes_and_existing_outputs(tmp_path, fake_jev):
    bad = bench(tmp_path, "--jev-budget-usd", "1", "--sizes", "1,21")
    assert bad.exit_code == 2 and "between 1 and 20" in bad.output
    (tmp_path / "bench").mkdir()
    (tmp_path / "bench" / "parallelism.json").write_text("{}")
    exists = bench(tmp_path, "--jev-budget-usd", "1")
    assert exists.exit_code == 2 and "refusing to overwrite" in exists.output
    assert fake_jev.instances == []


def test_bench_needs_the_typesafe_key(tmp_path, fake_jev, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY")
    result = bench(tmp_path, "--jev-budget-usd", "1")
    assert result.exit_code == 2 and "TYPESAFE_API_KEY is not set" in result.output
```

Create `tests/unit/test_bench.py`:

```python
"""relay bench internals: question prefixes, padding, sequential timing with a fake clock."""

from decimal import Decimal

import pytest
from typesafe_sdk import TypeSafeError

from relay.cases.policies import load_policy
from relay.decisions.questions import QUESTION_IDS_V0_3
from relay.evaluation.bench import (
    MAX_SIZE,
    PADDING_QUESTION,
    BenchCall,
    bench_question_ids,
    bench_questions,
    build_bench_result,
    nearest_rank,
    parse_sizes,
    render_bench,
    run_bench,
    summarize_size,
)
from tests.factories import make_case_input
from tests.jev_fakes import GenericSystemOneClient

POLICY = load_policy("immunara-v0.1")


class FakeClock:
    """perf_counter stand-in: the fake client advances it by 0.1 s + 0.01 s per question."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance_for(self, questions):
        self.now += 0.1 + 0.01 * len(questions)


def test_sizes_are_prefixes_of_the_q_v0_3_ordering_and_20_adds_the_padding():
    assert bench_question_ids(1) == ("diagnosis_support",)
    assert bench_question_ids(5) == QUESTION_IDS_V0_3[:5]
    assert bench_question_ids(10) == QUESTION_IDS_V0_3[:10]
    assert bench_question_ids(19) == QUESTION_IDS_V0_3
    assert bench_question_ids(20) == (*QUESTION_IDS_V0_3, PADDING_QUESTION)
    assert MAX_SIZE == 20
    for bad in (0, 21):
        with pytest.raises(ValueError, match="between 1 and 20"):
            bench_question_ids(bad)


def test_the_padding_question_duplicates_diagnosis_support():
    questions = bench_questions(POLICY, ["2026"], 20)
    assert len(questions) == 20
    assert questions[PADDING_QUESTION] == questions["diagnosis_support"]


def test_parse_sizes():
    assert parse_sizes("1,5,10,20") == (1, 5, 10, 20)
    for bad, message in (("1,x", "integers"), ("5,5", "duplicate"), ("1,25", "between")):
        with pytest.raises(ValueError, match=message):
            parse_sizes(bad)


def test_nearest_rank_percentiles():
    values = [float(v) for v in range(1, 41)]  # 1..40
    assert nearest_rank(values, 0.50) == 20.0
    assert nearest_rank(values, 0.95) == 38.0
    assert nearest_rank([7.0], 0.95) == 7.0


async def test_run_bench_times_each_call_sequentially_with_one_request_per_size():
    clock = FakeClock()
    client = GenericSystemOneClient(on_call=clock.advance_for)
    cases = [make_case_input("T-01"), make_case_input("T-02")]
    calls = await run_bench(cases, client, sizes=(1, 5, 20), clock=clock)
    assert [(c.case_id, c.size) for c in calls] == [
        ("T-01", 1),
        ("T-01", 5),
        ("T-01", 20),
        ("T-02", 1),
        ("T-02", 5),
        ("T-02", 20),
    ]
    assert [len(call["questions"]) for call in client.calls] == [1, 5, 20, 1, 5, 20]
    assert {call["model"] for call in client.calls} == {"jev-1.13.0"}
    assert [round(c.latency_ms, 6) for c in calls[:3]] == [110.0, 150.0, 300.0]
    assert calls[2].input_tokens == 1000 + 50 * 20
    assert calls[2].cost_usd == Decimal("0.042") / Decimal(1_000_000) * 2000
    assert all(c.error is None for c in calls)


class FlakyClient(GenericSystemOneClient):
    async def system_one(self, state, questions, *, model=None, **kwargs):
        if len(questions) == 5:
            raise TypeSafeError("rate limited")
        response = await super().system_one(state, questions, model=model)
        if len(questions) == 20:  # drop an answer
            answers = dict(response.answers)
            del answers[PADDING_QUESTION]
            return response.model_copy(update={"answers": answers})
        return response


async def test_errors_are_recorded_per_call_and_the_bench_continues():
    calls = await run_bench([make_case_input()], FlakyClient(), sizes=(1, 5, 20))
    assert [c.error for c in calls] == [
        None,
        "TypeSafeError: rate limited",
        f"missing answers: {PADDING_QUESTION}",
    ]
    assert calls[1].cost_usd is None and calls[2].cost_usd is not None


def test_summaries_exclude_errors_from_latency_and_count_all_cost():
    calls = [
        BenchCall(case_id="a", size=5, latency_ms=100.0, input_tokens=1000, cost_usd=Decimal("1")),
        BenchCall(case_id="b", size=5, latency_ms=300.0, input_tokens=3000, cost_usd=Decimal("2")),
        BenchCall(case_id="c", size=5, latency_ms=9000.0, error="TypeSafeError: x"),
    ]
    s = summarize_size(5, calls, case_count=3)
    assert (s.calls, s.errors) == (3, 1)
    assert (s.latency_ms_p50, s.latency_ms_p95, s.latency_ms_mean) == (100.0, 300.0, 200.0)
    assert s.input_tokens_mean == 2000.0
    assert (s.total_cost_usd, s.cost_per_case_usd) == (Decimal("3"), Decimal("1"))


async def test_result_and_markdown_disclose_batching_padding_and_sample():
    clock = FakeClock()
    client = GenericSystemOneClient(on_call=clock.advance_for)
    cases = [make_case_input(f"T-{i:02d}") for i in range(4)]
    calls = await run_bench(cases, client, sizes=(1, 20), clock=clock)
    result = build_bench_result(
        calls, dataset_id="gen-test", case_count=4, sizes=(1, 20), sample=(4, 11), model="jev-x"
    )
    assert [s.size for s in result.sizes] == [1, 20]
    assert result.sizes[0].latency_ms_p50 == pytest.approx(110.0)
    assert result.sizes[1].latency_ms_p95 == pytest.approx(300.0)
    assert result.ordering[-1] == PADDING_QUESTION and len(result.ordering) == 20
    text = render_bench(result)
    assert "| 1 | 4 | 0 | 110 | 110 | 110 | 1050 |" in text
    assert "| 20 | 4 | 0 | 300 | 300 | 300 | 2000 |" in text
    assert "--limit 4 --sample-seed 11" in text
    assert "one system_one request carrying all k questions" in text
    assert "returns no per-question timing" in text
    assert "a duplicate of 'diagnosis_support'" in text
    assert "not scored" in text
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run: `uv run pytest -q tests/integration/test_cli_bench.py tests/unit/test_bench.py`

Expected: FAIL. `ModuleNotFoundError: No module named 'relay.evaluation.bench'`, and the CLI has no `bench` command.

- [ ] **Step 3: Implement**

In `relay/cli.py`, replace:

```python
from relay.decisions.claude_prompt import CLAUDE_QUESTION_SETS
from relay.decisions.composition import MalformedAnswers
from relay.decisions.ground_truth import GroundTruthProvider
from relay.decisions.jev import JevProvider
from relay.decisions.questions import (
    DEFAULT_QUESTION_SET_VERSION,
    Q_V0_2,
```

with:

```python
from relay.decisions.claude_prompt import CLAUDE_QUESTION_SETS
from relay.decisions.composition import MalformedAnswers
from relay.decisions.ground_truth import GroundTruthProvider
from relay.decisions.jev import JEV_MODEL, JevProvider
from relay.decisions.questions import (
    DEFAULT_QUESTION_SET_VERSION,
    Q_V0_2,
```

In `relay/cli.py`, replace:

```python
)
from relay.decisions.rules_baseline import RulesBaselineProvider
from relay.evaluation.artifacts import write_eval_bundle
from relay.evaluation.budget import (
    DEFAULT_BUDGET_USD,
    DEFAULT_LEDGER,
```

with:

```python
)
from relay.decisions.rules_baseline import RulesBaselineProvider
from relay.evaluation.artifacts import write_eval_bundle
from relay.evaluation.bench import (
    DEFAULT_SIZES,
    BenchCall,
    build_bench_result,
    parse_sizes,
    render_bench,
    run_bench,
)
from relay.evaluation.budget import (
    DEFAULT_BUDGET_USD,
    DEFAULT_LEDGER,
```

In `relay/cli.py`, replace:

```python
    typer.echo(f"Traces: {trace_path}\nManifest: {manifest_path}")


GatesFile = Annotated[
    Path | None,
    typer.Option(
```

with:

```python
    typer.echo(f"Traces: {trace_path}\nManifest: {manifest_path}")


@app.command()
def bench(
    dataset: Dataset,
    jev_budget_usd: Annotated[
        float,
        typer.Option(
            min=0.0,
            help="Required: the Jev spend counter's cap on the ledger's total Jev spend.",
        ),
    ],
    limit: Limit = None,
    sample_seed: SampleSeed = None,
    sizes: Annotated[
        str, typer.Option(help="Comma-separated questions per call, each 1-20.")
    ] = ",".join(str(s) for s in DEFAULT_SIZES),
    jev_ledger: JevLedgerOption = None,
    out: Annotated[
        Path, typer.Option(help="Where parallelism.json and parallelism.md are written.")
    ] = Path("evals/baselines/bench"),
) -> None:
    """Latency vs narrow decisions per call: one Jev call per case and size (paid, sequential).

    Prints the estimate first and refuses (exit 2) if it could break the Jev cap.
    """
    try:
        size_list = parse_sizes(sizes)
    except ValueError as error:
        raise _fail(str(error)) from error
    json_path, md_path = out / "parallelism.json", out / "parallelism.md"
    existing = [str(p) for p in (json_path, md_path) if p.exists()]
    if existing:
        raise _fail(f"{', '.join(existing)} already exist; refusing to overwrite")
    cases, sample = _apply_limit(_load_cases(dataset), limit, sample_seed)
    if not os.environ.get("TYPESAFE_API_KEY"):
        raise _fail("TYPESAFE_API_KEY is not set (add it to .env or the environment)")
    jev = _resolve_jev(ProviderName.jev, jev_budget_usd, jev_ledger)
    assert jev is not None
    estimate = sum((estimate_jev_cost(len(cases), size) for size in size_list), Decimal("0"))
    per_case = "(" + "+".join(str(s) for s in size_list) + ")"
    _jev_budget_check(jev, len(cases), per_case, estimate)
    run_id = new_run_id()
    dataset_id = cases[0].input.dataset_id
    _jev_reserve(jev, run_id, dataset_id, len(cases), estimate)
    calls: list[BenchCall] = []

    async def go() -> None:
        async with AsyncTypeSafeClient(timeout=30.0) as client:
            await run_bench([c.input for c in cases], client, sizes=size_list, on_call=calls.append)

    try:
        asyncio.run(go())
    finally:
        actual = sum((c.cost_usd or Decimal("0") for c in calls), Decimal("0"))
        ledger = settle_jev(_load_jev_ledger(jev), run_id, actual)
        write_ledger(jev.ledger, ledger)
        typer.echo(
            f"Jev spend: this bench ${actual:.4f}; total ${ledger.spent_usd:.4f} of the "
            f"${jev.budget_usd:.2f} cap ({jev.ledger})"
        )
    result = build_bench_result(
        calls,
        dataset_id=dataset_id,
        case_count=len(cases),
        sizes=size_list,
        sample=sample,
        model=JEV_MODEL,
    )
    rendered = render_bench(result)
    out.mkdir(parents=True, exist_ok=True)
    json_path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    md_path.write_text(rendered, encoding="utf-8")
    typer.echo(rendered)
    typer.echo(f"Bench: {json_path}\nMarkdown: {md_path}")


GatesFile = Annotated[
    Path | None,
    typer.Option(
```

Create `relay/evaluation/bench.py`:

```python
"""relay bench: does adding narrow decisions cost latency? (handoff experiment 4)

For each sampled case and each size k, one TypeSafe System One request carries the first k
questions of a fixed ordering of q-v0.3's 19 (QUESTION_IDS_V0_3); size 20 adds one padding
question, a duplicate of diagnosis_support under another id (disclosed in every output). The
installed typesafe-sdk sends all of a call's questions in one HTTP request and returns no
per-question timing, so the bench measures per-call wall latency around that one request.
Calls run one at a time (never concurrently), case by case, sizes in the given order, so no
call's latency includes another's. Decisions are not scored: a partial question set cannot form
a bundle.
"""

import math
import time
from collections.abc import Callable, Sequence
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from typesafe_sdk import TypeSafeError

from relay.cases.models import CaseInput
from relay.cases.policies import AuthorizationPolicy, load_policy
from relay.decisions.jev import (
    CLIENT_VERSION,
    JEV_MODEL,
    PRICE_PER_INPUT_TOKEN_USD,
    SystemOneClient,
    build_state,
)
from relay.decisions.questions import Q_V0_3, QUESTION_IDS_V0_3, build_questions, candidate_years

PADDING_SOURCE = "diagnosis_support"
PADDING_QUESTION = "diagnosis_support_padding"
MAX_SIZE = len(QUESTION_IDS_V0_3) + 1  # 20: the 19 q-v0.3 questions plus the padding question
DEFAULT_SIZES: tuple[int, ...] = (1, 5, 10, 20)
BATCHING_NOTE = (
    "Each call is one system_one request carrying all k questions for one case "
    f"({CLIENT_VERSION}); the client does not split a request."
)
PER_QUESTION_NOTE = (
    f"Not measured: {CLIENT_VERSION} returns no per-question timing (one HTTP request per call)."
)
PADDING_NOTE = (
    f"Size {MAX_SIZE} is q-v0.3's {len(QUESTION_IDS_V0_3)} questions plus {PADDING_QUESTION!r}, "
    f"a duplicate of {PADDING_SOURCE!r} under another id (controlled padding)."
)


def bench_question_ids(size: int) -> tuple[str, ...]:
    """The first `size` ids of the fixed ordering; 20 appends the padding question."""
    if not 1 <= size <= MAX_SIZE:
        raise ValueError(f"size must be between 1 and {MAX_SIZE}, got {size}")
    if size == MAX_SIZE:
        return (*QUESTION_IDS_V0_3, PADDING_QUESTION)
    return QUESTION_IDS_V0_3[:size]


def bench_questions(policy: AuthorizationPolicy, years: Sequence[str], size: int) -> dict[str, Any]:
    full = build_questions(policy, years, Q_V0_3)
    full[PADDING_QUESTION] = full[PADDING_SOURCE]
    return {qid: full[qid] for qid in bench_question_ids(size)}


def parse_sizes(text: str) -> tuple[int, ...]:
    """'1,5,10,20' -> (1, 5, 10, 20). ValueError for anything else (empty, duplicate, range)."""
    try:
        sizes = tuple(int(part) for part in text.split(","))
    except ValueError:
        raise ValueError(f"--sizes must be comma-separated integers, got {text!r}") from None
    if len(set(sizes)) != len(sizes):
        raise ValueError(f"--sizes has a duplicate: {text!r}")
    for size in sizes:
        bench_question_ids(size)
    return sizes


class BenchCall(BaseModel):
    case_id: str
    size: int
    latency_ms: float
    input_tokens: int | None = None
    cost_usd: Decimal | None = None
    error: str | None = None


class BenchSize(BaseModel):
    size: int
    calls: int
    errors: int
    latency_ms_p50: float | None
    latency_ms_p95: float | None
    latency_ms_mean: float | None
    input_tokens_mean: float | None
    cost_per_case_usd: Decimal
    total_cost_usd: Decimal


class BenchResult(BaseModel):
    dataset_id: str
    case_count: int
    sample_limit: int | None
    sample_seed: int | None
    model: str
    client_version: str
    question_set_version: str
    ordering: list[str]
    padding_question: str
    batching: str
    per_question_latency: str
    sizes: list[BenchSize]
    total_cost_usd: Decimal
    calls: list[BenchCall]


def nearest_rank(values: Sequence[float], q: float) -> float:
    """The nearest-rank percentile: the ceil(q * n)-th smallest value (1-based)."""
    ordered = sorted(values)
    return ordered[max(math.ceil(q * len(ordered)), 1) - 1]


def summarize_size(size: int, calls: Sequence[BenchCall], case_count: int) -> BenchSize:
    """Latency over successful calls; cost over every call that reported tokens."""
    ok = [c for c in calls if c.error is None]
    latencies = [c.latency_ms for c in ok]
    tokens = [c.input_tokens for c in ok if c.input_tokens is not None]
    total = sum((c.cost_usd or Decimal("0") for c in calls), Decimal("0"))
    return BenchSize(
        size=size,
        calls=len(calls),
        errors=len(calls) - len(ok),
        latency_ms_p50=nearest_rank(latencies, 0.50) if latencies else None,
        latency_ms_p95=nearest_rank(latencies, 0.95) if latencies else None,
        latency_ms_mean=sum(latencies) / len(latencies) if latencies else None,
        input_tokens_mean=sum(tokens) / len(tokens) if tokens else None,
        cost_per_case_usd=total / case_count if case_count else Decimal("0"),
        total_cost_usd=total,
    )


async def run_bench(
    cases: Sequence[CaseInput],
    client: SystemOneClient,
    *,
    sizes: Sequence[int],
    model: str = JEV_MODEL,
    clock: Callable[[], float] = time.perf_counter,
    policy_loader: Callable[[str], AuthorizationPolicy] = load_policy,
    on_call: Callable[[BenchCall], None] | None = None,
) -> list[BenchCall]:
    """One call per (case, size), sequentially. A TypeSafeError or a response missing an asked
    question is recorded as that call's error, and the bench continues."""
    calls: list[BenchCall] = []
    for case in cases:
        policy = policy_loader(case.policy_id)
        state = build_state(case, policy)
        years = candidate_years(case)
        for size in sizes:
            questions = bench_questions(policy, years, size)
            started = clock()
            try:
                response = await client.system_one(state=state, questions=questions, model=model)
            except TypeSafeError as error:
                call = BenchCall(
                    case_id=case.id,
                    size=size,
                    latency_ms=(clock() - started) * 1000,
                    error=f"{type(error).__name__}: {error}",
                )
            else:
                latency_ms = (clock() - started) * 1000
                tokens = response.usage.input_tokens
                missing = sorted(set(questions) - set(response.answers))
                call = BenchCall(
                    case_id=case.id,
                    size=size,
                    latency_ms=latency_ms,
                    input_tokens=tokens,
                    cost_usd=None if tokens is None else PRICE_PER_INPUT_TOKEN_USD * tokens,
                    error=f"missing answers: {', '.join(missing)}" if missing else None,
                )
            calls.append(call)
            if on_call is not None:
                on_call(call)
    return calls


def build_bench_result(
    calls: Sequence[BenchCall],
    *,
    dataset_id: str,
    case_count: int,
    sizes: Sequence[int],
    sample: tuple[int, int] | None,
    model: str,
) -> BenchResult:
    per_size = [summarize_size(s, [c for c in calls if c.size == s], case_count) for s in sizes]
    return BenchResult(
        dataset_id=dataset_id,
        case_count=case_count,
        sample_limit=None if sample is None else sample[0],
        sample_seed=None if sample is None else sample[1],
        model=model,
        client_version=CLIENT_VERSION,
        question_set_version=Q_V0_3,
        ordering=list(bench_question_ids(MAX_SIZE)),
        padding_question=PADDING_QUESTION,
        batching=BATCHING_NOTE,
        per_question_latency=PER_QUESTION_NOTE,
        sizes=per_size,
        total_cost_usd=sum((s.total_cost_usd for s in per_size), Decimal("0")),
        calls=list(calls),
    )


def _ms(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0f}"


def render_bench(result: BenchResult) -> str:
    """The Markdown table and notes written to parallelism.md (also printed)."""
    sample = (
        f"--limit {result.sample_limit} --sample-seed {result.sample_seed}"
        if result.sample_limit is not None
        else "every case"
    )
    lines = [
        "# Relay bench: narrow decisions per call vs latency",
        "",
        f"Dataset {result.dataset_id}, {result.case_count} cases ({sample}); model "
        f"{result.model}; {result.question_set_version} ordering.",
        "",
        "| Questions per call | Calls | Errors | p50 latency (ms) | p95 latency (ms) | "
        "Mean latency (ms) | Mean input tokens | Est. cost / case |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in result.sizes:
        tokens = "n/a" if s.input_tokens_mean is None else f"{s.input_tokens_mean:.0f}"
        lines.append(
            f"| {s.size} | {s.calls} | {s.errors} | {_ms(s.latency_ms_p50)} | "
            f"{_ms(s.latency_ms_p95)} | {_ms(s.latency_ms_mean)} | {tokens} | "
            f"${s.cost_per_case_usd:.6f} |"
        )
    lines += [
        "",
        f"Total estimated cost: ${result.total_cost_usd:.4f}",
        "",
        f"- Batching: {result.batching}",
        f"- Per-question latency: {result.per_question_latency}",
        f"- Padding: {PADDING_NOTE}",
        "- Calls ran one at a time; latency is wall time around one request, retries included.",
        "- Latency-only: these runs' decisions are not scored.",
        "- Question ordering: " + ", ".join(result.ordering),
    ]
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run pytest -q tests/integration/test_cli_bench.py tests/unit/test_bench.py`

Expected: PASS.

- [ ] **Step 5: Full checks**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q`

Expected: all pass (about 1207 passed).

Then confirm the committed gates still pass, and that nothing under `evals/` changed:

```bash
env -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY uv run relay --env-file .no-such.env regression --config evals/regression/gates.json --strict-generated
git status --short evals/
```

Expected: `REGRESSION GATE: PASS` for all 9 gates, exit 0; `git status --short evals/` prints nothing.

- [ ] **Step 6: Commit**

```bash
git add relay/cli.py relay/evaluation/bench.py tests/integration/test_cli_bench.py tests/unit/test_bench.py
git commit -m "feat: add relay bench for latency vs narrow decisions per call" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

## Self-review (done while planning)

- **Spec coverage (the 3D1 part).** §2 generator gen-v0.3: `generator_version` parameter with gen-v0.2 byte-identical (Tasks 6–8); interrupted courses with the three variants and D8 labels (Tasks 6–7); course recency (Task 7); policy-aware labels (Task 6); the audit extended with leak, proportion and D8 checks (Task 7). §3 immunara-v0.2, `max_days_since_therapy`, the registry, `latest_policy_for`, and thresholds v0.2 (Task 1). §4 q-v0.3: 19 questions and two text edits (Task 3); composition with inclusion-exclusion, recency per candidate pair, derivations recording the segment probabilities, and the q-v0.2 path selected by version (Tasks 2 and 4); `recompose` (Task 5). §5 the spend counter (Task 9); `relay bench` with fakes (Task 11). §6 CLI: `generate --generator` (Task 8), `eval --jev-budget-usd/--jev-ledger` (Task 9), `recompose` (Task 10), `bench` (Task 11). §8 testing: every listed test is in Tasks 2–11, and the q-v0.2 golden test is Task 5. The datasets, paid runs, analyses, committed artifacts, gates, CI and README are plan 3D2.
- **Placeholders.** None. Every step has its code or command.
- **Type consistency.** `question_ids`, `question_groups`, `answer_set_from_raw`, `recompose(bundle, *, case, policy, question_set_version)`, `JevBudget`, `estimate_jev_cost`, `_resolve_jev`, `_jev_budget_check`, `_jev_reserve`, `_jev_settle`, `recompose_run`, `write_simulated_bundle`, `run_bench` and `render_bench` are used with the same names and signatures in every task that consumes them.
