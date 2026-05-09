import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService } from "@/api/services/ontology";
import type { components } from "@/api/types";

type PropertyDefinitionCreateRequest =
  components["schemas"]["PropertyDefinitionCreateRequest"];
type PropertyDefinitionUpdateRequest =
  components["schemas"]["PropertyDefinitionUpdateRequest"];

export function useProperties(isRelevant?: boolean) {
  return useQuery({
    queryKey: QUERY_KEYS.properties,
    queryFn: () => ontologyService.listProperties(isRelevant),
  });
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
    mutationFn: (data: PropertyDefinitionCreateRequest) =>
      ontologyService.createProperty(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.properties });
    },
  });
}

export function useUpdateProperty() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: PropertyDefinitionUpdateRequest;
    }) => ontologyService.updateProperty(id, data),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.properties });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.property(id) });
    },
  });
}

export function useDeleteProperty() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => ontologyService.deleteProperty(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.properties });
    },
  });
}
