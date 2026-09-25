# Relay — Project Handoff

## One-sentence goal

Build **Relay**, an evaluation-first, confidence-aware workflow engine for **synthetic prior-authorization cases**. Relay uses TypeSafe AI's Jev for narrow, typed probabilistic judgments, then uses a deterministic policy engine—not the model—to decide whether a case can be automatically processed, needs more information, or must be escalated to a human reviewer.

> The question Relay answers is: **How can probabilistic AI judgments be converted into safe autonomous workflow actions?**

## What this is and is not

Relay is an experimental systems and evaluation project, not a clinical product and not a prior-authorization form generator.

- It operates only on synthetic patients, policies, records, and outcomes.
- It does not diagnose, recommend treatment, determine medical necessity, submit real authorizations, or contact payers/pharmacies.
- It is deliberately scoped to the administrative workflow *after* a synthetic treatment has already been selected.
- Its value is reliability engineering: calibration, confidence-aware autonomy, human escalation, traceability, replay, regression testing, and safe rollout.

Put a short version of this disclaimer in the README and UI footer:

> Relay uses synthetic data only and is an engineering/evaluation prototype. It is not for clinical use or real authorization decisions.

## Why this maps to Forus

Forus works on the administrative path between a clinician choosing a medication and a patient actually receiving it: prior authorizations, appeals, benefits verification, pharmacy routing, affordability processes, and related follow-up. The difficult technical part is not generating prose; it is safely operating over fragmented, incomplete, conflicting, and changing information.

Relay is tailored to the engineering shape of that problem without pretending to recreate their product:

| Forus-shaped problem | Relay demonstration |
|---|---|
| Messy evidence across notes, structured records, and policies | Synthetic documents deliberately contain omissions, temporal ambiguity, and contradictions. |
| AI must make narrow factual judgments | Jev answers typed yes/no and choice questions, each with a probability. |
| A model should not own a consequential action | Deterministic policy code owns `AUTO_PROCESS`, `REQUEST_INFO`, and `HUMAN_REVIEW`. |
| Confidence must control autonomy | Higher certainty permits more automation; ambiguity escalates. |
| Accuracy alone misses safety failures | Relay foregrounds unsafe automation rate, calibration, abstention, and the automation/safety frontier. |
| Agent changes need safe deployment | Stored traces, replay, regression evaluation, baselines, and shadow mode make changes inspectable. |
| Policies and environments drift | A versioned synthetic policy can change over time to test robustness. |

The interview-quality story is therefore not “I made an AI healthcare chatbot.” It is: **I built a small but rigorous system for testing when an AI workflow has earned the right to act autonomously.**

## Jev’s role

Jev is the probabilistic **decision layer**. It receives unstructured case state and returns typed answers with probabilities. Use it for constrained questions, not for a single open-ended “what should we do?” prompt.

The architecture should preserve this contract:

```text
Jev:   What does the available evidence most likely establish?
Relay: What is software permitted to do given those judgments and their confidence?
```

Design the provider boundary so Jev can be compared fairly with a conventional structured-output LLM and a rules-only baseline:

```python
class DecisionProvider(Protocol):
    async def decide(self, case: PriorAuthCase, questions: list[Question]) -> DecisionBundle: ...

class JevProvider(DecisionProvider): ...
class OpenAIProvider(DecisionProvider): ...
class RulesBaselineProvider(DecisionProvider): ...
class GroundTruthProvider(DecisionProvider): ...  # tests only
```

Send independent Jev questions together where the API supports it. One systems experiment is to measure latency and quality with 1, 5, 10, and 20 concurrent/narrow decisions rather than serial model calls.

## Synthetic prior-authorization domain

Start with one fictional specialty-medication authorization workflow. Fictional medications and payers avoid accidental claims about real coverage rules while keeping the task intelligible.

Example controlled universe:

- Medications: `Immunara`, `Dermavax`, `Arthriquel`, `Neurofenix`, `Cardiovex`
- Conditions: a small set of fictionalized rheumatology, dermatology, or neurology indications
- Payers/plans: `ExampleHealth Gold`, `Northstar Choice`, `CivicCare Plus`
- Policies: age threshold, diagnosis requirement, prior-treatment duration, inadequate-response or contraindication requirement, documentation requirements

An individual case should combine structured fields with noisy documents, for example:

