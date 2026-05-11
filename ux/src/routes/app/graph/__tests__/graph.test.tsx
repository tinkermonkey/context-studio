import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/api/utils/queryClient";
import { GraphPage } from "../index";
import * as graphHooks from "@/api/hooks/graph";

vi.mock("@/api/hooks/graph");

describe("Graph Page", () => {
  const mockGraphData = {
    nodes: [
      { id: "node-1", label: "Node 1", centrality: 0.5 },
      { id: "node-2", label: "Node 2", centrality: 0.3 },
    ],
    edges: [
      { id: "edge-1", source: "node-1", target: "node-2" },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Mock useGraphMetrics for all tests
    vi.mocked(graphHooks.useGraphMetrics).mockReturnValue({
      data: {
        centrality: { "node-1": 0.8 },
        degree_distribution: { "node-1": 2 },
        communities: [],
        average_degree: 1,
        algorithm: "louvain",
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);
  });

  describe("page structure", () => {
    it("renders graph page container", () => {
      vi.mocked(graphHooks.useGraphVisualization).mockReturnValue({
        data: mockGraphData,
        isPending: false,
        error: null,
        mutate: vi.fn(),
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <GraphPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("graph-page")).toBeInTheDocument();
    });
  });

  describe("loading state", () => {
    it("renders page during loading", () => {
      vi.mocked(graphHooks.useGraphVisualization).mockReturnValue({
        data: null,
        isPending: true,
        error: null,
        mutate: vi.fn(),
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <GraphPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("graph-page")).toBeInTheDocument();
    });
  });

  describe("empty state", () => {
    it("renders empty state when no data", () => {
      vi.mocked(graphHooks.useGraphVisualization).mockReturnValue({
        data: { nodes: [], edges: [] },
        isPending: false,
        error: null,
        mutate: vi.fn(),
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <GraphPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("graph-page")).toBeInTheDocument();
    });
  });

  describe("populated state", () => {
    it("renders graph canvas with data", () => {
      vi.mocked(graphHooks.useGraphVisualization).mockReturnValue({
        data: mockGraphData,
        isPending: false,
        error: null,
        mutate: vi.fn(),
      } as any);

      vi.mocked(graphHooks.useGraphMetrics).mockReturnValue({
        data: {
          centrality: { "node-1": 0.8 },
          degree_distribution: { "node-1": 2 },
          communities: [],
          average_degree: 1,
          algorithm: "louvain",
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <GraphPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("graph-canvas")).toBeInTheDocument();
    });

    it("renders metrics panel when data available", () => {
      vi.mocked(graphHooks.useGraphVisualization).mockReturnValue({
        data: mockGraphData,
        isPending: false,
        error: null,
        mutate: vi.fn(),
      } as any);

      vi.mocked(graphHooks.useGraphMetrics).mockReturnValue({
        data: {
          centrality: { "node-1": 0.8 },
          degree_distribution: { "node-1": 2 },
          communities: [],
          average_degree: 1,
          algorithm: "louvain",
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <GraphPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("graph-metrics-panel")).toBeInTheDocument();
    });
  });

  describe("selectors present", () => {
    it("has graph-page data-testid", () => {
      vi.mocked(graphHooks.useGraphVisualization).mockReturnValue({
        data: mockGraphData,
        isPending: false,
        error: null,
        mutate: vi.fn(),
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <GraphPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("graph-page")).toBeInTheDocument();
    });

    it("has graph-canvas data-testid when rendered", () => {
      vi.mocked(graphHooks.useGraphVisualization).mockReturnValue({
        data: mockGraphData,
        isPending: false,
        error: null,
        mutate: vi.fn(),
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <GraphPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("graph-canvas")).toBeInTheDocument();
    });

    it("has graph-metrics-panel data-testid", () => {
      vi.mocked(graphHooks.useGraphVisualization).mockReturnValue({
        data: mockGraphData,
        isPending: false,
        error: null,
        mutate: vi.fn(),
      } as any);

      vi.mocked(graphHooks.useGraphMetrics).mockReturnValue({
        data: {
          centrality: { "node-1": 0.8 },
          degree_distribution: { "node-1": 2 },
          communities: [],
          average_degree: 1,
          algorithm: "louvain",
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <GraphPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("graph-metrics-panel")).toBeInTheDocument();
    });
  });
});
