/**
 * Test fixtures for GraphService using OpenAPI-generated types.
 */

import type { components } from "@/api/types";

export function createKnowledgeGraph(
  overrides?: Partial<components["schemas"]["KnowledgeGraphResponse"]>
): components["schemas"]["KnowledgeGraphResponse"] {
  return {
    nodes_count: 100,
    edges_count: 250,
    build_time_ms: 1500,
    ...overrides,
  };
}

export function createGraphMetrics(
  overrides?: Partial<components["schemas"]["GraphMetricsResponse"]>
): components["schemas"]["GraphMetricsResponse"] {
  return {
    algorithm: "pagerank",
    density: 0.25,
    clustering_coefficient: 0.45,
    average_degree: 5.0,
    diameter: 8,
    ...overrides,
  };
}

export function createPathResult(
  overrides?: Partial<components["schemas"]["PathResultResponse"]>
): components["schemas"]["PathResultResponse"] {
  return {
    source_id: "node-1",
    target_id: "node-5",
    path: ["node-1", "node-2", "node-3", "node-5"],
    distance: 3,
    ...overrides,
  };
}

export function createSPARQLRequest(
  overrides?: Partial<components["schemas"]["SPARQLRequest"]>
): components["schemas"]["SPARQLRequest"] {
  return {
    query: "SELECT ?x WHERE { ?x rdf:type owl:Thing }",
    ...overrides,
  };
}

export function createSPARQLResponse(
  overrides?: Partial<components["schemas"]["SPARQLResponse"]>
): components["schemas"]["SPARQLResponse"] {
  return {
    results: [{ x: "node-1" }, { x: "node-2" }],
    execution_time_ms: 250,
    ...overrides,
  };
}
