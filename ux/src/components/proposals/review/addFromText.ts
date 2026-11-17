/**
 * Adding an element the extraction missed from text the reviewer selects in
 * the source (#1612): the selection as offsets into the source's whole text,
 * whether the proposal takes additions, and what a refusal says.
 */
import { ApiError } from "@/api/client/interceptors";
import type { ChangeProposal, ProposedOperation } from "@/api/services/proposals";

/** A passage of the source: offsets into its whole text (end exclusive) and the text there. */
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
 * The passage a selection in `container` picks out of `text`, which starts
 * at `textStart` in the source's whole text: whole-text offsets and the quote.
 */
export function selectedPassage(
  container: Node,
  range: RangeBounds,
  text: string,
  textStart = 0,
): SelectedPassage | undefined {
  const offsets = rangeOffsets(container, range);
  const passage = offsets && trimPassage(text, offsets.start, offsets.end);
  return passage && { ...passage, start: passage.start + textStart, end: passage.end + textStart };
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
