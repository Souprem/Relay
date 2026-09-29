"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const strip = (p: string) => p.replace(/\/+$/, "") || "/";

/** The sub-navigation shared by every /questions/ page. */
export function QuestionsNav({
  pages,
  compares,
}: {
  pages: { href: string; label: string }[];
  compares: { href: string; label: string }[];
}) {
  const pathname = strip(usePathname() ?? "/");
  const item = (l: { href: string; label: string }) => {
    const active = strip(l.href) === pathname;
    return (
      <li key={l.href}>
        <Link
          href={l.href}
          aria-current={active ? "page" : undefined}
          className={`font-mono text-sm ${active ? "text-ink underline" : "text-ink-2 hover:text-ink"}`}
        >
          {l.label}
        </Link>
      </li>
    );
  };
  return (
    <nav aria-label="Question sets" className="mb-4 grid gap-1 border-b border-rule pb-2 md:grid-cols-[auto_minmax(0,1fr)] md:gap-x-4">
      <ul className="flex flex-wrap gap-x-2 gap-y-0.5">{pages.map(item)}</ul>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 md:justify-end">
        <span className="text-label font-semibold uppercase text-ink-3">Compare</span>
        <ul className="flex flex-wrap gap-x-2 gap-y-0.5">{compares.map(item)}</ul>
      </div>
    </nav>
  );
}
