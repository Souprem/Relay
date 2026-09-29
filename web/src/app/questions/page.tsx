import type { Metadata } from "next";
import Link from "next/link";

import { HashFacts, QuestionList } from "@/components/questions/QuestionSetView";
import { PageHeader, Section } from "@/components/ui/Section";
import { getQuestions } from "@/lib/data";
import { DECISION_LABELS } from "@/lib/format";
import { CLAUDE_PAGE, compareHref, shortHash } from "@/lib/questions";

export const metadata: Metadata = { title: "Questions" };

function Row({
  name,
  href,
  count,
  hash,
  detail,
  change,
  id,
}: {
  name: string;
  href?: string;
  count: string;
  hash: string | null;
  detail: React.ReactNode;
  change?: React.ReactNode;
  id?: string;
}) {
  return (
    <li id={id} className="grid scroll-mt-4 gap-x-3 gap-y-0.5 border-b border-rule py-2 md:grid-cols-[11rem_7rem_minmax(0,1fr)_12rem]">
      <p className="font-mono text-base">
        {href ? (
          <Link href={href} className="text-ink underline decoration-rule-strong hover:decoration-ink">
            {name}
          </Link>
        ) : (
          <span className="text-ink">{name}</span>
        )}
      </p>
      <p className="num text-sm text-ink">{count}</p>
      <div className="min-w-0 text-sm text-ink-2">
        {detail}
        {hash ? (
          <p className="font-mono text-label tracking-normal text-ink-3" title={hash}>
            {shortHash(hash)}
          </p>
        ) : null}
      </div>
      <div className="text-sm md:text-right">{change}</div>
    </li>
  );
}

export default function QuestionsPage() {
  const data = getQuestions();
  const byVersion = new Map(data.sets.map((s) => [s.version, s]));
  const intoVersion = new Map(data.transitions.map((t) => [t.to, t]));
  const defaultSet = byVersion.get(data.default_version)!;
  const c = data.composition;
  return (
    <>
      <PageHeader eyebrow="Questions" title="What each provider was asked">
        <p>
          Jev and Claude answer the same narrow questions, rendered from <code className="text-base">build_questions()</code> in{" "}
          <code className="text-base">relay/decisions/questions.py</code>. Code, not the model, turns the answers into the five
          decisions. Every text on these pages is exported from that code, and each hash is checked against the hash the
          committed traces record.
        </p>
      </PageHeader>

      <Section id="sets" label="Question sets and prompts">
        <ul className="border-t border-ink">
          {data.sets.map((s) => {
            const t = intoVersion.get(s.version);
            return (
              <Row
                key={s.version}
                name={s.version}
                href={`/questions/${s.version}/`}
                count={`${s.count} questions`}
                hash={s.hashes[0].hash}
                detail={
                  <p>
                    Jev · {s.used_by.length} run{s.used_by.length === 1 ? "" : "s"}
                    {s.version === data.default_version ? " · code default" : ""}
                    {s.version === data.latest_version ? " · latest adopted" : ""}
                  </p>
                }
                change={
                  t ? (
                    <Link href={compareHref(t.slug)} className="font-mono text-ink underline decoration-rule-strong hover:decoration-ink">
                      changes from {t.from}&nbsp;→
                    </Link>
                  ) : (
                    <span className="text-ink-3">first set</span>
                  )
                }
              />
            );
          })}
          <Row
            name="Claude prompt"
            href={`/questions/${CLAUDE_PAGE}/`}
            count={`${byVersion.get(data.claude.question_set)?.count ?? ""} questions`}
            hash={data.claude.hash}
            detail={
              <p>
                Claude · {data.claude.used_by.length} runs · the {data.claude.question_set} questions in one system prompt (
                <span className="font-mono">{data.claude.prompt_version}</span>)
              </p>
            }
            change={
              <Link href={`/questions/${data.claude.question_set}/`} className="font-mono text-ink underline decoration-rule-strong hover:decoration-ink">
                {data.claude.question_set}&nbsp;→
              </Link>
            }
          />
          <Row
            id="rules"
            name={data.rules.version}
            count="no prompt"
            hash={null}
            detail={
              <p>
                {data.rules.text}{" "}
                <a href={data.rules.source} className="underline decoration-rule-strong hover:decoration-ink">
                  Its patterns are described in RESULTS.md
                </a>
                .
              </p>
            }
          />
        </ul>
        <p className="mt-2 max-w-prose text-sm text-ink-2">{data.policy_note}</p>
      </Section>

      <Section id="composition" label="How answers become decisions" lede={c.intro}>
        <dl className="grid max-w-prose gap-y-2 md:max-w-none md:grid-cols-[13rem_minmax(0,1fr)] md:gap-x-4">
          {c.decisions.map((d) => (
            <div key={d.decision} className="contents">
              <dt className="text-sm text-ink">
                {DECISION_LABELS[d.decision] ?? d.decision}
                <span className="block font-mono text-label tracking-normal text-ink-3">{d.decision}</span>
              </dt>
              <dd className="-mt-1 max-w-prose text-sm text-ink-2 md:mt-0">
                {d.text}
                {d.decision === "step_therapy" ? (
                  <>
                    <ul className="mt-1 grid gap-1">
                      {c.step_therapy_paths.map((p) => (
                        <li key={p.versions.join()} className="border-l border-rule-strong pl-1">
                          <span className="font-mono text-ink">{p.versions.join(", ")}: </span>
                          {p.text}
                        </li>
                      ))}
                    </ul>
                    <p className="mt-1">{c.recency}</p>
                  </>
                ) : null}
              </dd>
            </div>
          ))}
        </dl>
        <p className="mt-2 font-mono text-label tracking-normal text-ink-3">{c.source}</p>
      </Section>

      <Section
        id="default"
        label={`The default set: ${defaultSet.version}`}
        lede={
          <p>
            <code className="text-md">DEFAULT_QUESTION_SET_VERSION</code> in the code
            {data.claude.question_set === defaultSet.version ? ", and the set every Claude run used" : ""}.{" "}
            <Link href={`/questions/${data.latest_version}/`} className="underline decoration-rule-strong hover:decoration-ink">
              {data.latest_version}
            </Link>{" "}
            is the latest adopted set. Year options are the {data.year_display}.
          </p>
        }
      >
        <HashFacts set={defaultSet} />
        <div className="mt-3">
          <QuestionList questions={defaultSet.questions} />
        </div>
      </Section>
    </>
  );
}
