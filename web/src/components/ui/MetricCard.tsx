import { ciText, pct } from "@/lib/format";
import type { Rate } from "@/lib/types";

/** One rate with its count and exact 95% interval, drawn as a range on a 0–100% scale. */
export function MetricCard({ label, rate, hint }: { label: string; rate: Rate; hint?: string }) {
  const ci = rate.ci95;
  return (
    <div className="border-t border-ink pt-1">
      <div className="text-label font-semibold uppercase text-ink-2">{label}</div>
      <div className="num mt-1 text-xl text-ink">{pct(rate.rate)}</div>
      <div className="num text-sm text-ink-2">
        {rate.count}/{rate.n}
        {hint ? <span className="text-ink-3"> {hint}</span> : null}
      </div>
      <div className="mt-1" aria-label={`95% confidence interval ${ciText(rate)}`}>
        <div className="relative h-1">
          <span className="absolute inset-x-0 top-1/2 h-px bg-rule" />
          {ci ? (
            <>
              <span
                className="absolute top-0.5 h-0.5 bg-ink-3"
                style={{ left: `${ci.low * 100}%`, width: `${Math.max((ci.high - ci.low) * 100, 0.5)}%` }}
              />
              {rate.rate !== null ? (
                <span
                  className="absolute top-0 h-1 w-px bg-ink"
                  style={{ left: `${rate.rate * 100}%` }}
                />
              ) : null}
            </>
          ) : null}
        </div>
        <div className="num mt-0.5 text-label tracking-normal text-ink-3">95% CI {ciText(rate)}</div>
      </div>
    </div>
  );
}
