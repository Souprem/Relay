import Link from "next/link";

import { Td, TableScroll, Th } from "@/components/ui/Table";
import { pct, rateText, threshold } from "@/lib/format";
import type { HeadlineRow } from "@/lib/types";

export function HeadlineTable({ rows }: { rows: HeadlineRow[] }) {
  return (
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
                <Td num className={unsafe ? "font-medium text-unsafe" : ""}>
                  {r.uar.count}/{r.uar.n}
                  {unsafe ? ` (${pct(r.uar.rate)})` : ""}
                </Td>
                <Td num>{pct(r.uar.ci95?.high ?? null)}</Td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </TableScroll>
  );
}
