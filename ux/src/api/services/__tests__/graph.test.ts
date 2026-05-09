/**
 * Unit tests for GraphService using MSW to mock HTTP responses.
 * Tests verify graph building, metrics, path finding, and SPARQL queries.
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { graphService } from "../graph";
import {
  createKnowledgeGraph,
  createGraphMetrics,
  createPathResult,
  createSPARQLRequest,
  createSPARQLResponse,
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
        nodes_count: 150,
        edges_count: 300,
      });

      server.use(
        rest.post("*/api/graph/build", (req, res, ctx) => res(ctx.json(mockGraph)))
      );

      const result = await graphService.buildGraph();

      expect(result).toEqual(mockGraph);
      expect(result.nodes_count).toBe(150);
      expect(result.edges_count).toBe(300);
    });

    it("throws ApiError on 500 from buildGraph", async () => {
      server.use(
        rest.post("*/api/graph/build", (req, res, ctx) =>
          res(
        ctx.status(500),
        ctx.json({
              detail: "Graph build failed",
            })
      )
        )
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

      server.use(
        rest.get("*/api/graph/metrics", (req, res, ctx) => res(ctx.json(mockMetrics)))
      );

      const result = await graphService.getMetrics();

      expect(result).toEqual(mockMetrics);
      expect(result.algorithm).toBe("pagerank");
      expect(result.density).toBe(0.25);
    });

    it("returns graph metrics with algorithm parameter", async () => {
      const mockMetrics = createGraphMetrics({
        algorithm: "betweenness_centrality",
      });

      server.use(
        rest.get("*/api/graph/metrics", (req, res, ctx) => res(ctx.json(mockMetrics)))
      );

      const result = await graphService.getMetrics("betweenness_centrality");

      expect(result.algorithm).toBe("betweenness_centrality");
    });

    it("throws ApiError on 400 from getMetrics", async () => {
      server.use(
        rest.get("*/api/graph/metrics", (req, res, ctx) =>
          res(
        ctx.status(400),
        ctx.json({
              detail: "Invalid algorithm",
            })
      )
        )
      );

      await expect(graphService.getMetrics("invalid")).rejects.toMatchObject({
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
        rest.get("*/api/graph/paths/shortest", (req, res, ctx) =>
          res(ctx.json(mockPath))
        )
      );

      const result = await graphService.getShortestPath("node-1", "node-10");

      expect(result).toEqual(mockPath);
      expect(result.distance).toBe(4);
      expect(result.path).toHaveLength(4);
    });

    it("throws ApiError on 404 when path not found", async () => {
      server.use(
        rest.get("*/api/graph/paths/shortest", (req, res, ctx) =>
          res(
        ctx.status(404),
        ctx.json({
              detail: "No path found between nodes",
            })
      )
        )
      );

      await expect(
        graphService.getShortestPath("node-1", "node-999")
      ).rejects.toMatchObject({
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

      server.use(
        rest.post("*/api/graph/sparql", (req, res, ctx) =>
          res(ctx.json(mockResults))
        )
      );

      const result = await graphService.sparqlQuery(sparqlRequest.query);

      expect(result).toEqual(mockResults);
      expect(result.results).toHaveLength(3);
      expect(result.execution_time_ms).toBe(250);
    });

    it("throws ApiError on 400 for invalid SPARQL query", async () => {
      server.use(
        rest.post("*/api/graph/sparql", (req, res, ctx) =>
          res(
        ctx.status(400),
        ctx.json({
              detail: "Invalid SPARQL query syntax",
            })
      )
        )
      );

      await expect(
        graphService.sparqlQuery("INVALID QUERY")
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
        detail: expect.stringContaining("Invalid"),
      });
    });

    it("throws ApiError on 500 for query execution error", async () => {
      server.use(
        rest.post("*/api/graph/sparql", (req, res, ctx) =>
          res(
        ctx.status(500),
        ctx.json({
              detail: "Query execution timeout",
            })
      )
        )
      );

      await expect(
        graphService.sparqlQuery("SELECT * WHERE { ?s ?p ?o }")
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });
});
