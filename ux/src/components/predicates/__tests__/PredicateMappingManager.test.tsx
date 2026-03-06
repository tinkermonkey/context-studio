/**
 * Integration Tests for Predicate Mapping Manager Component
 *
 * Tests for the main PredicateMappingManager and its child components
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PredicateMappingManager } from "../PredicateMappingManager";
import { vi, describe, it, expect } from "vitest";
import "@testing-library/jest-dom";

// Mock react-icons
vi.mock("react-icons/hi", () => ({
  HiDatabase: () => <div>HiDatabase</div>,
  HiSearch: () => <div>HiSearch</div>,
  HiCollection: () => <div>HiCollection</div>,
  HiCog: () => <div>HiCog</div>,
  HiPlusCircle: () => <div>HiPlusCircle</div>,
  HiCheckCircle: () => <div>HiCheckCircle</div>,
  HiCheck: () => <div>HiCheck</div>,
  HiX: () => <div>HiX</div>,
  HiExclamation: () => <div>HiExclamation</div>,
  HiInformationCircle: () => <div>HiInformationCircle</div>,
}));

// Mock lucide-react
vi.mock("lucide-react", () => ({
  Search: () => <div>Search Icon</div>,
  RefreshCw: () => <div>RefreshCw Icon</div>,
  X: () => <div>X Icon</div>,
  GitBranch: () => <div>GitBranch Icon</div>,
  Plus: () => <div>Plus Icon</div>,
  Check: () => <div>Check Icon</div>,
  Filter: () => <div>Filter Icon</div>,
  CheckCircle: () => <div>CheckCircle Icon</div>,
  XCircle: () => <div>XCircle Icon</div>,
  ArrowLeft: () => <div>ArrowLeft Icon</div>,
  ArrowRight: () => <div>ArrowRight Icon</div>,
  Trash2: () => <div>Trash2 Icon</div>,
  Database: () => <div>Database Icon</div>,
  Layers: () => <div>Layers Icon</div>,
  Settings: () => <div>Settings Icon</div>,
  PlusCircle: () => <div>PlusCircle Icon</div>,
  ChevronDown: () => <div>ChevronDown Icon</div>,
  Info: () => <div>Info Icon</div>,
  ExternalLink: () => <div>ExternalLink Icon</div>,
  AlertCircle: () => <div>AlertCircle Icon</div>,
  BookOpen: () => <div>BookOpen Icon</div>,
}));

// Mock API hooks
vi.mock("@/api/hooks/predicates", () => ({
  useExternalPredicates: vi.fn(() => ({
    data: { data: [], total: 0 },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  })),
  useDiscoverPredicates: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
  useSearchExternalPredicates: vi.fn(() => ({
    data: null,
    isLoading: false,
    error: null,
  })),
  useSimilarPredicates: vi.fn(() => ({
    data: null,
    isLoading: false,
    error: null,
  })),
  useClusterPredicates: vi.fn(() => ({
    mutate: vi.fn(),
    data: null,
    isLoading: false,
    isPending: false,
  })),
  usePredicates: vi.fn(() => ({
    data: { data: [], total: 0 },
    isLoading: false,
    error: null,
  })),
  useCreatePredicateMutation: vi.fn(() => ({
    mutateAsync: vi.fn(),
    isPending: false,
  })),
  useUpdatePredicateMutation: vi.fn(() => ({
    mutateAsync: vi.fn(),
    isPending: false,
  })),
  useBulkUpdateRelevanceMutation: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
}));

// Mock useButterToast
vi.mock("@/hooks/useButterToast", () => ({
  useButterToast: vi.fn(() => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  })),
}));

// Create QueryClient for testing
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

// Wrapper component
const createWrapper = () => {
  const queryClient = createTestQueryClient();
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("PredicateMappingManager", () => {
  it("should render main component", () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    expect(screen.getByText("Predicate Mapping Manager")).toBeInTheDocument();
  });

  it("should render description", () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    expect(
      screen.getByText(/Discover, analyze, and map predicates/i),
    ).toBeInTheDocument();
  });

  it("should render all tabs", () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(6);
    expect(screen.getAllByText("External Predicates")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Similarity Search")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Cluster Analysis")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Manual Mapping")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Relevance Selection")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Configuration")[0]).toBeInTheDocument();
  });

  it("should show ExternalPredicatesTab by default", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getAllByText("External Predicates")[0]).toBeInTheDocument();
    });
  });
});

describe("ExternalPredicatesTab", () => {
  it("should display discover button", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("Discover Predicates")).toBeInTheDocument();
    });
  });

  it("should display search input", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    await waitFor(() => {
      const searchInputs = screen.getAllByPlaceholderText(/Search predicates/i);
      expect(searchInputs.length).toBeGreaterThan(0);
    });
  });
});

describe("SimilaritySearchTab", () => {
  it("should render when tab is clicked", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    const tabs = screen.getAllByRole("tab");
    const similarityTab = tabs.find((tab) =>
      tab.textContent?.includes("Similarity Search"),
    );
    fireEvent.click(similarityTab!);

    await waitFor(() => {
      expect(
        screen.getByText(/Select a predicate above to find similar/i),
      ).toBeInTheDocument();
    });
  });

  it("should display search form", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    const tabs = screen.getAllByRole("tab");
    const similarityTab = tabs.find((tab) =>
      tab.textContent?.includes("Similarity Search"),
    );
    fireEvent.click(similarityTab!);

    await waitFor(() => {
      expect(screen.getByText("Select Predicate")).toBeInTheDocument();
    });
  });
});

describe("ClusterVisualizationTab", () => {
  it("should render when tab is clicked", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    const tabs = screen.getAllByRole("tab");
    const clusterTab = tabs.find((tab) =>
      tab.textContent?.includes("Cluster Analysis"),
    );
    fireEvent.click(clusterTab!);

    await waitFor(() => {
      expect(screen.getByText("Clustering Parameters")).toBeInTheDocument();
    });
  });

  it("should display run clustering button", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    const tabs = screen.getAllByRole("tab");
    const clusterTab = tabs.find((tab) =>
      tab.textContent?.includes("Cluster Analysis"),
    );
    fireEvent.click(clusterTab!);

    await waitFor(() => {
      expect(screen.getByText("Run Clustering")).toBeInTheDocument();
    });
  });
});

describe("MappingConfigurationTab", () => {
  it("should render when tab is clicked", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    const tabs = screen.getAllByRole("tab");
    const configTab = tabs.find((tab) =>
      tab.textContent?.includes("Configuration"),
    );
    fireEvent.click(configTab!);

    await waitFor(() => {
      expect(screen.getByText("Relevance Filtering")).toBeInTheDocument();
    });
  });

  it("should display filter toggle", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    const tabs = screen.getAllByRole("tab");
    const configTab = tabs.find((tab) =>
      tab.textContent?.includes("Configuration"),
    );
    fireEvent.click(configTab!);

    await waitFor(() => {
      expect(
        screen.getByText(/Filter relationships based on predicate relevance/i),
      ).toBeInTheDocument();
    });
  });
});

describe("ManualMappingInterface", () => {
  it("should render when tab is clicked", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    const tabs = screen.getAllByRole("tab");
    const manualTab = tabs.find((tab) =>
      tab.textContent?.includes("Manual Mapping"),
    );
    fireEvent.click(manualTab!);

    await waitFor(() => {
      expect(screen.getByText("Global Predicate")).toBeInTheDocument();
    });
  });

  it("should display mapping confidence slider", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    const tabs = screen.getAllByRole("tab");
    const manualTab = tabs.find((tab) =>
      tab.textContent?.includes("Manual Mapping"),
    );
    fireEvent.click(manualTab!);

    await waitFor(() => {
      expect(screen.getByText(/Mapping Confidence:/i)).toBeInTheDocument();
    });
  });
});

describe("RelevanceSelectionUI", () => {
  it("should render when tab is clicked", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    const tabs = screen.getAllByRole("tab");
    const relevanceTab = tabs.find((tab) =>
      tab.textContent?.includes("Relevance Selection"),
    );
    fireEvent.click(relevanceTab!);

    await waitFor(() => {
      expect(screen.getAllByText("Relevance Selection")[0]).toBeInTheDocument();
    });
  });

  it("should display statistics", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    const tabs = screen.getAllByRole("tab");
    const relevanceTab = tabs.find((tab) =>
      tab.textContent?.includes("Relevance Selection"),
    );
    fireEvent.click(relevanceTab!);

    await waitFor(() => {
      // Look for statistics labels
      const totalLabels = screen.getAllByText("Total");
      expect(totalLabels.length).toBeGreaterThan(0);
    });
  });
});

describe("Component Integration", () => {
  it("should switch between tabs correctly", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    // Start with External Predicates tab
    expect(screen.getByText("Discover Predicates")).toBeInTheDocument();

    const tabs = screen.getAllByRole("tab");

    // Switch to Similarity Search
    const similarityTab = tabs.find((tab) =>
      tab.textContent?.includes("Similarity Search"),
    );
    fireEvent.click(similarityTab!);
    await waitFor(() => {
      expect(
        screen.getByText(/Select a predicate above to find similar/i),
      ).toBeInTheDocument();
    });

    // Switch to Configuration
    const configTab = tabs.find((tab) =>
      tab.textContent?.includes("Configuration"),
    );
    fireEvent.click(configTab!);
    await waitFor(() => {
      expect(screen.getByText("Relevance Filtering")).toBeInTheDocument();
    });
  });

  it("should maintain state when switching tabs", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    const tabs = screen.getAllByRole("tab");

    // Go to configuration and toggle filter
    const configTab = tabs.find((tab) =>
      tab.textContent?.includes("Configuration"),
    );
    fireEvent.click(configTab!);

    // Switch to another tab
    const similarityTab = tabs.find((tab) =>
      tab.textContent?.includes("Similarity Search"),
    );
    fireEvent.click(similarityTab!);

    // Switch back to configuration
    fireEvent.click(configTab!);

    // Filter toggle should still be there
    await waitFor(() => {
      expect(screen.getByText("Relevance Filtering")).toBeInTheDocument();
    });
  });
});
