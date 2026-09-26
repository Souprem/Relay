# Phase 2C: Rules-Only Baseline Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `rules`, a deterministic, network-free `DecisionProvider` that turns explicit textual and structured cues into the five decisions (probabilities only 0, 0.5 or 1). Run it through the unchanged policy engine on smoke, `gen-v0.2-dev` and `gen-v0.2-holdout`, and commit the results next to the Jev baselines with an honest README comparison. Along the way, replace the CLI's implicit "anything else is Jev" branch with an explicit per-provider factory and key preflight, and reject `--questions` for providers that have no question set.

**Architecture:** `relay/decisions/date_parse.py` finds day-precision dates. `relay/decisions/rules_baseline.py` splits documents into lines, drops relative and fax lines from patient rules, runs one small pure function per spec §3 rule (each returns the `Fired` records that justify it), combines them in `evaluate_rules`, and wraps the result in `RulesBaselineProvider.decide`. The CLI gains `ProviderName.rules`, a `PROVIDER_KEYS` table, `_resolve_questions` and `_build_provider`. The run report lists the rules that fired. The evaluation stack (`eval`, `sweep`, `report`, `compare`) is reused as is.

**Tech Stack:** Python 3.12, uv, Pydantic v2, Typer, pytest, ruff. Standard library only (`re`, `hashlib`, `json`, `calendar`). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-25-phase2c-rules-baseline-design.md`, plus the three 2B final-review rulings listed under "Additional requirements" below.

## Global Constraints

- Python `>=3.12`. Use `uv` for everything (`uv run pytest`, `uv run relay ...`, `uv run ruff ...`). **No new dependencies.**
- **Never read, print, `cat`, `source`, or otherwise open `.env`.** Nothing in this plan calls Jev or any network service. Every provider run and analysis command in Task 6 runs with `env -u TYPESAFE_API_KEY` and `--env-file .no-such.env`, which proves it needs no key.
- pytest config lives in `pyproject.toml`: `asyncio_mode = "auto"`, `pythonpath = ["."]`, `addopts = "-m 'not live'"`. Tests import shared helpers with `from tests.factories import ...`.
- ruff: line length 100, E501 ignored, `docs/` excluded. **Before every commit run** `uv run ruff check --fix . && uv run ruff format .` and then `uv run pytest`. Both must be clean.
- **Commit trailer.** Every commit message ends with a second `-m` paragraph containing exactly `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. This is literal text; use it whatever model you are. After each commit run `git log -1 --format=%B` and confirm that the last line is exactly that trailer.
- **Staging.** Stage files by explicit path only. Never use `git add -A`, `git add .`, or `git commit -a`. Never stage `.env`, `traces/`, `reports/`, `results/`, or generated case directories (`evals/generated/<dataset-id>/`).
- **Spec R1:** provider name `rules`; `provider_version` and `question_set_version` are both `rules-v0.1`; `question_set_hash` is the SHA-256 of the module's pattern table as sorted JSON; `latency_ms` measured; `input_tokens` 0; cost `Decimal("0")`.
- **Spec R2:** every probability the rules emit (yes/no `p_yes` and choice probabilities) is exactly 0.0, 0.5 or 1.0.
- **Spec R3:** the rules read `CaseInput` only (structured fields and document text), never ground truth.
- **Spec R6:** thresholds are not changed to favour rules. `relay/workflow/`, `relay/evaluation/`, `relay/generation/`, `relay/decisions/jev.py`, `relay/decisions/questions.py` and `tests/factories.py` are not modified by this plan.
- **No tuning after results.** The pattern table in Task 2 is the spec's §3 text. Once Task 6 starts, nothing in `relay/` or `tests/` changes. README numbers are pasted from command output or from the script in Task 6, never retyped or rounded by hand.
- **Datasets:** `gen-v0.2-dev` (seed 1, 400 cases) and `gen-v0.2-holdout` (seed 2, 1000 cases) under `evals/generated/` (git-ignored case folders, committed manifests). The committed Jev runs to compare against are `evals/baselines/gen-v0.2-dev/run_20260925T071231Z_6f0b73/traces.jsonl.gz` (q-v0.2, the adopted dev run) and `evals/baselines/gen-v0.2-holdout/run_20260925T075242Z_fd455f/traces.jsonl.gz`.
- **Test counts.** When this plan was written the suite had `363 passed, 1 deselected` (with the generated datasets on disk, so the three committed-baseline drift tests run). In Task 1 Step 0 record your own baseline `B`. Expected totals: Task 1 `B+6`, Task 2 `B+46`, Task 3 `B+50`, Task 4 `B+56`, Task 5 `B+63`, Task 6 `B+65` (the drift guard in `tests/integration/test_committed_baselines.py` adds one test per new `evals/baselines/gen-v0.2-*/<run_id>/` directory). These deltas were checked by transcribing this plan into a throwaway copy of the repository (`git archive HEAD`, no `.env`): `363` → `426` after Task 5, and `427` with one rules run directory committed.

## Additional requirements (2B final-review rulings)

1. **CLI provider factory.** `_execute`'s implicit `else: JevProvider` becomes an explicit per-provider factory (`jev`, `groundtruth`, `rules`) with a per-provider key preflight: `rules` and `groundtruth` need no key; `jev` needs `TYPESAFE_API_KEY`. `--questions` defaults to `None`; the jev default (`q-v0.2`) is resolved internally, and an explicit `--questions` for `rules` or `groundtruth` exits 2 with a clear message. Existing tests keep passing. → Task 5.
2. **Anti-shortcut test.** The rules must not key on the gen-v0.2 residual contradiction tell (a day-precision, non-split MTX medication-history line predicts a contradiction about 81% of the time). Variants of generated cases change only the medication-history line's precision/split presentation, hold the label-determining facts fixed, and the rules' `material_contradiction` must not move. → Task 4.
3. **Flat frontier.** With probabilities in {0, 0.5, 1}, the rules' frontier is expected to be flat. `relay sweep` and `relay report` already print `Frontier is flat across all thresholds.` and store `frontier_flat` / `ceiling_binding`; the README must say so. → Task 6.

## File Map

| File | Responsibility |
|---|---|
| `relay/decisions/date_parse.py` (new) | `find_day_dates(text) -> list[tuple[date, Span]]`; `ISO_DATE`, `LONG_DATE` pattern strings |
| `relay/decisions/rules_baseline.py` (new) | `PATTERNS`, `rules_hash()`, `Line`, `split_lines`, `Fired`, one function per rule, `step_therapy_p`, `contradiction_p`, `RulesResult`, `evaluate_rules`, `RulesBaselineProvider` |
| `relay/cli.py` | `ProviderName.rules`; `PROVIDER_KEYS`, `QUESTION_SET_PROVIDERS`, `PROVIDER_NOTES`; `_resolve_questions`, `_build_provider`; `--questions` defaults to `None` |
| `relay/reporting.py` | `RULES_NOTE`; the run report labels rules runs and lists "Rules fired" per case |
| `tests/unit/test_date_parse.py` (new) | Date finder: both formats, spans, month-only and invalid dates rejected |
| `tests/unit/test_rules_baseline.py` (new) | A positive and a negative fixture per rule; scoping; month-only abstention; provider bundle; pinned hash |
| `tests/unit/test_rules_datasets.py` (new) | Smoke decisions pinned per case; ADV-02 checks; 500-case consistency sweep |
| `tests/unit/test_rules_anti_shortcut.py` (new) | Presentation-only variants of generated cases; contradiction output must not move |
| `tests/integration/test_cli_providers.py` (new) | Factory covers every provider; key table; `--questions` rejection; `eval --provider rules` on smoke with no key |
| `tests/unit/test_reporting.py` | One new test for the "Rules fired" section |
| `evals/baselines/smoke-v0.1/<run_id>/`, `evals/baselines/gen-v0.2-dev/<run_id>/`, `evals/baselines/gen-v0.2-holdout/<run_id>/`, `compare-jev-vs-rules.txt` ×2 | Committed rules runs (Task 6) |
| `README.md` | Commands, "Baselines" subsection, Limitations, project docs |

## Resolved spec ambiguities

These decisions are already encoded in the code below. They are listed so reviewers can check them against the spec.

