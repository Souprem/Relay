import type { Metadata } from "next";
import Link from "next/link";

import { LineChart } from "@/components/charts/LineChart";
import { RegressionMetrics } from "@/components/gates/RegressionTable";
import { Disclosure } from "@/components/ui/Disclosure";
import { PageHeader, Section } from "@/components/ui/Section";
import { Td, TableScroll, Th } from "@/components/ui/Table";
import { GateVerdict } from "@/components/ui/Verdicts";
import { getExperiments } from "@/lib/data";
import { pct, pyFixed, rateText, roundInt } from "@/lib/format";
import { compareHref } from "@/lib/questions";
import type { AblationRow } from "@/lib/types";
import { UNSAFE_TEXT } from "@/lib/semantic";

export const metadata: Metadata = { title: "Experiments" };

const TAG_LABELS: Record<string, string> = {
  interrupted: "Interrupted, then restarted",
  old_course: "Ended over 12 months earlier",
  other: "Everything else",
};

function MethodLink({ href }: { href: string }) {
  return (
    <p className="mt-2 text-sm">
      <a href={href} className="text-ink-2 underline hover:text-ink">
        Method and full output in RESULTS.md
      </a>
    </p>
  );
}

function frac([k, n]: [number, number]): string {
  return `${k}/${n} (${pct(n ? k / n : null)})`;
}

function ablationStatements(rows: AblationRow[]) {
  const me = rows.filter((r) => r.ablation === "missing_evidence");
  const meAutomationUnchanged = me.every((r) => r.automation.baseline.count === r.automation.ablated.count);
  const newly = rows.filter((r) => r.newly_unsafe.length > 0);
  const newlyCases = [...new Set(newly.flatMap((r) => r.newly_unsafe))].sort();
  const generatedNewly = newly.filter((r) => r.dataset !== "gold-v0.1").length;
  return { meAutomationUnchanged, meRuns: me.length, newlyCases, generatedNewly };
}

