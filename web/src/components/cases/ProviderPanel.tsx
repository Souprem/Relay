"use client";

import { ActionBadge } from "@/components/ui/ActionBadge";
import { GatePath } from "@/components/ui/GatePath";
import { ProbabilityBar } from "@/components/ui/ProbabilityBar";
import { VerdictLabel } from "@/components/ui/Verdict";
import { DECISION_LABELS, prob, threshold } from "@/lib/format";
import { ACTION_SWATCH } from "@/lib/semantic";
import type { CaseDetail, DecisionView, ProviderResult } from "@/lib/types";
import { useQueryString } from "@/lib/useQueryString";

function decisionBar(d: DecisionView) {
  const label = DECISION_LABELS[d.id] ?? d.id;
  if (d.kind === null) {
    return <ProbabilityBar key={d.id} label={label} value={null} ticks={d.ticks} />;
  }
  if (d.kind === "choice") {
    const others = Object.entries(d.probabilities ?? {})
      .filter(([k, v]) => k !== d.answer && v > 0)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([k, v]) => `${k} ${v.toFixed(2)}`)
      .join(" · ");
    return (
      <ProbabilityBar
        key={d.id}
        label={label}
        value={d.probability ?? null}
        valueText={`${d.answer} ${prob(d.probability)}`}
        ticks={d.answer === "NONE" ? [] : d.ticks}
        detail={others ? `others: ${others}` : undefined}
      />
    );
  }
  return <ProbabilityBar key={d.id} label={label} value={d.p_yes ?? null} ticks={d.ticks} />;
}

function SubHead({ children }: { children: React.ReactNode }) {
  return <h3 className="text-label font-semibold uppercase text-ink-2">{children}</h3>;
}

function ProviderView({ p }: { p: ProviderResult }) {
  return (
    <div>
      <p className="font-mono text-label tracking-normal text-ink-3">
        {p.run_id} · {p.question_set} · {p.policy}
      </p>
      <p className="mt-0.5 text-sm text-ink-2">
        <span className="num text-ink">auto_process {threshold(Number(p.thresholds.auto_process))}</span>,{" "}
        {p.operating_point_source}.{p.note ? ` ${p.note}` : ""}
      </p>

      <div className="mt-3">
        <SubHead>Judgments</SubHead>
        <p className="mt-0.5 text-sm text-ink-3">
          p_yes for yes/no questions; ticks are the thresholds a gate compares each one with.
        </p>
        <div className="mt-2 grid gap-2">{p.decisions.map(decisionBar)}</div>
      </div>

      <div className="mt-4">
        <SubHead>Gate path</SubHead>
        <div className="mt-2">
          <GatePath gates={p.gates} />
        </div>
      </div>

      <div className="mt-3">
        <SubHead>Action</SubHead>
        <div className="mt-1 text-lg">
          <ActionBadge action={p.action} />
        </div>
        <ul className="mt-1 grid gap-0.5 font-mono text-sm text-ink-2">
          {p.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function EvaluationOnly({ detail, p }: { detail: CaseDetail; p: ProviderResult }) {
  const gt = detail.ground_truth;
  const facts: [string, string][] = [
    ["diagnosis_supported", String(gt.diagnosis_supported)],
    ["step_therapy_satisfied", String(gt.step_therapy_satisfied)],
    ["documentation_complete", String(gt.documentation_complete)],
    ["contradiction_present", String(gt.contradiction_present)],
    ["missing_evidence", gt.missing_evidence],
  ];
  return (
    <aside aria-label="Evaluation only" className="mt-4 border border-dashed border-rule-strong p-2">
      <p className="text-label font-semibold uppercase text-ink-2">Evaluation only · never shown to the engine</p>
      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5">
        <span className="text-sm text-ink-3">Expected</span>
        <ActionBadge action={gt.expected_action} />
        <span className="text-sm text-ink-3">{p.label}:</span>
        <VerdictLabel verdict={p.verdict} />
      </div>
      <dl className="mt-2 grid grid-cols-[minmax(0,1fr)_auto] gap-x-2 font-mono text-sm">
        {facts.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-ink-2">{k}</dt>
            <dd className="text-right text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      {gt.notes ? <p className="mt-2 text-sm text-ink-2">{gt.notes}</p> : null}
    </aside>
  );
}

/** The provider switcher: one run's judgments, gate path and action for this case. */
export function ProviderPanel({ detail }: { detail: CaseDetail }) {
  const [query, setQuery] = useQueryString();
  const wanted = new URLSearchParams(query).get("provider");
  const selected = detail.providers.find((p) => p.slug === wanted) ?? detail.providers[0];

  function choose(slug: string) {
    const params = new URLSearchParams(query);
    if (slug === detail.providers[0].slug) params.delete("provider");
    else params.set("provider", slug);
    setQuery(params.toString());
  }

  return (
    <div>
      <div role="tablist" aria-label="Provider" className="flex flex-wrap gap-x-0.5 gap-y-1 border-b border-rule">
        {detail.providers.map((p) => {
          const active = p.slug === selected.slug;
          return (
            <button
              key={p.slug}
              type="button"
              role="tab"
              id={`tab-${p.slug}`}
              aria-selected={active}
              aria-controls="provider-panel"
              onClick={() => choose(p.slug)}
              className={`-mb-px flex items-center gap-1 border-b-2 px-1 py-1 text-base transition-colors ${
                active ? "border-ink text-ink" : "border-transparent text-ink-2 hover:text-ink"
              }`}
            >
              <span aria-hidden="true" className={`inline-block size-1 ${ACTION_SWATCH[p.action]}`} />
              {p.label}
              {p.verdict === "UNSAFE" ? <span className="font-mono text-label tracking-normal text-unsafe">UNSAFE</span> : null}
            </button>
          );
        })}
      </div>
      <div role="tabpanel" id="provider-panel" aria-labelledby={`tab-${selected.slug}`} className="pt-2">
        <ProviderView p={selected} />
        <EvaluationOnly detail={detail} p={selected} />
      </div>
    </div>
  );
}
