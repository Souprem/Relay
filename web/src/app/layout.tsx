import type { Metadata } from "next";

import { SiteFooter } from "@/components/layout/SiteFooter";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { getIndex } from "@/lib/data";

import { plexMono, plexSans } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Relay", template: "%s · Relay" },
  description:
    "Relay turns probabilistic judgments about synthetic prior-authorization cases into " +
    "traced, gated workflow actions. Synthetic data only.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const index = getIndex();
  return (
    <html lang="en" className={`${plexSans.variable} ${plexMono.variable}`}>
      <body className="flex min-h-screen flex-col bg-paper text-ink">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:bg-paper focus:px-1 focus:py-0.5"
        >
          Skip to content
        </a>
        <SiteHeader />
        <main id="main" className="mx-auto w-full max-w-page flex-1 px-3 pb-8 pt-5 md:px-4">
          {children}
        </main>
        <SiteFooter
          disclaimer={index.disclaimer}
          gitSha={index.git_sha}
          exportedAt={index.exported_at}
        />
      </body>
    </html>
  );
}
