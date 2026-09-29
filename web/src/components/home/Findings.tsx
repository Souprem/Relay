import Link from "next/link";

import { Disclosure } from "@/components/ui/Disclosure";
import { FINDING_TONE_TEXT } from "@/lib/semantic";
import type { Finding } from "@/lib/types";

/**
 * The home page's findings: five one-line headlines, each opening onto its full text and links.
 * The text, numbers included, comes from index.json (relay/site/findings.py); only unsafe and
 * correct figures take colour.
 */
export function Findings({ findings }: { findings: Finding[] }) {
  return (
    <div className="max-w-[48rem] border-b border-rule">
      {findings.map((f, i) => (
        <Disclosure
          key={f.id}
          id={`finding-${f.id}`}
          label={
            <span className="flex gap-1">
              <span className="num shrink-0 pt-px text-sm text-ink-3" aria-hidden="true">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="text-balance">{f.title}</span>
            </span>
          }
        >
          <div className="pl-5">
            <p className="text-md text-ink-2">
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
        </Disclosure>
      ))}
    </div>
  );
}
