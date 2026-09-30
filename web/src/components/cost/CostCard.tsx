import type { RunCost } from "@/lib/types";

const KIND_NOTE: Record<RunCost["kind"], string> = {
  ledger: "from the spend ledger",
  "ledger-sum": "from the spend ledger",
  "trace-estimate": "trace estimate",
  "no-call": "no provider call",
  reused: "no new calls",
};

/** A run's cost per case, total and source, beside its rate cards on /evals. */
export function CostCard({ cost }: { cost: RunCost }) {
  return (
    <div className="border-t border-ink pt-1" title={cost.source}>
      <div className="text-label font-semibold uppercase text-ink-2">Cost / case</div>
      <div className="num mt-1 text-xl text-ink">{cost.per_case_text ?? "—"}</div>
      <div className="num text-sm text-ink-2">
        {cost.total_text === null ? "reused answers" : `${cost.total_text} total`}
        {cost.mode ? <span className="text-ink-3"> · {cost.mode}</span> : null}
      </div>
      <div className="mt-0.5 text-label tracking-normal text-ink-3">{KIND_NOTE[cost.kind]}</div>
    </div>
  );
}
