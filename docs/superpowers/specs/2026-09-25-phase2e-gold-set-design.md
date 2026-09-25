# Phase 2E Design: 100-Case Gold Regression Set

- **Date:** 2026-09-25
- **Status:** Approved by controller. The user delegated Phase 2 design decisions.
- **Depends on:** 2B/2C/2D, whose providers and analysis commands are run on the gold set
- **Parent:** handoff §"Gold dataset" (100 cases: 20 each of straightforward, missing information, conflicting evidence, temporal reasoning, tricky/ambiguous; "never tune on the gold set")

## 1. Goal

A version-controlled set of 100 individually authored synthetic cases in `evals/gold/`. Their wording, document structure and scenarios are **not** produced by the 2A generator, so the gold set tests generalization beyond generator templates. Labels come from a written guide and a blind second labeling pass, with disagreements adjudicated and published. Every provider (Jev, rules, Claude) is evaluated on it, and it becomes the regression anchor for Phase 3.

## 2. Settled decisions

| # | Decision |
|---|---|
| Q1 | **Honest provenance.** The cases are authored by AI agents (Claude) following a written authoring guide. They are not written by a human domain expert. The README and `evals/gold/README.md` say so plainly and recommend human review before any external claim. |
| Q2 | Directory format and ids: the existing case format, `dataset_id = "gold-v0.1"`. Ids are `GOLD-STR-01..20`, `GOLD-MIS-01..20`, `GOLD-CON-01..20`, `GOLD-TMP-01..20` and `GOLD-TRK-01..20`. |
| Q3 | Label rules are the 2A rules (§3.4 of the 2A spec: documents are the evidence; conservative month precision; a year-less date establishes nothing; missing-evidence precedence DIAGNOSIS > TREATMENT_HISTORY > INSURANCE_INFORMATION; "never took MTX" is documented history), **plus one gold-only rule:** a relative date anchored to a dated document ("started methotrexate four months before this visit", with the note dated) **does** establish the date, computed by the labeler to the conservative month range. This is intentional, because it probes temporal reasoning the current pipeline may not handle. The expected consequence (such cases may go to review) is a legitimate finding. |
| Q4 | Labels are written as the five `GroundTruth` facts, plus a `notes` rationale of at most 3 sentences naming the evidence. `expected_action` stays derived by the engine. |
| Q5 | **Blind second labeling:** an independent reviewer agent reads each case's `case.json` and documents **without** `ground_truth.json` and writes its own five facts to `evals/gold/labels/second_pass.json`. Disagreements are adjudicated by a third agent that sees both labels and the rationales. Every disagreement and its ruling is recorded in `evals/gold/ADJUDICATION.md`. The agreement rate for each fact is published. |
| Q6 | Wording diversity is required. Across the set there must be at least 4 distinct note structures: SOAP, letter-style referral, bullet problem list, and narrative. Date formats must vary (ISO, US `MM/DD/YYYY` with a note that it's US format, long form, month-only, relative). Document kinds must include at least `physician_note`, `medication_history`, `lab_report`, `fax_cover` and `insurance_card`. |
| Q7 | Category composition targets (the authoring guide fixes these per id): <br>**STR:** 10 clear AUTO_PROCESS and 10 clear REQUEST_INFO. <br>**MIS:** 20 cases with gaps across all three missing labels, including 4 "looks missing but is actually present elsewhere" cases. <br>**CON:** 14 material contradictions and 6 immaterial wording or precision differences that are **not** contradictions. <br>**TMP:** 20 cases with boundary durations of 11–13 weeks, month precision, ongoing treatment, US dates, relative dates, and restarts/interruptions. <br>**TRK:** 20 cases with relatives, injected instructions, stale notes, other DMARDs, age exactly 18 and 17, "RA" abbreviation only, and diagnosis "consistent with" vs "suspected". |
| Q8 | "Never tune on the gold set": no question, threshold or code change may be motivated by gold results within Phase 2. Gold runs happen once per provider, after all other Phase 2 work is final. |

## 3. Deliverables

- `evals/gold/AUTHORING_GUIDE.md`: the label rules (Q3), style requirements (Q6), the per-id scenario table (Q7: id → scenario one-liner → intended facts), and the synthetic-data rules (fictional plans; every document starts with `SYNTHETIC RECORD - `).
- `evals/gold/<ID>/`: 100 case directories.
- `evals/gold/labels/second_pass.json`, `evals/gold/ADJUDICATION.md` and `evals/gold/README.md` (provenance, agreement rates, and how to run).
- `tests/unit/test_gold_dataset.py`:
  - exactly 100 cases loading with `dataset_id` gold-v0.1
  - 20 per category prefix
  - every document starts with `SYNTHETIC RECORD`
  - STR's derived actions are exactly 10 AUTO_PROCESS and 10 REQUEST_INFO
  - CON has exactly 14 `contradiction_present = true`
  - no document contains the strings `ground_truth` or `expected_action`
  - the diversity checks in Q6 are asserted where mechanically checkable: the document kinds present, and at least one US-format date
- Runs, once each after 2B–2D are final: groundtruth (pipeline check, 100%), Jev with the adopted question set, rules, and Claude in batch (within the 2D budget). Then `relay report` for each and `relay compare` of all three. Artifacts are committed under `evals/baselines/gold-v0.1/`.

## 4. Process

1. Write the guide.
2. Authoring: 5 tasks, one per category, 20 cases each, each written by an agent from the guide. Label drift across categories is prevented because every author follows the same guide and the scenario table.
3. Blind second pass.
4. Adjudication, with labels updated where the ruling says so and the change recorded.
5. Tests.
6. Runs.
7. README update with gold results per provider, including per-category correct-action rate and unsafe automations.

## 5. Definition of done

- 100 cases are committed with the adjudication record, and tests pass.
- All four provider runs are committed.
- The README reports gold results per provider and per category, with the provenance caveat.
