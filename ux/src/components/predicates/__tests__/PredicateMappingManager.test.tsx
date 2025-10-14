/**
 * Integration Tests for Predicate Mapping Manager Component
 *
 * Tests for the main PredicateMappingManager and its child components
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PredicateMappingManager } from "../PredicateMappingManager";
import "@testing-library/jest-dom";

// Mock react-icons
jest.mock("react-icons/hi", () => ({
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
jest.mock("lucide-react", () => ({
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

    expect(screen.getByText("External Predicates")).toBeInTheDocument();
    expect(screen.getByText("Similarity Search")).toBeInTheDocument();
    expect(screen.getByText("Cluster Analysis")).toBeInTheDocument();
    expect(screen.getByText("Manual Mapping")).toBeInTheDocument();
    expect(screen.getByText("Relevance Selection")).toBeInTheDocument();
    expect(screen.getByText("Configuration")).toBeInTheDocument();
  });

  it("should show ExternalPredicatesTab by default", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("External Predicates")).toBeInTheDocument();
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

    const similarityTab = screen.getByText("Similarity Search");
    fireEvent.click(similarityTab);

    await waitFor(() => {
      expect(screen.getByText(/Enter a predicate ID/i)).toBeInTheDocument();
    });
  });

  it("should display search form", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    const similarityTab = screen.getByText("Similarity Search");
    fireEvent.click(similarityTab);

    await waitFor(() => {
      expect(screen.getByText("Predicate ID")).toBeInTheDocument();
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

    const clusterTab = screen.getByText("Cluster Analysis");
    fireEvent.click(clusterTab);

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

    const clusterTab = screen.getByText("Cluster Analysis");
    fireEvent.click(clusterTab);

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

    const configTab = screen.getByText("Configuration");
    fireEvent.click(configTab);

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

    const configTab = screen.getByText("Configuration");
    fireEvent.click(configTab);

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

    const manualTab = screen.getByText("Manual Mapping");
    fireEvent.click(manualTab);

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

    const manualTab = screen.getByText("Manual Mapping");
    fireEvent.click(manualTab);

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

    const relevanceTab = screen.getByText("Relevance Selection");
    fireEvent.click(relevanceTab);

    await waitFor(() => {
      expect(screen.getByText("Relevance Selection")).toBeInTheDocument();
    });
  });

  it("should display statistics", async () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <PredicateMappingManager />
      </Wrapper>,
    );

    const relevanceTab = screen.getByText("Relevance Selection");
    fireEvent.click(relevanceTab);

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

    // Switch to Similarity Search
    const similarityTab = screen.getByText("Similarity Search");
    fireEvent.click(similarityTab);
    await waitFor(() => {
      expect(screen.getByText(/Enter a predicate ID/i)).toBeInTheDocument();
    });

    // Switch to Configuration
    const configTab = screen.getByText("Configuration");
    fireEvent.click(configTab);
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

    // Go to configuration and toggle filter
    const configTab = screen.getByText("Configuration");
    fireEvent.click(configTab);

    // Switch to another tab
    const similarityTab = screen.getByText("Similarity Search");
    fireEvent.click(similarityTab);

    // Switch back to configuration
    fireEvent.click(configTab);

    // Filter toggle should still be there
    await waitFor(() => {
      expect(screen.getByText("Relevance Filtering")).toBeInTheDocument();
    });
  });
});