```text
patient: age 42, state MA
requested medication: Immunara
indication: rheumatoid arthritis

physician_note.txt:
  Began MTX early February; stopped around July because joint pain and
  morning stiffness did not improve. Discussed Immunara today.

med_history.txt:
  METHOTREXATE — inactive — start 2026-02-04 — end unknown

policy_v4.txt:
  Requires a supported diagnosis, age >= 18, >=12 weeks of methotrexate,
  and documented inadequate response or contraindication.
```

The point is that the answer must be inferred from evidence—not handed to the model as pristine JSON.

## Architecture

```text
Synthetic Case Generator / Gold Dataset
                |
                v
       Evidence and State Assembly
                |
                v
     Jev Decision Provider (typed probabilities)
                |
                v
  Deterministic Policy + Threshold Engine
                |
       +--------+---------+
       |        |         |
       v        v         v
 AUTO_PROCESS REQUEST_INFO HUMAN_REVIEW
                |
                v
   Immutable Trace Store (case, evidence, decisions, policy, result)
                |
                v
 Evaluation / Calibration / Replay / Regression / Shadow Comparison
                |
                v
       API, CLI, and small inspection dashboard
```

Key invariants:

1. The provider never returns a workflow action; it returns judgments.
2. The policy engine is deterministic and versioned.
3. Every run persists enough information to reproduce or compare it later.
4. Ground truth is withheld from model input and used only for evaluation.
5. Side effects are simulated; shadow mode always records a proposed action instead of performing one.

## Core data model

Use Pydantic models in the backend. This is conceptual, not a command to mirror TypeScript exactly.

```python
class PriorAuthCase(BaseModel):
    id: str
    patient: Patient
    medication: MedicationRequest
    insurance: Insurance
    clinical: ClinicalState
    documents: list[Document]
    policy: AuthorizationPolicy
    ground_truth: GroundTruth  # never pass this to a provider

class GroundTruth(BaseModel):
    diagnosis_supported: bool
    step_therapy_satisfied: bool
    documentation_complete: bool
    contradiction_present: bool
    missing_evidence: MissingEvidence
    expected_action: WorkflowAction

class Decision(BaseModel):
    question_id: str
    answer: str | bool
    probability: float  # probability of the selected answer
    evidence_refs: list[str] = []
    provider: str

class DecisionBundle(BaseModel):
    case_id: str
    decisions: list[Decision]
    provider_version: str
    latency_ms: int
    estimated_cost_usd: Decimal | None

class WorkflowTrace(BaseModel):
    trace_id: str
    case_id: str
    timestamp: datetime
    dataset_id: str
    provider: str
    provider_version: str
    policy_version: str
    decisions: DecisionBundle
    action: WorkflowAction
    decision_reasons: list[str]
    autonomy_thresholds: dict[str, float]
    mode: Literal['evaluate', 'shadow', 'simulated']
```

Use stable IDs and version identifiers for cases, policies, datasets, prompt/question definitions, and providers. A trace that cannot identify its inputs is not replayable.

## The five initial Jev decisions

Build exactly these five before adding anything else.

| ID | Type | Question | Expected answers |
|---|---|---|---|
| `diagnosis_support` | yes/no | Does the available clinical evidence support the diagnosis required by this policy? | `YES`, `NO` |
| `step_therapy` | yes/no | Has the patient satisfied the policy’s prior-treatment requirement? | `YES`, `NO` |
| `documentation_complete` | yes/no | Is there sufficient documentation to submit this authorization? | `YES`, `NO` |
| `material_contradiction` | yes/no | Does the record contain a material contradiction that affects authorization? | `YES`, `NO` |
| `missing_evidence` | choice | What is the most important missing information, if any? | `DIAGNOSIS`, `TREATMENT_HISTORY`, `LAB_RESULT`, `DOSAGE`, `INSURANCE_INFORMATION`, `NONE` |

For contradiction cases, examples should be explicitly material. For example, a medication-history record says methotrexate ended in July while a note says the patient has never tried it. Minor wording differences should not be labeled contradictions.

Future decisions—only after v0.1—is working—could include whether a prior authorization is required, safe-to-automate scoring, or evidence citation selection. Do not expand the decision catalog prematurely.

## Deterministic policy engine and confidence thresholds

Treat probability as a signal, not a permission slip. The initial policy should be intentionally conservative:

