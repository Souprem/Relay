import json
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path

import pytest

from relay.cases.loader import load_case
from relay.cases.policies import load_policy
from relay.decisions.base import DecisionId
from relay.decisions.claude import (
    CLAUDE_MODEL,
    CLIENT_VERSION,
    EFFORT,
    MAX_TOKENS,
    bundle_from_message,
    error_bundle,
    estimate_cost_usd,
    request_params,
)
from relay.decisions.claude_prompt import (
    case_schema,
    claude_question_set_hash,
    render_system_prompt,
    user_message,
)
from relay.decisions.composition import UNASSIGNED
from relay.workflow.engine import bundle_problem, determine_action
from relay.workflow.outcomes import WorkflowAction
from relay.workflow.thresholds import THRESHOLDS_V0_1
from tests.claude_fakes import AUTO01_ANSWERS, answers, message

REPO = Path(__file__).resolve().parents[2]
AUTO01 = load_case(REPO / "evals" / "smoke" / "AUTO-01")
POLICY = load_policy("immunara-v0.1")


def bundle(msg, mode="sync", latency_ms=250):
    return bundle_from_message(msg, AUTO01.input, POLICY, mode=mode, latency_ms=latency_ms)


def test_request_params_follow_the_2d_contract():
    params = request_params(AUTO01.input, POLICY)
    assert params["model"] == CLAUDE_MODEL == "claude-opus-5"
    assert params["max_tokens"] == MAX_TOKENS == 4096
    assert "thinking" not in params  # Opus 5 defaults to adaptive thinking (L2)
    assert "fallbacks" not in params  # deliberately disabled (L6)
    assert params["output_config"]["effort"] == EFFORT == "low"
    assert params["output_config"]["format"] == {
        "type": "json_schema",
        "schema": case_schema(AUTO01.input, POLICY),
    }
    [system] = params["system"]
    assert system == {
        "type": "text",
        "text": render_system_prompt(POLICY),
        "cache_control": {"type": "ephemeral"},
    }
    assert params["messages"] == [{"role": "user", "content": user_message(AUTO01.input, POLICY)}]


def test_valid_reply_gives_five_well_formed_decisions():
    b = bundle(message())
    assert b.error is None
    assert bundle_problem(b) is None
    assert b.provider == "claude" and b.provider_version == "claude-opus-5"
    assert b.question_set_version == "q-v0.2+claude-prompt-v1"
    assert b.question_set_hash == claude_question_set_hash(POLICY)
    assert b.client_version == CLIENT_VERSION == f"anthropic=={version('anthropic')}"
    assert b.get(DecisionId.DIAGNOSIS_SUPPORT).p_yes == 0.97
    assert b.raw_answers == AUTO01_ANSWERS
    assert b.latency_ms == 250
    outcome = determine_action(AUTO01.input, b, POLICY, THRESHOLDS_V0_1)
    assert outcome.action is WorkflowAction.HUMAN_REVIEW  # step therapy 0.864 < 0.95


def test_the_leftover_choice_mass_contributes_no_date_candidate():
    """Hand-computed: start month 0.9 (everything else certain) -> p_duration 0.9, and step
    therapy = 0.9 x p(inadequate response) 0.96."""
    b = bundle(message())
    step = b.derivations["step_therapy"]
    assert step["p_duration"] == pytest.approx(0.9)
    assert b.get(DecisionId.STEP_THERAPY).p_yes == pytest.approx(0.9 * 0.96)
    assert step["start_candidates"] == [
        {"earliest": "2026-01-12", "latest": "2026-01-12", "probability": 0.9}
    ]


def test_missing_evidence_is_the_normalized_six_label_distribution():
    raw = {
        "DIAGNOSIS": 0.1,
        "TREATMENT_HISTORY": 0.6,
        "LAB_RESULT": 0.0,
        "DOSAGE": 0.0,
        "INSURANCE_INFORMATION": 0.0,
        "NONE": 0.25,
    }  # sums to 0.95
    b = bundle(message(answers(missing_evidence=raw)))
    missing = b.get(DecisionId.MISSING_EVIDENCE)
    assert missing.answer == "TREATMENT_HISTORY"
    assert set(missing.probabilities) == set(raw)
    assert sum(missing.probabilities.values()) == pytest.approx(1.0)
    assert missing.probabilities["TREATMENT_HISTORY"] == pytest.approx(0.6 / 0.95)
    assert missing.confidence == missing.probabilities["TREATMENT_HISTORY"]
    assert missing.probability == missing.probabilities[missing.answer]
    assert UNASSIGNED not in missing.probabilities
    assert b.derivations["missing_evidence"] == {"raw_sum": pytest.approx(0.95)}


def test_missing_evidence_ties_go_to_the_earlier_label():
    raw = dict.fromkeys(AUTO01_ANSWERS["missing_evidence"], 0.0) | {"DOSAGE": 0.5, "NONE": 0.5}
    assert (
        bundle(message(answers(missing_evidence=raw))).get(DecisionId.MISSING_EVIDENCE).answer
        == "DOSAGE"
    )


