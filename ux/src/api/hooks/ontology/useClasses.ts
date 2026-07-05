import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService, type ClassListParams } from "@/api/services/ontology";
import type { components } from "@/api/types";

type ClassCreateRequest = components["schemas"]["ClassCreateRequest"];
type ClassUpdateRequest = components["schemas"]["ClassUpdateRequest"];
type ClassMoveRequest = components["schemas"]["ClassMoveRequest"];

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
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classesRoot });
      // Scheme drawers show per-scheme class counts.
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.schemesRoot });
    },
  });
}

export function useUpdateClass() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ClassUpdateRequest }) =>
      ontologyService.updateClass(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classesRoot });
    },
  });
}

export function useMoveClass() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ClassMoveRequest }) =>
      ontologyService.moveClass(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classesRoot });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.schemesRoot });
    },
  });
}

export function useDeleteClass() {
  const queryClient = useQueryClient();
  return useMutation({
    meta: { skipGlobalErrorToast: true },
    mutationFn: (id: string) => ontologyService.deleteClass(id),
    // The backend rejects deleting a class that still has subclasses or
    // individuals, so a successful delete only removes a leaf class. Refresh
    // the class list and the parent scheme's class count.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classesRoot });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.schemesRoot });
    },
    // The drawer defers this delete behind an undo window and shows an
    // optimistic "deleted" toast up front. When the backend then rejects the
    // delete, re-fetch so the still-present row reflects server truth instead
    // of contradicting the error toast.
    onError: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classesRoot });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.schemesRoot });
    },
  });
}
