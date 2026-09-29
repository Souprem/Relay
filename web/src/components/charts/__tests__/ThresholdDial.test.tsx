import { render } from "@testing-library/react";

import { linear } from "@/lib/scale";
import type { FrontierPoint } from "@/lib/types";

import type { Frame } from "../ChartFrame";
import { ThresholdDial } from "../ThresholdDial";
import { countAxis, dialSummary, firstUnsafe, layoutDial, MONO_EM } from "../dialLayout";

/** 50 thresholds 0.50..0.99 with the given (auto, unsafe) per threshold. */
function points(counts: (t: number) => [number, number], n = 100): FrontierPoint[] {
  return Array.from({ length: 50 }, (_, i) => {
    const t = Number((0.5 + i / 100).toFixed(2));
    const [auto, unsafe] = counts(t);
    return {
      auto_threshold: t,
      n,
      auto,
      request_info: 0,
      human_review: n - auto,
      unsafe,
      correct: n - unsafe,
      automation_rate: auto / n,
      uar: auto ? unsafe / auto : null,
      human_review_rate: (n - auto) / n,
      correct_action_rate: (n - unsafe) / n,
    };
  });
}

// Like gold Jev q-v0.2: automation falls off above 0.9; one unsafe from 0.93, two from 0.81.
const GOLD = points((t) => [t >= 0.99 ? 0 : t > 0.93 ? 20 : t > 0.81 ? 29 : 33, t > 0.93 ? 0 : t > 0.81 ? 1 : 2]);

function frame(ps: FrontierPoint[], narrow: boolean, width = narrow ? 340 : 1104): Frame {
  const inner = { left: 56, top: narrow ? 70 : 54, right: width - 24, bottom: 340 - 48 };
  const axis = countAxis(Math.max(...ps.map((p) => p.auto)));
  return {
    x: linear([-0.5, ps.length - 0.5], [inner.left, inner.right]),
    y: linear([0, axis.max], [inner.bottom, inner.top]),
    width,
    height: 340,
    inner,
    narrow,
    fs: (s) => (narrow ? s + 1 : s),
  };
}

function inside(label: { x0: number; x1: number; ys: number[]; fontSize: number }, f: Frame) {
  expect(label.x0).toBeGreaterThanOrEqual(0);
  expect(label.x1).toBeLessThanOrEqual(f.width);
  expect(Math.min(...label.ys) - label.fontSize).toBeGreaterThanOrEqual(0);
}