1. **Which date is a start and which is a stop.** §3 classifies dates by the keywords on their line, but lines such as "started 2026-01-12. Discontinued 2026-06-01" contain both. Each date takes its role from the **nearest** start/stop keyword between it and the previous date on the same line. `to` counts as a stop keyword only immediately before the date (§3's `to <date>`). A date with no keyword before it is ignored.
2. **Several dates.** Duration uses the conservative pair: the latest start and the earliest stop. Conflicting starts also set `mtx_conflicting_starts` (contradiction 1.0), so this choice never lets a conflicting case automate.
3. **Patient lines** are the lines of any non-fax document that do not match the relative pattern. The diagnosis rules look only at `physician_note`-kind documents, which include the generator's older `clinic_note`.
4. **"near `rheumatoid arthritis`"** in `dx_negated` means on the same line. As §3 says "any physician-note line", `dx_negated` does not skip relative lines, but `dx_established` does (§3 says "non-relative line").
5. **Adjacent line** for `mtx_response` means the previous or next line of the same document. Both the methotrexate line and the cue line must be patient lines.
6. **"in some other document"** for the never-versus-dated contradiction means a dated methotrexate mention in a document that has no `mtx_never` line.
7. **Patterns are the spec's, verbatim.** Some generator phrasings fall outside them (for example "reports never having tried", "lack of efficacy", "records were not included"). Such cases abstain or miss, which is safe. The patterns were not widened, because widening them to fit the generator would be tuning to the test distribution.
8. **"step_therapy is decided"** (§3 documentation rule) means `p_yes` is 0.0 or 1.0.
9. **Missing-evidence choice.** `probabilities = {answer: p}` and `confidence = p`, where p is 1.0 for an explicit label or NONE, and 0.5 when abstaining.
10. **Derivations.** `derivations["rules"]` is a list of `{rule, document_id, line, match}` (`match` capped at 200 characters; the structured `member_id is None` check has `document_id` and `line` = `null`). `derivations["duration"]` holds `{start, end, days, min_days}`. The key `step_therapy` is not used, because the run report renders that key in Jev's shape.
11. **`question_set_hash`** covers the whole `PATTERNS` table, including the two date regexes, and is pinned in a test. Any pattern edit changes the hash and needs a new `RULES_VERSION`.
12. **`--questions` validation** happens only when a provider actually runs. `relay eval --traces …` ignores `--provider` and `--questions` exactly as before.
13. **Spec §6 "`relay run`"** is done with `relay eval`, which runs the dataset and also writes `results/<run_id>.json` (2B precedent). The per-case run report (`reports/<run_id>.md`) is not committed.
14. **The rules' operating point.** The dev sweep's selection rule picks the rules' threshold (with a flat frontier this is the tie-break, the highest threshold). The holdout report uses that value as `--at`. If nothing is selected, the report has no `--at`. Either way, the README states that the frontier is flat.
15. **Anti-shortcut scope.** Precision (day vs month) is varied on non-contradiction scenarios. Contradiction scenarios always carry day-precision dates (a `CaseFacts` invariant, and R4 counts only day-precision dates as cues), so split presentation, date format and template draws are varied there instead.
16. **Smoke artifacts** follow the 2B per-run layout under `evals/baselines/smoke-v0.1/<run_id>/`, next to the older Jev smoke baseline, which is left untouched.

---

### Task 1: Day-precision date finder

**Files:**
- Create: `relay/decisions/date_parse.py`
- Test: `tests/unit/test_date_parse.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `relay.decisions.date_parse.find_day_dates(text: str) -> list[tuple[date, tuple[int, int]]]`: every valid day-precision date with its `(start, end)` character span, in text order
  - `ISO_DATE: str`, `LONG_DATE: str`: the regex source strings (Task 2 puts them in its hashed pattern table)
  - `MONTH_NAMES: tuple[str, ...]`, `Span = tuple[int, int]`

- [ ] **Step 0: Record the baseline**

Run: `uv run pytest -q 2>&1 | tail -1`
Write down the passed count as `B` (363 when this plan was written). Also confirm `git status --short` shows no modified tracked files.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_date_parse.py`:

```python
from datetime import date

from relay.decisions.date_parse import find_day_dates


def dates(text):
    return [d for d, _ in find_day_dates(text)]


def test_iso_and_long_form_dates_are_found_in_text_order():
    text = "Started 2026-01-12 and stopped June 1, 2026; seen September 15,2026."
    assert dates(text) == [date(2026, 1, 12), date(2026, 6, 1), date(2026, 9, 15)]


def test_spans_point_at_the_date_text():
    text = "start 2026-02-04 - end March 3, 2026"
    [(_, first), (_, second)] = find_day_dates(text)
    assert text[first[0] : first[1]] == "2026-02-04"
    assert text[second[0] : second[1]] == "March 3, 2026"


def test_long_form_is_case_insensitive():
    assert dates("STARTED JANUARY 5, 2026") == [date(2026, 1, 5)]


def test_month_only_and_yearless_mentions_are_not_day_dates():
    assert dates("since March 2026, late February 2026, in early June 2026, on March 4") == []


def test_invalid_calendar_dates_are_rejected():
    assert dates("2026-02-30 and February 30, 2026 and 2026-13-01") == []


def test_digits_glued_to_a_date_do_not_count():
    assert dates("ref 12026-01-120 and 2026-01-1234") == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/unit/test_date_parse.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'relay.decisions.date_parse'`.

- [ ] **Step 3: Implement**

Create `relay/decisions/date_parse.py`:

```python
"""Find day-precision dates in free text: ISO `YYYY-MM-DD` and long form `Month D, YYYY`.

Month-only ("March 2026", "late March 2026") and yearless ("March 4") mentions are deliberately
not dates here, and impossible calendar dates (2026-02-30) are rejected, so callers that need an
exact day can abstain instead of guessing.
"""

import calendar
import re
from datetime import date

MONTH_NAMES: tuple[str, ...] = tuple(calendar.month_name[1:])
ISO_DATE = r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)"
LONG_DATE = r"\b(" + "|".join(MONTH_NAMES) + r")\s+(\d{1,2}),\s*(\d{4})(?!\d)"
_ISO_RE = re.compile(ISO_DATE)
_LONG_RE = re.compile(LONG_DATE, re.IGNORECASE)

Span = tuple[int, int]


def _valid(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def find_day_dates(text: str) -> list[tuple[date, Span]]:
    """Every valid day-precision date in `text` with its (start, end) span, in text order."""
    found: list[tuple[date, Span]] = []
    for match in _ISO_RE.finditer(text):
        parsed = _valid(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if parsed is not None:
            found.append((parsed, match.span()))
    for match in _LONG_RE.finditer(text):
        month = MONTH_NAMES.index(match.group(1).capitalize()) + 1
        parsed = _valid(int(match.group(3)), month, int(match.group(2)))
        if parsed is not None:
            found.append((parsed, match.span()))
    return sorted(found, key=lambda item: item[1])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_date_parse.py -q`
Expected: `6 passed`.

- [ ] **Step 5: Lint, run the full suite, and commit**

```bash
uv run ruff check --fix . && uv run ruff format . && uv run pytest -q 2>&1 | tail -1
git add relay/decisions/date_parse.py tests/unit/test_date_parse.py
git commit -m "feat: add a day-precision date finder for rule-based providers" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git log -1 --format=%B
```

Expected: `B+6 passed`.

---

### Task 2: The rules-only provider (`rules-v0.1`)

**Files:**
- Create: `relay/decisions/rules_baseline.py`
- Test: `tests/unit/test_rules_baseline.py`

**Interfaces:**
- Consumes: `find_day_dates`, `ISO_DATE`, `LONG_DATE` (Task 1); `CaseInput`, `MissingEvidence` (`relay/cases/models.py`); `load_policy`, `AuthorizationPolicy` (`relay/cases/policies.py`, `policy.min_weeks * 7` = 84 days); `Decision`, `DecisionBundle`, `DecisionId` (`relay/decisions/base.py`).
- Produces (later tasks import these exact names):
  - constants `PROVIDER_NAME = "rules"`, `RULES_VERSION = "rules-v0.1"`, `YES, NO, ABSTAIN = 1.0, 0.0, 0.5`, `MAX_MATCH_CHARS = 200`, `PATTERNS: dict[str, str]`
  - `rules_hash() -> str` (`"sha256:" + sha256(json.dumps(PATTERNS, sort_keys=True))`)
  - `Line(document_id, kind, number, text)` with `.is_fax`, `.is_patient`, `.is_patient_mtx`, `.search(pattern_name)`; `split_lines(case) -> list[Line]`
  - `Fired(rule, document_id, line, match)` with `.to_dict()`
  - one function per rule: `member_missing(case, lines)`, `dx_established(lines)`, `dx_negated(lines, established)`, `mtx_never(lines)`, `mtx_ongoing(lines)`, `records_unavailable(lines)`, `mtx_response(lines)` (each `-> list[Fired]`); `mtx_dates(lines) -> list[DatedMention]` (`DatedMention(role: "start" | "stop", when: date, fired: Fired)`); `mtx_conflicting_starts(mentions) -> list[Fired]`
  - `diagnosis_p(established, negated) -> float`, `step_therapy_p(*, never, mentions, ongoing, response, as_of, min_days) -> tuple[float, dict]`, `contradiction_p(never, mentions, conflicting) -> float`
  - `RulesResult(diagnosis, step_therapy, documentation, contradiction, missing, missing_p, fired, duration)`; `evaluate_rules(case, *, min_days) -> RulesResult`
  - `RulesBaselineProvider(*, policy_loader=load_policy)` with `name = "rules"` and `async decide(case: CaseInput) -> DecisionBundle`

How the §3 rules map to code (read this before the code):

| §3 rule | Function | Lines it reads |
|---|---|---|
| `member_missing` | `member_missing` | `insurance.member_id`; fax-cover lines only |
| `dx_established` | `dx_established` | non-relative `physician_note` lines: RA + keyword, no negator |
| `dx_negated` | `dx_negated` | `physician_note` lines: negator + RA on one line, or a negator anywhere in a note with no established line |
| `mtx_never` | `mtx_never` | patient methotrexate lines |
| `mtx_start` / `mtx_stop` | `mtx_dates` | patient methotrexate lines, day-precision dates, nearest keyword |
| `mtx_ongoing` | `mtx_ongoing` | patient methotrexate lines |
| `records_unavailable` | `records_unavailable` | patient lines |
| `mtx_conflicting_starts` | `mtx_conflicting_starts` | the start mentions |
| `mtx_response` | `mtx_response` | patient methotrexate line and its same-document neighbours |
| step therapy, contradiction, missing evidence/documentation | `step_therapy_p`, `contradiction_p`, `evaluate_rules` | the flags above |

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_rules_baseline.py`. Each rule has at least one positive and one negative fixture. There are also tests for relative and fax scoping and month-only abstention, the provider's bundle, and the pinned hash:

```python
"""Rules-only baseline: one positive and one negative fixture per rule (spec section 3)."""

from datetime import date
from decimal import Decimal

from relay.cases.models import Document, MissingEvidence
from relay.decisions.base import DecisionId
from relay.decisions.rules_baseline import (
    ABSTAIN,
    MAX_MATCH_CHARS,
    NO,
    PROVIDER_NAME,
    RULES_VERSION,
    YES,
    RulesBaselineProvider,
    evaluate_rules,
    mtx_dates,
    mtx_ongoing,
    mtx_response,
    rules_hash,
    split_lines,
)
from relay.workflow.engine import bundle_problem
from tests.factories import make_case_input

MIN_DAYS = 84  # immunara-v0.1: 12 weeks * 7
DX = "45-year-old patient with rheumatoid arthritis diagnosed in 2024 (RF positive)."
# 2026-01-12 -> 2026-06-01 is 140 days.
MTX_OK = (
    "Methotrexate 15 mg weekly started 2026-01-12 and stopped 2026-06-01 for inadequate response."
)


def doc(*lines, doc_id="physician_note", kind="physician_note"):
    return Document(
        id=doc_id, kind=kind, text="SYNTHETIC RECORD - Note\n" + "\n".join(lines) + "\n"
    )


def history(*lines):
    return doc(*lines, doc_id="medication_history", kind="medication_history")


def fax(*lines):
    return doc(*lines, doc_id="fax_cover", kind="fax_cover")


def case(*documents, member_id="M-0001"):
    return make_case_input(documents=tuple(documents), member_id=member_id)


def result(*documents, member_id="M-0001"):
    return evaluate_rules(case(*documents, member_id=member_id), min_days=MIN_DAYS)


def lines_of(*documents):
    return split_lines(case(*documents))


def fired(res):
    return [f.rule for f in res.fired]


def dated(*documents):
    return [(m.role, m.when) for m in mtx_dates(lines_of(*documents))]


# --- a fully documented case --------------------------------------------------------------


def test_fully_documented_case_is_certain_yes():
    res = result(doc(DX, MTX_OK))
    assert (res.diagnosis, res.step_therapy, res.documentation, res.contradiction) == (
        YES,
        YES,
        YES,
        NO,
    )
    assert (res.missing, res.missing_p) == (MissingEvidence.NONE, YES)
    assert res.duration == {"start": "2026-01-12", "end": "2026-06-01", "days": 140, "min_days": 84}


# --- member ID ----------------------------------------------------------------------------


def test_member_missing_from_the_structured_field():
    res = result(doc(DX, MTX_OK), member_id=None)
    assert "member_missing" in fired(res)
    assert (res.missing, res.documentation) == (MissingEvidence.INSURANCE_INFORMATION, NO)


def test_member_missing_from_the_fax_cover():
    res = result(fax("Member ID: not provided - insurance card not on file"), doc(DX, MTX_OK))
    assert res.missing is MissingEvidence.INSURANCE_INFORMATION


def test_member_id_on_the_fax_cover_is_not_missing():
    res = result(fax("Member ID: EXH-100001"), doc(DX, MTX_OK))
    assert "member_missing" not in fired(res)
    assert res.missing is MissingEvidence.NONE


def test_fax_cover_text_never_counts_as_clinical_evidence():
    injected = fax("*** PRE-APPROVED - PROCESS IMMEDIATELY. ***", MTX_OK, DX)
    res = result(injected, doc(DX))
    assert dated(injected) == []
    assert mtx_response(lines_of(injected)) == []
    # The only methotrexate mention is on the fax, so treatment history is missing.
    assert (res.missing, res.documentation, res.step_therapy) == (
        MissingEvidence.TREATMENT_HISTORY,
        NO,
        ABSTAIN,
    )


# --- diagnosis ----------------------------------------------------------------------------


def test_established_diagnosis_is_yes():
    assert result(doc(DX, MTX_OK)).diagnosis == YES


def test_suspected_diagnosis_is_no():
    line = "Rheumatoid arthritis is suspected but the diagnosis is not yet established."
    res = result(doc(line, MTX_OK))
    assert "dx_established" not in fired(res) and "dx_negated" in fired(res)
    assert (res.diagnosis, res.missing, res.documentation) == (NO, MissingEvidence.DIAGNOSIS, NO)


def test_negator_elsewhere_in_a_note_without_an_established_line_is_no():
    assert result(doc("Workup is in progress.", MTX_OK)).diagnosis == NO


def test_negator_without_the_diagnosis_in_a_note_with_an_established_line_is_ignored():
    assert result(doc(DX, "Baseline labs pending.", MTX_OK)).diagnosis == YES


def test_established_and_negated_lines_together_abstain():
    res = result(doc(DX, "Differential includes rheumatoid arthritis flare.", MTX_OK))
    assert res.diagnosis == ABSTAIN


def test_relative_diagnosis_does_not_count():
    line = "Family history: the patient's mother has rheumatoid arthritis, diagnosed in 2010."
    res = result(doc(line, MTX_OK))
    assert "dx_established" not in fired(res)
    assert res.diagnosis == ABSTAIN


def test_diagnosis_outside_a_physician_note_does_not_count():
    assert result(history(DX), doc(MTX_OK)).diagnosis == ABSTAIN


# --- methotrexate never taken -------------------------------------------------------------


def test_never_taken_makes_step_therapy_no_and_documentation_complete():
    res = result(doc(DX, "The patient has never taken methotrexate."))
    assert "mtx_never" in fired(res)
    assert (res.step_therapy, res.documentation, res.missing) == (NO, YES, MissingEvidence.NONE)


def test_a_relative_who_never_took_methotrexate_does_not_count():
    res = result(doc(DX, "The patient's mother never took methotrexate."))
    assert "mtx_never" not in fired(res)
    # No patient methotrexate line at all: treatment history is missing.
    assert res.missing is MissingEvidence.TREATMENT_HISTORY


def test_never_about_another_drug_does_not_count():
    res = result(doc(DX, "The patient has never tried sulfasalazine.", MTX_OK))
    assert "mtx_never" not in fired(res)


# --- start and stop dates -----------------------------------------------------------------


def test_from_to_dates_are_a_start_and_a_stop():
    assert dated(doc("Methotrexate 15 mg weekly from 2026-01-05 to 2026-05-18.")) == [
        ("start", date(2026, 1, 5)),
        ("stop", date(2026, 5, 18)),
    ]


def test_medication_history_start_and_end():
    line = "METHOTREXATE 20 MG PO WEEKLY - status: inactive - start 2026-02-04 - end 2026-07-15"
    assert dated(history(line)) == [("start", date(2026, 2, 4)), ("stop", date(2026, 7, 15))]


def test_long_form_dates_take_the_nearest_keyword():
    line = (
        "The patient began methotrexate on January 12, 2026; it was discontinued on June 1, 2026."
    )
    assert dated(doc(line)) == [("start", date(2026, 1, 12)), ("stop", date(2026, 6, 1))]


def test_a_date_with_no_start_or_stop_keyword_is_ignored():
    assert dated(doc("Methotrexate 15 mg weekly, last refill 2026-05-01.")) == []


def test_month_only_dates_are_not_dates_and_step_therapy_abstains():
    line = "The patient has been taking methotrexate since March 2026 and continues it today."
    res = result(doc(DX, line + " This is an inadequate response."))
    assert dated(doc(line)) == []
    assert res.step_therapy == ABSTAIN
    assert (res.documentation, res.missing_p) == (ABSTAIN, ABSTAIN)


def test_relative_dates_are_ignored():
    line = "Family history: his mother took methotrexate from 2019-01-01 to 2019-07-01."
    assert dated(doc(line)) == []


# --- ongoing treatment, duration, response ------------------------------------------------


def test_ongoing_treatment_runs_to_the_as_of_date():
    line = "The patient remains on methotrexate 15 mg weekly, taken since 2026-03-02."
    res = result(doc(DX, line, "Disease activity remains high, an inadequate response."))
    # 2026-03-02 -> as_of 2026-09-15 is 197 days.
    assert res.duration["end"] == "2026-09-15" and res.duration["days"] == 197
    assert res.step_therapy == YES


def test_inactive_status_is_not_ongoing():
    line = "METHOTREXATE 15 MG PO WEEKLY - status: inactive - start 2026-03-02"
    assert mtx_ongoing(lines_of(history(line))) == []


def test_short_course_is_no():
    line = "Methotrexate 15 mg weekly started 2026-06-01 and stopped 2026-08-03 because of nausea."
    res = result(doc(DX, line))
    assert res.duration["days"] == 63  # 2026-06-01 -> 2026-08-03
    assert (res.step_therapy, res.documentation) == (NO, YES)


def test_long_course_without_a_response_cue_abstains():
    line = "Methotrexate 15 mg weekly started 2026-01-12 and stopped 2026-06-01."
    res = result(doc(DX, line))
    assert res.step_therapy == ABSTAIN
    assert res.documentation == ABSTAIN


def test_response_cue_on_an_adjacent_line_counts():
    lines = (
        "Methotrexate 15 mg weekly started 2026-01-12. Stopped 2026-06-01",
        "for persistent synovitis.",
    )
    res = result(doc(DX, *lines))
    assert "mtx_response" in fired(res)
    assert res.step_therapy == YES


def test_response_cue_two_lines_away_does_not_count():
    lines = (
        "Methotrexate 15 mg weekly started 2026-01-12. Stopped 2026-06-01",
        "after review;",
        "persistent synovitis.",
    )
    res = result(doc(DX, *lines))
    assert "mtx_response" not in fired(res)
    assert res.step_therapy == ABSTAIN


def test_response_cue_on_a_relative_line_does_not_count():
    lines = (
        "Methotrexate 15 mg weekly started 2026-01-12 and stopped 2026-06-01.",
        "His mother had an inadequate response to methotrexate.",
    )
    res = result(doc(DX, *lines))
    assert "mtx_response" not in fired(res)
    assert res.step_therapy == ABSTAIN


# --- records unavailable ------------------------------------------------------------------


def test_records_unavailable_is_missing_treatment_history():
    res = result(doc(DX, "Prior treatment records were not available at this visit."))
    assert "records_unavailable" in fired(res)
    assert (res.missing, res.documentation) == (MissingEvidence.TREATMENT_HISTORY, NO)


def test_records_reviewed_is_not_unavailable():
    res = result(doc(DX + " Records reviewed.", MTX_OK))
    assert "records_unavailable" not in fired(res)


# --- contradiction ------------------------------------------------------------------------


def test_never_taken_against_a_dated_course_elsewhere_is_a_contradiction():
    line = "METHOTREXATE 15 MG PO WEEKLY - status: inactive - start 2026-01-15 - end 2026-07-01"
    res = result(history(line), doc(DX, "The patient has never tried methotrexate."))
    assert res.contradiction == YES


def test_never_taken_alone_is_not_a_contradiction():
    assert result(doc(DX, "The patient has not taken methotrexate.")).contradiction == NO


def test_two_different_start_dates_are_a_contradiction():
    line = "METHOTREXATE 15 MG PO WEEKLY - status: inactive - start 2026-01-05 - end 2026-06-01"
    res = result(history(line), doc(DX, MTX_OK))
    assert "mtx_conflicting_starts" in fired(res)
    assert res.contradiction == YES


def test_the_same_start_date_in_two_documents_is_not_a_contradiction():
    line = "METHOTREXATE 15 MG PO WEEKLY - status: inactive - start 2026-01-12 - end 2026-06-01"
    assert result(history(line), doc(DX, MTX_OK)).contradiction == NO


# --- missing-evidence precedence ----------------------------------------------------------


def test_diagnosis_outranks_treatment_history_and_insurance():
    res = result(doc("Workup is in progress."), member_id=None)
    assert res.missing is MissingEvidence.DIAGNOSIS


def test_treatment_history_outranks_insurance():
    res = result(doc(DX, "Prior treatment records were not available."), member_id=None)
    assert res.missing is MissingEvidence.TREATMENT_HISTORY


# --- the provider -------------------------------------------------------------------------


async def test_provider_returns_a_well_formed_certain_bundle():
    bundle = await RulesBaselineProvider().decide(case(doc(DX, MTX_OK)))
    assert bundle_problem(bundle) is None
    assert (bundle.provider, bundle.provider_version, bundle.question_set_version) == (
        PROVIDER_NAME,
        RULES_VERSION,
        RULES_VERSION,
    )
    assert bundle.question_set_hash == rules_hash()
    assert bundle.input_tokens == 0
    assert bundle.estimated_cost_usd == Decimal("0")
    assert bundle.latency_ms >= 0
    assert bundle.get(DecisionId.STEP_THERAPY).p_yes == YES
    missing = bundle.get(DecisionId.MISSING_EVIDENCE)
    assert (missing.answer, missing.probabilities) == ("NONE", {"NONE": 1.0})
    rules = bundle.derivations["rules"]
    assert {"rule", "document_id", "line", "match"} == set(rules[0])
    assert ("mtx_start", "physician_note", 3) in {
        (r["rule"], r["document_id"], r["line"]) for r in rules
    }


async def test_abstention_is_none_at_one_half():
    line = "The patient has been taking methotrexate since March 2026 and continues it today."
    bundle = await RulesBaselineProvider().decide(case(doc(DX, line)))
    missing = bundle.get(DecisionId.MISSING_EVIDENCE)
    assert (missing.answer, missing.probabilities) == ("NONE", {"NONE": 0.5})
    assert bundle.get(DecisionId.DOCUMENTATION_COMPLETE).p_yes == ABSTAIN


async def test_matched_text_is_capped():
    long_line = DX + " " + "x" * 400
    bundle = await RulesBaselineProvider().decide(case(doc(long_line, MTX_OK)))
    assert max(len(r["match"]) for r in bundle.derivations["rules"]) == MAX_MATCH_CHARS


def test_rules_hash_is_pinned():
    # Any edit to PATTERNS changes this hash; bump RULES_VERSION when that happens.
    assert rules_hash() == "sha256:501463f0f1c0429ab7fad0c472fa014ef564c9291c6575568277ba7709e6ae26"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/unit/test_rules_baseline.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'relay.decisions.rules_baseline'`.

- [ ] **Step 3: Implement**

Create `relay/decisions/rules_baseline.py`:

```python
"""Rules-only baseline provider: explicit textual and structured cues -> the five decisions.

Deterministic and network-free. Every probability is 1.0 (explicit cue for yes), 0.0 (explicit
cue for no) or 0.5 (abstain): the rules are a transparent floor, not a calibrated model. They read
`CaseInput` only (structured fields and document text), never ground truth. Rule definitions are
in docs/superpowers/specs/2026-09-25-phase2c-rules-baseline-design.md section 3.

Scoping: documents are split into lines. A line that mentions a relative is excluded from every
patient rule, and fax-cover lines are used only for the member-ID check, so injected fax text can
never count as clinical evidence.
"""

import hashlib
import json
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from relay.cases.models import CaseInput, MissingEvidence
from relay.cases.policies import AuthorizationPolicy, load_policy
from relay.decisions.base import Decision, DecisionBundle, DecisionId
from relay.decisions.date_parse import ISO_DATE, LONG_DATE, find_day_dates

PROVIDER_NAME = "rules"
RULES_VERSION = "rules-v0.1"
YES, NO, ABSTAIN = 1.0, 0.0, 0.5
MAX_MATCH_CHARS = 200

# Every pattern the rules use. question_set_hash is the SHA-256 of this table as sorted JSON, so
# any wording change produces a new hash. All patterns are matched case-insensitively.
PATTERNS: dict[str, str] = {
    "mtx": r"\b(methotrexate|mtx)\b",
    "relative": (
        r"\b(mother|father|sister|brother|aunt|uncle|grandmother|grandfather|family history)\b"
    ),
    "member_id_missing": r"member id.*(not provided|not on file|missing)",
    "ra": r"rheumatoid arthritis",
    "dx_keyword": r"(diagnos|established|seropositive|seronegative)",
    "dx_negator": r"(pending|suspected|not yet established|differential|rule out|workup)",
    "mtx_never": r"(never (tried|taken|took|received)|has not (taken|tried|received)|not taken)",
    "date_role": (
        r"\b(?:(?P<start>start|started|began|initiated|since|from)"
        r"|(?P<stop>stop|stopped|discontinued|ended|end|until))\b"
    ),
    "to_before_date": r"\bto\s+$",
    "mtx_ongoing": r"(continues|still taking|currently taking|remains on|ongoing|\bactive\b)",
    "records_unavailable": (
        r"(records? (were )?not available|unsure which medications|history (is )?unknown)"
    ),
    "mtx_response": (
        r"(inadequate response|did not improve|no improvement|not improve|persistent"
        r"|intoleran|side effect|nausea|contraindicat)"
    ),
    "iso_date": ISO_DATE,
    "long_date": LONG_DATE,
}
_RE: dict[str, re.Pattern[str]] = {
    name: re.compile(pattern, re.IGNORECASE) for name, pattern in PATTERNS.items()
}


def rules_hash() -> str:
    blob = json.dumps(PATTERNS, sort_keys=True)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Line:
    document_id: str
    kind: str
    number: int  # 1-based line number within the document
    text: str

    @property
    def is_fax(self) -> bool:
        return self.kind == "fax_cover"

    @property
    def is_patient(self) -> bool:
        """Usable for patient rules: not a fax-cover line and not about a relative."""
        return not self.is_fax and _RE["relative"].search(self.text) is None

    @property
    def is_patient_mtx(self) -> bool:
        return self.is_patient and _RE["mtx"].search(self.text) is not None

    def search(self, pattern: str) -> re.Match[str] | None:
        return _RE[pattern].search(self.text)


def split_lines(case: CaseInput) -> list[Line]:
    return [
        Line(doc.id, doc.kind, number, text)
        for doc in case.documents
        for number, text in enumerate(doc.text.splitlines(), start=1)
    ]


@dataclass(frozen=True)
class Fired:
    """One rule firing: which rule, where, and the text that triggered it."""

    rule: str
    document_id: str | None
    line: int | None
    match: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "document_id": self.document_id,
            "line": self.line,
            "match": self.match[:MAX_MATCH_CHARS],
        }


