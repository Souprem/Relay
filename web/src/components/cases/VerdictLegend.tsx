import { VerdictCell } from "@/components/ui/Verdict";

/** How to read a provider cell: the action it took, and what the background says about it. */
export function VerdictLegend() {
  return (
    <dl className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-2">
      <div className="flex items-center gap-1">
        <dt>
          <VerdictCell action="AUTO_PROCESS" verdict="correct" />
        </dt>
        <dd>correct</dd>
      </div>
      <div className="flex items-center gap-1">
        <dt>
          <VerdictCell action="HUMAN_REVIEW" verdict="wrong-safe" />
        </dt>
        <dd>wrong, but a person or the submitter sees it</dd>
      </div>
      <div className="flex items-center gap-1">
        <dt>
          <VerdictCell action="AUTO_PROCESS" verdict="UNSAFE" />
        </dt>
        <dd>automated a case that needed review or information</dd>
      </div>
    </dl>
  );
}
