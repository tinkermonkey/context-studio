/**
 * Terms and Relationships Integration Tests
 * 
 * Tests the integration between terms and relationships hooks
 */

import { renderHook, waitFor } from '@testing-library/react-native';
import { act } from 'react';
import { createTestQueryClient, createQueryWrapper, mockAxios } from '../utils/testUtils';
import {
  useTerms,
  useTerm,
  useCreateTerm,
  useDeleteTerm,
  termsQueryKeys,
} from '../../api/hooks/terms';
import {
  useRelationships,
  useTermRelationships,
  useCreateRelationship,
  useDeleteRelationship,
  relationshipsQueryKeys,
} from '../../api/hooks/relationships';
import type { components } from '../../api/client/types';

// Mock data
const mockTerm1: components['schemas']['TermOut'] = {
  id: 'term1',
  title: 'Source Term',
  definition: 'Source term definition',
  domain_id: 'domain1',
  layer_id: 'layer1',
  created_at: '2023-01-01T00:00:00Z',
  version: 1,
  last_modified: '2023-01-01T00:00:00Z',
};

const mockTerm2: components['schemas']['TermOut'] = {
  id: 'term2',
  title: 'Target Term',
  definition: 'Target term definition',
  domain_id: 'domain1',
  layer_id: 'layer1',
  created_at: '2023-01-02T00:00:00Z',
  version: 1,
  last_modified: '2023-01-02T00:00:00Z',
};

const mockRelationship: components['schemas']['TermRelationshipOut'] = {
  id: 'rel1',
  source_term_id: 'term1',
  target_term_id: 'term2',
  predicate: 'relates_to',
  created_at: '2023-01-03T00:00:00Z',
};

const mockCreateTerm: components['schemas']['TermCreate'] = {
  title: 'New Term',
  definition: 'New term definition',
  domain_id: 'domain1',
  layer_id: 'layer1',
};

const mockCreateRelationship: components['schemas']['TermRelationshipCreate'] = {
  source_term_id: 'term1',
  target_term_id: 'term2',
  predicate: 'relates_to',
};

