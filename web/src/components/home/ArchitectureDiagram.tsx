import { DECISION_LABELS, prob } from "@/lib/format";
import { ACTION_VAR, GATE_ACTION } from "@/lib/semantic";
import type { Action, DecisionView, GateRow } from "@/lib/types";

const ACTIONS: Action[] = ["AUTO_PROCESS", "REQUEST_INFO", "HUMAN_REVIEW"];
const DOCS = ["physician note", "medication history", "lab report", "fax cover", "insurance card"];

function barValue(d: DecisionView): number {
  return d.kind === "choice" ? (d.probability ?? 0) : (d.p_yes ?? 0);
}

function barText(d: DecisionView): string {
  return d.kind === "choice" ? `${d.answer} ${prob(d.probability)}` : prob(d.p_yes);
}

interface Props {
  caseId: string;
  providerLabel: string;
  decisions: DecisionView[];
  gates: GateRow[];
  action: Action;
}

function Arrow({ x1, x2, y }: { x1: number; x2: number; y: number }) {
  return (
    <g stroke="var(--ink-3)" fill="none">
      <line x1={x1} x2={x2 - 1} y1={y} y2={y} />
      <path d={`M${x2 - 6},${y - 4} L${x2},${y} L${x2 - 6},${y + 4}`} />
    </g>
  );
}

function StageTitle({ x, y, n, title }: { x: number; y: number; n: string; title: string }) {
  return (
    <text x={x} y={y} fontSize="11" fill="var(--ink-2)" fontFamily="var(--font-sans)" letterSpacing="0.08em">
      <tspan fontWeight="600">{n}</tspan>
      <tspan dx="6" fontWeight="600">
        {title.toUpperCase()}
      </tspan>
    </text>
  );
}

/** The pipeline, drawn with one real case moving through it (desktop: left to right). */
function Wide({ caseId, providerLabel, decisions, gates, action }: Props) {
  const top = 44;
  return (
    <svg viewBox="0 0 1152 300" role="img" aria-labelledby="arch-title" className="hidden h-auto w-full font-mono md:block">
      <title id="arch-title">
        {`How a case moves through Relay, shown with ${caseId} and ${providerLabel}: documents, five judgments with probabilities, the policy engine's gates in order, and the action.`}
      </title>
      {/* 1 documents */}
      <StageTitle x={0} y={16} n="1" title="Case documents" />
      {DOCS.map((d, i) => (
        <g key={d}>
          <rect x={0.5} y={top + i * 40 + 0.5} width={176} height={30} fill="var(--paper)" stroke="var(--rule-strong)" />
          <text x={12} y={top + i * 40 + 20} fontSize="12" fill="var(--ink)">
            {d}
          </text>
        </g>
      ))}
      <Arrow x1={184} x2={224} y={144} />
      {/* 2 judgments */}
      <StageTitle x={232} y={16} n="2" title="Narrow judgments" />
      <text x={232} y={34} fontSize="11" fill="var(--ink-3)">
        {providerLabel} on {caseId}
      </text>
      {decisions.map((d, i) => {
        const y = top + i * 40;
        const w = 150;
        return (
          <g key={d.id}>
            <text x={232} y={y + 10} fontSize="11" fill="var(--ink-2)" fontFamily="var(--font-sans)">
              {DECISION_LABELS[d.id] ?? d.id}
            </text>
            <rect x={232.5} y={y + 16.5} width={w} height={7} fill="var(--paper-2)" stroke="var(--rule)" />
            <rect x={233} y={y + 17} width={Math.max(0, barValue(d) * w - 1)} height={6} fill="var(--ink-2)" />
            <text x={232 + w + 8} y={y + 24} fontSize="11" fill="var(--ink)">
              {barText(d)}
            </text>
          </g>
        );
      })}
      <Arrow x1={488} x2={528} y={144} />
      {/* 3 policy engine */}
      <StageTitle x={536} y={16} n="3" title="Policy engine, in order" />
      <text x={536} y={34} fontSize="11" fill="var(--ink-3)">
        the first gate that fires decides
      </text>
      {gates.map((g, i) => {
        const y = top + 4 + i * 30;
        const fired = g.status === "FIRED";
        const color = fired ? ACTION_VAR[GATE_ACTION[g.gate] ?? "HUMAN_REVIEW"] : "var(--ink-3)";
        return (
          <g key={g.gate}>
            {i < gates.length - 1 ? (
              <line
                x1={544}
                x2={544}
                y1={y + 6}
                y2={y + 30 - 6}
                stroke="var(--rule-strong)"
                strokeDasharray={g.status === "passed" && gates[i + 1].status !== "not reached" ? undefined : "2 3"}
              />
            ) : null}
            {fired ? (
              <rect x={539} y={y - 5} width={10} height={10} fill={color} />
            ) : (
              <circle
                cx={544}
                cy={y}
                r={4.5}
                fill="var(--paper)"
                stroke={g.status === "passed" ? "var(--ink-2)" : "var(--ink-3)"}
                strokeDasharray={g.status === "not reached" ? "2 2" : undefined}
              />
            )}
            <text
              x={560}
              y={y + 4}
              fontSize="12"
              fill={g.status === "not reached" ? "var(--ink-3)" : "var(--ink)"}
              fontWeight={fired ? 600 : 400}
            >
              {g.gate}
            </text>
            <text x={700} y={y + 4} fontSize="11" fill={fired ? color : "var(--ink-3)"} fontWeight={fired ? 600 : 400}>
              {fired ? "FIRED" : g.status}
            </text>
          </g>
        );
      })}
      <Arrow x1={792} x2={832} y={144} />
      {/* 4 action */}
      <StageTitle x={840} y={16} n="4" title="One action" />
      {ACTIONS.map((a, i) => {
        const chosen = a === action;
        const y = top + 20 + i * 56;
        return (
          <g key={a}>
            <rect
              x={840.5}
              y={y + 0.5}
              width={200}
              height={36}
              fill={chosen ? "var(--paper-2)" : "var(--paper)"}
              stroke={chosen ? ACTION_VAR[a] : "var(--rule)"}
              strokeWidth={chosen ? 1.5 : 1}
            />
            <rect x={852} y={y + 14} width={8} height={8} fill={ACTION_VAR[a]} />
            <text x={870} y={y + 22} fontSize="12" fill={chosen ? ACTION_VAR[a] : "var(--ink-3)"} fontWeight={chosen ? 600 : 400}>
              {a}
            </text>
          </g>
        );
      })}
      <text x={840} y={top + 200} fontSize="11" fill="var(--ink-3)">
        every decision is written to a trace:
      </text>
      <text x={840} y={top + 218} fontSize="11" fill="var(--ink-2)">
        replay · regression gate · shadow
      </text>
    </svg>
  );
}

