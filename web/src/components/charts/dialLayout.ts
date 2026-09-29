// Layout for the threshold dial (ThresholdDial.tsx): pure geometry over exported frontier counts,
// kept apart from the SVG so it can be unit-tested. No metric is computed here; every number drawn
// is a count the exporter wrote (relay/site/core.py).
import { threshold } from "@/lib/format";
import { niceTicks } from "@/lib/scale";
import type { FrontierPoint } from "@/lib/types";

import type { Frame } from "./ChartFrame";

/** Plex Mono's advance width in em, for estimating label widths. */
export const MONO_EM = 0.6;
/** Keep every label this far inside the SVG edge. */
const EDGE = 4;

export interface DialBar {
  point: FrontierPoint;
  x: number;
  width: number;
  /** y of the bar top (all automations) and of the boundary between the safe and unsafe parts. */
  top: number;
  safeTop: number;
  bottom: number;
  operating: boolean;
}

export interface Segment {
  text: string;
  tone: "ink" | "unsafe";
}

export interface DialLabel {
  lines: Segment[][];
  /** The anchor x and each line's baseline. */
  x: number;
  ys: number[];
  anchor: "start" | "end";
  fontSize: number;
  /** Horizontal extent, for collision checks and tests. */
  x0: number;
  x1: number;
  /** A vertical leader from the label down to its column, when it has one. */
  leader: { x: number; y1: number; y2: number } | null;
}

export interface DialTick {
  x: number;
  text: string;
  operating: boolean;
}

export interface DialLayout {
  bars: DialBar[];
  ticks: DialTick[];
  operating: DialLabel | null;
  firstUnsafe: DialLabel | null;
  /** "no unsafe automation at any threshold", when that is so. */
  note: DialLabel | null;
}

/** Thresholds strict (high) to loose (low): the dial's left-to-right order. */
export function strictToLoose(points: FrontierPoint[]): FrontierPoint[] {
  return [...points].sort((a, b) => b.auto_threshold - a.auto_threshold);
}

/** A tight count axis: nice ticks from 0 whose last tick is the first at or above `max`. */
export function countAxis(max: number, count = 5): { max: number; ticks: number[] } {
  if (max <= 0) return { max: 1, ticks: [0, 1] };
  const base = niceTicks(0, max, count);
  const step = base.length > 1 ? base[1] - base[0] : max;
  const top = Math.ceil(max / step - 1e-9) * step;
  const ticks: number[] = [];
  for (let v = 0; v <= top + step * 1e-9; v += step) ticks.push(Number(v.toFixed(10)));
  return { max: top, ticks };
}

/** The strictest threshold with at least one unsafe automation (unsafe counts only grow as the
 * threshold loosens), or null when no threshold has one. */
export function firstUnsafe(points: FrontierPoint[]): FrontierPoint | null {
  return strictToLoose(points).find((p) => p.unsafe > 0) ?? null;
}

export function pointAt(points: FrontierPoint[], operating: number): FrontierPoint | null {
  return points.find((p) => Math.abs(p.auto_threshold - operating) < 1e-9) ?? null;
}

/** The screen-reader summary: the operating point and where unsafe automations begin. */
export function dialSummary(points: FrontierPoint[], operating: number, source: string): string {
  const ordered = strictToLoose(points);
  const op = pointAt(points, operating);
  const parts: string[] = [];
  if (op) {
    parts.push(
      `Operating point ${threshold(op.auto_threshold)} (${source}): ${op.auto} of ${op.n} cases auto-processed, ${op.unsafe} unsafe.`,
    );
  }
  const first = firstUnsafe(points);
  if (!first) {
    parts.push("No threshold produces an unsafe automation.");
  } else if (first === ordered[0]) {
    parts.push(
      `Unsafe automations appear at every threshold, from ${threshold(first.auto_threshold)} (${first.auto} auto-processed, ${first.unsafe} unsafe).`,
    );
  } else {
    parts.push(
      `The first unsafe automation appears at ${threshold(first.auto_threshold)} (${first.auto} auto-processed, ${first.unsafe} unsafe); stricter thresholds have none.`,
    );
  }
  return parts.join(" ");
}

function textWidth(chars: number, fontSize: number): number {
  return chars * fontSize * MONO_EM;
}

function lineChars(line: Segment[]): number {
  return line.reduce((n, s) => n + s.text.length, 0);
}

/**
 * Place a label beside x on one side or the other, preferring `prefer`: inside the SVG edges and
 * clear of every x in `avoid` (other labels' leaders). Returns null when neither side fits.
 */
function beside(
  x: number,
  w: number,
  gap: number,
  prefer: "start" | "end",
  frame: Frame,
  avoid: number[],
): { x: number; anchor: "start" | "end"; x0: number; x1: number } | null {
  const sides: ("start" | "end")[] = prefer === "start" ? ["start", "end"] : ["end", "start"];
  for (const anchor of sides) {
    const ax = anchor === "start" ? x + gap : x - gap;
    const x0 = anchor === "start" ? ax : ax - w;
    const x1 = x0 + w;
    if (x0 < EDGE || x1 > frame.width - EDGE) continue;
    if (avoid.some((a) => a >= x0 - 4 && a <= x1 + 4)) continue;
    return { x: ax, anchor, x0, x1 };
  }
  return null;
}

/**
 * The dial's geometry. The frame's x domain is [-0.5, n - 0.5], one unit per column, column 0
 * the strictest threshold; its y domain is counts of cases. Annotations sit in two rows above the
 * plot (frame.inner.top is left free for them): the operating point in the upper row, the first
 * unsafe threshold (or the "none" note) in the lower one, each clear of the other's leader.
 */
