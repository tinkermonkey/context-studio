import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService } from "@/api/services/ontology";

/** The kinds of entity provenance is kept for, with a sources endpoint each. */
export type ProvenanceKind = "individual" | "relationship";

/**
 * The source passages behind an individual or relationship (its provenance),
 * one per passage of each applied operation. Proposal applies and reverts
 * refresh it, as it sits under the entity's query root.
 */
export function useEntitySources(kind: ProvenanceKind, id: string | undefined) {
  return useQuery({
    queryKey:
      kind === "individual"
        ? QUERY_KEYS.individualSources(id ?? "")
        : QUERY_KEYS.relationshipSources(id ?? ""),
    queryFn: () =>
      kind === "individual"
        ? ontologyService.listIndividualSources(id!)
        : ontologyService.listRelationshipSources(id!),
    enabled: !!id,
  });
}
