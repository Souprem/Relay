import type { Question } from "../types";
import { diffQuestionSets, diffWords, tokenize, type Segment } from "../wordDiff";

const text = (segments: Segment[], keep: "before" | "after") =>
  segments
    .filter((s) => s.kind === "same" || s.kind === (keep === "before" ? "del" : "add"))
    .map((s) => s.text)
    .join("");

function noul(id: string, instructions: string, yes = "Yes.", no = "No."): Question {
  return {
    id,
    type: "noul",
    instructions,
    options: [
      { option: "true", text: yes },
      { option: "false", text: no },
    ],
    options_summary: null,
  };
}

describe("tokenize", () => {
  it("keeps every character, so joining the tokens gives the text back", () => {
    const s = "Answer 'none' if  the documents\ndo not state it.";
    expect(tokenize(s).join("")).toBe(s);
    expect(tokenize("")).toEqual([]);
  });
});

describe("diffWords", () => {
  it("returns one unchanged run for identical text", () => {
    expect(diffWords("In which month did it start?", "In which month did it start?")).toEqual([
      { kind: "same", text: "In which month did it start?" },
    ]);
  });

  it("marks an insertion as an addition and leaves the rest unchanged", () => {
    const d = diffWords("taking methotrexate?", "taking methotrexate (the first time, if it was restarted)?");
    expect(d.filter((s) => s.kind === "del")).toEqual([]);
    expect(d.filter((s) => s.kind === "add").map((s) => s.text).join("")).toContain("(the first time, if it was restarted)");
    expect(text(d, "after")).toBe("taking methotrexate (the first time, if it was restarted)?");
  });

  it("marks a deletion as a removal", () => {
    const d = diffWords("the patient never took the drug", "the patient took the drug");
    expect(d).toContainEqual({ kind: "del", text: "never " });
    expect(d.some((s) => s.kind === "add")).toBe(false);
    expect(text(d, "before")).toBe("the patient never took the drug");
    expect(text(d, "after")).toBe("the patient took the drug");
  });

  it("groups a reworded phrase as one removal followed by one addition", () => {
    const d = diffWords(
      "The patient's methotrexate treatment history (dates or outcome) is not documented.",
      "The records do not say whether or when the patient took methotrexate.",
    );
    const kinds = d.map((s) => s.kind);
    for (let i = 1; i < kinds.length; i++) {
      // never an addition directly followed by a removal inside one changed stretch
      expect(kinds[i - 1] === "add" && kinds[i] === "del").toBe(false);
    }
    expect(text(d, "before")).toBe("The patient's methotrexate treatment history (dates or outcome) is not documented.");
    expect(text(d, "after")).toBe("The records do not say whether or when the patient took methotrexate.");
  });

  it("handles an empty side as a whole addition or removal", () => {
    expect(diffWords("", "new text")).toEqual([{ kind: "add", text: "new text" }]);
    expect(diffWords("old text", "")).toEqual([{ kind: "del", text: "old text" }]);
  });
});

describe("diffQuestionSets", () => {
  const a = [noul("q1", "Is it so?"), noul("q2", "Was it taken?"), noul("gone", "Old question?")];
  const b = [noul("q1", "Is it so?"), noul("q2", "Was it ever taken?", "Yes, it was."), noul("new", "Was it restarted?")];
  const diff = diffQuestionSets(a, b);

  it("marks unchanged, changed, added and removed questions", () => {
    expect(diff.map((d) => [d.id, d.status])).toEqual([
      ["q1", "unchanged"],
      ["q2", "changed"],
      ["gone", "removed"],
      ["new", "added"],
    ]);
  });

  it("marks a whole added question as one addition, options included", () => {
    const added = diff.find((d) => d.id === "new")!;
    expect(added.instructions).toEqual([{ kind: "add", text: "Was it restarted?" }]);
    expect(added.options.map((o) => o.status)).toEqual(["added", "added"]);
  });

  it("marks a removed question as one removal", () => {
    const gone = diff.find((d) => d.id === "gone")!;
    expect(gone.instructions).toEqual([{ kind: "del", text: "Old question?" }]);
    expect(gone.options.every((o) => o.status === "removed")).toBe(true);
  });

  it("diffs criterion text option by option", () => {
    const q2 = diff.find((d) => d.id === "q2")!;
    expect(q2.instructions).toContainEqual({ kind: "add", text: "ever " });
    expect(q2.options.map((o) => [o.option, o.status])).toEqual([
      ["true", "changed"],
      ["false", "unchanged"],
    ]);
  });
});