```python
def determine_action(d: Decisions, t: Thresholds) -> PolicyOutcome:
    if d.material_contradiction.p_yes >= t.contradiction_review:
        return review('material contradiction is likely')

    if d.documentation_complete.p_yes < t.documentation_request_info:
        return request_info('documentation is likely incomplete')

    if d.missing_evidence.answer != 'NONE' and \
       d.missing_evidence.probability >= t.missing_evidence_request_info:
        return request_info(f'missing {d.missing_evidence.answer.lower()}')

    required = [
        d.diagnosis_support.p_yes,
        d.step_therapy.p_yes,
        d.documentation_complete.p_yes,
    ]
    if min(required) >= t.auto_process and \
       d.material_contradiction.p_yes < t.contradiction_auto_block:
        return auto_process('all required evidence is high confidence')

    return review('case does not meet the autonomous-action bar')
```

Suggested v0.1 starting thresholds, to be tuned using held-out data rather than treated as truth:

| Parameter | Initial value | Purpose |
|---|---:|---|
| `auto_process` | 0.95 | Every affirmative requirement must clear this bar before automatic processing. |
| `contradiction_review` | 0.80 | Likely contradiction immediately forces human review. |
| `contradiction_auto_block` | 0.20 | Any nontrivial contradiction signal blocks autonomous processing. |
| `documentation_request_info` | 0.60 | Clear insufficiency produces a simulated request for information. |
| `missing_evidence_request_info` | 0.70 | A confident missing-evidence classification produces a request. |

Autonomy bands are a useful dashboard explanation, but policy rules should be more precise than generic bands:

| Confidence | Default interpretation |
|---|---|
| >= 95% | May be eligible for autonomous action if all other safety gates pass. |
| 80–95% | May support low-risk workflow preparation; do not auto-process authorization. |
| 60–80% | Human review by default. |
| < 60% | Review or request information; never treat as decisive. |

## Dataset strategy

### Generated dataset

Write a deterministic, seedable generator that produces cases with explicit ground truth. Its controls should include:

```python
generate_case(
    seed: int,
    difficulty: Literal['easy', 'medium', 'hard', 'adversarial'],
    contradiction_probability: float,
    missing_data_probability: float,
    note_noise: float,
    policy_version: str,
)
```

Generate four difficulty classes:

- **Easy:** explicit, consistent evidence; should validate basic pipeline correctness.
- **Medium:** evidence is implicit or distributed across two documents; requires temporal inference.
- **Hard:** records disagree or dates are uncertain; often appropriate for review.
- **Adversarial:** distracting relatives, stale notes, irrelevant medications, partial forms, or near-miss durations; tests whether the system attributes facts to the right subject and policy.

### Gold dataset

Create a manually authored, version-controlled gold set of 100 cases in `evals/gold/`:

| Category | Cases | Purpose |
|---|---:|---|
| Straightforward | 20 | Clear allow/process and clear request-info paths |
| Missing information | 20 | Correct classification of absent key facts |
| Conflicting evidence | 20 | Safety behavior and escalation |
| Temporal reasoning | 20 | Start/end dates and treatment duration |
| Tricky/ambiguous | 20 | Abstention, calibration, and policy boundary behavior |

Keep a larger generated evaluation set separate from the gold set. Never tune on the gold set without a documented reason; it is your regression suite and credibility anchor.

## Evaluation plan

An `eval` run should write both a terminal summary and machine-readable results. Suggested commands:

```bash
relay generate --count 1000 --seed 42 --out evals/generated/v0.1
relay eval --dataset evals/gold --provider jev --policy v0.1
relay eval --dataset evals/generated/v0.1 --provider openai --policy v0.1
relay regression --baseline traces/jev-v0.1.jsonl --candidate jev-v0.2
relay replay CASE-0391 --trace TRACE-... --provider jev-v0.2
relay run --dataset evals/gold --mode shadow
```

Report, at minimum:

### Decision-level metrics

- Per-question accuracy, precision/recall where useful, and confusion matrices
- Invalid/missing structured outputs
- Evidence-reference coverage, if citations are implemented
- Latency: p50, p95, p99
- Cost per case and per 1,000 cases when provider pricing is available

### Workflow-level metrics

- **Correct action rate:** proposed action matches `expected_action`
- **Automation rate:** `AUTO_PROCESS / all cases`
- **Human escalation rate:** `HUMAN_REVIEW / all cases`
- **Unnecessary escalation rate:** review when the gold action allowed automatic processing
- **Request-info precision:** request-info actions that correctly identify an incomplete case
- **Unsafe automation rate (UAR):**

```text
count(AUTO_PROCESS where gold action is REQUEST_INFO or HUMAN_REVIEW)
---------------------------------------------------------------------
                         count(AUTO_PROCESS)
```

