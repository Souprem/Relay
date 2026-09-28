import type { Metadata } from "next";
import Link from "next/link";

import { CaseFacts } from "@/components/cases/CaseFacts";
import { DiffPanel } from "@/components/cases/DiffPanel";
import { ProviderPanel } from "@/components/cases/ProviderPanel";
import { getCase, getCases } from "@/lib/data";

export const dynamicParams = false;

export function generateStaticParams() {
  return getCases().cases.map((c) => ({ id: c.id }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  return { title: id };
}

export default async function CasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const detail = getCase(id);
  const categories = getCases().categories;
  return (
    <>
      <nav aria-label="Breadcrumb" className="text-sm text-ink-2">
        <Link href="/cases/" className="underline hover:text-ink">
          Cases
        </Link>
        <span aria-hidden="true"> / </span>
        <span className="font-mono">{detail.id}</span>
      </nav>
      <header className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <h1 className="font-mono text-xl font-medium text-ink">{detail.id}</h1>
        <p className="text-md text-ink-2">
          {categories[detail.category]} · {detail.dataset}
        </p>
      </header>

      <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <section aria-label="Case inputs" className="min-w-0">
          <h2 className="sr-only">Case inputs</h2>
          <CaseFacts detail={detail} />
        </section>
        <section aria-label="Decisions by provider" className="min-w-0">
          <h2 className="sr-only">Decisions by provider</h2>
          <ProviderPanel detail={detail} />
        </section>
      </div>

      {detail.diffs.length ? (
        <section aria-labelledby="changed" className="mt-6">
          <h2 id="changed" className="text-label font-semibold uppercase text-ink-2">
            What changed
          </h2>
          <div className="mt-2 grid gap-4">
            {detail.diffs.map((d) => (
              <DiffPanel key={`${d.title}-${d.candidate_label}`} diff={d} />
            ))}
          </div>
        </section>
      ) : null}
    </>
  );
}
