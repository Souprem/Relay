import Link from "next/link";

import { CostLine } from "@/components/cost/CostLine";
import { ArchitectureDiagram } from "@/components/home/ArchitectureDiagram";
import { EntryCase } from "@/components/home/EntryCase";
import { Findings } from "@/components/home/Findings";
import { HeadlineTable } from "@/components/home/HeadlineTable";
import { HeroFigures } from "@/components/home/HeroFigures";
import { Disclosure } from "@/components/ui/Disclosure";
import { Section } from "@/components/ui/Section";
import { getCase, getIndex } from "@/lib/data";
import { threshold, usd } from "@/lib/format";

export default function HomePage() {
  const index = getIndex();
  const easy = getCase(index.entry_cases.easy);
  const hard = getCase(index.entry_cases.hard);
  const failure = getCase("GOLD-TMP-17");
  const example = easy.providers[0];
  return (
    <>
      <header className="max-w-[48rem]">
        <p className="text-label font-semibold uppercase text-ink-2">
          Synthetic prior-authorization cases · evaluation prototype
        </p>
        <h1 className="mt-2 text-balance text-xl font-medium text-ink">
          Relay turns a model&rsquo;s probabilities into actions software is allowed to take, and
          records why.
        </h1>
        <p className="mt-2 text-md text-ink-2">
          Relay evaluates synthetic medication-coverage requests. Jev answers narrow questions
          about the evidence with probabilities; a versioned policy
          engine, not the model, decides what happens to the case.
        </p>
      </header>

      <section aria-label="Headline result" className="mt-5">
        <HeroFigures hero={index.hero} />
        <CostLine headline={index.cost.comparison.headline} />
        <p className="mt-2 max-w-prose text-sm text-ink-2">
          These results measure agreement with synthetic labels, not clinical validation.
          Gold labels were written and checked by AI agents, not clinicians.
        </p>
        <p className="mt-2 text-md">
          <Link href={`/cases/${failure.id}/#changed`} className="text-ink underline decoration-rule-strong hover:decoration-ink">
            See the paused-treatment failure and fix →
          </Link>
        </p>
        <div className="mt-3">
          <Disclosure id="results" label="Full results table" meta={`${index.headline.length} runs`}>
            <p className="max-w-prose text-md text-ink-2">
              Each provider runs at its own <code className="text-sm">auto_process</code> threshold,
              chosen on a dev set before the holdout or gold run. Unsafe means the engine
              auto-processed a case whose expected action was not{" "}
              <code className="text-sm">AUTO_PROCESS</code>. The bound is the exact 95%
              Clopper-Pearson upper limit on the unsafe rate.
            </p>
            <div className="mt-2">
              <HeadlineTable rows={index.headline} />
            </div>
            <ul className="mt-2 max-w-prose list-disc pl-2 text-sm text-ink-2">
              <li>All data is synthetic. Gold labels were written and checked by AI agents, not clinicians.</li>
              <li>Claude&rsquo;s holdout evidence is a 150-case sample, so it is not in the table.</li>
              <li>Gold is not a blind test for q-v0.3: GOLD-TMP-17 motivated that question set.</li>
              <li>
                Provider spend: Claude {usd(index.spend.claude_usd)} for every Claude run; Jev{" "}
                {usd(index.spend.jev_3d_usd)} for the q-v0.3, policy-shift and latency runs.
              </li>
            </ul>
          </Disclosure>
        </div>
      </section>

      <Section id="pipeline" label="How a case moves">
        <ArchitectureDiagram
          caseId={easy.id}
          documents={easy.input.documents.map((doc) => doc.kind.replaceAll("_", " "))}
          providerLabel={`${example.label} @${threshold(example.thresholds.auto_process)}`}
          decisions={example.decisions}
          gates={example.gates}
          action={example.action}
        />
      </Section>

      <Section id="findings" label="What we found">
        <Findings findings={index.findings} />
      </Section>

      <Section id="start" label="Start with a case">
        <ul className="max-w-[56rem] border-t border-rule">
          <EntryCase
            kind="A design failure"
            detail={failure}
            summary="Jev and Claude both missed a treatment pause; changing the questions resolved this case."
          />
          <EntryCase
            kind="An easy case"
            detail={easy}
            summary="Explicit dates; every provider auto-processes it, correctly."
          />
          <EntryCase
            kind="A hard case"
            detail={hard}
            summary="The note and the medication history disagree; only the rules baseline automates it."
          />
        </ul>
        <p className="mt-2 text-sm text-ink-2">
          Or browse <Link href="/cases/" className="underline hover:text-ink">all {index.counts.cases} cases</Link>.
        </p>
      </Section>
    </>
  );
}
