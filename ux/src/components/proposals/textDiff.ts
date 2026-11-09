/**
 * A changed text field as diff lines for Heimdall's SideBySideDiff. Its rows
 * are a fixed height and don't wrap, so the texts are compared sentence by
 * sentence (a longest common subsequence) and each sentence is wrapped to the
 * inspector's width. Long runs of unchanged sentences fold into one hunk row.
 */
import type { DiffLine } from "@tinkermonkey/heimdall-ui";

/** Characters per row: what fits the inspector's diff at 12px monospace. */
export const DIFF_WIDTH = 40;
/** Values shorter than this (on one line) stay inline: a diff adds nothing to a rename. */
const INLINE_LIMIT = 80;
/** Unchanged sentences kept around a change; the rest fold into a hunk row. */
const CONTEXT = 1;

/** True when a changed value reads better as a diff: long or multi-line text on either side. */
export function showsAsTextDiff(before: unknown, after: unknown): boolean {
  const texts = [before, after].filter((v): v is string => typeof v === "string");
  if (texts.length === 0) return false;
  if ([before, after].some((v) => v != null && typeof v !== "string")) return false;
  return texts.some((t) => t.length > INLINE_LIMIT || t.includes("\n"));
}

/** Paragraphs, then sentences; blank lines dropped. */
export function sentences(text: string): string[] {
  return text
    .split(/\n+/)
    .flatMap((paragraph) => paragraph.split(/(?<=[.!?;:])\s+/))
    .map((s) => s.trim())
    .filter(Boolean);
}

type Step = { type: "context" | "removed" | "added"; text: string };

/** The edit script turning `a` into `b`, by longest common subsequence. */
function editScript(all: string[], allB: string[]): Step[] {
  // Most edits touch a few sentences: match the common start and end first,
  // so the table below covers only what lies between them.
  let start = 0;
  while (start < all.length && start < allB.length && all[start] === allB[start]) start++;
  let end = 0;
  while (
    end < all.length - start &&
    end < allB.length - start &&
    all[all.length - 1 - end] === allB[allB.length - 1 - end]
  ) {
    end++;
  }
  const context = (texts: string[]): Step[] => texts.map((text) => ({ type: "context", text }));
  return [
    ...context(all.slice(0, start)),
    ...middleScript(all.slice(start, all.length - end), allB.slice(start, allB.length - end)),
    ...context(all.slice(all.length - end)),
  ];
}

function middleScript(a: string[], b: string[]): Step[] {
  const n = a.length;
  const m = b.length;
  const lcs = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }
  const steps: Step[] = [];
  let i = 0;
  let j = 0;
  while (i < n || j < m) {
    if (i < n && j < m && a[i] === b[j]) {
      steps.push({ type: "context", text: a[i] });
      i++;
      j++;
    } else if (j < m && (i === n || lcs[i][j + 1] >= lcs[i + 1][j])) {
      steps.push({ type: "added", text: b[j++] });
    } else {
      steps.push({ type: "removed", text: a[i++] });
    }
  }
  // Within each changed run, all removed sentences before the added ones.
  const ordered: Step[] = [];
  let run: Step[] = [];
  const flush = () => {
    ordered.push(
      ...run.filter((s) => s.type === "removed"),
      ...run.filter((s) => s.type === "added"),
    );
    run = [];
  };
  for (const step of steps) {
    if (step.type === "context") {
      flush();
      ordered.push(step);
    } else {
      run.push(step);
    }
  }
  flush();
  return ordered;
}

/** Words packed into rows of at most `width` characters; a longer word is split. */
export function wrap(text: string, width = DIFF_WIDTH): string[] {
  const rows: string[] = [];
  let row = "";
  for (const word of text.split(/\s+/).filter(Boolean)) {
    let rest = word;
    while (rest.length > width) {
      if (row) rows.push(row);
      row = "";
      rows.push(rest.slice(0, width));
      rest = rest.slice(width);
    }
    if (!rest) continue;
    if (!row) row = rest;
    else if (row.length + 1 + rest.length <= width) row = `${row} ${rest}`;
    else {
      rows.push(row);
      row = rest;
    }
  }
  if (row) rows.push(row);
  return rows;
}

/** "⋯ 3 unchanged sentences" */
function folded(count: number): DiffLine {
  return { type: "hunk", content: `⋯ ${count} unchanged sentence${count === 1 ? "" : "s"}` };
}

/** The diff lines from `before` to `after`, sentence by sentence, wrapped to `width`. */
export function textDiffLines(
  before: string | null | undefined,
  after: string | null | undefined,
  width = DIFF_WIDTH,
): DiffLine[] {
  const steps = editScript(sentences(before ?? ""), sentences(after ?? ""));
  const changed = steps.map((s) => s.type !== "context");
  const near = (index: number) =>
    changed.slice(Math.max(0, index - CONTEXT), index + CONTEXT + 1).some(Boolean);
  // Runs of unchanged sentences away from any change fold, unless the run is
  // a single sentence: its fold row would take as much room as the sentence.
  const shown = steps.map((_, index) => near(index));
  shown.forEach((visible, index) => {
    if (!visible && shown[index - 1] !== false && shown[index + 1] !== false) shown[index] = true;
  });
  const lines: DiffLine[] = [];
  let hidden = 0;
  steps.forEach((step, index) => {
    if (!shown[index]) {
      hidden++;
      return;
    }
    if (hidden > 0) lines.push(folded(hidden));
    hidden = 0;
    for (const content of wrap(step.text, width)) lines.push({ type: step.type, content });
  });
  if (hidden > 0) lines.push(folded(hidden));
  return lines;
}

/**
 * The diff lines for a changed value, or undefined when it should stay inline:
 * short, not text, or only whitespace changed (nothing a diff would mark).
 */
export function textDiffOf(before: unknown, after: unknown): DiffLine[] | undefined {
  if (!showsAsTextDiff(before, after)) return undefined;
  const lines = textDiffLines(before as string | null, after as string | null);
  return lines.some((l) => l.type === "added" || l.type === "removed") ? lines : undefined;
}
