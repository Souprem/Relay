import Link from "next/link";

import { threshold } from "@/lib/format";
import type { Hero } from "@/lib/types";

/** The home page's three headline figures; every value and caption is an exported string. */
export function HeroFigures({ hero }: { hero: Hero }) {
  return (
    <div>
      <dl className="grid gap-x-4 gap-y-2 sm:grid-cols-3">
        {hero.figures.map((f) => (
          <div key={f.id} className="border-t border-ink pt-1 sm:pt-1.5">
            <dt className="sr-only">{f.label}</dt>
            <dd>
              <span className="num block text-xl text-ink sm:text-display">{f.value}</span>
              <span className="mt-0.5 block text-md text-ink-2" aria-hidden="true">
                {f.label}
              </span>
              <span className="num mt-0.5 block text-sm text-ink-3">{f.caption}</span>
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-sm text-ink-3">
        <Link href={`/evals/${hero.run_id}/`} className="text-ink-2 underline decoration-rule-strong hover:text-ink">
          {hero.label} @{threshold(hero.auto_process)}
        </Link>{" "}
        on <span className="font-mono">{hero.dataset}</span>, {hero.n} synthetic cases, run once.
      </p>
    </div>
  );
}
