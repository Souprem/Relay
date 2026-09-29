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
        midWidth={760}
        height={360}
        xDomain={[0, xMax]}
        yDomain={[0, yMax]}
        xTicks={niceTicks(0, xMax, 5)}
        yTicks={niceTicks(0, yMax, 4)}
        xFormat={(v) => pct(v, 0)}
        yFormat={(v) => pct(v, yMax < 0.05 ? 1 : 0)}
        xLabel="Automation rate (share of cases auto-processed)"
        xLabelNarrow="Automation rate"
        yLabel="Unsafe / automated"
      >
        {({ x, y, inner, width, narrow, fs }) => {
          // The operating-point annotation sits above its point; an end label within ~48px of the
          // point would run into its leader line or text, so it is left out (VM-1).
          const opX = op && op.uar !== null ? x(op.automation_rate) : null;
          const opY = op && op.uar !== null ? y(op.uar) : null;
          const nearOp = (p: FrontierPoint) =>
            opX !== null && opY !== null && Math.hypot(x(p.automation_rate) - opX, y(p.uar ?? 0) - opY) < 48;
          // Flip the annotation to the left of its point when it would run past the plot's right edge
          // (0.6 em per mono character); the wide variants keep the original 60% rule.
          const annotationWidth = narrow && op ? `${pct(op.automation_rate)} auto, ${op.unsafe}/${op.auto} unsafe`.length * fs(12) * 0.6 : 0;
          const flip = op
            ? narrow
              ? (opX ?? 0) + 6 + annotationWidth > inner.right + 16
              : op.automation_rate > xMax * 0.6
            : false;
          // The annotation rises above the highest curve point near it, so it never sits on the line.
          const nearby = distinct.filter((p) => opX !== null && Math.abs(x(p.automation_rate) - opX) < (narrow ? 120 : 220));
          const topY = Math.min(opY ?? Infinity, ...nearby.map((p) => y(p.uar ?? 0)));
          const labelY = Math.max(inner.top + (narrow ? 26 : 12), topY - (narrow ? 44 : 32));
          return (

          <g>
            <line
              x1={inner.left}
              x2={inner.right}
              y1={y(ceiling)}
              y2={y(ceiling)}
              stroke="var(--ink-3)"
              strokeDasharray="4 4"
            />
            <text x={inner.right} y={y(ceiling) - 6} textAnchor="end" fontSize={fs(11)} fill="var(--ink-2)">
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
            {[first && first !== last ? first : null, last ? usable[usable.length - 1] : null].map((p, i) => {
              if (!p) return null;
              const at = i === 0 ? first : last;
              const text = `t=${threshold(p.auto_threshold)}`;
              const w = text.length * fs(11) * 0.6;
              const px = x(at.automation_rate);
              const py = y(at.uar ?? 0);
              // Right of the point unless that runs past the edge; above it when below would sit on
              // the x-axis tick labels.
              const right = px + 6 + w <= width - 4;
              const lx0 = right ? px + 6 : px - 6 - w;
              const ly = py + 14 > inner.bottom - 2 ? py - 8 : py + 14;
              // Leave the label out where it would touch the operating-point marker, leader or text.
              const hitsLeader =
                opX !== null && opY !== null && opX >= lx0 - 3 && opX <= lx0 + w + 3 && ly >= labelY - 16 && ly - 11 <= opY;
              if (nearOp(at) || hitsLeader) return null;
              return (
                <text key={text + i} x={lx0} y={ly} fontSize={fs(11)} fill="var(--ink-3)">
                  {text}
                </text>
              );
            })}
            {op && op.uar !== null ? (
              <g>
                <circle cx={x(op.automation_rate)} cy={y(op.uar)} r="6" fill="none" stroke="var(--ink)" strokeWidth="1.5" />
                <circle cx={x(op.automation_rate)} cy={y(op.uar)} r="2.5" fill="var(--ink)" />
                <line
                  x1={x(op.automation_rate)}
                  x2={x(op.automation_rate)}
                  y1={y(op.uar) - 8}
                  y2={labelY + 4}
                  stroke="var(--ink)"
                />
                {narrow ? (
                  <text
                    x={x(op.automation_rate) + (flip ? -6 : 6)}
                    y={labelY - fs(12) - 2}
                    textAnchor={flip ? "end" : "start"}
                    fontSize={fs(12)}
                    fill="var(--ink)"
                  >
                    <tspan>operating point {threshold(op.auto_threshold)}</tspan>
                    <tspan x={x(op.automation_rate) + (flip ? -6 : 6)} dy="1.2em">
                      {pct(op.automation_rate)} auto, {op.unsafe}/{op.auto} unsafe
                    </tspan>
                  </text>
                ) : (
                  <text
                    x={x(op.automation_rate) + (flip ? -6 : 6)}
                    y={labelY}
                    textAnchor={flip ? "end" : "start"}
                    fontSize="12"
                    fill="var(--ink)"
                  >
                    operating point {threshold(op.auto_threshold)}: {pct(op.automation_rate)} automated, {op.unsafe}/
                    {op.auto} unsafe
                  </text>
                )}
              </g>
            ) : null}
          </g>
          );
        }}
      </ChartFrame>
      <ChartData
        summary="Frontier data table, every threshold"
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
