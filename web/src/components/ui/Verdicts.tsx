const STYLE: Record<string, string> = {
  PASS: "text-auto",
  PROMOTE: "text-auto",
  FAIL: "text-unsafe",
  HOLD: "text-unsafe",
  SKIPPED: "text-ink-3",
};

/** A gate or rollout verdict: PASS / FAIL / SKIPPED / PROMOTE / HOLD. */
export function GateVerdict({ verdict }: { verdict: string }) {
  return (
    <span data-verdict={verdict} className={`font-mono text-sm font-medium ${STYLE[verdict] ?? "text-ink"}`}>
      {verdict}
    </span>
  );
}
