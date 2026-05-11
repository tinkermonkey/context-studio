import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService, type RelationshipListParams } from "@/api/services/ontology";
import type { components } from "@/api/types";

type RelationshipCreateRequest = components["schemas"]["RelationshipCreateRequest"];

export function useRelationships(params?: RelationshipListParams) {
  return useQuery({
    queryKey: QUERY_KEYS.relationships(params),
    queryFn: () => ontologyService.listRelationships(params),
  });
}

export function useCreateRelationship() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: RelationshipCreateRequest) => ontologyService.createRelationship(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.relationships() });
    },
  });
}

export function useDeleteRelationship() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => ontologyService.deleteRelationship(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.relationships() });
    },
  });
}
