import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { demoDatasetService } from "@/api/services/demoDataset";

export function useDemoDatasets() {
  return useQuery({
    queryKey: QUERY_KEYS.demoDatasets,
    queryFn: () => demoDatasetService.list(),
  });
}

export function useLoadDemoDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => demoDatasetService.load(name),
    onSuccess: () => {
      // After load, invalidate the ontology queries so the hierarchy tree refreshes
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.taxonomies });
      queryClient.invalidateQueries({ queryKey: ["schemes"] });
      queryClient.invalidateQueries({ queryKey: ["classes"] });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.properties });
    },
  });
}