/** The same pipeline stacked vertically for narrow screens. */
function Narrow({ caseId, providerLabel, decisions, gates, action }: Props) {
  const rows: { title: string; lines: string[] }[] = [
    { title: "1 Case documents", lines: [DOCS.slice(0, 2).join(" · "), DOCS.slice(2).join(" · ")] },
    {
      title: `2 Judgments (${providerLabel}, ${caseId})`,
      lines: decisions.map((d) => `${(DECISION_LABELS[d.id] ?? d.id).padEnd(24)}${barText(d)}`),
    },
    {
      title: "3 Policy engine",
      lines: gates.map((g) => `${g.gate.padEnd(18)}${g.status}`),
    },
    { title: "4 Action", lines: [action] },
  ];
  let y = 0;
  const blocks = rows.map((r) => {
    const block = { ...r, y };
    y += 28 + r.lines.length * 18 + 20;
    return block;
  });
  return (
    <svg viewBox={`0 0 340 ${y}`} role="img" aria-label={`How ${caseId} moves through Relay`} className="block h-auto w-full font-mono md:hidden">
      {blocks.map((b, i) => (
        <g key={b.title}>
          <text x={0} y={b.y + 12} fontSize="11" fontWeight="600" fill="var(--ink-2)" fontFamily="var(--font-sans)" letterSpacing="0.06em">
            {b.title.toUpperCase()}
          </text>
          {b.lines.map((line, j) => (
            <text
              key={j}
              x={0}
              y={b.y + 32 + j * 18}
              fontSize="11.5"
              style={{ whiteSpace: "pre" }}
              fill={i === 3 ? ACTION_VAR[action] : "var(--ink)"}
              fontWeight={i === 3 ? 600 : 400}
            >
              {line}
            </text>
          ))}
          {i < blocks.length - 1 ? (
            <line x1={4} x2={4} y1={b.y + 36 + b.lines.length * 18 - 10} y2={blocks[i + 1].y - 2} stroke="var(--rule-strong)" />
          ) : null}
        </g>
      ))}
    </svg>
  );
}

export function ArchitectureDiagram(props: Props) {
  return (
    <div>
      <Wide {...props} />
      <Narrow {...props} />
    </div>
  );
}
