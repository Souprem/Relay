import { getIndex } from "@/lib/data";

export default function HomePage() {
  const index = getIndex();
  return (
    <p className="text-md text-ink-2">
      {index.counts.cases} cases and {index.counts.runs} runs exported.
    </p>
  );
}