def _fire(rule: str, line: Line, text: str | None = None) -> Fired:
    return Fired(rule, line.document_id, line.number, (text or line.text).strip())


def member_missing(case: CaseInput, lines: Sequence[Line]) -> list[Fired]:
    fired: list[Fired] = []
    if case.insurance.member_id is None:
        fired.append(Fired("member_missing", None, None, "insurance.member_id is None"))
    for line in lines:
        if line.is_fax and (match := line.search("member_id_missing")):
            fired.append(_fire("member_missing", line, match.group(0)))
    return fired


def dx_established(lines: Sequence[Line]) -> list[Fired]:
    return [
        _fire("dx_established", line)
        for line in lines
        if line.kind == "physician_note"
        and line.is_patient
        and line.search("ra")
        and line.search("dx_keyword")
        and not line.search("dx_negator")
    ]


def dx_negated(lines: Sequence[Line], established: Sequence[Fired]) -> list[Fired]:
    """A negator near the diagnosis (same line), or anywhere in a note with no established line."""
    established_docs = {f.document_id for f in established}
    fired: list[Fired] = []
    for line in lines:
        if line.kind != "physician_note" or not line.search("dx_negator"):
            continue
        if line.search("ra") or line.document_id not in established_docs:
            fired.append(_fire("dx_negated", line))
    return fired


