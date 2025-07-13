/**
 * Test Utilities
 * 
 * Shared utilities for testing the API client
 */

import React from 'react';
import { render, RenderOptions } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';
import { apiClient } from '../../api/client/axios';

// Create a mock adapter for axios
export const mockAxios = new MockAdapter(apiClient);

// Create a test query client with no retries and short cache times
export const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      gcTime: 0,
      staleTime: 0,
    },
    mutations: {
      retry: false,
    },
  },
});

// Custom render function that includes QueryClientProvider
interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  queryClient?: QueryClient;
}

export const renderWithQueryClient = (
  ui: React.ReactElement,
  options: CustomRenderOptions = {}
) => {
  const { queryClient = createTestQueryClient(), ...renderOptions } = options;

  const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );

  return {
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
    queryClient,
  };
};

// Hook testing wrapper
export const createQueryWrapper = (queryClient?: QueryClient) => {
  const client = queryClient || createTestQueryClient();
  
  const QueryWrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>
      {children}
    </QueryClientProvider>
  );
  
  QueryWrapper.displayName = 'QueryWrapper';
  return QueryWrapper;
};

// Mock data generators
export const mockLayerData = {
  id: '123e4567-e89b-12d3-a456-426614174000',
  title: 'Test Layer',
  definition: 'A test layer definition',
  primary_predicate: 'test',
  created_at: '2024-01-01T00:00:00Z',
  version: 1,
  last_modified: '2024-01-01T00:00:00Z',
  title_embedding: null,
  definition_embedding: null,
};

export const mockDomainData = {
  id: '123e4567-e89b-12d3-a456-426614174001',
  title: 'Test Domain',
  definition: 'A test domain definition',
  layer_id: '123e4567-e89b-12d3-a456-426614174000',
  created_at: '2024-01-01T00:00:00Z',
  version: 1,
  last_modified: '2024-01-01T00:00:00Z',
  title_embedding: null,
  definition_embedding: null,
};

export const mockTermData = {
  id: '123e4567-e89b-12d3-a456-426614174002',
  title: 'Test Term',
  definition: 'A test term definition',
  domain_id: '123e4567-e89b-12d3-a456-426614174001',
  layer_id: '123e4567-e89b-12d3-a456-426614174000',
  parent_term_id: null,
  created_at: '2024-01-01T00:00:00Z',
  version: 1,
  last_modified: '2024-01-01T00:00:00Z',
  title_embedding: null,
  definition_embedding: null,
};

export const mockFindLayerResult = {
  ...mockLayerData,
  score: 0.95,
  distance: 0.05,
};

// Common test patterns
export const waitForQueryToSettle = async (queryClient: QueryClient) => {
  await queryClient.getQueryCache().findAll().forEach(query => {
    query.setData(query.state.data);
  });
};

// Error response helpers
export const mockValidationError = {
  detail: [
    {
      type: 'string_too_short',
      loc: ['body', 'title'],
      msg: 'String should have at least 2 characters',
      input: 'a',
      ctx: { min_length: 2 },
    },
  ],
};

export const mockNotFoundError = {
  detail: 'Layer not found',
};

// Reset mocks between tests
export const resetMocks = () => {
  mockAxios.reset();
};
