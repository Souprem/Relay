"""Calls the real Claude API: one smoke case, sync mode. Costs a few cents.

Run with: uv run pytest -m live tests/integration/test_live_claude.py -s
"""

import os
from pathlib import Path

import pytest
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

from relay.cases.loader import load_case
from relay.decisions.claude import ClaudeProvider
from relay.workflow.engine import bundle_problem

pytestmark = pytest.mark.live
REPO = Path(__file__).resolve().parents[2]


async def test_claude_answers_one_smoke_case():
    load_dotenv(REPO / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")
    case = load_case(REPO / "evals" / "smoke" / "AUTO-01")
    async with AsyncAnthropic(timeout=300.0) as client:
        bundle = await ClaudeProvider(client.messages).decide(case.input)
    print(
        f"\nlive Claude cost: ${bundle.estimated_cost_usd} (usage {bundle.derivations.get('usage')})"
    )
    assert bundle.error is None, bundle.error
    assert bundle_problem(bundle) is None
    assert len(bundle.decisions) == 5
    assert bundle.provider_version.startswith("claude-opus-5")
    assert bundle.derivations["usage"]["output_tokens"] > 0
    assert bundle.estimated_cost_usd > 0
