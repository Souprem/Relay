import type { CaseDetail } from "@/lib/types";

const KIND_LABELS: Record<string, string> = {
  physician_note: "Physician note",
  medication_history: "Medication history",
  lab_report: "Lab report",
  fax_cover: "Fax cover",
  insurance_card: "Insurance card",
  other: "Other document",
};

/** What the providers were given: the request and every document, as submitted. */
export function CaseFacts({ detail }: { detail: CaseDetail }) {
  const { input } = detail;
  const facts: [string, string][] = [
    ["As of", input.as_of_date],
    ["Patient", `${input.patient.age} years, ${input.patient.state}`],
    ["Request", `${input.medication.name} for ${input.medication.indication}`],
    ["Insurance", `${input.insurance.payer}, ${input.insurance.plan}${input.insurance.member_id ? ` · ${input.insurance.member_id}` : ""}`],
    ["Policy", input.policy_id],
  ];
  return (
    <div>
      <dl className="grid grid-cols-[6rem_minmax(0,1fr)] gap-x-2 gap-y-0.5 text-base">
        {facts.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-ink-3">{k}</dt>
            <dd className="text-ink">{v}</dd>
          </div>
        ))}
        <dt className="text-ink-3">Inputs</dt>
        <dd className="num truncate text-sm text-ink-2" title={input.content_hash}>
          {input.content_hash.slice(0, 19)}…
        </dd>
      </dl>
      <h2 className="mt-4 text-label font-semibold uppercase text-ink-2">
        Documents <span className="num font-normal text-ink-3">{input.documents.length}</span>
      </h2>
      <div className="mt-1 grid gap-2">
        {input.documents.map((doc) => (
          <article key={doc.id} className="border-t border-rule-strong pt-1">
            <header className="flex items-baseline justify-between gap-2">
              <h3 className="text-base font-medium text-ink">{KIND_LABELS[doc.kind] ?? doc.kind}</h3>
              <span className="font-mono text-label tracking-normal text-ink-3">{doc.id}</span>
            </header>
            <pre
              tabIndex={0}
              className="mt-1 max-h-[22rem] overflow-auto whitespace-pre-wrap break-words bg-paper-2 p-1.5 text-sm text-ink"
            >
              {doc.text.trim()}
            </pre>
          </article>
        ))}
      </div>
    </div>
  );
}
