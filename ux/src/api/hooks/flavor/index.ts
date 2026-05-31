import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { flavorService } from "@/api/services/flavor";

// TODO: These types are not yet in the OpenAPI spec (Phase 2 work)
type PipelineFlavorCreateRequest = any;
type PipelineFlavorUpdateRequest = any;

export function useFlavors() {
  return useQuery({
    queryKey: QUERY_KEYS.flavors,
    queryFn: () => flavorService.listFlavors(),
  });
}

export function useFlavor(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.flavor(id),
    queryFn: () => flavorService.getFlavor(id),
    enabled: !!id,
  });
}

export function useCreateFlavor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: PipelineFlavorCreateRequest) => flavorService.createFlavor(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.flavors });
    },
  });
}

export function useUpdateFlavor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PipelineFlavorUpdateRequest }) =>
      flavorService.updateFlavor(id, data),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.flavors });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.flavor(id) });
    },
  });
}

export function useDeleteFlavor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => flavorService.deleteFlavor(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.flavors });
    },
  });
}
