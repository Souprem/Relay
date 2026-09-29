import Link from "next/link";

import { optionLabel, QUESTION_TYPE_LABEL } from "@/lib/questions";
import type { Question, QuestionSet, RecordedHashes, RunRef } from "@/lib/types";

const pad = (n: number) => String(n).padStart(2, "0");

/** The left column of a question row: its number, id and type. */
export function QuestionHead({ index, id, type, children }: { index: number; id: string; type: Question["type"]; children?: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="flex flex-wrap items-baseline gap-x-1">
        <span className="num text-sm text-ink-3">{pad(index)}</span>
        <span className="break-words font-mono text-base text-ink">{id}</span>
      </p>
      <p className="text-label tracking-normal text-ink-3">{QUESTION_TYPE_LABEL[type]}</p>
      {children}
    </div>
  );
}

/** One question exactly as sent: instructions, the option list and each criterion. */
function QuestionRow({ q, index }: { q: Question; index: number }) {
  const described = q.options.filter((o) => o.text !== null);
  return (
    <li id={q.id} className="grid scroll-mt-4 gap-x-4 gap-y-1 border-t border-rule py-2 md:grid-cols-[15rem_minmax(0,1fr)]">
      <QuestionHead index={index} id={q.id} type={q.type} />
      <div className="min-w-0 max-w-prose">
        <p className="break-words font-mono text-sm text-ink">{q.instructions}</p>
        {q.options_summary !== null ? (
          <p className="mt-1 break-words text-sm text-ink-2">
            <span className="text-ink-3">Options: </span>
            <span className="font-mono">{q.options_summary}</span>
          </p>
        ) : null}
        {described.length ? (
          <dl className="mt-1 grid gap-y-1 font-mono text-sm sm:grid-cols-[auto_minmax(0,1fr)] sm:gap-x-2 sm:gap-y-0.5">
            {described.map((o) => (
              <div key={o.option} className="contents">
                <dt className="break-words text-ink-2">{optionLabel(q.type, o.option)}</dt>
                <dd className="-mt-1 break-words pl-2 text-ink sm:mt-0 sm:pl-0">{o.text}</dd>
              </div>
            ))}
          </dl>
        ) : null}
      </div>
    </li>
  );
}

export function QuestionList({ questions }: { questions: Question[] }) {
  return (
    <ol className="border-b border-rule">
      {questions.map((q, i) => (
        <QuestionRow key={q.id} q={q} index={i + 1} />
      ))}
    </ol>
  );
}

export function RecordedText({ recorded, hash }: { recorded: RecordedHashes | null; hash: string }) {
  if (recorded === null) return <span className="text-ink-3">no committed gold or smoke traces</span>;
  if (recorded.matches) {
    return (
      <span>
        the same hash is recorded in {recorded.traces} committed gold and smoke traces
      </span>
    );
  }
  return (
    <span className="text-ink">
      differs: the traces record <span className="break-all font-mono">{recorded.hashes.join(", ")}</span>, the code gives{" "}
      <span className="break-all font-mono">{hash}</span>
    </span>
  );
}

export function UsedBy({ runs }: { runs: RunRef[] }) {
  return (
    <ul className="flex flex-wrap gap-x-2 gap-y-0.5">
      {runs.map((r) => (
        <li key={r.run_id}>
          <Link href={`/evals/${r.run_id}/`} className="text-sm text-ink underline decoration-rule-strong hover:decoration-ink">
            {r.dataset}
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** A labelled fact list under a page header: label left, value right, stacked on a phone. */
export function Facts({ rows }: { rows: [string, React.ReactNode][] }) {
  return (
    <dl className="mt-3 grid gap-x-4 gap-y-1 border-y border-rule py-2 text-sm md:grid-cols-[10rem_minmax(0,1fr)]">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-ink-3">{k}</dt>
          <dd className="-mt-0.5 min-w-0 text-ink-2 md:mt-0">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function HashFacts({ set }: { set: QuestionSet }) {
  const rows: [string, React.ReactNode][] = set.same_hash_under_all_policies
    ? [
        [
          "question_set_hash",
          <span key="h">
            <span className="break-all font-mono text-ink">{set.hashes[0].hash}</span>
            <span className="block">under {set.hashes.map((h) => h.policy).join(" and ")} (identical)</span>
          </span>,
        ],
      ]
    : set.hashes.map((h) => [
        `hash · ${h.policy}`,
        <span key={h.policy} className="break-all font-mono text-ink">
          {h.hash}
        </span>,
      ]);
  rows.push(["Recorded", <RecordedText key="r" recorded={set.recorded} hash={set.hashes[0].hash} />]);
  rows.push(["Runs", <UsedBy key="u" runs={set.used_by} />]);
  return <Facts rows={rows} />;
}
