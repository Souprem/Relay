import fs from "node:fs";
import path from "node:path";

import { pct, ppText, prob, pyFixed, rateText, roundInt, threshold } from "../format";
import type { Rate } from "../types";

// I-1: README.md and docs/RESULTS.md were written by Python, which rounds an exact tie to even.
describe("Python-identical number formatting", () => {
  it("rounds ties to even the way f\"{x:.1%}\" does", () => {
    expect(pct(297 / 400)).toBe("74.2%"); // RESULTS.md aware shift; toFixed gives 74.3%
    expect(pct(13 / 400)).toBe("3.2%"); // toFixed gives 3.3%
    expect(pct(29 / 400)).toBe("7.2%");
    expect(pct(257 / 400)).toBe("64.2%");
    expect(pct(261 / 400)).toBe("65.2%");
    expect(pct(373 / 400)).toBe("93.2%");
    expect(pct(3 / 16)).toBe("18.8%"); // not a tie in binary: rounds up, as Python does
    expect(pct(0)).toBe("0.0%");
    expect(pct(1)).toBe("100.0%");
    expect(pct(null)).toBe("—");
  });

  it("rounds the parallelism token mean like Python's round()", () => {
    expect(roundInt(982.5)).toBe("982");
    expect(roundInt(1525.5)).toBe("1526");
    expect(roundInt(178.45645896159112)).toBe("178");
    expect(roundInt(229.77108391933143)).toBe("230");
  });

  it("matches Python on exact binary ties at other precisions", () => {
    expect(prob(0.0625)).toBe("0.062");
    expect(prob(0.1875)).toBe("0.188");
    expect(threshold(0.125)).toBe("0.12");
    expect(threshold(0.375)).toBe("0.38");
    expect(pyFixed(0.5, 0)).toBe("0");
    expect(pyFixed(1.5, 0)).toBe("2");
    expect(pyFixed(9.95, 1)).toBe("9.9"); // 9.95 is 9.949999... in binary
    expect(pyFixed(9.96, 1)).toBe("10.0");
    expect(pyFixed(99.96, 1)).toBe("100.0");
    expect(pyFixed(-0.25, 1)).toBe("-0.2");
    expect(pyFixed(0.000041265, 6)).toBe("0.000041");
  });

  it("prints percentage-point changes as the regression gate does", () => {
    expect(ppText(0.735, 0.7425)).toBe("+0.8 pp"); // Python: f"{(0.7425 - 0.735) * 100:+.1f}"
    expect(ppText(16 / 400, 13 / 400)).toBe("−0.8 pp");
    expect(ppText(null, 0.5)).toBe("—");
  });

  it("renders rates from the exporter's Python display strings", () => {
    const r: Rate = {
      count: 297,
      n: 400,
      rate: 0.7425,
      ci95: { low: 0.69, high: 0.79 },
      pct: "74.2%",
      text: "297/400 (74.2%)",
      ci_text: "69.0–79.0%",
      ci_high_pct: "79.0%",
    };
    expect(rateText(r)).toBe("297/400 (74.2%)");
  });

  // Every rate in the exported data: the Python display string agrees with pct() on the same
  // float, so the two display paths can never disagree. Runs when public/data exists.
  const DATA = path.resolve(__dirname, "../../../public/data");
  it.runIf(fs.existsSync(DATA))("agrees with every exported Python display string", () => {
    const seen: string[] = [];
    const walk = (v: unknown) => {
      if (Array.isArray(v)) return v.forEach(walk);
      if (v && typeof v === "object") {
        const o = v as Record<string, unknown>;
        if ("count" in o && "n" in o && "rate" in o && "ci95" in o && typeof o.rate === "number") {
          expect(pct(o.rate)).toBe(o.pct);
          seen.push(o.pct as string);
        }
        Object.values(o).forEach(walk);
      }
    };
    const files = (dir: string): string[] =>
      fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
        e.isDirectory() ? files(path.join(dir, e.name)) : e.name.endsWith(".json") ? [path.join(dir, e.name)] : [],
      );
    for (const f of files(DATA)) walk(JSON.parse(fs.readFileSync(f, "utf-8")));
    expect(seen.length).toBeGreaterThan(100);
  });
});
