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
  title?: string;
  filename?: string;
  description?: string | null;
  path?: string | null;
  created_at?: string;
  updated_at?: string;
  last_accessed?: string;
  schema_version?: string;
  is_active?: boolean;
  metrics: {
    layers_count?: number;
    terms_count?: number;
    relationships_count?: number;
    domains_count?: number;
  };
}

export interface CreateDatasetRequest {
  name?: string;
  title?: string;
  filename?: string;
  description?: string | null;
}

export interface AddExistingDatasetRequest {
  path?: string;
  title?: string;
  file_path?: string;
  name?: string | null;
}

export interface UpdateDatasetDirectoryRequest {
  path?: string;
  datasets_directory?: string;
}

export interface ActionLogResponse {
  entries: ActionLogEntry[];
  timestamp?: string;
  total_count?: number;
}

export interface ActionLogEntry {
  timestamp: string;
  action: string;
  dataset_id?: string;
  dataset_title?: string;
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

// Pipeline-related types
export interface PipelineExecutionRequest {
  pipeline_type?: string;
  flavor_id?: string;
  context_data?: Record<string, unknown>;
  pipeline_id?: string;
  input?: Record<string, unknown>;
  parameters?: Record<string, unknown>;
}

export interface PipelineExecutionResponse {
  execution_id?: string;
  pipeline_id?: string;
  status?: string;
  result?: Record<string, unknown>;
  error?: string | null;
  created_at?: string;
  completed_at?: string | null;
  response_content?: unknown;
  token_usage?: unknown;
}

export interface LlmConfigType {
  temperature: number;
  max_tokens: number;
  top_p: number;
  top_k?: number;
  frequency_penalty: number;
  presence_penalty: number;
  [key: string]: unknown;
}

export interface PipelineFlavor {
  id: string;
  name?: string;
  title: string;
  type?: string;
  configuration?: Record<string, unknown>;
  created_at?: string;
  pipeline: string;
  llm_config: LlmConfigType;
  llm_provider: string;
  llm_model: string;
  system_prompt: string;
  user_prompt: string;
  enabled: boolean;
  version?: number;
}

export interface CreatePipelineFlavorRequest {
  name?: string;
  title: string;
  type?: string;
  configuration?: Record<string, unknown>;
  pipeline: string;
  llm_config: LlmConfigType;
  llm_provider: string;
  llm_model: string;
  system_prompt: string;
  user_prompt: string;
  enabled: boolean;
}

export interface UpdatePipelineFlavorRequest {
  name?: string;
  title?: string;
  configuration?: Record<string, unknown>;
  llm_config?: LlmConfigType;
  llm_provider?: string;
  llm_model?: string;
  system_prompt?: string;
  user_prompt?: string;
  enabled?: boolean;
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
  title: string;
  type: string;
  identifier?: string;
  definition: string;
  date_created?: string;
  date_modified?: string;
}

export interface PredicateCreate {
  name: string;
  type: string;
  title?: string;
  identifier?: string;
  definition: string;
}

export interface PredicateUpdate {
  name?: string;
  type?: string;
  title?: string;
  identifier?: string;
  definition?: string;
}

export interface PaginatedPredicatesResponse {
  items?: PredicateOut[];
  data: PredicateOut[];
  total?: number;
  page?: number;
  page_size?: number;
}

export interface ExternalPredicateOut {
  id: string;
  predicate_id?: string;
  source_id?: string;
  name: string;
  title: string;
  source: string;
  uri?: string;
  external_id: string;
  definition: string;
  similarity_score: number;
}

export interface PaginatedExternalPredicatesResponse {
  items?: ExternalPredicateOut[];
  data: ExternalPredicateOut[];
  total?: number;
  page?: number;
  page_size?: number;
}

// Node-related types
export interface NodeOut {
  id: string;
  name?: string;
  [key: string]: unknown;
}

export interface NodeLinkOut {
  id: string;
  source_node_id?: string;
  target_node_id?: string;
  relationship_type?: string;
  [key: string]: unknown;
}

// Model capabilities types
export interface ModelCapabilitiesResponse {
  models?: Record<string, unknown> | ModelInfo[];
  capabilities?: Record<string, unknown>;
  name?: string;
  provider?: string;
  [key: string]: unknown;
}

export interface ModelInfo {
  name: string;
  provider: string;
  capabilities: Record<string, unknown>;
  [key: string]: unknown;
}

export interface SupportedModelsResponse {
  models: ModelInfo[];
  default_model?: string;
}

// NLP Reference types
export interface ResponseFormat {
  format_type: string;
  schema?: Record<string, unknown>;
}

// Clustering and search results
export interface ClusterResult {
  clusters: Record<string, unknown>[];
  [key: string]: unknown;
}

export interface SimilarPredicateResult {
  id: string;
  name: string;
  source: string;
  similarity_score: number;
  [key: string]: unknown;
}

export interface SearchResultsResponse {
  results: SimilarPredicateResult[];
  total_count?: number;
  [key: string]: unknown;
}

export interface MultiSourceSearchResponse {
  results: Record<string, unknown>[];
  total_count: number;
  sources: string[];
}

export interface DBpediaSparqlRequest {
  sparql_query?: string;
  query?: string;
}

export interface WikidataSparqlRequest {
  sparql_query?: string;
  query?: string;
}

// RAG Experiment types
export interface Annotation {
  start_char: number;
  end_char: number;
  [key: string]: unknown;
}

export interface TestParagraphResponse {
  id: string;
  text: string;
  created_at: string;
  notes?: string;
  annotations: Annotation[];
}

export type CreateParagraphResponse = TestParagraphResponse;
export type UpdateParagraphResponse = TestParagraphResponse;
export type GetParagraphResponse = TestParagraphResponse;

export interface CreateTestParagraphRequest {
  text: string;
  notes?: string;
}

export interface UpdateTestParagraphRequest {
  text: string;
  notes?: string;
}

export interface TestParagraphListResponse {
  paragraphs?: TestParagraphResponse[];
  total?: number;
}

export interface PipelineComparisonItem {
  pipeline_name: string;
  precision_score?: number;
  recall_score?: number;
  f1_score?: number;
  execution_time_ms?: number;
  entities_extracted?: number;
  [key: string]: unknown;
}

export interface PipelineComparisonSummary {
  total_pipelines: number;
  best_pipeline: string;
  best_f1_score: number;
  [key: string]: unknown;
}

export interface PipelineComparisonResponse {
  runs: PipelineComparisonItem[];
  summary: PipelineComparisonSummary;
  [key: string]: unknown;
}

// Pipeline run types
export interface PipelineResult {
  flavorId: string;
  flavorTitle: string;
  status: "pending" | "running" | "success" | "error";
  data?: Record<string, unknown>;
  error?: string;
  startTime?: number;
  endTime?: number;
}
