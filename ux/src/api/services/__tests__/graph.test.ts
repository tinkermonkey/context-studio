/**
 * Unit tests for GraphService using MSW to mock HTTP responses.
 * Tests verify graph building, metrics, path finding, and SPARQL queries.
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { graphService } from "../graph";
import {
  createKnowledgeGraph,
  createGraphMetrics,
  createPathResult,
  createSPARQLRequest,
  createSPARQLResponse,
  createSubgraphData,
} from "./fixtures/graph.fixtures";

const server = setupServer();

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});

describe("GraphService", () => {
  describe("buildGraph", () => {
    it("builds graph and returns KnowledgeGraphResponse", async () => {
      const mockGraph = createKnowledgeGraph({
        node_count: 150,
        edge_count: 300,
      });

      server.use(http.post("*/api/graph/build", () => HttpResponse.json(mockGraph)));

      const result = await graphService.buildGraph();

      expect(result).toEqual(mockGraph);
      expect(result.node_count).toBe(150);
      expect(result.edge_count).toBe(300);
    });

    it("throws ApiError on 500 from buildGraph", async () => {
      server.use(
        http.post("*/api/graph/build", () =>
          HttpResponse.json({
              detail: "Graph build failed",
            }, { status: 500 }),
        ),
      );

      await expect(graphService.buildGraph()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("getMetrics", () => {
    it("returns graph metrics without algorithm parameter", async () => {
      const mockMetrics = createGraphMetrics();

      server.use(http.get("*/api/graph/metrics", () => HttpResponse.json(mockMetrics)));

      const result = await graphService.getMetrics();

      expect(result).toEqual(mockMetrics);
      expect(result.algorithm).toBe("pagerank");
      expect(result.density).toBe(0.25);
    });

    it("returns graph metrics with algorithm parameter", async () => {
      const mockMetrics = createGraphMetrics({
        algorithm: "betweenness_centrality",
      });

      server.use(http.get("*/api/graph/metrics", () => HttpResponse.json(mockMetrics)));

      const result = await graphService.getMetrics("betweenness_centrality");

      expect(result.algorithm).toBe("betweenness_centrality");
    });

    it("throws ApiError on 400 from getMetrics", async () => {
      server.use(
        http.get("*/api/graph/metrics", () =>
          HttpResponse.json({
              detail: "Invalid algorithm",
            }, { status: 400 }),
        ),
      );

      await expect(graphService.getMetrics("invalid")).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });
  });

  describe("getSubgraph", () => {
    it("returns subgraph containing specified nodes and connecting edges", async () => {
      const mockSubgraph = createSubgraphData({
        nodes: ["node-1", "node-2"],
        edges: [["node-1", "node-2"]],
      });

      server.use(
        http.get("*/api/graph/subgraph", ({ request }) => {
          const url = new URL(request.url);
          const nodes = url.searchParams.get("nodes");
          if (nodes === "node-1,node-2") {
            return HttpResponse.json(mockSubgraph);
          }
          return HttpResponse.json({ detail: "Invalid nodes" }, { status: 400 });
        }),
      );

      const result = await graphService.getSubgraph(["node-1", "node-2"]);

      expect(result.nodes).toHaveLength(2);
      expect(result.nodes[0]).toBe("node-1");
    });

    it("throws ApiError with 400 on getSubgraph with empty node list", async () => {
      server.use(
        http.get("*/api/graph/subgraph", () =>
          HttpResponse.json({
              detail: "At least one node ID is required",
            }, { status: 400 }),
        ),
      );

      await expect(graphService.getSubgraph([])).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });
  });

  describe("getShortestPath", () => {
    it("returns shortest path between two nodes", async () => {
      const mockPath = createPathResult({
        source_id: "node-1",
        target_id: "node-10",
        distance: 4,
      });

      server.use(
        http.get("*/api/graph/paths/shortest", () => HttpResponse.json(mockPath)),
      );

      const result = await graphService.getShortestPath("node-1", "node-10");

      expect(result).toEqual(mockPath);
      expect(result.distance).toBe(4);
      expect(result.nodes).toHaveLength(4);
    });

    it("throws ApiError on 404 when path not found", async () => {
      server.use(
        http.get("*/api/graph/paths/shortest", () =>
          HttpResponse.json({
              detail: "No path found between nodes",
            }, { status: 404 }),
        ),
      );

      await expect(graphService.getShortestPath("node-1", "node-999")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("sparqlQuery", () => {
    it("executes SPARQL query and returns results", async () => {
      const sparqlRequest = createSPARQLRequest();
      const mockResults = createSPARQLResponse({
        results: [{ x: "node-1" }, { x: "node-2" }, { x: "node-3" }],
      });

      server.use(http.post("*/api/graph/sparql", () => HttpResponse.json(mockResults)));

      const result = await graphService.sparqlQuery(sparqlRequest.query);

      expect(result).toEqual(mockResults);
      expect(result.results).toHaveLength(3);
      expect(result.triple_count).toBe(1000);
    });

    it("throws ApiError on 400 for invalid SPARQL query", async () => {
      server.use(
        http.post("*/api/graph/sparql", () =>
          HttpResponse.json({
              detail: "Invalid SPARQL query syntax",
            }, { status: 400 }),
        ),
      );

      await expect(graphService.sparqlQuery("INVALID QUERY")).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
        detail: expect.stringContaining("Invalid"),
      });
    });

    it("throws ApiError on 500 for query execution error", async () => {
      server.use(
        http.post("*/api/graph/sparql", () =>
          HttpResponse.json({
              detail: "Query execution timeout",
            }, { status: 500 }),
        ),
      );

      await expect(graphService.sparqlQuery("SELECT * WHERE { ?s ?p ?o }")).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });
});
