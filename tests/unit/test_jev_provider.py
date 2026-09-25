import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from typesafe_sdk import SystemOneResponse, TypeSafeError

from relay.cases.loader import load_case
from relay.cases.policies import load_policy
from relay.decisions.base import DecisionId
from relay.decisions.jev import JEV_MODEL, JevProvider, build_state
from relay.decisions.questions import QUESTION_IDS
from relay.workflow.engine import bundle_problem, determine_action
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1

REPO = Path(__file__).resolve().parents[2]
AUTO01 = load_case(REPO / "evals" / "smoke" / "AUTO-01")
FIXTURE = REPO / "tests" / "fixtures" / "jev" / "auto01_response.json"


def fixture_payload():
    return json.loads(FIXTURE.read_text())


def response(payload=None):
    return SystemOneResponse.model_validate(payload or fixture_payload())


class FakeClient:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    async def system_one(self, state, questions, *, model=None, **kwargs):
        self.calls.append({"state": state, "questions": questions, "model": model})
        if self.error is not None:
            raise self.error
        return self.result


class FakeRateLimit(TypeSafeError):
    pass


async def decide(payload=None, error=None):
    client = FakeClient(result=None if error else response(payload), error=error)
    bundle = await JevProvider(client).decide(AUTO01.input)
    return bundle, client


async def test_request_pins_model_and_sends_twelve_questions():
    _, client = await decide()
    [call] = client.calls
    assert call["model"] == JEV_MODEL == "jev-1.13.0"
    assert tuple(call["questions"]) == QUESTION_IDS


async def test_year_options_come_from_case_documents():
    _, client = await decide()
    years = list(client.calls[0]["questions"]["mtx_start_year"].criteria)
    assert years == ["2025", "2026", "none"]


def test_state_contains_case_but_no_ground_truth():
    state = build_state(AUTO01.input, load_policy("immunara-v0.1"))
    blob = json.dumps(state)
    assert set(state) == {"policy", "request", "documents"}
    assert "physician_note" in state["documents"]
    assert state["request"]["as_of_date"] == "2026-09-15"
    for forbidden in ("ground_truth", "diagnosis_supported", "step_therapy_satisfied", "expected"):
        assert forbidden not in blob


async def test_parses_response_into_five_decisions():
    bundle, _ = await decide()
    assert bundle_problem(bundle) is None
    assert bundle.provider == "jev"
    assert bundle.provider_version == "jev-1.13.0"
    assert bundle.get(DecisionId.DIAGNOSIS_SUPPORT).p_yes == pytest.approx(0.98)
    assert bundle.get(DecisionId.MATERIAL_CONTRADICTION).p_yes == pytest.approx(0.03)
    missing = bundle.get(DecisionId.MISSING_EVIDENCE)
    assert (missing.answer, missing.confidence) == ("NONE", 0.91)
    assert bundle.input_tokens == 1800
    assert bundle.estimated_cost_usd == Decimal("0.0000756")
    assert set(bundle.raw_answers) == set(QUESTION_IDS)
    assert bundle.question_set_version == "q-v0.1"
    assert bundle.question_set_hash.startswith("sha256:")


async def test_step_therapy_is_composed_in_code():
    bundle, _ = await decide()
    step = bundle.derivations["step_therapy"]
    # start: Jan 12 (0.99; 'none' mass dropped) -> end Jun 1 = 140 days >= 84.
    assert step["p_duration"] == pytest.approx(0.99)
    assert step["p_inadequate_response"] == pytest.approx(0.97)
    assert bundle.get(DecisionId.STEP_THERAPY).p_yes == pytest.approx(0.99 * 0.97)


async def test_fixture_case_auto_processes_end_to_end():
    bundle, _ = await decide()
    outcome = determine_action(AUTO01.input, bundle, load_policy("immunara-v0.1"), THRESHOLDS_V0_1)
    assert outcome.action is WorkflowAction.AUTO_PROCESS


async def test_api_error_yields_error_bundle():
    bundle, _ = await decide(error=FakeRateLimit("rate limited"))
    assert bundle.decisions == []
    assert "FakeRateLimit" in bundle.error and "rate limited" in bundle.error
    assert bundle.provider_version == JEV_MODEL


async def test_missing_answer_yields_error_bundle():
    payload = fixture_payload()
    del payload["answers"]["material_contradiction"]
    bundle, _ = await decide(payload)
    assert bundle.decisions == []
    assert "material_contradiction" in bundle.error


async def test_unknown_missing_evidence_label_yields_error_bundle():
    payload = fixture_payload()
    payload["answers"]["missing_evidence"]["choice"] = "SOMETHING"
    bundle, _ = await decide(payload)
    assert "SOMETHING" in bundle.error


async def test_out_of_range_noul_yields_error_bundle_instead_of_crashing():
    payload = fixture_payload()
    payload["answers"]["diagnosis_support"]["noul"] = 1.5
    bundle, _ = await decide(payload)
    assert bundle.decisions == []
    assert bundle.error is not None
    assert "diagnosis_support" in bundle.error


async def test_non_finite_noul_is_either_rejected_by_the_sdk_or_yields_error_bundle():
    payload = fixture_payload()
    payload["answers"]["diagnosis_support"] = {"type": "noul", "noul": float("nan")}
    try:
        parsed = SystemOneResponse.model_validate(payload)
    except ValidationError:
        return  # the SDK itself rejects non-finite nouls; nothing further for the adapter to do.
    client = FakeClient(result=parsed)
    bundle = await JevProvider(client).decide(AUTO01.input)
    assert bundle.decisions == []
    assert bundle.error is not None
    assert "diagnosis_support" in bundle.error


async def test_out_of_range_choice_probability_yields_error_bundle():
    payload = fixture_payload()
    payload["answers"]["missing_evidence"]["probabilities"]["DIAGNOSIS"] = 5.0
    bundle, _ = await decide(payload)
    assert bundle.decisions == []
    assert bundle.error is not None
    assert "missing_evidence" in bundle.error
