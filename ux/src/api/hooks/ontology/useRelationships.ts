import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService } from "@/api/services/ontology";
import type { components } from "@/api/types";

type RelationshipResponse = components["schemas"]["RelationshipResponse"];
type RelationshipCreateRequest = components["schemas"]["RelationshipCreateRequest"];

interface RelationshipListParams {
  source_id?: string;
  target_id?: string;
  property_id?: string;
}

export function useRelationships(params?: RelationshipListParams) {
  return useQuery({
    queryKey: QUERY_KEYS.relationships(params),
    queryFn: () => ontologyService.listRelationships(params),
  });
}

export function useRelationship(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.relationship(id),
    queryFn: () => ontologyService.getRelationship(id),
    enabled: !!id,
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
