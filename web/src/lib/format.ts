import type { Action, Rate } from "./types";

export const ACTIONS: Action[] = ["AUTO_PROCESS", "REQUEST_INFO", "HUMAN_REVIEW"];

export const ACTION_SHORT: Record<Action, string> = {
  AUTO_PROCESS: "AUTO",
  REQUEST_INFO: "INFO",
  HUMAN_REVIEW: "REVIEW",
};

export const DECISION_LABELS: Record<string, string> = {
  diagnosis_support: "Diagnosis supported",
  step_therapy: "Step therapy met",
  documentation_complete: "Documentation complete",
  material_contradiction: "Material contradiction",
  missing_evidence: "Missing evidence",
};

export const THRESHOLD_LABELS: Record<string, string> = {
  auto_process: "auto",
  contradiction_review: "review",
  contradiction_auto_block: "block",
  documentation_request_info: "request info",
  missing_evidence_request_info: "request info",
};

/** 0.912 -> "91.2%"; null -> "—". */
export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

/** "91/100 (91.0%)", the way the CLI prints a rate. */
export function rateText(r: Rate): string {
  return r.n === 0 ? `${r.count}/0` : `${r.count}/${r.n} (${pct(r.rate)})`;
}

/** "83.6–95.8%" for a Clopper-Pearson interval; "—" when there is none. */
export function ciText(r: Rate): string {
  if (!r.ci95) return "—";
  return `${(r.ci95.low * 100).toFixed(1)}–${(r.ci95.high * 100).toFixed(1)}%`;
}

/** Probabilities to three places, as the engine's reasons print them. */
export function prob(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(3);
}

export function threshold(value: number): string {
  return value.toFixed(2);
}

export function usd(value: string): string {
  return `$${Number(value).toFixed(2)}`;
}

export function shortSha(sha: string | null): string {
  return sha ? sha.slice(0, 7) : "unknown";
}