describe('Terms and Relationships Integration', () => {
  let queryClient: ReturnType<typeof createTestQueryClient>;
  let QueryWrapper: ReturnType<typeof createQueryWrapper>;

  beforeEach(() => {
    queryClient = createTestQueryClient();
    QueryWrapper = createQueryWrapper(queryClient);
    mockAxios.reset();
  });

  describe('Term and Relationship Creation Workflow', () => {
    it('should create terms and then create a relationship between them', async () => {
      // Mock term creation
      mockAxios.onPost('/api/terms/').reply(201, mockTerm1);
      mockAxios.onPost('/api/terms/').reply(201, mockTerm2);
      mockAxios.onPost('/api/term-relationships/').reply(201, mockRelationship);

      // Create first term
      const { result: createTermResult1 } = renderHook(() => useCreateTerm(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await createTermResult1.current.mutateAsync(mockCreateTerm);
      });

      expect(createTermResult1.current.isSuccess).toBe(true);

      // Create second term
      const { result: createTermResult2 } = renderHook(() => useCreateTerm(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await createTermResult2.current.mutateAsync({
          ...mockCreateTerm,
          title: 'Second Term',
        });
      });

      expect(createTermResult2.current.isSuccess).toBe(true);

      // Create relationship between terms
      const { result: createRelationshipResult } = renderHook(() => useCreateRelationship(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await createRelationshipResult.current.mutateAsync(mockCreateRelationship);
      });

      expect(createRelationshipResult.current.isSuccess).toBe(true);
      expect(createRelationshipResult.current.data).toEqual(mockRelationship);
    });

    it('should invalidate term queries when relationships are created', async () => {
      mockAxios.onPost('/api/term-relationships/').reply(201, mockRelationship);

      const invalidateQueriesSpy = jest.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useCreateRelationship(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await result.current.mutateAsync(mockCreateRelationship);
      });

      // Verify that term queries were invalidated
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: termsQueryKeys.detail('term1'),
      });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: termsQueryKeys.detail('term2'),
      });
    });
  });

  describe('Term and Relationship Deletion Workflow', () => {
    it('should handle deletion of terms with existing relationships', async () => {
      // Set up cached data
      queryClient.setQueryData(relationshipsQueryKeys.detail('rel1'), mockRelationship);
      
      mockAxios.onDelete('/api/terms/term1').reply(204);
      mockAxios.onDelete('/api/term-relationships/rel1').reply(204);

      // Delete relationship first
      const { result: deleteRelationshipResult } = renderHook(() => useDeleteRelationship(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await deleteRelationshipResult.current.mutateAsync('rel1');
      });

      expect(deleteRelationshipResult.current.isSuccess).toBe(true);

      // Then delete term
      const { result: deleteTermResult } = renderHook(() => useDeleteTerm(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await deleteTermResult.current.mutateAsync('term1');
      });

      expect(deleteTermResult.current.isSuccess).toBe(true);
    });
  });

  describe('Term Relationships Query Integration', () => {
    it('should fetch relationships for a specific term and update when new relationships are added', async () => {
      const existingRelationships = [mockRelationship];
      const newRelationship: components['schemas']['TermRelationshipOut'] = {
        id: 'rel2',
        source_term_id: 'term1',
        target_term_id: 'term3',
        predicate: 'is_related_to',
        created_at: '2023-01-04T00:00:00Z',
      };

      // Mock initial relationships fetch
      mockAxios.onGet('/api/term-relationships/').reply((config) => {
        if (config.params?.source_term_id === 'term1') {
          return [200, existingRelationships];
        }
        if (config.params?.target_term_id === 'term1') {
          return [200, []];
        }
        return [200, []];
      });

      // Fetch existing relationships
      const { result: termRelationshipsResult } = renderHook(() => useTermRelationships('term1'), {
        wrapper: QueryWrapper,
      });

      await waitFor(() => {
        expect(termRelationshipsResult.current.isSuccess).toBe(true);
      });

      expect(termRelationshipsResult.current.data).toEqual(existingRelationships);

      // Mock creation of new relationship
      mockAxios.onPost('/api/term-relationships/').reply(201, newRelationship);

      // Create new relationship
      const { result: createRelationshipResult } = renderHook(() => useCreateRelationship(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await createRelationshipResult.current.mutateAsync({
          source_term_id: 'term1',
          target_term_id: 'term3',
          predicate: 'is_related_to',
        });
      });

      expect(createRelationshipResult.current.isSuccess).toBe(true);

      // Verify that term relationships query was invalidated
      const invalidateQueriesSpy = jest.spyOn(queryClient, 'invalidateQueries');
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: relationshipsQueryKeys.byTerm('term1'),
      });
    });
  });

  describe('Complex Query Interactions', () => {
    it('should handle concurrent operations on terms and relationships', async () => {
      // Mock multiple API calls
      mockAxios.onGet('/api/terms/').reply(200, [mockTerm1, mockTerm2]);
      mockAxios.onGet('/api/term-relationships/').reply(200, [mockRelationship]);
      mockAxios.onGet('/api/terms/term1').reply(200, mockTerm1);

      // Start multiple queries concurrently
      const { result: termsResult } = renderHook(() => useTerms(), {
        wrapper: QueryWrapper,
      });

      const { result: relationshipsResult } = renderHook(() => useRelationships(), {
        wrapper: QueryWrapper,
      });

      const { result: termResult } = renderHook(() => useTerm('term1'), {
        wrapper: QueryWrapper,
      });

      // Wait for all queries to complete
      await waitFor(() => {
        expect(termsResult.current.isSuccess).toBe(true);
        expect(relationshipsResult.current.isSuccess).toBe(true);
        expect(termResult.current.isSuccess).toBe(true);
      });

      expect(termsResult.current.data).toEqual([mockTerm1, mockTerm2]);
      expect(relationshipsResult.current.data).toEqual([mockRelationship]);
      expect(termResult.current.data).toEqual(mockTerm1);
    });

    it('should maintain cache consistency across multiple entity types', async () => {
      const invalidateQueriesSpy = jest.spyOn(queryClient, 'invalidateQueries');
      const setQueryDataSpy = jest.spyOn(queryClient, 'setQueryData');

      // Mock term creation
      mockAxios.onPost('/api/terms/').reply(201, mockTerm1);

      const { result: createTermResult } = renderHook(() => useCreateTerm(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await createTermResult.current.mutateAsync(mockCreateTerm);
      });

      // Verify term cache updates
      expect(setQueryDataSpy).toHaveBeenCalledWith(
        termsQueryKeys.detail(mockTerm1.id),
        mockTerm1
      );
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: termsQueryKeys.lists(),
      });

      // Mock relationship creation
      mockAxios.onPost('/api/term-relationships/').reply(201, mockRelationship);

      const { result: createRelationshipResult } = renderHook(() => useCreateRelationship(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await createRelationshipResult.current.mutateAsync(mockCreateRelationship);
      });

      // Verify relationship cache updates affect both entities
      expect(setQueryDataSpy).toHaveBeenCalledWith(
        relationshipsQueryKeys.detail(mockRelationship.id),
        mockRelationship
      );
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: relationshipsQueryKeys.lists(),
      });
      // Verify that term queries were also invalidated
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: termsQueryKeys.detail(mockRelationship.source_term_id),
      });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: termsQueryKeys.detail(mockRelationship.target_term_id),
      });
    });
  });

  describe('Error Handling in Complex Scenarios', () => {
    it('should handle partial failures in bulk operations', async () => {
      // Mock term creation success and relationship creation failure
      mockAxios.onPost('/api/terms/').reply(201, mockTerm1);
      mockAxios.onPost('/api/term-relationships/').reply(400, { detail: 'Relationship creation failed' });

      // Create term successfully
      const { result: createTermResult } = renderHook(() => useCreateTerm(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        await createTermResult.current.mutateAsync(mockCreateTerm);
      });

      expect(createTermResult.current.isSuccess).toBe(true);

      // Attempt to create relationship (should fail)
      const { result: createRelationshipResult } = renderHook(() => useCreateRelationship(), {
        wrapper: QueryWrapper,
      });

      await act(async () => {
        try {
          await createRelationshipResult.current.mutateAsync(mockCreateRelationship);
        } catch {
          // Expected to throw
        }
      });

      expect(createRelationshipResult.current.isError).toBe(true);
      expect(createTermResult.current.isSuccess).toBe(true); // Term should still be successful
    });
  });
});
