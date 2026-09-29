import { DIFF_TEXT } from "@/lib/semantic";
import type { Segment } from "@/lib/wordDiff";

/** Word-diff segments inline: additions as <ins>, removals struck through as <del>. */
export function DiffText({ segments }: { segments: Segment[] }) {
  return (
    <>
      {segments.map((s, i) =>
        s.kind === "same" ? (
          <span key={i}>{s.text}</span>
        ) : s.kind === "add" ? (
          <ins key={i} className={DIFF_TEXT.add}>
            {s.text}
          </ins>
        ) : (
          <del key={i} className={DIFF_TEXT.del}>
            {s.text}
          </del>
        ),
      )}
    </>
  );
}
