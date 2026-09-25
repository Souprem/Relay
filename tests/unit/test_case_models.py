import pytest
from pydantic import ValidationError

import relay
from relay.cases.models import CaseInput, MissingEvidence
from relay.cases.policies import load_policy
from tests.factories import make_case_input, make_truth


def test_package_version():
    assert relay.__version__ == "0.1.0"


def test_case_input_has_no_ground_truth_field():
    assert "ground_truth" not in CaseInput.model_fields


def test_content_hash_is_stable_and_content_sensitive():
    a = make_case_input()
    b = make_case_input()
    c = make_case_input(age=41)
    assert a.content_hash() == b.content_hash()
    assert a.content_hash() != c.content_hash()
    assert a.content_hash().startswith("sha256:")


def test_case_input_is_immutable():
    case = make_case_input()
    with pytest.raises(ValidationError):
        case.id = "other"


def test_ground_truth_rejects_missing_evidence_with_complete_documentation():
    with pytest.raises(ValidationError, match="documentation_complete"):
        make_truth(missing_evidence=MissingEvidence.DIAGNOSIS, documentation_complete=True)


def test_ground_truth_rejects_incomplete_documentation_without_named_gap():
    with pytest.raises(ValidationError, match="missing_evidence"):
        make_truth(documentation_complete=False, missing_evidence=MissingEvidence.NONE)


def test_ground_truth_accepts_consistent_incomplete_case():
    truth = make_truth(
        documentation_complete=False, missing_evidence=MissingEvidence.TREATMENT_HISTORY
    )
    assert truth.missing_evidence is MissingEvidence.TREATMENT_HISTORY


def test_load_policy_immunara():
    policy = load_policy("immunara-v0.1")
    assert policy.version == "v0.1"
    assert policy.min_age == 18
    assert policy.min_weeks == 12
    assert policy.required_therapy == "methotrexate"
    assert "SYNTHETIC" in policy.text


def test_load_policy_unknown_id():
    with pytest.raises(KeyError, match="unknown policy"):
        load_policy("nope-v9")
