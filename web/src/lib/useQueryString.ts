"use client";

import { useCallback, useSyncExternalStore } from "react";

const EVENT = "relay:querystring";

function subscribe(onChange: () => void) {
  window.addEventListener("popstate", onChange);
  window.addEventListener(EVENT, onChange);
  return () => {
    window.removeEventListener("popstate", onChange);
    window.removeEventListener(EVENT, onChange);
  };
}

/**
 * The page's query string as state. The static HTML renders with an empty query (the server
 * snapshot), then the browser's real query applies after hydration; setting it replaces the
 * history entry, so filters live in the URL without a page load.
 */
export function useQueryString(): [string, (next: string) => void] {
  const query = useSyncExternalStore(
    subscribe,
    () => window.location.search.replace(/^\?/, ""),
    () => "",
  );
  const setQuery = useCallback((next: string) => {
    const url = `${window.location.pathname}${next ? `?${next}` : ""}${window.location.hash}`;
    window.history.replaceState(window.history.state, "", url);
    window.dispatchEvent(new Event(EVENT));
  }, []);
  return [query, setQuery];
}
