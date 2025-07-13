/**
 * Terms Hooks Tests
 * 
 * Tests for terms query and mutation hooks
 */

import { renderHook, waitFor } from '@testing-library/react-native';
import { act } from 'react';
import { createTestQueryClient, createQueryWrapper, mockAxios } from '../utils/testUtils';
import {
  useTerms,
  useTerm,
  useTermsSearch,
  useCreateTerm,
  useUpdateTerm,
  useDeleteTerm,
  termsQueryKeys,
} from '../../api/hooks/terms';
import type { components } from '../../api/client/types';

// Mock data
const mockTerm: components['schemas']['TermOut'] = {
  id: '1',
  title: 'Test Term',
  definition: 'Test term definition',
  domain_id: 'domain1',
  layer_id: 'layer1',
  created_at: '2023-01-01T00:00:00Z',
  version: 1,
  last_modified: '2023-01-01T00:00:00Z',
};

const mockTermsList: components['schemas']['TermOut'][] = [
  mockTerm,
  {
    id: '2',
    title: 'Another Term',
    definition: 'Another test term definition',
    domain_id: 'domain1',
    layer_id: 'layer1',
    created_at: '2023-01-02T00:00:00Z',
    version: 1,
    last_modified: '2023-01-02T00:00:00Z',
  },
];

const mockCreateTerm: components['schemas']['TermCreate'] = {
  title: 'New Term',
  definition: 'New term definition',
  domain_id: 'domain1',
  layer_id: 'layer1',
};

const mockUpdateTerm: components['schemas']['TermUpdate'] = {
  title: 'Updated Term',
  definition: 'Updated term definition',
};

const mockSearchResults: components['schemas']['FindTermResult'][] = [
  {
    id: '1',
    title: 'Test Term',
    definition: 'Test term definition',
    domain_id: 'domain1',
    layer_id: 'layer1',
    created_at: '2023-01-01T00:00:00Z',
    version: 1,
    last_modified: '2023-01-01T00:00:00Z',
    distance: 0.05,
    score: 0.95,
  },
];

