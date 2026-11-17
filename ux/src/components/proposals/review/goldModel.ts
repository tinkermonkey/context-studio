/**
 * Gold mode (#1614): a benchmark gold file loaded as a proposal to check
 * (`extraction_benchmark.py check`), read in the browser. Its client_metadata
 * holds what write-gold maps the decisions back with: each element's gold
 * key, tier, acceptable classes (class references) and aliases, by "$ref",
 * and each relationship's tier, by seq.
 */
import type { ChangeProposal, ProposedOperation, ReviewAnnotation } from "@/api/services/proposals";
import type { components } from "@/api/types";
import { DR_SOURCE } from "../decisionModel";
import { isAwaiting, type ChipVariant } from "../proposalModel";

type ClassResponse = components["schemas"]["ClassResponse"];

/** The implementation a gold check's proposal names in its origin. */
export const GOLD_CHECK_IMPLEMENTATION = "gold_check";

export type Tier = "core" | "supporting";
export type Split = "dev" | "holdout";

/** The tier an element added in review gets unless the reviewer says otherwise. */
export const ADDED_TIER: Tier = "supporting";

export interface GoldElement {
  key: string;
  tier: Tier;
  /** Class references ("product.feature"), as the gold file names classes. */
  acceptableClasses: string[];
  aliases: string[];
}

export interface GoldRelationship {
  source: string;
  predicate: string;
  target: string;
  tier: Tier;
}

export interface GoldCheck {
  document: string;
  split: Split;
  /** By the element's "$ref" (its gold key). */
  elements: Record<string, GoldElement>;
  /** By the relationship operation's seq. */
  relationships: Record<string, GoldRelationship>;
}

export const SPLIT_CHIP: Record<Split, ChipVariant> = { dev: "cyan", holdout: "violet" };

