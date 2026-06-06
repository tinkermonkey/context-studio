import { useQuery, UseQueryResult } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService } from "@/api/services/ontology";

type EntityType = "Class" | "Taxonomy" | "ConceptScheme" | "Individual";

interface ListResponse {
  items: Array<{ id: string; title?: string }>;
  total: number;
  limit: number;
  offset: number;
}

export function useEntityTypeQuery(
  entityType: EntityType
): UseQueryResult<ListResponse, Error> {
  const queryKey =
    entityType === "Class"
      ? QUERY_KEYS.classes()
      : entityType === "Taxonomy"
        ? QUERY_KEYS.taxonomies
        : entityType === "ConceptScheme"
          ? QUERY_KEYS.schemes()
          : QUERY_KEYS.individuals();

  const queryFn = async () => {
    const response =
      entityType === "Class"
        ? await ontologyService.listClasses()
        : entityType === "Taxonomy"
          ? await ontologyService.listTaxonomies()
          : entityType === "ConceptScheme"
            ? await ontologyService.listSchemes()
            : await ontologyService.listIndividuals();
    return response as ListResponse;
  };

  return useQuery({ queryKey, queryFn });
}
