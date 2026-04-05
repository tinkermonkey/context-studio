/**
 * Missing Type Definitions
 *
 * This file provides type definitions for API schemas that are not yet
 * exposed in the back-end OpenAPI specification but are used by front-end services.
 *
 * These types should be temporary until the corresponding back-end endpoints
 * are implemented.
 */

// Dataset-related types
export interface DatasetResponse {
  id: string;
  name: string;
  description?: string | null;
  path?: string | null;
  created_at?: string;
  updated_at?: string;
}

export type CreateDatasetRequest = Record<string, unknown> & {
  name?: string;
  title?: string;
  filename?: string;
  description?: string | null;
};

export type AddExistingDatasetRequest = Record<string, unknown> & {
  path?: string;
  title?: string;
  file_path?: string;
  name?: string | null;
};

export interface UpdateDatasetDirectoryRequest {
  path?: string;
  datasets_directory?: string;
}

export interface ActionLogResponse {
  entries: ActionLogEntry[];
  timestamp: string;
}

export interface ActionLogEntry {
  timestamp: string;
  action: string;
  details?: Record<string, unknown>;
}

// Graph-related types
export interface SPARQLQuery {
  query: string;
}

export interface SearchRequest {
  query?: string;
  term?: string;
  limit?: number;
}

export interface CentralityRequest {
  algorithm?: string;
  node_ids?: string[];
}

export interface PathRequest {
  source?: string;
  source_id?: string;
  target?: string;
  target_id?: string;
}

export interface NeighborsRequest {
  node_id?: string;
  entity_id?: string;
  depth?: number;
}

// Pipeline-related types - allowing any property for compatibility
export type PipelineExecutionRequest = Record<string, unknown> & {
  pipeline_type?: string;
  flavor_id?: string;
  context_data?: Record<string, unknown>;
  pipeline_id?: string;
  input?: Record<string, unknown>;
  parameters?: Record<string, unknown>;
};

export type PipelineExecutionResponse = Record<string, unknown> & {
  execution_id?: string;
  pipeline_id?: string;
  status?: string;
  result?: Record<string, unknown>;
  error?: string | null;
  created_at?: string;
  completed_at?: string | null;
  response_content?: unknown;
  token_usage?: unknown;
};

export type PipelineFlavor = Record<string, unknown> & {
  id?: string;
  name?: string;
  type?: string;
  configuration?: Record<string, unknown>;
  created_at?: string;
  pipeline?: Record<string, unknown>;
};

export type CreatePipelineFlavorRequest = Record<string, unknown> & {
  name?: string;
  type?: string;
  configuration?: Record<string, unknown>;
  pipeline?: Record<string, unknown>;
};

export interface UpdatePipelineFlavorRequest {
  name?: string;
  configuration?: Record<string, unknown>;
}

export interface PipelineFlavorListResponse {
  flavors?: PipelineFlavor[];
  pipeline?: Record<string, unknown>;
  total?: number;
}

export type PipelineType = string; // Flexible type to accept various pipeline type values

// Predicate-related types
export interface PredicateOut {
  id: string;
  name: string;
  type: string;
}

export interface PredicateCreate {
  name: string;
  type: string;
}

export interface PredicateUpdate {
  name?: string;
  type?: string;
}

export type PaginatedPredicatesResponse = Record<string, unknown> & {
  items?: PredicateOut[];
  data?: PredicateOut[];
  total?: number;
  page?: number;
  page_size?: number;
};

export interface ExternalPredicateOut {
  id: string;
  name: string;
  source: string;
  uri?: string;
}

export interface PaginatedExternalPredicatesResponse {
  items: ExternalPredicateOut[];
  total: number;
  page: number;
  page_size: number;
}

// Model capabilities types
export interface ModelCapabilitiesResponse {
  models: Record<string, unknown>;
  capabilities: Record<string, unknown>;
}

export interface SupportedModelsResponse {
  models: string[];
  default_model: string;
}

// NLP Reference types
export interface ResponseFormat {
  format_type: string;
  schema?: Record<string, unknown>;
}

export interface MultiSourceSearchResponse {
  results: Record<string, unknown>[];
  total_count: number;
  sources: string[];
}

export type DBpediaSparqlRequest = Record<string, unknown> & {
  sparql_query?: string;
  query?: string;
};

export type WikidataSparqlRequest = Record<string, unknown> & {
  sparql_query?: string;
  query?: string;
};

// RAG Experiment types
export interface TestParagraphResponse {
  id: string;
  text: string;
  created_at: string;
}

export interface CreateTestParagraphRequest {
  text: string;
}

export interface UpdateTestParagraphRequest {
  text: string;
}

export interface TestParagraphListResponse {
  paragraphs: TestParagraphResponse[];
  total: number;
}
