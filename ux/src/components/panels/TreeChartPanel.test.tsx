/**
 * TreeChartPanel Component Tests
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TreeChartPanel } from '@/components/panels/TreeChartPanel';
import { useLayers } from '@/api/hooks/layers/useLayers';
import { useDomains } from '@/api/hooks/domains/useDomains';
import { useTerms, useTerm } from '@/api/hooks/terms/useTerms';
import { vi } from 'vitest';

// Mock the hooks
vi.mock('@/api/hooks/layers/useLayers');
vi.mock('@/api/hooks/domains/useDomains');
vi.mock('@/api/hooks/terms/useTerms');
vi.mock('@/components/graphs/hierarchy/tree_chart', () => ({
  TreeChart: ({ chartData }: any) => (
    <div data-testid="tree-chart">
      Tree Chart - Root: {chartData?.root?.title || 'No data'}
    </div>
  ),
}));

const mockUseLayers = useLayers as ReturnType<typeof vi.fn>;
const mockUseDomains = useDomains as ReturnType<typeof vi.fn>;
const mockUseTerms = useTerms as ReturnType<typeof vi.fn>;
const mockUseTerm = useTerm as ReturnType<typeof vi.fn>;

const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

describe('TreeChartPanel', () => {
  const mockLayers = [
    { id: '1', title: 'Layer 1', definition: 'Test layer 1' }
  ];
  
  const mockDomains = [
    { id: '1', layer_id: '1', title: 'Domain 1', definition: 'Test domain 1' }
  ];
  
  const mockTerms = [
    { id: '1', domain_id: '1', title: 'Term 1', definition: 'Test term 1' }
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    
    // Default mock return value for useTerm
    mockUseTerm.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as any);
  });

  it('displays loading state while data is being fetched', () => {
    mockUseLayers.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);
    mockUseDomains.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);
    mockUseTerms.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <TreeChartPanel />
      </TestWrapper>
    );

    expect(screen.getByRole('status')).toBeInTheDocument(); // Spinner
  });

  it('displays error state when data loading fails', () => {
    const testError = new Error('Failed to load data');
    
    mockUseLayers.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: testError,
    } as any);
    mockUseDomains.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as any);
    mockUseTerms.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <TreeChartPanel />
      </TestWrapper>
    );

    expect(screen.getByText('Error loading data')).toBeInTheDocument();
    expect(screen.getByText('Failed to load data')).toBeInTheDocument();
  });

  it('renders TreeChart when data is successfully loaded', async () => {
    mockUseLayers.mockReturnValue({
      data: mockLayers,
      isLoading: false,
      error: null,
    } as any);
    mockUseDomains.mockReturnValue({
      data: mockDomains,
      isLoading: false,
      error: null,
    } as any);
    mockUseTerms.mockReturnValue({
      data: mockTerms,
      isLoading: false,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <TreeChartPanel />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByTestId('tree-chart')).toBeInTheDocument();
    });
  });

  it('loads specific term when termId is provided', async () => {
    const testTermId = 'test-term-id';
    const mockTargetTerm = { 
      id: testTermId, 
      domain_id: '1', 
      title: 'Target Term', 
      definition: 'Target term definition' 
    };

    mockUseLayers.mockReturnValue({
      data: mockLayers,
      isLoading: false,
      error: null,
    } as any);
    mockUseDomains.mockReturnValue({
      data: mockDomains,
      isLoading: false,
      error: null,
    } as any);
    mockUseTerms.mockReturnValue({
      data: mockTerms,
      isLoading: false,
      error: null,
    } as any);
    mockUseTerm.mockReturnValue({
      data: mockTargetTerm,
      isLoading: false,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <TreeChartPanel termId={testTermId} />
      </TestWrapper>
    );

    // Verify that useTerm was called with the correct termId
    expect(mockUseTerm).toHaveBeenCalledWith(testTermId, true);

    await waitFor(() => {
      expect(screen.getByTestId('tree-chart')).toBeInTheDocument();
    });
  });

  it('displays custom loading component when provided', () => {
    const customLoadingComponent = <div data-testid="custom-loading">Custom loading...</div>;
    
    mockUseLayers.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);
    mockUseDomains.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);
    mockUseTerms.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <TreeChartPanel loadingComponent={customLoadingComponent} />
      </TestWrapper>
    );

    expect(screen.getByTestId('custom-loading')).toBeInTheDocument();
    expect(screen.getByText('Custom loading...')).toBeInTheDocument();
  });

  it('displays custom error component when provided', () => {
    const customErrorComponent = <div data-testid="custom-error">Custom error message</div>;
    const testError = new Error('Failed to load');
    
    mockUseLayers.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: testError,
    } as any);
    mockUseDomains.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as any);
    mockUseTerms.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <TreeChartPanel errorComponent={customErrorComponent} />
      </TestWrapper>
    );

    expect(screen.getByTestId('custom-error')).toBeInTheDocument();
    expect(screen.getByText('Custom error message')).toBeInTheDocument();
  });

  it('applies custom className when provided', () => {
    mockUseLayers.mockReturnValue({
      data: mockLayers,
      isLoading: false,
      error: null,
    } as any);
    mockUseDomains.mockReturnValue({
      data: mockDomains,
      isLoading: false,
      error: null,
    } as any);
    mockUseTerms.mockReturnValue({
      data: mockTerms,
      isLoading: false,
      error: null,
    } as any);

    const { container } = render(
      <TestWrapper>
        <TreeChartPanel className="custom-tree-panel" />
      </TestWrapper>
    );

    expect(container.querySelector('.custom-tree-panel')).toBeInTheDocument();
  });
});
