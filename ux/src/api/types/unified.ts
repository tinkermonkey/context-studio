/**
 * Types for Unified Reference API
 * These types are based on the PRP specification and will be updated
 * when the backend implementation is available
 */

export interface UnifiedSearchRequest {
  query: string;
  search_type: 'title' | 'definition';
  sources?: string[];
  limit?: number;
  offset?: number;
}

export interface UnifiedNode {
  id: string;
  title: string;
  definition?: string;
  source: string;
  source_url?: string;
  confidence_score: number;
  merged_from?: string[];
  created_at?: string;
  updated_at?: string;
  metadata?: Record<string, any>;
}

export interface UnifiedLink {
  id: string;
  source_node_id: string;
  target_node_id: string;
  predicate: string;
  source: string;
  confidence_score: number;
  metadata?: Record<string, any>;
}

export interface UnifiedSearchResponse {
  query: string;
  results: UnifiedNode[];
  total_results: number;
  search_type: 'title' | 'definition';
  sources: string[];
  source_errors?: Record<string, string>;
  execution_time_ms?: number;
}

export interface SourceStatus {
  name: string;
  available: boolean;
  last_check?: string;
  error_message?: string;
  response_time_ms?: number;
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
export const SOURCE_METADATA: Record<string, SourceMetadata> = {
  conceptnet: {
    label: 'ConceptNet',
    color: 'blue',
    description: 'Common sense knowledge graph',
    url: 'https://conceptnet.io/'
  },
  wordnet: {
    label: 'WordNet',
    color: 'green',
    description: 'Lexical database of English',
    url: 'https://wordnet.princeton.edu/'
  },
  dbpedia: {
    label: 'DBpedia',
    color: 'orange',
    description: 'Structured content from Wikipedia',
    url: 'https://dbpedia.org/'
  },
  wikidata: {
    label: 'Wikidata',
    color: 'purple',
    description: 'Free and open knowledge base',
    url: 'https://www.wikidata.org/'
  },
  schema_org: {
    label: 'Schema.org',
    color: 'red',
    description: 'Structured data schemas',
    url: 'https://schema.org/'
  }
};

// Error types
export class UnifiedReferenceError extends Error {
  constructor(
    message: string,
    public source?: string,
    public originalError?: Error
  ) {
    super(message);
    this.name = 'UnifiedReferenceError';
  }
}

export class SourceUnavailableError extends UnifiedReferenceError {
  constructor(source: string, originalError?: Error) {
    super(`Source ${source} is currently unavailable`, source, originalError);
    this.name = 'SourceUnavailableError';
  }
}

export class SearchTimeoutError extends UnifiedReferenceError {
  constructor(timeoutMs: number) {
    super(`Search timed out after ${timeoutMs}ms`);
    this.name = 'SearchTimeoutError';
  }
}