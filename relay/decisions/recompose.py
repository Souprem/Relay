"""Recompose a Jev bundle's step_therapy from its stored raw answers, under another policy.

No provider is called. The raw answers a Jev call returned are parsed back into the AnswerSet
decide() composed, then composed again under `policy`. The policy-shift experiment uses this to
build its stale (immunara-v0.1) and aware (immunara-v0.2) runs from one paid run.
"""

from relay.cases.models import CaseInput
from relay.cases.policies import AuthorizationPolicy
from relay.decisions.base import DecisionBundle
from relay.decisions.composition import compose_decisions
from relay.decisions.jev import PROVIDER_NAME, answer_set_from_raw


def recompose(
    bundle: DecisionBundle,
    *,
    case: CaseInput,
    policy: AuthorizationPolicy,
    question_set_version: str,
) -> DecisionBundle:
    """`bundle` with its decisions and derivations recomposed under `policy`.

    `question_set_version` must be the bundle's own: it names the composition path, and a
    mismatch is a ValueError rather than a silent reinterpretation of the answers. A bundle that
    carries a provider error is returned unchanged: there is nothing to recompose, and the engine
    still routes it to human review. Everything else (raw answers, latency, tokens, cost) is kept,
    because it describes the one Jev call whose answers are reused. Raises ValueError for a
    non-Jev bundle or another case, and MalformedAnswers if the stored answers are unusable.
    """
    if bundle.provider != PROVIDER_NAME:
        raise ValueError(f"only Jev bundles can be recomposed, not provider {bundle.provider!r}")
    if bundle.case_id != case.id:
        raise ValueError(f"bundle is for case {bundle.case_id}, not {case.id}")
    if question_set_version != bundle.question_set_version:
        raise ValueError(
            f"{case.id}: bundle was answered with {bundle.question_set_version}, "
            f"not {question_set_version}"
        )
    if bundle.error is not None:
        return bundle
    answers = answer_set_from_raw(bundle.raw_answers, question_set_version)
    decisions, derivations = compose_decisions(
        answers, case, policy, PROVIDER_NAME, question_set_version
    )
    return bundle.model_copy(update={"decisions": decisions, "derivations": derivations})
