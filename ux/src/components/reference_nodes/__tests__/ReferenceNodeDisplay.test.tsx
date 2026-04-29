/**
 * ReferenceNodeDisplay Component Tests
 */

import React from "react";
import { render, screen, cleanup } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";

import { ReferenceNodeDisplay } from "../ReferenceNodeDisplay";
import { useRemoveReferenceLink } from "@/api/hooks/structure_nodes/useReferenceLinks";
import { ReferenceLink } from "@/api/types/structureNodes";

// Mock the hooks
vi.mock("@/api/hooks/structure_nodes/useReferenceLinks");
vi.mock("@/utils/toast");

const mockUseRemoveReferenceLink = useRemoveReferenceLink as ReturnType<
  typeof vi.fn
>;

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

describe("ReferenceNodeDisplay", () => {
  const mockNodeId = "550e8400-e29b-41d4-a716-446655440000"; // Valid UUID
  let mockWindowOpen: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();

    // Mock window.open and store reference
    mockWindowOpen = vi.fn().mockReturnValue(null);
     
    window.open = mockWindowOpen as any;

    // Default mock for remove mutation
    mockUseRemoveReferenceLink.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
       
    } as any);
  });

  afterEach(() => {
    cleanup();
    // Restore window.open if needed
    if (mockWindowOpen) {
      mockWindowOpen.mockRestore?.();
    }
  });

  it("returns null when no reference links are provided", () => {
    const { container } = render(
      <TestWrapper>
        <ReferenceNodeDisplay nodeId={mockNodeId} referenceLinks={[]} />
      </TestWrapper>,
    );

    expect(container.firstChild).toBeNull();
  });

  it("groups reference links by source", () => {
    const mockLinks: ReferenceLink[] = [
      { source: "dbpedia", external_id: "Test_Concept_1" },
      { source: "dbpedia", external_id: "Test_Concept_2" },
      { source: "schema_org", external_id: "Thing" },
      { source: "wikidata", external_id: "Q12345" },
    ];

    render(
      <TestWrapper>
        <ReferenceNodeDisplay nodeId={mockNodeId} referenceLinks={mockLinks} />
      </TestWrapper>,
    );

    // Check that source labels are displayed
    expect(screen.getByText("DBpedia")).toBeInTheDocument();
    expect(screen.getByText("Schema.org")).toBeInTheDocument();
    expect(screen.getByText("Wikidata")).toBeInTheDocument();

    // Check link counts
    expect(screen.getByText("(2 links)")).toBeInTheDocument();
    expect(screen.getAllByText("(1 link)")).toHaveLength(2);
  });

  it("displays external IDs for each reference link", () => {
    const mockLinks: ReferenceLink[] = [
      { source: "dbpedia", external_id: "Test_Concept" },
      { source: "schema_org", external_id: "Thing" },
    ];

    render(
      <TestWrapper>
        <ReferenceNodeDisplay nodeId={mockNodeId} referenceLinks={mockLinks} />
      </TestWrapper>,
    );

    expect(screen.getByText("Test_Concept")).toBeInTheDocument();
    expect(screen.getByText("Thing")).toBeInTheDocument();
  });

  it("shows view button with external link for each reference", () => {
    const mockLinks: ReferenceLink[] = [
      { source: "dbpedia", external_id: "Test_Concept" },
    ];

    render(
      <TestWrapper>
        <ReferenceNodeDisplay nodeId={mockNodeId} referenceLinks={mockLinks} />
      </TestWrapper>,
    );

    const viewButtons = screen.getAllByText("View");
    expect(viewButtons.length).toBeGreaterThan(0);
  });

  it("renders remove buttons for each reference link", () => {
    const mockLinks: ReferenceLink[] = [
      { source: "dbpedia", external_id: "Test_Concept" },
      { source: "schema_org", external_id: "Thing" },
    ];

    render(
      <TestWrapper>
        <ReferenceNodeDisplay nodeId={mockNodeId} referenceLinks={mockLinks} />
      </TestWrapper>,
    );

    // Verify that remove buttons are rendered
    const buttons = screen.getAllByRole("button");
    expect(buttons.length).toBeGreaterThan(0);
  });

  it("uses remove mutation hook for delete functionality", () => {
    const mockLinks: ReferenceLink[] = [
      { source: "dbpedia", external_id: "Test_Concept" },
    ];

    const mockMutate = vi.fn();
    mockUseRemoveReferenceLink.mockReturnValue({
      mutate: mockMutate,
      isPending: false,
       
    } as any);

    render(
      <TestWrapper>
        <ReferenceNodeDisplay nodeId={mockNodeId} referenceLinks={mockLinks} />
      </TestWrapper>,
    );

    // Verify the component renders without errors when using the mutation hook
    expect(screen.getByText("Test_Concept")).toBeInTheDocument();
    expect(mockUseRemoveReferenceLink).toHaveBeenCalledWith(
      mockNodeId,
      expect.any(Object),
    );
  });

  it("sorts sources alphabetically", () => {
    const mockLinks: ReferenceLink[] = [
      { source: "wikidata", external_id: "Q12345" },
      { source: "dbpedia", external_id: "Test_Concept" },
      { source: "schema_org", external_id: "Thing" },
    ];

    render(
      <TestWrapper>
        <ReferenceNodeDisplay nodeId={mockNodeId} referenceLinks={mockLinks} />
      </TestWrapper>,
    );

    const headings = screen.getAllByRole("heading", { level: 4 });
    const sourceTexts = headings.map((h) => h.textContent);

    // Verify DBpedia comes before Schema.org and Wikidata
    const dbpediaIndex = sourceTexts.findIndex((text) =>
      text?.includes("DBpedia"),
    );
    const schemaIndex = sourceTexts.findIndex((text) =>
      text?.includes("Schema.org"),
    );
    const wikidataIndex = sourceTexts.findIndex((text) =>
      text?.includes("Wikidata"),
    );

    expect(dbpediaIndex).toBeLessThan(schemaIndex);
    expect(schemaIndex).toBeLessThan(wikidataIndex);
  });
});
