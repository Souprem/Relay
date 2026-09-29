import Link from "next/link";

import { QuestionsLink } from "@/components/questions/QuestionsLink";
import { FrontierChart } from "@/components/charts/FrontierChart";
import { ReliabilityDiagram } from "@/components/charts/ReliabilityDiagram";
import { Disclosure } from "@/components/ui/Disclosure";
import { MetricCard } from "@/components/ui/MetricCard";
import { PageHeader, Section } from "@/components/ui/Section";
import { Td, TableScroll, Th } from "@/components/ui/Table";
import { getRun, getRuns } from "@/lib/data";
import { ciText, rateText, threshold } from "@/lib/format";
import { UNSAFE_TEXT } from "@/lib/semantic";

const DECISIONS = [
  "diagnosis_support",
  "step_therapy",
  "documentation_complete",
  "material_contradiction",
  "missing_evidence",
];

/** One run's evaluation: rates with intervals, the frontier, calibration, and its dataset's runs. */
export function EvalsView({ runId }: { runId: string }) {
  const runs = getRuns();
  const run = getRun(runId);
  const dataset = runs.datasets.find((d) => d.id === run.dataset);
  if (!dataset) throw new Error(`run ${runId} has no dataset in runs.json`);
  const m = run.metrics;
  const op = run.operating_point;
  const calibrated = DECISIONS.filter((d) => run.calibration.decisions[d]);
  return (
    <>
      <PageHeader eyebrow="Evaluation" title="Every committed run, at its operating point">
        <p>Rates carry exact 95% Clopper-Pearson intervals.</p>
        <Disclosure label="How this is measured" variant="inline" className="mt-0.5">
          <p className="text-sm text-ink-2">
            Runs on gold and smoke are re-scored from their traces; runs on generated sets come from
            their committed report bundles.
          </p>
        </Disclosure>
      </PageHeader>

      <nav aria-label="Datasets and runs" className="mt-4 grid gap-2 border-y border-rule py-2 md:grid-cols-[12rem_minmax(0,1fr)]">
        <ul className="flex flex-wrap gap-x-2 gap-y-0.5 md:block">
          {runs.datasets.map((d) => {
            const active = d.id === dataset.id;
            return (
              <li key={d.id}>
                <Link
                  href={`/evals/${d.runs[0].run_id}/`}
                  aria-current={active ? "true" : undefined}
                  className={`font-mono text-sm ${active ? "text-ink underline" : "text-ink-2 hover:text-ink"}`}
                >
                  {d.id}
                </Link>
              </li>
            );
          })}
        </ul>
        <div>
          <p className="text-sm text-ink-2">{dataset.description}</p>
          <ul className="mt-1 flex flex-wrap gap-1">
            {dataset.runs.map((r) => {
              const active = r.run_id === run.run_id;
              return (
                <li key={r.run_id}>
                  <Link
                    href={`/evals/${r.run_id}/`}
                    aria-current={active ? "page" : undefined}
                    className={`block border px-1 py-0.5 text-sm ${
                      active ? "border-ink text-ink" : "border-rule text-ink-2 hover:border-rule-strong hover:text-ink"
                    }`}
                  >
                    {r.label} <span className="num text-ink-3">@{threshold(r.auto_process)}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      </nav>

      <section className="mt-4" aria-labelledby="run-title">
        <h2 id="run-title" className="text-lg text-ink">
          {run.label} on {run.dataset}
        </h2>
        <p className="mt-0.5 text-sm text-ink-2">
          <span className="num">{run.run_id}</span> · n {run.n} · auto_process{" "}
          <span className="num text-ink">{threshold(op.auto_process)}</span> ({op.source}
          {op.auto_process !== op.recorded ? `; recorded at ${threshold(op.recorded)}` : ""})
        </p>
        <QuestionsLink questionSet={run.question_set} page={run.questions_page} className="mt-0.5" />
        {run.note ? <p className="mt-0.5 text-sm text-ink-2">{run.note}</p> : null}
        <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-3 md:grid-cols-5">
          <MetricCard label="Correct action" rate={m.correct} />
          <MetricCard label="Automation" rate={m.automation} />
          <MetricCard label="Unsafe / auto" rate={m.uar} />
        </div>
      </section>

      <Section
        id="frontier"
        label="Automation against safety"
        lede={
          run.frontier.flat ? (
            "This frontier is flat: every threshold from 0.50 to 0.99 gives the same actions, because the probabilities are all 0, 0.5 or 1."
          ) : (
            <>
              <p>Lower thresholds automate more; the dashed line is the 1% unsafe ceiling.</p>
              <Disclosure label="How this is measured" variant="inline" className="mt-0.5">
                <p className="text-sm text-ink-2">
                  Each point is one auto_process threshold re-decided over the stored judgments. The
                  1% unsafe ceiling is the one used to pick thresholds on dev sets.
                </p>
              </Disclosure>
            </>
          )
        }
      >
        <FrontierChart
          points={run.frontier.points}
          operating={op.auto_process}
          ceiling={run.frontier.ceiling}
          label={`${run.label} on ${run.dataset}`}
        />
      </Section>

      <div className="mt-6 border-b border-rule">
        <Disclosure id="other-rates" label="Request info and human review" meta="2 rates">
          <div className="grid grid-cols-2 gap-x-3 gap-y-3 md:grid-cols-5">
            <MetricCard label="Request info" rate={m.request_info} />
            <MetricCard label="Human review" rate={m.human_review} />
          </div>
        </Disclosure>
        <Disclosure id="calibration" label="Calibration" meta={`${calibrated.length} charts`}>
          <p className="max-w-prose text-md text-ink-2">
            Accuracy against stated confidence for each judgment. Points below the diagonal are
            over-confident; hollow points hold fewer than 20 cases.
          </p>
          <div className="mt-3">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {DECISIONS.map((d) =>
            run.calibration.decisions[d] ? (
              <ReliabilityDiagram key={d} decision={d} report={run.calibration.decisions[d]} />
            ) : null,
          )}
        </div>
          </div>
        </Disclosure>
        <Disclosure id="compare" label={`All runs on ${dataset.id}`} meta={`${dataset.runs.length} runs`}>
          <TableScroll hint>
          <table className="w-full min-w-[56rem]">
            <thead>
              <tr>
                <Th>Provider</Th>
                <Th align="right">auto_process</Th>
                <Th align="right">n</Th>
                <Th align="right">Correct</Th>
                <Th align="right">95% CI</Th>
                <Th align="right">Automation</Th>
                <Th align="right">Unsafe / auto</Th>
                <Th align="right">95% CI</Th>
              </tr>
            </thead>
            <tbody>
              {dataset.runs.map((r) => (
                <tr key={r.run_id} className={r.run_id === run.run_id ? "bg-paper-2" : "hover:bg-paper-2"}>
                  <Td>
                    <Link href={`/evals/${r.run_id}/`} className="underline decoration-rule-strong hover:decoration-ink">
                      {r.label}
                    </Link>
                  </Td>
                  <Td num>{threshold(r.auto_process)}</Td>
                  <Td num>{r.n}</Td>
                  <Td num>{rateText(r.metrics.correct)}</Td>
                  <Td num className="text-ink-2">{ciText(r.metrics.correct)}</Td>
                  <Td num>{rateText(r.metrics.automation)}</Td>
                  <Td num className={r.metrics.uar.count > 0 ? `font-medium ${UNSAFE_TEXT}` : ""}>
                    {rateText(r.metrics.uar)}
                  </Td>
                  <Td num className="text-ink-2">{ciText(r.metrics.uar)}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableScroll>
        </Disclosure>
      </div>
    </>
  );
}
