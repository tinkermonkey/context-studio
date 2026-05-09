/**
 * Test fixtures for GraphService using OpenAPI-generated types.
 */

import type { components } from "@/api/types";

export function createKnowledgeGraph(
  overrides?: Partial<components["schemas"]["KnowledgeGraphResponse"]>
): components["schemas"]["KnowledgeGraphResponse"] {
  return {
    node_count: 100,
    edge_count: 250,
    is_directed: true,
    timestamp: new Date().toISOString(),
    ...overrides,
  };
}

export function createGraphMetrics(
  overrides?: Partial<components["schemas"]["GraphMetricsResponse"]>
): components["schemas"]["GraphMetricsResponse"] {
  return {
    algorithm: "pagerank",
    density: 0.25,
    average_degree: 5.0,
    connected_components: 1,
    degree_distribution: { "0": 10, "1": 20, "2": 15 },
    centrality: { "node-1": 0.85, "node-2": 0.75 },
    communities: [["node-1", "node-2"], ["node-3", "node-4"]],
    computed_at: new Date().toISOString(),
    ...overrides,
  };
}

export function createPathResult(
  overrides?: Partial<components["schemas"]["PathResultResponse"]>
): components["schemas"]["PathResultResponse"] {
  return {
    source_id: "node-1",
    target_id: "node-5",
    nodes: ["node-1", "node-2", "node-3", "node-5"],
    distance: 3,
    relationships: ["connects_to", "connects_to", "connects_to"],
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
    triple_count: 1000,
    ...overrides,
  };
}
