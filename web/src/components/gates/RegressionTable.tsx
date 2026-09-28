import Link from "next/link";

import { ActionBadge } from "@/components/ui/ActionBadge";
import { Td, TableScroll, Th } from "@/components/ui/Table";
import { ciText, rateText } from "@/lib/format";
import type { CaseEntry, RegressionReport } from "@/lib/types";

const ROWS: [keyof RegressionReport["baseline"], string][] = [
  ["correct", "Correct action"],
  ["automation", "Automation"],
  ["request_info", "Request info"],
  ["human_review", "Human review"],
  ["uar", "Unsafe / auto"],
];

function pp(a: number | null, b: number | null): string {
  if (a === null || b === null) return "—";
  const d = (b - a) * 100;
  return `${d >= 0 ? "+" : "−"}${Math.abs(d).toFixed(1)} pp`;
}

/** Baseline against candidate, each rate with its interval, as the regression gate prints it. */
export function RegressionMetrics({ report }: { report: RegressionReport }) {
  return (
    <TableScroll>
      <table className="w-full min-w-[44rem]">
        <thead>
          <tr>
            <Th>Metric</Th>
            <Th align="right">Baseline</Th>
            <Th align="right">95% CI</Th>
            <Th align="right">Candidate</Th>
            <Th align="right">95% CI</Th>
            <Th align="right">Δ</Th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map(([key, label]) => {
            const a = report.baseline[key] as RegressionReport["baseline"]["correct"];
            const b = report.candidate[key] as RegressionReport["baseline"]["correct"];
            return (
              <tr key={key}>
                <Td>{label}</Td>
                <Td num>{rateText(a)}</Td>
                <Td num className="text-ink-2">{ciText(a)}</Td>
                <Td num className={key === "uar" && b.count > a.count ? "font-medium text-unsafe" : ""}>{rateText(b)}</Td>
                <Td num className="text-ink-2">{ciText(b)}</Td>
                <Td num>{pp(a.rate, b.rate)}</Td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </TableScroll>
  );
}

export function CaseEntries({ title, entries, tone = "neutral" }: { title: string; entries: CaseEntry[]; tone?: "unsafe" | "neutral" }) {
  if (entries.length === 0) return null;
  return (
    <div className="mt-2">
      <p className={`font-mono text-sm font-medium ${tone === "unsafe" ? "text-unsafe" : "text-ink-2"}`}>
        {title} ({entries.length})
      </p>
      <ul className="mt-1 grid gap-1">
        {entries.slice(0, 12).map((e) => (
          <li key={e.case_id} className="grid gap-x-2 text-sm md:grid-cols-[9rem_minmax(0,1fr)]">
            {e.case_id.startsWith("GOLD-") || /^[A-Z]+-\d\d$/.test(e.case_id) ? (
              <Link href={`/cases/${e.case_id}/`} className="font-mono text-ink underline decoration-rule-strong hover:decoration-ink">
                {e.case_id}
              </Link>
            ) : (
              <span className="font-mono text-ink">{e.case_id}</span>
            )}
            <span className="flex flex-wrap items-center gap-x-1 text-ink-2">
              expected <ActionBadge action={e.expected} size="sm" />
              <span className="font-mono text-label tracking-normal">
                {e.action_baseline} → {e.action_candidate}
              </span>
              {Object.keys(e.crossed_gated).length ? (
                <span className="font-mono text-label tracking-normal text-ink-3">
                  crossed:{" "}
                  {Object.entries(e.crossed_gated)
                    .map(([d, ts]) => `${d} (${ts.join(", ")})`)
                    .join("; ")}
                </span>
              ) : null}
            </span>
          </li>
        ))}
        {entries.length > 12 ? <li className="text-sm text-ink-3">and {entries.length - 12} more</li> : null}
      </ul>
    </div>
  );
}
