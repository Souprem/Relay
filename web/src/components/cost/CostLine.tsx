import Link from "next/link";

import type { CostData } from "@/lib/types";

/**
 * The home page's one-line cost statement, under the hero figures. Every figure is an exported
 * display string (relay/site/cost.py); the sentence reads exactly as the exported `text`.
 */
export function CostLine({ headline }: { headline: CostData["comparison"]["headline"] }) {
  const { jev, claude, ratio } = headline;
  return (
    <p className="mt-3 border-t border-rule pt-1.5 text-md text-ink-2">
      <span data-testid="cost-sentence">
        <span className="text-ink">Cost per case on gold:</span> Jev{" "}
        <span className="num text-ink">{jev.per_case_short}</span> · {claude.label}{" "}
        <span className="num text-ink">{claude.per_case_short}</span> (batch), about{" "}
        <span className="num font-medium text-ink">{ratio.text}</span> more, at similar gold accuracy.
      </span>{" "}
      <Link
        href="/experiments/#cost"
        className="whitespace-nowrap text-ink underline decoration-rule-strong hover:decoration-ink"
      >
        Cost and speed →
      </Link>
    </p>
  );
}
