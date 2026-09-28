import type { Metadata } from "next";

import { EvalsView } from "@/components/evals/EvalsView";
import { getRun, getRuns } from "@/lib/data";

export const dynamicParams = false;

export function generateStaticParams() {
  return getRuns().datasets.flatMap((d) => d.runs.map((r) => ({ runId: r.run_id })));
}

export async function generateMetadata({ params }: { params: Promise<{ runId: string }> }): Promise<Metadata> {
  const { runId } = await params;
  const run = getRun(runId);
  return { title: `${run.label} on ${run.dataset}` };
}

export default async function RunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  return <EvalsView runId={runId} />;
}
