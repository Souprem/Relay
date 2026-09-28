/** The Relay mark: a probability bar with a threshold tick, the unit every page is built from. */
export function Wordmark() {
  return (
    <span className="inline-flex items-center gap-1">
      <svg width="28" height="14" viewBox="0 0 28 14" aria-hidden="true" className="text-ink">
        <line x1="1" y1="9" x2="27" y2="9" stroke="currentColor" strokeOpacity="0.3" />
        <line x1="1" y1="9" x2="19" y2="9" stroke="currentColor" strokeWidth="3" />
        <line x1="22.5" y1="3" x2="22.5" y2="13" stroke="currentColor" strokeWidth="1.25" />
      </svg>
      <span className="font-mono text-md font-medium tracking-tight">relay</span>
    </span>
  );
}
