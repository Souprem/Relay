"use client";

import { useEffect, useRef } from "react";

function hashName(): string {
  const hash = window.location.hash.slice(1);
  if (!hash) return "";
  try {
    return decodeURIComponent(hash);
  } catch {
    return hash;
  }
}

/**
 * Content kept one click away, on a native <details>: it works without JavaScript, the browser's
 * find-in-page still reaches it, and the summary is a real focusable control. A URL hash that
 * names an element inside it (or one of `hashIds`, such as the id of the section it belongs to)
 * opens it on load and on every hash change, so deep links keep working.
 */
export function Disclosure({
  label,
  meta,
  id,
  hashIds,
  variant = "section",
  className = "",
  children,
}: {
  /** The summary text: what is inside, e.g. "Calibration". */
  label: React.ReactNode;
  /** A quiet count or qualifier after the label, e.g. "5 charts". */
  meta?: React.ReactNode;
  id?: string;
  /** Hash targets outside the disclosure that should also open it. */
  hashIds?: string[];
  /** section: a full-width row with a rule above; inline: a small "show more" control. */
  variant?: "section" | "inline";
  className?: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDetailsElement>(null);
  const extra = (hashIds ?? []).join(" ");

  useEffect(() => {
    const details = ref.current;
    if (!details) return;
    const ids = extra ? extra.split(" ") : [];
    function openForHash() {
      if (!details || details.open) return;
      const name = hashName();
      if (!name) return;
      const target = document.getElementById(name);
      const inside = target !== null && (target === details || details.contains(target));
      if (!inside && !ids.includes(name)) return;
      details.open = true;
      // The browser scrolled before the content was visible; scroll again now that it is.
      if (target && target !== details) target.scrollIntoView?.({ block: "start" });
    }
    openForHash();
    // Next.js moves between hashes with history.pushState, which fires no hashchange, so a click
    // on any in-page link is checked again once the URL has changed.
    function onClick(event: MouseEvent) {
      const link = (event.target as Element | null)?.closest?.("a[href*='#']");
      if (link) window.setTimeout(openForHash, 0);
    }
    window.addEventListener("hashchange", openForHash);
    document.addEventListener("click", onClick);
    return () => {
      window.removeEventListener("hashchange", openForHash);
      document.removeEventListener("click", onClick);
    };
  }, [extra]);

  const section = variant === "section";
  return (
    <details ref={ref} id={id} className={`group ${section ? "border-t border-rule" : ""} ${className}`}>
      <summary
        className={`flex cursor-pointer list-none items-start gap-1 [&::-webkit-details-marker]:hidden ${
          section ? "py-1.5 text-md text-ink hover:text-ink-2" : "py-0.5 text-sm text-ink-2 hover:text-ink"
        }`}
      >
        <svg
          viewBox="0 0 10 10"
          aria-hidden="true"
          className="mt-[0.45em] size-[0.625rem] shrink-0 text-ink-3 transition-transform duration-150 group-open:rotate-90"
        >
          <path d="M3 1.5 L7 5 L3 8.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
        </svg>
        <span className="min-w-0">
          {label}
          {meta ? <span className="ml-1 whitespace-nowrap text-sm text-ink-3">· {meta}</span> : null}
        </span>
      </summary>
      <div className={section ? "pb-3 pt-1" : "pb-1 pt-1"}>{children}</div>
    </details>
  );
}
