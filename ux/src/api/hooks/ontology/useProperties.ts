import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService, type PropertyListParams } from "@/api/services/ontology";
import type { components } from "@/api/types";
import { listQueryOptions, type ListQueryOptions } from "./listQueryOptions";

type PropertyDefinitionCreateRequest = components["schemas"]["PropertyDefinitionCreateRequest"];
type PropertyDefinitionUpdateRequest = components["schemas"]["PropertyDefinitionUpdateRequest"];

export function useProperties(
  isRelevant?: boolean,
  params?: PropertyListParams,
  options?: ListQueryOptions,
) {
  return useQuery({
    // Include isRelevant and params in the key so filtered, paged and unfiltered
    // queries do not collide on one cache entry. Mutations invalidate the
    // ["properties"] prefix, which still matches all of them.
    queryKey: [...QUERY_KEYS.properties, isRelevant ?? null, params ?? null],
    queryFn: () => ontologyService.listProperties(isRelevant, params),
    ...listQueryOptions(options),
  });
}

/** Fetch exactly the property definitions with these ids; skipped when there are none. */
export function usePropertiesByIds(ids: Array<string | null | undefined>) {
  const unique = [...new Set(ids.filter((id): id is string => !!id))].sort();
  return useProperties(
    undefined,
    { ids: unique, limit: Math.max(unique.length, 1) },
    { enabled: unique.length > 0, keepPrevious: true },
  );
}

export function useProperty(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.property(id),
    queryFn: () => ontologyService.getProperty(id),
    enabled: !!id,
  });
}

export function useCreateProperty() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: PropertyDefinitionCreateRequest) => ontologyService.createProperty(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.properties });
      // Scheme and class pages count property definitions by domain class.
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.contentCountsRoot });
    },
  });
}

export function useUpdateProperty() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PropertyDefinitionUpdateRequest }) =>
      ontologyService.updateProperty(id, data),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.properties });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.property(id) });
      // Scheme and class pages count property definitions by domain class.
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.contentCountsRoot });
    },
  });
}

export function useSetPropertyRelevance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, isRelevant }: { id: string; isRelevant: boolean | null }) =>
      ontologyService.updateProperty(id, { is_relevant: isRelevant }),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.properties });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.property(id) });
    },
  });
}

export function useDeleteProperty() {
  const queryClient = useQueryClient();
  return useMutation({
    meta: { skipGlobalErrorToast: true },
    mutationFn: (id: string) => ontologyService.deleteProperty(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.properties });
      // Scheme and class pages count property definitions by domain class.
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.contentCountsRoot });
    },
    // The drawer defers this delete behind an undo window and shows an
    // optimistic "deleted" toast up front. The backend rejects deleting a
    // property still referenced by relationships, so on rejection re-fetch the
    // list so the still-present row reflects server truth instead of
    // contradicting the error toast.
    onError: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.properties });
    },
  });
}
