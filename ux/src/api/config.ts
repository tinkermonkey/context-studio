/**
 * API Configuration
 *
 * Configuration settings for the Context Studio API client
 */

// Get the correct localhost URL based on platform
const getDefaultBaseURL = () => {
  return "http://localhost:8001";
};

export const API_CONFIG = {
  baseURL: getDefaultBaseURL(),
  timeout: 30000,
  retryAttempts: 3,
  retryDelay: 1000,
  staleTime: 5 * 60 * 1000, // 5 minutes
  cacheTime: 10 * 60 * 1000, // 10 minutes
} as const;

export const QUERY_KEYS = {
  LAYERS: "layers",
  DOMAINS: "domains",
  TERMS: "terms",
  RELATIONSHIPS: "relationships",
  PREDICATES: "predicates",
  GRAPH: "graph",
  FIND: "find",
  DATASETS: "datasets",
  SCHEMA: "schema",
  SCHEMA_ORG: "schema-org",
  NLP: "nlp",
  LLM: "llm",
  LLM_TRACEABILITY: "llm_traceability",
  PIPELINE_FLAVORS: "pipeline-flavors",
  NLP_REFERENCE: "nlp-reference",
  REFERENCE: "reference",
  STRUCTURE_NODES: "structure_nodes",
  NODE_LINKS: "node_links",
  CHANGE_EVENTS: "change_events",
} as const;

export const ENDPOINTS = {
  PREDICATES: "/api/predicates",
  GRAPH: "/api/graph",
  DATASETS: "/api/datasets",
  SCHEMA: "/api/schema",
  SCHEMA_ORG: "/api/schema-org",
  NLP: "/api/nlp_analysis",
  LLM: "/api/llm",
  LLM_TRACEABILITY: {
    RECORD_SELECTION: "/api/llm/record-selection",
    EXECUTION_ANALYTICS: "/api/llm/execution-analytics",
    EXECUTION_HISTORY: "/api/llm/execution-history", // New: gets history by flavor_id query param
    EXECUTION_DETAILS: "/api/llm/execution-details", // Renamed from execution-history/{id}
    FLAVOR_ANALYTICS: "/api/llm/flavor-analytics", // New: flavor-specific analytics
    HEALTH: "/api/llm/health",
  },
  PIPELINE_FLAVORS: "/api/pipeline-flavors",
  NLP_REFERENCE: "/api/reference",
  STRUCTURE_NODES: "/api/structure_nodes",
  NODE_LINKS: "/api/structure_nodes/links",
  CHANGE_EVENTS: "/api/change_events",
} as const;
