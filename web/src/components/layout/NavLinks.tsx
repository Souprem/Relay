"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/cases/", label: "Cases" },
  { href: "/evals/", label: "Evals" },
  { href: "/gates/", label: "Gates" },
  { href: "/experiments/", label: "Experiments" },
];

export function NavLinks() {
  const pathname = usePathname() ?? "/";
  return (
    <ul className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
      {LINKS.map((link) => {
        const active = pathname.startsWith(link.href.replace(/\/$/, ""));
        return (
          <li key={link.href}>
            <Link
              href={link.href}
              aria-current={active ? "page" : undefined}
              className={
                "border-b py-0.5 text-base transition-colors " +
                (active
                  ? "border-ink text-ink"
                  : "border-transparent text-ink-2 hover:border-rule-strong hover:text-ink")
              }
            >
              {link.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
