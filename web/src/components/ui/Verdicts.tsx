import { GATE_VERDICT_TEXT, type GateVerdictName } from "@/lib/semantic";

/** A gate or rollout verdict: PASS / FAIL / SKIPPED / PROMOTE / HOLD. */
export function GateVerdict({ verdict }: { verdict: string }) {
  const tone = GATE_VERDICT_TEXT[verdict as GateVerdictName] ?? "text-ink";
  return (
    <span data-verdict={verdict} className={`font-mono text-sm font-medium ${tone}`}>
      {verdict}
    </span>
  );
}
