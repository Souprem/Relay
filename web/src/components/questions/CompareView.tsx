import Link from "next/link";

import { optionLabel } from "@/lib/questions";
import { QUESTION_STATUS_TEXT } from "@/lib/semantic";
import type { QuestionSet, QuestionTransition } from "@/lib/types";
import { diffQuestionSets, type QuestionDiff } from "@/lib/wordDiff";

import { DiffText } from "./DiffText";
import { QuestionHead } from "./QuestionSetView";

const STATUS_LABEL: Record<QuestionDiff["status"], string> = {
  added: "ADDED",
  removed: "REMOVED",
  changed: "CHANGED",
  unchanged: "UNCHANGED",
};

function DiffRow({ d, index }: { d: QuestionDiff; index: number }) {
  return (
    <li id={d.id} className="grid scroll-mt-4 gap-x-4 gap-y-1 border-t border-rule py-2 md:grid-cols-[15rem_minmax(0,1fr)]">
      <QuestionHead index={index} id={d.id} type={d.type}>
        <p className={`mt-0.5 font-mono text-label ${QUESTION_STATUS_TEXT[d.status]}`}>{STATUS_LABEL[d.status]}</p>
      </QuestionHead>
      <div className="min-w-0 max-w-prose">
        <p className="break-words font-mono text-sm text-ink">
          <DiffText segments={d.instructions} />
        </p>
        {d.summary !== null ? (
          <p className="mt-1 break-words text-sm text-ink-2">
            <span className="text-ink-3">Options: </span>
            <span className="font-mono">
              <DiffText segments={d.summary} />
            </span>
          </p>
        ) : null}
        {d.options.length ? (
          <dl className="mt-1 grid gap-y-1 font-mono text-sm sm:grid-cols-[auto_minmax(0,1fr)] sm:gap-x-2 sm:gap-y-0.5">
            {d.options.map((o) => (
              <div key={o.option} className="contents">
                <dt className={`break-words ${o.status === "unchanged" ? "text-ink-3" : "text-ink-2"}`}>{optionLabel(d.type, o.option)}</dt>
                <dd className={`-mt-1 break-words pl-2 sm:mt-0 sm:pl-0 ${o.status === "unchanged" ? "text-ink-2" : "text-ink"}`}>
                  <DiffText segments={o.text} />
                </dd>
              </div>
            ))}
          </dl>
        ) : null}
      </div>
    </li>
  );
}

/** Two question sets compared question by question, with why each step changed. */
export function CompareView({ before, after, transitions }: { before: QuestionSet; after: QuestionSet; transitions: QuestionTransition[] }) {
  const diffs = diffQuestionSets(before.questions, after.questions);
  const count = (s: QuestionDiff["status"]) => diffs.filter((d) => d.status === s).length;
  const shown = diffs.filter((d) => d.status !== "unchanged");
  const unchanged = diffs.filter((d) => d.status === "unchanged");
  const numbered = new Map(diffs.map((d, i) => [d.id, i + 1]));
  return (
    <>
      <header className="max-w-prose">
        <p className="text-label font-semibold uppercase text-ink-2">Compare question sets</p>
        <h1 className="mt-1 font-mono text-xl font-medium text-ink">
          <Link href={`/questions/${before.version}/`} className="hover:underline">
            {before.version}
          </Link>{" "}
          →{" "}
          <Link href={`/questions/${after.version}/`} className="hover:underline">
            {after.version}
          </Link>
        </h1>
      </header>

      <section aria-label="Why it changed" className="mt-3 max-w-prose border-l-2 border-ink pl-2">
        {transitions.map((t) => (
          <div key={t.slug} className="mt-2 first:mt-0">
            <p className="text-label font-semibold uppercase text-ink-2">
              Why it changed{transitions.length > 1 ? `: ${t.from} → ${t.to}` : ""}
            </p>
            <p className="mt-0.5 text-md text-ink">{t.why}</p>
            <a href={t.source} className="text-sm text-ink-2 underline decoration-rule-strong hover:decoration-ink">
              docs/RESULTS.md
            </a>
          </div>
        ))}
      </section>

      <div className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1 border-y border-rule py-1 text-sm text-ink-2">
        <span className="num text-ink">
          {before.count} → {after.count} questions
        </span>
        <span>
          <span className={QUESTION_STATUS_TEXT.added}>{count("added")} added</span> · {count("changed")} changed ·{" "}
          <span className={count("removed") ? QUESTION_STATUS_TEXT.removed : ""}>{count("removed")} removed</span> ·{" "}
          {count("unchanged")} unchanged
        </span>
        <span className="font-mono">
          key: <DiffText segments={[{ kind: "add", text: "added words" }]} />{" "}
          <DiffText segments={[{ kind: "del", text: "removed words" }]} />
        </span>
      </div>

      <ol className="mt-2 border-b border-rule">
        {shown.map((d) => (
          <DiffRow key={d.id} d={d} index={numbered.get(d.id)!} />
        ))}
      </ol>

      {unchanged.length ? (
        <details className="mt-3 border-b border-rule pb-2">
          <summary className="cursor-pointer text-sm text-ink-2 hover:text-ink">
            {unchanged.length} unchanged question{unchanged.length === 1 ? "" : "s"}:{" "}
            <span className="font-mono">{unchanged.map((d) => d.id).join(", ")}</span>
          </summary>
          <ol className="mt-2">
            {unchanged.map((d) => (
              <DiffRow key={d.id} d={d} index={numbered.get(d.id)!} />
            ))}
          </ol>
        </details>
      ) : null}
    </>
  );
}