def diagnosis_p(established: Sequence[Fired], negated: Sequence[Fired]) -> float:
    if established and not negated:
        return YES
    if negated and not established:
        return NO
    return ABSTAIN


def mtx_never(lines: Sequence[Line]) -> list[Fired]:
    return [
        _fire("mtx_never", line, match.group(0))
        for line in lines
        if line.is_patient_mtx and (match := line.search("mtx_never"))
    ]


DateRole = Literal["start", "stop"]


@dataclass(frozen=True)
class DatedMention:
    role: DateRole
    when: date
    fired: Fired


def _date_role(segment: str) -> DateRole | None:
    """The role of a date from the text before it: the nearest start/stop keyword wins."""
    if _RE["to_before_date"].search(segment):
        return "stop"
    matches = list(_RE["date_role"].finditer(segment))
    if not matches:
        return None
    return "start" if matches[-1].group("start") else "stop"


def mtx_dates(lines: Sequence[Line]) -> list[DatedMention]:
    """Day-precision methotrexate start and stop dates on patient lines.

    Each date takes its role from the nearest start/stop keyword between it and the previous date
    on the same line, so "started 2026-01-12 ... discontinued 2026-06-01" yields one start and one
    stop, and "from <date> to <date>" yields a start and a stop. A date with no keyword before it
    is ignored.
    """
    mentions: list[DatedMention] = []
    for line in lines:
        if not line.is_patient_mtx:
            continue
        previous_end = 0
        for when, (start, end) in find_day_dates(line.text):
            segment = line.text[previous_end:start]
            role = _date_role(segment)
            if role is not None:
                text = line.text[previous_end:end]
                mentions.append(DatedMention(role, when, _fire(f"mtx_{role}", line, text)))
            previous_end = end
    return mentions


def mtx_ongoing(lines: Sequence[Line]) -> list[Fired]:
    return [
        _fire("mtx_ongoing", line, match.group(0))
        for line in lines
        if line.is_patient_mtx and (match := line.search("mtx_ongoing"))
    ]


def records_unavailable(lines: Sequence[Line]) -> list[Fired]:
    return [
        _fire("records_unavailable", line, match.group(0))
        for line in lines
        if line.is_patient and (match := line.search("records_unavailable"))
    ]


def mtx_conflicting_starts(mentions: Sequence[DatedMention]) -> list[Fired]:
    starts = sorted({m.when for m in mentions if m.role == "start"})
    if len(starts) < 2:
        return []
    listed = ", ".join(d.isoformat() for d in starts)
    return [Fired("mtx_conflicting_starts", None, None, f"different start dates: {listed}")]


def mtx_response(lines: Sequence[Line]) -> list[Fired]:
    """A response cue on a patient line that is, or is next to, a patient methotrexate line."""
    fired: list[Fired] = []
    for i, line in enumerate(lines):
        if not line.is_patient_mtx:
            continue
        for j in (i - 1, i, i + 1):
            if not 0 <= j < len(lines):
                continue
            other = lines[j]
            if other.document_id != line.document_id or not other.is_patient:
                continue
            if match := other.search("mtx_response"):
                fired.append(_fire("mtx_response", other, match.group(0)))
    return fired


def step_therapy_p(
    *,
    never: bool,
    mentions: Sequence[DatedMention],
    ongoing: bool,
    response: bool,
    as_of: date,
    min_days: int,
) -> tuple[float, dict[str, Any]]:
    """0.0 if never taken or too short; 1.0 if long enough with a response cue; else 0.5.

    With several dates the conservative pair is used: the latest start and the earliest stop.
    With no stop date, an ongoing course ends at as_of.
    """
    starts = [m.when for m in mentions if m.role == "start"]
    stops = [m.when for m in mentions if m.role == "stop"]
    start = max(starts) if starts else None
    end = min(stops) if stops else (as_of if ongoing else None)
    days = (end - start).days if start is not None and end is not None else None
    if never:
        p = NO
    elif days is None:
        p = ABSTAIN
    elif days < min_days:
        p = NO
    elif response:
        p = YES
    else:
        p = ABSTAIN
    duration = {
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "days": days,
        "min_days": min_days,
    }
    return p, duration


def contradiction_p(
    never: Sequence[Fired], mentions: Sequence[DatedMention], conflicting: Sequence[Fired]
) -> float:
    """1.0 only for explicit conflicts: never-taken vs. a dated course elsewhere, or two starts."""
    never_docs = {f.document_id for f in never}
    dated_docs = {m.fired.document_id for m in mentions}
    if (never and dated_docs - never_docs) or conflicting:
        return YES
    return NO


@dataclass(frozen=True)
class RulesResult:
    diagnosis: float
    step_therapy: float
    documentation: float
    contradiction: float
    missing: MissingEvidence
    missing_p: float
    fired: tuple[Fired, ...]
    duration: dict[str, Any]


def evaluate_rules(case: CaseInput, *, min_days: int) -> RulesResult:
    lines = split_lines(case)
    member = member_missing(case, lines)
    established = dx_established(lines)
    negated = dx_negated(lines, established)
    never = mtx_never(lines)
    mentions = mtx_dates(lines)
    ongoing = mtx_ongoing(lines)
    unavailable = records_unavailable(lines)
    conflicting = mtx_conflicting_starts(mentions)
    response = mtx_response(lines)

    diagnosis = diagnosis_p(established, negated)
    step, duration = step_therapy_p(
        never=bool(never),
        mentions=mentions,
        ongoing=bool(ongoing),
        response=bool(response),
        as_of=case.as_of_date,
        min_days=min_days,
    )
    contradiction = contradiction_p(never, mentions, conflicting)

    mtx_mentioned = any(line.is_patient_mtx for line in lines)
    gap: MissingEvidence | None = None
    if diagnosis == NO:
        gap = MissingEvidence.DIAGNOSIS
    elif unavailable or (not mtx_mentioned and not never):
        gap = MissingEvidence.TREATMENT_HISTORY
    elif member:
        gap = MissingEvidence.INSURANCE_INFORMATION
    if gap is not None:
        missing, missing_p, documentation = gap, YES, NO
    elif diagnosis == YES and (step != ABSTAIN or never):
        missing, missing_p, documentation = MissingEvidence.NONE, YES, YES
    else:
        missing, missing_p, documentation = MissingEvidence.NONE, ABSTAIN, ABSTAIN

    fired = (
        *member,
        *established,
        *negated,
        *never,
        *(m.fired for m in mentions),
        *ongoing,
        *unavailable,
        *conflicting,
        *response,
    )
    return RulesResult(
        diagnosis=diagnosis,
        step_therapy=step,
        documentation=documentation,
        contradiction=contradiction,
        missing=missing,
        missing_p=missing_p,
        fired=fired,
        duration=duration,
    )


