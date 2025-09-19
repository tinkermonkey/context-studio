/**
 * Types for Unified Reference API
 * Updated to match the latest backend API at /api/nlp_analysis/reference/search
 */

export interface MultiSourceSearchRequest {
  query: string;
  sources?: SourceType[];
  limit?: number;
  offset?: number;
}

export interface SearchNode {
  id: string;
  source: SourceType;
  title: string;
  definition?: string;
  source_url?: string;
  confidence_score?: number;
  metadata?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
  merged_from?: string[];
}

export interface SearchLink {
  id: string;
  source: SourceType;
  subject: string;
  predicate: string;
  object: string;
  weight?: number | null;
  attributes?: Record<string, unknown>;
}

export interface MultiSourceSearchResponse {
  query: string;
  results: SearchNode[];
  links?: SearchLink[];
  total_results: number;
  total_links: number;
  sources_searched: SourceType[];
  source_errors?: Record<string, string>;
  execution_time_ms?: number;
}

export type SourceType = "dbpedia" | "conceptnet" | "wikidata" | "schema_org";

export interface SourceStatus {
  name: string;
  available: boolean;
  last_check?: string;
  error_message?: string;
  response_time_ms?: number;
}

// Legacy interfaces for backward compatibility
export interface UnifiedSearchRequest extends MultiSourceSearchRequest {}

export interface UnifiedNode extends SearchNode {}

export interface UnifiedSearchResponse extends MultiSourceSearchResponse {}

export interface UnifiedSearchLink extends SearchLink {}

export interface UnifiedLink {
  id: string;
  source_node_id: string;
  target_node_id: string;
  predicate: string;
  source: string;
  confidence_score: number;
  metadata?: Record<string, any>;
}

export interface DeduplicationInfo {
  merged_from: string[];
  similarity_score: number;
  merge_algorithm?: string;
}

// Source metadata for UI display
export interface SourceMetadata {
  label: string;
  color: string;
  description: string;
  url?: string;
}

// Predefined source metadata
export const SOURCE_METADATA: Record<SourceType, SourceMetadata> & Record<string, SourceMetadata> = {
  conceptnet: {
    label: "ConceptNet",
    color: "blue",
    description: "Common sense knowledge graph",
    url: "https://conceptnet.io/",
  },
  dbpedia: {
    label: "DBpedia",
    color: "orange",
    description: "Structured content from Wikipedia",
    url: "https://dbpedia.org/",
  },
  wikidata: {
    label: "Wikidata",
    color: "purple",
    description: "Free and open knowledge base",
    url: "https://www.wikidata.org/",
  },
  schema_org: {
    label: "Schema.org",
    color: "red",
    description: "Structured data schemas",
    url: "https://schema.org/",
  },
};

// Error types
export class UnifiedReferenceError extends Error {
  constructor(
    message: string,
    public source?: string,
    public originalError?: Error,
  ) {
    super(message);
    this.name = "UnifiedReferenceError";
  }
}

export class SourceUnavailableError extends UnifiedReferenceError {
  constructor(source: string, originalError?: Error) {
    super(`Source ${source} is currently unavailable`, source, originalError);
    this.name = "SourceUnavailableError";
  }
}

export class SearchTimeoutError extends UnifiedReferenceError {
  constructor(timeoutMs: number) {
    super(`Search timed out after ${timeoutMs}ms`);
    this.name = "SearchTimeoutError";
  }
}
