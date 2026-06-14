import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService, type IndividualListParams } from "@/api/services/ontology";
import type { components } from "@/api/types";

type IndividualCreateRequest = components["schemas"]["IndividualCreateRequest"];
type IndividualUpdateRequest = components["schemas"]["IndividualUpdateRequest"];
type IndividualClassRequest = components["schemas"]["IndividualClassRequest"];
type IndividualClassListRequest = components["schemas"]["IndividualClassListRequest"];

export function useIndividuals(params?: IndividualListParams) {
  return useQuery({
    queryKey: QUERY_KEYS.individuals(params),
    queryFn: () => ontologyService.listIndividuals(params),
  });
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
