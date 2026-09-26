"""latest_policy_for: the newest registered policy for the same medication."""

import pytest

import relay.cases.policies as policies_module
from relay.cases.policies import latest_policy_for


def spec(version: str, medication: str) -> dict[str, object]:
    return {
        "version": version,
        "medication": medication,
        "indication": "rheumatoid arthritis",
        "min_age": 18,
        "required_therapy": "methotrexate",
        "min_weeks": 12,
        "text_file": "unused.md",
    }


@pytest.fixture
def registry(monkeypatch):
    fake = {
        "immunara-v0.1": spec("v0.1", "Immunara"),
        "immunara-v0.9": spec("v0.9", "Immunara"),
        "immunara-v0.10": spec("v0.10", "Immunara"),
        "otheria-v2.0": spec("v2.0", "Otheria"),
    }
    monkeypatch.setattr(policies_module, "_POLICIES", fake)
    return fake


def test_the_real_registry_resolves_immunara_to_itself():
    assert latest_policy_for("immunara-v0.1") == "immunara-v0.1"


def test_versions_compare_numerically_not_as_text(registry):
    assert latest_policy_for("immunara-v0.1") == "immunara-v0.10"
    assert latest_policy_for("immunara-v0.9") == "immunara-v0.10"
    assert latest_policy_for("immunara-v0.10") == "immunara-v0.10"


def test_other_medications_are_never_candidates(registry):
    assert latest_policy_for("otheria-v2.0") == "otheria-v2.0"


def test_an_unknown_policy_is_a_key_error_naming_the_known_ones(registry):
    with pytest.raises(KeyError, match="unknown policy 'nope'"):
        latest_policy_for("nope")
