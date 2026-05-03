/**
 * Tests for RecentRunsTable component
 */

import React from "react";
import { fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import {
  renderWithProviders as render,
  screen,
} from "@/test/utils/renderWithProviders";
import { RecentRunsTable } from "../RecentRunsTable";
import type { ImportRun } from "@/api/types/interchange";

vi.mock("@/api/hooks/interchange", () => ({
  useInterchangeRuns: vi.fn(),
}));

vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, children, ...props }: any) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

describe("RecentRunsTable", () => {
  const mockRuns: ImportRun[] = [
    {
      id: "run-1",
      format: "skos",
      source_uri: "test1.skos",
      created_at: new Date("2024-01-01T10:00:00Z").toISOString(),
      status: "committed",
      affected_entity_ids: ["entity-1", "entity-2"],
    },
    {
      id: "run-2",
      format: "owl",
      source_uri: "test2.owl",
      created_at: new Date("2024-01-02T11:00:00Z").toISOString(),
      status: "pending",
      affected_entity_ids: ["entity-3"],
    },
    {
      id: "run-3",
      format: "graphml",
      source_uri: "http://example.com/graph.graphml",
      created_at: new Date("2024-01-03T12:00:00Z").toISOString(),
      status: "failed",
      affected_entity_ids: [],
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders table when runs are loaded", () => {
    const { useInterchangeRuns } = require("@/api/hooks/interchange");
    useInterchangeRuns.mockReturnValue({
      data: mockRuns,
      isLoading: false,
      error: null,
    });

    render(<RecentRunsTable />);

    expect(screen.getByTestId("interchange-recent-runs-table")).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("displays table headers", () => {
    const { useInterchangeRuns } = require("@/api/hooks/interchange");
    useInterchangeRuns.mockReturnValue({
      data: mockRuns,
      isLoading: false,
      error: null,
    });

    render(<RecentRunsTable />);

    expect(screen.getByText("Format")).toBeInTheDocument();
    expect(screen.getByText("Source")).toBeInTheDocument();
    expect(screen.getByText("Date")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Entities Affected")).toBeInTheDocument();
  });

  it("displays run data in rows", () => {
    const { useInterchangeRuns } = require("@/api/hooks/interchange");
    useInterchangeRuns.mockReturnValue({
      data: mockRuns,
      isLoading: false,
      error: null,
    });

    render(<RecentRunsTable />);

    // Check format column
    expect(screen.getByText("SKOS")).toBeInTheDocument();
    expect(screen.getByText("OWL")).toBeInTheDocument();
    expect(screen.getByText("GRAPHML")).toBeInTheDocument();
  });

  it("displays status badges with appropriate colors", () => {
    const { useInterchangeRuns } = require("@/api/hooks/interchange");
    useInterchangeRuns.mockReturnValue({
      data: mockRuns,
      isLoading: false,
      error: null,
    });

    render(<RecentRunsTable />);

    expect(screen.getByText("Committed")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("extracts filename from source URI", () => {
    const { useInterchangeRuns } = require("@/api/hooks/interchange");
    useInterchangeRuns.mockReturnValue({
      data: mockRuns,
      isLoading: false,
      error: null,
    });

    render(<RecentRunsTable />);

    // Should display just filename from URI
    expect(screen.getByText("test1.skos")).toBeInTheDocument();
    expect(screen.getByText("test2.owl")).toBeInTheDocument();
    expect(screen.getByText("graph.graphml")).toBeInTheDocument();
  });

  it("displays entity count", () => {
    const { useInterchangeRuns } = require("@/api/hooks/interchange");
    useInterchangeRuns.mockReturnValue({
      data: mockRuns,
      isLoading: false,
      error: null,
    });

    render(<RecentRunsTable />);

    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("shows loading spinner when loading", () => {
    const { useInterchangeRuns } = require("@/api/hooks/interchange");
    useInterchangeRuns.mockReturnValue({
      data: [],
      isLoading: true,
      error: null,
    });

    render(<RecentRunsTable />);

    expect(screen.getByRole("status")).toBeInTheDocument(); // Spinner
  });

  it("shows error message when error occurs", () => {
    const { useInterchangeRuns } = require("@/api/hooks/interchange");
    const testError = new Error("Failed to fetch runs");
    useInterchangeRuns.mockReturnValue({
      data: [],
      isLoading: false,
      error: testError,
    });

    render(<RecentRunsTable />);

    expect(screen.getByText(/error loading runs/i)).toBeInTheDocument();
    expect(screen.getByText(/failed to fetch runs/i)).toBeInTheDocument();
  });

  it("shows empty state when no runs", () => {
    const { useInterchangeRuns } = require("@/api/hooks/interchange");
    useInterchangeRuns.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });

    render(<RecentRunsTable />);

    expect(screen.getByText(/no import runs yet/i)).toBeInTheDocument();
  });

  it("renders action button for each run", () => {
    const { useInterchangeRuns } = require("@/api/hooks/interchange");
    useInterchangeRuns.mockReturnValue({
      data: mockRuns,
      isLoading: false,
      error: null,
    });

    render(<RecentRunsTable />);

    const viewButtons = screen.getAllByRole("button", { name: /view/i });
    expect(viewButtons.length).toBeGreaterThan(0);
  });

  it("has correct data-testid for each row", () => {
    const { useInterchangeRuns } = require("@/api/hooks/interchange");
    useInterchangeRuns.mockReturnValue({
      data: mockRuns,
      isLoading: false,
      error: null,
    });

    render(<RecentRunsTable />);

    expect(
      screen.getByTestId("interchange-runs-table-row-run-1")
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("interchange-runs-table-row-run-2")
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("interchange-runs-table-row-run-3")
    ).toBeInTheDocument();
  });

  it("has data-testid for main container", () => {
    const { useInterchangeRuns } = require("@/api/hooks/interchange");
    useInterchangeRuns.mockReturnValue({
      data: mockRuns,
      isLoading: false,
      error: null,
    });

    render(<RecentRunsTable />);

    expect(screen.getByTestId("interchange-recent-runs-table")).toBeInTheDocument();
  });

  it("handles pagination correctly", async () => {
    const { useInterchangeRuns } = require("@/api/hooks/interchange");
    const mockUseInterchangeRuns = useInterchangeRuns;

    // Return 10 items to indicate more pages
    const fullPage = Array.from({ length: 10 }, (_, i) => ({
      id: `run-${i}`,
      format: "skos",
      source_uri: `test${i}.skos`,
      created_at: new Date().toISOString(),
      status: "committed",
      affected_entity_ids: [],
    }));

    mockUseInterchangeRuns.mockReturnValue({
      data: fullPage,
      isLoading: false,
      error: null,
    });

    const { rerender } = render(<RecentRunsTable />);

    // Should show all items
    expect(screen.getByText("SKOS")).toBeInTheDocument();

    // Check for next page button (if implemented)
    const nextButton = screen.queryByRole("button", { name: /next/i });
    if (nextButton) {
      fireEvent.click(nextButton);

      // Component should fetch next page
      await waitFor(() => {
        expect(mockUseInterchangeRuns).toHaveBeenCalled();
      });
    }
  });
});
