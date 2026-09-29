import { ciText, ratePct } from "@/lib/format";
import type { Rate } from "@/lib/types";

/** One rate with its count and exact 95% interval, as the exporter formatted them. */
export function MetricCard({ label, rate, hint }: { label: string; rate: Rate; hint?: string }) {
  return (
    <div className="border-t border-ink pt-1">
      <div className="text-label font-semibold uppercase text-ink-2">{label}</div>
      <div className="num mt-1 text-xl text-ink">{ratePct(rate)}</div>
      <div className="num text-sm text-ink-2">
        {rate.count}/{rate.n}
        {hint ? <span className="text-ink-3"> {hint}</span> : null}
      </div>
      <div className="num mt-0.5 text-label tracking-normal text-ink-3">95% CI {ciText(rate)}</div>
    </div>
  );
}
