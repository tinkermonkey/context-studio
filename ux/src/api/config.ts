/**
 * API Configuration
 *
 * Configuration settings for the Context Studio API client
 */

// Get the correct localhost URL based on platform and environment
const getDefaultBaseURL = () => {
  // Check for Vite environment variable first (for E2E tests and custom configs)
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  // Default to production port
  return "http://localhost:8100";
};

export const API_CONFIG = {
  baseURL: getDefaultBaseURL(),
  timeout: 30000,
  retryAttempts: 3,
  retryDelay: 1000,
  maxRetryDelay: 30000, // Maximum retry delay: 30 seconds
  staleTime: 5 * 60 * 1000, // 5 minutes
  cacheTime: 10 * 60 * 1000, // 10 minutes
  // Conflict resolution settings
  refetchOnConflict: true,
  conflictRetryDelay: 2000,
} as const;

export const QUERY_KEYS = {
  TAXONOMIES: "taxonomies",
  CONCEPT_SCHEMES: "concept_schemes",
  ONTOLOGY_CLASSES: "ontology_classes",
  INDIVIDUALS: "individuals",
  RELATIONSHIPS: "relationships",
  PROPERTY_DEFINITIONS: "property_definitions",
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
  CHANGE_EVENTS: "change_events",
  RAG: "rag",
  RAG_EXPERIMENTS: "rag_experiments",
} as const;

export const ENDPOINTS = {
  TAXONOMIES: "/api/taxonomies",
  CONCEPT_SCHEMES: "/api/schemes",
  ONTOLOGY_CLASSES: "/api/classes",
  INDIVIDUALS: "/api/individuals",
  RELATIONSHIPS: "/api/relationships",
  PROPERTY_DEFINITIONS: "/api/properties",
  GRAPH: "/api/graph",
  DATASETS: "/api/datasets",
  SCHEMA: "/api/schema",
  SCHEMA_ORG: "/api/schema-org",
  NLP: "/api/nlp_analysis",
  LLM: "/api/llm",
  LLM_TRACEABILITY: {
    RECORD_SELECTION: "/api/llm/record-selection",
    EXECUTION_ANALYTICS: "/api/llm/execution-analytics",
    EXECUTION_HISTORY: "/api/llm/execution-history",
    EXECUTION_DETAILS: "/api/llm/execution-details",
    FLAVOR_ANALYTICS: "/api/llm/flavor-analytics",
    HEALTH: "/api/v1/admin/health",
  },
  PIPELINE_FLAVORS: "/api/pipeline-flavors",
  NLP_REFERENCE: "/api/reference",
  REFERENCE: {
    BASE: "/api/reference/ref-db",
    FILTER_STATISTICS: "/api/reference/ref-db/filter/statistics",
    NODES: "/api/reference/ref-db/nodes",
  },
  CHANGE_EVENTS: "/api/v1/versioning/changes",
  RAG: {
    EXTRACT: "/api/rag/extract",
    METRICS: (requestId: string) => `/api/rag/metrics/${requestId}`,
    TRACE: (requestId: string) => `/api/rag/trace/${requestId}`,
    TRACE_BY_LAYER: (requestId: string, layerName: string) =>
      `/api/rag/trace/${requestId}/layer/${layerName}`,
    CONFIG_UPDATE: "/api/rag/config/update",
  },
  RAG_EXPERIMENTS: {
    PARAGRAPHS: "/api/rag-experiments/paragraphs",
    PARAGRAPH: (paragraphId: string) =>
      `/api/rag-experiments/paragraphs/${paragraphId}`,
    ANNOTATIONS: (paragraphId: string) =>
      `/api/rag-experiments/paragraphs/${paragraphId}/annotations`,
    DELETE_ANNOTATION: (annotationId: string) =>
      `/api/rag-experiments/annotations/${annotationId}`,
    RUN: "/api/rag-experiments/run",
    COMPARISON: (paragraphId: string) =>
      `/api/rag-experiments/results/paragraphs/${paragraphId}`,
    RUN_DETAILS: (runId: string) =>
      `/api/rag-experiments/results/runs/${runId}`,
  },
} as const;
