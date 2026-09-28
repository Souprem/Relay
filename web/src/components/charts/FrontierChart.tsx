import { pct, threshold } from "@/lib/format";
import { niceMax, niceTicks } from "@/lib/scale";
import type { FrontierPoint } from "@/lib/types";

import { ChartData } from "./ChartData";
import { ChartFrame } from "./ChartFrame";

/**
 * The automation/safety frontier: every auto_process threshold from 0.50 to 0.99 re-decided over
 * the stored judgments. x is the share of cases automated, y the share of automations that were
 * unsafe. Lowering the threshold moves right along the curve.
 */
export function FrontierChart({
  points,
  operating,
  ceiling,
  label,
}: {
  points: FrontierPoint[];
  operating: number;
  ceiling: number;
  label: string;
}) {
  const usable = [...points]
    .filter((p) => p.uar !== null)
    .sort((a, b) => b.auto_threshold - a.auto_threshold);
  const distinct: FrontierPoint[] = [];
  for (const p of usable) {
    const last = distinct[distinct.length - 1];
    if (!last || last.auto !== p.auto || last.unsafe !== p.unsafe) distinct.push(p);
  }
  const op = points.find((p) => Math.abs(p.auto_threshold - operating) < 1e-9);
  const xMax = niceMax(Math.max(0.1, ...usable.map((p) => p.automation_rate)) * 1.1);
  const yMax = niceMax(Math.max(ceiling * 3, ...usable.map((p) => p.uar ?? 0)));
  const first = distinct[0];
  const last = distinct[distinct.length - 1];
  return (
    <figure>
      <ChartFrame
        title={`Automation against unsafe automation rate for ${label}, auto_process 0.50 to 0.99`}
        width={1104}
        height={360}
        xDomain={[0, xMax]}
        yDomain={[0, yMax]}
        xTicks={niceTicks(0, xMax, 5)}
        yTicks={niceTicks(0, yMax, 4)}
        xFormat={(v) => pct(v, 0)}
        yFormat={(v) => pct(v, yMax < 0.05 ? 1 : 0)}
        xLabel="Automation rate (share of cases auto-processed)"
        yLabel="Unsafe / automated"
      >
        {({ x, y, inner }) => (
          <g>
            <line
              x1={inner.left}
              x2={inner.right}
              y1={y(ceiling)}
              y2={y(ceiling)}
              stroke="var(--ink-3)"
              strokeDasharray="4 4"
            />
            <text x={inner.right} y={y(ceiling) - 6} textAnchor="end" fontSize="11" fill="var(--ink-2)">
              {pct(ceiling, 0)} ceiling
            </text>
            <polyline
              fill="none"
              stroke="var(--ink-2)"
              strokeWidth="1.5"
              points={distinct.map((p) => `${x(p.automation_rate)},${y(p.uar ?? 0)}`).join(" ")}
            />
            {distinct.map((p) => (
              <circle
                key={p.auto_threshold}
                cx={x(p.automation_rate)}
                cy={y(p.uar ?? 0)}
                r="2.5"
                fill="var(--paper)"
                stroke="var(--ink-2)"
              />
            ))}
            {first && first !== last ? (
              <text x={x(first.automation_rate) + 6} y={y(first.uar ?? 0) + 14} fontSize="11" fill="var(--ink-3)">
                t={threshold(first.auto_threshold)}
              </text>
            ) : null}
            {last ? (
              <text
                x={x(last.automation_rate) + 6}
                y={y(last.uar ?? 0) + 14}
                textAnchor="start"
                fontSize="11"
                fill="var(--ink-3)"
              >
                t={threshold(usable[usable.length - 1].auto_threshold)}
              </text>
            ) : null}
            {op && op.uar !== null ? (
              <g>
                <circle cx={x(op.automation_rate)} cy={y(op.uar)} r="6" fill="none" stroke="var(--ink)" strokeWidth="1.5" />
                <circle cx={x(op.automation_rate)} cy={y(op.uar)} r="2.5" fill="var(--ink)" />
                <line
                  x1={x(op.automation_rate)}
                  x2={x(op.automation_rate)}
                  y1={y(op.uar) - 8}
                  y2={y(op.uar) - 36}
                  stroke="var(--ink)"
                />
                <text
                  x={x(op.automation_rate) + (op.automation_rate > xMax * 0.6 ? -6 : 6)}
                  y={y(op.uar) - 40}
                  textAnchor={op.automation_rate > xMax * 0.6 ? "end" : "start"}
                  fontSize="12"
                  fill="var(--ink)"
                >
                  operating point {threshold(op.auto_threshold)}: {pct(op.automation_rate)} automated, {op.unsafe}/
                  {op.auto} unsafe
                </text>
              </g>
            ) : null}
          </g>
        )}
      </ChartFrame>
      <ChartData
        summary="Frontier data (every threshold)"
        columns={["auto_process", "automated", "unsafe", "unsafe / auto", "correct"]}
        rows={points.map((p) => [
          threshold(p.auto_threshold),
          `${p.auto}/${p.n}`,
          p.unsafe,
          pct(p.uar),
          `${p.correct}/${p.n}`,
        ])}
      />
    </figure>
  );
}
