/**
 * API Configuration
 * 
 * Configuration settings for the Context Studio API client
 */

// Get the correct localhost URL based on platform
const getDefaultBaseURL = () => {
  return 'http://127.0.0.1:8000';
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
  FIND: 'find',
} as const;

export const ENDPOINTS = {
  LAYERS: '/api/layers',
  DOMAINS: '/api/domains',
  TERMS: '/api/terms',
  RELATIONSHIPS: '/api/term-relationships',
} as const;
