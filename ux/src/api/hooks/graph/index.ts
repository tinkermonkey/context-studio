import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { graphService } from "@/api/services/graph";

export interface GraphNode {
  id: string;
  label: string;
  centrality: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
}

export interface GraphVisualizationData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata: {
    nodeCount: number;
    edgeCount: number;
    timestamp: string;
  };
}

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

export function useGraphVisualization() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (): Promise<GraphVisualizationData> => {
      try {
        await graphService.buildGraph();
      } catch (error) {
        throw new Error(
          `Failed to build graph: ${error instanceof Error ? error.message : String(error)}`,
          { cause: error }
        );
      }

      let metrics;
      try {
        metrics = await graphService.getMetrics();
      } catch (error) {
        throw new Error(
          `Failed to compute metrics: ${error instanceof Error ? error.message : String(error)}`,
          { cause: error }
        );
      }

      const nodeIds = Object.keys(metrics.centrality);

      if (nodeIds.length === 0) {
        return {
          nodes: [],
          edges: [],
          metadata: {
            nodeCount: 0,
            edgeCount: 0,
            timestamp: new Date().toISOString(),
          },
        };
      }

      let subgraph;
      try {
        subgraph = await graphService.getSubgraph(nodeIds);
      } catch (error) {
        throw new Error(
          `Failed to fetch subgraph: ${error instanceof Error ? error.message : String(error)}`,
          { cause: error }
        );
      }

      return {
        nodes: nodeIds.map((id) => ({
          id,
          label: id,
          centrality: metrics.centrality[id],
        })),
        edges: subgraph.edges.map(([source, target]) => ({
          id: `${source}-${target}`,
          source,
          target,
        })),
        metadata: {
          nodeCount: subgraph.node_count,
          edgeCount: subgraph.edge_count,
          timestamp: metrics.computed_at,
        },
      };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.graph });
    },
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
