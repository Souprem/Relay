// Links into /questions/ from a recorded question_set_version (runs, provider tabs, diffs).

export const CLAUDE_PAGE = "claude-prompt";
export const RULES_PAGE = "rules";

/** The href for an exported questions_page: a question set, Claude's prompt or the rules note. */
export function questionsHref(page: string): string {
  if (page === RULES_PAGE) return "/questions/#rules";
  return `/questions/${page}/`;
}

export function compareHref(slug: string): string {
  return `/questions/compare/${slug}/`;
}

/** "q-v0.2...q-v0.3" -> ["q-v0.2", "q-v0.3"] */
export function comparePair(slug: string): [string, string] {
  const [a, b] = slug.split("...");
  return [a, b];
}

/** "q-v0.2+claude-prompt-v1" reads as "q-v0.2 + claude-prompt-v1". */
export function questionSetLabel(questionSet: string): string {
  return questionSet.replace("+", " + ");
}

export const QUESTION_TYPE_LABEL: Record<"noul" | "choice", string> = {
  noul: "yes/no · Noul",
  choice: "choice · Choice",
};

/** A Noul's criteria keys read as the answers they describe. */
export function optionLabel(type: "noul" | "choice", option: string): string {
  if (type !== "noul") return option;
  return option === "true" ? "yes (true)" : option === "false" ? "no (false)" : option;
}

/** "sha256:4589d78b…" shortened for tables; the full value stays in the title attribute. */
export function shortHash(hash: string): string {
  return hash.length > 19 ? `${hash.slice(0, 19)}…` : hash;
}
