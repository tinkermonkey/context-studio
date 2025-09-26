/**
 * Types for Unified Reference API
 * Updated to match the latest backend API at /api/reference/search
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
  definition?: string | null;
  attributes?: Record<string, unknown>;
  source_url?: string | null;
  relevance_score: number;
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
  sources_queried: SourceType[];
  source_errors?: Record<string, string>;
  offset: number;
  limit: number;
  search_time_ms: number;
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

// Individual source endpoint response types (different from unified format)
export interface DBpediaSourceResult {
  uri: string;
  label: string;
  description?: string;
  score: number;
  types: string[];
}

export interface SchemaOrgSourceResult {
  type: string;
  identifier: string;
  title: string;
  definition?: string;
  relevance_score: number;
}

export interface ConceptNetEdge {
  "@id": string;
  start: {
    "@id": string;
    "@type": string;
    label: string;
    language: string;
    term: string;
  };
  rel: {
    "@id": string;
    "@type": string;
    label: string;
  };
  end: {
    "@id": string;
    "@type": string;
    label: string;
    language: string;
    term: string;
  };
  weight: number;
  sources: Array<any>;
}

export interface ConceptNetSourceResult {
  query_params: {
    node: string;
  };
  edges: ConceptNetEdge[];
}

export interface WikidataSourceResult {
  uri: string;
  label: string;
  description?: string;
  score: number;
  types: string[];
}

// Union type for all source result formats
export type IndividualSourceResult =
  | DBpediaSourceResult
  | SchemaOrgSourceResult
  | ConceptNetSourceResult
  | WikidataSourceResult;

export interface IndividualSourceResponse {
  success: boolean;
  source: string;
  retrieved_at?: string;
  error: string | null;
  query: string;
  search_type?: string;
  total_results: number;
  results: IndividualSourceResult[];
}
