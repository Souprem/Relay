import { linear, type Scale } from "@/lib/scale";

export interface Frame {
  x: Scale;
  y: Scale;
  width: number;
  height: number;
  inner: { left: number; top: number; right: number; bottom: number };
  /** True in the phone variant (the viewBox is NARROW_WIDTH wide). */
  narrow: boolean;
  /** A font size for this variant: one step larger on a phone so it renders at 11px or more. */
  fs: (size: number) => number;
}

const MARGIN = { top: 16, right: 24, bottom: 48, left: 56 };

/** The phone viewBox width: about the rendered width on a 360–390px screen, so 12-unit text
 * renders at 11px or more. */
export const NARROW_WIDTH = 340;

/**
 * An SVG plot area with light gridlines, labelled ticks and real axis titles. Children draw the
 * marks with the frame's scales. The SVG scales to its container, so text stays legible only while
 * the viewBox is close to the rendered width. A chart wider than a phone is drawn more than once:
 * a NARROW_WIDTH variant below md, an optional `midWidth` variant from md to xl, and `width` above
 * that (above md when there is no midWidth). Only one is displayed at a time.
 */
export function ChartFrame(props: ChartProps) {
  const { width = 640 } = props;
  if (width <= NARROW_WIDTH * 1.1) return <ChartSvg {...props} width={width} narrow={false} />;
  return (
    <div>
      <ChartSvg {...props} width={NARROW_WIDTH} narrow className="md:hidden" />
      {props.midWidth ? (
        <>
          <ChartSvg {...props} width={props.midWidth} narrow={false} className="hidden md:block xl:hidden" />
          <ChartSvg {...props} width={width} narrow={false} className="hidden xl:block" />
        </>
      ) : (
        <ChartSvg {...props} width={width} narrow={false} className="hidden md:block" />
      )}
    </div>
  );
}

interface ChartProps {
  title: string;
  /** A longer summary for screen readers, read after the title. */
  description?: string;
  width?: number;
  midWidth?: number;
  height?: number;
  marginRight?: number;
  /** Room above the plot area, for annotations drawn over it (wide and mid variants). */
  marginTop?: number;
  /** The same for the phone variant; defaults to marginTop. */
  marginTopNarrow?: number;
  xDomain: [number, number];
  yDomain: [number, number];
  xTicks: number[];
  yTicks: number[];
  xFormat: (v: number) => string;
  yFormat: (v: number) => string;
  xLabel: string;
  /** A shorter x-axis title for the phone variant. */
  xLabelNarrow?: string;
  yLabel: string;
  children: (frame: Frame) => React.ReactNode;
}

function ChartSvg({
  title,
  description,
  width,
  narrow,
  className = "",
  height = 320,
  marginRight = MARGIN.right,
  marginTop = MARGIN.top,
  marginTopNarrow,
  xDomain,
  yDomain,
  xTicks,
  yTicks,
  xFormat,
  yFormat,
  xLabel,
  xLabelNarrow,
  yLabel,
  children,
}: Omit<ChartProps, "width"> & { width: number; narrow: boolean; className?: string }) {
  const fs = (size: number) => (narrow ? size + 1 : size);
  const inner = {
    left: MARGIN.left,
    top: narrow ? (marginTopNarrow ?? marginTop) : marginTop,
    right: width - marginRight,
    bottom: height - MARGIN.bottom,
  };
  const x = linear(xDomain, [inner.left, inner.right]);
  const y = linear(yDomain, [inner.bottom, inner.top]);
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={description ? `${title}. ${description}` : title}
      data-variant={narrow ? "narrow" : "wide"}
      className={`block h-auto w-full overflow-visible font-mono text-ink ${className}`}
    >
      <title>{title}</title>
      {description ? <desc>{description}</desc> : null}
      <g aria-hidden="true">
        {yTicks.map((t) => (
          <g key={`y${t}`}>
            <line x1={inner.left} x2={inner.right} y1={y(t)} y2={y(t)} stroke="var(--rule)" />
            <text x={inner.left - 8} y={y(t)} dy="0.32em" textAnchor="end" fontSize={fs(11)} fill="var(--ink-3)">
              {yFormat(t)}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <g key={`x${t}`}>
            <line x1={x(t)} x2={x(t)} y1={inner.bottom} y2={inner.bottom + 4} stroke="var(--rule-strong)" />
            <text x={x(t)} y={inner.bottom + 18} textAnchor="middle" fontSize={fs(11)} fill="var(--ink-3)">
              {xFormat(t)}
            </text>
          </g>
        ))}
        <line x1={inner.left} x2={inner.right} y1={inner.bottom} y2={inner.bottom} stroke="var(--rule-strong)" />
        <text
          x={(inner.left + inner.right) / 2}
          y={height - 8}
          textAnchor="middle"
          fontSize={fs(12)}
          fill="var(--ink-2)"
          fontFamily="var(--font-sans)"
        >
          {narrow && xLabelNarrow ? xLabelNarrow : xLabel}
        </text>
        <text
          transform={`translate(14 ${(inner.top + inner.bottom) / 2}) rotate(-90)`}
          textAnchor="middle"
          fontSize={fs(12)}
          fill="var(--ink-2)"
          fontFamily="var(--font-sans)"
        >
          {yLabel}
        </text>
      </g>
      {children({ x, y, width, height, inner, narrow, fs })}
    </svg>
  );
}