describe('Terms Hooks', () => {
  let queryClient: ReturnType<typeof createTestQueryClient>;
  let QueryWrapper: ReturnType<typeof createQueryWrapper>;

  beforeEach(() => {
    queryClient = createTestQueryClient();
    QueryWrapper = createQueryWrapper(queryClient);
    mockAxios.reset();
  });

  describe('useTerms', () => {
    it('should fetch terms successfully', async () => {
      mockAxios.onGet('/api/terms/').reply(200, mockTermsList);

      const { result } = renderHook(() => useTerms(), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockTermsList);
      expect(mockAxios.history.get).toHaveLength(1);
      expect(mockAxios.history.get[0].url).toBe('/api/terms/');
    });

    it('should handle query parameters', async () => {
      const params = { domain_id: 'domain1', limit: 10 };
      mockAxios.onGet('/api/terms/').reply(200, mockTermsList);

      const { result } = renderHook(() => useTerms(params), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(mockAxios.history.get[0].params).toEqual(params);
    });

    it('should handle errors', async () => {
      const errorMessage = 'Failed to fetch terms';
      mockAxios.onGet('/api/terms/').reply(500, { detail: errorMessage });

      const { result } = renderHook(() => useTerms(), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error).toBeDefined();
    });
  });

  describe('useTerm', () => {
    it('should fetch a single term successfully', async () => {
      mockAxios.onGet('/api/terms/1').reply(200, mockTerm);

      const { result } = renderHook(() => useTerm('1'), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockTerm);
      expect(mockAxios.history.get).toHaveLength(1);
      expect(mockAxios.history.get[0].url).toBe('/api/terms/1');
    });

    it('should not fetch when disabled', async () => {
      const { result } = renderHook(() => useTerm('1', false), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isPending).toBe(true);
      });

      expect(mockAxios.history.get).toHaveLength(0);
    });

    it('should not fetch when ID is empty', async () => {
      const { result } = renderHook(() => useTerm(''), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isPending).toBe(true);
      });

      expect(mockAxios.history.get).toHaveLength(0);
    });
  });

  describe('useTermsSearch', () => {
    it('should search terms successfully', async () => {
      mockAxios.onPost('/api/terms/find').reply(200, mockSearchResults);

      const { result } = renderHook(() => useTermsSearch('test query'), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockSearchResults);
      expect(mockAxios.history.post).toHaveLength(1);
      expect(mockAxios.history.post[0].url).toBe('/api/terms/find');
      expect(JSON.parse(mockAxios.history.post[0].data)).toEqual({
        query: 'test query',
      });
    });

    it('should not search when query is empty', async () => {
      const { result } = renderHook(() => useTermsSearch(''), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isPending).toBe(true);
      });

      expect(mockAxios.history.post).toHaveLength(0);
    });

    it('should not search when disabled', async () => {
      const { result } = renderHook(() => useTermsSearch('test query', false), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isPending).toBe(true);
      });

      expect(mockAxios.history.post).toHaveLength(0);
    });
  });

  describe('useCreateTerm', () => {
    it('should create a term successfully', async () => {
      mockAxios.onPost('/api/terms/').reply(201, mockTerm);

      const { result } = renderHook(() => useCreateTerm(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await result.current.mutateAsync(mockCreateTerm);
      });

      expect(result.current.isSuccess).toBe(true);
      expect(result.current.data).toEqual(mockTerm);
      expect(mockAxios.history.post).toHaveLength(1);
      expect(mockAxios.history.post[0].url).toBe('/api/terms/');
      expect(JSON.parse(mockAxios.history.post[0].data)).toEqual(mockCreateTerm);
    });

    it('should invalidate related queries on success', async () => {
      mockAxios.onPost('/api/terms/').reply(201, mockTerm);

      const invalidateQueriesSpy = jest.spyOn(queryClient, 'invalidateQueries');
      const setQueryDataSpy = jest.spyOn(queryClient, 'setQueryData');

      const { result } = renderHook(() => useCreateTerm(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await result.current.mutateAsync(mockCreateTerm);
      });

      expect(setQueryDataSpy).toHaveBeenCalledWith(
        termsQueryKeys.detail(mockTerm.id),
        mockTerm
      );
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: termsQueryKeys.lists(),
      });
    });

    it('should handle creation errors', async () => {
      const errorMessage = 'Failed to create term';
      mockAxios.onPost('/api/terms/').reply(400, { detail: errorMessage });

      const { result } = renderHook(() => useCreateTerm(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        try {
          await result.current.mutateAsync(mockCreateTerm);
        } catch {
          // Expected to throw
        }
      });

      expect(result.current.isError).toBe(true);
      expect(result.current.error).toBeDefined();
    });
  });

  describe('useUpdateTerm', () => {
    it('should update a term successfully', async () => {
      const updatedTerm = { ...mockTerm, ...mockUpdateTerm };
      mockAxios.onPut('/api/terms/1').reply(200, updatedTerm);

      const { result } = renderHook(() => useUpdateTerm(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await result.current.mutateAsync({ id: '1', data: mockUpdateTerm });
      });

      expect(result.current.isSuccess).toBe(true);
      expect(result.current.data).toEqual(updatedTerm);
      expect(mockAxios.history.put).toHaveLength(1);
      expect(mockAxios.history.put[0].url).toBe('/api/terms/1');
      expect(JSON.parse(mockAxios.history.put[0].data)).toEqual(mockUpdateTerm);
    });

    it('should update cache on success', async () => {
      const updatedTerm = { ...mockTerm, ...mockUpdateTerm };
      mockAxios.onPut('/api/terms/1').reply(200, updatedTerm);

      const setQueryDataSpy = jest.spyOn(queryClient, 'setQueryData');

      const { result } = renderHook(() => useUpdateTerm(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await result.current.mutateAsync({ id: '1', data: mockUpdateTerm });
      });

      expect(setQueryDataSpy).toHaveBeenCalledWith(
        termsQueryKeys.detail('1'),
        updatedTerm
      );
    });
  });

  describe('useDeleteTerm', () => {
    it('should delete a term successfully', async () => {
      mockAxios.onDelete('/api/terms/1').reply(204);

      const { result } = renderHook(() => useDeleteTerm(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await result.current.mutateAsync('1');
      });

      expect(result.current.isSuccess).toBe(true);
      expect(mockAxios.history.delete).toHaveLength(1);
      expect(mockAxios.history.delete[0].url).toBe('/api/terms/1');
    });

    it('should remove from cache on success', async () => {
      mockAxios.onDelete('/api/terms/1').reply(204);

      const removeQueriesSpy = jest.spyOn(queryClient, 'removeQueries');

      const { result } = renderHook(() => useDeleteTerm(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await result.current.mutateAsync('1');
      });

      expect(removeQueriesSpy).toHaveBeenCalledWith({
        queryKey: termsQueryKeys.detail('1'),
      });
    });
  });
});
