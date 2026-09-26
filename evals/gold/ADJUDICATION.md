# gold-v0.1 adjudication record

First pass: the authors' `ground_truth.json`. Second pass: `second_pass.json`, a blind reviewer
agent that saw only `case.json`, the documents and the guide's label rules, under neutral case ids.
Agreement before adjudication: `agreement.json` (never regenerated). Adjudicator: a third agent
that saw both labels, both rationales and the full guide. The rules (guide §4) were not changed.

**Summary:** 0 disagreements. No labels or documents were changed.

## Rules-gap notes from the blind reviewer (no labels changed)

Both passes agreed on every fact and action in all 100 cases (see `agreement.json`); no
adjudication was needed. Guide §4 was frozen after Task 1 and was not reopened for this task. In
its final reply (Task 7 Step 5), the blind reviewer nonetheless flagged ten cases where it judged
the rules did not unambiguously decide the label it ended up agreeing with — it reasoned to the
same value the authors used, but by a path it considered underdetermined by §4. These are recorded
here as documented ambiguities for a future `gold-v0.2`; no label or document changes were made.

| GOLD id | Fact | Reviewer's concern | Rule the committed label rests on |
|---|---|---|---|
| GOLD-TMP-16 | `missing_evidence` | MTX dates "March 3"-"August 28" carry no year, and "under care since 2022" doesn't anchor one; reviewer considered year-recovery ambiguous before settling on `TREATMENT_HISTORY`. | D3 (no anchor recovers the year, so the course establishes nothing) with R4.2 |
| GOLD-CON-20 | `step_therapy_satisfied` | The consult note is dated 2025-12-05 but reports an MTX course (2025-12-15 to 2026-05-11) starting after the note's own date; §4 doesn't address a course reported ahead of the reporting document's date. | R3(a)-(c), D1, D7 (dates taken at face value; 147-day segment) |
| GOLD-CON-05 | `step_therapy_satisfied` | Diagnosis is contested (problem list: psoriatic arthritis, RA excluded) yet `step_therapy_satisfied` is still true; reviewer noted R3 never conditions on diagnosis being established. | R3 (no diagnosis precondition), independent of R1/R2 |
| GOLD-CON-06 | `contradiction_present` | Physician note and medication history disagree on whether the course is ongoing, with neither document naming a different patient; reviewer treated them as the same patient by default. | R2, with E2's exclusion read narrowly (applies only to an explicit different-patient reference) |
| GOLD-MIS-16 | `missing_evidence` | `step_therapy_satisfied` is true while `missing_evidence` is `DIAGNOSIS`; reviewer flagged that R3 doesn't require a confirmed diagnosis even though R4 ranks `DIAGNOSIS` first. | R4.1 (diagnosis precedence) together with R3 (diagnosis-independent) |
| GOLD-CON-09 | `contradiction_present` | Physician note (established RA) and consult note (gout instead) conflict with no explicit different-patient reference; reviewer again defaulted to same-patient. | R2, with E2's exclusion read narrowly |
| GOLD-MIS-04 | `missing_evidence` | Same pattern as GOLD-MIS-16: `step_therapy_satisfied` true, diagnosis not established, `missing_evidence` is `DIAGNOSIS`. | R4.1 together with R3 (diagnosis-independent) |
| GOLD-TRK-18 | `missing_evidence` | Diagnosis is only suspected (serology incomplete) while `step_therapy_satisfied` is still true from the documented MTX course. | R4.1 together with R3 (diagnosis-independent) |
| GOLD-STR-19 | `missing_evidence` | Diagnosis is an open differential pending workup while `step_therapy_satisfied` is still true from the documented MTX course. | R4.1 together with R3 (diagnosis-independent) |
| GOLD-CON-04 | `contradiction_present` | Consult note (clinician's own account: excellent response, stopped for relocation) conflicts with a referral letter relaying a patient-reported "trial failed" claim; §4 doesn't distinguish a clinician document relaying a patient's own account from the clinician's direct observation. | R2 (both are clinician documents about the patient; the conflict is material under R2's second bullet) |
