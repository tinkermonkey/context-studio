/**
 * API Client Main Export
 * 
 * Main entry point for the Context Studio API client
 */

// Services
export * from './services/layers';
export * from './services/domains';
export * from './services/terms';
export * from './services/relationships';

// Hooks
export * from './hooks/layers';
export * from './hooks/domains';
export * from './hooks/terms';
export * from './hooks/relationships';

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
