import Link from "next/link";

import { questionSetLabel, questionsHref, RULES_PAGE } from "@/lib/questions";

/** "questions: q-v0.2 →", linking a run or provider tab to the questions it was asked. */
export function QuestionsLink({
  questionSet,
  page,
  className = "",
}: {
  questionSet: string;
  page: string | null;
  className?: string;
}) {
  if (page === null) {
    return <p className={`text-sm text-ink-3 ${className}`}>questions: none (ground-truth labels)</p>;
  }
  const label = page === RULES_PAGE ? `none, ${questionSet} matches keyword patterns` : questionSetLabel(questionSet);
  return (
    <p className={`text-sm text-ink-2 ${className}`}>
      questions:{" "}
      <Link href={questionsHref(page)} className="font-mono text-ink underline decoration-rule-strong hover:decoration-ink">
        {label}&nbsp;→
      </Link>
    </p>
  );
}
