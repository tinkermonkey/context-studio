import { BaseService } from "./base";
import type { components } from "@/api/types";

type KnowledgeGraphResponse = components["schemas"]["KnowledgeGraphResponse"];
type GraphMetricsResponse = components["schemas"]["GraphMetricsResponse"];
type PathResultResponse = components["schemas"]["PathResultResponse"];
type SPARQLRequest = components["schemas"]["SPARQLRequest"];
type SPARQLResponse = components["schemas"]["SPARQLResponse"];

class GraphService extends BaseService {
  async buildGraph(): Promise<KnowledgeGraphResponse> {
    return this.post<KnowledgeGraphResponse>("/api/graph/build");
  }

  async getMetrics(algorithm?: string): Promise<GraphMetricsResponse> {
    return this.get<GraphMetricsResponse>(
      "/api/graph/metrics",
      algorithm ? { algorithm } : undefined,
    );
  }

  async getShortestPath(sourceId: string, targetId: string): Promise<PathResultResponse> {
    return this.get<PathResultResponse>("/api/graph/paths/shortest", {
      source_id: sourceId,
      target_id: targetId,
    });
  }

  async sparqlQuery(query: string): Promise<SPARQLResponse> {
    const body: SPARQLRequest = { query };
    return this.post<SPARQLResponse>("/api/graph/sparql", body);
  }
}

export const graphService = new GraphService();