describe("layoutDial", () => {
  it("orders the columns strict (high threshold) to loose, left to right", () => {
    const f = frame(GOLD, false);
    const { bars } = layoutDial(GOLD, 0.89, "chosen on gen-v0.2-dev", f);
    expect(bars.map((b) => b.point.auto_threshold)).toEqual([...GOLD].map((p) => p.auto_threshold).reverse());
    for (let i = 1; i < bars.length; i++) expect(bars[i].x).toBeGreaterThan(bars[i - 1].x);
  });

  it("draws bar heights and the unsafe segment in proportion to the counts", () => {
    const f = frame(GOLD, false);
    const { bars } = layoutDial(GOLD, 0.89, "chosen on gen-v0.2-dev", f);
    const unit = f.y(0) - f.y(1);
    for (const b of bars) {
      expect(b.bottom - b.top).toBeCloseTo(b.point.auto * unit);
      expect(b.safeTop - b.top).toBeCloseTo(b.point.unsafe * unit);
    }
    const loose = bars[bars.length - 1];
    expect((loose.safeTop - loose.top) / (loose.bottom - loose.top)).toBeCloseTo(2 / 33);
  });

  it("uses a tight count axis", () => {
    expect(countAxis(33)).toEqual({ max: 40, ticks: [0, 10, 20, 30, 40] });
    expect(countAxis(245).max).toBe(250);
    expect(countAxis(0).max).toBe(1);
  });

  it("labels the operating point and the first unsafe threshold", () => {
    const f = frame(GOLD, false);
    const layout = layoutDial(GOLD, 0.89, "chosen on gen-v0.2-dev", f);
    const text = (l: typeof layout.operating) => l?.lines.map((line) => line.map((s) => s.text).join("")).join(" ");
    expect(text(layout.operating)).toBe("chosen on gen-v0.2-dev: 0.89 · 29 auto · 1 unsafe");
    expect(text(layout.firstUnsafe)).toMatch(/first unsafe.*0\.93/);
    expect(firstUnsafe(GOLD)?.auto_threshold).toBe(0.93);
    // The first-unsafe label stays clear of the operating point's leader.
    const opX = layout.operating!.leader!.x;
    expect(opX < layout.firstUnsafe!.x0 || opX > layout.firstUnsafe!.x1).toBe(true);
    expect(layout.ticks.find((t) => t.operating)?.text).toBe("0.89");
    expect(layout.ticks.some((t) => t.text === "0.90")).toBe(false);
  });

  it.each([
    [0.99, false],
    [0.5, false],
    [0.99, true],
    [0.5, true],
    [0.81, true],
  ])("keeps the operating-point label inside the chart at %s (narrow %s)", (op, narrow) => {
    const flat = points(() => [134, 0], 1000);
    for (const ps of [GOLD, flat]) {
      const f = frame(ps, narrow);
      const label = layoutDial(ps, op, "chosen on gen-v0.2-dev", f).operating!;
      expect(label).not.toBeNull();
      inside(label, f);
      const w = Math.max(...label.lines.map((l) => l.reduce((n, s) => n + s.text.length, 0))) * label.fontSize * MONO_EM;
      expect(label.x1 - label.x0).toBeCloseTo(w);
      // A label pinned over its column starts its leader below the text, never through it.
      if (label.leader!.x >= label.x0 && label.leader!.x <= label.x1) {
        expect(label.leader!.y1).toBeGreaterThan(Math.max(...label.ys));
      }
    }
  });

  it("notes when no threshold is unsafe, and skips a first-unsafe label on the operating column", () => {
    const safe = points((t) => [t > 0.95 ? 10 : 245, 0], 1000);
    const f = frame(safe, false);
    const layout = layoutDial(safe, 0.81, "chosen on gen-v0.3-dev", f);
    expect(layout.firstUnsafe).toBeNull();
    expect(layout.note?.lines[0][0].text).toBe("no unsafe automation at any threshold");
    inside(layout.note!, f);
    const rules = points(() => [20, 6]);
    expect(layoutDial(rules, 0.99, "chosen on gen-v0.2-dev", frame(rules, false)).firstUnsafe).toBeNull();
  });
});

describe("dialSummary", () => {
  it("summarises the operating point and where unsafe automations begin", () => {
    expect(dialSummary(GOLD, 0.89, "chosen on gen-v0.2-dev")).toBe(
      "Operating point 0.89 (chosen on gen-v0.2-dev): 29 of 100 cases auto-processed, 1 unsafe. " +
        "The first unsafe automation appears at 0.93 (29 auto-processed, 1 unsafe); stricter thresholds have none.",
    );
    expect(dialSummary(points(() => [20, 6]), 0.99, "x")).toMatch(/at every threshold, from 0\.99/);
    expect(dialSummary(points(() => [5, 0]), 0.99, "x")).toMatch(/No threshold produces an unsafe automation/);
  });
});

describe("ThresholdDial", () => {
  it("renders an accessible chart per variant with the operating-point label", () => {
    const { container } = render(
      <ThresholdDial points={GOLD} operating={0.89} source="chosen on gen-v0.2-dev" label="Jev q-v0.2 on gold-v0.1" />,
    );
    const svgs = [...container.querySelectorAll("svg[data-variant]")];
    expect(svgs).toHaveLength(3);
    for (const svg of svgs) {
      expect(svg.getAttribute("role")).toBe("img");
      expect(svg.querySelector("desc")?.textContent).toMatch(/first unsafe automation appears at 0\.93/);
      expect(svg.getAttribute("aria-label")).toMatch(/Operating point 0\.89/);
      expect(svg.textContent).toContain("29 auto");
      expect(svg.querySelectorAll('[data-part="unsafe"]').length).toBe(GOLD.filter((p) => p.unsafe > 0).length);
      expect(svg.querySelector("text")).not.toBeNull();
    }
    expect(container.textContent).toContain("Every threshold");
    expect(container.textContent).not.toMatch(/ceiling/);
  });
});

describe("layoutDial on a phone", () => {
  it("shortens the first-unsafe label rather than dropping it when space is tight", () => {
    const f = frame(GOLD, true);
    const layout = layoutDial(GOLD, 0.89, "chosen on gen-v0.2-dev", f);
    expect(layout.firstUnsafe?.lines[0][0].text).toMatch(/unsafe.*0\.93/);
    inside(layout.firstUnsafe!, f);
    const opX = layout.operating!.leader!.x;
    expect(opX < layout.firstUnsafe!.x0 || opX > layout.firstUnsafe!.x1).toBe(true);
  });
});
