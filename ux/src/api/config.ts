/**
 * API Configuration
 * 
 * Configuration settings for the Context Studio API client
 */

// Get the correct localhost URL based on platform
const getDefaultBaseURL = () => {
  return 'http://localhost:8000';
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
  LAYERS: 'layers',
  DOMAINS: 'domains',
  TERMS: 'terms',
  RELATIONSHIPS: 'relationships',
  PREDICATES: 'predicates',
  GRAPH: 'graph',
  FIND: 'find',
  DATASETS: 'datasets',
  SCHEMA: 'schema',
  SCHEMA_ORG: 'schema-org',
  NLP: 'nlp',
  LLM: 'llm',
  PIPELINE_FLAVORS: 'pipeline-flavors',
  NLP_REFERENCE: 'nlp-reference',
} as const;

export const ENDPOINTS = {
  LAYERS: '/api/layers',
  DOMAINS: '/api/domains',
  TERMS: '/api/terms',
  RELATIONSHIPS: '/api/term-relationships',
  PREDICATES: '/api/predicates',
  GRAPH: '/api/graph',
  DATASETS: '/api/datasets',
  SCHEMA: '/api/schema',
  SCHEMA_ORG: '/api/schema-org',
  NLP: '/api/nlp_analysis',
  LLM: '/api/llm',
  PIPELINE_FLAVORS: '/api/pipeline-flavors',
  NLP_REFERENCE: '/api/nlp_analysis/reference',
} as const;
