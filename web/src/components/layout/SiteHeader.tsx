import Link from "next/link";

import { NavLinks } from "./NavLinks";
import { Wordmark } from "./Wordmark";

export function SiteHeader() {
  return (
    <header className="border-b border-rule">
      <nav
        aria-label="Main"
        className="mx-auto flex w-full max-w-page flex-wrap items-center justify-between gap-2 px-3 py-2 md:px-4"
      >
        <Link href="/" className="no-underline" aria-label="Relay home">
          <Wordmark />
        </Link>
        <NavLinks />
      </nav>
    </header>
  );
}
