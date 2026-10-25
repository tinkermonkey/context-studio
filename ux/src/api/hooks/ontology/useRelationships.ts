import { useQuery, useQueries, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService, type RelationshipListParams } from "@/api/services/ontology";
import type { components } from "@/api/types";
import { listQueryOptions, type ListQueryOptions } from "./listQueryOptions";

type RelationshipCreateRequest = components["schemas"]["RelationshipCreateRequest"];

export function useRelationships(params?: RelationshipListParams, options?: ListQueryOptions) {
  return useQuery({
    queryKey: QUERY_KEYS.relationships(params),
    queryFn: () => ontologyService.listRelationships(params),
    ...listQueryOptions(options),
  });
}

/**
 * The newest relationships with any of `entityIds` as source or target: one
 * source and one target request per id (each capped at `limit`), merged,
 * de-duplicated and trimmed to `limit`. `total` sums the per-request totals,
 * so a relationship between two of the ids counts twice.
 */
export function useRelationshipsTouching(entityIds: string[], limit: number) {
  const ids = [...new Set(entityIds)];
  const paramsList: RelationshipListParams[] = ids.flatMap((id) => [
    { source_id: id, limit, sort_order: "desc" },
    { target_id: id, limit, sort_order: "desc" },
  ]);
  const results = useQueries({
    queries: paramsList.map((params) => ({
      queryKey: QUERY_KEYS.relationships(params),
      queryFn: () => ontologyService.listRelationships(params),
    })),
  });
  const byId = new Map<string, NonNullable<(typeof results)[number]["data"]>["items"][number]>();
  let total = 0;
  for (const result of results) {
    total += result.data?.total ?? 0;
    for (const rel of result.data?.items ?? []) byId.set(rel.id, rel);
  }
  const items = [...byId.values()]
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))
    .slice(0, limit);
  return {
    items,
    total,
    error: results.find((r) => r.error)?.error ?? null,
    refetch: () => results.forEach((r) => void r.refetch()),
  };
}

export function useCreateRelationship() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: RelationshipCreateRequest) => ontologyService.createRelationship(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.relationshipsRoot });
      // Class drawers and property drawers show relationship counts / "used by".
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classesRoot });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.properties });
    },
  });
}

export function useDeleteRelationship() {
  const queryClient = useQueryClient();
  return useMutation({
    meta: { skipGlobalErrorToast: true },
    mutationFn: (id: string) => ontologyService.deleteRelationship(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.relationshipsRoot });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classesRoot });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.properties });
    },
  });
}
