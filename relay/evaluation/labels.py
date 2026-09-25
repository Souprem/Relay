"""Expected actions are derived from ground-truth facts through the same versioned engine."""

from relay.cases.models import PriorAuthCase
from relay.cases.policies import AuthorizationPolicy
from relay.decisions.ground_truth import bundle_from_truth
from relay.workflow.engine import determine_action
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import Thresholds


def expected_action(
    case: PriorAuthCase, policy: AuthorizationPolicy, thresholds: Thresholds
) -> WorkflowAction:
    bundle = bundle_from_truth(case.input.id, case.ground_truth)
    return determine_action(case.input, bundle, policy, thresholds).action
