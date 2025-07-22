/**
 * Integration Test Example
 * 
 * End-to-end test of the LayerList component
 */

import React from 'react';
import { waitFor } from '@testing-library/react-native';
import { ENDPOINTS } from '../../api/config';
import { 
  mockAxios, 
  mockLayerData, 
  renderWithQueryClient,
  resetMocks 
} from '../utils/testUtils';

// Simple mock component since we don't have the actual UI components
const MockLayerList = () => {
  // This would be your actual LayerList component
  return null;
};

describe('LayerList Integration', () => {
  beforeEach(() => {
    resetMocks();
  });

  it('should render the LayerList component with mocked data', async () => {
    const mockData = [mockLayerData];
    mockAxios.onGet(`${ENDPOINTS.LAYERS}/`).reply(200, mockData);

    const { queryClient } = renderWithQueryClient(<MockLayerList />);

    // Wait for query to settle
    await waitFor(() => {
      expect(queryClient.isFetching()).toBe(0);
    });

    // Verify the API was called
    expect(mockAxios.history.get).toHaveLength(1);
    expect(mockAxios.history.get[0].url).toBe(`${ENDPOINTS.LAYERS}/`);
  });

  // Add more integration tests here as you build actual components
});
