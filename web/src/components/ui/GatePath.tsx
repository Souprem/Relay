import { ACTION_SWATCH, ACTION_TEXT, GATE_ACTION, GATE_STATUS_TEXT } from "@/lib/semantic";
import type { GateRow } from "@/lib/types";

const GATE_LABELS: Record<string, string> = {
  provider: "provider",
  age: "age",
  contradiction: "contradiction",
  documentation: "documentation",
  missing_evidence: "missing_evidence",
  auto_process: "auto_process",
  default_review: "default_review",
};

function Marker({ row }: { row: GateRow }) {
  if (row.status === "FIRED") {
    const action = GATE_ACTION[row.gate] ?? "HUMAN_REVIEW";
    return <span className={`block size-1.5 ${ACTION_SWATCH[action]}`} aria-hidden="true" />;
  }
  if (row.status === "passed") {
    return <span className="block size-1.5 rounded-full border border-ink-2 bg-paper" aria-hidden="true" />;
  }
  return (
    <span className="block size-1.5 rounded-full border border-dashed border-ink-3 bg-paper" aria-hidden="true" />
  );
}

/**
 * The engine's gates in the order it runs them. The first gate that fires decides the action;
 * the gates after it are not reached.
 */
export function GatePath({ gates }: { gates: GateRow[] }) {
  return (
    <ol className="relative" aria-label="Gate path">
      {gates.map((row, i) => {
        const last = i === gates.length - 1;
        const fired = row.status === "FIRED";
        const action = GATE_ACTION[row.gate] ?? "HUMAN_REVIEW";
        return (
          <li
            key={row.gate}
            data-status={row.status}
            className="relative grid grid-cols-[1.5rem_minmax(0,1fr)] gap-x-1 pb-1.5"
          >
            <div className="relative flex justify-center pt-1">
              <Marker row={row} />
              {!last ? (
                <span
                  aria-hidden="true"
                  className={`absolute top-3 bottom-[-0.25rem] left-1/2 w-0 border-l ${
                    row.status === "not reached" || gates[i + 1]?.status === "not reached"
                      ? "border-dashed border-rule-strong"
                      : "border-rule-strong"
                  }`}
                />
              ) : null}
            </div>
            <div className={fired ? "border-l-2 border-ink pl-1" : "pl-1"}>
              <div className="flex flex-wrap items-baseline gap-x-1">
                <span className={`font-mono text-sm ${fired ? "font-medium text-ink" : GATE_STATUS_TEXT[row.status]}`}>
                  {GATE_LABELS[row.gate] ?? row.gate}
                </span>
                <span
                  className={`font-mono text-label tracking-normal ${
                    fired ? `font-medium ${ACTION_TEXT[action]}` : GATE_STATUS_TEXT[row.status]
                  }`}
                >
                  {fired ? `FIRED → ${action}` : row.status}
                </span>
              </div>
              {row.detail ? (
                <p className="font-mono text-label tracking-normal text-ink-2 break-words">{row.detail}</p>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
