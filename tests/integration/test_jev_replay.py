"""2D L4 guard: moving Jev's composition into composition.py must not change Jev's output.

Replays every committed Jev q-v0.2 dev trace. Its stored raw answers go back through JevProvider
(behind a fake client), and the decisions, derivations and cost must match the committed bundle
exactly. Skips cleanly when `evals/generated/gen-v0.2-dev` is absent (git-ignored; see
`tests/integration/test_committed_baselines.py`).
"""

from pathlib import Path

import pytest
from typesafe_sdk import SystemOneResponse

from relay.cases.loader import CaseLoadError, load_dataset
from relay.decisions.jev import JevProvider
from relay.traces.store import read_traces

REPO = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO / "evals" / "generated" / "gen-v0.2-dev"
JEV_DEV_TRACES = (
    REPO
    / "evals"
    / "baselines"
    / "gen-v0.2-dev"
    / "run_20260925T071231Z_6f0b73"
    / "traces.jsonl.gz"
)


class ReplayClient:
    def __init__(self, response):
        self.response = response

    async def system_one(self, state, questions, *, model=None, **kwargs):
        return self.response


async def test_jev_recomposes_the_committed_dev_traces_identically():
    if not DATASET_DIR.exists():
        pytest.skip(f"{DATASET_DIR} is not on disk; run `relay generate` to materialize it")
    try:
        cases = {c.input.id: c for c in load_dataset(DATASET_DIR)}
    except CaseLoadError as error:
        pytest.skip(f"{DATASET_DIR}: {error}")
    traces = read_traces(JEV_DEV_TRACES)
    assert len(traces) == 400
    for trace in traces:
        stored = trace.decisions
        response = SystemOneResponse.model_validate(
            {
                "model": stored.provider_version,
                "answers": stored.raw_answers,
                "usage": {"input_tokens": stored.input_tokens},
            }
        )
        provider = JevProvider(
            ReplayClient(response), question_set_version=stored.question_set_version
        )
        fresh = await provider.decide(cases[trace.case_id].input)
        assert fresh.error == stored.error, trace.case_id
        assert fresh.decisions == stored.decisions, trace.case_id
        assert fresh.derivations == stored.derivations, trace.case_id
        assert fresh.estimated_cost_usd == stored.estimated_cost_usd, trace.case_id
