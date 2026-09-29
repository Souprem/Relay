// Word-level diffs between two question sets, for /questions/compare/. Pure functions: the
// compare page renders what these return, and the unit tests pin their behaviour.
import type { Question } from "./types";

export type SegmentKind = "same" | "add" | "del";

export interface Segment {
  kind: SegmentKind;
  text: string;
}

/**
 * Words, punctuation marks and the whitespace between them, in order; joining them gives the text
 * back. Punctuation is its own token, so "methotrexate?" -> "methotrexate (…)?" is an insertion.
 */
export function tokenize(text: string): string[] {
  return text.match(/\s+|[\p{L}\p{N}_'’-]+|[^\s\p{L}\p{N}_'’-]/gu) ?? [];
}

function merge(segments: Segment[]): Segment[] {
  const out: Segment[] = [];
  for (const s of segments) {
    const last = out[out.length - 1];
    if (last && last.kind === s.kind) last.text += s.text;
    else if (s.text) out.push({ ...s });
  }
  return out;
}

/**
 * The word-level difference from `before` to `after` (longest common subsequence of tokens).
 * Within each changed stretch every removal comes before every addition, and a lone space
 * between two changes joins them, so a reworded phrase reads as one struck run then one new run.
 */
export function diffWords(before: string, after: string): Segment[] {
  const a = tokenize(before);
  const b = tokenize(after);
  const n = a.length;
  const m = b.length;
  // lcs[i][j] = LCS length of a[i:] and b[j:]
  const lcs: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }
  const ops: Segment[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      ops.push({ kind: "same", text: a[i] });
      i++;
      j++;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      ops.push({ kind: "del", text: a[i++] });
    } else {
      ops.push({ kind: "add", text: b[j++] });
    }
  }
  while (i < n) ops.push({ kind: "del", text: a[i++] });
  while (j < m) ops.push({ kind: "add", text: b[j++] });

  // Group each changed stretch (changes plus whitespace-only matches between them) as
  // removals then additions.
  const out: Segment[] = [];
  let k = 0;
  while (k < ops.length) {
    if (ops[k].kind === "same") {
      out.push(ops[k++]);
      continue;
    }
    let end = k;
    let last = k;
    while (end < ops.length) {
      const op = ops[end];
      if (op.kind !== "same") last = end;
      else if (!/^\s+$/.test(op.text) || end + 1 >= ops.length || ops[end + 1].kind === "same") break;
      end++;
    }
    let dels = "";
    let adds = "";
    for (const op of ops.slice(k, last + 1)) {
      if (op.kind !== "add") dels += op.text;
      if (op.kind !== "del") adds += op.text;
    }
    out.push({ kind: "del", text: dels }, { kind: "add", text: adds });
    k = last + 1;
  }
  return merge(out);
}

export type QuestionStatus = "added" | "removed" | "changed" | "unchanged";

export interface OptionDiff {
  option: string;
  status: QuestionStatus;
  text: Segment[];
}

export interface QuestionDiff {
  id: string;
  type: Question["type"];
  status: QuestionStatus;
  instructions: Segment[];
  summary: Segment[] | null;
  /** Only the options that carry criterion text on either side. */
  options: OptionDiff[];
}

function changed(segments: Segment[]): boolean {
  return segments.some((s) => s.kind !== "same");
}

function whole(kind: "add" | "del", text: string): Segment[] {
  return text ? [{ kind, text }] : [];
}

function diffOptions(before: Question | undefined, after: Question | undefined): OptionDiff[] {
  const a = new Map((before?.options ?? []).map((o) => [o.option, o.text]));
  const b = new Map((after?.options ?? []).map((o) => [o.option, o.text]));
  const order = [...b.keys(), ...[...a.keys()].filter((k) => !b.has(k))];
  const out: OptionDiff[] = [];
  for (const option of order) {
    const was = a.get(option) ?? null;
    const now = b.get(option) ?? null;
    if (was === null && now === null) continue;
    if (!a.has(option) || was === null) out.push({ option, status: "added", text: whole("add", now ?? "") });
    else if (!b.has(option) || now === null) out.push({ option, status: "removed", text: whole("del", was) });
    else {
      const text = diffWords(was, now);
      out.push({ option, status: changed(text) ? "changed" : "unchanged", text });
    }
  }
  return out;
}

/** One question compared across two sets; either side may be missing. */
export function diffQuestion(before: Question | undefined, after: Question | undefined): QuestionDiff {
  const q = (after ?? before) as Question;
  if (!before || !after) {
    const kind = after ? "add" : "del";
    return {
      id: q.id,
      type: q.type,
      status: after ? "added" : "removed",
      instructions: whole(kind, q.instructions),
      summary: q.options_summary === null ? null : whole(kind, q.options_summary),
      options: diffOptions(before, after),
    };
  }
  const instructions = diffWords(before.instructions, after.instructions);
  const summary =
    before.options_summary === null && after.options_summary === null
      ? null
      : diffWords(before.options_summary ?? "", after.options_summary ?? "");
  const options = diffOptions(before, after);
  const any =
    changed(instructions) ||
    (summary !== null && changed(summary)) ||
    options.some((o) => o.status !== "unchanged") ||
    before.type !== after.type;
  return { id: q.id, type: q.type, status: any ? "changed" : "unchanged", instructions, summary, options };
}

/**
 * Every question in either set, in the later set's order, with each removed question placed
 * after the question that preceded it in the earlier set.
 */
export function diffQuestionSets(before: Question[], after: Question[]): QuestionDiff[] {
  const a = new Map(before.map((q) => [q.id, q]));
  const b = new Map(after.map((q) => [q.id, q]));
  const order = after.map((q) => q.id);
  before.forEach((q, index) => {
    if (b.has(q.id)) return;
    const prev = before.slice(0, index).reverse().find((p) => order.includes(p.id));
    order.splice(prev ? order.indexOf(prev.id) + 1 : 0, 0, q.id);
  });
  return order.map((id) => diffQuestion(a.get(id), b.get(id)));
}
