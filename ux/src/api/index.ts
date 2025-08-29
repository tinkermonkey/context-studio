/**
 * API Client Main Export
 * 
 * Main entry point for the Context Studio API client
 */

// Services
export * from './services/base';
export * from './services/layers';
export * from './services/domains';
export * from './services/terms';
export * from './services/relationships';
export * from './services/predicates';
export * from './services/graph';
export * from './services/datasets';
export * from './services/schema';
export * from './services/nlp';

// Hooks
export * from './hooks/layers';
export * from './hooks/domains';
export * from './hooks/terms';
export * from './hooks/relationships';
export * from './hooks/predicates';
export * from './hooks/graph';
export * from './hooks/datasets';
export * from './hooks/schema';
export * from './hooks/nlp';

// Client configuration
export * from './config';
export * from './client/axios';

// Error handling
export * from './errors/ApiError';
export * from './errors/errorHandlers';

// Provider
export * from './ApiProvider';

// Types
export type { components } from './client/types';
