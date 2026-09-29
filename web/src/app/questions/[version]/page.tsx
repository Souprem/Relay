import type { Metadata } from "next";
import Link from "next/link";

import { Facts, HashFacts, QuestionList, RecordedText, UsedBy } from "@/components/questions/QuestionSetView";
import { PageHeader, Section } from "@/components/ui/Section";
import { getQuestions } from "@/lib/data";
import { CLAUDE_PAGE, compareHref, questionSetLabel } from "@/lib/questions";
import type { QuestionsData, QuestionSet } from "@/lib/types";

export const dynamicParams = false;

export function generateStaticParams() {
  return [...getQuestions().sets.map((s) => ({ version: s.version })), { version: CLAUDE_PAGE }];
}

export async function generateMetadata({ params }: { params: Promise<{ version: string }> }): Promise<Metadata> {
  const { version } = await params;
  return { title: version === CLAUDE_PAGE ? "Claude's system prompt" : `Question set ${version}` };
}

const linkClass = "underline decoration-rule-strong hover:decoration-ink";

function SetPage({ data, set }: { data: QuestionsData; set: QuestionSet }) {
  const into = data.transitions.find((t) => t.to === set.version);
  const out = data.transitions.find((t) => t.from === set.version);
  const path = data.composition.step_therapy_paths.find((p) => p.versions.includes(set.version));
  return (
    <>
      <PageHeader eyebrow="Question set" title={<span className="font-mono">{set.version}</span>}>
        <p>
          {set.count} questions, sent to Jev in one call per case under{" "}
          <span className="font-mono">{set.policy}</span>
          {set.version === data.default_version ? "; the code's default set" : ""}
          {set.version === data.latest_version ? "; the latest adopted set" : ""}. Question ids are for code and
          are not sent; the instructions and criteria below are. Year options are the {data.year_display}.
        </p>
      </PageHeader>
      <HashFacts set={set} />

      {into ? (
        <section aria-label={`Changes from ${into.from}`} className="mt-3 max-w-prose border-l-2 border-ink pl-2">
          <p className="text-label font-semibold uppercase text-ink-2">Why it changed from {into.from}</p>
          <p className="mt-0.5 text-md text-ink">{into.why}</p>
          <Link href={compareHref(into.slug)} className={`font-mono text-sm text-ink ${linkClass}`}>
            compare {into.from} → {into.to}&nbsp;→
          </Link>
        </section>
      ) : null}
      {out ? (
        <p className="mt-2 text-sm text-ink-2">
          Replaced by{" "}
          <Link href={compareHref(out.slug)} className={`font-mono text-ink ${linkClass}`}>
            {out.to} (compare)&nbsp;→
          </Link>
        </p>
      ) : null}

      <Section id="questions" label={`The ${set.count} questions`}>
        <QuestionList questions={set.questions} />
      </Section>

      {path ? (
        <Section id="composition" label="Step therapy under this set">
          <p className="max-w-prose text-sm text-ink-2">
            {path.text} {data.composition.recency}{" "}
            <Link href="/questions/#composition" className={linkClass}>
              How every decision is composed
            </Link>
            .
          </p>
        </Section>
      ) : null}
    </>
  );
}

function ClaudePage({ data }: { data: QuestionsData }) {
  const c = data.claude;
  return (
    <>
      <PageHeader eyebrow="Claude baseline" title="Claude's exact system prompt">
        <p>
          Rendered by <code className="text-base">render_system_prompt()</code> from the same{" "}
          <Link href={`/questions/${c.question_set}/`} className={`font-mono ${linkClass}`}>
            {c.question_set}
          </Link>{" "}
          questions Jev answers, under <span className="font-mono">{c.policy}</span>. It is the same for every case,
          so it can be cached; the case-specific years appear only in the per-case response schema.
        </p>
      </PageHeader>
      <Facts
        rows={[
          ["Prompt version", <span key="v" className="font-mono text-ink">{c.prompt_version}</span>],
          ["Recorded as", <span key="r" className="font-mono text-ink">{questionSetLabel(c.question_set_version)}</span>],
          [
            "question_set_hash",
            <span key="h">
              <span className="break-all font-mono text-ink">{c.hash}</span>
              <span className="block">{c.hash_covers}</span>
            </span>,
          ],
          ["Recorded", <RecordedText key="rec" recorded={c.recorded} hash={c.hash} />],
          ["Runs", <UsedBy key="u" runs={c.used_by} />],
        ]}
      />
      <Section id="prompt" label="System prompt">
        <pre className="max-w-[80ch] whitespace-pre-wrap break-words border-y border-rule py-2 font-mono text-sm text-ink">
          {c.system_prompt}
        </pre>
      </Section>
    </>
  );
}

export default async function QuestionSetPage({ params }: { params: Promise<{ version: string }> }) {
  const { version } = await params;
  const data = getQuestions();
  if (version === CLAUDE_PAGE) return <ClaudePage data={data} />;
  const set = data.sets.find((s) => s.version === version);
  if (!set) throw new Error(`no question set ${version} in questions.json`);
  return <SetPage data={data} set={set} />;
}
