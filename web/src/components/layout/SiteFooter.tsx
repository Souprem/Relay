import { shortSha } from "@/lib/format";

const REPO_URL = "https://github.com/Souprem/Relay";

export function SiteFooter({
  disclaimer,
  gitSha,
  exportedAt,
}: {
  disclaimer: string;
  gitSha: string | null;
  exportedAt: string;
}) {
  return (
    <footer className="border-t border-rule">
      <div className="mx-auto grid w-full max-w-page gap-1 px-3 py-3 text-sm text-ink-2 md:grid-cols-[1fr_auto] md:gap-4 md:px-4">
        <p className="max-w-prose">{disclaimer}</p>
        <p className="num text-ink-3 md:text-right">
          data {shortSha(gitSha)} · exported {exportedAt.slice(0, 10)} ·{" "}
          <a href={REPO_URL} className="underline hover:text-ink">
            source
          </a>
        </p>
      </div>
    </footer>
  );
}
