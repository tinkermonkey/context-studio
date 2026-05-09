import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { graphService } from "@/api/services/graph";

export function useBuildGraph() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => graphService.buildGraph(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.graph });
    },
  });
}

export function useGraphMetrics(algorithm?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.graphMetrics,
    queryFn: () => graphService.getMetrics(algorithm),
  });
}

export function useShortestPath(sourceId: string, targetId: string) {
  return useQuery({
    queryKey: ["graph", "path", sourceId, targetId],
    queryFn: () => graphService.getShortestPath(sourceId, targetId),
    enabled: !!sourceId && !!targetId,
  });
}

export function useSparqlQuery() {
  return useMutation({
    mutationFn: (query: string) => graphService.sparqlQuery(query),
  });
}
