import { useQuery, keepPreviousData, type UseQueryResult } from "@tanstack/react-query";
import { SMALL_SET_LIMIT } from "@/api/config";
import { ontologyService } from "@/api/services/ontology";
import { useDebounce } from "@/hooks/useDebounce";
import { ENTITY_SEARCH_DEBOUNCE_MS } from "./useEntitySearch";

export type EntityType = "Class" | "Taxonomy" | "ConceptScheme" | "Individual" | "PropertyDefinition";

export interface EntityListResponse {
  items: Array<{ id: string; title?: string }>;
  total: number;
  limit: number;
  offset: number;
}

/** How many matches a picker shows for one search. */
export const ENTITY_PICKER_RESULT_LIMIT = 50;

/** Root cache keys, so the ontology mutations' prefix invalidation reaches picker queries. */
const ROOT_KEY: Record<EntityType, string> = {
  Class: "classes",
  Taxonomy: "taxonomies",
  ConceptScheme: "schemes",
  Individual: "individuals",
  PropertyDefinition: "properties",
};

/** Types whose list endpoint accepts an `ids` filter; the others are small bounded sets. */
const SUPPORTS_IDS: Record<EntityType, boolean> = {
  Class: true,
  Taxonomy: false,
  ConceptScheme: false,
  Individual: true,
  PropertyDefinition: true,
};

interface PickerListParams {
  q?: string;
  ids?: string[];
  limit: number;
  sort_by?: "title";
}

async function listEntities(type: EntityType, params: PickerListParams): Promise<EntityListResponse> {
  switch (type) {
    case "Class":
      return (await ontologyService.listClasses(params)) as EntityListResponse;
    case "Individual":
      return (await ontologyService.listIndividuals(params)) as EntityListResponse;
    case "PropertyDefinition":
      return (await ontologyService.listProperties(undefined, params)) as EntityListResponse;
    case "Taxonomy":
      return (await ontologyService.listTaxonomies(params)) as EntityListResponse;
    case "ConceptScheme":
      return (await ontologyService.listSchemes(undefined, params)) as EntityListResponse;
  }
}

/**
 * Server-side search for an entity picker: the first ENTITY_PICKER_RESULT_LIMIT
 * entities of this type whose title or identifier contains the debounced text.
 * Skipped while the text is empty (the picker shows no results then).
 */
export function useEntityTypeQuery(
  entityType: EntityType,
  text: string,
): UseQueryResult<EntityListResponse, Error> {
  const q = useDebounce(text.trim(), ENTITY_SEARCH_DEBOUNCE_MS);
  const params: PickerListParams = { q, limit: ENTITY_PICKER_RESULT_LIMIT, sort_by: "title" };
  return useQuery({
    queryKey: [ROOT_KEY[entityType], "picker-search", params],
    queryFn: () => listEntities(entityType, params),
    enabled: q.length > 0,
    placeholderData: keepPreviousData,
  });
}

/**
 * Resolve the picker's selected entities by id, so their labels show even when
 * they are not among the current search results. Types without an `ids` filter
 * (taxonomies, concept schemes) are small curated sets fetched in full.
 */
export function useEntitiesById(
  entityType: EntityType,
  ids: string[],
): UseQueryResult<EntityListResponse, Error> {
  const unique = [...new Set(ids.filter(Boolean))].sort();
  const params: PickerListParams = SUPPORTS_IDS[entityType]
    ? { ids: unique, limit: Math.max(unique.length, 1) }
    : { limit: SMALL_SET_LIMIT };
  return useQuery({
    queryKey: [ROOT_KEY[entityType], "picker-selected", params],
    queryFn: () => listEntities(entityType, params),
    enabled: unique.length > 0,
    placeholderData: keepPreviousData,
  });
}
