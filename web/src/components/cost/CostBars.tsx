import type { CostData } from "@/lib/types";

/**
 * Two horizontal bars on a linear scale from $0: Claude's cost per case and Jev's. The longer bar
 * spans the full width, so the shorter one is its true fraction of it (at 89× it is a sliver,
 * which is the point). Neutral ink only: colour on this site means an action or an unsafe case.
 */
export function CostBars({ headline }: { headline: CostData["comparison"]["headline"] }) {
  const { claude, jev, ratio } = headline;
  const max = Math.max(Number(claude.per_case_usd), Number(jev.per_case_usd));
  const rows = [
    { key: "claude", label: `${claude.label}, ${claude.mode}`, side: claude, tone: "bg-ink-3" },
    {
      key: "jev",
      label: `${jev.label}, ${jev.mode}${jev.estimate_label ? ` (${jev.estimate_label})` : ""}`,
      side: jev,
      tone: "bg-ink",
    },
  ];
  return (
    <figure className="max-w-[40rem]">
      <figcaption className="text-label font-semibold uppercase text-ink-2">
        Cost per case on {headline.claude.n} gold cases, same questions · linear scale from $0
      </figcaption>
      <dl className="mt-1 grid grid-cols-[minmax(0,1fr)] gap-y-1 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-x-2">
        {rows.map((r) => {
          const width = (Number(r.side.per_case_usd) / max) * 100;
          return (
            <div key={r.key} className="contents">
              <dt className="text-sm text-ink-2 sm:pt-0.5">{r.label}</dt>
              <dd className="flex items-center gap-1">
                <span className="relative block h-2 min-w-0 flex-1" aria-hidden="true">
                  <span
                    className={`absolute inset-y-0 left-0 block ${r.tone}`}
                    style={{ width: `max(2px, ${width}%)` }}
                  />
                </span>
                <span className="num w-[5.5rem] shrink-0 text-right text-sm text-ink">{r.side.per_case_text}</span>
              </dd>
            </div>
          );
        })}
      </dl>
      <p className="mt-1 text-sm text-ink-3">
        Claude cost {ratio.text} as much per case. The Jev bar is drawn at least 2px wide so it stays visible.
      </p>
    </figure>
  );
}
