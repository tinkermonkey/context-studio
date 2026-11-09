import { useQuery, useQueries, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS, SMALL_SET_LIMIT } from "@/api/config";
import { ontologyService, type ClassListParams } from "@/api/services/ontology";
import type { components } from "@/api/types";
import { listQueryOptions, type ListQueryOptions } from "./listQueryOptions";
import { listByIdChunks, loadedData, uniqueIds } from "./idChunks";

type ClassCreateRequest = components["schemas"]["ClassCreateRequest"];
type ClassUpdateRequest = components["schemas"]["ClassUpdateRequest"];
type ClassMoveRequest = components["schemas"]["ClassMoveRequest"];

export function useClasses(params?: ClassListParams, options?: ListQueryOptions) {
  return useQuery({
    queryKey: QUERY_KEYS.classes(params),
    queryFn: () => ontologyService.listClasses(params),
    ...listQueryOptions(options),
  });
}

/**
 * Fetch exactly the classes with these ids (e.g. to resolve titles for the
 * rows on one table page), in chunks of 100. Skips the request when there are
 * no ids.
 */
export function useClassesByIds(ids: Array<string | null | undefined>) {
  const unique = uniqueIds(ids);
  return useQuery({
    queryKey: QUERY_KEYS.classes({ ids: unique, limit: Math.max(unique.length, 1) }),
    queryFn: () =>
      listByIdChunks(unique, (chunk) =>
        ontologyService.listClasses({ ids: chunk, limit: chunk.length }),
      ),
    ...listQueryOptions({ enabled: unique.length > 0, keepPrevious: true }),
  });
}

/**
 * Every class of one taxonomy: its concept schemes, then each scheme's classes
 * (bounded per scheme). Skipped while `enabled` is false.
 */
export function useTaxonomyClasses(taxonomyId: string, enabled = true) {
  const schemeParams = { limit: SMALL_SET_LIMIT };
  const schemes = useQuery({
    queryKey: [...QUERY_KEYS.schemes(taxonomyId), schemeParams],
    queryFn: () => ontologyService.listSchemes(taxonomyId, schemeParams),
    enabled: enabled && !!taxonomyId,
  });
  const schemeIds = (schemes.data?.items ?? []).map((s) => s.id);
  const results = useQueries({
    queries: schemeIds.map((schemeId) => {
      const params: ClassListParams = { concept_scheme_id: schemeId, limit: SMALL_SET_LIMIT };
      return {
        queryKey: QUERY_KEYS.classes(params),
        queryFn: () => ontologyService.listClasses(params),
        enabled,
      };
    }),
  });
  const isSuccess = schemes.isSuccess && results.every((r) => r.isSuccess);
  return {
    classes: isSuccess ? results.flatMap((r) => r.data?.items ?? []) : undefined,
    isSuccess,
    isError: schemes.isError || results.some((r) => r.isError),
  };
}

/**
 * Class count per concept scheme, from one `limit=1` request per scheme that
 * reads the response `total`. Returns a map of scheme id → count (missing
 * while loading).
 */
export function useClassCountsByScheme(schemeIds: string[]): Record<string, number> {
  const results = useQueries({
    queries: schemeIds.map((schemeId) => {
      const params: ClassListParams = { concept_scheme_id: schemeId, limit: 1 };
      return {
        queryKey: QUERY_KEYS.classes(params),
        queryFn: () => ontologyService.listClasses(params),
      };
    }),
  });
  const counts: Record<string, number> = {};
  schemeIds.forEach((id, i) => {
    const total = results[i]?.data?.total;
    if (total !== undefined) counts[id] = total;
  });
  return counts;
}

export function useClass(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.class(id),
    queryFn: () => ontologyService.getClass(id),
    enabled: !!id,
  });
}

/** A class's attribute definitions (under the class key, so class mutations refresh it). */
export function useClassAttributeDefinitions(classId: string) {
  return useQuery({
    queryKey: [...QUERY_KEYS.class(classId), "attribute-definitions"],
    queryFn: () => ontologyService.listClassAttributeDefinitions(classId, { limit: 500 }),
    enabled: !!classId,
  });
}

/**
 * Fetch the attribute definitions with these ids, one request each (the API
 * has no ids filter for them). Skips the requests when there are no ids.
 */
export function useAttributeDefinitionsByIds(ids: Array<string | null | undefined>) {
  return useQueries({
    queries: uniqueIds(ids).map((id) => ({
      queryKey: QUERY_KEYS.attributeDefinition(id),
      queryFn: () => ontologyService.getAttributeDefinition(id),
      staleTime: 5 * 60 * 1000,
      retry: false,
    })),
    combine: loadedData,
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
