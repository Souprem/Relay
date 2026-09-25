"""C2: a logic-drift guard for the frozen rules baseline.

`rules_hash()` (the SHA-256 of the pattern table) only changes when a *pattern string* changes;
it says nothing about the surrounding matching/combination logic (line splitting, role
assignment, duration math, contradiction combination, ...). This test re-runs
`RulesBaselineProvider` on `gen-v0.2-dev` and checks its decisions and derivations against the
committed rules dev traces bit-for-bit, so an accidental logic change is caught even though the
pattern hash alone would not see it.

Skips cleanly (not a failure) when `evals/generated/gen-v0.2-dev` is absent, since that directory
is git-ignored and only exists locally after `relay generate` (2C plan precedent, see
`tests/integration/test_committed_baselines.py`).
"""

import asyncio
from pathlib import Path

import pytest

from relay.cases.loader import CaseLoadError, load_dataset
from relay.decisions.rules_baseline import RulesBaselineProvider
from relay.traces.store import read_traces

REPO = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO / "evals" / "generated" / "gen-v0.2-dev"
RULES_DEV_TRACES = (
    REPO
    / "evals"
    / "baselines"
    / "gen-v0.2-dev"
    / "run_20260925T092358Z_36888d"
    / "traces.jsonl.gz"
)

PROVIDER = RulesBaselineProvider()


def decide(case_input):
    return asyncio.run(PROVIDER.decide(case_input))


def test_rules_logic_replay_matches_the_committed_dev_traces():
    if not DATASET_DIR.exists():
        pytest.skip(f"{DATASET_DIR} is not on disk; run `relay generate` to materialize it")
    try:
        cases = load_dataset(DATASET_DIR)
    except CaseLoadError as error:
        pytest.skip(f"{DATASET_DIR}: {error}")
    by_id = {c.input.id: c.input for c in cases}
    traces = read_traces(RULES_DEV_TRACES)
    assert traces, "committed rules dev traces are empty"
    assert {t.provider for t in traces} == {"rules"}
    assert {t.case_id for t in traces} <= set(by_id), "a committed case is missing from the dataset"

    mismatched = []
    for trace in traces:
        fresh = decide(by_id[trace.case_id])
        if fresh.decisions != trace.decisions.decisions:
            mismatched.append((trace.case_id, "decisions"))
        elif fresh.derivations != trace.decisions.derivations:
            mismatched.append((trace.case_id, "derivations"))
    assert mismatched == []
