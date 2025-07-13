/**
 * Layer Service Tests
 * 
 * Unit tests for the layer service
 */

import { layerService } from '../../api/services/layers';
import { ENDPOINTS } from '../../api/config';
import { 
  mockAxios, 
  mockLayerData, 
  mockFindLayerResult,
  mockValidationError,
  resetMocks 
} from '../utils/apiTestUtils';
import { ApiError, ValidationError, NotFoundError } from '../../api/errors/ApiError';

describe('LayerService', () => {
  beforeEach(() => {
    resetMocks();
  });

  describe('list', () => {
    it('should fetch layers successfully', async () => {
      const mockData = [mockLayerData];
      mockAxios.onGet(`${ENDPOINTS.LAYERS}/`).reply(200, mockData);

      const result = await layerService.list();

      expect(result).toEqual(mockData);
      expect(mockAxios.history.get).toHaveLength(1);
      expect(mockAxios.history.get[0].url).toBe(`${ENDPOINTS.LAYERS}/`);
    });

    it('should pass query parameters correctly', async () => {
      const mockData = [mockLayerData];
      const params = { skip: 10, limit: 20, sort: 'title' as const };
      
      mockAxios.onGet(`${ENDPOINTS.LAYERS}/`).reply(200, mockData);

      await layerService.list(params);

      expect(mockAxios.history.get[0].params).toEqual(params);
    });

    it('should handle server errors', async () => {
      mockAxios.onGet(`${ENDPOINTS.LAYERS}/`).reply(500, { message: 'Server error' });

      await expect(layerService.list()).rejects.toThrow(ApiError);
    });
  });

  describe('get', () => {
    it('should fetch a single layer successfully', async () => {
      const layerId = mockLayerData.id;
      mockAxios.onGet(`${ENDPOINTS.LAYERS}/${layerId}`).reply(200, mockLayerData);

      const result = await layerService.get(layerId);

      expect(result).toEqual(mockLayerData);
      expect(mockAxios.history.get).toHaveLength(1);
      expect(mockAxios.history.get[0].url).toBe(`${ENDPOINTS.LAYERS}/${layerId}`);
    });

    it('should handle not found errors', async () => {
      const layerId = 'non-existent-id';
      mockAxios.onGet(`${ENDPOINTS.LAYERS}/${layerId}`).reply(404);

      await expect(layerService.get(layerId)).rejects.toThrow(NotFoundError);
    });
  });

  describe('create', () => {
    it('should create a layer successfully', async () => {
      const createData = {
        title: 'New Layer',
        definition: 'A new layer',
        primary_predicate: 'test',
      };
      
      mockAxios.onPost(`${ENDPOINTS.LAYERS}/`).reply(201, mockLayerData);

      const result = await layerService.create(createData);

      expect(result).toEqual(mockLayerData);
      expect(mockAxios.history.post).toHaveLength(1);
      expect(mockAxios.history.post[0].url).toBe(`${ENDPOINTS.LAYERS}/`);
      expect(JSON.parse(mockAxios.history.post[0].data)).toEqual(createData);
    });

    it('should handle validation errors', async () => {
      const createData = {
        title: 'a', // Too short
        definition: 'A new layer',
        primary_predicate: 'test',
      };
      
      mockAxios.onPost(`${ENDPOINTS.LAYERS}/`).reply(422, mockValidationError);

      await expect(layerService.create(createData)).rejects.toThrow(ValidationError);
    });
  });

  describe('update', () => {
    it('should update a layer successfully', async () => {
      const layerId = mockLayerData.id;
      const updateData = { title: 'Updated Layer' };
      const updatedLayer = { ...mockLayerData, ...updateData };
      
      mockAxios.onPut(`${ENDPOINTS.LAYERS}/${layerId}`).reply(200, updatedLayer);

      const result = await layerService.update(layerId, updateData);

      expect(result).toEqual(updatedLayer);
      expect(mockAxios.history.put).toHaveLength(1);
      expect(mockAxios.history.put[0].url).toBe(`${ENDPOINTS.LAYERS}/${layerId}`);
      expect(JSON.parse(mockAxios.history.put[0].data)).toEqual(updateData);
    });
  });

  describe('delete', () => {
    it('should delete a layer successfully', async () => {
      const layerId = mockLayerData.id;
      mockAxios.onDelete(`${ENDPOINTS.LAYERS}/${layerId}`).reply(200);

      await layerService.delete(layerId);

      expect(mockAxios.history.delete).toHaveLength(1);
      expect(mockAxios.history.delete[0].url).toBe(`${ENDPOINTS.LAYERS}/${layerId}`);
    });
  });

  describe('find', () => {
    it('should search layers successfully', async () => {
      const searchParams = { query: 'test layer' };
      const mockResults = [mockFindLayerResult];
      
      mockAxios.onPost(`${ENDPOINTS.LAYERS}/find`).reply(200, mockResults);

      const result = await layerService.find(searchParams);

      expect(result).toEqual(mockResults);
      expect(mockAxios.history.post).toHaveLength(1);
      expect(mockAxios.history.post[0].url).toBe(`${ENDPOINTS.LAYERS}/find`);
      expect(JSON.parse(mockAxios.history.post[0].data)).toEqual(searchParams);
    });

    it('should handle empty search results', async () => {
      const searchParams = { query: 'nonexistent' };
      mockAxios.onPost(`${ENDPOINTS.LAYERS}/find`).reply(200, []);

      const result = await layerService.find(searchParams);

      expect(result).toEqual([]);
    });
  });
});
