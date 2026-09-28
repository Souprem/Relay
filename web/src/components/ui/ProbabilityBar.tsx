import { THRESHOLD_LABELS, prob, threshold as fmtThreshold } from "@/lib/format";

export interface BarTick {
  name: string;
  value: number;
}

/**
 * A probability on a 0–1 track, with a tick at every threshold an engine gate compares it with.
 * The fill is neutral: whether a threshold was cleared is shown by the gate path, not by colour.
 */
export function ProbabilityBar({
  label,
  value,
  valueText,
  ticks,
  detail,
}: {
  label: string;
  value: number | null;
  valueText?: string;
  ticks: BarTick[];
  detail?: string;
}) {
  const shown = value === null ? null : Math.min(1, Math.max(0, value));
  const tickText = ticks
    .map((t) => `${THRESHOLD_LABELS[t.name] ?? t.name} threshold ${fmtThreshold(t.value)}`)
    .join("; ");
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-x-2 gap-y-0.5 md:grid-cols-[11rem_minmax(0,1fr)_5.5rem]">
      <div className="text-base text-ink md:pb-0.5">{label}</div>
      <div className="order-3 col-span-2 md:order-none md:col-span-1">
        <div
          role="img"
          aria-label={`${label}: ${value === null ? "missing" : prob(value)}${tickText ? `; ${tickText}` : ""}`}
          className="relative h-5"
        >
          {ticks.map((t) => {
            const left = `${(t.value * 100).toFixed(2)}%`;
            const alignRight = t.value > 0.9;
            const alignLeft = t.value < 0.1;
            return (
              <span
                key={t.name}
                data-testid={`tick-${t.name}`}
                style={{ left }}
                className="absolute top-0 bottom-0"
              >
                <span
                  className={`absolute top-0 whitespace-nowrap font-mono text-label tracking-normal text-ink-2 ${
                    alignRight ? "right-0 pr-0.5" : alignLeft ? "left-0 pl-0.5" : "-translate-x-1/2"
                  }`}
                >
                  {THRESHOLD_LABELS[t.name] ?? t.name} {fmtThreshold(t.value)}
                </span>
                <span className="absolute top-2 bottom-0 w-px bg-ink" />
              </span>
            );
          })}
          <span className="absolute inset-x-0 bottom-1 h-1 border border-rule bg-paper-2" />
          {shown !== null ? (
            <span
              data-testid="bar-fill"
              className="absolute bottom-1 left-0 h-1 bg-ink-2"
              style={{ width: `${(shown * 100).toFixed(2)}%` }}
            />
          ) : null}
        </div>
      </div>
      <div className="num text-right text-base text-ink md:pb-0.5">
        {valueText ?? (value === null ? "missing" : prob(value))}
      </div>
      {detail ? (
        <div className="order-4 col-span-2 font-mono text-label tracking-normal text-ink-3 md:col-start-2 md:col-span-2">
          {detail}
        </div>
      ) : null}
    </div>
  );
}
