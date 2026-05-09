import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService } from "@/api/services/ontology";
import type { components } from "@/api/types";

type ClassCreateRequest = components["schemas"]["ClassCreateRequest"];
type ClassUpdateRequest = components["schemas"]["ClassUpdateRequest"];
type ClassMoveRequest = components["schemas"]["ClassMoveRequest"];

interface ClassListParams {
  concept_scheme_id?: string;
  parent_class_id?: string;
  limit?: number;
  offset?: number;
}

export function useClasses(params?: ClassListParams) {
  return useQuery({
    queryKey: QUERY_KEYS.classes(params),
    queryFn: () => ontologyService.listClasses(params),
  });
}

export function useClass(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.class(id),
    queryFn: () => ontologyService.getClass(id),
    enabled: !!id,
  });
}

export function useCreateClass() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ schemeId, data }: { schemeId: string; data: ClassCreateRequest }) =>
      ontologyService.createClass(schemeId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classes() });
    },
  });
}

export function useUpdateClass() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ClassUpdateRequest }) =>
      ontologyService.updateClass(id, data),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classes() });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.class(id) });
    },
  });
}

export function useMoveClass() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ClassMoveRequest }) =>
      ontologyService.moveClass(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classes() });
    },
  });
}

export function useDeleteClass() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => ontologyService.deleteClass(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classes() });
    },
  });
}