UAR is the primary safety metric. A system with a high automation rate is worse, not better, if it gets there by automatically processing cases that should have been reviewed.

### Automation frontier

Sweep the `auto_process` threshold across a range (for example, 0.50–0.99) and plot:

- x-axis: automation rate
- y-axis: unsafe automation rate
- optionally label human-review rate

The project’s central experimental question is: **what is the maximum automation rate that remains below a stated unsafe-automation ceiling?** For a demo, use a candidate ceiling such as 1%; report the observed trade-off, do not fabricate favorable results.

## Calibration

Because Jev returns probabilities, assess whether confidence deserves to be trusted.

For each yes/no decision, bucket predictions (50–60%, 60–70%, …, 90–100%), then compare average predicted confidence with empirical accuracy in the bucket. Calculate:

- Brier score
- Expected Calibration Error (ECE)
- Reliability diagram / calibration curve

Calibration must be evaluated on held-out cases. A model can have higher raw accuracy but be less useful for autonomous action if its 95% predictions are only correct 80% of the time.

Keep the calibration module provider-agnostic so the Jev and LLM comparison uses identical definitions and bins.

## Baselines and experiments

Build baselines before claiming that Relay improves anything.

| System | Purpose |
|---|---|
| Rules-only baseline | Only uses explicit structured cues; otherwise abstains/reviews. Establishes safe but low-automation floor. |
| Jev + policy engine | Primary system. Narrow probabilistic decisions feed the deterministic policy. |
| Conventional LLM + same policy engine | Fair structured-output comparison using the same questions, dataset, thresholds, and metrics. |
| Ground-truth provider | Test fixture for validating policy-engine behavior independently of model quality. |

Required initial experiments:

1. **Provider comparison:** Jev vs LLM vs rules on the same gold and generated evaluation sets.
2. **Threshold sweep:** automation frontier and unsafe automation rate at each threshold.
3. **Calibration analysis:** reliability, Brier score, and ECE per key decision.
4. **Parallelism experiment:** measure 1/5/10/20 narrow decisions for p50/p95 latency and cost.
5. **Distribution-shift experiment:** introduce `policy_v5` with an added prior-treatment requirement; compare policy-aware behavior with stale/naive logic.
6. **Ablation:** remove contradiction detection or missing-evidence routing and quantify the safety/automation effect.

Do not invent benchmark results. A carefully explained negative result—e.g., a baseline is safer at the cost of automation, or an LLM is more accurate but poorly calibrated—is valuable.

## Traceability, replay, regression, and shadow mode

### Traces

Persist every case run as an append-only trace. Include the sanitized case snapshot or content hash, document IDs/versions, provider and prompt/question version, raw typed decisions, policy version/thresholds, proposed action, reasons, latency, estimated cost, timestamp, and mode.

Example:

```json
{
  "trace_id": "tr_01H...",
  "case_id": "CASE-0391",
  "provider": "jev",
  "provider_version": "jev-v1",
  "policy_version": "v0.1",
  "decisions": [{"name": "step_therapy", "answer": true, "probability": 0.94}],
  "action": "AUTO_PROCESS",
  "decision_reasons": ["all required judgments exceeded 0.95"],
  "thresholds": {"auto_process": 0.95},
  "latency_ms": 142,
  "mode": "evaluate"
}
```

### Replay

`relay replay CASE-0391` should show the original trace beside a candidate run and explicitly call out changed judgments, confidence deltas, policy deltas, and workflow-action changes. It should be possible to replay with either the original frozen inputs or the latest policy, clearly labeled.

### Regression evaluation

`relay regression` compares candidate and baseline traces over a fixed dataset and surfaces:

- improved / unchanged / regressed actions
- changes in UAR, automation rate, and calibration
- newly unsafe auto-actions (highest-priority failures)
- case IDs and diff links/data for investigation

Any candidate that increases unsafe automation without a deliberate, reviewed policy decision should fail the regression gate.

### Shadow mode

In shadow mode, Relay calculates a proposed action and saves the trace but never effects a simulated status transition. The dashboard should label it plainly:

```text
SHADOW: Would auto-process CASE-3817; no action was taken.
```

For the project, shadow mode can compare a candidate provider/policy with a chosen baseline or gold action. Its purpose is to show safe progressive rollout, not to pretend the system has real production traffic.

## Dashboard pages

Build the backend and evaluation harness first. The dashboard is an inspection layer, not the project’s core.

