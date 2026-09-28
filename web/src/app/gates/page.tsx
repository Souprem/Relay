import type { Metadata } from "next";
import Link from "next/link";

import { CaseEntries, RegressionMetrics } from "@/components/gates/RegressionTable";
import { ShadowCard } from "@/components/gates/ShadowCard";
import { PageHeader, Section } from "@/components/ui/Section";
import { Td, TableScroll, Th } from "@/components/ui/Table";
import { GateVerdict } from "@/components/ui/Verdicts";
import { getGates } from "@/lib/data";
import type { RegressionReport } from "@/lib/types";

export const metadata: Metadata = { title: "Gates" };

function Report({ report }: { report: RegressionReport }) {
  return (
    <article className="min-w-0 border-t border-ink pt-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-lg text-ink">{report.title}</h3>
        <GateVerdict verdict={report.verdict} />
      </div>
      <p className="mt-1 max-w-prose text-md text-ink-2">{report.description}</p>
      <p className="mt-1 break-words font-mono text-label tracking-normal text-ink-3">{report.source}</p>
      <div className="mt-2 grid gap-1 text-sm text-ink-2 md:grid-cols-2">
        <p>
          <span className="text-label font-semibold uppercase text-ink-3">Baseline </span>
          {report.baseline.label}
        </p>
        <p>
          <span className="text-label font-semibold uppercase text-ink-3">Candidate </span>
          {report.candidate.label}
        </p>
      </div>
      <div className="mt-2">
        <RegressionMetrics report={report} />
      </div>
      <p className="num mt-1 text-sm text-ink-2">
        {Object.entries(report.change_counts)
          .map(([k, v]) => `${k} ${v}`)
          .join(" · ")}
      </p>
      <CaseEntries title="NEWLY UNSAFE" entries={report.newly_unsafe} tone="unsafe" />
      {report.waived.length ? (
        <div className="mt-2">
          <p className="font-mono text-sm font-medium text-ink-2">WAIVED ({report.waived.length})</p>
          {report.waived.map((w) => (
            <pre key={w.case_id} className="mt-1 overflow-x-auto whitespace-pre-wrap bg-paper-2 p-1.5 text-label tracking-normal text-ink">
              {JSON.stringify(w.waiver, null, 2)}
            </pre>
          ))}
        </div>
      ) : null}
      <CaseEntries title="STILL UNSAFE, also unsafe in the baseline" entries={report.still_unsafe} />
      <CaseEntries title="UNSAFE RESOLVED" entries={report.unsafe_resolved} />
      <p className="mt-2 font-mono text-sm text-ink">
        REGRESSION GATE: {report.verdict}
        {report.failures.length ? ` — ${report.failures.join("; ")}` : ""}
      </p>
    </article>
  );
}

export default function GatesPage() {
  const data = getGates();
  const reports = Object.fromEntries(data.regressions.map((r) => [r.key, r]));
  const passed = data.gates.filter((g) => g.verdict === "PASS").length;
  const skipped = data.gates.filter((g) => g.verdict === "SKIPPED").length;
  return (
    <>
      <PageHeader eyebrow="Gates" title="How do you know a change made it safer?">
        <p>
          Every change is replayed against an accepted baseline on the same frozen cases. The gate
          fails when a case that was handled safely becomes an unsafe automation, unless a reviewer
          has signed a waiver for it. CI runs these gates on every push, with no provider keys.
        </p>
      </PageHeader>

      <Section
        id="ci"
        label={`The ${data.gates.length} committed gates`}
        lede={
          <>
            {passed} pass{skipped ? `; ${skipped} need generated datasets that are not on this machine and are skipped` : ""}.
            A reproduce gate replays stored decisions through today&rsquo;s engine and fails on any
            difference; a compare gate diffs two configurations.
          </>
        }
      >
        <TableScroll>
          <table className="w-full min-w-[52rem]">
            <thead>
              <tr>
                <Th>Gate</Th>
                <Th>Kind</Th>
                <Th>Dataset</Th>
                <Th>Verdict</Th>
                <Th align="right">Newly unsafe</Th>
                <Th align="right">Still unsafe</Th>
                <Th align="right">Waived</Th>
                <Th align="right">Regressed</Th>
              </tr>
            </thead>
            <tbody>
              {data.gates.map((g) => (
                <tr key={g.name} className="hover:bg-paper-2">
                  <Td className="font-mono text-sm">{g.name}</Td>
                  <Td className="text-sm text-ink-2">{g.kind}</Td>
                  <Td className="font-mono text-sm text-ink-2">{g.dataset.replace("evals/", "")}</Td>
                  <Td>
                    <GateVerdict verdict={g.verdict} />
                  </Td>
                  <Td num>{g.newly_unsafe ?? "—"}</Td>
                  <Td num>{g.still_unsafe ?? "—"}</Td>
                  <Td num>{g.waived ?? "—"}</Td>
                  <Td num>{g.regressed ?? "—"}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableScroll>
        <p className="mt-1 text-sm text-ink-3">
          Still unsafe counts a baseline&rsquo;s own unsafe automations; they are reported but never
          fail a gate.
        </p>
      </Section>

      <Section
        id="fail"
        label="A gate that fails on purpose"
        lede={
          <>
            Lowering Jev&rsquo;s threshold from the recorded 0.95 to its dev-selected 0.89 automates
            11 more gold cases. One of them is{" "}
            <Link href="/cases/GOLD-TMP-17/" className="font-mono underline hover:text-ink">
              GOLD-TMP-17
            </Link>
            , an interrupted methotrexate course that needs a person. The gate fails; a signed waiver
            is the only way through, and the waived case stays listed.
          </>
        }
      >
        <div className="grid gap-6">
          <Report report={reports["gold-fail"]} />
          <Report report={reports["gold-waiver"]} />
        </div>
      </Section>

      <Section
        id="shadow"
        label="Shadow rollout"
        lede={
          <>
            A candidate runs beside the live configuration. Its actions are recorded and never
            applied: the case-status file is hashed before and after, and the run only reports{" "}
            <span className="font-mono text-sm">case state unchanged (verified)</span> when the hashes
            match. The promotion check is the regression gate, so it needs ground truth and is
            evaluation-only.
          </>
        }
      >
        <div className="grid gap-6 lg:grid-cols-2">
          {data.shadow.map((s) => (
            <ShadowCard key={s.key} demo={s} />
          ))}
        </div>
      </Section>

      <Section id="committed" label="Other committed gate reports">
        <div className="grid gap-6">
          {["gold-jev-vs-claude", "holdout-adoption", "stale-to-aware"].map((k) =>
            reports[k] ? <Report key={k} report={reports[k]} /> : null,
          )}
        </div>
        <p className="mt-3 text-sm text-ink-2">
          Methods:{" "}
          <a href={data.links.regression} className="underline hover:text-ink">
            regression gate
          </a>{" "}
          and{" "}
          <a href={data.links.shadow} className="underline hover:text-ink">
            shadow mode
          </a>{" "}
          in RESULTS.md.
        </p>
      </Section>
    </>
  );
}
