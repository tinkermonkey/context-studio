import type { Claim, ClaimFilters, Validity } from "@/api/services/claims";

export const VALIDITIES: Validity[] = [
  "real_defect",
  "works_as_designed",
  "judgment_call",
  "out_of_scope",
];

export const VALIDITY_LABELS: Record<Validity, string> = {
  real_defect: "real defect",
  works_as_designed: "works as designed",
  judgment_call: "judgment call",
  out_of_scope: "out of scope",
};

/** A real defect needs work; works-as-designed needs none; a judgment call needs a person. */
export const VALIDITY_VARIANT: Record<Validity, "rose" | "emerald" | "amber" | "neutral"> = {
  real_defect: "rose",
  works_as_designed: "emerald",
  judgment_call: "amber",
  out_of_scope: "neutral",
};

/** Severity 0 to 3. */
export const SEVERITY_LABELS = ["cosmetic", "minor", "significant", "blocking"] as const;
/** Fix scope 0 to 3. */
export const FIX_SCOPE_LABELS = ["wording", "additive", "breaking", "roadmap"] as const;

/**
 * DR's triage categories (local-server domain/pipelines/claim_triage/
 * configurations/default.py DR_CATEGORIES), offered as verdict categories.
 */
export const DR_CATEGORIES = [
  "attribute_typing",
  "attribute_naming",
  "enum_gap",
  "missing_attribute",
  "type_overlap",
  "definition_conflict",
  "relationship_redundant",
  "relationship_direction",
  "relationship_missing",
  "classifier_concern",
  "other",
] as const;

export function isValidity(value: unknown): value is Validity {
  return VALIDITIES.includes(value as Validity);
}

/** "2 · significant" for a 0–3 score, "—" when unset. */
export function formatScore(score: number | null | undefined, labels: readonly string[]): string {
  if (score === null || score === undefined) return "—";
  return labels[score] ? `${score} · ${labels[score]}` : String(score);
}

export function formatProbability(p: number | null | undefined): string {
  return p === null || p === undefined ? "—" : p.toFixed(2);
}

/** The triage's probability for the validity it chose. */
export function triageConfidence(claim: Claim): number | undefined {
  const triage = claim.triage;
  return triage ? triage.validity_probabilities?.[triage.validity] : undefined;
}

/** Probabilities, most likely first. */
export function rankedProbabilities(
  probabilities: Record<string, number> | undefined,
): Array<[string, number]> {
  return Object.entries(probabilities ?? {}).sort((a, b) => b[1] - a[1]);
}

/** The verdict's category choices: DR's list, plus any other category already in play. */
export function categoryOptions(...extra: Array<string | null | undefined>): string[] {
  const options: string[] = [...DR_CATEGORIES];
  for (const category of extra) {
    if (category && !options.includes(category)) options.push(category);
  }
  return options;
}

export type TriageFilter = "triaged" | "untriaged";
export type VerdictFilter = "with" | "without";

/** The page's filters, as they appear in the URL. */
export interface ClaimsSearch {
  taxonomy?: string;
  subject?: string;
  validity?: Validity;
  triage?: TriageFilter;
  verdict?: VerdictFilter;
  /** The selected claim's id. */
  selected?: string;
}

/** The URL's filters as the claims API's filters. */
export function apiFilters(search: ClaimsSearch): ClaimFilters {
  return {
    subject_id: search.subject,
    validity: search.validity,
    triaged: search.triage === undefined ? undefined : search.triage === "triaged",
    has_verdict: search.verdict === undefined ? undefined : search.verdict === "with",
  };
}
