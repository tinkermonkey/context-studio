import { describe, it, expect } from "vitest";
import { sentences, showsAsTextDiff, textDiffLines, textDiffOf, wrap } from "../textDiff";

describe("showsAsTextDiff", () => {
  it("diffs long or multi-line text", () => {
    expect(showsAsTextDiff("a".repeat(81), "b")).toBe(true);
    expect(showsAsTextDiff("one\ntwo", "one")).toBe(true);
    expect(showsAsTextDiff(null, "x".repeat(90))).toBe(true);
  });
  it("leaves short values and non-text inline", () => {
    expect(showsAsTextDiff("realizes", "serves")).toBe(false);
    expect(showsAsTextDiff(["open"], ["open", "done"])).toBe(false);
    expect(showsAsTextDiff(3, 4)).toBe(false);
    expect(showsAsTextDiff("x".repeat(90), ["y"])).toBe(false);
  });
});

describe("sentences", () => {
  it("splits paragraphs and sentences, dropping blank lines", () => {
    expect(sentences("One. Two? Three!\n\n# Head\nFour: five")).toEqual([
      "One.",
      "Two?",
      "Three!",
      "# Head",
      "Four:",
      "five",
    ]);
  });
});

describe("wrap", () => {
  it("packs words into rows of at most the width", () => {
    expect(wrap("the quick brown fox jumps", 10)).toEqual(["the quick", "brown fox", "jumps"]);
  });
  it("splits a word longer than the width", () => {
    expect(wrap("a abcdefghijkl b", 5)).toEqual(["a", "abcde", "fghij", "kl b"]);
  });
});

describe("textDiffLines", () => {
  it("marks only the changed sentence, removed before added, with its neighbours as context", () => {
    const before = "Tasks are work. A task has a status. It is open or done.";
    const after = "Tasks are work. A task has a status. It is open, in progress or done.";
    expect(textDiffLines(before, after, 80)).toEqual([
      // A single unchanged sentence shows rather than folding.
      { type: "context", content: "Tasks are work." },
      { type: "context", content: "A task has a status." },
      { type: "removed", content: "It is open or done." },
      { type: "added", content: "It is open, in progress or done." },
    ]);
  });

  it("folds long unchanged runs into a hunk row", () => {
    const same = ["S1.", "S2.", "S3.", "S4."].join(" ");
    expect(textDiffLines(`Old. ${same}`, `New. ${same}`, 80)).toEqual([
      { type: "removed", content: "Old." },
      { type: "added", content: "New." },
      { type: "context", content: "S1." },
      { type: "hunk", content: "⋯ 3 unchanged sentences" },
    ]);
  });

  it("wraps each sentence into rows of its type", () => {
    const lines = textDiffLines("", "A sentence long enough to wrap twice.", 12);
    expect(lines.every((l) => l.type === "added")).toBe(true);
    expect(lines.map((l) => l.content)).toEqual(["A sentence", "long enough", "to wrap", "twice."]);
  });

  it("shows the text as context when nothing changed", () => {
    expect(textDiffLines("Same.", "Same.")).toEqual([{ type: "context", content: "Same." }]);
  });
});

describe("textDiffOf", () => {
  const long = "A sentence long enough to pass the inline limit of eighty characters, surely. Two.";
  it("gives the lines of a long text change", () => {
    expect(textDiffOf(long, long.replace("Two.", "Three."))).toContainEqual({
      type: "added",
      content: "Three.",
    });
  });
  it("is undefined for whitespace-only and short changes", () => {
    expect(textDiffOf(`${long}\n`, long)).toBeUndefined();
    expect(textDiffOf(long.replace(". ", ".  "), long)).toBeUndefined();
    expect(textDiffOf("realizes", "serves")).toBeUndefined();
  });
  it("handles a long text with one sentence changed in the middle", () => {
    const many = Array.from({ length: 400 }, (_, i) => `Sentence ${i}.`);
    const changed = [...many];
    changed[200] = "Sentence two hundred.";
    const lines = textDiffLines(many.join(" "), changed.join(" "), 80);
    expect(lines.filter((l) => l.type === "removed")).toEqual([
      { type: "removed", content: "Sentence 200." },
    ]);
    expect(lines.filter((l) => l.type === "added")).toEqual([
      { type: "added", content: "Sentence two hundred." },
    ]);
    expect(lines.filter((l) => l.type === "hunk")).toHaveLength(2);
  });
});