export default function ExperimentsPage() {
  const x = getExperiments();
  const holdout = x.qv03.reports.holdout;
  const dev = x.qv03.reports.dev;
  const gold = x.qv03.reports.gold;
  const shift = x.shift.regression;
  const sizes = x.parallelism.sizes;
  const abl = ablationStatements(x.ablation.rows);
  const claudeNote = x.ablation.rows.find((r) => r.note)?.note ?? null;
  return (
    <>
      <PageHeader eyebrow="Experiments" title="Four changes, each measured before it was believed">
        <p>
          Each section states what was tried, the rule fixed in advance, and what the committed
          runs show, including the results that did not go the way we hoped.
        </p>
      </PageHeader>

      <Section
        id="qv03"
        label={x.qv03.title}
        title={`${holdout.baseline.correct.count} → ${holdout.candidate.correct.count} correct of ${holdout.n} on the holdout, with ${holdout.candidate.uar.count}/${holdout.candidate.uar.n} unsafe automations.`}
        lede="q-v0.3 adds questions about paused and restarted methotrexate courses; the gain is concentrated in interrupted courses."
      >
        <Disclosure label="Show details" hashIds={["qv03"]} variant="inline" className="-mt-1">
          <div className="max-w-prose text-md text-ink-2">
            <>
            q-v0.2 has one start and one end date, so it cannot express a paused methotrexate course.
            q-v0.3 adds seven questions about pauses and restarts. It was adopted on gen-v0.3-dev (
            {dev.baseline.correct.count} → {dev.candidate.correct.count} of {dev.n} correct, gate{" "}
            {dev.verdict}) and then run once on gen-v0.3-holdout.{" "}
            <Link href={compareHref("q-v0.2...q-v0.3")} className="font-mono text-ink underline decoration-rule-strong hover:decoration-ink">
              Compare the question sets&nbsp;→
            </Link>
          </>
          </div>
          <div className="mt-3">
        <RegressionMetrics report={holdout} />
        <p className="mt-1 text-sm text-ink-3">
          Baseline: {holdout.baseline.label}. Candidate: {holdout.candidate.label}.
        </p>
        <h3 className="mt-4 text-label font-semibold uppercase text-ink-2">Where the gain comes from: step-therapy accuracy by course</h3>
        {x.qv03.course_split.map((s) =>
          s.status === "ok" && s.tags ? (
            <div key={s.dataset} className="mt-2">
              <p className="font-mono text-sm text-ink-2">{s.dataset} · n {s.n}</p>
              <TableScroll>
                <table className="mt-1 w-full min-w-[36rem]">
                  <thead>
                    <tr>
                      <Th>Course</Th>
                      <Th align="right">Cases</Th>
                      <Th align="right">q-v0.2</Th>
                      <Th align="right">q-v0.3</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {s.tags.map((t) => (
                      <tr key={t.tag}>
                        <Td>{TAG_LABELS[t.tag] ?? t.tag}</Td>
                        <Td num>{t.n}</Td>
                        <Td num>{frac(t.q_v0_2)}</Td>
                        <Td num>{frac(t.q_v0_3)}</Td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableScroll>
            </div>
          ) : (
            <p key={s.dataset} className="mt-2 text-sm text-ink-2">
              {s.dataset}: not shown. {s.note}.
            </p>
          ),
        )}
        <p className="mt-2 max-w-prose text-md text-ink-2">
          The gain is concentrated in interrupted courses. On old and other courses q-v0.3 is slightly
          worse than q-v0.2. On gold, which is not a blind test here, the gate fails:{" "}
          {gold.newly_unsafe.map((e) => (
            <Link key={e.case_id} href={`/cases/${e.case_id}/`} className="font-mono underline hover:text-ink">
              {e.case_id}
            </Link>
          ))}{" "}
          becomes newly unsafe at the lower 0.81 threshold.
        </p>
        <MethodLink href={x.qv03.link} />
          </div>
        </Disclosure>
      </Section>

      <Section
        id="shift"
        label={x.shift.title}
        title={`Stale: ${shift.baseline.uar.count}/${shift.baseline.uar.n} unsafe automations. Aware: ${shift.candidate.uar.count}/${shift.candidate.uar.n}.`}
        lede="The same stored Jev answers, composed under the old policy and under immunara-v0.2, which adds a 12-month recency rule."
      >
        <Disclosure label="Show details" hashIds={["shift"]} variant="inline" className="-mt-1">
          <div className="max-w-prose text-md text-ink-2">
            {"immunara-v0.2 adds one rule: the qualifying methotrexate course must have been ongoing or ended within 12 months of the request. The same stored Jev answers on gen-v0.3-shift were composed twice: under the old policy (stale) and under the new one (aware)."}
          </div>
          <div className="mt-3">
        <TableScroll hint>
          <table className="w-full min-w-[40rem]">
            <thead>
              <tr>
                <Th>Composition</Th>
                <Th align="right">Correct action</Th>
                <Th align="right">Automation</Th>
                <Th align="right">Unsafe / auto</Th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <Td>Stale, immunara-v0.1</Td>
                <Td num>{rateText(shift.baseline.correct)}</Td>
                <Td num>{rateText(shift.baseline.automation)}</Td>
                <Td num className={`font-medium ${UNSAFE_TEXT}`}>{rateText(shift.baseline.uar)}</Td>
              </tr>
              <tr>
                <Td>Aware, immunara-v0.2</Td>
                <Td num>{rateText(shift.candidate.correct)}</Td>
                <Td num>{rateText(shift.candidate.automation)}</Td>
                <Td num>{rateText(shift.candidate.uar)}</Td>
              </tr>
              <tr>
                <Td className="text-ink-2">Rules, no recency rule</Td>
                <Td num className="text-ink-2">
                  {x.shift.rules.correct}/{x.shift.rules.n}
                </Td>
                <Td num className="text-ink-2">
                  {x.shift.rules.automation}/{x.shift.rules.n}
                </Td>
                <Td num className="text-ink-2">
                  {x.shift.rules.unsafe}/{x.shift.rules.automation}
                </Td>
              </tr>
            </tbody>
          </table>
        </TableScroll>
        <p className="mt-2 max-w-prose text-md text-ink-2">
          The stale → aware gate is <GateVerdict verdict={shift.verdict} /> with{" "}
          {shift.newly_unsafe.length} newly unsafe and {shift.regressed.length} regressed, and the
          shadow rollout of aware against stale is <GateVerdict verdict={x.shift.shadow_decision} />.
          Being aware costs {shift.baseline.automation.count - shift.candidate.automation.count}{" "}
          automations out of {shift.n}.
        </p>
        <MethodLink href={x.shift.link} />
          </div>
        </Disclosure>
      </Section>

      <Section
        id="parallelism"
        label={x.parallelism.title}
        title={`p50 latency goes from ${roundInt(sizes[0].p50_ms)} to ${roundInt(sizes[sizes.length - 1].p50_ms)} ms as questions per call go from ${sizes[0].size} to ${sizes[sizes.length - 1].size}.`}
        lede="Narrow decisions are cheap to add; cost per case grows with tokens."
      >
        <Disclosure label="Show details" hashIds={["parallelism"]} variant="inline" className="-mt-1">
          <div className="max-w-prose text-md text-ink-2">
            {`${x.parallelism.cases} ${x.parallelism.dataset} cases were sent to ${x.parallelism.model} with 1, 5, 10 and 20 questions in one call. Narrow decisions are cheap to add; cost per case grows with tokens.`}
          </div>
          <div className="mt-3">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <LineChart
            title="Latency against questions per call"
            xs={sizes.map((s) => s.size)}
            series={[
              { name: "p95", values: sizes.map((s) => s.p95_ms) },
              { name: "p50", values: sizes.map((s) => s.p50_ms), emphasis: true },
            ]}
            xLabel="Questions per call"
            yLabel="Latency"
            yUnit="ms"
            table={false}
          />
          <TableScroll>
            <table className="w-full">
              <thead>
                <tr>
                  <Th align="right">Questions</Th>
                  <Th align="right">p50 ms</Th>
                  <Th align="right">p95 ms</Th>
                  <Th align="right">Tokens</Th>
                  <Th align="right">$ / case</Th>
                </tr>
              </thead>
              <tbody>
                {sizes.map((s) => (
                  <tr key={s.size}>
                    <Td num>{s.size}</Td>
                    <Td num>{roundInt(s.p50_ms)}</Td>
                    <Td num>{roundInt(s.p95_ms)}</Td>
                    <Td num>{roundInt(s.input_tokens_mean)}</Td>
                    <Td num>{pyFixed(Number(s.cost_per_case_usd), 6)}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>
        </div>
        <p className="mt-2 max-w-prose text-md text-ink-2">
          The p95 at 20 questions rests on three slow calls out of 40, so it is not a stable estimate.
        </p>
        <MethodLink href={x.parallelism.link} />
          </div>
        </Disclosure>
      </Section>

      <Section
        id="ablation"
        label={x.ablation.title}
        title={
          <>
            Removing contradiction detection makes{" "}
            {abl.newlyCases.map((id, i) => (
              <span key={id}>
                {i ? " and " : ""}
                <span className="whitespace-nowrap">{id}</span>
              </span>
            ))}{" "}
            newly unsafe for every model provider on gold.
          </>
        }
        lede="Each committed run was re-decided with the contradiction gate, the missing-evidence gate, or both disabled."
      >
        <Disclosure label="Show details" hashIds={["ablation"]} variant="inline" className="-mt-1">
          <div className="max-w-prose text-md text-ink-2">
            <>
            The null results:{" "}
            {abl.generatedNewly === 0 ? "no ablation creates a newly unsafe case on the generated sets" : `${abl.generatedNewly} generated-set ablations create newly unsafe cases`}
            , and{" "}
            {abl.meAutomationUnchanged
              ? `removing the missing-evidence gate changes no automation in any of the ${abl.meRuns} runs`
              : "removing the missing-evidence gate changes automation in some runs"}
            .{" "}
            {claudeNote ? `The claude-150 rows: ${claudeNote}` : null}
          </>
          </div>
          <div className="mt-3">
        <TableScroll hint>
          <table className="w-full min-w-[68rem]">
            <thead>
              <tr>
                <Th>Dataset</Th>
                <Th>Run</Th>
                <Th>Gate removed</Th>
                <Th>Verdict</Th>
                <Th align="right">Actions changed</Th>
                <Th align="right">Automation</Th>
                <Th align="right">Unsafe / auto</Th>
                <Th>Newly unsafe</Th>
              </tr>
            </thead>
            <tbody>
              {x.ablation.rows.map((r) => (
                <tr key={`${r.dataset}-${r.run}-${r.ablation}`} className="hover:bg-paper-2">
                  <Td className="whitespace-nowrap font-mono text-sm">{r.dataset}</Td>
                  <Td className="whitespace-nowrap font-mono text-sm">
                    {r.run}
                    {r.note ? (
                      <span className="block font-sans text-label tracking-normal text-ink-3" title={r.note}>
                        150-case sample
                      </span>
                    ) : null}
                  </Td>
                  <Td className="whitespace-nowrap font-mono text-sm">{r.ablation}</Td>
                  <Td>
                    <GateVerdict verdict={r.verdict} />
                  </Td>
                  <Td num>
                    {r.actions_changed}/{r.n}
                  </Td>
                  <Td num>
                    {r.automation.baseline.count} → {r.automation.ablated.count}
                  </Td>
                  <Td num className="whitespace-nowrap">
                    {r.uar.baseline.count}/{r.uar.baseline.n} → {r.uar.ablated.count}/{r.uar.ablated.n}
                  </Td>
                  <Td className="font-mono text-sm">
                    {r.newly_unsafe.length ? <span className={UNSAFE_TEXT}>{r.newly_unsafe.join(", ")}</span> : <span className="text-ink-3">none</span>}
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableScroll>
        <MethodLink href={x.ablation.link} />
          </div>
        </Disclosure>
      </Section>
    </>
  );
}
