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

/** Rebuild the graph: the schema plus `datasetId`'s data, or all data. */
export function useBuildGraph(datasetId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => graphService.buildGraph(datasetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.graph });
    },
  });
}

/** The graph view: the schema plus `datasetId`'s data, or all data (cached per dataset). */
export function useGraphView(datasetId?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.graphView(datasetId),
    queryFn: () => graphService.getGraphView(datasetId),
    staleTime: GRAPH_VIEW_STALE_TIME_MS,
  });
}

export function useGraphMetrics(algorithm?: string, datasetId?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.graphMetrics(datasetId),
    queryFn: () => graphService.getMetrics(algorithm, datasetId),
  });
}

export function useShortestPath(datasetId?: string) {
  return useMutation({
    mutationFn: (args: { sourceId: string; targetId: string }) =>
      graphService.getShortestPath(args.sourceId, args.targetId, datasetId),
  });
}

/** Run a SPARQL query over the schema plus `datasetId`'s data, or all data. */
export function useSparqlQuery(datasetId?: string) {
  return useMutation({
    mutationFn: (query: string) => graphService.sparqlQuery(query, datasetId),
  });
}
