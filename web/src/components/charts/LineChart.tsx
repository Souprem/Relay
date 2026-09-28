import { niceMax, niceTicks } from "@/lib/scale";

import { ChartData } from "./ChartData";
import { ChartFrame } from "./ChartFrame";

export interface Series {
  name: string;
  values: number[];
  emphasis?: boolean;
}

/** A few series over shared x values, each labelled at its right end (no legend). */
export function LineChart({
  title,
  xs,
  series,
  xLabel,
  yLabel,
  yUnit,
}: {
  title: string;
  xs: number[];
  series: Series[];
  xLabel: string;
  yLabel: string;
  yUnit: string;
}) {
  const yMax = niceMax(Math.max(...series.flatMap((s) => s.values)) * 1.1);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  return (
    <figure>
      <ChartFrame
        title={title}
        height={280}
        xDomain={[xMin, xMax]}
        yDomain={[0, yMax]}
        xTicks={xs}
        yTicks={niceTicks(0, yMax, 4)}
        xFormat={(v) => String(v)}
        yFormat={(v) => `${v}`}
        xLabel={xLabel}
        yLabel={`${yLabel} (${yUnit})`}
      >
        {({ x, y }) => (
          <g>
            {series.map((s) => (
              <g key={s.name}>
                <polyline
                  fill="none"
                  stroke={s.emphasis ? "var(--ink)" : "var(--ink-3)"}
                  strokeWidth={s.emphasis ? 2 : 1.25}
                  points={s.values.map((v, i) => `${x(xs[i])},${y(v)}`).join(" ")}
                />
                {s.values.map((v, i) => (
                  <circle key={i} cx={x(xs[i])} cy={y(v)} r="2.5" fill="var(--paper)" stroke="var(--ink-2)" />
                ))}
                <text
                  x={x(xs[xs.length - 1]) + 8}
                  y={y(s.values[s.values.length - 1])}
                  dy="0.32em"
                  fontSize="11"
                  fill={s.emphasis ? "var(--ink)" : "var(--ink-2)"}
                >
                  {s.name} {Math.round(s.values[s.values.length - 1])}
                </text>
              </g>
            ))}
          </g>
        )}
      </ChartFrame>
      <ChartData
        columns={[xLabel, ...series.map((s) => `${s.name} (${yUnit})`)]}
        rows={xs.map((xv, i) => [xv, ...series.map((s) => Math.round(s.values[i]))])}
      />
    </figure>
  );
}
