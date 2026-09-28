import type { Action, CaseRow, Category } from "./types";

export interface Filters {
  category: Category | "all";
  expected: Action | "all";
  provider: string; // a provider slug, or "all"
  unsafe: boolean;
  disagree: boolean;
  sort: string; // "id" | "category" | "expected" | a provider slug
  dir: "asc" | "desc";
}

export const DEFAULT_FILTERS: Filters = {
  category: "all",
  expected: "all",
  provider: "all",
  unsafe: false,
  disagree: false,
  sort: "id",
  dir: "asc",
};

const CATEGORIES = new Set(["STR", "MIS", "CON", "TMP", "TRK", "SMOKE"]);
const EXPECTED = new Set(["AUTO_PROCESS", "REQUEST_INFO", "HUMAN_REVIEW"]);

/** Filters from URL query params; unknown values fall back to the defaults. */
export function parseFilters(params: URLSearchParams): Filters {
  const category = params.get("category") ?? "all";
  const expected = params.get("expected") ?? "all";
  return {
    category: CATEGORIES.has(category) ? (category as Category) : "all",
    expected: EXPECTED.has(expected) ? (expected as Action) : "all",
    provider: params.get("provider") ?? "all",
    unsafe: params.get("unsafe") === "1",
    disagree: params.get("disagree") === "1",
    sort: params.get("sort") ?? "id",
    dir: params.get("dir") === "desc" ? "desc" : "asc",
  };
}

/** Only the filters that differ from the defaults, so a clean URL means no filter. */
export function filtersToParams(f: Filters): URLSearchParams {
  const p = new URLSearchParams();
  if (f.category !== "all") p.set("category", f.category);
  if (f.expected !== "all") p.set("expected", f.expected);
  if (f.provider !== "all") p.set("provider", f.provider);
  if (f.unsafe) p.set("unsafe", "1");
  if (f.disagree) p.set("disagree", "1");
  if (f.sort !== "id") p.set("sort", f.sort);
  if (f.dir !== "asc") p.set("dir", f.dir);
  return p;
}

/** True when the model providers that ran this case chose different actions. */
export function providersDisagree(row: CaseRow): boolean {
  return new Set(Object.values(row.results).map((r) => r.action)).size > 1;
}

const VERDICT_RANK = { UNSAFE: 0, "wrong-safe": 1, correct: 2 } as const;
const ACTION_RANK = { AUTO_PROCESS: 0, REQUEST_INFO: 1, HUMAN_REVIEW: 2 } as const;
const CATEGORY_RANK = { STR: 0, MIS: 1, CON: 2, TMP: 3, TRK: 4, SMOKE: 5 } as const;

export function applyFilters(rows: CaseRow[], f: Filters): CaseRow[] {
  const kept = rows.filter((row) => {
    if (f.category !== "all" && row.category !== f.category) return false;
    if (f.expected !== "all" && row.expected !== f.expected) return false;
    const results =
      f.provider === "all" ? Object.values(row.results) : row.results[f.provider] ? [row.results[f.provider]] : [];
    if (f.provider !== "all" && results.length === 0) return false;
    if (f.unsafe && !results.some((r) => r.verdict === "UNSAFE")) return false;
    if (f.disagree && !providersDisagree(row)) return false;
    return true;
  });
  const key = (row: CaseRow): [number, string] => {
    if (f.sort === "category") return [CATEGORY_RANK[row.category], row.id];
    if (f.sort === "expected") return [ACTION_RANK[row.expected], row.id];
    if (f.sort !== "id") {
      const r = row.results[f.sort];
      return [r ? VERDICT_RANK[r.verdict] : 3, row.id];
    }
    return [0, row.id];
  };
  const sign = f.dir === "asc" ? 1 : -1;
  return [...kept].sort((a, b) => {
    const [ka, ia] = key(a);
    const [kb, ib] = key(b);
    return ka !== kb ? (ka - kb) * sign : ia.localeCompare(ib) * sign;
  });
}
