import { applyFilters, DEFAULT_FILTERS, filtersToParams, parseFilters, providersDisagree } from "../caseFilters";
import type { CaseRow } from "../types";

const ROWS: CaseRow[] = [
  {
    id: "GOLD-TMP-17",
    dataset: "gold-v0.1",
    category: "TMP",
    expected: "HUMAN_REVIEW",
    has_diff: true,
    results: {
      "jev-q-v0.2": { action: "AUTO_PROCESS", verdict: "UNSAFE" },
      claude: { action: "AUTO_PROCESS", verdict: "UNSAFE" },
      rules: { action: "HUMAN_REVIEW", verdict: "correct" },
    },
  },
  {
    id: "GOLD-STR-01",
    dataset: "gold-v0.1",
    category: "STR",
    expected: "AUTO_PROCESS",
    has_diff: false,
    results: {
      "jev-q-v0.2": { action: "AUTO_PROCESS", verdict: "correct" },
      claude: { action: "AUTO_PROCESS", verdict: "correct" },
      rules: { action: "AUTO_PROCESS", verdict: "correct" },
    },
  },
  {
    id: "AUTO-01",
    dataset: "smoke-v0.1",
    category: "SMOKE",
    expected: "AUTO_PROCESS",
    has_diff: false,
    results: { "jev-q-v0.1": { action: "AUTO_PROCESS", verdict: "correct" } },
  },
];

describe("case filters", () => {
  it("round-trips through the URL and drops defaults", () => {
    const f = { ...DEFAULT_FILTERS, category: "TMP" as const, unsafe: true, provider: "claude" };
    const params = filtersToParams(f);
    expect(params.toString()).toBe("category=TMP&provider=claude&unsafe=1");
    expect(parseFilters(params)).toEqual(f);
    expect(filtersToParams(DEFAULT_FILTERS).toString()).toBe("");
    expect(parseFilters(new URLSearchParams("category=nope")).category).toBe("all");
  });

  it("filters by unsafe for one provider or any provider", () => {
    expect(applyFilters(ROWS, { ...DEFAULT_FILTERS, unsafe: true }).map((r) => r.id)).toEqual(["GOLD-TMP-17"]);
    expect(applyFilters(ROWS, { ...DEFAULT_FILTERS, unsafe: true, provider: "rules" })).toEqual([]);
  });

  it("drops cases the chosen provider did not run", () => {
    expect(applyFilters(ROWS, { ...DEFAULT_FILTERS, provider: "jev-q-v0.1" }).map((r) => r.id)).toEqual(["AUTO-01"]);
  });

  it("finds cases where providers chose different actions", () => {
    expect(providersDisagree(ROWS[0])).toBe(true);
    expect(providersDisagree(ROWS[1])).toBe(false);
    expect(applyFilters(ROWS, { ...DEFAULT_FILTERS, disagree: true }).map((r) => r.id)).toEqual(["GOLD-TMP-17"]);
  });

  it("sorts by a provider's verdict with unsafe first", () => {
    const sorted = applyFilters(ROWS, { ...DEFAULT_FILTERS, sort: "claude" });
    expect(sorted.map((r) => r.id)).toEqual(["GOLD-TMP-17", "GOLD-STR-01", "AUTO-01"]);
  });
});
