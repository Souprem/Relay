import { pct, threshold } from "@/lib/format";
import type { FrontierPoint } from "@/lib/types";

import { ChartData } from "./ChartData";
import { ChartFrame } from "./ChartFrame";
import { countAxis, dialSummary, layoutDial, strictToLoose, type DialLabel } from "./dialLayout";

const TONE = { ink: "var(--ink)", unsafe: "var(--unsafe)" } as const;

function Label({ label, fill = "var(--ink)" }: { label: DialLabel; fill?: string }) {
  return (
    <g>
      {label.leader ? (
        <line
          x1={label.leader.x}
          x2={label.leader.x}
          y1={label.leader.y1}
          y2={label.leader.y2}
          stroke={fill}
          strokeWidth="1"
        />
      ) : null}
      <text x={label.x} textAnchor={label.anchor} fontSize={label.fontSize} fill={fill}>
        {label.lines.map((line, i) => (
          <tspan key={i} x={label.x} y={label.ys[i]}>
            {line.map((s, j) => (
              <tspan key={j} fill={s.tone === "unsafe" ? TONE.unsafe : undefined}>
                {s.text}
              </tspan>
            ))}
          </tspan>
        ))}
      </text>
    </g>
  );
}

/**
 * The threshold dial: one column per auto_process threshold, strict on the left, loose on the
 * right. A column's height is the cases that threshold would auto-process; its red top is the
 * unsafe automations among them. Every count comes from the exported frontier points.
 */
export function ThresholdDial({
  points,
  operating,
  source,
  label,
}: {
  points: FrontierPoint[];
  operating: number;
  /** Where the operating point came from, e.g. "chosen on gen-v0.2-dev". */
  source: string;
  label: string;
}) {
  const ordered = strictToLoose(points);
  const n = ordered[0]?.n ?? 0;
  const axis = countAxis(Math.max(0, ...ordered.map((p) => p.auto)));
  const span = ordered.length
    ? `${threshold(ordered[0].auto_threshold)} to ${threshold(ordered[ordered.length - 1].auto_threshold)}`
    : "";
  return (
    <figure>
      <ChartFrame
        title={`Cases auto-processed and unsafe automations at each auto_process threshold, ${span}, for ${label}`}
        description={dialSummary(points, operating, source)}
        width={1104}
        midWidth={700}
        height={340}
        marginTop={54}
        marginTopNarrow={70}
        xDomain={[-0.5, ordered.length - 0.5]}
        yDomain={[0, axis.max]}
        xTicks={[]}
        yTicks={axis.ticks}
        xFormat={() => ""}
        yFormat={(v) => String(v)}
        xLabel="stricter ← auto_process threshold → looser"
        yLabel={`cases auto-processed (of ${n})`}
      >
        {(frame) => {
          const { inner, fs } = frame;
          const layout = layoutDial(points, operating, source, frame);
          return (
            <g>
              <g aria-hidden="true">
                {layout.ticks.map((t) => (
                  <g key={t.text}>
                    <line x1={t.x} x2={t.x} y1={inner.bottom} y2={inner.bottom + 4} stroke="var(--rule-strong)" />
                    <text
                      x={t.x}
                      y={inner.bottom + 18}
                      textAnchor="middle"
                      fontSize={fs(11)}
                      fill={t.operating ? "var(--ink)" : "var(--ink-3)"}
                      fontWeight={t.operating ? 600 : 400}
                    >
                      {t.text}
                    </text>
                  </g>
                ))}
              </g>
              <g data-role="bars">
                {layout.bars.map((b) => (
                  <g key={b.point.auto_threshold} data-threshold={threshold(b.point.auto_threshold)}>
                    {b.point.auto - b.point.unsafe > 0 ? (
                      <rect
                        data-part="safe"
                        x={b.x - b.width / 2}
                        y={b.safeTop}
                        width={b.width}
                        height={b.bottom - b.safeTop}
                        fill={b.operating ? "var(--ink)" : "var(--hatch)"}
                      />
                    ) : null}
                    {b.point.unsafe > 0 ? (
                      <rect
                        data-part="unsafe"
                        x={b.x - b.width / 2}
                        y={b.top}
                        width={b.width}
                        height={b.safeTop - b.top}
                        fill="var(--unsafe)"
                      />
                    ) : null}
                  </g>
                ))}
              </g>
              <g aria-hidden="true">
                {layout.firstUnsafe ? <Label label={layout.firstUnsafe} fill="var(--unsafe)" /> : null}
                {layout.note ? <Label label={layout.note} fill="var(--ink-3)" /> : null}
                {layout.operating ? <Label label={layout.operating} /> : null}
              </g>
            </g>
          );
        }}
      </ChartFrame>
      <ChartData
        summary="Every threshold"
        columns={["auto_process", "automated", "unsafe", "unsafe / auto", "correct"]}
        rows={ordered.map((p) => [
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
