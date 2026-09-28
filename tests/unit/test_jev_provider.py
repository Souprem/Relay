import json
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path

import pytest
from pydantic import ValidationError
from typesafe_sdk import SystemOneResponse, TypeSafeError

from relay.cases.loader import load_case
from relay.cases.policies import load_policy
from relay.decisions.base import DecisionId
from relay.decisions.composition import MalformedAnswers
from relay.decisions.jev import (
    CLIENT_VERSION,
    JEV_MODEL,
    JevProvider,
    answer_set_from_raw,
    build_state,
)
from relay.decisions.questions import (
    DEFAULT_QUESTION_SET_VERSION,
    QUESTION_IDS,
    QUESTION_IDS_V0_3,
    question_set_hash,
)
from relay.workflow.engine import bundle_problem, determine_action
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1
from tests.jev_fakes import q_v0_3_payload, raw_date, raw_noul

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
    assert bundle.question_set_version == DEFAULT_QUESTION_SET_VERSION
    assert bundle.question_set_hash == question_set_hash(
        load_policy("immunara-v0.1"), DEFAULT_QUESTION_SET_VERSION
    )


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


async def test_bundles_record_the_sdk_client_version():
    assert CLIENT_VERSION == f"typesafe-sdk=={version('typesafe-sdk')}"
    ok, _ = await decide()
    failed, _ = await decide(error=FakeRateLimit("rate limited"))
    assert ok.client_version == CLIENT_VERSION
    assert failed.client_version == CLIENT_VERSION


@pytest.mark.parametrize("version", ["q-v0.1", "q-v0.2"])
async def test_provider_sends_and_records_the_requested_question_set(version):
    client = FakeClient(result=response())
    bundle = await JevProvider(client, question_set_version=version).decide(AUTO01.input)
    policy = load_policy("immunara-v0.1")
    assert bundle.question_set_version == version
    assert bundle.question_set_hash == question_set_hash(policy, version)
    sent = client.calls[0]["questions"]["missing_evidence"].criteria["TREATMENT_HISTORY"]
    assert ("never took methotrexate" in sent) is (version == "q-v0.2")


def test_unknown_question_set_is_rejected_at_construction():
    with pytest.raises(ValueError, match="q-v9"):
        JevProvider(FakeClient(), question_set_version="q-v9")


# ---- Phase 3D: q-v0.3 over the wire, and rebuilding answers from a trace ----


async def decide_v3(payload):
    client = FakeClient(result=response(payload))
    bundle = await JevProvider(client, question_set_version="q-v0.3").decide(AUTO01.input)
    return bundle, client


async def test_q_v0_3_sends_nineteen_questions_and_records_the_version():
    bundle, client = await decide_v3(q_v0_3_payload())
    [call] = client.calls
    assert tuple(call["questions"]) == QUESTION_IDS_V0_3
    assert bundle.question_set_version == "q-v0.3"
    assert bundle.question_set_hash == question_set_hash(load_policy("immunara-v0.1"), "q-v0.3")
    assert set(bundle.raw_answers) == set(QUESTION_IDS_V0_3)
    assert bundle_problem(bundle) is None


async def test_q_v0_3_composes_the_interruption():
    # AUTO-01 fixture: 2026-01-12 -> 2026-06-01. Held 2026-02-23 (42 d), restarted 2026-03-23
    # (70 d to the end): certainly interrupted, so no segment reaches 12 weeks.
    payload = q_v0_3_payload(
        mtx_interrupted=raw_noul(1.0),
        **raw_date("mtx_pause", "February", "23", "2026"),
        **raw_date("mtx_restart", "March", "23", "2026"),
    )
    bundle, _ = await decide_v3(payload)
    assert bundle.get(DecisionId.STEP_THERAPY).p_yes == 0.0
    step = bundle.derivations["step_therapy"]
    # The fixture's start month is January at 0.99 (0.01 "none"), so the continuous reading
    # would be 0.99; the certain interruption replaces it with the two short segments.
    assert step["p_continuous"] == pytest.approx(0.99)
    assert (step["p_either_segment"], step["p_interrupted"]) == (0.0, 1.0)


async def test_a_q_v0_3_response_missing_an_interruption_answer_is_malformed():
    payload = q_v0_3_payload()
    del payload["answers"]["mtx_restart_day"]
    bundle, _ = await decide_v3(payload)
    assert bundle.error is not None and "mtx_restart_day" in bundle.error
    assert bundle.decisions == []


def test_answer_set_from_raw_rebuilds_what_decide_composed():
    raw = fixture_payload()["answers"]
    answers = answer_set_from_raw(raw, "q-v0.2")
    assert answers.yes_no["mtx_inadequate_response"] == 0.97
    start = answers.choices["mtx_start_month"]
    assert (start.answer, start.probabilities, start.confidence) == (
        "January",
        {"January": 0.99, "none": 0.01},
        0.98,
    )


def test_answer_set_from_raw_refuses_missing_or_garbled_answers():
    raw = fixture_payload()["answers"]
    with pytest.raises(MalformedAnswers, match="mtx_pause_month"):
        answer_set_from_raw(raw, "q-v0.3")
    garbled = raw | {"diagnosis_support": {"type": "noul", "noul": "high"}}
    with pytest.raises(MalformedAnswers):
        answer_set_from_raw(garbled, "q-v0.2")