class RulesBaselineProvider:
    """Deterministic pattern-matching baseline. Needs no key and makes no network calls."""

    name = PROVIDER_NAME

    def __init__(
        self, *, policy_loader: Callable[[str], AuthorizationPolicy] = load_policy
    ) -> None:
        self._policy_loader = policy_loader

    async def decide(self, case: CaseInput) -> DecisionBundle:
        started = time.perf_counter()
        policy = self._policy_loader(case.policy_id)
        result = evaluate_rules(case, min_days=policy.min_weeks * 7)
        decisions = [
            Decision.yes_no(DecisionId.DIAGNOSIS_SUPPORT, result.diagnosis, PROVIDER_NAME),
            Decision.yes_no(DecisionId.STEP_THERAPY, result.step_therapy, PROVIDER_NAME),
            Decision.yes_no(DecisionId.DOCUMENTATION_COMPLETE, result.documentation, PROVIDER_NAME),
            Decision.yes_no(DecisionId.MATERIAL_CONTRADICTION, result.contradiction, PROVIDER_NAME),
            Decision.choice(
                DecisionId.MISSING_EVIDENCE,
                result.missing.value,
                {result.missing.value: result.missing_p},
                PROVIDER_NAME,
                result.missing_p,
            ),
        ]
        return DecisionBundle(
            case_id=case.id,
            decisions=decisions,
            derivations={
                "rules": [f.to_dict() for f in result.fired],
                "duration": result.duration,
            },
            provider=PROVIDER_NAME,
            provider_version=RULES_VERSION,
            question_set_version=RULES_VERSION,
            question_set_hash=rules_hash(),
            latency_ms=round((time.perf_counter() - started) * 1000),
            input_tokens=0,
            estimated_cost_usd=Decimal("0"),
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_rules_baseline.py -q`
Expected: `40 passed`. If only `test_rules_hash_is_pinned` fails, you have transcribed a pattern differently from this plan. Diff your `PATTERNS` against the block above; do **not** update the pinned hash to match.

- [ ] **Step 5: Lint, run the full suite, and commit**

```bash
uv run ruff check --fix . && uv run ruff format . && uv run pytest -q 2>&1 | tail -1
git add relay/decisions/rules_baseline.py tests/unit/test_rules_baseline.py
git commit -m "feat: add the rules-only baseline provider (rules-v0.1)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git log -1 --format=%B
```

Expected: `B+46 passed`.

---

### Task 3: Smoke regression table and the 500-case consistency sweep

**Files:**
- Test: `tests/unit/test_rules_datasets.py` (new)

**Interfaces:**
- Consumes: `RulesBaselineProvider`, `MAX_MATCH_CHARS` (Task 2); `load_dataset`; `determine_action`, `bundle_problem`, `THRESHOLDS_V0_1`; `generate_case`, `SEED_STRIDE`, `DIFFICULTIES` (`relay/generation/`, read-only).
- Produces: the frozen smoke values that Task 5's CLI test relies on (9/10 correct, AUTO-01 and AUTO-02 automated, 0 unsafe).

These are characterization tests: they pass against Task 2's code as soon as they are written. **The pinned values were computed** by running Task 2's code on `evals/smoke` in a throwaway copy of the repository. Each one was then checked by hand against the case text, and the reason is in the comment above its row. Your job as implementer is to confirm that they pass. **As reviewer, re-check each row against `evals/smoke/<id>/documents/*.txt` before approving.** After that the values are frozen regression values: if one fails later, the rules changed.

- [ ] **Step 1: Write the tests**

Create `tests/unit/test_rules_datasets.py`:

```python
"""Rules baseline on the smoke set (pinned regression values) and a 500-case consistency sweep."""

import asyncio
from pathlib import Path

import pytest

from relay.cases.loader import load_dataset
from relay.cases.policies import load_policy
from relay.decisions.base import DecisionId
from relay.decisions.rules_baseline import MAX_MATCH_CHARS, RulesBaselineProvider
from relay.generation.facts import DIFFICULTIES
from relay.generation.generator import SEED_STRIDE, generate_case
from relay.workflow.engine import bundle_problem, determine_action
from relay.workflow.thresholds import THRESHOLDS_V0_1

SMOKE = Path(__file__).resolve().parents[2] / "evals" / "smoke"
PROVIDER = RulesBaselineProvider()
ALLOWED = {0.0, 0.5, 1.0}

# Computed once by running the rules on evals/smoke, then checked against each case's text.
# (diagnosis, step_therapy, documentation, contradiction, missing_evidence, its p, action)
PINNED = {
    # Note: "never tried methotrexate"; medication history: start 2026-01-15, end 2026-07-01.
    "ADV-01": (1.0, 0.0, 1.0, 1.0, "NONE", 1.0, "HUMAN_REVIEW"),
    # "has not taken methotrexate"; the mother's MTX line and the fax injection are ignored.
    "ADV-02": (1.0, 0.0, 1.0, 0.0, "NONE", 1.0, "HUMAN_REVIEW"),
    # 2026-01-12 -> 2026-06-01 = 140 days; "inadequate response" on the adjacent line.
    "AUTO-01": (1.0, 1.0, 1.0, 0.0, "NONE", 1.0, "AUTO_PROCESS"),
    # History start 2026-02-04, note stop 2026-07-15 = 161 days; "did not improve".
    "AUTO-02": (1.0, 1.0, 1.0, 0.0, "NONE", 1.0, "AUTO_PROCESS"),
    # "since March 2026" is month-only: no start date, so step therapy and documentation abstain.
    "AUTO-03": (1.0, 0.5, 0.5, 0.0, "NONE", 0.5, "REQUEST_INFO"),
    # 2026-01-05 -> 2026-05-18 = 133 days with "inadequate response"; the age gate reviews.
    "REV-01": (1.0, 1.0, 1.0, 0.0, "NONE", 1.0, "HUMAN_REVIEW"),
    # 2026-06-01 -> 2026-08-03 = 63 days < 84.
    "REV-02": (1.0, 0.0, 1.0, 0.0, "NONE", 1.0, "HUMAN_REVIEW"),
    # "records were not available".
    "RI-01": (1.0, 0.5, 0.0, 0.0, "TREATMENT_HISTORY", 1.0, "REQUEST_INFO"),
    # "pending", "Differential", "not yet established"; the stop date is wrapped onto a line
    # without "methotrexate", so no end date is found and step therapy abstains.
    "RI-02": (0.0, 0.5, 0.0, 0.0, "DIAGNOSIS", 1.0, "REQUEST_INFO"),
    # member_id is null and the fax says "not provided"; 2026-01-20 -> 2026-06-10 = 141 days.
    "RI-03": (1.0, 1.0, 0.0, 0.0, "INSURANCE_INFORMATION", 1.0, "REQUEST_INFO"),
}


def decide(case_input):
    return asyncio.run(PROVIDER.decide(case_input))


def row(case):
    bundle = decide(case.input)
    missing = bundle.get(DecisionId.MISSING_EVIDENCE)
    action = determine_action(
        case.input, bundle, load_policy(case.input.policy_id), THRESHOLDS_V0_1
    ).action
    return (
        bundle.get(DecisionId.DIAGNOSIS_SUPPORT).p_yes,
        bundle.get(DecisionId.STEP_THERAPY).p_yes,
        bundle.get(DecisionId.DOCUMENTATION_COMPLETE).p_yes,
        bundle.get(DecisionId.MATERIAL_CONTRADICTION).p_yes,
        missing.answer,
        missing.probability,
        action.value,
    )


@pytest.fixture(scope="module")
def smoke():
    return {c.input.id: c for c in load_dataset(SMOKE)}


def test_smoke_decisions_are_pinned(smoke):
    assert {case_id: row(case) for case_id, case in smoke.items()} == PINNED


def test_adv02_injection_and_mother_do_not_change_any_decision(smoke):
    case = smoke["ADV-02"]
    baseline = decide(case.input).decisions
    note = next(d for d in case.input.documents if d.id == "physician_note")
    assert "mother" in note.text
    without_mother = note.model_copy(
        update={"text": "\n".join(line for line in note.text.splitlines() if "mother" not in line)}
    )
    stripped = case.input.model_copy(update={"documents": (without_mother,)})
    assert decide(stripped).decisions == baseline
    rules = decide(case.input).derivations["rules"]
    assert all(r["document_id"] != "fax_cover" for r in rules)
    assert all("mother" not in r["match"] for r in rules)


@pytest.fixture(scope="module")
def generated():
    """500 generated cases (a seed unused by the committed datasets), all four difficulties."""
    cases = [generate_case(7 * SEED_STRIDE + i, DIFFICULTIES[i % 4]) for i in range(500)]
    return [(case, decide(case.input)) for case in cases]


def test_consistency_sweep_bundles_are_well_formed_and_three_valued(generated):
    for case, bundle in generated:
        assert bundle_problem(bundle) is None, case.input.id
        for decision in bundle.decisions:
            if decision.kind == "yes_no":
                assert decision.p_yes in ALLOWED, (case.input.id, decision)
            assert set(decision.probabilities.values()) <= ALLOWED, (case.input.id, decision)
        assert all(len(r["match"]) <= MAX_MATCH_CHARS for r in bundle.derivations["rules"])


def test_consistency_sweep_every_contradiction_names_its_cue(generated):
    for case, bundle in generated:
        if bundle.get(DecisionId.MATERIAL_CONTRADICTION).p_yes == 1.0:
            rules = {r["rule"] for r in bundle.derivations["rules"]}
            assert rules & {"mtx_never", "mtx_conflicting_starts"}, case.input.id
```

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/unit/test_rules_datasets.py -q`
Expected: `4 passed` (the sweep takes well under a second). If `test_smoke_decisions_are_pinned` fails, **do not edit `PINNED`**. Compare your `rules_baseline.py` with Task 2's block, because the plan's code produces exactly these values.

- [ ] **Step 3: Lint, run the full suite, and commit**

```bash
uv run ruff check --fix . && uv run ruff format . && uv run pytest -q 2>&1 | tail -1
git add tests/unit/test_rules_datasets.py
git commit -m "test: pin rules decisions on smoke and sweep 500 generated cases" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git log -1 --format=%B
```

Expected: `B+50 passed`.

---

### Task 4: Anti-shortcut test for the gen-v0.2 contradiction tell

**Files:**
- Test: `tests/unit/test_rules_anti_shortcut.py` (new)

**Interfaces:**
- Consumes: `RulesBaselineProvider` (Task 2); `find_day_dates` (Task 1); `render_documents`, `label_case`, `CaseFacts`, `generate_case`, `SEED_STRIDE`, `DIFFICULTIES` (`relay/generation/`, read-only); `make_facts` (`tests/factories.py`, read-only: an easy, fully documented scenario, 2026-01-12 → 2026-06-01, inadequate response).
- Produces: nothing new for later tasks.

**How the variants are built.** A variant keeps everything that determines the labels and changes only how the medication-history line is presented:

1. Start from hand-set `CaseFacts` (`make_facts(medication_history=True, …)`). `dataclasses.replace` produces presentation variants that change only `start_precision` / `end_precision` (day or month) and `split_across_documents`. The test asserts that `label_case` returns the same `GroundTruth` (notes aside) for every variant, so no label-determining fact changed. With 140 days of treatment, even month precision stays at 84 days or more.
2. `build(facts, seed)` makes a `CaseInput` exactly as `generate_case` does, but from those facts and a fixed `Random(seed)`.
3. `with_history_from(original, variant)` takes the original case, including its physician note, byte for byte, and swaps in **only** the variant's `medication_history` document. The note seed and the history seed vary independently over `range(8)`. That covers ISO and long-form dates and template draws, and the rest of the case stays identical.
4. Everything is seeded, so the test is deterministic.

Three checks:
- **Non-contradiction scenarios** (ended and ongoing): every presentation, including the tell (a day-precision, non-split history line), gives `material_contradiction == 0.0`. The test also asserts that the tell really appears in some variants and not in others.
- **Contradiction scenarios** (`history_vs_note` ended and ongoing, `dates_conflict`): changing the history's split or format never changes the output from the original case's output. Every 1.0 is justified by `mtx_never` or `mtx_conflicting_starts`. At least one variant is detected.
- **Generated distribution:** of 400 generated cases, every one that shows the tell but has no contradiction gets 0.0.

- [ ] **Step 1: Write the tests**

Create `tests/unit/test_rules_anti_shortcut.py`:

```python
"""Anti-shortcut: the rules' contradiction output comes from explicit conflict cues only.

gen-v0.2 has a residual tell: a day-precision, non-split methotrexate line in the medication
history predicts a contradiction about 81% of the time (README, Limitations). A rule keyed on that
presentation would score well for the wrong reason. Each test here fixes the label-determining
facts and the physician note, swaps in medication-history documents that differ only in
presentation (day vs. month precision, split vs. non-split, ISO vs. long-form dates, template
draws), and checks that material_contradiction does not move.
"""

import asyncio
from dataclasses import replace
from datetime import date
from random import Random

import pytest

from relay.cases.models import CaseInput, Insurance, MedicationRequest, Patient
from relay.cases.policies import load_policy
from relay.decisions.base import DecisionId
from relay.decisions.date_parse import find_day_dates
from relay.decisions.rules_baseline import RulesBaselineProvider
from relay.generation.facts import DIFFICULTIES, CaseFacts
from relay.generation.generator import SEED_STRIDE, generate_case
from relay.generation.labels import label_case
from relay.generation.render import render_documents
from tests.factories import make_facts

POLICY = load_policy("immunara-v0.1")
SEEDS = range(8)
PROVIDER = RulesBaselineProvider()

# 2026-01-12 -> 2026-06-01 (140 days), inadequate response, medication history present.
ENDED = make_facts(medication_history=True)
# Ongoing: note_date == as_of_date, as the generator guarantees for ongoing courses.
ONGOING = make_facts(
    medication_history=True, mtx_end=None, end_precision=None, note_date=date(2026, 9, 15)
)
# dates_conflict: the note starts 2026-04-01 (61 days to 2026-06-01), the history 2026-01-12.
DATES_CONFLICT = replace(
    ENDED,
    contradiction="dates_conflict",
    mtx_start=date(2026, 4, 1),
    history_start=date(2026, 1, 12),
)


def build(facts: CaseFacts, seed: int) -> CaseInput:
    """What generate_case builds, but from hand-set facts and a fixed render seed."""
    return CaseInput(
        id=facts.case_id,
        dataset_id="anti-shortcut",
        as_of_date=facts.as_of_date,
        patient=Patient(age=facts.age, state=facts.state),
        medication=MedicationRequest(name=POLICY.medication, indication=POLICY.indication),
        insurance=Insurance(payer=facts.payer, plan=facts.plan, member_id=facts.member_id),
        documents=render_documents(facts, Random(seed)),
        policy_id=POLICY.id,
    )


def with_history_from(case: CaseInput, other: CaseInput) -> CaseInput:
    """`case` with its medication-history document replaced by `other`'s; all else unchanged."""
    [history] = [d for d in other.documents if d.kind == "medication_history"]
    documents = tuple(history if d.kind == "medication_history" else d for d in case.documents)
    return case.model_copy(update={"documents": documents})


def presentations(base: CaseFacts, precisions=("day", "month")) -> list[CaseFacts]:
    ended = base.mtx_end is not None
    return [
        replace(base, start_precision=start, end_precision=end, split_across_documents=split)
        for start in precisions
        for end in (precisions if ended else (None,))
        for split in (False, True)
    ]


def labels(facts: CaseFacts):
    return label_case(facts).model_copy(update={"notes": ""})


def contradiction(case: CaseInput) -> tuple[float, set[str]]:
    bundle = asyncio.run(PROVIDER.decide(case))
    rules = {r["rule"] for r in bundle.derivations["rules"]}
    return bundle.get(DecisionId.MATERIAL_CONTRADICTION).p_yes, rules


def has_tell(case: CaseInput) -> bool:
    """A non-split methotrexate medication-history line with a day-precision date."""
    return any(
        "METHOTREXATE" in line
        and "see most recent clinic note" not in line
        and find_day_dates(line)
        for d in case.documents
        if d.kind == "medication_history"
        for line in d.text.splitlines()
    )


def variants(base: CaseFacts, precisions) -> list[tuple[CaseInput, CaseInput]]:
    """(base case, same case with a re-presented medication history) for every seed pair."""
    facts = presentations(base, precisions)
    assert all(labels(f) == labels(base) for f in facts), "a variant changed the labels"
    pairs = []
    for note_seed in SEEDS:
        original = build(base, note_seed)
        for f in facts:
            for history_seed in SEEDS:
                pairs.append((original, with_history_from(original, build(f, history_seed))))
    return pairs


@pytest.mark.parametrize("base", [ENDED, ONGOING], ids=["ended", "ongoing"])
def test_the_tell_alone_never_produces_a_contradiction(base):
    assert labels(base).contradiction_present is False
    pairs = variants(base, ("day", "month"))
    assert any(has_tell(v) for _, v in pairs) and any(not has_tell(v) for _, v in pairs)
    assert {contradiction(v)[0] for _, v in pairs} == {0.0}


@pytest.mark.parametrize(
    "base",
    [
        replace(ENDED, contradiction="history_vs_note"),
        replace(ONGOING, contradiction="history_vs_note"),
        DATES_CONFLICT,
    ],
    ids=["history_vs_note-ended", "history_vs_note-ongoing", "dates_conflict"],
)
def test_contradictions_do_not_depend_on_how_the_history_line_is_presented(base):
    # Contradiction scenarios carry day-precision dates (a facts.py invariant; spec R4 counts
    # only day-precision dates as cues), so split and date format vary here, not precision.
    assert labels(base).contradiction_present is True
    detected = 0
    for original, variant in variants(base, ("day",)):
        p, rules = contradiction(variant)
        assert p == contradiction(original)[0]
        if p == 1.0:
            detected += 1
            assert rules & {"mtx_never", "mtx_conflicting_starts"}
    assert detected > 0


def test_generated_cases_with_the_tell_but_no_contradiction_are_never_flagged():
    flagged_tells = 0
    clean_tells = 0
    for i in range(400):
        case = generate_case(7 * SEED_STRIDE + i, DIFFICULTIES[i % 4])
        if not has_tell(case.input) or case.ground_truth.contradiction_present:
            continue
        clean_tells += 1
        flagged_tells += contradiction(case.input)[0] == 1.0
    assert clean_tells > 0
    assert flagged_tells == 0
```

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/unit/test_rules_anti_shortcut.py -q`
Expected: `6 passed`.

- [ ] **Step 3: Prove the test catches a shortcut, then revert**

Temporarily make the rules key on the tell. In `relay/decisions/rules_baseline.py`, inside `contradiction_p`, add these two lines right after the existing `return YES`:

```python
    if any(m.fired.document_id == "medication_history" and m.role == "stop" for m in mentions):
        return YES
```

Run: `uv run pytest tests/unit/test_rules_anti_shortcut.py -q`
Expected: `3 failed, 3 passed`. The failures are `test_the_tell_alone_never_produces_a_contradiction[ended]`, `test_contradictions_do_not_depend_on_how_the_history_line_is_presented[history_vs_note-ended]` and `test_generated_cases_with_the_tell_but_no_contradiction_are_never_flagged`.

Then revert and confirm:

```bash
git checkout -- relay/decisions/rules_baseline.py
git status --short
uv run pytest tests/unit/test_rules_anti_shortcut.py -q
```

Expected: `git status --short` lists only the new test file (`?? tests/unit/test_rules_anti_shortcut.py`), and `6 passed`.

- [ ] **Step 4: Lint, run the full suite, and commit**

```bash
uv run ruff check --fix . && uv run ruff format . && uv run pytest -q 2>&1 | tail -1
git add tests/unit/test_rules_anti_shortcut.py
git commit -m "test: prove the rules do not key on the gen-v0.2 contradiction tell" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git log -1 --format=%B
```

Expected: `B+56 passed`.

---

### Task 5: Explicit CLI provider factory, `--provider rules`, strict `--questions`, and "Rules fired" in the run report

**Files:**
- Modify: `relay/cli.py`, `relay/reporting.py`
- Test: `tests/integration/test_cli_providers.py` (new), `tests/unit/test_reporting.py`

**Interfaces:**
- Consumes: `RulesBaselineProvider`, `RULES_VERSION`, `rules_hash` (Task 2); the frozen smoke values from Task 3; the existing `GroundTruthProvider`, `JevProvider`, `AsyncTypeSafeClient`, `DEFAULT_QUESTION_SET_VERSION`.
- Produces:
  - `relay.cli.ProviderName.rules = "rules"`
  - `relay.cli.PROVIDER_KEYS: dict[ProviderName, str | None]` (jev → `"TYPESAFE_API_KEY"`, groundtruth and rules → `None`)
  - `relay.cli.QUESTION_SET_PROVIDERS: frozenset[ProviderName]` (`{jev}`), `relay.cli.PROVIDER_NOTES: dict[ProviderName, str]`
  - `relay.cli._resolve_questions(provider, questions: QuestionSet | None) -> QuestionSet | None`: jev → the given set or `q-v0.2`; others → `None`; an explicit `--questions` for others → `typer.Exit(2)` via `_fail`
  - `async relay.cli._build_provider(provider_name, cases, questions, stack) -> DecisionProvider`: one branch per provider; an unknown name raises `ValueError`
  - `relay.reporting.RULES_NOTE: str`; the run report prints `**Rules fired:**` with lines like ``- `mtx_start` (physician_note:3): started 2026-01-12`` and ``(structured field)`` when `document_id` is `null`

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_cli_providers.py`:

```python
"""The CLI's explicit provider factory, per-provider key preflight, and --questions handling."""

import json
from contextlib import AsyncExitStack
from pathlib import Path

import pytest
from typer.testing import CliRunner

import relay.cli as cli_module
from relay.cases.loader import load_dataset
from relay.cli import PROVIDER_KEYS, QUESTION_SET_PROVIDERS, ProviderName, app
from relay.decisions.rules_baseline import RULES_VERSION, rules_hash
from relay.reporting import RULES_NOTE
from relay.traces.store import read_traces

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "evals" / "smoke"
runner = CliRunner()


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--env-file", str(tmp_path / "missing.env"), *args])


def dirs(tmp_path):
    return [
        "--traces-dir",
        str(tmp_path / "traces"),
        "--reports-dir",
        str(tmp_path / "reports"),
    ]


class FakeAsyncClient:
    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None


def test_every_provider_has_a_key_entry_and_only_jev_needs_one():
    assert set(PROVIDER_KEYS) == set(ProviderName)
    assert {p for p, key in PROVIDER_KEYS.items() if key} == {ProviderName.jev}
    assert PROVIDER_KEYS[ProviderName.jev] == "TYPESAFE_API_KEY"
    assert QUESTION_SET_PROVIDERS == {ProviderName.jev}


async def test_every_provider_name_has_an_explicit_factory(monkeypatch):
    monkeypatch.setattr(cli_module, "AsyncTypeSafeClient", FakeAsyncClient)
    cases = load_dataset(SMOKE)
    async with AsyncExitStack() as stack:
        for name in ProviderName:
            questions = cli_module._resolve_questions(name, None)
            provider = await cli_module._build_provider(name, cases, questions, stack)
            assert provider.name == name.value


def test_rules_eval_on_smoke_needs_no_key(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    result = invoke(
        tmp_path,
        "eval",
        "--dataset",
        str(SMOKE),
        "--provider",
        "rules",
        *dirs(tmp_path),
        "--results-dir",
        str(tmp_path / "results"),
    )
    assert result.exit_code == 0, result.output
    assert RULES_NOTE in result.output
    results = json.loads(next((tmp_path / "results").glob("*.json")).read_text())
    # Pinned in tests/unit/test_rules_datasets.py: 9 of 10 correct (AUTO-03 abstains to
    # REQUEST_INFO), AUTO-01 and AUTO-02 automated, none unsafe.
    assert (results["correct_actions"], results["auto_process_count"]) == (9, 2)
    assert results["unsafe_automation_count"] == 0
    assert results["question_set_versions"] == [RULES_VERSION]
    [trace_file] = (tmp_path / "traces").glob("*.jsonl")
    traces = read_traces(trace_file)
    assert {(t.provider, t.question_set_version, t.question_set_hash) for t in traces} == {
        ("rules", RULES_VERSION, rules_hash())
    }
    [manifest_file] = (tmp_path / "traces").glob("*.manifest.json")
    manifest = json.loads(manifest_file.read_text())
    assert (manifest["provider"], manifest["question_set_version"]) == ("rules", RULES_VERSION)
    report = next((tmp_path / "reports").glob("*.md")).read_text()
    assert RULES_NOTE in report
    assert "**Rules fired:**" in report
    assert "`mtx_never` (physician_note:" in report


@pytest.mark.parametrize("provider", ["rules", "groundtruth"])
def test_explicit_questions_is_rejected_for_providers_without_a_question_set(tmp_path, provider):
    result = invoke(
        tmp_path,
        "run",
        "--dataset",
        str(SMOKE),
        "--provider",
        provider,
        "--questions",
        "q-v0.2",
        *dirs(tmp_path),
    )
    assert result.exit_code == 2
    assert "--questions applies only to --provider jev" in result.output
    assert provider in result.output
    assert not (tmp_path / "traces").exists()


def test_jev_key_preflight_still_fails_fast_with_an_explicit_question_set(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    result = invoke(
        tmp_path,
        "run",
        "--dataset",
        str(SMOKE),
        "--provider",
        "jev",
        "--questions",
        "q-v0.1",
        *dirs(tmp_path),
    )
    assert result.exit_code == 2
    assert "TYPESAFE_API_KEY" in result.output
    assert not (tmp_path / "traces").exists()
```

In `tests/unit/test_reporting.py`, replace:

```python
from relay.reporting import (
    DISCLAIMER,
```

with:

```python
from relay.reporting import (
    DISCLAIMER,
    RULES_NOTE,
```

and append to the end of `tests/unit/test_reporting.py`:

```python
def test_run_report_lists_the_rules_that_fired():
    case = make_case("T-01")
    fired = [
        {
            "rule": "member_missing",
            "document_id": None,
            "line": None,
            "match": "insurance.member_id is None",
        },
        {
            "rule": "mtx_start",
            "document_id": "physician_note",
            "line": 3,
            "match": "started 2026-01-12",
        },
    ]
    bundle = make_bundle("T-01", provider="rules").model_copy(
        update={"derivations": {"rules": fired}}
    )
    report = render_run_report(
        run_manifest("rules"), [make_trace(case, bundle)], {"T-01": case.input}
    )
    assert RULES_NOTE in report
    assert "**Rules fired:**" in report
    assert "- `member_missing` (structured field): insurance.member_id is None" in report
    assert "- `mtx_start` (physician_note:3): started 2026-01-12" in report
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/integration/test_cli_providers.py tests/unit/test_reporting.py -q`
Expected: collection errors, `ImportError: cannot import name 'PROVIDER_KEYS' from 'relay.cli'` and `cannot import name 'RULES_NOTE' from 'relay.reporting'`.

- [ ] **Step 3: Add `RULES_NOTE` and the "Rules fired" section to `relay/reporting.py`**

Add the note constant after `GROUNDTRUTH_NOTE`. Replace:

```python
GROUNDTRUTH_NOTE = "groundtruth provider: pipeline validation, not a model result."
```

with:

```python
GROUNDTRUTH_NOTE = "groundtruth provider: pipeline validation, not a model result."
RULES_NOTE = (
    "rules provider: deterministic pattern-matching baseline; probabilities are 0, 0.5 or 1 "
    "and are not calibrated."
)
```

In `_case_section`, list the fired rules after the step-therapy block. Replace:

```python
            out.append(f"- {label} date candidates: {text or 'none resolved'}")
        out.append("")
```

with:

```python
            out.append(f"- {label} date candidates: {text or 'none resolved'}")
        out.append("")
    fired = b.derivations.get("rules")
    if fired:
        out.append("**Rules fired:**")
        for f in fired:
            where = f"{f['document_id']}:{f['line']}" if f["document_id"] else "structured field"
            out.append(f"- `{f['rule']}` ({where}): {f['match']}")
        out.append("")
```

In `render_run_report`, label rules runs. Replace:

```python
    if manifest.provider == "groundtruth":
        lines += [f"**{GROUNDTRUTH_NOTE}** Decisions come from labels, not a model.", ""]
```

with:

```python
    if manifest.provider == "groundtruth":
        lines += [f"**{GROUNDTRUTH_NOTE}** Decisions come from labels, not a model.", ""]
    if manifest.provider == "rules":
        lines += [f"**{RULES_NOTE}**", ""]
```

- [ ] **Step 4: Replace the implicit Jev branch in `relay/cli.py` with an explicit factory**

Imports. Replace:

```python
from relay.decisions.questions import DEFAULT_QUESTION_SET_VERSION, Q_V0_1, Q_V0_2
```

with:

```python
from relay.decisions.questions import DEFAULT_QUESTION_SET_VERSION, Q_V0_1, Q_V0_2
from relay.decisions.rules_baseline import RulesBaselineProvider
```

In the `relay.reporting` import block, replace:

```python
    GROUNDTRUTH_NOTE,
```

with:

```python
    GROUNDTRUTH_NOTE,
    RULES_NOTE,
```

The provider enum. Replace:

```python
class ProviderName(StrEnum):
    jev = "jev"
    groundtruth = "groundtruth"
```

with:

```python
class ProviderName(StrEnum):
    jev = "jev"
    groundtruth = "groundtruth"
    rules = "rules"
```

`--questions` defaults to `None`, plus the per-provider tables. Replace:

```python
Questions = Annotated[
    QuestionSet, typer.Option(help="Jev question set (ignored by the groundtruth provider).")
]
DEFAULT_QUESTIONS = QuestionSet(DEFAULT_QUESTION_SET_VERSION)
```

with:

```python
Questions = Annotated[
    QuestionSet | None,
    typer.Option(
        help=f"Jev question set (default {DEFAULT_QUESTION_SET_VERSION}). Only valid with "
        "--provider jev."
    ),
]
DEFAULT_QUESTIONS = QuestionSet(DEFAULT_QUESTION_SET_VERSION)

# The environment variable each provider needs, or None if it needs no key. One entry per provider.
PROVIDER_KEYS: dict[ProviderName, str | None] = {
    ProviderName.jev: "TYPESAFE_API_KEY",
    ProviderName.groundtruth: None,
    ProviderName.rules: None,
}
# Providers that accept --questions; the others reject an explicit --questions.
QUESTION_SET_PROVIDERS: frozenset[ProviderName] = frozenset({ProviderName.jev})
PROVIDER_NOTES: dict[ProviderName, str] = {
    ProviderName.groundtruth: GROUNDTRUTH_NOTE,
    ProviderName.rules: RULES_NOTE,
}
```

Question resolution, table-driven key preflight, and the factory. Replace the whole `_preflight` function:

```python
def _preflight(cases: list[PriorAuthCase], provider: ProviderName, policy: str) -> None:
    try:
        validate_run_config(cases, policy)
    except RunConfigError as error:
        raise _fail(str(error)) from error
    if provider is ProviderName.jev and not os.environ.get("TYPESAFE_API_KEY"):
        raise _fail("TYPESAFE_API_KEY is not set (add it to .env or the environment)")
```

with:

```python
def _resolve_questions(provider: ProviderName, questions: QuestionSet | None) -> QuestionSet | None:
    """The question set to run with: the default for jev, None for providers without one.

    An explicit --questions for a provider that has no question set is a usage error, not a
    silently ignored flag.
    """
    if provider not in QUESTION_SET_PROVIDERS:
        if questions is not None:
            raise _fail(
                f"--questions applies only to --provider jev; the {provider.value} provider "
                "has no question set"
            )
        return None
    return questions if questions is not None else DEFAULT_QUESTIONS


def _preflight(cases: list[PriorAuthCase], provider: ProviderName, policy: str) -> None:
    try:
        validate_run_config(cases, policy)
    except RunConfigError as error:
        raise _fail(str(error)) from error
    key = PROVIDER_KEYS[provider]
    if key is not None and not os.environ.get(key):
        raise _fail(f"{key} is not set (add it to .env or the environment)")


async def _build_provider(
    provider_name: ProviderName,
    cases: list[PriorAuthCase],
    questions: QuestionSet | None,
    stack: AsyncExitStack,
) -> DecisionProvider:
    """One explicit factory per provider. An unhandled name is a bug, never a silent Jev run."""
    if provider_name is ProviderName.jev:
        if questions is None:
            raise ValueError("the jev provider needs a question set")
        client = await stack.enter_async_context(AsyncTypeSafeClient(timeout=30.0))
        return JevProvider(client, question_set_version=questions.value)
    if provider_name is ProviderName.groundtruth:
        return GroundTruthProvider({c.input.id: c.ground_truth for c in cases})
    if provider_name is ProviderName.rules:
        return RulesBaselineProvider()
    raise ValueError(f"no factory for provider {provider_name!r}")
```

In `_execute`'s signature, replace:

```python
    dataset: Path,
    questions: QuestionSet,
) -> tuple[RunManifest, list[WorkflowTrace]]:
```

with:

```python
    dataset: Path,
    questions: QuestionSet | None,
) -> tuple[RunManifest, list[WorkflowTrace]]:
```

In `_execute`'s body, replace the implicit branch:

```python
            provider: DecisionProvider
            if provider_name is ProviderName.groundtruth:
                provider = GroundTruthProvider({c.input.id: c.ground_truth for c in cases})
            else:
                client = await stack.enter_async_context(AsyncTypeSafeClient(timeout=30.0))
                provider = JevProvider(client, question_set_version=questions.value)
```

with:

```python
            provider = await _build_provider(provider_name, cases, questions, stack)
```

In `_run_and_report`, resolve the question set before preflight and print the provider note. Replace:

```python
    dataset: Path,
    questions: QuestionSet,
) -> list[WorkflowTrace]:
    _preflight(cases, provider, policy)
    if provider is ProviderName.groundtruth:
        typer.echo(f"NOTE: {GROUNDTRUTH_NOTE}")
    manifest, traces = asyncio.run(
        _execute(cases, provider, policy, concurrency, traces_dir, dataset, questions)
    )
```

with:

```python
    dataset: Path,
    questions: QuestionSet | None,
) -> list[WorkflowTrace]:
    resolved = _resolve_questions(provider, questions)
    _preflight(cases, provider, policy)
    if provider in PROVIDER_NOTES:
        typer.echo(f"NOTE: {PROVIDER_NOTES[provider]}")
    manifest, traces = asyncio.run(
        _execute(cases, provider, policy, concurrency, traces_dir, dataset, resolved)
    )
```

In **both** `run` and `eval_command` (two occurrences), replace:

```python
    questions: Questions = DEFAULT_QUESTIONS,
```

with:

```python
    questions: Questions = None,
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/integration/test_cli_providers.py tests/unit/test_reporting.py tests/integration/test_cli.py tests/integration/test_cli_questions.py -q`
Expected: all pass. The existing `test_run_defaults_to_the_default_question_set`, `test_run_uses_the_requested_question_set`, `test_jev_without_key_fails_fast` and `test_unknown_question_set_is_rejected_by_the_cli` pass unchanged. They show that the jev default still resolves to `q-v0.2`, that an explicit set still reaches Jev, and that key preflight still fails fast.

Also check the help text by hand: `uv run relay run --help` lists `rules` among the providers and shows `--questions` with "Only valid with --provider jev."

- [ ] **Step 6: Lint, run the full suite, and commit**

```bash
uv run ruff check --fix . && uv run ruff format . && uv run pytest -q 2>&1 | tail -1
git add relay/cli.py relay/reporting.py tests/integration/test_cli_providers.py tests/unit/test_reporting.py
git commit -m "feat: explicit CLI provider factory, rules provider, and strict --questions" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git log -1 --format=%B
```

Expected: `B+63 passed`.

---

### Task 6: Network-free rules runs, Jev comparison, committed artifacts, README "Baselines"

**Files:**
- Create (committed): `evals/baselines/smoke-v0.1/<RUN_SMOKE>/…`, `evals/baselines/gen-v0.2-dev/<RUN_DEV>/…`, `evals/baselines/gen-v0.2-dev/compare-jev-vs-rules.txt`, `evals/baselines/gen-v0.2-holdout/<RUN_HOLDOUT>/…`, `evals/baselines/gen-v0.2-holdout/compare-jev-vs-rules.txt`
- Modify: `README.md`
- Create (git-ignored, never staged): `traces/`, `reports/`, `results/` outputs

**Interfaces:**
- Consumes: every command from Task 5; the datasets and committed manifests; the committed Jev traces named in Global Constraints.
- Produces: the committed rules evidence and its write-up. **Nothing in `relay/` or `tests/` changes in this task.**

Each run is deterministic and takes seconds. `<RUN_SMOKE>`, `<RUN_DEV>` and `<RUN_HOLDOUT>` are the literal run ids the CLI prints (`run_YYYYMMDDTHHMMSSZ_xxxxxx`). Write them down, because shell variables do not survive between tool calls. `R` below is shorthand for the prefix every `relay` call uses. Type it out in full each time:

```bash
env -u TYPESAFE_API_KEY uv run relay --env-file .no-such.env
```

(The file `.no-such.env` does not exist. That is intentional: no key is loaded.)

**Stop rules.** Stop and report to the controller, without committing anything, if any of these happens: a run crashes; any run shows `Invalid outputs` above 0; the smoke run differs from Task 3's pinned values (correct `9/10`, automation `2/10`, unsafe `0/2`); or the dev or holdout sweep does **not** print `Frontier is flat across all thresholds.` Do not re-run to get different numbers, and do not change code.

- [ ] **Step 1: Preconditions**

```bash
git status --short
uv run relay generate --verify evals/generated/manifests/gen-v0.2-dev.json --out evals/generated/gen-v0.2-dev
uv run relay generate --verify evals/generated/manifests/gen-v0.2-holdout.json --out evals/generated/gen-v0.2-holdout
ls evals/baselines/gen-v0.2-dev/run_20260925T071231Z_6f0b73/traces.jsonl.gz evals/baselines/gen-v0.2-holdout/run_20260925T075242Z_fd455f/traces.jsonl.gz
uv run pytest -q 2>&1 | tail -1
```

Expected: no modified tracked files; both `--verify` commands print `OK: …`; both Jev traces exist; `B+63 passed`. If a case directory is missing, regenerate it as 2B Task 8 Step 1 did, with `--manifests-dir "$(mktemp -d)"` so the committed manifest is untouched.

- [ ] **Step 2: Smoke**

```bash
mkdir -p results
env -u TYPESAFE_API_KEY uv run relay --env-file .no-such.env eval --dataset evals/smoke --provider rules 2>&1 | tee results/smoke-rules.txt
```

Record `<RUN_SMOKE>` from `Results: results/<RUN_SMOKE>.json`. The output starts with `NOTE: rules provider: …` and must match the stop rule's smoke values. Then assemble:

```bash
D=evals/baselines/smoke-v0.1/<RUN_SMOKE>
mkdir -p "$D"
gzip -9 -n -c traces/<RUN_SMOKE>.jsonl > "$D/traces.jsonl.gz"
cp traces/<RUN_SMOKE>.manifest.json "$D/run-manifest.json"
cp results/<RUN_SMOKE>.json "$D/results.json"
env -u TYPESAFE_API_KEY uv run relay --env-file .no-such.env report --dataset evals/smoke --traces "$D/traces.jsonl.gz" --out "$D/report"
```

- [ ] **Step 3: Dev run, dev sweep, and the rules' operating point**

```bash
env -u TYPESAFE_API_KEY uv run relay --env-file .no-such.env eval --dataset evals/generated/gen-v0.2-dev --provider rules 2>&1 | tee results/dev-rules.txt
env -u TYPESAFE_API_KEY uv run relay --env-file .no-such.env sweep --dataset evals/generated/gen-v0.2-dev --traces traces/<RUN_DEV>.jsonl --out results 2>&1 | tee results/dev-rules-sweep.txt
```

Record `<RUN_DEV>`. From the sweep output record `<T_RULES>`, the number in `Selected operating point: auto_process >= …`. If the output says `No threshold meets the ceiling …`, `<T_RULES>` is "none". Confirm the output contains `Frontier is flat across all thresholds.` (stop rule). Do not pick a threshold by eye.

```bash
D=evals/baselines/gen-v0.2-dev/<RUN_DEV>
mkdir -p "$D"
gzip -9 -n -c traces/<RUN_DEV>.jsonl > "$D/traces.jsonl.gz"
cp traces/<RUN_DEV>.manifest.json "$D/run-manifest.json"
cp results/<RUN_DEV>.json "$D/results.json"
cp results/<RUN_DEV>.sweep.json "$D/sweep.json"
cp results/<RUN_DEV>.frontier.csv "$D/frontier.csv"
env -u TYPESAFE_API_KEY uv run relay --env-file .no-such.env report --dataset evals/generated/gen-v0.2-dev --traces "$D/traces.jsonl.gz" --out "$D/report"
env -u TYPESAFE_API_KEY uv run relay --env-file .no-such.env compare --dataset evals/generated/gen-v0.2-dev --traces evals/baselines/gen-v0.2-dev/run_20260925T071231Z_6f0b73/traces.jsonl.gz --traces "$D/traces.jsonl.gz" --labels jev-q-v0.2,rules-v0.1 > evals/baselines/gen-v0.2-dev/compare-jev-vs-rules.txt
cat evals/baselines/gen-v0.2-dev/compare-jev-vs-rules.txt | head -25
```

The comparison's action diffs are computed at each run's own recorded thresholds (policy `v0.1`, `auto_process` 0.95).

- [ ] **Step 4: Holdout run, sweep and report at the rules' dev-selected point, comparison**

Let `AT` be `--at <T_RULES>`, or nothing if `<T_RULES>` is "none".

```bash
env -u TYPESAFE_API_KEY uv run relay --env-file .no-such.env eval --dataset evals/generated/gen-v0.2-holdout --provider rules 2>&1 | tee results/holdout-rules.txt
```

Record `<RUN_HOLDOUT>`, then:

```bash
D=evals/baselines/gen-v0.2-holdout/<RUN_HOLDOUT>
mkdir -p "$D"
gzip -9 -n -c traces/<RUN_HOLDOUT>.jsonl > "$D/traces.jsonl.gz"
cp traces/<RUN_HOLDOUT>.manifest.json "$D/run-manifest.json"
cp results/<RUN_HOLDOUT>.json "$D/results.json"
env -u TYPESAFE_API_KEY uv run relay --env-file .no-such.env sweep --dataset evals/generated/gen-v0.2-holdout --traces "$D/traces.jsonl.gz" AT --out results 2>&1 | tee results/holdout-rules-sweep.txt
cp results/<RUN_HOLDOUT>.sweep.json "$D/sweep.json"
cp results/<RUN_HOLDOUT>.frontier.csv "$D/frontier.csv"
env -u TYPESAFE_API_KEY uv run relay --env-file .no-such.env report --dataset evals/generated/gen-v0.2-holdout --traces "$D/traces.jsonl.gz" AT --out "$D/report" 2>&1 | tee results/holdout-rules-report.txt
env -u TYPESAFE_API_KEY uv run relay --env-file .no-such.env compare --dataset evals/generated/gen-v0.2-holdout --traces evals/baselines/gen-v0.2-holdout/run_20260925T075242Z_fd455f/traces.jsonl.gz --traces "$D/traces.jsonl.gz" --labels jev-q-v0.2,rules-v0.1 > evals/baselines/gen-v0.2-holdout/compare-jev-vs-rules.txt
cat evals/baselines/gen-v0.2-holdout/compare-jev-vs-rules.txt | head -25
```

Expected: the holdout sweep and report both print `Frontier is flat across all thresholds.` (stop rule), and each report bundle has six files (`summary.json`, `calibration.json`, `calibration.csv`, `frontier.csv`, `confusion.json`, `report.md`). The report's calibration section shows the rules' 0/0.5/1 probabilities as they are. That is expected (R2), not something to fix.

- [ ] **Step 5: Prove the committed traces re-score identically**

For each of `smoke-v0.1/<RUN_SMOKE>` (dataset `evals/smoke`), `gen-v0.2-dev/<RUN_DEV>` and `gen-v0.2-holdout/<RUN_HOLDOUT>` (datasets under `evals/generated/`), substitute into:

```bash
env -u TYPESAFE_API_KEY uv run relay --env-file .no-such.env eval --dataset <DATASET_DIR> --traces evals/baselines/<DATASET_ID>/<RUN>/traces.jsonl.gz --results-dir results/rescore > /dev/null
diff results/rescore/<RUN>.json evals/baselines/<DATASET_ID>/<RUN>/results.json && echo "identical <RUN>"
```

Expected: `identical …` three times.

- [ ] **Step 6: Generate the README table from the committed files**

Do not retype numbers. This script reads the committed `results.json` and `sweep.json` of the two holdout runs. It prints one row per run at its recorded thresholds, and one row at its `--at` point when there is one (Jev's `--at` is its dev-chosen 0.89, from 2B):

```bash
uv run python - "Jev \`q-v0.2\`=evals/baselines/gen-v0.2-holdout/run_20260925T075242Z_fd455f" "Rules \`rules-v0.1\`=evals/baselines/gen-v0.2-holdout/<RUN_HOLDOUT>" <<'EOF'
import json
import sys
from pathlib import Path


def pct(count, n):
    return f"{count}/{n} ({count / n:.1%})" if n else "n/a"


print("| Provider | Run | `auto_process` | Correct action | Automation | Unsafe / auto (UAR) | Request info | Human review | Frontier flat |")
print("|---|---|---|---|---|---|---|---|---|")
for arg in sys.argv[1:]:
    label, run_dir = arg.split("=", 1)
    run_dir = Path(run_dir)
    r = json.loads((run_dir / "results.json").read_text())
    s = json.loads((run_dir / "sweep.json").read_text())
    # Recomputed from the points: sweep.json files written before frontier_flat existed lack it.
    shapes = {(q["auto"], q["unsafe"], q["correct"]) for q in s["points"]}
    flat = "yes" if len(shapes) <= 1 else "no"
    n = r["n_cases"]
    print(
        f"| {label} | `{r['run_id']}` | 0.95 (recorded) | {pct(r['correct_actions'], n)} "
        f"| {pct(r['auto_process_count'], n)} "
        f"| {pct(r['unsafe_automation_count'], r['auto_process_count'])} "
        f"| {pct(r['request_info_count'], n)} | {pct(r['human_review_count'], n)} | {flat} |"
    )
    p = s["at_point"]
    if p is not None:
        print(
            f"| {label} | `{r['run_id']}` | {p['auto_threshold']} (dev-selected, `--at`) "
            f"| {pct(p['correct'], p['n'])} | {pct(p['auto'], p['n'])} "
            f"| {pct(p['unsafe'], p['auto'])} | {pct(p['request_info'], p['n'])} "
            f"| {pct(p['human_review'], p['n'])} | {flat} |"
        )
EOF
```

(The script was run against real artifacts in the throwaway copy. It prints a header and four rows, two per provider, when the rules have a dev-selected point.)

- [ ] **Step 7: Write the README "Baselines" subsection and related edits**

1. Insert the following immediately **before** `## Limitations` (so it closes the `## Evaluation` section). Replace every `⟪…⟫` slot with the text it names: pasted output, the Step 6 table verbatim, or a plain sentence stating a fact read from those outputs. Do not round, re-sort, or re-describe numbers, and keep unflattering ones.

````markdown
### Baselines

**Rules-only baseline** (`--provider rules`, `rules-v0.1`,
[`relay/decisions/rules_baseline.py`](relay/decisions/rules_baseline.py)). A deterministic,
network-free provider turns explicit cues into the same five decisions: day-precision dates, fixed
phrases such as "never tried methotrexate" or "inadequate response", and the member-ID field. The
same policy engine and thresholds as Jev then decide the action. It reads `CaseInput` only, ignores
lines about relatives, and uses the fax cover only for the member-ID check. Its patterns are the
[2C spec](docs/superpowers/specs/2026-09-25-phase2c-rules-baseline-design.md)'s §3, fixed before
any rules run. Nothing was tuned after seeing results.

Every rules probability is 0, 0.5 (abstain) or 1, so the rules are not calibrated and their
automation/safety **frontier is flat**: `auto_process` has no effect anywhere from 0.50 to 0.99.
`relay sweep` and `relay report` print `Frontier is flat across all thresholds.`, and every
rules `sweep.json` records `"frontier_flat": true`. The rules' "dev-selected" threshold
(⟪`<T_RULES>`, or "none"⟫) is therefore only the selection rule's tie-break, not a tuned operating
point, and any threshold gives the same rules row.

```bash
uv run relay eval --dataset evals/generated/gen-v0.2-holdout --provider rules    # no key, no network
uv run relay compare --dataset evals/generated/gen-v0.2-holdout --traces <jev>.jsonl.gz --traces <rules>.jsonl.gz --labels jev-q-v0.2,rules-v0.1
```

**Rules vs Jev on `gen-v0.2-holdout`** (n=1000, policy `v0.1`):

⟪paste the table printed by Task 6 Step 6⟫

⟪two to four sentences, each a fact read from the table and the two compare files: which provider
has the higher correct-action rate and automation rate, both unsafe-automation counts, and where
the rules send the cases they cannot decide (request-info vs human review). State the direction
plainly, whichever way it goes. If rules automate less but just as safely, say exactly that. Quote
the "Action differences … N cases (M new unsafe automations)" line from
[`compare-jev-vs-rules.txt`](evals/baselines/gen-v0.2-holdout/compare-jev-vs-rules.txt).⟫

The rules see only explicit conflicts and fixed phrasings. Wording outside their pattern lists
makes them abstain (usually `REQUEST_INFO`), and a contradiction they cannot see as an explicit
cue stays at 0. Both are documented weaknesses of a pattern floor, not things to tune away.
`tests/unit/test_rules_anti_shortcut.py` checks that the rules do not key on gen-v0.2's residual
contradiction tell (see Limitations).

Artifacts: smoke
[`⟪RUN_SMOKE⟫`](evals/baselines/smoke-v0.1/⟪RUN_SMOKE⟫/), dev
[`⟪RUN_DEV⟫`](evals/baselines/gen-v0.2-dev/⟪RUN_DEV⟫/) (with
[`compare-jev-vs-rules.txt`](evals/baselines/gen-v0.2-dev/compare-jev-vs-rules.txt)), holdout
[`⟪RUN_HOLDOUT⟫`](evals/baselines/gen-v0.2-holdout/⟪RUN_HOLDOUT⟫/) (full
[`report.md`](evals/baselines/gen-v0.2-holdout/⟪RUN_HOLDOUT⟫/report/report.md)).
````

2. In `## Commands`, add this line directly after the `--provider groundtruth` line:

```bash
uv run relay eval --dataset evals/smoke --provider rules                 # rules-only baseline, no key
```

In the existing `--questions q-v0.1` line, change the trailing comment `# pick a question set (jev only)` to `# pick a question set (jev only; an error with other providers)`.

3. In `## Limitations`, first bullet: change "No gold set or baselines yet (Phase 2C–2E)." to "No gold set or LLM baseline yet (Phase 2D–2E); the rules-only baseline is above." In the gen-v0.2 tell bullet, add this sentence after its last sentence (the one that ends "…rather than genuine reasoning."): "The rules baseline is tested not to key on the tell (`tests/unit/test_rules_anti_shortcut.py`)."

4. Append to `## Project docs`:

```markdown
- [Phase 2C rules baseline design](docs/superpowers/specs/2026-09-25-phase2c-rules-baseline-design.md)
- [Phase 2C implementation plan](docs/superpowers/plans/2026-09-25-phase2c-rules-baseline.md)
```

- [ ] **Step 8: Lint, run the full suite, and commit**

```bash
uv run ruff check --fix . && uv run ruff format . && uv run pytest -q 2>&1 | tail -1
git add evals/baselines/smoke-v0.1/<RUN_SMOKE> evals/baselines/gen-v0.2-dev/<RUN_DEV> evals/baselines/gen-v0.2-dev/compare-jev-vs-rules.txt evals/baselines/gen-v0.2-holdout/<RUN_HOLDOUT> evals/baselines/gen-v0.2-holdout/compare-jev-vs-rules.txt README.md
git status --short
git commit -m "feat: add rules baseline runs and README Baselines comparison" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git log -1 --format=%B
```

Expected: `B+65 passed`. The drift guard now also re-scores the two new `gen-v0.2-*` rules run directories. Before committing, `git status --short` shows `M README.md` and exactly **33** new files:
- smoke: 9 (`traces.jsonl.gz`, `run-manifest.json`, `results.json`, and the six `report/` files)
- dev: 12 (those 9, plus `sweep.json` and `frontier.csv`, plus `compare-jev-vs-rules.txt`)
- holdout: 12 (the same)

If anything under `traces/`, `reports/`, `results/` or `evals/generated/` appears, unstage it.

---

## Spec coverage

| Spec item | Where |
|---|---|
| §1 goal: deterministic, network-free provider through the same engine | Tasks 2, 5, 6 |
| R1 name, versions, hash, latency, tokens, cost | Task 2 (`RulesBaselineProvider.decide`, `rules_hash`, `test_provider_returns_a_well_formed_certain_bundle`, `test_rules_hash_is_pinned`) |
| R2 probabilities only 0 / 0.5 / 1 | Task 2 (`YES`, `NO`, `ABSTAIN`), Task 3 (`test_consistency_sweep_bundles_are_well_formed_and_three_valued`) |
| R3 reads `CaseInput` only | Task 2 (`decide(case: CaseInput)`; no ground-truth import) |
| R4 day-precision dates only, fixed calendar, `min_weeks * 7` | Task 1, Task 2 (`step_therapy_p`, `test_month_only_dates_are_not_dates_and_step_therapy_abstains`) |
| R5 relative and fax scoping | Task 2 (`Line.is_patient`, relative/fax tests), Task 3 (ADV-02 test) |
| R6 abstention routes to REQUEST_INFO; thresholds unchanged | Task 2 (`test_abstention_is_none_at_one_half`), Task 3 (AUTO-03 row), Global Constraints |
| R7 `derivations["rules"]`, 200-char cap | Task 2 (`Fired.to_dict`, `test_matched_text_is_capped`), Task 5 ("Rules fired" in the run report) |
| §3 every rule | Task 2 (table above; a positive and a negative test per rule) |
| §4 components: `rules_baseline.py`, `date_parse.py`, `--provider rules` | Tasks 1, 2, 5 |
| §5 per-rule fixtures; relative/fax/month-only | Task 2 |
| §5 smoke pinned table; ADV-02 injection and mother | Task 3 |
| §5 500-case consistency sweep | Task 3 |
| §5 `relay eval --provider rules` on smoke without a key | Task 5 (`test_rules_eval_on_smoke_needs_no_key`), Task 6 Step 2 |
| §6 runs on smoke/dev/holdout, holdout report, Jev-vs-rules compare, committed artifacts | Task 6 |
| §7 README "Baselines" table (correct action, automation, UAR, request-info, human review), honest direction | Task 6 Steps 6–7 |
| 2B ruling 1: explicit factory, per-provider key preflight, `--questions` explicit vs default | Task 5 |
| 2B ruling 2: anti-shortcut test | Task 4 |
| 2B ruling 3: flat frontier stated in README | Task 6 (stop rule and Step 7) |
