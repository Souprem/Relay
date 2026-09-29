import { QuestionsNav } from "@/components/questions/QuestionsNav";
import { getQuestions } from "@/lib/data";
import { CLAUDE_PAGE, compareHref, comparePair } from "@/lib/questions";

export default function QuestionsLayout({ children }: { children: React.ReactNode }) {
  const data = getQuestions();
  const pages = [
    { href: "/questions/", label: "Overview" },
    ...data.sets.map((s) => ({ href: `/questions/${s.version}/`, label: s.version })),
    { href: `/questions/${CLAUDE_PAGE}/`, label: "Claude prompt" },
  ];
  const compares = data.compare.map((slug) => {
    const [a, b] = comparePair(slug);
    return { href: compareHref(slug), label: `${a.replace("q-", "")}→${b.replace("q-", "")}` };
  });
  return (
    <>
      <QuestionsNav pages={pages} compares={compares} />
      {children}
    </>
  );
}
