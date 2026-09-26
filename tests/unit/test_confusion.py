import pytest

from relay.cases.models import MissingEvidence
from relay.evaluation.confusion import YES_NO_LABELS, confusion_matrices
from relay.evaluation.metrics import EvalError
from tests.factories import make_bundle, make_case, make_trace, make_truth

INCOMPLETE = make_truth(
    documentation_complete=False, missing_evidence=MissingEvidence.TREATMENT_HISTORY
)


def sample():
    cases = [
        make_case("A"),  # contradiction truth: no
        make_case("B", truth=make_truth(contradiction_present=True)),  # truth: yes
        make_case("C", truth=make_truth(contradiction_present=True)),  # truth: yes
        make_case("D", truth=INCOMPLETE),  # truth: no; missing TREATMENT_HISTORY
        make_case("E"),  # invalid bundle: excluded everywhere
    ]
    traces = [
        make_trace(cases[0], make_bundle("A", contra=0.1)),  # predicted no  -> TN
        make_trace(cases[1], make_bundle("B", contra=0.9)),  # predicted yes -> TP
        make_trace(cases[2], make_bundle("C", contra=0.2)),  # predicted no  -> FN
        make_trace(cases[3], make_bundle("D", contra=0.5, missing="TREATMENT_HISTORY")),  # FP
        make_trace(cases[4], make_bundle("E", error="timeout")),
    ]
    return traces, cases


def test_yes_no_matrix_from_fixtures_with_invalid_excluded():
    traces, cases = sample()
    matrices = confusion_matrices(traces, cases)
    contra = matrices["material_contradiction"]
    assert contra.labels == list(YES_NO_LABELS) == ["yes", "no"]
    # rows = truth (yes, no); columns = predicted (yes, no). p = 0.5 counts as "yes".
    assert contra.counts == [[1, 1], [1, 1]]
    assert contra.count("yes", "no") == 1  # C: missed contradiction
    assert contra.count("no", "yes") == 1  # D: p 0.5 -> yes, truth no
    assert contra.n == 4
    assert contra.invalid_excluded == 1


def test_choice_matrix_uses_all_six_labels():
    traces, cases = sample()
    missing = confusion_matrices(traces, cases)["missing_evidence"]
    assert missing.labels == [m.value for m in MissingEvidence]
    assert missing.count("NONE", "NONE") == 3  # A, B, C
    assert missing.count("TREATMENT_HISTORY", "TREATMENT_HISTORY") == 1  # D
    assert missing.n == 4
    assert sum(map(sum, missing.counts)) == 4


def test_every_decision_has_a_matrix():
    traces, cases = sample()
    matrices = confusion_matrices(traces, cases)
    assert list(matrices) == [
        "diagnosis_support",
        "step_therapy",
        "documentation_complete",
        "material_contradiction",
        "missing_evidence",
    ]
    # documentation_complete: D truth no, predicted 0.99 -> yes; A, B, C truth yes, predicted yes
    assert matrices["documentation_complete"].counts == [[3, 0], [1, 0]]


def test_hash_mismatch_is_an_error():
    case = make_case("A")
    trace = make_trace(case).model_copy(update={"case_content_hash": "sha256:stale"})
    with pytest.raises(EvalError, match="hash"):
        confusion_matrices([trace], [case])
