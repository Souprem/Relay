"""Calls the real TypeSafe API. Run with: uv run pytest -m live"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from typesafe_sdk import AsyncTypeSafeClient

from relay.cases.loader import load_case
from relay.decisions.jev import JevProvider

pytestmark = pytest.mark.live
REPO = Path(__file__).resolve().parents[2]


async def test_jev_answers_one_smoke_case():
    load_dotenv(REPO / ".env")
    if not os.environ.get("TYPESAFE_API_KEY"):
        pytest.skip("TYPESAFE_API_KEY not set")
    case = load_case(REPO / "evals" / "smoke" / "AUTO-01")
    async with AsyncTypeSafeClient(timeout=30.0) as client:
        bundle = await JevProvider(client).decide(case.input)
    assert bundle.error is None, bundle.error
    assert len(bundle.decisions) == 5
    assert bundle.provider_version.startswith("jev-1.13")
    assert bundle.input_tokens and bundle.input_tokens > 0
    assert "step_therapy" in bundle.derivations
