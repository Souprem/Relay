import fs from "node:fs";
import path from "node:path";

// Spec §3: Tailwind only with Relay's own theme. Components may not use Tailwind's default
// palette (blue-500, slate-100, ...), gradients or shadows; colour comes from lib/semantic.ts
// tokens only.
const SRC = path.resolve(__dirname, "../..");
const PALETTE =
  /\b(?:bg|text|border|ring|outline|fill|stroke|from|to|via|decoration|accent|divide|placeholder)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|black|white)(?:-\d{2,3})?\b/;
const FORBIDDEN = [PALETTE, /\bbg-gradient-|\bbg-linear-|\bshadow-(?:sm|md|lg|xl|2xl)\b|\brounded-(?:lg|xl|2xl|3xl)\b|\bbackdrop-blur/];

function files(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return e.name === "__tests__" ? [] : files(p);
    return /\.(tsx?|css)$/.test(e.name) ? [p] : [];
  });
}

describe("theme discipline", () => {
  it("uses no default palette classes, gradients, big radii or shadows", () => {
    const offenders = files(SRC).flatMap((file) =>
      fs
        .readFileSync(file, "utf-8")
        .split("\n")
        .map((line, i) => ({ line, i }))
        .filter(({ line }) => FORBIDDEN.some((re) => re.test(line)))
        .map(({ line, i }) => `${path.relative(SRC, file)}:${i + 1}: ${line.trim()}`),
    );
    expect(offenders).toEqual([]);
  });

  it("removes Tailwind's default colours in the theme", () => {
    const css = fs.readFileSync(path.join(SRC, "app/globals.css"), "utf-8");
    expect(css).toContain("--color-*: initial;");
    expect(css).toContain("--shadow-*: initial;");
  });
});
