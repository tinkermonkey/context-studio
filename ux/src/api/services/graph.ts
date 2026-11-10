import { BaseService } from "./base";
import type { components } from "@/api/types";

type KnowledgeGraphResponse = components["schemas"]["KnowledgeGraphResponse"];
type GraphMetricsResponse = components["schemas"]["GraphMetricsResponse"];
type PathResultResponse = components["schemas"]["PathResultResponse"];
type SPARQLRequest = components["schemas"]["SPARQLRequest"];
type SPARQLResponse = components["schemas"]["SPARQLResponse"];
type SubgraphDataResponse = components["schemas"]["SubgraphDataResponse"];
type GraphViewResponse = components["schemas"]["GraphViewResponse"];

/**
 * Every graph call takes an optional dataset: the graph is then the schema plus
 * that dataset's data (all data when omitted).
 */
function datasetParams(datasetId?: string): Record<string, unknown> {
  return datasetId ? { dataset_id: datasetId } : {};
}

class GraphService extends BaseService {
  async buildGraph(datasetId?: string): Promise<KnowledgeGraphResponse> {
    return this.post<KnowledgeGraphResponse>(
      "/api/graph/build",
      undefined,
      datasetId ? datasetParams(datasetId) : undefined,
    );
  }

  async getGraphView(datasetId?: string): Promise<GraphViewResponse> {
    return this.get<GraphViewResponse>(
      "/api/graph/view",
      datasetId ? datasetParams(datasetId) : undefined,
    );
  }

  async getMetrics(algorithm?: string, datasetId?: string): Promise<GraphMetricsResponse> {
    const params = { ...(algorithm ? { algorithm } : {}), ...datasetParams(datasetId) };
    return this.get<GraphMetricsResponse>(
      "/api/graph/metrics",
      Object.keys(params).length ? params : undefined,
    );
  }

  async getSubgraph(nodeIds: string[], datasetId?: string): Promise<SubgraphDataResponse> {
    return this.get<SubgraphDataResponse>("/api/graph/subgraph", {
      nodes: nodeIds.join(","),
      ...datasetParams(datasetId),
    });
  }

  async getShortestPath(
    sourceId: string,
    targetId: string,
    datasetId?: string,
  ): Promise<PathResultResponse> {
    return this.get<PathResultResponse>("/api/graph/paths/shortest", {
      source_id: sourceId,
      target_id: targetId,
      ...datasetParams(datasetId),
    });
  }

  async sparqlQuery(query: string, datasetId?: string): Promise<SPARQLResponse> {
    const body: SPARQLRequest = datasetId ? { query, dataset_id: datasetId } : { query };
    return this.post<SPARQLResponse>("/api/graph/sparql", body);
  }
}

export const graphService = new GraphService();
