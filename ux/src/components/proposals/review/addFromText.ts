/**
 * Adding an element the extraction missed from text the reviewer selects in
 * the source (#1612): the selection as offsets into the source's whole text,
 * whether the proposal takes additions, and what a refusal says.
 */
import { ApiError, isTimeout } from "@/api/client/interceptors";
import type { ChangeProposal, ProposedOperation } from "@/api/services/proposals";
import { offsetMap } from "./textOffsets";

/** A passage of the source: offsets (end exclusive) and the text there. */
export interface SelectedPassage {
  start: number;
  end: number;
  quote: string;
}

/** The part of a DOM Range a selection reads. */
export type RangeBounds = Pick<
  Range,
  "startContainer" | "startOffset" | "endContainer" | "endOffset" | "collapsed"
>;

/** The number of text characters in `container` before the boundary (node, offset). */
function textBefore(container: Node, node: Node, offset: number): number {
  const range = (container.ownerDocument ?? document).createRange();
  range.setStart(container, 0);
  range.setEnd(node, offset);
  return range.toString().length;
}

/**
 * A selection's offsets into the text `container` shows, counted across the
 * highlight marks the text is split into; undefined when it is empty or
 * either end lies outside the container.
 */
export function rangeOffsets(
  container: Node,
  range: RangeBounds,
): { start: number; end: number } | undefined {
  if (range.collapsed) return undefined;
  if (!container.contains(range.startContainer) || !container.contains(range.endContainer)) {
    return undefined;
  }
  const start = textBefore(container, range.startContainer, range.startOffset);
  const end = textBefore(container, range.endContainer, range.endOffset);
  return end > start ? { start, end } : undefined;
}

/**
 * The passage at [start, end) of `text`, its surrounding whitespace left out
 * (the offsets move in with it); undefined when nothing but whitespace is left.
 */
export function trimPassage(text: string, start: number, end: number): SelectedPassage | undefined {
  let from = Math.max(0, start);
  let to = Math.min(text.length, end);
  while (from < to && /\s/.test(text[from])) from++;
  while (to > from && /\s/.test(text[to - 1])) to--;
  return to > from ? { start: from, end: to, quote: text.slice(from, to) } : undefined;
}

/**
 * The passage a selection in `container` picks out of `text`, at UTF-16
 * offsets into `text` (see toSourcePassage for the server's offsets).
 */
export function selectedPassage(
  container: Node,
  range: RangeBounds,
  text: string,
): SelectedPassage | undefined {
  const offsets = rangeOffsets(container, range);
  return offsets && trimPassage(text, offsets.start, offsets.end);
}

/**
 * A selected passage as the server reads it: code-point offsets into the
 * source's whole text, given the shown `text` and where it starts there
 * (`textStart`, in code points).
 */
export function toSourcePassage(
  passage: SelectedPassage,
  text: string,
  textStart = 0,
): SelectedPassage {
  const offsets = offsetMap(text);
  return {
    start: textStart + offsets.toCodePoint(passage.start),
    end: textStart + offsets.toCodePoint(passage.end),
    quote: passage.quote,
  };
}

/** The title an added element starts with: the selection on one line. */
export function titleFromQuote(quote: string): string {
  return quote.replace(/\s+/g, " ").trim();
}

/** The source a proposal was extracted from, as it records it. */
export function proposalSourceId(proposal: ChangeProposal | undefined): string | undefined {
  const id = proposal?.client_metadata?.source_id;
  return typeof id === "string" && id ? id : undefined;
}

/**
 * Why the proposal takes no added element, in a few words; undefined when it
 * does. (A proposal superseded by a newer extraction is refused by the server.)
 */
export function additionsBlocked(proposal: ChangeProposal): string | undefined {
  if (proposal.status === "reverted") return "the proposal was reverted.";
  if (proposal.landed) return "the proposal has landed.";
  if (!proposalSourceId(proposal) || !proposal.dataset_id) {
    return "the proposal doesn't record the source and dataset it was extracted into.";
  }
  return undefined;
}

/** The operation an addition made: the one the proposal didn't have before. */
export function addedOperation(
  beforeIds: Set<string>,
  after: ChangeProposal,
): ProposedOperation | undefined {
  return after.operations.find((o) => !beforeIds.has(o.id) && o.added_by_reviewer);
}

interface ValidationError {
  code?: string;
  message?: string;
}

/**
 * What a refused addition says beside the form: a taken title as "<title>
 * already exists in this dataset as <class>", otherwise the server's message
 * for the first problem, or the error's own.
 */
export function addErrorMessage(
  error: unknown,
  { title, classLabel }: { title: string; classLabel: string },
): string {
  if (isTimeout(error)) {
    return "The server is taking longer than expected. The proposal was refreshed: check whether the element was added before adding it again.";
  }
  if (error instanceof ApiError) {
    const errors = (error.body as { errors?: ValidationError[] } | undefined)?.errors ?? [];
    const first = errors[0];
    if (first?.code === "duplicate_title") {
      return `${title} already exists in this dataset as ${classLabel}.`;
    }
    return first?.message || error.detail;
  }
  return error instanceof Error ? error.message : "The element couldn't be added.";
}
