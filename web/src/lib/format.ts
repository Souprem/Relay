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

/**
 * Python's `f"{x:.{digits}f}"`: the exact binary value of x rounded half to even.
 *
 * JS `toFixed` rounds an exact tie up (74.25 -> "74.3") where Python rounds it to even
 * ("74.2"), and README.md and docs/RESULTS.md were written by Python. `toFixed(100)` gives the
 * exact decimal expansion of any double with |x| >= 2^-47 (at most 100 fractional digits), so
 * the half-even decision below is made on the same exact value Python uses. Smaller magnitudes
 * cannot sit on a tie at the few digits the site prints.
 */
export function pyFixed(x: number, digits: number): string {
  if (!Number.isFinite(x)) return String(x);
  const negative = x < 0 || Object.is(x, -0);
  const [whole, frac = ""] = Math.abs(x).toFixed(100).split(".");
  const kept = frac.slice(0, digits);
  const rest = frac.slice(digits);
  let digitsStr = whole + kept;
  const last = Number(digitsStr[digitsStr.length - 1]);
  const first = rest[0] ?? "0";
  const tail = rest.slice(1);
  const roundUp = first > "5" || (first === "5" && (/[1-9]/.test(tail) || last % 2 === 1));
  if (roundUp) {
    const chars = digitsStr.split("");
    let i = chars.length - 1;
    while (i >= 0 && chars[i] === "9") chars[i--] = "0";
    if (i < 0) chars.unshift("1");
    else chars[i] = String(Number(chars[i]) + 1);
    digitsStr = chars.join("");
  }
  const intPart = digits ? digitsStr.slice(0, digitsStr.length - digits) : digitsStr;
  const body = digits ? `${intPart}.${digitsStr.slice(-digits)}` : intPart;
  return negative ? `-${body}` : body;
}

/** Python's `f"{x:.1%}"` (x * 100 in floating point, then pyFixed): 0.7425 -> "74.2%"; null -> "—". */
export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return `${pyFixed(value * 100, digits)}%`;
}

/** Python's `round(x)` for display: 982.5 -> "982". */
export function roundInt(value: number): string {
  return pyFixed(value, 0);
}

/** "91/100 (91.0%)", the way the CLI prints a rate; the exporter formats it in Python. */
export function rateText(r: Rate): string {
  return r.text;
}

/** A rate's percentage as the exporter formatted it; "—" when n is 0. */
export function ratePct(r: Rate): string {
  return r.pct ?? "—";
}

/** "83.6–95.8%" for a Clopper-Pearson interval, formatted by the exporter; "—" when there is none. */
export function ciText(r: Rate): string {
  return r.ci_text ?? "—";
}

/** A signed percentage-point change, as the regression gate prints it: "+2.4 pp". */
export function ppText(a: number | null, b: number | null): string {
  if (a === null || b === null) return "—";
  const d = (b - a) * 100;
  const negative = d < 0 || Object.is(d, -0);
  return `${negative ? "−" : "+"}${pyFixed(Math.abs(d), 1)} pp`;
}

/** Probabilities to three places, as the engine's reasons print them. */
export function prob(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return pyFixed(value, 3);
}

export function threshold(value: number): string {
  return pyFixed(value, 2);
}

export function usd(value: string): string {
  return `$${pyFixed(Number(value), 2)}`;
}

export function shortSha(sha: string | null): string {
  return sha ? sha.slice(0, 7) : "unknown";
}
