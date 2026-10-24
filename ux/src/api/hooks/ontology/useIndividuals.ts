import { useQuery, useQueries, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService, type IndividualListParams } from "@/api/services/ontology";
import type { components } from "@/api/types";
import { listQueryOptions, type ListQueryOptions } from "./listQueryOptions";

type IndividualCreateRequest = components["schemas"]["IndividualCreateRequest"];
type IndividualUpdateRequest = components["schemas"]["IndividualUpdateRequest"];
type IndividualClassRequest = components["schemas"]["IndividualClassRequest"];
type IndividualClassListRequest = components["schemas"]["IndividualClassListRequest"];

export function useIndividuals(params?: IndividualListParams, options?: ListQueryOptions) {
  return useQuery({
    queryKey: QUERY_KEYS.individuals(params),
    queryFn: () => ontologyService.listIndividuals(params),
    ...listQueryOptions(options),
  });
}

/**
 * Individuals that belong to any of `classIds` (one request per class, each
 * capped at `limit`), merged and de-duplicated in request order.
 */
export function useIndividualsInClasses(classIds: string[], limit: number) {
  const ids = [...new Set(classIds)];
  const results = useQueries({
    queries: ids.map((classId) => {
      const params: IndividualListParams = { class_id: classId, limit, sort_by: "title" };
      return {
        queryKey: QUERY_KEYS.individuals(params),
        queryFn: () => ontologyService.listIndividuals(params),
      };
    }),
  });
  const byId = new Map<string, NonNullable<(typeof results)[number]["data"]>["items"][number]>();
  for (const result of results) {
    for (const ind of result.data?.items ?? []) if (!byId.has(ind.id)) byId.set(ind.id, ind);
  }
  return [...byId.values()];
}

export function useIndividual(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.individual(id),
    queryFn: () => ontologyService.getIndividual(id),
    enabled: !!id,
  });
}

export function useCreateIndividual() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: IndividualCreateRequest) => ontologyService.createIndividual(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.individualsRoot });
      // Class drawers show per-class individual counts.
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classesRoot });
    },
  });
}

export function useUpdateIndividual() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: IndividualUpdateRequest }) =>
      ontologyService.updateIndividual(id, data),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.individualsRoot });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.individual(id) });
    },
  });
}

export function useDeleteIndividual() {
  const queryClient = useQueryClient();
  return useMutation({
    meta: { skipGlobalErrorToast: true },
    mutationFn: (id: string) => ontologyService.deleteIndividual(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.individualsRoot });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classesRoot });
    },
  });
}

export function useAddClassToIndividual() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ individualId, data }: { individualId: string; data: IndividualClassRequest }) =>
      ontologyService.addParentClass(individualId, data),
    onSuccess: (_result, { individualId }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.individualsRoot });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.individual(individualId) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classesRoot });
    },
  });
}

export function useRemoveClassFromIndividual() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ individualId, classId }: { individualId: string; classId: string }) =>
      ontologyService.removeParentClass(individualId, classId),
    onSuccess: (_result, { individualId }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.individualsRoot });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.individual(individualId) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classesRoot });
    },
  });
}

export function useReorderIndividualClasses() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      individualId,
      data,
    }: {
      individualId: string;
      data: IndividualClassListRequest;
    }) => ontologyService.reorderIndividualClasses(individualId, data),
    onSuccess: (_result, { individualId }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.individualsRoot });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.individual(individualId) });
    },
  });
}

export function useIndividualInheritedProperties(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.individual(id, "inherited-properties"),
    queryFn: () => ontologyService.getIndividualInheritedProperties(id),
    enabled: !!id,
  });
}
