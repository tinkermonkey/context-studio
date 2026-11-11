/**
 * Extraction proposals read beside their sources, worked out in the browser:
 * an operation's source passages (evidence that locates a quote in a source),
 * a passage placed in its surrounding text, an individual create's near
 * matches, and which ends of a relationship create are new in the proposal.
 */
import type { ProposedOperation } from "@/api/services/proposals";

// ==================== Source passages ====================

/** Evidence that locates a quote in a source: character offsets into its text, end exclusive. */
export interface SourcePassage {
  sourceId: string;
  page: number | null;
  start: number;
  end: number;
  quote?: string;
}

/**
 * What is known about a passage's source beyond the evidence: its title, the
 * section the passage is in, and some of its text around the passage
 * (`start` is the offset of `text` in the source's text).
 */
export interface PassageSource {
  title?: string;
  /** The source's taxonomy, for a link to its Sources page. */
  taxonomyId?: string;
  section?: string;
  text?: { text: string; start: number };
  /** The source was removed; its passages stay as provenance. */
  removed?: boolean;
}

function isOffset(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function asPassage(item: Record<string, unknown>): SourcePassage | undefined {
  const { source_id: sourceId, page, start, end, quote } = item;
  if (typeof sourceId !== "string" || !sourceId || !isOffset(start) || !isOffset(end)) {
    return undefined;
  }
  return {
    sourceId,
    page: isOffset(page) ? page : null,
    start,
    end,
    quote: typeof quote === "string" && quote ? quote : undefined,
  };
}

/** An operation's evidence items that locate a passage in a source, in their order. */
export function sourcePassagesOf(operation: ProposedOperation): SourcePassage[] {
  return (operation.evidence ?? []).flatMap((item) => asPassage(item) ?? []);
}

/** An operation's other evidence: quotes, links and claims that name no source passage. */
export function plainEvidenceOf(operation: ProposedOperation): Record<string, unknown>[] {
  return (operation.evidence ?? []).filter((item) => !asPassage(item));
}

/** "p. 5", or undefined when the source has no pages. Pages are stored from 1. */
export function pageLabel(page: number | null): string | undefined {
  return page === null ? undefined : `p. ${page}`;
}

/** "chars 8,412–8,447" */
export function charsLabel(passage: { start: number; end: number }): string {
  return `chars ${passage.start.toLocaleString("en-US")}–${passage.end.toLocaleString("en-US")}`;
}

/** "Also on pp. 1, 54" for further passages in the shown passage's own source. */
function sameSourceLabel(first: SourcePassage, rest: SourcePassage[]): string | undefined {
  if (rest.length === 0) return undefined;
  const more = `${rest.length} more passage${rest.length === 1 ? "" : "s"}`;
  if (rest.some((p) => p.page === null)) return `Also ${more}`;
  const pages = [...new Set(rest.map((p) => p.page as number))]
    .filter((page) => page !== first.page)
    .sort((a, b) => a - b);
  if (pages.length === 0) return `Also ${more} on this page`;
  return `Also on ${pages.length === 1 ? "p." : "pp."} ${pages.join(", ")}`;
}

/**
 * Where further passages are, beside the first (the one shown): the pages of
 * those in its source ("Also on p. 55", "Also on pp. 1, 54", or "Also 2 more
 * passages" when some have no page), then "Also in 2 other sources" for the
 * rest; undefined when there are none. The first passage's page is left out.
 */
export function alsoOnLabel(passages: SourcePassage[]): string | undefined {
  const [first, ...rest] = passages;
  if (!first) return undefined;
  const same = sameSourceLabel(
    first,
    rest.filter((p) => p.sourceId === first.sourceId),
  );
  const others = new Set(rest.filter((p) => p.sourceId !== first.sourceId).map((p) => p.sourceId))
    .size;
  const elsewhere =
    others > 0
      ? `${same ? "also" : "Also"} in ${others} other source${others === 1 ? "" : "s"}`
      : "";
  if (!same && !elsewhere) return undefined;
  return [same, elsewhere].filter(Boolean).join("; ");
}

/** The page (from 1) holding `offset`, given each page's start offset; null without pages. */
export function pageAt(offset: number, pageStarts: number[]): number | null {
  if (pageStarts.length === 0) return null;
  let page = 1;
  pageStarts.forEach((start, index) => {
    if (start <= offset) page = index + 1;
  });
  return page;
}

/** The title of the last heading at or before `offset`, if any. */
export function sectionAt(
  offset: number,
  headings: { start: number; title: string }[],
): string | undefined {
  let section: string | undefined;
  for (const heading of headings) if (heading.start <= offset) section = heading.title;
  return section;
}

/** How much text either side of a placed quote shows. */
const CONTEXT_CHARS = 240;

/** A passage as shown: the quote, and the text around it when it could be placed there. */
export interface PlacedPassage {
  before: string;
  quote: string;
  after: string;
  /** The quote was found at its offsets in the surrounding text: it is highlighted. */
  placed: boolean;
}

/** Cut `text` to its last `max` characters, starting at a word. */
function tail(text: string, max: number): string {
  if (text.length <= max) return text;
  const cut = text.slice(-max);
  const space = cut.indexOf(" ");
  return `…${space >= 0 ? cut.slice(space + 1) : cut}`;
}

/** Cut `text` to its first `max` characters, ending at a word. */
function head(text: string, max: number): string {
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  const space = cut.lastIndexOf(" ");
  return `${space >= 0 ? cut.slice(0, space) : cut}…`;
}

/**
 * A passage in its surrounding text: the quote highlighted between the text
 * before and after it, when the source's text around it is known and the
 * text at its offsets is the quote. Otherwise the quote alone, unhighlighted.
 */
export function placePassage(passage: SourcePassage, source?: PassageSource): PlacedPassage {
  const quote = passage.quote ?? "";
  const around = source?.text;
  if (around) {
    const from = passage.start - around.start;
    const to = passage.end - around.start;
    const inside = from >= 0 && to <= around.text.length && to > from;
    const found = inside ? around.text.slice(from, to) : undefined;
    if (found !== undefined && (!quote || found === quote)) {
      return {
        before: tail(around.text.slice(0, from), CONTEXT_CHARS),
        quote: found,
        after: head(around.text.slice(to), CONTEXT_CHARS),
        placed: true,
      };
    }
  }
  return { before: "", quote, after: "", placed: false };
}

// ==================== Near matches ====================

export type Alternative = NonNullable<ProposedOperation["alternatives"]>[number];

/** An individual create's near matches, most alike first. */
export function nearMatchesOf(operation: ProposedOperation): Alternative[] {
  if (operation.op !== "create" || operation.kind !== "individual") return [];
  return (operation.alternatives ?? [])
    .filter((a) => a.kind === "existing")
    .sort((a, b) => (b.similarity ?? 0) - (a.similarity ?? 0));
}

/** An individual create that may be an individual already in the dataset. */
export function isNearMatch(operation: ProposedOperation): boolean {
  return nearMatchesOf(operation).length > 0;
}

/** "similarity 0.93", or undefined when none was recorded. */
export function similarityLabel(alternative: Alternative): string | undefined {
  return typeof alternative.similarity === "number"
    ? `similarity ${alternative.similarity.toFixed(2)}`
    : undefined;
}

/**
 * Operations a bulk accept leaves for the reviewer: awaiting near matches
 * (accepting one unchosen would create a new individual) and the operations
 * that name one by "$ref", which can't apply until it is decided.
 */
export function nearMatchHeldIds(operations: ProposedOperation[]): Set<string> {
  const open = operations.filter(
    (o) => (o.status === "pending" || o.status === "failed") && isNearMatch(o),
  );
  const refs = new Set(open.flatMap((o) => (o.ref ? [`$${o.ref}`] : [])));
  const held = new Set(open.map((o) => o.id));
  // The backend resolves "$ref" only in a relationship's ends.
  for (const o of operations) {
    const ends = [o.fields?.source_id, o.fields?.target_id];
    if (ends.some((v) => typeof v === "string" && refs.has(v))) held.add(o.id);
  }
  return held;
}

/**
 * What a bulk accept left for the reviewer among `held` (see nearMatchHeldIds):
 * "2 near matches are left for you to decide, with 1 operation that names one."
 */
export function nearMatchHeldNote(held: ProposedOperation[]): string | undefined {
  if (held.length === 0) return undefined;
  const near = held.filter(isNearMatch).length;
  const waiting = held.length - near;
  const nearText =
    near > 0
      ? `${near} near match${near === 1 ? " is" : "es are"} left for you to decide`
      : "Operations that name a near match are left until you decide it";
  const waitingText =
    near > 0 && waiting > 0
      ? `, with ${waiting} operation${waiting === 1 ? "" : "s"} that name${waiting === 1 ? "s" : ""} one`
      : "";
  return `${nearText}${waitingText}.`;
}

/** The existing individual a matched create applied as, by its alternative. */
export function matchedAlternative(operation: ProposedOperation): Alternative | undefined {
  if (!operation.matched) return undefined;
  return nearMatchesOf(operation).find((a) => a.entity_id === operation.result_entity_id);
}

/** What the reviewer chose for a near match: an existing individual's id, or "new". */
export type NearMatchChoice = string;
export const CREATE_NEW: NearMatchChoice = "new";

/** The choice a near match opens on: the most alike individual that still exists. */
export function defaultNearMatchChoice(operation: ProposedOperation): NearMatchChoice {
  return nearMatchesOf(operation).find((a) => a.title)?.entity_id ?? CREATE_NEW;
}

/** The `chosen_alternatives` entry a choice sends; none for creating a new individual. */
export function chosenAlternative(
  choice: NearMatchChoice,
): { kind: "existing"; entity_id: string } | undefined {
  return choice === CREATE_NEW ? undefined : { kind: "existing", entity_id: choice };
}

// ==================== Relationship ends ====================

export interface RelationshipEnd {
  role: "source" | "target";
  /** existing: already in the dataset; new: a create in this proposal; near: a create with near matches. */
  kind: "existing" | "new" | "near";
  /** For a "$ref" end: its create's seq and status. */
  seq?: number;
  status?: ProposedOperation["status"];
  /** For a create that applied as an existing individual: that individual's title. */
  matchedTitle?: string;
}

/** The ends of a relationship create, and whether each is new in its proposal. */
export function relationshipEnds(
  operation: ProposedOperation,
  operations: ProposedOperation[],
): RelationshipEnd[] {
  if (operation.kind !== "relationship" || operation.op !== "create") return [];
  const roles = [
    ["source", operation.fields?.source_id],
    ["target", operation.fields?.target_id],
  ] as const;
  return roles.map(([role, value]) => {
    const ref = typeof value === "string" && value.startsWith("$") ? value.slice(1) : undefined;
    const create = ref ? operations.find((o) => o.op === "create" && o.ref === ref) : undefined;
    if (!create) return { role, kind: "existing" as const };
    return {
      role,
      kind: isNearMatch(create) ? ("near" as const) : ("new" as const),
      seq: create.seq,
      status: create.status,
      matchedTitle: matchedAlternative(create)?.title ?? undefined,
    };
  });
}

function endText(end: RelationshipEnd): string {
  if (end.kind === "existing") return `${end.role} is already in the dataset`;
  const create = `#${end.seq}`;
  if (end.matchedTitle)
    return `${end.role} is ${create}, which used the existing ${end.matchedTitle}`;
  if (end.status === "rejected") return `${end.role} is ${create}, which was rejected`;
  if (end.status === "applied") return `${end.role} is ${create}, created by this proposal`;
  if (end.kind === "near") {
    return `${end.role} is ${create}, a near match: it follows the choice made there`;
  }
  return `${end.role} is new in this proposal (${create})`;
}

/**
 * Which ends of a relationship create are new in its proposal and which
 * follow a near-match choice, e.g. "Source is new in this proposal (#3);
 * target is #1, a near match: it follows the choice made there. Rejecting #3
 * or #1 leaves this relationship unable to apply."
 */
export function relationshipEndsNote(ends: RelationshipEnd[]): string | undefined {
  if (ends.length === 0) return undefined;
  const text = ends.map(endText).join("; ");
  const open = ends.filter((e) => e.status === "pending" || e.status === "failed");
  const rejected = ends.some((e) => e.status === "rejected");
  const after = rejected
    ? " This relationship can't apply."
    : open.length > 0
      ? ` Rejecting ${open.map((e) => `#${e.seq}`).join(" or ")} leaves this relationship unable to apply.`
      : "";
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}.${after}`;
}
