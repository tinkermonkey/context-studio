import { describe, it, expect, afterEach } from "vitest";
import { ApiError } from "@/api/client/interceptors";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";
import {
  addErrorMessage,
  addedOperation,
  additionsBlocked,
  proposalSourceId,
  rangeOffsets,
  selectedPassage,
  titleFromQuote,
  toSourcePassage,
  trimPassage,
} from "../addFromText";

const TEXT = "Edit Check offers feedback.  TextMatch is new.";

/** The text split as SourceText splits it: plain spans and highlight marks. */
function render(): HTMLElement {
  const container = document.createElement("div");
  container.innerHTML =
    "<p><mark>Edit Check</mark><span> offers </span><mark>feedback</mark>" +
    "<span>.  TextMatch is new.</span></p>";
  document.body.append(container);
  return container;
}

function text(container: HTMLElement, index: number): Text {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const nodes: Text[] = [];
  while (walker.nextNode()) nodes.push(walker.currentNode as Text);
  return nodes[index];
}

function range(start: [Node, number], end: [Node, number]): Range {
  const r = document.createRange();
  r.setStart(...start);
  r.setEnd(...end);
  return r;
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("selection offsets", () => {
  it("reads a selection inside one text node", () => {
    const container = render();
    const last = text(container, 3); // ".  TextMatch is new."
    const r = range([last, 3], [last, 12]);
    expect(rangeOffsets(container, r)).toEqual({ start: 29, end: 38 });
    expect(selectedPassage(container, r, TEXT)).toEqual({ start: 29, end: 38, quote: "TextMatch" });
  });

  it("counts across highlight marks", () => {
    const container = render();
    // From "Check" in the first mark to "feed" in the second.
    const r = range([text(container, 0), 5], [text(container, 2), 4]);
    expect(selectedPassage(container, r, TEXT)).toEqual({
      start: 5,
      end: 22,
      quote: "Check offers feed",
    });
  });

  it("reads boundaries given as element offsets", () => {
    const container = render();
    const p = container.querySelector("p")!;
    // Before the second mark, to after it.
    const r = range([p, 2], [p, 3]);
    expect(selectedPassage(container, r, TEXT)).toEqual({ start: 18, end: 26, quote: "feedback" });
  });

  it("leaves out the whitespace around a selection, moving the offsets in", () => {
    const container = render();
    // " offers " with its spaces.
    const r = range([text(container, 1), 0], [text(container, 1), 8]);
    expect(selectedPassage(container, r, TEXT)).toEqual({ start: 11, end: 17, quote: "offers" });
    expect(trimPassage(TEXT, 27, 33)).toEqual({ start: 29, end: 33, quote: "Text" });
    expect(trimPassage(TEXT, 27, 29)).toBeUndefined();
  });

  it("gives the server code-point offsets, where the shown text starts", () => {
    const passage = { start: 18, end: 26, quote: "feedback" };
    expect(toSourcePassage(passage, TEXT, 1000)).toEqual({
      start: 1018,
      end: 1026,
      quote: "feedback",
    });
    // An emoji is two UTF-16 units but one code point.
    const withEmoji = `😀 ${TEXT}`;
    const at = withEmoji.indexOf("feedback");
    expect(at).toBe(21);
    expect(toSourcePassage({ start: at, end: at + 8, quote: "feedback" }, withEmoji)).toEqual({
      start: 20,
      end: 28,
      quote: "feedback",
    });
  });

  it("starts the title as the selection on one line", () => {
    expect(titleFromQuote("Reference\n  check")).toBe("Reference check");
    expect(titleFromQuote(" Tone\tcheck ")).toBe("Tone check");
  });

  it("ignores an empty selection, or one reaching outside the source text", () => {
    const container = render();
    const outside = document.createElement("p");
    outside.textContent = "elsewhere";
    document.body.append(outside);
    const first = text(container, 0);
    expect(rangeOffsets(container, range([first, 2], [first, 2]))).toBeUndefined();
    expect(
      selectedPassage(container, range([first, 2], [outside.firstChild!, 4]), TEXT),
    ).toBeUndefined();
    expect(
      selectedPassage(container, range([outside.firstChild!, 0], [outside.firstChild!, 4]), TEXT),
    ).toBeUndefined();
  });
});

describe("additions", () => {
  const open = createChangeProposal({
    dataset_id: "ds-1",
    client_metadata: { source_id: "src-1" },
  });

  it("reads the recorded source", () => {
    expect(proposalSourceId(open)).toBe("src-1");
    expect(proposalSourceId(createChangeProposal())).toBeUndefined();
    expect(proposalSourceId(undefined)).toBeUndefined();
  });

  it("says why a proposal takes no addition", () => {
    expect(additionsBlocked(open)).toBeUndefined();
    expect(additionsBlocked({ ...open, status: "reverted" })).toBe("the proposal was reverted.");
    expect(
      additionsBlocked({
        ...open,
        landed: { commit: "abc", landed_at: "2026-11-17T00:00:00Z" } as never,
      }),
    ).toBe("the proposal has landed.");
    expect(additionsBlocked({ ...open, client_metadata: {} })).toMatch(/doesn't record the source/);
    expect(additionsBlocked({ ...open, dataset_id: null })).toMatch(/doesn't record the source/);
  });

  it("finds the operation an addition made", () => {
    const added = createProposedOperation({ id: "op-new", added_by_reviewer: true });
    const after = createChangeProposal({ operations: [createProposedOperation(), added] });
    expect(addedOperation(new Set(["op-1"]), after)).toBe(added);
    expect(addedOperation(new Set(["op-1", "op-new"]), after)).toBeUndefined();
  });

  it("words a refusal: a taken title by its class, else the server's message", () => {
    const names = { title: "TextMatch", classLabel: "product.feature" };
    const duplicate = new ApiError("Invalid", 422, "Invalid", {
      message: "Invalid",
      errors: [{ seq: 7, code: "duplicate_title", message: "An individual titled …" }],
    });
    expect(addErrorMessage(duplicate, names)).toBe(
      "TextMatch already exists in this dataset as product.feature.",
    );
    const mismatch = new ApiError("Invalid", 422, "Invalid", {
      errors: [
        { seq: 7, code: "quote_mismatch", message: "The source's text at [1, 4) is not the quote" },
      ],
    });
    expect(addErrorMessage(mismatch, names)).toBe("The source's text at [1, 4) is not the quote");
    const superseded = new ApiError("x", 409, "Change proposal p was superseded");
    expect(addErrorMessage(superseded, names)).toBe("Change proposal p was superseded");
    expect(addErrorMessage(new Error("Network Error"), names)).toBe("Network Error");
    const timeout = new ApiError(
      "timeout",
      0,
      "timeout of 30000ms exceeded",
      undefined,
      "ECONNABORTED",
    );
    expect(addErrorMessage(timeout, names)).toMatch(/^The server is taking longer than expected/);
  });
});
