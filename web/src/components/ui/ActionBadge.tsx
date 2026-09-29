import { ACTION_SWATCH, ACTION_TEXT } from "@/lib/semantic";
import type { Action } from "@/lib/types";

/** An engine action, named as the engine names it, with its colour swatch. */
export function ActionBadge({ action, size = "base" }: { action: Action; size?: "sm" | "base" }) {
  return (
    <span
      className={`inline-flex items-center gap-0.5 font-mono font-medium ${ACTION_TEXT[action]} ${
        size === "sm" ? "text-label tracking-normal" : "text-sm"
      }`}
      data-action={action}
    >
      <span aria-hidden="true" className={`inline-block size-1 rounded-sm ${ACTION_SWATCH[action]}`} />
      {action}
    </span>
  );
}
