import { THRESHOLD_LABELS, prob, threshold as fmtThreshold } from "@/lib/format";

export interface BarTick {
  name: string;
  value: number;
}

const CHAR_PX = 7.3; // IBM Plex Mono at text-label (12px): 0.6em per character
const LABEL_PAD_PX = 8;
// The narrowest the track gets (a 390px phone, less page padding). Labels that fit apart here fit
// apart at every wider size, because the gap between two ticks grows with the track.
export const MIN_TRACK_PX = 300;

export function tickLabel(t: BarTick): string {
  return `${THRESHOLD_LABELS[t.name] ?? t.name} ${fmtThreshold(t.value)}`;
}

function alignment(value: number): "right" | "left" | "center" {
  return value > 0.9 ? "right" : value < 0.1 ? "left" : "center";
}

/**
 * The label row for each tick: 0 above the track, 1 below it. Labels are laid out left to right on
 * the narrowest track; a label that would overlap the previous one in the row above goes below.
 */
export function tickRows(ticks: BarTick[], trackPx = MIN_TRACK_PX): number[] {
  const extent = (t: BarTick): [number, number] => {
    const x = t.value * trackPx;
    const w = tickLabel(t).length * CHAR_PX;
    const a = alignment(t.value);
    return a === "right" ? [x - w, x] : a === "left" ? [x, x + w] : [x - w / 2, x + w / 2];
  };
  const order = ticks.map((t, i) => i).sort((a, b) => ticks[a].value - ticks[b].value);
  const rows = new Array<number>(ticks.length).fill(0);
  const rowEnd = [-Infinity, -Infinity];
  for (const i of order) {
    const [start, end] = extent(ticks[i]);
    const row = start >= rowEnd[0] + LABEL_PAD_PX ? 0 : 1;
    rows[i] = row;
    rowEnd[row] = end;
  }
  return rows;
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
  const rows = tickRows(ticks);
  const twoRows = rows.includes(1);
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
          className={`relative ${twoRows ? "h-7" : "h-5"}`}
        >
          {ticks.map((t, i) => {
            const left = `${(t.value * 100).toFixed(2)}%`;
            const align = alignment(t.value);
            const below = rows[i] === 1;
            return (
              <span
                key={t.name}
                data-testid={`tick-${t.name}`}
                data-row={rows[i]}
                style={{ left }}
                className="absolute top-0 bottom-0"
              >
                <span
                  className={`absolute ${below ? "top-5" : "top-0"} whitespace-nowrap font-mono text-label tracking-normal text-ink-2 ${
                    align === "right" ? "right-0 pr-0.5" : align === "left" ? "left-0 pl-0.5" : "-translate-x-1/2"
                  }`}
                >
                  {tickLabel(t)}
                </span>
                <span className={`absolute w-px bg-ink ${below ? "top-3 h-2" : "top-2 h-3"}`} />
              </span>
            );
          })}
          <span className="absolute inset-x-0 top-3 h-1 border border-rule bg-paper-2" />
          {shown !== null ? (
            <span
              data-testid="bar-fill"
              className="absolute top-3 left-0 h-1 bg-ink-2"
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
