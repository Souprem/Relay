// The only place colour is assigned. Every class here is a Relay theme token (globals.css).
import type { Action, GateStatus } from "./types";

export const ACTION_TEXT: Record<Action, string> = {
  AUTO_PROCESS: "text-auto",
  REQUEST_INFO: "text-info",
  HUMAN_REVIEW: "text-review",
};

export const ACTION_SWATCH: Record<Action, string> = {
  AUTO_PROCESS: "bg-auto",
  REQUEST_INFO: "bg-info",
  HUMAN_REVIEW: "bg-review",
};

// The CSS variable behind each action, for SVG fills and strokes.
export const ACTION_VAR: Record<Action, string> = {
  AUTO_PROCESS: "var(--auto)",
  REQUEST_INFO: "var(--info)",
  HUMAN_REVIEW: "var(--review)",
};

/** The action a gate produces when it fires (relay/workflow/engine.py). */
export const GATE_ACTION: Record<string, Action> = {
  provider: "HUMAN_REVIEW",
  age: "HUMAN_REVIEW",
  contradiction: "HUMAN_REVIEW",
  documentation: "REQUEST_INFO",
  missing_evidence: "REQUEST_INFO",
  auto_process: "AUTO_PROCESS",
  default_review: "HUMAN_REVIEW",
};

export const GATE_STATUS_TEXT: Record<GateStatus, string> = {
  passed: "text-ink-2",
  FIRED: "text-ink",
  "not reached": "text-ink-3",
};
