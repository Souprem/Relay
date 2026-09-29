import { DECISION_LABELS, pct, pyFixed } from "@/lib/format";
import type { CalibrationReport } from "@/lib/types";

import { ChartData } from "./ChartData";
import { ChartFrame } from "./ChartFrame";

const LOW_BIN_N = 20; // relay/reporting.py: bins with fewer cases are marked low-sample

/**
 * Stated confidence against observed accuracy, one point per confidence bin. Points on the
 * diagonal are calibrated; below it, over-confident. Bins with fewer than 20 cases are hollow.
 */
export function ReliabilityDiagram({ decision, report }: { decision: string; report: CalibrationReport }) {
  const x0 = report.bins[0]?.lower ?? 0.5;
  const filled = report.bins.filter((b) => b.n > 0 && b.mean_confidence !== null && b.accuracy !== null);
  const label = DECISION_LABELS[decision] ?? decision;
  const maxN = Math.max(1, ...filled.map((b) => b.n));
  return (
    <figure>
      <figcaption className="mb-1">
        <span className="block text-base text-ink">{label}</span>
        <span className="num block text-sm text-ink-2">
          Brier {report.brier === null ? "—" : pyFixed(report.brier, 3)} · ECE{" "}
          {report.ece === null ? "—" : pyFixed(report.ece, 3)} · n {report.n}
        </span>
        {x0 === 0 ? (
          <span className="block text-label tracking-normal text-ink-3">
            x from 0: a multiple-choice answer&rsquo;s top confidence can fall below 0.5.
          </span>
        ) : null}
      </figcaption>
      <ChartFrame
        title={`Reliability of ${label}: accuracy against stated confidence`}
        width={320}
        height={280}
        xDomain={[x0, 1]}
        yDomain={[0, 1]}
        xTicks={x0 === 0 ? [0, 0.25, 0.5, 0.75, 1] : [0.5, 0.6, 0.7, 0.8, 0.9, 1]}
        yTicks={[0, 0.25, 0.5, 0.75, 1]}
        xFormat={(v) => pyFixed(v, x0 === 0 ? 2 : 1)}
        yFormat={(v) => pct(v, 0)}
        xLabel="Stated confidence"
        yLabel="Accuracy"
      >
        {({ x, y }) => (
          <g>
            <line x1={x(x0)} y1={y(x0)} x2={x(1)} y2={y(1)} stroke="var(--rule-strong)" strokeDasharray="3 3" />
            {filled.map((b) => {
              const r = 3 + 7 * Math.sqrt(b.n / maxN);
              const low = b.n < LOW_BIN_N;
              return (
                <g key={b.lower}>
                  <circle
                    cx={x(b.mean_confidence as number)}
                    cy={y(b.accuracy as number)}
                    r={r}
                    fill={low ? "var(--paper)" : "var(--ink-2)"}
                    fillOpacity={low ? 1 : 0.85}
                    stroke="var(--ink-2)"
                  />
                  <text
                    x={x(b.mean_confidence as number) - r - 3}
                    y={y(b.accuracy as number)}
                    dy="0.32em"
                    textAnchor="end"
                    fontSize="11"
                    fill="var(--ink-3)"
                  >
                    {b.n}
                  </text>
                </g>
              );
            })}
          </g>
        )}
      </ChartFrame>
      <ChartData
        summary="Bins"
        columns={["bin", "n", "mean confidence", "accuracy"]}
        rows={report.bins.map((b) => [
          `${pyFixed(b.lower, 1)}–${pyFixed(b.upper, 1)}`,
          b.n,
          b.mean_confidence === null ? "—" : pyFixed(b.mean_confidence, 3),
          pct(b.accuracy),
        ])}
      />
    </figure>
  );
}
