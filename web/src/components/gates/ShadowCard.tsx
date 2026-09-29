import Link from "next/link";

import { GateVerdict } from "@/components/ui/Verdicts";
import { ACTIONS, ACTION_SHORT, rateText, ciText } from "@/lib/format";
import { ACTION_TEXT, UNSAFE_TEXT } from "@/lib/semantic";
import type { ShadowDemo } from "@/lib/types";

function Ids({ ids }: { ids: string[] }) {
  if (ids.length === 0) return <span className="text-ink-3">none</span>;
  return (
    <>
      {ids.map((id, i) => (
        <span key={id}>
          {i > 0 ? ", " : ""}
          <Link href={`/cases/${id}/`} className="font-mono underline decoration-rule-strong hover:decoration-ink">
            {id}
          </Link>
        </span>
      ))}
    </>
  );
}

/** A shadow rollout: agreement without ground truth, then the evaluation-only promotion check. */
export function ShadowCard({ demo }: { demo: ShadowDemo }) {
  const m = demo.agreement.matrix;
  return (
    <article className="min-w-0 border-t border-ink pt-2">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-lg text-ink">{demo.title}</h3>
        <GateVerdict verdict={demo.decision} />
      </div>
      <p className="mt-1 text-md text-ink-2">{demo.description}</p>
      <p className="mt-2 font-mono text-sm text-ink">
        SHADOW RUN: {demo.proposals} proposals recorded; {demo.state_line}.
      </p>
      <p className="mt-2 text-sm text-ink-2">
        Agreement (no ground truth): <span className="num text-ink">{rateText(demo.agreement.agreed)}</span>, 95% CI{" "}
        <span className="num">{ciText(demo.agreement.agreed)}</span>
      </p>
      <table className="mt-1 text-sm" aria-label={`Incumbent ${demo.incumbent} by candidate ${demo.candidate}`}>
        <thead>
          <tr>
            <th scope="col" className="py-0.5 pr-2 text-left text-label font-semibold uppercase text-ink-3">
              incumbent \ candidate
            </th>
            {ACTIONS.map((a) => (
              <th key={a} scope="col" className={`num px-1 py-0.5 text-right text-label ${ACTION_TEXT[a]}`}>
                {ACTION_SHORT[a]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ACTIONS.map((row) => (
            <tr key={row} className="border-t border-rule">
              <th scope="row" className={`num py-0.5 pr-2 text-left text-label font-normal ${ACTION_TEXT[row]}`}>
                {ACTION_SHORT[row]}
              </th>
              {ACTIONS.map((col) => (
                <td
                  key={col}
                  className={`num px-1 py-0.5 text-right ${row === col ? "text-ink" : m[row][col] ? "font-medium text-ink" : "text-ink-3"}`}
                >
                  {m[row][col]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <dl className="mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-x-2 gap-y-0.5 text-sm">
        <dt className="text-ink-3">Would newly auto-process</dt>
        <dd>
          <Ids ids={demo.agreement.newly_auto} />
        </dd>
        <dt className="text-ink-3">Newly unsafe</dt>
        <dd className={demo.newly_unsafe.length ? UNSAFE_TEXT : ""}>
          <Ids ids={demo.newly_unsafe} />
        </dd>
        <dt className="text-ink-3">Still unsafe</dt>
        <dd>
          <Ids ids={demo.still_unsafe} />
        </dd>
      </dl>
      <p className="mt-2 font-mono text-sm text-ink">
        PROMOTION CHECK: {demo.decision}
        {demo.failures.length ? ` — ${demo.failures.join("; ")}` : ""}
      </p>
    </article>
  );
}
