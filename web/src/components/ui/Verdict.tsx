import { ACTION_SHORT } from "@/lib/format";
import { ACTION_TEXT } from "@/lib/semantic";
import type { Action, Verdict } from "@/lib/types";

const VERDICT_LABEL: Record<Verdict, string> = {
  correct: "correct",
  "wrong-safe": "wrong, safe",
  UNSAFE: "UNSAFE",
};

/** The verdict in words: correct, wrong but safe, or an unsafe automation. */
export function VerdictLabel({ verdict }: { verdict: Verdict }) {
  if (verdict === "UNSAFE") {
    return (
      <span data-verdict={verdict} className="font-mono text-sm font-medium text-unsafe">
        UNSAFE
      </span>
    );
  }
  return (
    <span data-verdict={verdict} className="font-mono text-sm text-ink-2">
      {verdict === "wrong-safe" ? (
        <span className="hatch mr-0.5 inline-block size-1 align-middle" aria-hidden="true" />
      ) : null}
      {VERDICT_LABEL[verdict]}
    </span>
  );
}

/**
 * One provider's result in the dense case table: the action it took (short name, action colour)
 * on a background that carries the verdict: none when correct, a hatch when wrong but safe, a red
 * tint when it automated a case that needed a person or more information.
 */
export function VerdictCell({ action, verdict }: { action: Action; verdict: Verdict }) {
  const base = "inline-flex h-3 w-8 items-center justify-center font-mono text-label tracking-normal";
  if (verdict === "UNSAFE") {
    return (
      <span
        data-verdict={verdict}
        title={`${action}: unsafe automation`}
        className={`${base} bg-unsafe-tint font-medium text-unsafe outline outline-1 outline-unsafe`}
      >
        {ACTION_SHORT[action]}
        <span className="sr-only">, unsafe</span>
      </span>
    );
  }
  return (
    <span
      data-verdict={verdict}
      title={`${action}: ${verdict === "correct" ? "correct" : "wrong, safe"}`}
      className={`${base} ${ACTION_TEXT[action]} ${verdict === "wrong-safe" ? "hatch" : ""}`}
    >
      {ACTION_SHORT[action]}
      <span className="sr-only">{verdict === "correct" ? ", correct" : ", wrong but safe"}</span>
    </span>
  );
}
