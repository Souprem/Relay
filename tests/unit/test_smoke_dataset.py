from collections import Counter
from pathlib import Path

from relay.cases.loader import load_dataset
from relay.cases.policies import load_policy
from relay.evaluation.labels import expected_action
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1

SMOKE = Path(__file__).resolve().parents[2] / "evals" / "smoke"
AUTO, INFO, REVIEW = (
    WorkflowAction.AUTO_PROCESS,
    WorkflowAction.REQUEST_INFO,
    WorkflowAction.HUMAN_REVIEW,
)
DESIGNED = {
    "AUTO-01": AUTO,
    "AUTO-02": AUTO,
    "AUTO-03": AUTO,
    "RI-01": INFO,
    "RI-02": INFO,
    "RI-03": INFO,
    "REV-01": REVIEW,
    "REV-02": REVIEW,
    "ADV-01": REVIEW,
    "ADV-02": REVIEW,
}


def test_all_ten_smoke_cases_load():
    cases = load_dataset(SMOKE)
    assert [c.input.id for c in cases] == sorted(DESIGNED)
    assert {c.input.dataset_id for c in cases} == {"smoke-v0.1"}
    assert {c.input.as_of_date.isoformat() for c in cases} == {"2026-09-15"}


def test_derived_expected_actions_match_design():
    for case in load_dataset(SMOKE):
        policy = load_policy(case.input.policy_id)
        assert expected_action(case, policy, THRESHOLDS_V0_1) is DESIGNED[case.input.id], (
            case.input.id
        )


def test_expected_action_distribution():
    counts = Counter(
        expected_action(c, load_policy(c.input.policy_id), THRESHOLDS_V0_1)
        for c in load_dataset(SMOKE)
    )
    assert counts == {AUTO: 3, INFO: 3, REVIEW: 4}


def test_documents_are_marked_synthetic_and_mention_no_ground_truth_terms():
    for case in load_dataset(SMOKE):
        text = " ".join(d.text for d in case.input.documents).lower()
        assert "synthetic" in text, case.input.id
        assert "ground truth" not in text and "expected_action" not in text
