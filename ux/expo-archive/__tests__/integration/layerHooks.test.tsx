/**
 * Layer Hooks Tests
 * 
 * Integration tests for layer React Query hooks
 */

import { renderHook, waitFor, act } from '@testing-library/react-native';
import { useLayers, useLayer, useCreateLayer, useDeleteLayer } from '../../api/hooks/layers';
import { ENDPOINTS } from '../../api/config';
import { 
  mockAxios, 
  mockLayerData, 
  createQueryWrapper,
  resetMocks,
  createTestQueryClient 
} from '../utils/testUtils';

describe('Layer Hooks', () => {
  beforeEach(() => {
    resetMocks();
  });

  describe('useLayers', () => {
    it('should fetch layers successfully', async () => {
      const mockData = [mockLayerData];
      mockAxios.onGet(`${ENDPOINTS.LAYERS}/`).reply(200, mockData);

      const { result } = renderHook(() => useLayers(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockData);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBe(null);
    });

    it('should handle loading state', () => {
      mockAxios.onGet(`${ENDPOINTS.LAYERS}/`).reply(() => new Promise(() => {})); // Never resolves

      const { result } = renderHook(() => useLayers(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.data).toBeUndefined();
      expect(result.current.error).toBe(null);
    });

    it('should handle error state', async () => {
      mockAxios.onGet(`${ENDPOINTS.LAYERS}/`).reply(500, { message: 'Server error' });

      const { result } = renderHook(() => useLayers(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.data).toBeUndefined();
      expect(result.current.error).toBeTruthy();
    });

    it('should pass parameters correctly', async () => {
      const params = { skip: 10, limit: 20 };
      mockAxios.onGet(`${ENDPOINTS.LAYERS}/`).reply(200, []);

      renderHook(() => useLayers(params), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(mockAxios.history.get[0].params).toEqual(params);
      });
    });
  });

  describe('useLayer', () => {
    it('should fetch a single layer successfully', async () => {
      const layerId = mockLayerData.id;
      mockAxios.onGet(`${ENDPOINTS.LAYERS}/${layerId}`).reply(200, mockLayerData);

      const { result } = renderHook(() => useLayer(layerId), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockLayerData);
    });

    it('should not fetch when id is empty', () => {
      const { result } = renderHook(() => useLayer(''), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.fetchStatus).toBe('idle');
      expect(mockAxios.history.get).toHaveLength(0);
    });
  });

  describe('useCreateLayer', () => {
    it('should create a layer successfully', async () => {
      const createData = {
        title: 'New Layer',
        definition: 'A new layer',
        primary_predicate: 'test',
      };
      
      mockAxios.onPost(`${ENDPOINTS.LAYERS}/`).reply(201, mockLayerData);
      mockAxios.onGet(`${ENDPOINTS.LAYERS}/`).reply(200, [mockLayerData]);

      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useCreateLayer(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.mutateAsync(createData);
      });

      expect(result.current.isSuccess).toBe(true);
      expect(result.current.data).toEqual(mockLayerData);
      expect(mockAxios.history.post).toHaveLength(1);
    });

    it('should handle validation errors', async () => {
      const createData = {
        title: 'a', // Too short
        definition: 'A new layer',
        primary_predicate: 'test',
      };
      
      mockAxios.onPost(`${ENDPOINTS.LAYERS}/`).reply(422, {
        detail: [
          {
            type: 'string_too_short',
            loc: ['body', 'title'],
            msg: 'String should have at least 2 characters',
          },
        ],
      });

      const { result } = renderHook(() => useCreateLayer(), {
        wrapper: createQueryWrapper(),
      });

      await act(async () => {
        try {
          await result.current.mutateAsync(createData);
        } catch {
          // Expected error
        }
      });

      expect(result.current.isError).toBe(true);
      expect(result.current.error).toBeTruthy();
    });
  });

  describe('useDeleteLayer', () => {
    it('should delete a layer successfully', async () => {
      const layerId = mockLayerData.id;
      mockAxios.onDelete(`${ENDPOINTS.LAYERS}/${layerId}`).reply(200);
      mockAxios.onGet(`${ENDPOINTS.LAYERS}/`).reply(200, []);

      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useDeleteLayer(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.mutateAsync(layerId);
      });

      expect(result.current.isSuccess).toBe(true);
      expect(mockAxios.history.delete).toHaveLength(1);
    });
  });
});
