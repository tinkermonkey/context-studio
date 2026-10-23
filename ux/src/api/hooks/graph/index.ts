import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { graphService } from "@/api/services/graph";
import type { components } from "@/api/types";

export type GraphView = components["schemas"]["GraphViewResponse"];
export type GraphViewNode = components["schemas"]["GraphViewNodeResponse"];
export type GraphViewEdge = components["schemas"]["GraphViewEdgeResponse"];
export type GraphViewLayer = components["schemas"]["GraphViewLayerResponse"];
export type GraphViewTaxonomy = components["schemas"]["GraphViewTaxonomyResponse"];

/** The graph view only changes when the ontology changes; filter changes must not refetch it. */
const GRAPH_VIEW_STALE_TIME_MS = 5 * 60 * 1000;

export function useBuildGraph() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => graphService.buildGraph(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.graph });
    },
  });
}

export function useGraphView() {
  return useQuery({
    queryKey: QUERY_KEYS.graphView,
    queryFn: () => graphService.getGraphView(),
    staleTime: GRAPH_VIEW_STALE_TIME_MS,
  });
}

export function useGraphMetrics(algorithm?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.graphMetrics,
    queryFn: () => graphService.getMetrics(algorithm),
  });
}

export function useShortestPath() {
  return useMutation({
    mutationFn: (args: { sourceId: string; targetId: string }) =>
      graphService.getShortestPath(args.sourceId, args.targetId),
  });
}

export function useSparqlQuery() {
  return useMutation({
    mutationFn: (query: string) => graphService.sparqlQuery(query),
  });
}
