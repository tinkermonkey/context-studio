import { ENTITY_SEARCH_LIMIT } from "@/api/config";
import type { ClassListParams, IndividualListParams } from "@/api/services/ontology";
import { useDebounce } from "@/hooks/useDebounce";
import { useClasses } from "./useClasses";
import { useIndividuals } from "./useIndividuals";
import { useProperties } from "./useProperties";

/** Debounce applied to picker search text before it is sent as `q`. */
export const ENTITY_SEARCH_DEBOUNCE_MS = 250;

function useSearchTerm(text: string): string | undefined {
  const debounced = useDebounce(text.trim(), ENTITY_SEARCH_DEBOUNCE_MS);
  return debounced || undefined;
}

/**
 * Server-side class search for pickers: the first ENTITY_SEARCH_LIMIT classes
 * (by title) whose title or identifier contains the debounced text. An empty
 * text lists the first classes alphabetically.
 */
export function useClassSearch(
  text: string,
  filters?: Pick<ClassListParams, "concept_scheme_id">,
  options?: { enabled?: boolean },
) {
  const q = useSearchTerm(text);
  return useClasses(
    { ...filters, q, limit: ENTITY_SEARCH_LIMIT, sort_by: "title" },
    { enabled: options?.enabled, keepPrevious: true },
  );
}

/** Server-side individual search for pickers (see useClassSearch). */
export function useIndividualSearch(
  text: string,
  filters?: Pick<IndividualListParams, "class_id">,
  options?: { enabled?: boolean },
) {
  const q = useSearchTerm(text);
  return useIndividuals(
    { ...filters, q, limit: ENTITY_SEARCH_LIMIT, sort_by: "title" },
    { enabled: options?.enabled, keepPrevious: true },
  );
}

/** Server-side property definition search for pickers (see useClassSearch). */
export function usePropertySearch(text: string, options?: { enabled?: boolean }) {
  const q = useSearchTerm(text);
  return useProperties(
    undefined,
    { q, limit: ENTITY_SEARCH_LIMIT, sort_by: "title" },
    { enabled: options?.enabled, keepPrevious: true },
  );
}
