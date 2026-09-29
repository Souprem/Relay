import type { Metadata } from "next";

import { CompareView } from "@/components/questions/CompareView";
import { getQuestions } from "@/lib/data";
import { comparePair } from "@/lib/questions";

export const dynamicParams = false;

export function generateStaticParams() {
  return getQuestions().compare.map((pair) => ({ pair }));
}

export async function generateMetadata({ params }: { params: Promise<{ pair: string }> }): Promise<Metadata> {
  const { pair } = await params;
  const [a, b] = comparePair(decodeURIComponent(pair));
  return { title: `${a} → ${b}` };
}

export default async function ComparePage({ params }: { params: Promise<{ pair: string }> }) {
  const { pair } = await params;
  const data = getQuestions();
  const [a, b] = comparePair(decodeURIComponent(pair));
  const versions = data.sets.map((s) => s.version);
  const before = data.sets.find((s) => s.version === a);
  const after = data.sets.find((s) => s.version === b);
  if (!before || !after) throw new Error(`unknown comparison ${pair}`);
  // Every step between the two sets, in order: one note for adjacent sets, both for v0.1 -> v0.3.
  const transitions = data.transitions.filter(
    (t) => versions.indexOf(t.from) >= versions.indexOf(a) && versions.indexOf(t.to) <= versions.indexOf(b),
  );
  return <CompareView before={before} after={after} transitions={transitions} />;
}
