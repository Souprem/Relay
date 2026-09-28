import { linear, type Scale } from "@/lib/scale";

export interface Frame {
  x: Scale;
  y: Scale;
  width: number;
  height: number;
  inner: { left: number; top: number; right: number; bottom: number };
}

const MARGIN = { top: 16, right: 24, bottom: 48, left: 56 };

/**
 * An SVG plot area with light gridlines, labelled ticks and real axis titles. Children draw the
 * marks with the frame's scales. The SVG scales to its container; text stays legible because the
 * viewBox is sized close to the rendered width.
 */
export function ChartFrame({
  title,
  width = 640,
  height = 320,
  xDomain,
  yDomain,
  xTicks,
  yTicks,
  xFormat,
  yFormat,
  xLabel,
  yLabel,
  children,
}: {
  title: string;
  width?: number;
  height?: number;
  xDomain: [number, number];
  yDomain: [number, number];
  xTicks: number[];
  yTicks: number[];
  xFormat: (v: number) => string;
  yFormat: (v: number) => string;
  xLabel: string;
  yLabel: string;
  children: (frame: Frame) => React.ReactNode;
}) {
  const inner = {
    left: MARGIN.left,
    top: MARGIN.top,
    right: width - MARGIN.right,
    bottom: height - MARGIN.bottom,
  };
  const x = linear(xDomain, [inner.left, inner.right]);
  const y = linear(yDomain, [inner.bottom, inner.top]);
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={title}
      className="block h-auto w-full overflow-visible font-mono text-ink"
    >
      <title>{title}</title>
      <g aria-hidden="true">
        {yTicks.map((t) => (
          <g key={`y${t}`}>
            <line x1={inner.left} x2={inner.right} y1={y(t)} y2={y(t)} stroke="var(--rule)" />
            <text x={inner.left - 8} y={y(t)} dy="0.32em" textAnchor="end" fontSize="11" fill="var(--ink-3)">
              {yFormat(t)}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <g key={`x${t}`}>
            <line x1={x(t)} x2={x(t)} y1={inner.bottom} y2={inner.bottom + 4} stroke="var(--rule-strong)" />
            <text x={x(t)} y={inner.bottom + 18} textAnchor="middle" fontSize="11" fill="var(--ink-3)">
              {xFormat(t)}
            </text>
          </g>
        ))}
        <line x1={inner.left} x2={inner.right} y1={inner.bottom} y2={inner.bottom} stroke="var(--rule-strong)" />
        <text
          x={(inner.left + inner.right) / 2}
          y={height - 8}
          textAnchor="middle"
          fontSize="12"
          fill="var(--ink-2)"
          fontFamily="var(--font-sans)"
        >
          {xLabel}
        </text>
        <text
          transform={`translate(14 ${(inner.top + inner.bottom) / 2}) rotate(-90)`}
          textAnchor="middle"
          fontSize="12"
          fill="var(--ink-2)"
          fontFamily="var(--font-sans)"
        >
          {yLabel}
        </text>
      </g>
      {children({ x, y, width, height, inner })}
    </svg>
  );
}
