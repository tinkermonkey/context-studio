import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService } from "@/api/services/ontology";
import type { components } from "@/api/types";

type IndividualCreateRequest = components["schemas"]["IndividualCreateRequest"];
type IndividualUpdateRequest = components["schemas"]["IndividualUpdateRequest"];

interface IndividualListParams {
  class_id?: string;
  limit?: number;
  offset?: number;
}

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
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.individuals() });
    },
  });
}

export function useUpdateIndividual() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: IndividualUpdateRequest }) =>
      ontologyService.updateIndividual(id, data),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.individuals() });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.individual(id) });
    },
  });
}

export function useDeleteIndividual() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => ontologyService.deleteIndividual(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.individuals() });
    },
  });
}
