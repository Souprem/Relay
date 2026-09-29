import Link from "next/link";

import { FINDING_TONE_TEXT } from "@/lib/semantic";
import type { Finding } from "@/lib/types";

/**
 * The home page's findings: a numbered list split by thin rules. The text, numbers included,
 * comes from index.json (relay/site/findings.py); only unsafe and correct figures take colour.
 */
export function Findings({ findings }: { findings: Finding[] }) {
  return (
    <ol className="max-w-[48rem] border-t border-ink">
      {findings.map((f, i) => (
        <li
          key={f.id}
          id={`finding-${f.id}`}
          className="grid grid-cols-[1.5rem_minmax(0,1fr)] gap-x-1 border-b border-rule py-2 md:grid-cols-[2.5rem_minmax(0,1fr)]"
        >
          <span className="num pt-px text-sm text-ink-3" aria-hidden="true">
            {String(i + 1).padStart(2, "0")}
          </span>
          <div>
            <p className="text-balance text-md font-medium text-ink">{f.title}</p>
            <p className="mt-1 text-md text-ink-2">
              {f.body.map((s, j) =>
                s.tone ? (
                  <span key={j} className={`font-medium ${FINDING_TONE_TEXT[s.tone]}`}>
                    {s.text}
                  </span>
                ) : (
                  <span key={j}>{s.text}</span>
                ),
              )}
            </p>
            <p className="mt-1 flex flex-wrap gap-x-2 text-sm">
              <Link href={f.link.href} className="text-ink underline decoration-rule-strong hover:decoration-ink">
                {f.link.label}
              </Link>
              <a href={f.source} className="text-ink-2 underline decoration-rule-strong hover:text-ink">
                Method in RESULTS.md
              </a>
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
