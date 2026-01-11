/**
 * ReferenceNodePanel Component Tests
 */

import React from "react";
import { render, screen, waitFor, fireEvent, cleanup } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";

import { ReferenceNodePanel } from "../ReferenceNodePanel";
import { useReferenceLinks } from "@/api/hooks/structure_nodes/useReferenceLinks";

// Mock the hooks
vi.mock("@/api/hooks/structure_nodes/useReferenceLinks", () => ({
  useReferenceLinks: vi.fn(),
  useAddReferenceLinks: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
  useRemoveReferenceLink: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
}));
vi.mock("@/api/hooks/unifiedReference/useStreamingReference", () => ({
  useStreamingUnifiedSearch: vi.fn(() => ({
    search: vi.fn(),
    searchState: null,
    isSearching: false,
    hasResults: false,
    results: [],
    totalResults: 0,
    completedSources: [],
    errorSources: [],
  })),
  useSourceLoadingStates: vi.fn(() => ({
    isSourceLoading: vi.fn(() => false),
    isSourceComplete: vi.fn(() => false),
    isSourceError: vi.fn(() => false),
    getSourceExecutionTime: vi.fn(() => 0),
    getSourceError: vi.fn(() => null),
  })),
}));
vi.mock("@/utils/toast");

const mockUseReferenceLinks = useReferenceLinks as ReturnType<typeof vi.fn>;

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

describe("ReferenceNodePanel", () => {
  const mockNodeId = "550e8400-e29b-41d4-a716-446655440000"; // Valid UUID

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("displays loading state while fetching reference links", () => {
    mockUseReferenceLinks.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <ReferenceNodePanel nodeId={mockNodeId} />
      </TestWrapper>
    );

    expect(screen.getByText(/loading reference links/i)).toBeInTheDocument();
  });

  it("displays error state when fetching fails", () => {
    const errorMessage = "Failed to fetch";
    mockUseReferenceLinks.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error(errorMessage),
    } as any);

    render(
      <TestWrapper>
        <ReferenceNodePanel nodeId={mockNodeId} />
      </TestWrapper>
    );

    expect(screen.getByText(/failed to load reference links/i)).toBeInTheDocument();
  });

  it("displays empty state when no reference links exist", () => {
    mockUseReferenceLinks.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <ReferenceNodePanel nodeId={mockNodeId} />
      </TestWrapper>
    );

    expect(screen.getByText(/no reference nodes associated/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/search reference sources/i)).toBeInTheDocument();
  });

  it("displays persisted reference links when available", () => {
    const mockLinks = [
      { source: "dbpedia", external_id: "Test_Concept" },
      { source: "schema_org", external_id: "Thing" },
    ];

    mockUseReferenceLinks.mockReturnValue({
      data: mockLinks,
      isLoading: false,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <ReferenceNodePanel nodeId={mockNodeId} />
      </TestWrapper>
    );

    expect(screen.getByText("Reference Nodes")).toBeInTheDocument();
    expect(screen.getByText("Add References")).toBeInTheDocument();
  });

  it("shows search interface when 'Add References' button is clicked", async () => {
    const mockLinks = [
      { source: "dbpedia", external_id: "Test_Concept" },
    ];

    mockUseReferenceLinks.mockReturnValue({
      data: mockLinks,
      isLoading: false,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <ReferenceNodePanel nodeId={mockNodeId} />
      </TestWrapper>
    );

    const addButton = screen.getByText("Add References");
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search reference sources/i)).toBeInTheDocument();
    });
  });

  it("shows cancel button when search is active and links exist", async () => {
    const mockLinks = [
      { source: "dbpedia", external_id: "Test_Concept" },
    ];

    mockUseReferenceLinks.mockReturnValue({
      data: mockLinks,
      isLoading: false,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <ReferenceNodePanel nodeId={mockNodeId} />
      </TestWrapper>
    );

    const addButton = screen.getByText("Add References");
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(screen.getByText("Cancel")).toBeInTheDocument();
    });
  });

  it("displays error for invalid UUID format", () => {
    mockUseReferenceLinks.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <ReferenceNodePanel nodeId="invalid-uuid" />
      </TestWrapper>
    );

    expect(screen.getByText(/invalid node id format/i)).toBeInTheDocument();
  });
});