def test_execution_usage_and_stop_reason_are_recorded():
    b = bundle(message())
    assert b.derivations["execution"] == {
        "mode": "sync",
        "effort": "low",
        "max_tokens": 4096,
        "model_requested": "claude-opus-5",
    }
    assert b.derivations["usage"] == {
        "input_tokens": 1200,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 1800,
        "output_tokens": 600,
    }
    assert b.derivations["stop_reason"] == "end_turn"
    assert b.input_tokens == 3000


def test_cost_is_hand_computed_for_sync_and_batch():
    counts = {
        "input_tokens": 1000,
        "cache_creation_input_tokens": 2000,
        "cache_read_input_tokens": 3000,
        "output_tokens": 500,
    }
    # 1000 x $5/M + 2000 x $5/M x 1.25 + 3000 x $5/M x 0.1 + 500 x $25/M
    # = 0.005 + 0.0125 + 0.0015 + 0.0125 = 0.0315; the batch tier halves it.
    assert estimate_cost_usd(counts, "sync") == Decimal("0.0315")
    assert estimate_cost_usd(counts, "batch") == Decimal("0.01575")


def test_bundle_cost_uses_the_mode():
    # 1200 x 5 + 1800 x 5 x 0.1 + 600 x 25 = 6000 + 900 + 15000 = 21900 micro-dollars
    assert bundle(message()).estimated_cost_usd == Decimal("0.0219")
    batch = bundle(message(), mode="batch", latency_ms=None)
    assert batch.estimated_cost_usd == Decimal("0.01095")
    assert batch.latency_ms is None
    assert batch.derivations["execution"]["mode"] == "batch"


def test_the_first_text_block_is_parsed_even_after_a_thinking_block():
    msg = message()
    assert [block.type for block in msg.content] == ["thinking", "text"]
    assert bundle(msg).error is None


def test_refusal_is_an_error_bundle_that_keeps_its_cost_and_stop_reason():
    msg = message(
        stop_reason="refusal",
        stop_details={"type": "refusal", "category": "cyber", "explanation": "declined"},
    )
    b = bundle(msg)
    assert b.decisions == []
    assert b.error == "refusal: Claude declined to answer (category cyber)"
    assert b.derivations["stop_reason"] == "refusal"
    assert b.estimated_cost_usd == Decimal("0.0219")
    assert bundle_problem(b) is not None


def test_max_tokens_is_an_error_bundle():
    b = bundle(message(stop_reason="max_tokens"))
    assert b.decisions == []
    assert b.error.startswith("max_tokens:")
    assert b.derivations["stop_reason"] == "max_tokens"


@pytest.mark.parametrize(
    "payload, fragment",
    [
        (answers(diagnosis_support={"p_yes": 1.5}), "diagnosis_support.p_yes"),
        (answers(diagnosis_support={"p_yes": True}), "diagnosis_support.p_yes"),
        (answers(mtx_start_month={"answer": "January", "probability": -0.1}), "mtx_start_month"),
        (answers(mtx_start_year={"answer": "1999", "probability": 1.0}), "not an option"),
        (answers(mtx_end_day={"answer": "1"}), "mtx_end_day"),
        (
            {k: v for k, v in AUTO01_ANSWERS.items() if k != "documentation_complete"},
            "documentation_complete",
        ),
        (answers(extra={"p_yes": 0.5}), "unexpected keys"),
        (
            answers(missing_evidence=dict.fromkeys(AUTO01_ANSWERS["missing_evidence"], 1.0)),
            "sum to 6.000",
        ),
        (answers(missing_evidence={"NONE": 1.0}), "missing_evidence"),
        ([1, 2, 3], "not a JSON object"),
    ],
)
def test_invalid_replies_are_error_bundles(payload, fragment):
    b = bundle(message(payload))
    assert b.decisions == []
    assert b.error.startswith("malformed response: ")
    assert fragment in b.error


def test_bad_json_is_an_error_bundle_that_keeps_the_text():
    b = bundle(message(text="{not json"))
    assert b.error.startswith("malformed response: invalid JSON")
    assert b.raw_answers == {"text": "{not json"}


def test_error_bundle_for_a_request_with_no_reply_costs_nothing():
    b = error_bundle("AUTO-01", POLICY, "RateLimitError: slow down", mode="batch")
    assert (b.error, b.provider_version, b.estimated_cost_usd) == (
        "RateLimitError: slow down",
        "claude-opus-5",
        Decimal("0"),
    )
    assert b.latency_ms is None
    assert b.derivations == {
        "execution": {
            "mode": "batch",
            "effort": "low",
            "max_tokens": 4096,
            "model_requested": "claude-opus-5",
        }
    }
    assert json.loads(b.model_dump_json())["question_set_version"] == "q-v0.2+claude-prompt-v1"
