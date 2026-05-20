import { describe, it, expect } from "vitest";
import { validateEdgeEndpoints } from "../GraphCanvas";
import type { GraphNode, GraphEdge } from "@/api/hooks/graph";

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

      const edges: GraphEdge[] = [
        { id: "edge-1", source: "node-missing", target: "node-2" },
      ];

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

      const edges: GraphEdge[] = [
        { id: "edge-1", source: "node-1", target: "node-missing" },
      ];

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

      const edges: GraphEdge[] = [
        { id: "edge-1", source: "node-1", target: "node-2" },
      ];

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

      const edges: GraphEdge[] = [
        { id: "edge-xy", source: "node-missing-x", target: "node-a" },
      ];

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
});
