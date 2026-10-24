import type { SourceSpan } from "@/api/hooks/pipeline/useExtractionCandidates";
import type { ReviewDecisionValue } from "@/api/hooks/pipeline/useApplyReviewedRun";

/** A provenance span tagged with the key of the item it belongs to. */
export interface KeyedSpan extends SourceSpan {
  key: string;
}

export interface LocatedSpan extends KeyedSpan {
  start: number;
  end: number;
}

export interface TextSegment {
  start: number;
  end: number;
  covering: LocatedSpan[];
}

export const pct = (v: number | null | undefined): string =>
  v == null ? "—" : `${Math.round(v * 100)}%`;

export const isLocated = (s: SourceSpan): s is SourceSpan & { start: number; end: number } =>
  s.start != null && s.end != null;

/**
 * Split text at every span boundary. Overlapping spans produce segments covered
 * by several keys; spans without offsets (unlocated) are skipped here and shown
 * only in the inspector's provenance list.
 */
export function segmentText(text: string, spans: KeyedSpan[]): TextSegment[] {
  const located = spans.filter(
    (s): s is LocatedSpan => isLocated(s) && s.start < s.end && s.end <= text.length,
  );
  const cuts = Array.from(
    new Set([0, text.length, ...located.flatMap((s) => [s.start, s.end])]),
  ).sort((a, b) => a - b);
  const segments: TextSegment[] = [];
  for (let i = 0; i < cuts.length - 1; i++) {
    const start = cuts[i];
    const end = cuts[i + 1];
    segments.push({
      start,
      end,
      covering: located.filter((s) => s.start <= start && s.end >= end),
    });
  }
  return segments;
}

/** Locate a mention label in the run text (recognition hits carry no spans). */
export function locateMention(text: string, label: string): SourceSpan {
  const at = label ? text.indexOf(label) : -1;
  return at < 0
    ? { quote: label, start: null, end: null }
    : { quote: label, start: at, end: at + label.length };
}

export function countDecisions(
  decisions: Record<string, ReviewDecisionValue>,
  keys: string[],
): Record<ReviewDecisionValue, number> {
  const c = { yes: 0, no: 0, pending: 0 };
  keys.forEach((k) => c[decisions[k] ?? "pending"]++);
  return c;
}

/** DR spec layers (spec 0.9.x). Unknown layers (e.g. a newer spec's 13th) map to null. */
const DR_LAYERS: Record<string, string> = {
  motivation: "01",
  business: "02",
  security: "03",
  application: "04",
  technology: "05",
  api: "06",
  "data-model": "07",
  "data-store": "08",
  ux: "09",
  navigation: "10",
  apm: "11",
  testing: "12",
};

/** Layer keys as they appear in imported Class identifiers ("data-model" → "data_model"), longest first. */
const DR_LAYER_SLUGS = Object.keys(DR_LAYERS)
  .map((layer) => ({ layer, slug: layer.replace(/-/g, "_") }))
  .sort((a, b) => b.slug.length - a.slug.length);

/**
 * Map a DR class key to its layer. Accepts the dotted spec node id
 * ("motivation.stakeholder") and the imported Class identifier slug
 * ("motivation_stakeholder", "data_model_entity").
 */
export function drLayerOf(classKey?: string | null): { layer: string; num: string } | null {
  if (!classKey) return null;
  const key = classKey.toLowerCase();
  if (key.includes(".")) {
    const layer = key.split(".")[0];
    const num = DR_LAYERS[layer];
    return num ? { layer, num } : null;
  }
  const hit = DR_LAYER_SLUGS.find(({ slug }) => key.startsWith(`${slug}_`));
  return hit ? { layer: hit.layer, num: DR_LAYERS[hit.layer] } : null;
}
