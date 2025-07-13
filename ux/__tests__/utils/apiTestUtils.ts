/**
 * API Test Utilities
 * 
 * Test utilities specifically for API client testing without React Native dependencies
 */

import { QueryClient } from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';
import { apiClient } from '../../api/client/axios';
import type { components } from '../../api/client/types';

// Mock Axios instance
export const mockAxios = new MockAdapter(apiClient);

// Mock data
export const mockLayerData: components['schemas']['LayerOut'] = {
  id: '1',
  title: 'Test Layer',
  definition: 'Test definition',
  primary_predicate: 'test_predicate',
  created_at: new Date().toISOString(),
  last_modified: new Date().toISOString(),
};

export const mockDomainData: components['schemas']['DomainOut'] = {
  id: '1',
  title: 'Test Domain',
  definition: 'Test domain description',
  layer_id: '1',
  created_at: new Date().toISOString(),
  last_modified: new Date().toISOString(),
};

export const mockTermData: components['schemas']['TermOut'] = {
  id: '1',
  title: 'Test Term',
  definition: 'Test term definition',
  domain_id: '1',
  layer_id: '1',
  created_at: new Date().toISOString(),
  version: 1,
  last_modified: new Date().toISOString(),
};

export const mockRelationshipData: components['schemas']['TermRelationshipOut'] = {
  id: '1',
  source_term_id: '1',
  target_term_id: '2',
  predicate: 'test_predicate',
  created_at: new Date().toISOString(),
};

export const mockFindLayerResult = {
  found: true,
  data: mockLayerData,
  message: 'Layer found',
};

export const mockValidationError = {
  detail: [
    {
      loc: ['body', 'title'],
      msg: 'field required',
      type: 'value_error.missing',
    },
  ],
};

export const mockServerError = {
  detail: 'Internal server error',
};

// Test query client
export const createTestQueryClient = () => {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
};

// Reset mocks
export const resetMocks = () => {
  mockAxios.reset();
  jest.clearAllMocks();
};
