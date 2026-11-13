/**
 * Pure helpers for the Sources and Extract pages: how a source reads in a
 * row, page ranges, the chunk and cost estimate, and what a finished run says.
 */
import type {
  ExtractionPipeline,
  Source,
  SourceFailure,
  SourceStatus,
} from "@/api/services/sources";
import type { ChangeProposal } from "@/api/services/proposals";
import type { components } from "@/api/types";

type PipelineRun = components["schemas"]["PipelineRunResponse"];
type PipelineConfiguration = components["schemas"]["PipelineConfigurationResponse"];
export type ChipTone = "emerald" | "amber" | "rose" | "cyan" | "violet" | "neutral";

/**
 * The server's chunk size: it fills a chunk to at least half of it before
 * breaking at a heading or page, so a chunk holds between half and all of it.
 */
export const CHUNK_CHARS = 8000;
/** Rough tokens per character of English text. */
const TOKENS_PER_CHAR = 1 / 4;
/** Rough prompt (instructions, class definitions) sent with every chunk. */
const PROMPT_TOKENS_PER_CHUNK = 1500;
/** Rough tokens the model writes back per chunk. */
const OUTPUT_TOKENS_PER_CHUNK = 800;

/** 940, 2.4k, 118k, 1.2M */
export function formatCount(n: number): string {
  if (n < 1000) return String(n);
  if (n < 10_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, "")}k`;
  if (n < 1_000_000) return `${Math.round(n / 1000)}k`;
  return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
}

/** A URL without its scheme or trailing slash: "energystar.gov/products". */
function shortUrl(url: string): string {
  return url.replace(/^https?:\/\//i, "").replace(/\/$/, "");
}

/** The muted line under a source's title: where it came from and its size. */
export function sourceDetail(source: Source): string {
  const origin = source.origin
    ? source.kind === "web"
      ? shortUrl(source.origin)
      : source.origin
    : "pasted text";
  if (source.status !== "ready") return origin;
  const parts = [origin];
  if (source.pages > 1) parts.push(`${source.pages} pages`);
  parts.push(`${formatCount(source.chars)} chars`);
  return parts.join(" · ");
}

export const STATUS_TONE: Record<SourceStatus, ChipTone> = {
  ready: "emerald",
  fetching: "cyan",
  failed: "rose",
};

export const FAILURE_LABEL: Record<SourceFailure, string> = {
  too_large: "Too large",
  unsupported_type: "Unsupported file type",
  no_text: "No text layer (scanned?)",
  fetch_failed: "Could not fetch the page",
};

/** A source's status note: the failure reason, or progress while fetching. */
export function statusNote(source: Source): string {
  if (source.status === "fetching") return "Reading the page";
  if (source.status !== "failed") return "";
  // A PDF without text is most likely a scan; a web page or file just had none.
  if (source.failure === "no_text" && source.kind !== "pdf") return "No text found";
  return source.failure ? FAILURE_LABEL[source.failure] : "Could not read it";
}

export type PagesResult = { pages: number[] } | { error: string };

const PAGES_FORMAT_ERROR = "Use page numbers and ranges, like 1-12, 15.";

/**
 * Parse a page list such as "1-12, 15" into sorted page numbers. Blank means
 * every page (an empty list). An en dash reads as "-".
 */
export function parsePages(spec: string, pageCount: number): PagesResult {
  const trimmed = spec.replace(/\u2013/g, "-").trim();
  if (!trimmed) return { pages: [] };
  const pages = new Set<number>();
  for (const part of trimmed.split(",")) {
    const match = /^\s*(\d+)\s*(?:-\s*(\d+)\s*)?$/.exec(part);
    if (!match) return { error: PAGES_FORMAT_ERROR };
    const first = Number(match[1]);
    const last = match[2] ? Number(match[2]) : first;
    if (first < 1 || last > pageCount || first > last) {
      return { error: `Pages run from 1 to ${pageCount}.` };
    }
    for (let p = first; p <= last; p++) pages.add(p);
  }
  return { pages: [...pages].sort((a, b) => a - b) };
}

/**
 * The page spec the server takes (digits, "-" and commas: "1-5,7") for these
 * sorted pages, or undefined when they are every page or none was chosen.
 */
export function pagesSpec(pages: number[], pageCount: number): string | undefined {
  if (pages.length === 0 || pages.length >= pageCount) return undefined;
  const ranges: string[] = [];
  let first = pages[0];
  let last = first;
  for (const p of [...pages.slice(1), Infinity]) {
    if (p === last + 1) {
      last = p;
      continue;
    }
    ranges.push(first === last ? String(first) : `${first}-${last}`);
    first = last = p;
  }
  return ranges.join(",");
}

/** Characters on the given pages (every page when the list is empty). */
export function charsInPages(source: Source, pages: number[]): number {
  if (pages.length === 0 || source.page_starts.length === 0) return source.chars;
  const starts = source.page_starts;
  return pages.reduce((sum, p) => {
    const start = starts[p - 1] ?? source.chars;
    const end = starts[p] ?? source.chars;
    return sum + Math.max(0, end - start);
  }, 0);
}

export interface ChunkRange {
  min: number;
  max: number;
}

/**
 * How many chunks the server may split this much text into: full chunks at
 * best, half-full ones (each broken early at a heading or page) at worst.
 */
export function chunkRange(chars: number): ChunkRange {
  const min = Math.max(1, Math.ceil(chars / CHUNK_CHARS));
  return { min, max: Math.max(min, Math.ceil(chars / (CHUNK_CHARS / 2))) };
}

export interface ModelPrice {
  /** USD per million input tokens. */
  input: number;
  /** USD per million output tokens. */
  output: number;
}

const asPrice = (v: unknown) => (typeof v === "number" && v >= 0 ? v : undefined);

/**
 * A configuration's model price, when its parameters carry one
 * (`price_per_mtok_in`, optionally `price_per_mtok_out`); undefined otherwise.
 */
export function configurationPrice(config?: PipelineConfiguration): ModelPrice | undefined {
  const params = (config?.parameters ?? {}) as Record<string, unknown>;
  const input = asPrice(params.price_per_mtok_in);
  if (input === undefined) return undefined;
  return { input, output: asPrice(params.price_per_mtok_out) ?? input };
}

/** A rough USD cost for extracting this much text, in this many chunks, in this many runs. */
export function estimateCost(
  chars: number,
  chunks: number,
  runs: number,
  price: ModelPrice,
): number {
  const inputTokens = chars * TOKENS_PER_CHAR + chunks * PROMPT_TOKENS_PER_CHUNK;
  const outputTokens = chunks * OUTPUT_TOKENS_PER_CHUNK;
  return (runs * (inputTokens * price.input + outputTokens * price.output)) / 1_000_000;
}

/** "3–6", or "3" when the range is one number. */
export function formatRange(min: number | string, max: number | string): string {
  return min === max ? String(min) : `${min}–${max}`;
}

export function formatUsd(usd: number): string {
  return usd < 0.01 ? "under $0.01" : `$${usd.toFixed(2)}`;
}

/** "p. 3", "pp. 3–5", or "" without pages. */
export function pageRangeLabel(first?: number | null, last?: number | null): string {
  if (!first) return "";
  if (!last || last === first) return `p. ${first}`;
  return `pp. ${first}–${last}`;
}

/** One chunk of a finished run, from output_summary.metadata.chunks. */
export interface RunChunk {
  index: number;
  start: number;
  end: number;
  page_first?: number | null;
  page_last?: number | null;
  heading?: string | null;
  triples: number;
  /** Why the chunk's extraction failed; unset when it was read. What a failed chunk holds is missing. */
  failure_reason?: string | null;
}

/** A finished chunked run's chunks; empty while running or for an unchunked run. */
export function runChunks(run?: PipelineRun): RunChunk[] {
  const output = (run?.output_summary ?? {}) as { metadata?: { chunks?: unknown } };
  const chunks = output.metadata?.chunks;
  return Array.isArray(chunks) ? (chunks as RunChunk[]) : [];
}

function joinWords(words: string[]): string {
  if (words.length <= 1) return words.join("");
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}

/** "chunk 2 (Warranty)" or "chunks 14 and 15 (Warranty, Index)". */
function namedChunks(chunks: RunChunk[]): string {
  const numbers = joinWords(chunks.map((c) => String(c.index + 1)));
  const headings = chunks.map((c) => c.heading).filter((h): h is string => !!h);
  const named = headings.length > 0 ? ` (${headings.join(", ")})` : "";
  return `${chunks.length === 1 ? "chunk" : "chunks"} ${numbers}${named}`;
}

const capitalized = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** The chunks whose extraction failed. */
export function failedChunks(chunks: RunChunk[]): RunChunk[] {
  return chunks.filter((c) => !!c.failure_reason);
}

/**
 * "Chunks 14 and 15 (Warranty, Index) gave no candidates.", or "" when every
 * chunk that was read gave some. A failed chunk was not read, so it is not
 * counted here: see failedChunksWarning.
 */
export function emptyChunksWarning(chunks: RunChunk[]): string {
  const empty = chunks.filter((c) => c.triples === 0 && !c.failure_reason);
  if (empty.length === 0) return "";
  return `${capitalized(namedChunks(empty))} gave no candidates.`;
}

/**
 * "Extraction failed for 2 of 3 chunks: chunks 2 and 3 (Warranty, Index). What
 * they hold is missing.", or "" when no chunk failed.
 */
export function failedChunksWarning(chunks: RunChunk[]): string {
  const failed = failedChunks(chunks);
  if (failed.length === 0) return "";
  const total = chunks.length === 1 ? "1 chunk" : `${chunks.length} chunks`;
  const missing = failed.length === 1 ? "What it holds is missing." : "What they hold is missing.";
  return `Extraction failed for ${failed.length} of ${total}: ${namedChunks(failed)}. ${missing}`;
}

export interface ProposalCounts {
  operations: number;
  individuals: number;
  relationships: number;
  /** Individual creates with near matches: existing individuals they may be. */
  nearMatches: number;
}

export function proposalCounts(proposal: ChangeProposal): ProposalCounts {
  const ops = proposal.operations;
  return {
    operations: ops.length,
    individuals: ops.filter((o) => o.op === "create" && o.kind === "individual").length,
    relationships: ops.filter((o) => o.kind === "relationship").length,
    nearMatches: ops.filter((o) => (o.alternatives?.length ?? 0) > 0).length,
  };
}

/** The run ids the extract page follows (its `run` and `schemaRun` URL parameters). */
export interface ExtractionRunIds {
  run?: string;
  schemaRun?: string;
}

/** The individual and schema run ids among an extraction's runs. */
export function extractionRunIds(
  runs: Array<{ run_id: string; pipeline: ExtractionPipeline }>,
): ExtractionRunIds {
  return {
    run: runs.find((r) => r.pipeline === "individual_extraction")?.run_id,
    schemaRun: runs.find((r) => r.pipeline === "schema_extraction")?.run_id,
  };
}

// ==================== A run that made no proposal ====================

/** Why a candidate became no operation, as a reviewer reads it. */
const SKIP_REASON_LABEL: Record<string, string> = {
  exists: "already exist",
  missing_class: "no matching class",
  unresolved_predicate: "unknown relationship type",
  unresolved_endpoint: "an end wasn't proposed",
  literal: "values, not entities",
  derived_type: "derived relationship type",
  self_loop: "points at itself",
  domain_range_mismatch: "doesn't fit the relationship type",
  invalid: "refused as invalid",
  no_scheme: "no concept scheme",
  identifier_taken: "identifier already in use",
  no_class: "no class to put it on",
  // Operations the proposal service refused (refused_operations), when the run lists them.
  refused: "refused",
};

/** A skip reason's label: a known one's words, else the code with spaces. */
export function skipReasonLabel(reason: string): string {
  return SKIP_REASON_LABEL[reason] ?? reason.replace(/_/g, " ");
}

/** What a finished run that made no proposal says about why. */
export interface NoProposalSummary {
  /** Candidates its chunks found; 0 for an unchunked run. */
  found: number;
  /** The server's reason (output_summary.no_proposal_reason), when it gives one. */
  reason?: string;
  /** Candidates not proposed, by reason, most first. */
  skipped: Array<{ reason: string; count: number }>;
  /** True when candidates were found but none could be proposed. */
  candidatesFound: boolean;
  /**
   * Which chunks failed, as a sentence (failedChunksWarning); "" when every
   * chunk was read. With it, the run cannot say the text holds no candidates.
   */
  failedNote: string;
}

/** A {reason: count} object's positive counts. */
function reportedCounts(value: unknown): Map<string, number> {
  const counts = new Map<string, number>();
  if (!value || typeof value !== "object" || Array.isArray(value)) return counts;
  for (const [reason, n] of Object.entries(value)) {
    if (typeof n === "number" && n > 0) counts.set(reason, n);
  }
  return counts;
}

/** A [{reason}] list counted by reason. */
function listedCounts(value: unknown): Map<string, number> {
  const counts = new Map<string, number>();
  if (!Array.isArray(value)) return counts;
  for (const item of value) {
    const reason = (item as { reason?: unknown } | null)?.reason;
    const key = typeof reason === "string" && reason ? reason : "invalid";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return counts;
}

/**
 * Why a completed run made no proposal: the server's reason and skipped
 * candidates by reason when it reports them (`no_proposal_reason`,
 * `skipped_by_reason`); otherwise what its chunks and `skipped_candidates` show.
 */
export function noProposalSummary(run?: PipelineRun): NoProposalSummary {
  const output = (run?.output_summary ?? {}) as Record<string, unknown>;
  const chunks = runChunks(run);
  const found = chunks.reduce((sum, c) => sum + (c.triples ?? 0), 0);
  const reported = reportedCounts(output.skipped_by_reason);
  const counts = reported.size > 0 ? reported : listedCounts(output.skipped_candidates);
  const refused = Array.isArray(output.refused_operations) ? output.refused_operations.length : 0;
  if (refused > 0 && !counts.has("refused")) counts.set("refused", refused);
  const skipped = [...counts.entries()]
    .map(([reason, count]) => ({ reason, count }))
    .sort((a, b) => b.count - a.count);
  // A sentence, shown as the server words it.
  const reason =
    typeof output.no_proposal_reason === "string" && output.no_proposal_reason.trim()
      ? output.no_proposal_reason.trim()
      : undefined;
  return {
    found,
    reason,
    skipped,
    candidatesFound: found > 0 || skipped.length > 0,
    failedNote: failedChunksWarning(chunks),
  };
}

/** "12 already exist, 8 no matching class", or "" when nothing was skipped. */
export function skippedText(skipped: NoProposalSummary["skipped"]): string {
  return skipped.map((s) => `${s.count} ${skipReasonLabel(s.reason)}`).join(", ");
}
