# Gold regression set `gold-v0.1`

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical
> use or real authorization decisions.

**Provenance.** These 100 cases were written by AI agents (Claude) following
[`AUTHORING_GUIDE.md`](AUTHORING_GUIDE.md). They were **not** written or reviewed by a human
clinical or prior-authorization expert. The labels come from the same guide, a blind second
labelling pass by a separate agent, and adjudication by a third agent. The authors, blind reviewer
and adjudicator are all Claude agents, and Claude (`claude-opus-5`) is also an evaluated provider on
this set (see the repository README's "Gold set" section). The 100% blind agreement reflects one
model family applying one guide consistently, not independent validation, and Claude's results here
may benefit from shared interpretation with its own labels. Treat results on this set as
engineering evidence about Relay's pipeline, not as clinical validation. Have a qualified human
review the cases and labels before making any external claim based on them.

## Contents

| Category | Ids | What it tests |
|---|---|---|
| Straightforward | `GOLD-STR-01..20` | 10 clear AUTO_PROCESS and 10 clear REQUEST_INFO |
| Missing information | `GOLD-MIS-01..20` | Gaps across all three missing labels and precedence, plus 4 "looks missing but present elsewhere" cases |
| Conflicting evidence | `GOLD-CON-01..20` | 14 material contradictions and 6 immaterial differences that are not contradictions |
| Temporal reasoning | `GOLD-TMP-01..20` | 11–13 week boundaries, month precision, ongoing courses, US and relative dates, yearless dates, restarts |
| Tricky / ambiguous | `GOLD-TRK-01..20` | Relatives, injected instructions, older notes, other DMARDs, ages 18 and 17, "RA" only, "consistent with" versus "suspected" |

Each case uses the standard case-folder format (`case.json`, `ground_truth.json`, `documents/`)
with `dataset_id` `gold-v0.1`. Expected actions are derived by the engine from the five labelled
facts, as for every other dataset. The per-id design (scenario, intended facts and derived action)
is the table in [`AUTHORING_GUIDE.md`](AUTHORING_GUIDE.md) §7.

Two label rules go beyond the generator's (2E spec Q3). A year-less date counts when the year is
unambiguously recoverable from the same record, and a relative date anchored to a dated document
counts, computed to the conservative month range. Both are deliberate: they probe temporal
reasoning the pipeline may not handle, and cases that go to review because of them are a
legitimate finding.

## How the labels were made

1. Authoring agents wrote each category from the guide and labelled every case with the five facts
   and a short rationale (`ground_truth.json` `notes`).
2. A blind reviewer agent received only `case.json` and the documents, under neutral ids
   (`CASE-001…`, shuffled), plus the guide's label-rules section. It wrote its own labels:
   [`second_pass.json`](second_pass.json).
3. A third agent adjudicated every disagreement: [`ADJUDICATION.md`](ADJUDICATION.md). The rules
   were not changed.

**Agreement before adjudication** ([`agreement.json`](agreement.json)):

| Fact | Agreement with the first pass |
|---|---|
| `diagnosis_supported` | 100/100 (100.0%) |
| `step_therapy_satisfied` | 100/100 (100.0%) |
| `documentation_complete` | 100/100 (100.0%) |
| `contradiction_present` | 100/100 (100.0%) |
| `missing_evidence` | 100/100 (100.0%) |
| all five facts | 100/100 (100.0%) |
| derived action | 100/100 (100.0%) |

**Adjudication:** 0 disagreements. No labels or documents were changed.

**After adjudication**, the second pass agrees with the final labels as follows:

| Fact | Agreement with the first pass |
|---|---|
| `diagnosis_supported` | 100/100 (100.0%) |
| `step_therapy_satisfied` | 100/100 (100.0%) |
| `documentation_complete` | 100/100 (100.0%) |
| `contradiction_present` | 100/100 (100.0%) |
| `missing_evidence` | 100/100 (100.0%) |
| all five facts | 100/100 (100.0%) |
| derived action | 100/100 (100.0%) |

0 fact disagreement(s) in 0 case(s)

## Rules for using this set

- **Never tune on gold.** No question, threshold, rule pattern, prompt or code change may be
  motivated by gold results. Tune on `gen-v0.2-dev` only. Each provider configuration runs on gold
  once.
- **Frozen.** `gold-v0.1` is pinned by its dataset hash `sha256:3ba49030a21f4d715e56df2b3cb3e0b03f07dbdcb097205be15e5674c8e42679` (`relay.generation.manifest.dataset_hash`) in `tests/unit/test_gold_dataset.py`. Fix
  mistakes by publishing a new dataset id, never by editing these files.

## How to run

```bash
uv run relay eval --dataset evals/gold --provider groundtruth   # pipeline check: must be 100%
uv run python -m scripts.gold_check                             # structural and label checks
uv run pytest tests/unit/test_gold_dataset.py tests/integration/test_cli_gold.py
```

## Results

Per-provider and per-category results are in the repository README's "Gold set" section. The runs
are committed under [`evals/baselines/gold-v0.1/`](../baselines/gold-v0.1/).
