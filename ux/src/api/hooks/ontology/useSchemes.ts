import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService } from "@/api/services/ontology";
import type { components } from "@/api/types";

type ConceptSchemeCreateRequest = components["schemas"]["ConceptSchemeCreateRequest"];
type ConceptSchemeUpdateRequest = components["schemas"]["ConceptSchemeUpdateRequest"];

interface SchemeMoveRequest {
  target_taxonomy_id: string;
}

export function useSchemes(taxonomyId?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.schemes(taxonomyId),
    queryFn: () => ontologyService.listSchemes(taxonomyId),
  });
}

export function useScheme(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.scheme(id),
    queryFn: () => ontologyService.getScheme(id),
    enabled: !!id,
  });
}

export function useCreateScheme() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ taxonomyId, data }: { taxonomyId: string; data: ConceptSchemeCreateRequest }) =>
      ontologyService.createScheme(taxonomyId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.schemes() });
    },
  });
}

export function useUpdateScheme() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ConceptSchemeUpdateRequest }) =>
      ontologyService.updateScheme(id, data),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.schemes() });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.scheme(id) });
    },
  });
}

export function useMoveScheme() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: SchemeMoveRequest }) =>
      ontologyService.updateScheme(id, { taxonomy_id: data.target_taxonomy_id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.schemes() });
    },
  });
}

export function useDeleteScheme() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => ontologyService.deleteScheme(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.schemes() });
    },
  });
}