export function layoutDial(
  points: FrontierPoint[],
  operating: number,
  source: string,
  frame: Frame,
): DialLayout {
  const { x, y, inner, narrow, fs } = frame;
  const ordered = strictToLoose(points);
  const step = ordered.length > 1 ? Math.abs(x(1) - x(0)) : inner.right - inner.left;
  const barWidth = Math.max(2, Math.min(14, step * (narrow ? 0.7 : 0.62)));
  const op = pointAt(points, operating);

  const bars: DialBar[] = ordered.map((p, i) => ({
    point: p,
    x: x(i),
    width: barWidth,
    top: y(p.auto),
    safeTop: y(p.auto - p.unsafe),
    bottom: y(0),
    operating: p === op,
  }));

  // ---- ticks: every 0.05 (0.10 on a phone) and the operating point, never crowding it
  const tickFs = fs(11);
  const tickW = textWidth(4, tickFs);
  const every = narrow ? 10 : 5;
  const opIndex = op ? ordered.indexOf(op) : -1;
  const opX = opIndex >= 0 ? x(opIndex) : null;
  const ticks: DialTick[] = [];
  ordered.forEach((p, i) => {
    const hundredths = Math.round(p.auto_threshold * 100);
    const isOp = i === opIndex;
    if (!isOp && hundredths % every !== 0) return;
    if (!isOp && opX !== null && Math.abs(x(i) - opX) < tickW + 6) return;
    ticks.push({ x: x(i), text: threshold(p.auto_threshold), operating: isOp });
  });

  // ---- rows above the plot
  const opFs = fs(12);
  const noteFs = fs(11);
  // Row A clears the top y tick label, which straddles inner.top.
  const rowA = inner.top - 14;
  const lineH = opFs + 4;

  let operatingLabel: DialLabel | null = null;
  if (op && opX !== null) {
    const tail: Segment[] = [
      { text: `${threshold(op.auto_threshold)} · ${op.auto} auto · `, tone: "ink" },
      { text: `${op.unsafe} unsafe`, tone: op.unsafe > 0 ? "unsafe" : "ink" },
    ];
    const lines: Segment[][] = narrow ? [[{ text: source, tone: "ink" }], tail] : [[{ text: `${source}: `, tone: "ink" }, ...tail]];
    const w = textWidth(Math.max(...lines.map(lineChars)), opFs);
    const last = rowA - (opFs + 6);
    const ys = lines.map((_, i) => last - (lines.length - 1 - i) * lineH);
    const placed =
      beside(opX, w, 6, "start", frame, []) ?? {
        // Wider than either side: pin it inside the edge nearer the column.
        ...(opX < frame.width / 2
          ? { x: EDGE, anchor: "start" as const, x0: EDGE, x1: EDGE + w }
          : { x: frame.width - EDGE, anchor: "end" as const, x0: frame.width - EDGE - w, x1: frame.width - EDGE }),
      };
    const bar = bars[opIndex];
    const covers = opX >= placed.x0 - 2 && opX <= placed.x1 + 2;
    operatingLabel = {
      lines,
      x: placed.x,
      ys,
      anchor: placed.anchor,
      fontSize: opFs,
      x0: placed.x0,
      x1: placed.x1,
      // Beside the column the leader runs up alongside the text; pinned over it, the leader starts
      // below the last line so it never strikes through the label.
      leader: {
        x: opX,
        y1: covers ? ys[ys.length - 1] + 5 : ys[0] - opFs * 0.75,
        y2: bar.top - 3,
      },
    };
  }

  const avoid = opX !== null ? [opX] : [];
  let firstLabel: DialLabel | null = null;
  let note: DialLabel | null = null;
  const first = firstUnsafe(points);
  if (first && first !== op) {
    const i = ordered.indexOf(first);
    const t = threshold(first.auto_threshold);
    // The longest wording that fits beside the column; the red leader carries the rest.
    const texts = [
      ...(narrow ? [] : [`first unsafe automation at ${t}`]),
      `first unsafe ${t}`,
      `unsafe from ${t}`,
      `unsafe ${t}`,
    ];
    // Extend away from the operating point, so its leader stays clear.
    const prefer = opX !== null && opX > x(i) ? "end" : "start";
    let text = texts[0];
    let placed: ReturnType<typeof beside> = null;
    for (const candidate of texts) {
      placed = beside(x(i), textWidth(candidate.length, noteFs), 5, prefer, frame, avoid);
      text = candidate;
      if (placed) break;
    }
    if (placed) {
      firstLabel = {
        lines: [[{ text, tone: "unsafe" }]],
        x: placed.x,
        ys: [rowA],
        anchor: placed.anchor,
        fontSize: noteFs,
        x0: placed.x0,
        x1: placed.x1,
        leader: { x: x(i), y1: rowA - noteFs * 0.75, y2: bars[i].top - 3 },
      };
    }
  } else if (!first) {
    const text = narrow ? "no unsafe at any threshold" : "no unsafe automation at any threshold";
    const w = textWidth(text.length, noteFs);
    const spots = [
      { x: inner.right, anchor: "end" as const, x0: inner.right - w, x1: inner.right },
      { x: inner.left, anchor: "start" as const, x0: inner.left, x1: inner.left + w },
    ];
    const spot = spots.find(
      (s) => s.x0 >= EDGE && s.x1 <= frame.width - EDGE && !avoid.some((a) => a >= s.x0 - 4 && a <= s.x1 + 4),
    );
    if (spot) {
      note = { lines: [[{ text, tone: "ink" }]], ys: [rowA], fontSize: noteFs, leader: null, ...spot };
    }
  }

  return { bars, ticks, operating: operatingLabel, firstUnsafe: firstLabel, note };
}
