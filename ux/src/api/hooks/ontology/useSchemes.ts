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
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.schemesRoot });
    },
  });
}

export function useUpdateScheme() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ConceptSchemeUpdateRequest }) =>
      ontologyService.updateScheme(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.schemesRoot });
    },
  });
}

export function useMoveScheme() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: SchemeMoveRequest }) =>
      ontologyService.updateScheme(id, { taxonomy_id: data.target_taxonomy_id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.schemesRoot });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classesRoot });
    },
  });
}

export function useDeleteScheme() {
  const queryClient = useQueryClient();
  return useMutation({
    meta: { skipGlobalErrorToast: true },
    mutationFn: (id: string) => ontologyService.deleteScheme(id),
    // The backend rejects deleting a scheme that still has classes, so a
    // successful delete only removes an empty scheme. The schemesRoot prefix
    // also refreshes the parent taxonomy's scheme list.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.schemesRoot });
    },
  });
}
