# Phase 2C Design: Rules-Only Baseline Provider

- **Date:** 2026-09-25
- **Status:** Approved by controller. The user delegated Phase 2 design decisions.
- **Depends on:** 2A datasets, and 2B `report`/`sweep`/`compare`
- **Parent:** handoff §"Baselines and experiments": "Rules-only baseline: only uses explicit structured cues; otherwise abstains/reviews. Establishes safe but low-automation floor."

## 1. Goal

A deterministic, network-free `DecisionProvider` that turns explicit textual and structured cues into the same five decisions. The policy engine then decides actions as usual. This gives a transparent floor that shows how much Jev adds (or doesn't) over simple pattern matching, measured on the same datasets, thresholds and metrics.

## 2. Settled decisions

| # | Decision |
|---|---|
| R1 | The provider is named `rules`, with provider_version and question_set_version `rules-v0.1`. `question_set_hash` is the SHA-256 of the rules module's pattern tables, serialized as sorted JSON. `latency_ms` is measured, input_tokens is 0, and cost is `Decimal("0")`. |
| R2 | Probabilities are only 1.0 (explicit cue for yes), 0.0 (explicit cue for no) and 0.5 (abstain). The rules never pretend to be calibrated. The report's calibration section will show this plainly. |
| R3 | Rules read the structured fields (member_id, as_of_date) and the document text only. They never read ground truth. Like every provider, the only input is `CaseInput`. |
| R4 | Dates: only day-precision dates count, in ISO `YYYY-MM-DD` or long form `Month D, YYYY`. Month-only and year-less mentions make the rules abstain on duration. Duration arithmetic reuses `relay.decisions.step_therapy` conventions: a fixed calendar and ≥ `policy.min_weeks*7` days. |
| R5 | Scoping by line. Documents are split into lines, and a line mentioning a relative (`mother|father|sister|brother|aunt|uncle|grandmother|grandfather|family history`) is excluded from all patient-treatment rules. Lines of a document whose kind is `fax_cover` are ignored for clinical rules, so injected text cannot count as evidence. The fax cover is only used for the member-ID check. |
| R6 | No abstention trickery. When the rules can't decide documentation completeness they emit 0.5, which the v0.1 engine routes to REQUEST_INFO (0.5 < 0.60). That is a safe, non-automated outcome, and it's reported honestly as the rules baseline's behavior. The thresholds are not changed to favor rules. |
| R7 | `derivations["rules"]` records every rule that fired: rule name, document id, line number and matched text, capped at 200 characters per match. The run report and dashboard can then show why the rules decided. |

## 3. Rules (v0.1)

All matching is case-insensitive. `MTX_TERMS = (methotrexate|mtx)`.

**Structured and fax checks**
- `member_missing`: `insurance.member_id is None`, or a fax cover line matches `member id.*(not provided|not on file|missing)`.

**Diagnosis**
- `dx_established`: a non-relative line in a physician note matches `rheumatoid arthritis` together with (`diagnos|established|seropositive|seronegative`), and the same line does not match a negator.
- `dx_negated`: any physician-note line matches `(pending|suspected|not yet established|differential|rule out|workup)` near `rheumatoid arthritis`, or anywhere in a note that has no `dx_established` line.
- `diagnosis_support.p_yes`: 1.0 if `dx_established` and not `dx_negated`; 0.0 if `dx_negated` and not `dx_established`; otherwise 0.5.

**Treatment history** (patient lines only, fax excluded)
- `mtx_never`: `(never (tried|taken|took|received)|has not (taken|tried|received)|not taken)` within the same line as MTX_TERMS.
- `mtx_start`: a day-precision date on a line with MTX_TERMS and `(start|started|began|initiated|since|from)`. Also accepted: a medication-history line with MTX_TERMS and `start <date>`.
- `mtx_stop`: a day-precision date on a line with MTX_TERMS and `(stop|stopped|discontinued|ended|end|until|to <date>)`. Also: the medication-history `end <date>`, and the second date in a `from <date> to <date>` pattern.
- `mtx_ongoing`: MTX_TERMS together with `(continues|still taking|currently taking|remains on|ongoing|active)`. When there is no stop date, the end is `as_of_date`.
- `records_unavailable`: `(records? (were )?not available|unsure which medications|history (is )?unknown)`.
- `mtx_conflicting_starts`: two different day-precision start dates for MTX across the patient lines.

**Response**
- `mtx_response`: MTX_TERMS in the same or an adjacent line as `(inadequate response|did not improve|no improvement|not improve|persistent|intoleran|side effect|nausea|contraindicat)`.

**Step therapy**
- `step_therapy.p_yes` is 0.0 if `mtx_never`.
- Otherwise, if a start date and an end date (a stop date, or ongoing) are both known, compute `days = end - start`:
  - 0.0 if `days < min_days`
  - 1.0 if `days >= min_days` and `mtx_response`
  - 0.5 otherwise
- Otherwise, 0.5.

**Contradiction**
- `material_contradiction.p_yes` is 1.0 if (`mtx_never` and (`mtx_start` or `mtx_stop`) in some other document) or `mtx_conflicting_starts`.
- Otherwise 0.0. The rules can only see explicit conflicts. That limit is a documented weakness, not something to hide.

**Missing evidence and documentation**, with precedence DIAGNOSIS > TREATMENT_HISTORY > INSURANCE_INFORMATION:
- `DIAGNOSIS` if `diagnosis_support == 0.0`
- `TREATMENT_HISTORY` if `records_unavailable`, or (no MTX_TERMS in any patient line and not `mtx_never`)
- `INSURANCE_INFORMATION` if `member_missing`
- If one of those applies: `missing_evidence` = that label with probabilities `{label: 1.0}`, and `documentation_complete.p_yes` = 0.0.
- If none applies and `diagnosis_support == 1.0` and (step_therapy is decided or `mtx_never`): `missing_evidence` = NONE with probability 1.0, and documentation 1.0.
- Otherwise, abstain: `missing_evidence` = NONE with probabilities `{NONE: 0.5}`, and documentation 0.5.

## 4. Components

- `relay/decisions/rules_baseline.py`: `RulesBaselineProvider` (`name = "rules"`, `async decide(case) -> DecisionBundle`), plus pure helper functions for each rule. Pattern tables are module-level constants.
- `relay/decisions/date_parse.py`: `find_day_dates(text) -> list[tuple[date, span]]` for ISO and long form, rejecting invalid dates. It's shared so later work can reuse it.
- `relay/cli.py`: `--provider rules`, which needs no key.

## 5. Testing

- **Each rule** gets a positive and a negative unit fixture. Relative and fax lines are ignored, and month-only dates cause abstention.
- **Smoke dataset:**
  - For every smoke case, the rules' decisions are pinned in a table test. The authoring agent computes them from the rules and the case text once, the reviewer checks them, and after that they're frozen as regression values.
  - In particular, ADV-02's injected "PRE-APPROVED" does not raise any probability, and the mother's MTX does not count.
- **Consistency sweep:** over 500 generated cases the provider never raises an exception, always returns a well-formed bundle (`bundle_problem is None`), and never emits a probability outside {0, 0.5, 1}.
- **Integration:** `relay eval --provider rules` on smoke exits 0 without any key present.

## 6. Live runs and committed artifacts

These are network-free and deterministic:
- `relay run --provider rules` on smoke, dev and holdout
- `relay report` for holdout
- `relay compare` of Jev vs rules on dev and on holdout, using the 2B runs
- Committed under `evals/baselines/<dataset>/<run_id>/` (traces gzipped), the same as in 2B.

## 7. Definition of done

- Tests and ruff pass.
- Rules baseline results are committed.
- The README gets a "Baselines" subsection with the rules vs Jev table on holdout: correct-action rate, automation rate, UAR, request-info rate and human-review rate. Any direction is reported honestly. Rules may well be safer but automate less.
