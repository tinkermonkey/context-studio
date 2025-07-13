/**
 * Relationships Hooks Tests
 * 
 * Tests for relationship query and mutation hooks
 */

import { renderHook, waitFor } from '@testing-library/react-native';
import { act } from 'react';
import { createTestQueryClient, createQueryWrapper, mockAxios } from '../utils/testUtils';
import {
  useRelationships,
  useRelationship,
  useTermRelationships,
  useRelationshipsByPredicate,
  useCreateRelationship,
  useUpdateRelationship,
  useDeleteRelationship,
  relationshipsQueryKeys,
} from '../../api/hooks/relationships';
import type { components } from '../../api/client/types';

// Mock data
const mockRelationship: components['schemas']['TermRelationshipOut'] = {
  id: '1',
  source_term_id: 'term1',
  target_term_id: 'term2',
  predicate: 'relates_to',
  created_at: '2023-01-01T00:00:00Z',
};

const mockRelationshipsList: components['schemas']['TermRelationshipOut'][] = [
  mockRelationship,
  {
    id: '2',
    source_term_id: 'term2',
    target_term_id: 'term3',
    predicate: 'is_part_of',
    created_at: '2023-01-02T00:00:00Z',
  },
];

const mockCreateRelationship: components['schemas']['TermRelationshipCreate'] = {
  source_term_id: 'term1',
  target_term_id: 'term2',
  predicate: 'relates_to',
};

const mockUpdateRelationship: components['schemas']['TermRelationshipUpdate'] = {
  predicate: 'updated_predicate',
};

