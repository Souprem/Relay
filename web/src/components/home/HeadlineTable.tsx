import Link from "next/link";

import { Td, TableScroll, Th } from "@/components/ui/Table";
import { ratePct, rateText, threshold } from "@/lib/format";
import type { HeadlineRow } from "@/lib/types";
import { UNSAFE_TEXT } from "@/lib/semantic";

/** Below md the table becomes one stacked block per run, so no column is hidden off-screen. */
function HeadlineStack({ rows }: { rows: HeadlineRow[] }) {
  return (
    <ul className="border-t border-ink md:hidden">
      {rows.map((r) => {
        const unsafe = r.uar.count > 0;
        const cells: [string, string, string?][] = [
          ["Correct action", rateText(r.correct)],
          ["Automation", rateText(r.automation)],
          [
            "Unsafe / auto",
            `${r.uar.count}/${r.uar.n}${unsafe ? ` (${ratePct(r.uar)})` : ""}`,
            unsafe ? `font-medium ${UNSAFE_TEXT}` : "",
          ],
          ["Unsafe 95% upper", r.uar.ci_high_pct ?? "—"],
        ];
        return (
          <li key={r.run_id} className="border-b border-rule py-1.5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-2">
              <Link href={`/evals/${r.run_id}/`} className="text-md underline decoration-rule-strong hover:decoration-ink">
                {r.label}
              </Link>
              <span className="num text-sm text-ink-2">
                @{threshold(r.auto_process)}
                {r.flat ? " flat" : ""}
              </span>
            </div>
            <div className="whitespace-nowrap font-mono text-sm text-ink-2">
              {r.dataset} · n {r.n}
              {r.note ? <span className="font-sans text-ink-3"> ({r.note})</span> : null}
            </div>
            <dl className="mt-1 grid grid-cols-2 gap-x-2 gap-y-0.5">
              {cells.map(([k, v, cls]) => (
                <div key={k}>
                  <dt className="text-label font-semibold uppercase text-ink-3">{k}</dt>
                  <dd className={`num text-base text-ink ${cls ?? ""}`}>{v}</dd>
                </div>
              ))}
            </dl>
          </li>
        );
      })}
    </ul>
  );
}

export function HeadlineTable({ rows }: { rows: HeadlineRow[] }) {
  return (
    <>
      <HeadlineStack rows={rows} />
      <div className="hidden md:block">
        <TableScroll>
          <table className="w-full min-w-[56rem]">
            <thead>
              <tr>
                <Th>Dataset</Th>
                <Th align="right">n</Th>
                <Th>Provider</Th>
                <Th align="right">auto_process</Th>
                <Th align="right">Correct action</Th>
                <Th align="right">Automation</Th>
                <Th align="right">Unsafe / auto</Th>
                <Th align="right">Unsafe 95% upper</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const unsafe = r.uar.count > 0;
                return (
                  <tr key={r.run_id} className="hover:bg-paper-2">
                    <Td className="whitespace-nowrap font-mono text-sm">{r.dataset}</Td>
                    <Td num>{r.n}</Td>
                    <Td>
                      <Link href={`/evals/${r.run_id}/`} className="underline decoration-rule-strong hover:decoration-ink">
                        {r.label}
                      </Link>
                      {r.note ? <span className="ml-1 text-sm text-ink-3">({r.note})</span> : null}
                    </Td>
                    <Td num>
                      {threshold(r.auto_process)}
                      {r.flat ? <span className="text-ink-3"> flat</span> : null}
                    </Td>
                    <Td num>{rateText(r.correct)}</Td>
                    <Td num>{rateText(r.automation)}</Td>
                    <Td num className={unsafe ? `font-medium ${UNSAFE_TEXT}` : ""}>
                      {r.uar.count}/{r.uar.n}
                      {unsafe ? ` (${ratePct(r.uar)})` : ""}
                    </Td>
                    <Td num>{r.uar.ci_high_pct ?? "—"}</Td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </TableScroll>
      </div>
    </>
  );
}
