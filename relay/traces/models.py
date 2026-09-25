"""Immutable run records. A trace that cannot identify its inputs is not replayable."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from relay.decisions.base import DecisionBundle
from relay.workflow.outcomes import GateResult, WorkflowAction
from relay.workflow.thresholds import Thresholds


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
    thresholds: Thresholds
    decisions: DecisionBundle
    action: WorkflowAction
    decision_reasons: list[str]
    gate_path: list[GateResult]
    mode: Literal["evaluate", "shadow", "simulated"] = "evaluate"
    relay_git_sha: str | None


class RunManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    created_at: datetime
    dataset_id: str
    dataset_path: str
    provider: str
    policy_version: str
    case_count: int
    trace_file: str
    relay_git_sha: str | None
