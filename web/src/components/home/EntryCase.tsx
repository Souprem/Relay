import Link from "next/link";

import type { CaseDetail } from "@/lib/types";

/** One suggested starting case, on one line: what kind it is, its id, and why it is worth opening. */
export function EntryCase({ kind, detail, summary }: { kind: string; detail: CaseDetail; summary: string }) {
  return (
    <li className="grid gap-x-2 border-b border-rule py-1.5 md:grid-cols-[7rem_9rem_minmax(0,1fr)] md:items-baseline">
      <span className="text-label font-semibold uppercase text-ink-3">{kind}</span>
      <Link href={`/cases/${detail.id}/`} className="font-mono text-md text-ink underline decoration-rule-strong hover:decoration-ink">
        {detail.id}
      </Link>
      <span className="text-md text-ink-2">{summary}</span>
    </li>
  );
}
