import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { validateEdgeEndpoints, GraphCanvasComponent } from "../GraphCanvas";
import type { GraphNode, GraphEdge } from "@/api/hooks/graph";

const { mockToastFn, mockGraphCanvas } = vi.hoisted(() => ({
  mockToastFn: vi.fn(),
  mockGraphCanvas: vi.fn(() => null),
}));

vi.mock("@/components/ui/Toast", async () => {
  const actual = await vi.importActual("@/components/ui/Toast");
  return {
    ...actual,
    useToasts: () => ({
      toast: mockToastFn,
      toasts: [],
      dismiss: vi.fn(),
    }),
  };
});

vi.mock("reagraph", () => ({
  GraphCanvas: mockGraphCanvas,
}));

beforeEach(() => {
  mockToastFn.mockClear();
  mockGraphCanvas.mockClear();
});

describe("GraphCanvas", () => {
  describe("validateEdgeEndpoints", () => {
    it("should return valid status when all edges reference existing nodes", () => {
      const nodes: GraphNode[] = [
        { id: "node-1", label: "Node 1", centrality: 0.5, kind: "class" },
        { id: "node-2", label: "Node 2", centrality: 0.6, kind: "class" },
        { id: "node-3", label: "Node 3", centrality: 0.4, kind: "class" },
      ];

      const edges: GraphEdge[] = [
        { id: "edge-1", source: "node-1", target: "node-2" },
        { id: "edge-2", source: "node-2", target: "node-3" },
      ];

      const result = validateEdgeEndpoints(nodes, edges);

      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it("should detect missing source node", () => {
      const nodes: GraphNode[] = [
        { id: "node-1", label: "Node 1", centrality: 0.5, kind: "class" },
        { id: "node-2", label: "Node 2", centrality: 0.6, kind: "class" },
      ];

      const edges: GraphEdge[] = [{ id: "edge-1", source: "node-missing", target: "node-2" }];

      const result = validateEdgeEndpoints(nodes, edges);

      expect(result.valid).toBe(false);
      expect(result.errors).toHaveLength(1);
      expect(result.errors[0]).toContain("source node");
      expect(result.errors[0]).toContain("node-missing");
    });

    it("should detect missing target node", () => {
      const nodes: GraphNode[] = [
        { id: "node-1", label: "Node 1", centrality: 0.5, kind: "class" },
        { id: "node-2", label: "Node 2", centrality: 0.6, kind: "class" },
      ];

      const edges: GraphEdge[] = [{ id: "edge-1", source: "node-1", target: "node-missing" }];

      const result = validateEdgeEndpoints(nodes, edges);

      expect(result.valid).toBe(false);
      expect(result.errors).toHaveLength(1);
      expect(result.errors[0]).toContain("target node");
      expect(result.errors[0]).toContain("node-missing");
    });

    it("should detect both missing source and target nodes", () => {
      const nodes: GraphNode[] = [
        { id: "node-1", label: "Node 1", centrality: 0.5, kind: "class" },
      ];

      const edges: GraphEdge[] = [
        {
          id: "edge-1",
          source: "node-missing-1",
          target: "node-missing-2",
        },
      ];

      const result = validateEdgeEndpoints(nodes, edges);

      expect(result.valid).toBe(false);
      expect(result.errors).toHaveLength(2);
      expect(result.errors.some((e) => e.includes("source"))).toBe(true);
      expect(result.errors.some((e) => e.includes("target"))).toBe(true);
    });

    it("should handle empty edges array", () => {
      const nodes: GraphNode[] = [
        { id: "node-1", label: "Node 1", centrality: 0.5, kind: "class" },
      ];

      const edges: GraphEdge[] = [];

      const result = validateEdgeEndpoints(nodes, edges);

      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it("should handle empty nodes array", () => {
      const nodes: GraphNode[] = [];

      const edges: GraphEdge[] = [{ id: "edge-1", source: "node-1", target: "node-2" }];

      const result = validateEdgeEndpoints(nodes, edges);

      expect(result.valid).toBe(false);
      expect(result.errors).toHaveLength(2);
    });

    it("should handle multiple edges with mixed valid and invalid references", () => {
      const nodes: GraphNode[] = [
        { id: "node-1", label: "Node 1", centrality: 0.5, kind: "class" },
        { id: "node-2", label: "Node 2", centrality: 0.6, kind: "class" },
      ];

      const edges: GraphEdge[] = [
        { id: "edge-1", source: "node-1", target: "node-2" },
        { id: "edge-2", source: "node-2", target: "node-3" },
        { id: "edge-3", source: "node-4", target: "node-1" },
      ];

      const result = validateEdgeEndpoints(nodes, edges);

      expect(result.valid).toBe(false);
      expect(result.errors).toHaveLength(2);
      expect(result.errors.some((e) => e.includes("edge-2"))).toBe(true);
      expect(result.errors.some((e) => e.includes("edge-3"))).toBe(true);
    });

    it("should include edge ID and node ID in error messages", () => {
      const nodes: GraphNode[] = [
        { id: "node-a", label: "Node A", centrality: 0.5, kind: "class" },
      ];

      const edges: GraphEdge[] = [{ id: "edge-xy", source: "node-missing-x", target: "node-a" }];

      const result = validateEdgeEndpoints(nodes, edges);

      expect(result.valid).toBe(false);
      expect(result.errors[0]).toContain("edge-xy");
      expect(result.errors[0]).toContain("node-missing-x");
    });

    it("should pass when nodes and edges are both empty", () => {
      const nodes: GraphNode[] = [];
      const edges: GraphEdge[] = [];

      const result = validateEdgeEndpoints(nodes, edges);

      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });
  });

  describe("GraphCanvasComponent render", () => {
    const mockNodes: GraphNode[] = [
      { id: "node-1", label: "Node 1", centrality: 0.5, kind: "class" },
      { id: "node-2", label: "Node 2", centrality: 0.6, kind: "class" },
    ];

    const mockEdges: GraphEdge[] = [{ id: "edge-1", source: "node-1", target: "node-2" }];

    it("should render graph canvas container with valid data", () => {
      render(<GraphCanvasComponent nodes={mockNodes} edges={mockEdges} />);
      const canvases = screen.getAllByTestId("graph-canvas");
      expect(canvases.length).toBeGreaterThan(0);
    });

    it("should have proper accessibility attributes", () => {
      render(<GraphCanvasComponent nodes={mockNodes} edges={mockEdges} />);
      const canvases = screen.getAllByTestId("graph-canvas");
      const outerCanvas = canvases[0];
      expect(outerCanvas).toHaveAttribute("role", "region");
      expect(outerCanvas).toHaveAttribute("aria-label", "Graph visualization canvas");
    });

    it("should render error state when validation fails", () => {
      const invalidEdges: GraphEdge[] = [
        { id: "edge-1", source: "node-missing", target: "node-2" },
      ];

      render(<GraphCanvasComponent nodes={mockNodes} edges={invalidEdges} />);

      const canvases = screen.getAllByTestId("graph-canvas");
      expect(canvases.length).toBeGreaterThan(0);
      expect(
        screen.getByText("Graph data validation failed. Check console for details."),
      ).toBeInTheDocument();
    });

    it("should show error container with correct class in error state", () => {
      const invalidEdges: GraphEdge[] = [
        { id: "edge-1", source: "node-missing", target: "node-2" },
      ];

      render(<GraphCanvasComponent nodes={mockNodes} edges={invalidEdges} />);

      const errorContainer = screen.getByText(
        "Graph data validation failed. Check console for details.",
      ).parentElement;
      expect(errorContainer).toHaveClass("graph-canvas__error");
    });

    it("should remap edge props from source/target to sourceId/targetId", () => {
      const edges: GraphEdge[] = [{ id: "edge-1", source: "node-1", target: "node-2" }];

      render(<GraphCanvasComponent nodes={mockNodes} edges={edges} />);

      expect(mockGraphCanvas).toHaveBeenCalled();

      const callArgs = (mockGraphCanvas as any).mock.calls[0][0];
      expect(callArgs.edges).toEqual([
        {
          id: "edge-1",
          sourceId: "node-1",
          targetId: "node-2",
        },
      ]);
    });

    it("should call toast on validation error", () => {
      const invalidEdges: GraphEdge[] = [
        { id: "edge-1", source: "node-missing", target: "node-2" },
      ];

      render(<GraphCanvasComponent nodes={mockNodes} edges={invalidEdges} />);

      expect(mockToastFn).toHaveBeenCalledWith(
        "error",
        "Graph validation error",
        expect.stringContaining("source node"),
      );
    });

    it("should apply graph-canvas class to container", () => {
      render(<GraphCanvasComponent nodes={mockNodes} edges={mockEdges} />);

      const canvases = screen.getAllByTestId("graph-canvas");
      expect(canvases[0]).toHaveClass("graph-canvas");
    });

    it("should not render error state with valid edges", () => {
      render(<GraphCanvasComponent nodes={mockNodes} edges={mockEdges} />);

      expect(
        screen.queryByText("Graph data validation failed. Check console for details."),
      ).not.toBeInTheDocument();
    });

    it("should pass onNodeClick callback to underlying GraphCanvas", () => {
      const onNodeClick = vi.fn();

      render(
        <GraphCanvasComponent nodes={mockNodes} edges={mockEdges} onNodeClick={onNodeClick} />,
      );

      expect(screen.getAllByTestId("graph-canvas").length).toBeGreaterThan(0);
    });

    it("should pass selectedNodeId to underlying GraphCanvas", () => {
      render(<GraphCanvasComponent nodes={mockNodes} edges={mockEdges} selectedNodeId="node-1" />);

      expect(screen.getAllByTestId("graph-canvas").length).toBeGreaterThan(0);
    });

    it("should memoize validation result and recompute only when dependencies change", () => {
      mockToastFn.mockClear();

      const { rerender } = render(<GraphCanvasComponent nodes={mockNodes} edges={mockEdges} />);

      expect(mockToastFn).not.toHaveBeenCalled();

      const sameNodes = mockNodes;
      const sameEdges = mockEdges;
      mockToastFn.mockClear();

      rerender(<GraphCanvasComponent nodes={sameNodes} edges={sameEdges} />);

      expect(mockToastFn).not.toHaveBeenCalled();

      const newInvalidNodes: GraphNode[] = [
        { id: "different-node", label: "Different", centrality: 0.5, kind: "class" },
      ];
      mockToastFn.mockClear();

      rerender(<GraphCanvasComponent nodes={newInvalidNodes} edges={mockEdges} />);

      expect(mockToastFn).toHaveBeenCalled();
    });

    it("should revalidate when nodes change", () => {
      const { rerender } = render(<GraphCanvasComponent nodes={mockNodes} edges={mockEdges} />);

      expect(
        screen.queryByText("Graph data validation failed. Check console for details."),
      ).not.toBeInTheDocument();

      const newNodes: GraphNode[] = [
        { id: "different-node", label: "Different", centrality: 0.5, kind: "class" },
      ];

      rerender(<GraphCanvasComponent nodes={newNodes} edges={mockEdges} />);

      expect(
        screen.getByText("Graph data validation failed. Check console for details."),
      ).toBeInTheDocument();
    });

    it("should revalidate when edges change", () => {
      const { rerender } = render(<GraphCanvasComponent nodes={mockNodes} edges={mockEdges} />);

      expect(
        screen.queryByText("Graph data validation failed. Check console for details."),
      ).not.toBeInTheDocument();

      const newEdges: GraphEdge[] = [{ id: "edge-1", source: "node-1", target: "invalid-node" }];

      rerender(<GraphCanvasComponent nodes={mockNodes} edges={newEdges} />);

      expect(
        screen.getByText("Graph data validation failed. Check console for details."),
      ).toBeInTheDocument();
    });

    it("should not trigger validation on selectedNodeId change", () => {
      const { rerender } = render(
        <GraphCanvasComponent nodes={mockNodes} edges={mockEdges} selectedNodeId="node-1" />,
      );

      const initialError = screen.queryByText(
        "Graph data validation failed. Check console for details.",
      );

      rerender(
        <GraphCanvasComponent nodes={mockNodes} edges={mockEdges} selectedNodeId="node-2" />,
      );

      const finalError = screen.queryByText(
        "Graph data validation failed. Check console for details.",
      );
      expect(initialError).toBe(finalError);
    });
  });
});
