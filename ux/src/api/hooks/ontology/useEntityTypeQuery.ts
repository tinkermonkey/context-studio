import { useQuery, UseQueryResult } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService } from "@/api/services/ontology";

type EntityType = "Class" | "Taxonomy" | "ConceptScheme" | "Individual" | "PropertyDefinition";

interface ListResponse {
  items: Array<{ id: string; title?: string }>;
  total: number;
  limit: number;
  offset: number;
}

export function useEntityTypeQuery(entityType: EntityType): UseQueryResult<ListResponse, Error> {
  const queryKey =
    entityType === "Class"
      ? QUERY_KEYS.classes()
      : entityType === "Taxonomy"
        ? QUERY_KEYS.taxonomies
        : entityType === "ConceptScheme"
          ? QUERY_KEYS.schemes()
          : entityType === "Individual"
            ? QUERY_KEYS.individuals()
            : QUERY_KEYS.properties;

  const queryFn = async () => {
    const response =
      entityType === "Class"
        ? await ontologyService.listClasses()
        : entityType === "Taxonomy"
          ? await ontologyService.listTaxonomies()
          : entityType === "ConceptScheme"
            ? await ontologyService.listSchemes()
            : entityType === "Individual"
              ? await ontologyService.listIndividuals()
              : await ontologyService.listProperties();
    return response as ListResponse;
  };

  return useQuery({ queryKey, queryFn });
}
