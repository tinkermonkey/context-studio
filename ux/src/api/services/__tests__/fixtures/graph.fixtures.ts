/**
 * Test fixtures for GraphService using OpenAPI-generated types.
 */

import type { components } from "@/api/types";

export function createKnowledgeGraph(
  overrides?: Partial<components["schemas"]["KnowledgeGraphResponse"]>,
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
  overrides?: Partial<components["schemas"]["GraphMetricsResponse"]>,
): components["schemas"]["GraphMetricsResponse"] {
  return {
    algorithm: "pagerank",
    density: 0.25,
    average_degree: 5.0,
    connected_components: 1,
    degree_distribution: { "0": 10, "1": 20, "2": 15 },
    centrality: { "node-1": 0.85, "node-2": 0.75 },
    communities: [
      ["node-1", "node-2"],
      ["node-3", "node-4"],
    ],
    computed_at: new Date().toISOString(),
    ...overrides,
  };
}

export function createPathResult(
  overrides?: Partial<components["schemas"]["PathResultResponse"]>,
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
  overrides?: Partial<components["schemas"]["SPARQLRequest"]>,
): components["schemas"]["SPARQLRequest"] {
  return {
    query: "SELECT ?x WHERE { ?x rdf:type owl:Thing }",
    ...overrides,
  };
}

export function createSPARQLResponse(
  overrides?: Partial<components["schemas"]["SPARQLResponse"]>,
): components["schemas"]["SPARQLResponse"] {
  return {
    results: [{ x: "node-1" }, { x: "node-2" }],
    triple_count: 1000,
    ...overrides,
  };
}

export function createSubgraphData(
  overrides?: Partial<components["schemas"]["SubgraphDataResponse"]>,
): components["schemas"]["SubgraphDataResponse"] {
  return {
    nodes: ["node-1", "node-2", "node-3"],
    edges: [
      ["node-1", "node-2"],
      ["node-2", "node-3"],
    ],
    node_count: 3,
    edge_count: 2,
    ...overrides,
  };
}

/**
 * A two-taxonomy graph view: DR (`tax-dr`) with three layers and a
 * one-layer side taxonomy. `svc` (business) has a cross-layer schema edge to
 * `op` (api); `checkout` / `post-order` are individuals with a cross-layer
 * relationship; `goal` (motivation) is only linked within its layer.
 */
export function createGraphView(
  overrides?: Partial<components["schemas"]["GraphViewResponse"]>,
): components["schemas"]["GraphViewResponse"] {
  return {
    taxonomies: [
      { id: "tax-dr", title: "Documentation Robotics", identifier: "dr_spec" },
      { id: "tax-side", title: "Side Taxonomy", identifier: "side" },
    ],
    layers: [
      {
        id: "layer-motivation",
        title: "Motivation Layer",
        identifier: "motivation",
        taxonomy_id: "tax-dr",
      },
      {
        id: "layer-business",
        title: "Business Layer",
        identifier: "business",
        taxonomy_id: "tax-dr",
      },
      { id: "layer-api", title: "API Layer", identifier: "api", taxonomy_id: "tax-dr" },
      {
        id: "layer-side",
        title: "Side Scheme",
        identifier: "side_scheme",
        taxonomy_id: "tax-side",
      },
    ],
    nodes: [
      {
        id: "goal",
        label: "Goal",
        node_type: "class",
        identifier: "motivation_goal",
        description: "A desired outcome",
        concept_scheme_id: "layer-motivation",
        taxonomy_id: "tax-dr",
        class_ids: [],
      },
      {
        id: "outcome",
        label: "Outcome",
        node_type: "class",
        identifier: "motivation_outcome",
        description: null,
        concept_scheme_id: "layer-motivation",
        taxonomy_id: "tax-dr",
        class_ids: [],
      },
      {
        id: "svc",
        label: "Business Service",
        node_type: "class",
        identifier: "business_service",
        description: "A service offered",
        concept_scheme_id: "layer-business",
        taxonomy_id: "tax-dr",
        class_ids: [],
      },
      {
        id: "op",
        label: "Operation",
        node_type: "class",
        identifier: "api_operation",
        description: null,
        concept_scheme_id: "layer-api",
        taxonomy_id: "tax-dr",
        class_ids: [],
      },
      {
        id: "checkout",
        label: "Checkout",
        node_type: "individual",
        identifier: null,
        description: "Checkout service",
        concept_scheme_id: "layer-business",
        taxonomy_id: "tax-dr",
        class_ids: ["svc"],
      },
      {
        id: "post-order",
        label: "POST /orders",
        node_type: "individual",
        identifier: null,
        description: null,
        concept_scheme_id: "layer-api",
        taxonomy_id: "tax-dr",
        class_ids: ["op"],
      },
      {
        id: "side-class",
        label: "Side Class",
        node_type: "class",
        identifier: "side_class",
        description: null,
        concept_scheme_id: "layer-side",
        taxonomy_id: "tax-side",
        class_ids: [],
      },
    ],
    edges: [
      {
        id: "e-goal-outcome",
        source: "goal",
        target: "outcome",
        edge_type: "schema",
        predicate_id: "p1",
        predicate: "realized by",
      },
      {
        id: "e-svc-op",
        source: "svc",
        target: "op",
        edge_type: "schema",
        predicate_id: "p2",
        predicate: "business.service realized-by api.operation",
      },
      {
        id: "e-checkout-post",
        source: "checkout",
        target: "post-order",
        edge_type: "relationship",
        predicate_id: "p2",
        predicate: "realized by",
      },
      {
        id: "checkout:instance_of:svc",
        source: "checkout",
        target: "svc",
        edge_type: "instance_of",
        predicate_id: null,
        predicate: "instance of",
      },
      {
        id: "post-order:instance_of:op",
        source: "post-order",
        target: "op",
        edge_type: "instance_of",
        predicate_id: null,
        predicate: "instance of",
      },
    ],
    ...overrides,
  };
}
