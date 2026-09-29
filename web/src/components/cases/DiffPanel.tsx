import Link from "next/link";

import { ActionBadge } from "@/components/ui/ActionBadge";
import { Td, TableScroll, Th } from "@/components/ui/Table";
import { VerdictLabel } from "@/components/ui/Verdict";
import { DECISION_LABELS, pyFixed, threshold } from "@/lib/format";
import { compareHref, comparePair } from "@/lib/questions";
import type { CaseDetail } from "@/lib/types";
import { RESOLVED_TEXT, UNSAFE_TEXT } from "@/lib/semantic";

type Diff = CaseDetail["diffs"][number];

function signed(v: number | null): string {
  if (v === null) return "—";
  return `${v >= 0 ? "+" : "−"}${pyFixed(Math.abs(v), 3)}`;
}

function changeTag(diff: Diff) {
  if (diff.newly_unsafe) return <span className={`font-mono text-sm font-medium ${UNSAFE_TEXT}`}>NEWLY UNSAFE</span>;
  if (diff.unsafe_resolved) return <span className={`font-mono text-sm font-medium ${RESOLVED_TEXT}`}>UNSAFE RESOLVED</span>;
  if (diff.action_original === diff.action_candidate) return <span className="font-mono text-sm text-ink-2">ACTION UNCHANGED</span>;
  return <span className="font-mono text-sm text-ink-2">{(diff.change ?? "changed").toUpperCase()}</span>;
}

/** relay replay's comparison of two traces of this case, rendered: what moved and what it did. */
export function DiffPanel({ diff }: { diff: Diff }) {
  const gateChanges = diff.gates.filter((g) => g.original !== g.candidate);
  const thresholds = Object.entries(diff.thresholds);
  return (
    <article className="min-w-0 border-t border-ink pt-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-lg text-ink">{diff.title}</h3>
        {changeTag(diff)}
      </div>
      <p className="mt-1 max-w-prose text-md text-ink-2">{diff.summary}</p>
      {diff.questions_compare ? (
        <p className="mt-1 text-sm text-ink-2">
          The question sets differ:{" "}
          <Link
            href={compareHref(diff.questions_compare)}
            className="font-mono text-ink underline decoration-rule-strong hover:decoration-ink"
          >
            compare {comparePair(diff.questions_compare).join(" → ")}&nbsp;→
          </Link>
        </p>
      ) : null}

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {[
          ["Before", diff.original_label, diff.action_original, diff.verdict_original, diff.reasons_original],
          ["After", diff.candidate_label, diff.action_candidate, diff.verdict_candidate, diff.reasons_candidate],
        ].map(([side, label, action, verdict, reasons]) => (
          <div key={side as string}>
            <p className="text-label font-semibold uppercase text-ink-2">{side as string}</p>
            <p className="mt-0.5 text-sm text-ink">{label as string}</p>
            <div className="mt-1 flex items-center gap-2">
              <ActionBadge action={action as Diff["action_original"]} />
              <VerdictLabel verdict={verdict as Diff["verdict_original"]} />
            </div>
            <ul className="mt-1 grid gap-0.5 font-mono text-label tracking-normal text-ink-2">
              {(reasons as string[]).map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="mt-3">
        <TableScroll hint>
          <table className="w-full min-w-[36rem]">
            <thead>
              <tr>
                <Th>Judgment</Th>
                <Th align="right">Before</Th>
                <Th align="right">After</Th>
                <Th align="right">Δ</Th>
                <Th>Thresholds crossed</Th>
              </tr>
            </thead>
            <tbody>
              {diff.decisions.map((d) => (
                <tr key={d.question_id} className={d.answer_changed ? "bg-paper-2" : ""}>
                  <Td>
                    {DECISION_LABELS[d.question_id] ?? d.question_id}
                    {d.answer_changed ? <span className="ml-1 font-mono text-label tracking-normal text-ink">answer changed</span> : null}
                  </Td>
                  <Td num>{d.original}</Td>
                  <Td num>{d.candidate}</Td>
                  <Td num>{signed(d.delta)}</Td>
                  <Td className="font-mono text-sm">
                    {d.crossed.length === 0
                      ? <span className="text-ink-3">none</span>
                      : d.crossed.map((c) => (d.crossed_gated.includes(c) ? c : `(${c})`)).join(", ")}
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableScroll>
        <p className="mt-1 text-sm text-ink-3">(name) = a comparison no engine gate acts on.</p>
      </div>

      {thresholds.length || gateChanges.length || diff.ablation_candidate ? (
        <dl className="mt-3 grid gap-x-4 gap-y-1 text-sm md:grid-cols-[auto_1fr]">
          {thresholds.map(([name, [a, b]]) => (
            <div key={name} className="contents">
              <dt className="text-ink-3">Threshold</dt>
              <dd className="num text-ink">
                {name} {threshold(a)} → {threshold(b)}
              </dd>
            </div>
          ))}
          {diff.ablation_candidate ? (
            <div className="contents">
              <dt className="text-ink-3">Ablated</dt>
              <dd className="font-mono text-ink">{diff.ablation_candidate.join(", ")} gate disabled in the candidate</dd>
            </div>
          ) : null}
          {gateChanges.map((g) => (
            <div key={g.gate} className="contents">
              <dt className="text-ink-3">Gate</dt>
              <dd className="font-mono text-ink">
                {g.gate}: {g.original} → {g.candidate}
                {g.detail_candidate ? <span className="block text-label tracking-normal text-ink-2">{g.detail_candidate}</span> : null}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
    </article>
  );
}