describe('Relationships Hooks', () => {
  let queryClient: ReturnType<typeof createTestQueryClient>;
  let QueryWrapper: ReturnType<typeof createQueryWrapper>;

  beforeEach(() => {
    queryClient = createTestQueryClient();
    QueryWrapper = createQueryWrapper(queryClient);
    mockAxios.reset();
  });

  describe('useRelationships', () => {
    it('should fetch relationships successfully', async () => {
      mockAxios.onGet('/api/term-relationships/').reply(200, mockRelationshipsList);

      const { result } = renderHook(() => useRelationships(), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockRelationshipsList);
      expect(mockAxios.history.get).toHaveLength(1);
      expect(mockAxios.history.get[0].url).toBe('/api/term-relationships/');
    });

    it('should handle query parameters', async () => {
      const params = { source_term_id: 'term1', predicate: 'relates_to' };
      mockAxios.onGet('/api/term-relationships/').reply(200, mockRelationshipsList);

      const { result } = renderHook(() => useRelationships(params), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(mockAxios.history.get[0].params).toEqual(params);
    });

    it('should handle errors', async () => {
      const errorMessage = 'Failed to fetch relationships';
      mockAxios.onGet('/api/term-relationships/').reply(500, { detail: errorMessage });

      const { result } = renderHook(() => useRelationships(), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error).toBeDefined();
    });
  });

  describe('useRelationship', () => {
    it('should fetch a single relationship successfully', async () => {
      mockAxios.onGet('/api/term-relationships/1').reply(200, mockRelationship);

      const { result } = renderHook(() => useRelationship('1'), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockRelationship);
      expect(mockAxios.history.get).toHaveLength(1);
      expect(mockAxios.history.get[0].url).toBe('/api/term-relationships/1');
    });

    it('should not fetch when disabled', async () => {
      const { result } = renderHook(() => useRelationship('1', false), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isPending).toBe(true);
      });

      expect(mockAxios.history.get).toHaveLength(0);
    });

    it('should not fetch when ID is empty', async () => {
      const { result } = renderHook(() => useRelationship(''), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isPending).toBe(true);
      });

      expect(mockAxios.history.get).toHaveLength(0);
    });
  });

  describe('useTermRelationships', () => {
    it('should fetch relationships for a term successfully', async () => {
      const sourceRelationships = [mockRelationship];
      const targetRelationships = [mockRelationshipsList[1]];
      
      mockAxios.onGet('/api/term-relationships/').reply((config) => {
        if (config.params?.source_term_id === 'term1') {
          return [200, sourceRelationships];
        }
        if (config.params?.target_term_id === 'term1') {
          return [200, targetRelationships];
        }
        return [200, []];
      });

      const { result } = renderHook(() => useTermRelationships('term1'), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toHaveLength(2);
      expect(mockAxios.history.get).toHaveLength(2);
    });

    it('should deduplicate relationships', async () => {
      const duplicateRelationship = mockRelationship;
      
      mockAxios.onGet('/api/term-relationships/').reply((config) => {
        if (config.params?.source_term_id === 'term1') {
          return [200, [duplicateRelationship]];
        }
        if (config.params?.target_term_id === 'term1') {
          return [200, [duplicateRelationship]]; // Same relationship
        }
        return [200, []];
      });

      const { result } = renderHook(() => useTermRelationships('term1'), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toHaveLength(1); // Should be deduplicated
    });

    it('should not fetch when disabled', async () => {
      const { result } = renderHook(() => useTermRelationships('term1', false), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isPending).toBe(true);
      });

      expect(mockAxios.history.get).toHaveLength(0);
    });
  });

  describe('useRelationshipsByPredicate', () => {
    it('should fetch relationships by predicate successfully', async () => {
      mockAxios.onGet('/api/term-relationships/').reply(200, [mockRelationship]);

      const { result } = renderHook(() => useRelationshipsByPredicate('relates_to'), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual([mockRelationship]);
      expect(mockAxios.history.get).toHaveLength(1);
      expect(mockAxios.history.get[0].params).toEqual({ predicate: 'relates_to' });
    });

    it('should not fetch when predicate is empty', async () => {
      const { result } = renderHook(() => useRelationshipsByPredicate(''), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(result.current.isPending).toBe(true);
      });

      expect(mockAxios.history.get).toHaveLength(0);
    });
  });

  describe('useCreateRelationship', () => {
    it('should create a relationship successfully', async () => {
      mockAxios.onPost('/api/term-relationships/').reply(201, mockRelationship);

      const { result } = renderHook(() => useCreateRelationship(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await result.current.mutateAsync(mockCreateRelationship);
      });

      expect(result.current.isSuccess).toBe(true);
      expect(result.current.data).toEqual(mockRelationship);
      expect(mockAxios.history.post).toHaveLength(1);
      expect(mockAxios.history.post[0].url).toBe('/api/term-relationships/');
      expect(JSON.parse(mockAxios.history.post[0].data)).toEqual(mockCreateRelationship);
    });

    it('should invalidate related queries on success', async () => {
      mockAxios.onPost('/api/term-relationships/').reply(201, mockRelationship);

      const invalidateQueriesSpy = jest.spyOn(queryClient, 'invalidateQueries');
      const setQueryDataSpy = jest.spyOn(queryClient, 'setQueryData');

      const { result } = renderHook(() => useCreateRelationship(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await result.current.mutateAsync(mockCreateRelationship);
      });

      expect(setQueryDataSpy).toHaveBeenCalledWith(
        relationshipsQueryKeys.detail(mockRelationship.id),
        mockRelationship
      );
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: relationshipsQueryKeys.lists(),
      });
    });

    it('should handle creation errors', async () => {
      const errorMessage = 'Failed to create relationship';
      mockAxios.onPost('/api/term-relationships/').reply(400, { detail: errorMessage });

      const { result } = renderHook(() => useCreateRelationship(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        try {
          await result.current.mutateAsync(mockCreateRelationship);
        } catch {
          // Expected to throw
        }
      });

      expect(result.current.isError).toBe(true);
      expect(result.current.error).toBeDefined();
    });
  });

  describe('useUpdateRelationship', () => {
    it('should update a relationship successfully', async () => {
      const updatedRelationship = { ...mockRelationship, ...mockUpdateRelationship };
      mockAxios.onPut('/api/term-relationships/1').reply(200, updatedRelationship);

      const { result } = renderHook(() => useUpdateRelationship(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await result.current.mutateAsync({ id: '1', data: mockUpdateRelationship });
      });

      expect(result.current.isSuccess).toBe(true);
      expect(result.current.data).toEqual(updatedRelationship);
      expect(mockAxios.history.put).toHaveLength(1);
      expect(mockAxios.history.put[0].url).toBe('/api/term-relationships/1');
      expect(JSON.parse(mockAxios.history.put[0].data)).toEqual(mockUpdateRelationship);
    });

    it('should update cache on success', async () => {
      const updatedRelationship = { ...mockRelationship, ...mockUpdateRelationship };
      mockAxios.onPut('/api/term-relationships/1').reply(200, updatedRelationship);

      const setQueryDataSpy = jest.spyOn(queryClient, 'setQueryData');

      const { result } = renderHook(() => useUpdateRelationship(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await result.current.mutateAsync({ id: '1', data: mockUpdateRelationship });
      });

      expect(setQueryDataSpy).toHaveBeenCalledWith(
        relationshipsQueryKeys.detail('1'),
        updatedRelationship
      );
    });
  });

  describe('useDeleteRelationship', () => {
    it('should delete a relationship successfully', async () => {
      mockAxios.onDelete('/api/term-relationships/1').reply(204);

      const { result } = renderHook(() => useDeleteRelationship(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await result.current.mutateAsync('1');
      });

      expect(result.current.isSuccess).toBe(true);
      expect(mockAxios.history.delete).toHaveLength(1);
      expect(mockAxios.history.delete[0].url).toBe('/api/term-relationships/1');
    });

    it('should remove from cache on success', async () => {
      mockAxios.onDelete('/api/term-relationships/1').reply(204);

      const removeQueriesSpy = jest.spyOn(queryClient, 'removeQueries');

      const { result } = renderHook(() => useDeleteRelationship(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await result.current.mutateAsync('1');
      });

      expect(removeQueriesSpy).toHaveBeenCalledWith({
        queryKey: relationshipsQueryKeys.detail('1'),
      });
    });

    it('should invalidate broader queries when relationship data is not available', async () => {
      mockAxios.onDelete('/api/term-relationships/1').reply(204);

      const invalidateQueriesSpy = jest.spyOn(queryClient, 'invalidateQueries');
      
      // Mock getQueryData to return null (no cached data)
      jest.spyOn(queryClient, 'getQueryData').mockReturnValue(null);

      const { result } = renderHook(() => useDeleteRelationship(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await result.current.mutateAsync('1');
      });

      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: relationshipsQueryKeys.all,
      });
    });
  });
});
