"use client";

import Link from "next/link";
import { useMemo } from "react";

import { ActionBadge } from "@/components/ui/ActionBadge";
import { ScrollHint } from "@/components/ui/Table";
import { VerdictCell } from "@/components/ui/Verdict";
import {
  applyFilters,
  DEFAULT_FILTERS,
  filtersToParams,
  parseFilters,
  type Filters,
} from "@/lib/caseFilters";
import { ACTIONS } from "@/lib/format";
import type { CasesIndex } from "@/lib/types";
import { useQueryString } from "@/lib/useQueryString";

const control =
  "h-4 border border-rule-strong bg-paper px-1 text-base text-ink hover:border-ink focus-visible:border-ink";

export function CasesTable({ data }: { data: CasesIndex }) {
  const [query, setQuery] = useQueryString();
  const providers = useMemo(() => {
    const seen = new Map<string, string>();
    for (const d of data.datasets) {
      for (const p of d.providers) {
        if (!seen.has(p.slug)) seen.set(p.slug, p.label);
      }
    }
    return [...seen.entries()].map(([slug, label]) => ({ slug, label }));
  }, [data]);
  const slugs = providers.map((p) => p.slug);
  const filters = parseFilters(new URLSearchParams(query), slugs);

  const rows = applyFilters(data.cases, filters);

  function update(change: Partial<Filters>) {
    // Select values go through the same validation as the URL (a value no select offers is dropped).
    const next = parseFilters(filtersToParams({ ...filters, ...change }), slugs);
    setQuery(filtersToParams(next).toString());
  }

  function sortBy(key: string) {
    update({ sort: key, dir: filters.sort === key && filters.dir === "asc" ? "desc" : "asc" });
  }

  function sortHeader(id: string, label: string, align: "left" | "center" = "left", extra = "") {
    const active = filters.sort === id;
    return (
      <th
        key={id}
        scope="col"
        aria-sort={active ? (filters.dir === "asc" ? "ascending" : "descending") : "none"}
        className={`border-b border-ink py-1 pr-2 align-bottom text-label font-semibold uppercase text-ink-2 ${
          align === "center" ? "text-center" : "text-left"
        } ${extra}`}
      >
        <button
          type="button"
          onClick={() => sortBy(id)}
          className={`hover:text-ink ${align === "center" ? "normal-case tracking-normal" : "uppercase"}`}
        >
          {label}
          <span aria-hidden="true" className="ml-0.5 font-mono">
            {active ? (filters.dir === "asc" ? "↑" : "↓") : ""}
          </span>
        </button>
      </th>
    );
  }

  return (
    <div>
      <form
        className="flex flex-wrap items-end gap-x-3 gap-y-2 border-y border-rule py-2"
        onSubmit={(e) => e.preventDefault()}
        aria-label="Filter cases"
      >
        <label className="grid gap-0.5">
          <span className="text-label font-semibold uppercase text-ink-2">Category</span>
          <select
            className={control}
            value={filters.category}
            onChange={(e) => update({ category: e.target.value as Filters["category"] })}
          >
            <option value="all">All</option>
            {Object.entries(data.categories).map(([id, label]) => (
              <option key={id} value={id}>
                {id} · {label}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-0.5">
          <span className="text-label font-semibold uppercase text-ink-2">Expected action</span>
          <select
            className={control}
            value={filters.expected}
            onChange={(e) => update({ expected: e.target.value as Filters["expected"] })}
          >
            <option value="all">All</option>
            {ACTIONS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-0.5">
          <span className="text-label font-semibold uppercase text-ink-2">Provider</span>
          <select className={control} value={filters.provider} onChange={(e) => update({ provider: e.target.value })}>
            <option value="all">Any provider</option>
            {providers.map((p) => (
              <option key={p.slug} value={p.slug}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex h-4 items-center gap-1 text-base text-ink">
          <input
            type="checkbox"
            className="size-2 accent-[var(--unsafe)]"
            checked={filters.unsafe}
            onChange={(e) => update({ unsafe: e.target.checked })}
          />
          Unsafe only
        </label>
        <label className="flex h-4 items-center gap-1 text-base text-ink">
          <input
            type="checkbox"
            className="size-2 accent-[var(--ink)]"
            checked={filters.disagree}
            onChange={(e) => update({ disagree: e.target.checked })}
          />
          Providers disagree
        </label>
        <p className="ml-auto self-center text-sm text-ink-2" aria-live="polite">
          <span className="num text-ink">{rows.length}</span> of {data.cases.length} cases
          {filtersToParams(filters).toString() ? (
            <>
              {" · "}
              <button type="button" className="underline hover:text-ink" onClick={() => update(DEFAULT_FILTERS)}>
                Clear filters
              </button>
            </>
          ) : null}
        </p>
      </form>

      <ScrollHint>Scroll sideways for every provider → (the case id stays put)</ScrollHint>
      <div className="relative -mx-3 overflow-x-auto md:mx-0">
        <table className="mt-1 w-full md:min-w-[48rem]">
          <thead>
            <tr>
              {sortHeader("id", "Case", "left", "sticky left-0 z-10 bg-paper pl-3 md:static md:pl-0")}
              {sortHeader("category", "Category", "left", "hidden md:table-cell")}
              {sortHeader("expected", "Expected")}
              {providers.map((p) => sortHeader(p.slug, p.label, "center"))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="group hover:bg-paper-2">
                <td className="sticky left-0 z-10 whitespace-nowrap border-b border-rule bg-paper py-0.5 pr-2 pl-3 group-hover:bg-paper-2 md:static md:bg-transparent md:pl-0">
                  <Link href={`/cases/${row.id}/`} className="font-mono text-sm text-ink underline decoration-rule-strong hover:decoration-ink">
                    {row.id}
                  </Link>
                  {row.has_diff ? (
                    <span className="ml-1 text-label tracking-normal text-ink-3" title="Has a replay diff">
                      diff
                    </span>
                  ) : null}
                </td>
                <td className="hidden border-b border-rule py-0.5 pr-2 text-sm text-ink-2 md:table-cell">{data.categories[row.category]}</td>
                <td className="border-b border-rule py-0.5 pr-2">
                  <ActionBadge action={row.expected} size="sm" />
                </td>
                {providers.map((p) => {
                  const r = row.results[p.slug];
                  return (
                    <td key={p.slug} className="border-b border-rule py-0.5 pr-2 text-center last:pr-3 md:last:pr-0">
                      {r ? (
                        <VerdictCell action={r.action} verdict={r.verdict} />
                      ) : (
                        <span className="text-ink-3">
                          <span aria-hidden="true">·</span>
                          <span className="sr-only">not run on this dataset</span>
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 ? (
          <p className="py-4 text-md text-ink-2">
            No case matches these filters.{" "}
            <button type="button" className="underline hover:text-ink" onClick={() => update(DEFAULT_FILTERS)}>
              Clear filters
            </button>
          </p>
        ) : null}
      </div>
    </div>
  );
}
