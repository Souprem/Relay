import type { Metadata } from "next";

import { CasesTable } from "@/components/cases/CasesTable";
import { VerdictLegend } from "@/components/cases/VerdictLegend";
import { PageHeader } from "@/components/ui/Section";
import { getCases } from "@/lib/data";

export const metadata: Metadata = { title: "Cases" };

export default function CasesPage() {
  const data = getCases();
  const gold = data.cases.filter((c) => c.dataset === "gold-v0.1").length;
  const smoke = data.cases.length - gold;
  return (
    <>
      <PageHeader eyebrow="Cases" title={`${data.cases.length} cases, every provider's action on each`}>
        <p>
          {gold} gold cases in five categories and {smoke} smoke cases. Each provider is shown at its
          operating point. Open a case to see the documents, the five judgments and the gate that
          decided.
        </p>
      </PageHeader>
      <div className="mt-4">
        <VerdictLegend />
      </div>
      <div className="mt-3">
        <CasesTable data={data} />
      </div>
    </>
  );
}
