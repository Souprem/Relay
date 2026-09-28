import type { Metadata } from "next";

import { EvalsView } from "@/components/evals/EvalsView";
import { getRuns } from "@/lib/data";

export const metadata: Metadata = { title: "Evals" };

export default function EvalsPage() {
  return <EvalsView runId={getRuns().datasets[0].runs[0].run_id} />;
}
