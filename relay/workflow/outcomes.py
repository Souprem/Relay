"""Workflow actions and the explanation of how the policy engine reached one."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class WorkflowAction(StrEnum):
    AUTO_PROCESS = "AUTO_PROCESS"
    REQUEST_INFO = "REQUEST_INFO"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class GateResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    gate: str
    fired: bool
    detail: str


class PolicyOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: WorkflowAction
    reasons: list[str]
    gate_path: list[GateResult]