| Route | Must show |
|---|---|
| `/cases` | Paginated case list, dataset/difficulty, proposed action, mode, provider, confidence summary, and filters for review/unsafe/regression cases. |
| `/cases/[id]` | Synthetic patient/case state, documents with evidence references, five decisions and probabilities, policy evaluation path, final action and reasons, ground truth (clearly marked evaluation-only), and related traces. |
| `/evals` | Latest run summary, decision metrics, UAR, automation/escalation rates, latency/cost, calibration curve, and automation frontier. |
| `/compare` | Provider/policy comparison table, regression deltas, threshold sweep, and links to the cases driving changes. |

Nice-to-have only after v0.1: a trace replay diff page, policy-threshold sandbox, and downloadable evaluation report.

## Suggested stack

Keep the stack boring and optimized for correct iteration.

| Layer | Choice | Why |
|---|---|---|
| Backend | Python, FastAPI, Pydantic | Natural fit for evaluation, typing, and provider adapters. |
| Database | SQLite first; Postgres later | SQLite is enough for local traces and datasets. Migrate only when a real need appears. |
| Evaluation | Pandas, NumPy, scikit-learn | Metrics, reliability curves, Brier/ECE calculations. |
| Tests | pytest | Policy, generator, trace, regression, and API tests. |
| Frontend | Next.js, TypeScript, React, Tailwind | Fast, familiar inspection UI. |
| Charts | Recharts | Calibration and threshold trade-off visualizations. |
| Packaging | `uv` or Poetry plus a task runner | Reproducible Python environment and explicit commands. |

Keep provider API keys in environment variables; do not commit secrets or include them in traces.

## Proposed repository structure

```text
relay/
├── apps/
│   ├── api/                       # FastAPI entrypoint/routes
│   └── web/                       # Next.js dashboard
├── relay/
│   ├── cases/
│   │   ├── models.py
│   │   ├── generator.py
│   │   ├── fixtures.py
│   │   └── policies.py
│   ├── decisions/
│   │   ├── base.py
│   │   ├── questions.py
│   │   ├── jev.py
│   │   ├── openai.py
│   │   └── rules_baseline.py
│   ├── workflow/
│   │   ├── engine.py
│   │   ├── thresholds.py
│   │   └── outcomes.py
│   ├── traces/
│   │   ├── models.py
│   │   ├── store.py
│   │   └── replay.py
│   ├── evaluation/
│   │   ├── runner.py
│   │   ├── metrics.py
│   │   ├── calibration.py
│   │   ├── frontier.py
│   │   └── regression.py
│   └── cli.py
├── evals/
│   ├── gold/                      # 100 manual cases + expected labels
│   └── generated/                 # seed/dataset-versioned outputs
├── scripts/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── regression/
├── docs/
│   └── evaluation-methodology.md
├── README.md
├── pyproject.toml
└── docker-compose.yml              # optional; do not need this for v0.1
```

## Build phases

### Phase 0 — Foundation

- Initialize monorepo, Python environment, linting, formatting, test runner, and README.
- Define Pydantic case, policy, decision, outcome, and trace schemas.
- Add a ground-truth provider and unit tests for the deterministic policy engine.

### Phase 1 — v0.1 decision pipeline

- Implement one fictional policy and the five initial decisions.
- Hand-author 10 smoke-test cases and build a seeded generator.
- Implement `JevProvider` behind the provider interface.
- Create policy engine outcomes: `AUTO_PROCESS`, `REQUEST_INFO`, `HUMAN_REVIEW`.
- Persist a JSONL or SQLite trace for every run.

### Phase 2 — evaluation credibility

- Build the 100-case gold set and a 1,000+ case generated holdout set.
- Implement decision/workflow metrics, calibration, threshold sweep, and report artifacts.
- Add the rules-only baseline; add the structured-output LLM baseline when the Jev flow is stable.

### Phase 3 — engineering depth

- Add replay, candidate-vs-baseline regression, and shadow mode.
- Add policy versioning/distribution-shift experiment.
- Make unsafe-regression failures visible in CLI and CI.

### Phase 4 — presentation

- Add the four dashboard pages.
- Write a rigorous README: problem, synthetic-data guarantee, architecture, evaluation protocol, actual results, limitations, and demo instructions.
- Record a short demo after results are real and reproducible.

## v0.1 scope: explicitly small

v0.1 is complete when it can do all of the following locally:

