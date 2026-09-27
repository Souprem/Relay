"""relay recompose: a stored Jev run's raw answers recomposed under a policy, as a simulated run.

Offline. Each trace's decisions are rebuilt by relay.decisions.recompose.recompose (step_therapy
composed again from the stored date-part answers under `policy`), then re-decided by the engine
under that policy's thresholds (replay_thresholds: the trace's own for the same version, the
registered ones for another). The result is written in the committed-bundle format:
traces.jsonl.gz plus run-manifest.json with mode "simulated", source_run_id, and the extra keys
policy_id and thresholds.
"""

import gzip
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from relay.cases.models import PriorAuthCase
from relay.cases.policies import AuthorizationPolicy
from relay.decisions.base import DecisionId
from relay.decisions.recompose import recompose
from relay.evaluation.metrics import paired_cases
from relay.evaluation.runner import policy_text_hash
from relay.evaluation.tracediff import replay_thresholds
from relay.traces.models import RunManifest, WorkflowTrace
from relay.traces.store import current_git_sha, new_run_id, new_trace_id
from relay.workflow.engine import determine_action

TRACES_NAME = "traces.jsonl.gz"
MANIFEST_NAME = "run-manifest.json"


def recompose_run(
    traces: Sequence[WorkflowTrace],
    cases: Sequence[PriorAuthCase],
    *,
    policy: AuthorizationPolicy,
    run_id: str | None = None,
    now: datetime | None = None,
    git_sha: str | None = None,
) -> list[WorkflowTrace]:
    """Every trace recomposed under `policy`, in trace order, as one new simulated run.

    Pairs traces with cases (paired_cases: one run, full coverage, unchanged inputs; EvalError
    otherwise). Raises ValueError for a non-Jev trace, EvalError for a policy version without
    thresholds, and MalformedAnswers for unusable stored answers.
    """
    pairs = paired_cases(traces, cases)
    run_id = run_id or new_run_id()
    now = now or datetime.now(UTC)
    git_sha = git_sha if git_sha is not None else current_git_sha()
    text_hash = policy_text_hash(policy)
    out: list[WorkflowTrace] = []
    for trace, case in pairs:
        bundle = recompose(
            trace.decisions,
            case=case.input,
            policy=policy,
            question_set_version=trace.question_set_version,
        )
        thresholds = replay_thresholds(trace, policy, None)
        outcome = determine_action(case.input, bundle, policy, thresholds)
        out.append(
            trace.model_copy(
                update={
                    "trace_id": new_trace_id(),
                    "run_id": run_id,
                    "timestamp": now,
                    "policy_id": policy.id,
                    "policy_version": policy.version,
                    "policy_text_hash": text_hash,
                    "thresholds": thresholds,
                    "decisions": bundle,
                    "action": outcome.action,
                    "decision_reasons": outcome.reasons,
                    "gate_path": outcome.gate_path,
                    "mode": "simulated",
                    "relay_git_sha": git_sha,
                    "replay_of": trace.trace_id,
                }
            )
        )
    return out


def changed_counts(
    source: Sequence[WorkflowTrace], recomposed: Sequence[WorkflowTrace]
) -> tuple[int, int]:
    """(cases whose step_therapy p_yes changed, cases whose action changed), paired by case id."""
    before = {t.case_id: t for t in source}
    step_changed = action_changed = 0
    for trace in recomposed:
        old = before[trace.case_id]
        old_step = old.decisions.get(DecisionId.STEP_THERAPY)
        new_step = trace.decisions.get(DecisionId.STEP_THERAPY)
        if (old_step and old_step.p_yes) != (new_step and new_step.p_yes):
            step_changed += 1
        if old.action != trace.action:
            action_changed += 1
    return step_changed, action_changed


def write_simulated_bundle(
    out: Path,
    traces: Sequence[WorkflowTrace],
    *,
    dataset: Path,
    source: Sequence[WorkflowTrace],
    source_manifest: RunManifest | None = None,
) -> tuple[Path, Path]:
    """Write out/traces.jsonl.gz and out/run-manifest.json. Refuses a non-empty `out`
    (FileExistsError). The source run's sample_limit/sample_seed carry over when its manifest is
    given."""
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"{out} is not empty; refusing to overwrite")
    out.mkdir(parents=True, exist_ok=True)
    trace_path, manifest_path = out / TRACES_NAME, out / MANIFEST_NAME
    with gzip.open(trace_path, "wt", encoding="utf-8") as handle:
        for trace in traces:
            handle.write(trace.model_dump_json() + "\n")
    first = traces[0]
    manifest = RunManifest(
        run_id=first.run_id,
        created_at=datetime.now(UTC),
        dataset_id=first.dataset_id,
        dataset_path=str(dataset),
        provider=first.provider,
        policy_version=first.policy_version,
        question_set_version=first.question_set_version,
        case_count=len(traces),
        trace_file=str(trace_path),
        relay_git_sha=first.relay_git_sha,
        sample_limit=None if source_manifest is None else source_manifest.sample_limit,
        sample_seed=None if source_manifest is None else source_manifest.sample_seed,
        mode="simulated",
        source_run_id=source[0].run_id,
    )
    data = manifest.model_dump(mode="json") | {
        "policy_id": first.policy_id,
        "thresholds": first.thresholds.model_dump(mode="json"),
    }
    manifest_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return trace_path, manifest_path
