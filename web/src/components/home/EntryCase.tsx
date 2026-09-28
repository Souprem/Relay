import Link from "next/link";

import { ActionBadge } from "@/components/ui/ActionBadge";
import { VerdictCell } from "@/components/ui/Verdict";
import type { CaseDetail } from "@/lib/types";

export function EntryCase({ kind, detail, summary }: { kind: string; detail: CaseDetail; summary: string }) {
  const models = detail.providers.filter((p) => p.provider !== "groundtruth");
  return (
    <article className="border-t border-ink pt-2">
      <p className="text-label font-semibold uppercase text-ink-2">{kind}</p>
      <h3 className="mt-1">
        <Link href={`/cases/${detail.id}/`} className="font-mono text-lg text-ink underline decoration-rule-strong hover:decoration-ink">
          {detail.id}
        </Link>
      </h3>
      <p className="mt-1 max-w-prose text-md text-ink-2">{summary}</p>
      <dl className="mt-2 grid grid-cols-[auto_1fr] items-center gap-x-2 gap-y-0.5 text-sm">
        <dt className="text-ink-3">Expected</dt>
        <dd>
          <ActionBadge action={detail.ground_truth.expected_action} size="sm" />
        </dd>
        {models.map((p) => (
          <div key={p.slug} className="contents">
            <dt className="text-ink-2">{p.label}</dt>
            <dd>
              <VerdictCell action={p.action} verdict={p.verdict} />
            </dd>
          </div>
        ))}
      </dl>
    </article>
  );
}
