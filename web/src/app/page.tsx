import Link from "next/link";

import { ArchitectureDiagram } from "@/components/home/ArchitectureDiagram";
import { EntryCase } from "@/components/home/EntryCase";
import { Findings } from "@/components/home/Findings";
import { HeadlineTable } from "@/components/home/HeadlineTable";
import { Section } from "@/components/ui/Section";
import { getCase, getIndex } from "@/lib/data";
import { threshold, usd } from "@/lib/format";

export default function HomePage() {
  const index = getIndex();
  const easy = getCase(index.entry_cases.easy);
  const hard = getCase(index.entry_cases.hard);
  const example = easy.providers[0];
  return (
    <>
      <header className="grid gap-3 md:grid-cols-[minmax(0,42rem)_1fr] md:gap-6">
        <div>
          <p className="text-label font-semibold uppercase text-ink-2">
            Synthetic prior-authorization cases · evaluation prototype
          </p>
          <h1 className="mt-2 text-xl font-medium text-ink">
            Relay turns a model&rsquo;s probabilities into actions software is allowed to take, and
            records why.
          </h1>
          <p className="mt-2 text-md text-ink-2">
            Jev answers narrow questions about each case, such as whether the methotrexate course
            lasted twelve weeks, with probabilities. A versioned policy engine, not the model, then
            decides whether the case is auto-processed, sent back for information, or reviewed by a
            person.
          </p>
        </div>
        <dl className="self-end border-l border-rule pl-2 font-mono text-sm">
          <div>
            <dt className="text-ink-3">Jev</dt>
            <dd className="text-ink">What does the available evidence most likely establish?</dd>
          </div>
          <div className="mt-1">
            <dt className="text-ink-3">Relay</dt>
            <dd className="text-ink">
              What is software permitted to do given those judgments and their confidence?
            </dd>
          </div>
        </dl>
      </header>

      <Section id="pipeline" label="How a case moves">
        <ArchitectureDiagram
          caseId={easy.id}
          providerLabel={`${example.label} @${threshold(example.thresholds.auto_process)}`}
          decisions={example.decisions}
          gates={example.gates}
          action={example.action}
        />
      </Section>

      <Section
        id="results"
        label="Headline results"
        lede={
          <>
            Each provider runs at its own <code className="text-sm">auto_process</code> threshold,
            chosen on a dev set before the holdout or gold run. Unsafe means the engine
            auto-processed a case whose expected action was not{" "}
            <code className="text-sm">AUTO_PROCESS</code>. The bound is the exact 95%
            Clopper-Pearson upper limit on the unsafe rate.
          </>
        }
      >
        <HeadlineTable rows={index.headline} />
        <ul className="mt-2 max-w-prose list-disc pl-2 text-sm text-ink-2">
          <li>All data is synthetic. Gold labels were written and checked by AI agents, not clinicians.</li>
          <li>Claude&rsquo;s holdout evidence is a 150-case sample, so it is not in the table.</li>
          <li>Gold is not a blind test for q-v0.3: GOLD-TMP-17 motivated that question set.</li>
          <li>
            Provider spend: Claude {usd(index.spend.claude_usd)} for every Claude run; Jev{" "}
            {usd(index.spend.jev_3d_usd)} for the q-v0.3, policy-shift and latency runs.
          </li>
        </ul>
      </Section>

      <Section id="findings" label="What we found">
        <Findings findings={index.findings} />
      </Section>

      <Section id="start" label="Start with a case">
        <div className="grid gap-4 md:grid-cols-2">
          <EntryCase
            kind="An easy case"
            detail={easy}
            summary="One note with explicit dates: methotrexate for 24 weeks, stopped for inadequate response. Every provider auto-processes it, correctly."
          />
          <EntryCase
            kind="A hard case"
            detail={hard}
            summary="The note says seven weeks of methotrexate; the medication history implies 136 days. The models send it to review. The rules baseline automates it."
          />
        </div>
        <p className="mt-3 text-sm text-ink-2">
          Or browse <Link href="/cases/" className="underline hover:text-ink">all {index.counts.cases} cases</Link>.
        </p>
      </Section>
    </>
  );
}
