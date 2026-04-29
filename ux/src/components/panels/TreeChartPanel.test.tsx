/**
 * TreeChartPanel Component Tests
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TreeChartPanel } from "@/components/panels/TreeChartPanel";
import { vi } from "vitest";
import {
  useTaxonomies,
} from "@/api/hooks/taxonomies/useTaxonomies";
import { useConceptSchemes } from "@/api/hooks/conceptSchemes/useConceptSchemes";
import { useOntologyClasses, useOntologyClass } from "@/api/hooks/ontologyClasses/useOntologyClasses";

// Mock the router
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
}));

// Mock the hooks
vi.mock("@/api/hooks/taxonomies/useTaxonomies");
vi.mock("@/api/hooks/conceptSchemes/useConceptSchemes");
vi.mock("@/api/hooks/ontologyClasses/useOntologyClasses");
vi.mock("@/api/hooks/graph/useGraph", () => ({
  useTermHierarchy: () => ({
    data: null,
    isLoading: false,
    error: null,
  }),
}));

// Mock the TreeMenu component
vi.mock("@/components/graphs/tree_menu/tree_menu", () => ({
  TreeMenu: ({ chartData }: any) => (
    <div data-testid="tree-menu">
      Tree Menu - Root: {chartData?.root?.title || "No data"}
    </div>
  ),
}));

const mockUseTaxonomies = useTaxonomies as ReturnType<typeof vi.fn>;
const mockUseConceptSchemes = useConceptSchemes as ReturnType<typeof vi.fn>;
const mockUseOntologyClasses = useOntologyClasses as ReturnType<typeof vi.fn>;
const mockUseOntologyClass = useOntologyClass as ReturnType<typeof vi.fn>;

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("TreeChartPanel", () => {
  const mockLayers = [
    { id: "1", title: "Layer 1", description: "Test layer 1", version: 1 },
  ];

  const mockDomains = [
    { id: "1", taxonomy_id: "1", title: "Domain 1", description: "Test domain 1", version: 1 },
  ];

  const mockTerms = [
    { id: "1", scheme_id: "1", title: "Term 1", definition: "Test term 1", version: 1 },
  ];

  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock return value for useOntologyClass
    mockUseOntologyClass.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as any);
  });

  it("displays loading state while data is being fetched", () => {
    mockUseTaxonomies.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);
    mockUseConceptSchemes.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);
    mockUseOntologyClasses.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <TreeChartPanel />
      </TestWrapper>,
    );

    expect(screen.getByRole("status")).toBeInTheDocument(); // Spinner
  });

  it("displays error state when data loading fails", () => {
    // Suppress expected error logs during this test
    const consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    const testError = new Error("Failed to load data");

    mockUseTaxonomies.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: testError,
       
    } as any);
    mockUseConceptSchemes.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
       
    } as any);
    mockUseOntologyClasses.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
       
    } as any);

    render(
      <TestWrapper>
        <TreeChartPanel />
      </TestWrapper>,
    );

    expect(screen.getByText("Error loading data")).toBeInTheDocument();
    expect(screen.getByText("Failed to load data")).toBeInTheDocument();

    consoleErrorSpy.mockRestore();
  });

  it("renders TreeMenu when data is successfully loaded", async () => {
    mockUseTaxonomies.mockReturnValue({
      data: mockLayers,
      isLoading: false,
      error: null,
       
    } as any);
    mockUseConceptSchemes.mockReturnValue({
      data: mockDomains,
      isLoading: false,
      error: null,
       
    } as any);
    mockUseOntologyClasses.mockReturnValue({
      data: mockTerms,
      isLoading: false,
      error: null,
       
    } as any);

    render(
      <TestWrapper>
        <TreeChartPanel />
      </TestWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("tree-menu")).toBeInTheDocument();
    });
  });

  it("loads specific term when termId is provided", async () => {
    const testTermId = "test-term-id";
    const mockTargetTerm = {
      id: testTermId,
      scheme_id: "1",
      title: "Target Term",
      definition: "Target term definition",
    };

    // Include the target term in the terms array so it exists in the tree
    const mockTermsWithTarget = [...mockTerms, mockTargetTerm];

    mockUseTaxonomies.mockReturnValue({
      data: mockLayers,
      isLoading: false,
      error: null,
       
    } as any);
    mockUseConceptSchemes.mockReturnValue({
      data: mockDomains,
      isLoading: false,
      error: null,
       
    } as any);
    mockUseOntologyClasses.mockReturnValue({
      data: mockTermsWithTarget,
      isLoading: false,
      error: null,
       
    } as any);
    mockUseOntologyClass.mockReturnValue({
      data: mockTargetTerm,
      isLoading: false,
      error: null,
       
    } as any);

    render(
      <TestWrapper>
        <TreeChartPanel termId={testTermId} />
      </TestWrapper>,
    );

    // Verify that useStructureNode was called with the correct termId
    expect(mockUseOntologyClass).toHaveBeenCalledWith(testTermId);

    await waitFor(() => {
      expect(screen.getByTestId("tree-menu")).toBeInTheDocument();
    });
  });

  it("displays custom loading component when provided", () => {
    const customLoadingComponent = (
      <div data-testid="custom-loading">Custom loading...</div>
    );

    mockUseTaxonomies.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
       
    } as any);
    mockUseConceptSchemes.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
       
    } as any);
    mockUseOntologyClasses.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
       
    } as any);

    render(
      <TestWrapper>
        <TreeChartPanel loadingComponent={customLoadingComponent} />
      </TestWrapper>,
    );

    expect(screen.getByTestId("custom-loading")).toBeInTheDocument();
    expect(screen.getByText("Custom loading...")).toBeInTheDocument();
  });

  it("displays custom error component when provided", () => {
    // Suppress expected error logs during this test
    const consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    const customErrorComponent = (
      <div data-testid="custom-error">Custom error message</div>
    );
    const testError = new Error("Failed to load");

    mockUseTaxonomies.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: testError,
       
    } as any);
    mockUseConceptSchemes.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
       
    } as any);
    mockUseOntologyClasses.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
       
    } as any);

    render(
      <TestWrapper>
        <TreeChartPanel errorComponent={customErrorComponent} />
      </TestWrapper>,
    );

    expect(screen.getByTestId("custom-error")).toBeInTheDocument();
    expect(screen.getByText("Custom error message")).toBeInTheDocument();

    consoleErrorSpy.mockRestore();
  });

  it("applies custom className when provided", () => {
    mockUseTaxonomies.mockReturnValue({
      data: mockLayers,
      isLoading: false,
      error: null,
       
    } as any);
    mockUseConceptSchemes.mockReturnValue({
      data: mockDomains,
      isLoading: false,
      error: null,
       
    } as any);
    mockUseOntologyClasses.mockReturnValue({
      data: mockTerms,
      isLoading: false,
      error: null,
       
    } as any);

    const { container } = render(
      <TestWrapper>
        <TreeChartPanel className="custom-tree-panel" />
      </TestWrapper>,
    );

    expect(container.querySelector(".custom-tree-panel")).toBeInTheDocument();
  });
});
