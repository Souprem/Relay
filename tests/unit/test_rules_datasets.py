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
