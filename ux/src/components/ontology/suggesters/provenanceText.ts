import type { SourceSpan } from "@/api/services/pipeline";

/** Candidate provenance is a list of source spans; suggesters show their quotes inline. */
export function provenanceText(spans?: SourceSpan[] | null): string {
  return (spans ?? [])
    .map((s) => s.quote)
    .filter(Boolean)
    .join(" … ");
}
