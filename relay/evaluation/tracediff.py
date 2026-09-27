"""Compare two traces of the same case: judgments, thresholds, gate path and action.

The diff functions are pure (no I/O). replay_trace / replay_run re-run stored decisions through
today's engine. `relay replay` renders one TraceDiff; the Phase 3B regression gate builds on the
same functions over whole runs.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

from relay.cases.models import MissingEvidence, PriorAuthCase
from relay.cases.policies import AuthorizationPolicy, load_policy
from relay.decisions.base import Decision, DecisionBundle, DecisionId
from relay.evaluation.labels import expected_action
from relay.evaluation.metrics import EvalError, paired_cases
from relay.evaluation.runner import policy_text_hash
from relay.traces.models import WorkflowMode, WorkflowTrace
from relay.traces.store import current_git_sha, new_trace_id
from relay.workflow.engine import determine_action
from relay.workflow.outcomes import GateResult, WorkflowAction
from relay.workflow.thresholds import Thresholds, load_thresholds, override_auto_process

EXIT_ENGINE_DRIFT = 3
EXIT_NEWLY_UNSAFE = 4

# The engine's gates in the order determine_action runs them.
GATE_ORDER: tuple[str, ...] = (
    "provider",
    "age",
    "contradiction",
    "documentation",
    "missing_evidence",
    "auto_process",
    "default_review",
)
THRESHOLD_NAMES: tuple[str, ...] = tuple(n for n in Thresholds.model_fields if n != "version")
# Bundle fields that vary between otherwise identical runs; ignored by `identical`.
VOLATILE_BUNDLE_FIELDS = frozenset({"latency_ms", "estimated_cost_usd", "input_tokens"})

REPRODUCE_LABEL = "reproduce: stored decisions, current engine, original policy"

Change = Literal["improved", "regressed", "unchanged", "changed-both-wrong"]
Verdict = Literal["correct", "wrong-safe", "UNSAFE"]
Comparison = Callable[[Decision, float], bool | None]


def _p_yes_at_least(decision: Decision, t: float) -> bool | None:
    return None if decision.p_yes is None else decision.p_yes >= t


def _p_no_at_least(decision: Decision, t: float) -> bool | None:
    return None if decision.p_yes is None else 1.0 - decision.p_yes >= t


def _p_none_at_least(decision: Decision, t: float) -> bool | None:
    if decision.kind != "choice":
        return None
    return decision.probabilities.get(MissingEvidence.NONE.value, 0.0) >= t


def _missing_requests_info(decision: Decision, t: float) -> bool | None:
    if decision.kind != "choice" or decision.answer is None:
        return None
    return decision.answer != MissingEvidence.NONE and decision.probability >= t


@dataclass(frozen=True)
class Crossing:
    """How one decision is compared with one threshold.

    `gate` is the engine gate whose outcome that comparison decides, or None for a comparison
    the spec reports but the engine never makes (tests/unit/test_tracediff.py checks every gated
    row against determine_action).
    """

    compare: Comparison
    gate: str | None


CROSSINGS: dict[tuple[DecisionId, str], Crossing] = {
    (DecisionId.DIAGNOSIS_SUPPORT, "auto_process"): Crossing(_p_yes_at_least, "auto_process"),
    (DecisionId.STEP_THERAPY, "auto_process"): Crossing(_p_yes_at_least, "auto_process"),
    (DecisionId.DOCUMENTATION_COMPLETE, "auto_process"): Crossing(_p_yes_at_least, "auto_process"),
    (DecisionId.MATERIAL_CONTRADICTION, "auto_process"): Crossing(_p_no_at_least, None),
    (DecisionId.MISSING_EVIDENCE, "auto_process"): Crossing(_p_none_at_least, None),
    (DecisionId.MATERIAL_CONTRADICTION, "contradiction_review"): Crossing(
        _p_yes_at_least, "contradiction"
    ),
    (DecisionId.MATERIAL_CONTRADICTION, "contradiction_auto_block"): Crossing(
        _p_yes_at_least, "auto_process"
    ),
    (DecisionId.DOCUMENTATION_COMPLETE, "documentation_request_info"): Crossing(
        _p_yes_at_least, "documentation"
    ),
    (DecisionId.MISSING_EVIDENCE, "missing_evidence_request_info"): Crossing(
        _missing_requests_info, "missing_evidence"
    ),
}


class DecisionDelta(BaseModel):
    question_id: DecisionId
    kind: Literal["yes_no", "choice"] | None  # None if missing on both sides
    original: str  # rendered: "p_yes=0.931", "NONE (0.62)" or "missing"
    candidate: str
    answer_changed: bool  # yes/no side of 0.5, choice label, or presence changed
    delta: float | None  # yes_no: p_yes change; choice: change in the ORIGINAL answer's probability
    crossed: list[str]  # threshold names whose comparison flipped for this decision
    # The subset of `crossed` whose CROSSINGS row feeds a real engine gate (F4); the rest are
    # reported-only comparisons. Regression counts use this, never raw `crossed`.
    crossed_gated: list[str]


class GateDelta(BaseModel):
    gate: str
    original: str  # "passed" | "FIRED" | "not reached"
    candidate: str
    detail_original: str | None
    detail_candidate: str | None


class TraceDiff(BaseModel):
    case_id: str
    original_label: str
    candidate_label: str
    decisions: list[DecisionDelta]
    gates: list[GateDelta]  # union of both gate paths in engine order
    thresholds: dict[str, tuple[float, float]]  # only changed thresholds
    policy: tuple[str, str] | None  # ("id version", "id version") when different
    policy_text_changed: bool | None  # None when the original trace has no policy_text_hash
    policy_text_hash_original: str | None
    policy_text_hash_current: str | None
    action_original: WorkflowAction
    action_candidate: WorkflowAction
    reasons_original: list[str]
    reasons_candidate: list[str]
    # Under each side's own policy/thresholds. expected_original/expected_candidate through
    # unsafe_both below are all None for an unlabelled diff (no ground truth, e.g. 3C shadow
    # traffic).
    expected_original: WorkflowAction | None
    expected_candidate: WorkflowAction | None
    change: Change | None
    newly_unsafe: bool | None
    unsafe_resolved: bool | None
    unsafe_both: bool | None  # UNSAFE on both sides: not newly unsafe, invisible to the gate
    identical: bool  # same action, reasons, gate path and decisions (volatile fields ignored)
    # Phase 3E: each side's disabled engine gates (WorkflowTrace.ablation); None when not ablated.
    ablation_original: list[str] | None = None
    ablation_candidate: list[str] | None = None


def classify(action: WorkflowAction, expected: WorkflowAction) -> Verdict:
    if action == expected:
        return "correct"
    if action == WorkflowAction.AUTO_PROCESS:
        return "UNSAFE"
    return "wrong-safe"


def _change(
    action_o: WorkflowAction,
    expected_o: WorkflowAction,
    action_c: WorkflowAction,
    expected_c: WorkflowAction,
) -> Change:
    ok_o, ok_c = action_o == expected_o, action_c == expected_c
    if ok_c and not ok_o:
        return "improved"
    if ok_o and not ok_c:
        return "regressed"
    if not ok_o and not ok_c and action_o != action_c:
        return "changed-both-wrong"
    return "unchanged"


def render_decision(decision: Decision | None) -> str:
    if decision is None:
        return "missing"
    if decision.kind == "yes_no":
        return f"p_yes={decision.p_yes:.3f}"
    return f"{decision.answer} ({decision.probability:.2f})"


def _answer_changed(o: Decision | None, c: Decision | None) -> bool:
    if o is None or c is None:
        return (o is None) != (c is None)
    if o.kind != c.kind:
        return True
    if o.kind == "yes_no":
        assert o.p_yes is not None and c.p_yes is not None
        return (o.p_yes >= 0.5) != (c.p_yes >= 0.5)
    return o.answer != c.answer


def _delta(o: Decision | None, c: Decision | None) -> float | None:
    if o is None or c is None or o.kind != c.kind:
        return None
    if o.kind == "yes_no":
        assert o.p_yes is not None and c.p_yes is not None
        return c.p_yes - o.p_yes
    assert o.answer is not None
    return c.probabilities.get(o.answer, 0.0) - o.probabilities.get(o.answer, 0.0)


def crossed_thresholds(
    question_id: DecisionId,
    original: Decision | None,
    candidate: Decision | None,
    thresholds_original: Thresholds,
    thresholds_candidate: Thresholds,
) -> list[str]:
    """Threshold names (in Thresholds field order) whose comparison for this decision differs
    between the two sides, each side judged against its own thresholds."""
    if original is None or candidate is None:
        return []
    crossed = []
    for name in THRESHOLD_NAMES:
        crossing = CROSSINGS.get((question_id, name))
        if crossing is None:
            continue
        before = crossing.compare(original, getattr(thresholds_original, name))
        after = crossing.compare(candidate, getattr(thresholds_candidate, name))
        if before is not None and after is not None and before != after:
            crossed.append(name)
    return crossed


def gated_only(question_id: DecisionId, crossed: Sequence[str]) -> list[str]:
    """The names in `crossed` whose (question_id, name) CROSSINGS row has an engine gate."""
    return [name for name in crossed if CROSSINGS[(question_id, name)].gate is not None]


def _decision_deltas(original: WorkflowTrace, candidate: WorkflowTrace) -> list[DecisionDelta]:
    deltas = []
    for question_id in DecisionId:
        o = original.decisions.get(question_id)
        c = candidate.decisions.get(question_id)
        kind = o.kind if o is not None else (c.kind if c is not None else None)
        crossed = crossed_thresholds(question_id, o, c, original.thresholds, candidate.thresholds)
        deltas.append(
            DecisionDelta(
                question_id=question_id,
                kind=kind,
                original=render_decision(o),
                candidate=render_decision(c),
                answer_changed=_answer_changed(o, c),
                delta=_delta(o, c),
                crossed=crossed,
                crossed_gated=gated_only(question_id, crossed),
            )
        )
    return deltas


def _gate_status(path: list[GateResult], gate: str) -> tuple[str, str | None]:
    for result in path:
        if result.gate == gate:
            return ("FIRED" if result.fired else "passed"), result.detail
    return "not reached", None


def _gate_deltas(original: WorkflowTrace, candidate: WorkflowTrace) -> list[GateDelta]:
    seen = {g.gate for g in original.gate_path} | {g.gate for g in candidate.gate_path}
    extra = [
        g.gate for g in [*original.gate_path, *candidate.gate_path] if g.gate not in GATE_ORDER
    ]
    order = [g for g in GATE_ORDER if g in seen] + list(dict.fromkeys(extra))
    rows = []
    for gate in order:
        status_o, detail_o = _gate_status(original.gate_path, gate)
        status_c, detail_c = _gate_status(candidate.gate_path, gate)
        rows.append(
            GateDelta(
                gate=gate,
                original=status_o,
                candidate=status_c,
                detail_original=detail_o,
                detail_candidate=detail_c,
            )
        )
    return rows


def _comparable(bundle: DecisionBundle) -> dict:
    return bundle.model_dump(exclude=set(VOLATILE_BUNDLE_FIELDS))


def diff_traces(
    original: WorkflowTrace,
    candidate: WorkflowTrace,
    *,
    expected_original: WorkflowAction | None,
    expected_candidate: WorkflowAction | None,
    original_label: str,
    candidate_label: str,
    current_policy_text_hash: str | None,
) -> TraceDiff:
    """Everything that differs between two traces of one case.

    `current_policy_text_hash` is the hash of the current text of the ORIGINAL trace's policy id
    (relay.evaluation.runner.policy_text_hash), computed by the caller to keep this function pure.
    Both expected actions None makes an unlabelled diff: expected_*, change, newly_unsafe and
    unsafe_resolved are then None. Exactly one None is a ValueError.
    """
    if original.case_id != candidate.case_id:
        raise ValueError(
            f"cannot diff traces of different cases: {original.case_id} vs {candidate.case_id}"
        )
    if (expected_original is None) != (expected_candidate is None):
        raise ValueError("give both expected actions, or neither for an unlabelled diff")
    thresholds = {
        name: (getattr(original.thresholds, name), getattr(candidate.thresholds, name))
        for name in THRESHOLD_NAMES
        if getattr(original.thresholds, name) != getattr(candidate.thresholds, name)
    }
    policy_o = f"{original.policy_id} {original.policy_version}"
    policy_c = f"{candidate.policy_id} {candidate.policy_version}"
    text_hash = original.policy_text_hash
    change: Change | None = None
    newly_unsafe: bool | None = None
    unsafe_resolved: bool | None = None
    unsafe_both: bool | None = None
    if expected_original is not None and expected_candidate is not None:
        unsafe_o = classify(original.action, expected_original) == "UNSAFE"
        unsafe_c = classify(candidate.action, expected_candidate) == "UNSAFE"
        change = _change(original.action, expected_original, candidate.action, expected_candidate)
        newly_unsafe = unsafe_c and not unsafe_o
        unsafe_resolved = unsafe_o and not unsafe_c
        unsafe_both = unsafe_o and unsafe_c
    return TraceDiff(
        case_id=original.case_id,
        original_label=original_label,
        candidate_label=candidate_label,
        decisions=_decision_deltas(original, candidate),
        gates=_gate_deltas(original, candidate),
        thresholds=thresholds,
        policy=None if policy_o == policy_c else (policy_o, policy_c),
        policy_text_changed=None if text_hash is None else text_hash != current_policy_text_hash,
        policy_text_hash_original=text_hash,
        policy_text_hash_current=current_policy_text_hash,
        action_original=original.action,
        action_candidate=candidate.action,
        reasons_original=list(original.decision_reasons),
        reasons_candidate=list(candidate.decision_reasons),
        expected_original=expected_original,
        expected_candidate=expected_candidate,
        change=change,
        newly_unsafe=newly_unsafe,
        unsafe_resolved=unsafe_resolved,
        unsafe_both=unsafe_both,
        identical=(
            original.action == candidate.action
            and original.decision_reasons == candidate.decision_reasons
            and original.gate_path == candidate.gate_path
            and _comparable(original.decisions) == _comparable(candidate.decisions)
        ),
        ablation_original=original.ablation,
        ablation_candidate=candidate.ablation,
    )


def diff_case(
    original: WorkflowTrace,
    candidate: WorkflowTrace,
    case: PriorAuthCase,
    *,
    original_label: str,
    candidate_label: str,
    policies: Mapping[str, AuthorizationPolicy] | None = None,
    labelled: bool = True,
) -> TraceDiff:
    """diff_traces with its inputs derived here rather than by every caller.

    Each side's expected action comes from ground truth under that side's own policy and
    thresholds; the current policy-text hash is that of the original trace's policy id.
    `policies` is an optional cache by policy id; an id missing from it is loaded with
    load_policy (KeyError for an unknown id). labelled=False makes an unlabelled diff (no
    expected actions; see diff_traces).
    """

    def policy(policy_id: str) -> AuthorizationPolicy:
        if policies is not None and policy_id in policies:
            return policies[policy_id]
        return load_policy(policy_id)

    policy_o = policy(original.policy_id)
    policy_c = (
        policy_o if candidate.policy_id == original.policy_id else policy(candidate.policy_id)
    )
    return diff_traces(
        original,
        candidate,
        expected_original=(
            expected_action(case, policy_o, original.thresholds) if labelled else None
        ),
        expected_candidate=(
            expected_action(case, policy_c, candidate.thresholds) if labelled else None
        ),
        original_label=original_label,
        candidate_label=candidate_label,
        current_policy_text_hash=policy_text_hash(policy_o),
    )


def diff_runs(
    originals: Sequence[WorkflowTrace],
    candidates: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
    *,
    original_label: str,
    candidate_label: str,
    labelled: bool = True,
) -> list[TraceDiff]:
    """One diff_case per case, in the original run's trace order (labelled as diff_case).

    The two runs must cover the same case ids (EvalError naming the missing and extra ids), and
    each goes through paired_cases (one run, no duplicates, known cases with unchanged content
    hashes, the whole dataset; EvalError otherwise). Each policy id is loaded once.
    """
    original_ids = {t.case_id for t in originals}
    candidate_ids = {t.case_id for t in candidates}
    if original_ids != candidate_ids:
        missing = sorted(original_ids - candidate_ids)
        extra = sorted(candidate_ids - original_ids)
        raise EvalError(
            "the candidate run does not cover the same cases as the original run: "
            f"missing {missing}, extra {extra}"
        )
    pairs = paired_cases(originals, cases)
    candidate_by_id = {t.case_id: t for t, _ in paired_cases(candidates, cases)}
    policies: dict[str, AuthorizationPolicy] = {}
    for policy_id in sorted({t.policy_id for t in [*originals, *candidates]}):
        try:
            policies[policy_id] = load_policy(policy_id)
        except KeyError as error:
            raise EvalError(str(error.args[0])) from error
    return [
        diff_case(
            original,
            candidate_by_id[original.case_id],
            case,
            original_label=original_label,
            candidate_label=candidate_label,
            policies=policies,
            labelled=labelled,
        )
        for original, case in pairs
    ]


def replay_exit_code(diff: TraceDiff, *, reproduce: bool) -> int:
    """0, EXIT_ENGINE_DRIFT (reproduce mode only) or EXIT_NEWLY_UNSAFE; the higher code wins."""
    code = 0
    if reproduce and not diff.identical:
        code = EXIT_ENGINE_DRIFT
    if diff.newly_unsafe:
        code = max(code, EXIT_NEWLY_UNSAFE)
    return code


def ablation_suffix(trace: WorkflowTrace) -> str:
    """The label suffix " · ablate=<names>" for an ablated trace (Phase 3E), else ""."""
    return f" · ablate={'+'.join(trace.ablation)}" if trace.ablation else ""


def original_label(trace: WorkflowTrace) -> str:
    return (
        f"{trace.run_id} · {trace.provider} {trace.question_set_version} · policy "
        f"{trace.policy_id} ({trace.policy_version}) · thresholds "
        f"auto_process={trace.thresholds.auto_process:g}{ablation_suffix(trace)}"
    )


def policy_replay_label(
    policy: AuthorizationPolicy, thresholds: Thresholds, auto_process: float | None
) -> str:
    at = "" if auto_process is None else f", auto_process={auto_process:g}"
    return (
        f"policy replay: STORED DECISIONS under policy {policy.id} ({policy.version}){at}, "
        f"thresholds {thresholds.version} — judgments were made against the original policy's "
        "questions"
    )


def replay_thresholds(
    trace: WorkflowTrace, target: AuthorizationPolicy, auto_process: float | None
) -> Thresholds:
    """The thresholds a policy replay of `trace` onto `target` runs under (F1).

    Same policy version as the trace: the trace's own thresholds. A different version: the
    thresholds registered for `target.version` (an unknown version raises EvalError). An
    `auto_process` override is then applied with override_auto_process.
    """
    if target.version == trace.policy_version:
        base = trace.thresholds
    else:
        try:
            base = load_thresholds(target.version)
        except KeyError as error:
            raise EvalError(str(error.args[0])) from error
    return base if auto_process is None else override_auto_process(base, auto_process)


def candidate_trace_label(trace: WorkflowTrace) -> str:
    return (
        f"candidate trace {trace.run_id} · {trace.provider} {trace.question_set_version}"
        f"{ablation_suffix(trace)}"
    )


def live_label(trace: WorkflowTrace) -> str:
    return (
        f"live run {trace.run_id} · {trace.provider} {trace.question_set_version} on frozen inputs"
    )


def replay_trace(
    trace: WorkflowTrace,
    case: PriorAuthCase,
    *,
    policy: AuthorizationPolicy,
    thresholds: Thresholds,
    now: datetime | None = None,
    git_sha: str | None = None,
    mode: WorkflowMode = "simulated",
    run_id: str | None = None,
) -> WorkflowTrace:
    """The trace's stored decisions re-run through determine_action under `policy`/`thresholds`.

    Returns a new trace: new trace_id, run_id `run_id` (default "replay-<original run_id>"),
    replay_of the original trace_id, the given policy (and its current policy_text_hash) and
    thresholds, and `mode` (default "simulated"; relay run --workflow shadow passes "shadow").
    `git_sha` defaults to current_git_sha(); replay_run passes it once for a whole run. The
    trace's own ablation (Phase 3E) is re-applied, so an ablated trace reproduces. Raises
    ValueError if `case` is not the trace's case or its inputs changed.
    """
    if case.input.id != trace.case_id:
        raise ValueError(f"case {case.input.id} is not the trace's case {trace.case_id}")
    if case.input.content_hash() != trace.case_content_hash:
        raise ValueError(f"{trace.case_id}: case content hash changed since run {trace.run_id}")
    outcome = determine_action(
        case.input, trace.decisions, policy, thresholds, ablate=frozenset(trace.ablation or ())
    )
    return trace.model_copy(
        update={
            "trace_id": new_trace_id(),
            "run_id": run_id if run_id is not None else f"replay-{trace.run_id}",
            "timestamp": now or datetime.now(UTC),
            "policy_id": policy.id,
            "policy_version": policy.version,
            "policy_text_hash": policy_text_hash(policy),
            "thresholds": thresholds,
            "action": outcome.action,
            "decision_reasons": outcome.reasons,
            "gate_path": outcome.gate_path,
            "mode": mode,
            "relay_git_sha": git_sha if git_sha is not None else current_git_sha(),
            "replay_of": trace.trace_id,
        }
    )


def replay_run(
    traces: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
    *,
    policy_id: str | None,
    auto_process: float | None,
    mode: WorkflowMode = "simulated",
    run_id: str | None = None,
) -> list[WorkflowTrace]:
    """Run-level policy replay (for Phase 3B and relay run --from-traces), in trace order.

    Pairs traces with cases through paired_cases, so every check there applies (one run, no
    duplicates, no unknown or changed cases, full coverage; EvalError otherwise). None keeps each
    trace's own policy / auto_process. Thresholds follow replay_thresholds: a target policy of
    another version brings that version's thresholds (EvalError if none are registered). Every
    replayed trace shares run_id `run_id` (default "replay-<run_id>") and carries `mode`.
    """
    pairs = paired_cases(traces, cases)
    now = datetime.now(UTC)
    git_sha = current_git_sha()
    policies: dict[str, AuthorizationPolicy] = {}
    replayed = []
    for trace, case in pairs:
        target = policy_id or trace.policy_id
        if target not in policies:
            try:
                policies[target] = load_policy(target)
            except KeyError as error:
                raise EvalError(str(error.args[0])) from error
        replayed.append(
            replay_trace(
                trace,
                case,
                policy=policies[target],
                thresholds=replay_thresholds(trace, policies[target], auto_process),
                now=now,
                git_sha=git_sha,
                mode=mode,
                run_id=run_id,
            )
        )
    return replayed