export const HOLDOUT_NOTE =
  "Holdout: check it like the others; its element-level errors are never shown where pipelines are tuned.";

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function asTier(value: unknown): Tier {
  return value === "supporting" ? "supporting" : "core";
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

/** The proposal's gold check, when it is one (origin gold_check, with its mapping). */
export function goldCheckOf(proposal: ChangeProposal | undefined): GoldCheck | undefined {
  if (proposal?.origin?.implementation_id !== GOLD_CHECK_IMPLEMENTATION) return undefined;
  const meta = asRecord(proposal.client_metadata?.gold_check);
  if (!meta || typeof meta.document !== "string") return undefined;
  const elements: Record<string, GoldElement> = {};
  for (const [ref, raw] of Object.entries(asRecord(meta.elements) ?? {})) {
    const item = asRecord(raw);
    if (!item) continue;
    elements[ref] = {
      key: typeof item.key === "string" ? item.key : ref,
      tier: asTier(item.tier),
      acceptableClasses: strings(item.acceptable_classes),
      aliases: strings(item.aliases),
    };
  }
  const relationships: Record<string, GoldRelationship> = {};
  for (const [seq, raw] of Object.entries(asRecord(meta.relationships) ?? {})) {
    const item = asRecord(raw);
    if (!item) continue;
    relationships[seq] = {
      source: String(item.source ?? ""),
      predicate: String(item.predicate ?? ""),
      target: String(item.target ?? ""),
      tier: asTier(item.tier),
    };
  }
  return {
    document: meta.document,
    split: meta.split === "holdout" ? "holdout" : "dev",
    elements,
    relationships,
  };
}

/** The gold entry of an element operation, by its "$ref". */
export function goldElementOf(
  gold: GoldCheck,
  operation: ProposedOperation,
): GoldElement | undefined {
  return operation.ref ? gold.elements[operation.ref] : undefined;
}

/** The tier gold gives an operation: its element's, or its relationship's by seq. */
export function goldTierOf(gold: GoldCheck, operation: ProposedOperation): Tier | undefined {
  if (operation.kind === "relationship") return gold.relationships[String(operation.seq)]?.tier;
  return goldElementOf(gold, operation)?.tier;
}

/** A class's reference as gold files name it: its DR reference, else its first, else its identifier. */
export function classRef(cls: ClassResponse): string {
  const references = cls.external_references ?? [];
  const dr = references.find((r) => r.source === DR_SOURCE);
  return (dr ?? references[0])?.identifier ?? cls.identifier;
}

/** The classes these references name, in their order; unknown references are left out. */
export function classesByRef(refs: string[], classes: ClassResponse[]): ClassResponse[] {
  const byRef = new Map(classes.map((c) => [classRef(c), c]));
  return refs.flatMap((ref) => byRef.get(ref) ?? []);
}

/** What the reviewer has noted on one operation so far. */
export interface GoldDraft {
  tier?: Tier;
  /** Class ids marked also defensible. */
  alsoDefensible: string[];
  /** On a better class: keep the old one as also defensible. */
  keepOld: boolean;
}

export const EMPTY_DRAFT: GoldDraft = { alsoDefensible: [], keepOld: false };

/**
 * The annotation a decision sends: the tier only when the reviewer changed it
 * from gold's, and the also defensible classes (with the replaced class when
 * kept), never the class the element ends up with. Undefined when nothing is noted.
 */
export function annotationOf(
  draft: GoldDraft,
  {
    goldTier,
    oldClassId,
    newClassId,
  }: { goldTier?: Tier; oldClassId?: string; newClassId?: string },
): ReviewAnnotation | undefined {
  const also = [
    ...draft.alsoDefensible,
    ...(newClassId && draft.keepOld && oldClassId ? [oldClassId] : []),
  ].filter((id, i, all) => id !== newClassId && all.indexOf(id) === i);
  const tierChanged = !!draft.tier && draft.tier !== goldTier;
  if (!tierChanged && also.length === 0) return undefined;
  return {
    ...(tierChanged ? { tier: draft.tier } : {}),
    ...(also.length > 0 ? { also_defensible: also } : {}),
  };
}

// ==================== The Gold page ====================

export type GoldStatus = "model-made" | "checked";

export const GOLD_STATUS_CHIP: Record<GoldStatus, ChipVariant> = {
  "model-made": "amber",
  checked: "emerald",
};

export interface GoldRow {
  proposalId: string;
  document: string;
  split: Split;
  individuals: number;
  relationships: number;
  decided: number;
  total: number;
  percent: number;
  status: GoldStatus;
  /** "Check gold" before any decision, "Continue" while some await, "Open" once checked. */
  action: "Check gold" | "Continue" | "Open";
}

/** One gold check's row: what it holds and how far its check is. */
export function goldRow(proposal: ChangeProposal, gold: GoldCheck): GoldRow {
  const reviewed = proposal.operations.filter(
    (o) => (o.op === "create" && o.kind === "individual") || o.kind === "relationship",
  );
  const awaiting = reviewed.filter(isAwaiting).length;
  const total = reviewed.length;
  const decided = total - awaiting;
  const status: GoldStatus = awaiting > 0 ? "model-made" : "checked";
  return {
    proposalId: proposal.id,
    document: gold.document,
    split: gold.split,
    individuals: reviewed.filter((o) => o.kind === "individual").length,
    relationships: reviewed.filter((o) => o.kind === "relationship").length,
    decided,
    total,
    percent: total === 0 ? 0 : Math.round((decided / total) * 100),
    status,
    action: decided === 0 ? "Check gold" : awaiting > 0 ? "Continue" : "Open",
  };
}

/** The gold checks among proposals, newest first; a reverted one is no check any more. */
export function goldRows(proposals: ChangeProposal[]): GoldRow[] {
  return proposals
    .filter((p) => p.status !== "reverted")
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .flatMap((p) => {
      const gold = goldCheckOf(p);
      return gold ? [goldRow(p, gold)] : [];
    });
}

/** The commands the Gold page shows. */
export const GOLD_COMMANDS = {
  check: (document: string) =>
    `python scripts/extraction_benchmark.py check --document ${document}`,
  writeGold: (document: string, proposalId: string) =>
    `python scripts/extraction_benchmark.py write-gold --document ${document} --proposal ${proposalId}`,
  validate: (document: string) =>
    `python scripts/extraction_benchmark.py validate --document ${document}`,
  replay: "python scripts/benchmark_replay.py --all",
  replayExternal: "python scripts/benchmark_external.py replay",
};

/** What each verdict writes to gold.json (the benchmark README's "Checking the gold"). */
export const GOLD_WRITES: { verdict: string; effect: string }[] = [
  { verdict: "Correct", effect: "The element is marked checked." },
  {
    verdict: "Better class",
    effect:
      "class is replaced; the old one goes to acceptable_classes only if marked also defensible. A corrected title replaces title and the old one becomes an alias.",
  },
  {
    verdict: "Tier and also defensible",
    effect: "Noted on any decision: tier is set, and the classes join acceptable_classes.",
  },
  {
    verdict: "Not an element",
    effect:
      "It moves to excluded with the note, and the relationships that use it go too. To merge two elements, reject one as a duplicate with a note.",
  },
  {
    verdict: "Added from the text",
    effect:
      "A new individual with the selected passage as its evidence and the tier noted (supporting when none), marked checked.",
  },
  {
    verdict: "Relationships",
    effect:
      "Accepted ones are marked checked and take a tier noted on them; rejected ones are removed.",
  },
];
