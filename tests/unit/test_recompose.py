"""recompose: a Jev bundle's step_therapy rebuilt from its stored raw answers under a policy."""

from decimal import Decimal
from pathlib import Path

import pytest
from typesafe_sdk import SystemOneResponse

from relay.cases.loader import load_dataset
from relay.cases.policies import load_policy
from relay.decisions.base import DecisionId
from relay.decisions.composition import MalformedAnswers
from relay.decisions.jev import JevProvider
from relay.decisions.recompose import recompose
from relay.traces.store import read_traces
from tests.factories import make_bundle, make_case_input
from tests.jev_fakes import q_v0_3_payload, raw_date

REPO = Path(__file__).resolve().parents[2]
GOLD = REPO / "evals" / "gold"
GOLD_JEV = REPO / "evals" / "baselines" / "gold-v0.1" / "run_20260925T170857Z_b95be9"
GENERATED = REPO / "evals" / "generated"
GEN_V0_2_JEV_RUNS = [
    ("gen-v0.2-dev", "run_20260925T071157Z_d6b218"),  # q-v0.1
    ("gen-v0.2-dev", "run_20260925T071231Z_6f0b73"),  # q-v0.2
    ("gen-v0.2-holdout", "run_20260925T075242Z_fd455f"),  # q-v0.2
]
V1, V2 = load_policy("immunara-v0.1"), load_policy("immunara-v0.2")


class OneAnswerClient:
    def __init__(self, payload):
        self.payload = payload

    async def system_one(self, state, questions, *, model=None, **kwargs):
        return SystemOneResponse.model_validate(self.payload)


def old_course_payload():
    """Methotrexate 2025-01-13 -> 2025-06-02 (140 days), ended 470 days before the 2026-09-15
    as-of date; inadequate response 0.97; not interrupted."""
    return q_v0_3_payload(
        **raw_date("mtx_start", "January", "13", "2025"),
        **raw_date("mtx_end", "June", "2", "2025"),
    )


async def jev_bundle(payload, version="q-v0.3"):
    case = make_case_input(documents=None)
    provider = JevProvider(OneAnswerClient(payload), question_set_version=version)
    return case, await provider.decide(case)


def step(bundle):
    return bundle.get(DecisionId.STEP_THERAPY).p_yes


async def test_stale_and_aware_from_the_same_bundle():
    case, bundle = await jev_bundle(old_course_payload())
    stale = recompose(bundle, case=case, policy=V1, question_set_version="q-v0.3")
    aware = recompose(bundle, case=case, policy=V2, question_set_version="q-v0.3")
    assert step(stale) == pytest.approx(0.98 * 0.97)
    assert step(aware) == 0.0
    assert aware.derivations["step_therapy"]["max_days_since_therapy"] == 365
    assert stale.derivations["step_therapy"]["max_days_since_therapy"] is None
    for other in (DecisionId.DIAGNOSIS_SUPPORT, DecisionId.MISSING_EVIDENCE):
        assert stale.get(other) == aware.get(other) == bundle.get(other)
    # Only decisions and derivations change; the call's record is kept.
    keep = {"raw_answers", "latency_ms", "input_tokens", "estimated_cost_usd", "question_set_hash"}
    assert stale.model_dump(include=keep) == aware.model_dump(include=keep)
    assert stale.model_dump(include=keep) == bundle.model_dump(include=keep)


async def test_recompose_under_the_bundles_own_policy_is_the_identity():
    case, bundle = await jev_bundle(old_course_payload())
    assert recompose(bundle, case=case, policy=V1, question_set_version="q-v0.3") == bundle


async def test_a_mismatched_question_set_or_case_is_refused():
    case, bundle = await jev_bundle(old_course_payload())
    with pytest.raises(ValueError, match="answered with q-v0.3, not q-v0.2"):
        recompose(bundle, case=case, policy=V1, question_set_version="q-v0.2")
    with pytest.raises(ValueError, match="bundle is for case T-01, not T-02"):
        recompose(bundle, case=make_case_input("T-02"), policy=V1, question_set_version="q-v0.3")


def test_only_jev_bundles_can_be_recomposed():
    bundle = make_bundle(provider="rules")
    with pytest.raises(ValueError, match="only Jev bundles"):
        recompose(bundle, case=make_case_input(), policy=V1, question_set_version="q-v0.2")


def test_an_error_bundle_is_returned_unchanged():
    bundle = make_bundle(provider="jev", error="TypeSafeAPIError: boom").model_copy(
        update={"question_set_version": "q-v0.2", "decisions": []}
    )
    assert (
        recompose(bundle, case=make_case_input(), policy=V2, question_set_version="q-v0.2")
        is bundle
    )


def test_unusable_raw_answers_are_malformed():
    bundle = make_bundle(provider="jev", cost=Decimal("0")).model_copy(
        update={"question_set_version": "q-v0.2", "raw_answers": {}}
    )
    with pytest.raises(MalformedAnswers):
        recompose(bundle, case=make_case_input(), policy=V1, question_set_version="q-v0.2")


def assert_recomposes_to_itself(trace_file, cases):
    """Golden: every committed Jev trace, recomposed under its own policy and question set,
    equals its stored decisions and derivations (step_therapy p_yes to 1e-9)."""
    by_id = {c.input.id: c.input for c in cases}
    traces = read_traces(trace_file)
    assert traces and {t.provider for t in traces} == {"jev"}
    for trace in traces:
        stored = trace.decisions
        again = recompose(
            stored,
            case=by_id[trace.case_id],
            policy=load_policy(trace.policy_id),
            question_set_version=stored.question_set_version,
        )
        assert step(again) == pytest.approx(step(stored), abs=1e-9), trace.case_id
        assert again.decisions == stored.decisions, trace.case_id
        assert again.derivations == stored.derivations, trace.case_id


def test_golden_committed_gold_q_v0_2_jev_traces_recompose_unchanged():
    assert_recomposes_to_itself(GOLD_JEV / "traces.jsonl.gz", load_dataset(GOLD))


@pytest.mark.parametrize("dataset_id,run", GEN_V0_2_JEV_RUNS, ids=[r for _, r in GEN_V0_2_JEV_RUNS])
def test_golden_committed_gen_v0_2_jev_traces_recompose_unchanged(dataset_id, run):
    dataset = GENERATED / dataset_id
    if not dataset.is_dir():
        pytest.skip(f"{dataset} is not generated; run relay generate to create it")
    trace_file = REPO / "evals" / "baselines" / dataset_id / run / "traces.jsonl.gz"
    assert_recomposes_to_itself(trace_file, load_dataset(dataset))