1. Load or generate a synthetic case with messy text documents and hidden ground truth.
2. Ask Jev the five defined questions and record typed answers/probabilities.
3. Deterministically produce one of three workflow outcomes with human-readable reasons.
4. Store a replayable trace including provider and policy version.
5. Evaluate at least 10 hand-authored smoke cases end to end.
6. Run unit tests proving the policy engine behaves correctly for known decision bundles.
7. Print a small metric summary including correct-action rate, automation rate, UAR, p50/p95 latency, and any unavailable metric marked honestly as unavailable.

Do **not** put the dashboard, real PDFs/OCR, 20 decisions, Postgres, deployment, fine-tuning, real medical data, or a multi-agent planner into v0.1.

## Demo flow

Use one easy case and one ambiguous case. Keep it under five minutes.

1. Open `/cases`; select a synthetic case marked `easy`.
2. Show the policy and the messy documents that establish diagnosis, treatment duration, and inadequate response.
3. Show the five Jev decisions and their probabilities.
4. Show the deterministic policy explanation: all requirements cleared the high-confidence bar; no material contradiction; proposed result is `AUTO_PROCESS`.
5. Switch to a hard/contradictory case. Show why high raw confidence on one fact does not override the contradiction gate; result is `HUMAN_REVIEW`.
6. Open `/evals`; show actual UAR, automation rate, calibration, and the threshold frontier.
7. Open `/compare` or replay to show a baseline/candidate difference and how an unsafe regression becomes visible before rollout.

The point of the demo is not to claim clinical usefulness. It is to demonstrate that the system can explain **why it acted, why it declined to act, and how you know whether a change made it safer or less safe.**

## Resume-bullet targets

Do not use these until the measurements are actually true. Replace bracketed fields with verified results.

- Built **Relay**, a confidence-aware workflow engine that combines TypeSafe AI’s Jev with deterministic policy gates to route synthetic prior-authorization cases to automatic processing, information requests, or human review.
- Designed a reproducible synthetic prior-authorization benchmark with [N] gold cases and [N] generated cases covering missing data, contradiction detection, temporal reasoning, and adversarial document noise.
- Implemented trace replay, shadow mode, and regression evaluation; surfaced unsafe automation rate, calibration (Brier/ECE), latency, cost, and automation/safety trade-offs across Jev, structured-output LLM, and rules-only baselines.
- Calibrated autonomy thresholds to achieve [X]% automation at [Y]% unsafe automation on a held-out synthetic dataset.

## Guardrails and quality bar

- Synthetic data only; never ingest, store, or demo real patient information.
- Fictional policy and medication names by default; clearly label any domain-inspired example as synthetic.
- Do not market Relay as medical, clinical, payer, or legal decision support.
- Never auto-process solely because one model score is high; policy gates must include all required evidence and contradiction checks.
- Keep policy, data, questions/prompts, provider, and trace versions explicit.
- Separate training/tuning, development, gold regression, and final holdout data where possible.
- Record failed and ambiguous cases; do not remove them to improve a headline metric.
- Treat UAR regressions as release blockers until inspected and explicitly accepted.
- Keep a rules-only baseline so added AI capability has a measurable cost/benefit comparison.
- Report confidence and calibration honestly. A score is not calibrated merely because it is between 0 and 1.
- Keep all actions simulated; shadow mode must never make a side effect.
- Build backend/evaluation quality before visual polish.

## Immediate first milestone

**Milestone: “Ten cases, five judgments, one safe action.”**

Deliver this before building a UI or comparison baseline:

1. Set up the Python project and typed core schemas.
2. Write one `policy_v0.1` for `Immunara` with age, diagnosis, 12-week prior treatment, and inadequate-response requirements.
3. Hand-author 10 synthetic cases: 3 clear auto-process, 3 clear request-info, 2 clear review, and 2 adversarial/contradictory cases.
4. Implement the five-question Jev adapter and a fake deterministic provider for tests.
5. Implement the policy engine with the initial conservative thresholds.
6. Save an immutable trace for every run.
7. Add tests for every policy branch and run the ten cases end to end from a CLI command.
8. Write a short output report containing the proposed action, reasons, decision probabilities, and UAR across those ten cases.

Definition of done: a stranger can clone the repository, set the provider key, run one command, inspect ten synthetic traces, and understand exactly why each case was auto-processed, asked for information, or escalated.

## Suggested first commands after scaffolding

```bash
uv run pytest
uv run relay run --dataset evals/smoke --provider jev --policy v0.1
uv run relay eval --dataset evals/smoke --provider jev --policy v0.1
```

Only add the web app after these commands are stable, traceable, and reproducible.
