"""Immutable run records. A trace that cannot identify its inputs is not replayable."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from relay.decisions.base import DecisionBundle
from relay.workflow.outcomes import GateResult, WorkflowAction
from relay.workflow.thresholds import Thresholds

# How a run's actions are used: "evaluate" (scored only; relay eval and plain relay run),
# "simulated" (the incumbent: its actions become simulated case-status transitions) or "shadow"
# (a candidate's proposals: recorded, never applied).
WorkflowMode = Literal["evaluate", "simulated", "shadow"]


class WorkflowTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    trace_id: str
    run_id: str
    timestamp: datetime
    case_id: str
    case_content_hash: str
    dataset_id: str
    provider: str
    provider_version: str
    question_set_version: str
    question_set_hash: str
    policy_id: str
    policy_version: str
    policy_text_hash: str | None = None
    thresholds: Thresholds
    decisions: DecisionBundle
    action: WorkflowAction
    decision_reasons: list[str]
    gate_path: list[GateResult]
    mode: WorkflowMode = "evaluate"
    relay_git_sha: str | None
    # The trace_id this trace was replayed from (relay replay); None for ordinary runs and for
    # every trace written before Phase 3A.
    replay_of: str | None = None


class RunManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    created_at: datetime
    dataset_id: str
    dataset_path: str
    provider: str
    policy_version: str
    question_set_version: str | None = None
    case_count: int
    trace_file: str
    relay_git_sha: str | None
    # Set when the run used --limit/--sample-seed (a deterministic subsample of the dataset).
    sample_limit: int | None = None
    sample_seed: int | None = None
    # Phase 3C. Manifests written before 3C have neither key and load as an "evaluate" run.
    mode: WorkflowMode = "evaluate"
    # The run whose stored decisions this run re-issued (relay run --from-traces, and the
    # regression gate's re-decided runs); None for a run that called a provider.
    source_run_id: str | None = None
