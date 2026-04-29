import { rest } from "msw";

/**
 * Centralized MSW handlers for common API endpoints used in integration tests.
 * These handlers mock the NEW back-end API endpoints (taxonomies, schemes, classes, properties).
 * All handlers use relative URLs that work with the configured baseURL from API_CONFIG.
 */

// Helper to get base URL - matches the logic in src/api/config.ts
const getBaseURL = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  return "http://localhost:8100";
};

export const handlers = [
  // Taxonomies endpoints
  rest.get("/api/taxonomies", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: [
          {
            id: "taxonomy-1",
            title: "Taxonomy 1",
            node_type: "taxonomy",
            created_at: new Date().toISOString(),
          },
        ],
      }),
    );
  }),

  rest.get("/api/taxonomies/:id", (req, res, ctx) => {
    const { id } = req.params as { id: string };
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          id,
          title: `Taxonomy ${id}`,
          node_type: "taxonomy",
          created_at: new Date().toISOString(),
        },
      }),
    );
  }),

  rest.post("/api/taxonomies", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(201),
      ctx.json({
        data: { ...body, id: "new-taxonomy", node_type: "taxonomy" },
      }),
    );
  }),

  rest.put("/api/taxonomies/:id", async (req, res, ctx) => {
    const { id } = req.params as { id: string };
    const body = await req.json();
    if (!body || typeof body.title !== "string" || body.title.trim() === "") {
      return res(
        ctx.status(400),
        ctx.json({ message: "Validation failed: title is required" }),
      );
    }
    return res(
      ctx.status(200),
      ctx.json({
        data: { ...body, id, node_type: "taxonomy" },
      }),
    );
  }),

  // Schemes endpoints
  rest.get("/api/schemes", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: [
          {
            id: "scheme-1",
            title: "Scheme 1",
            node_type: "scheme",
            created_at: new Date().toISOString(),
          },
        ],
      }),
    );
  }),

  rest.get("/api/schemes/:id", (req, res, ctx) => {
    const { id } = req.params as { id: string };
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          id,
          title: `Scheme ${id}`,
          node_type: "scheme",
          created_at: new Date().toISOString(),
        },
      }),
    );
  }),

  rest.post("/api/schemes", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(201),
      ctx.json({
        data: { ...body, id: "new-scheme", node_type: "scheme" },
      }),
    );
  }),

  rest.put("/api/schemes/:id", async (req, res, ctx) => {
    const { id } = req.params as { id: string };
    const body = await req.json();
    if (!body || typeof body.title !== "string" || body.title.trim() === "") {
      return res(
        ctx.status(400),
        ctx.json({ message: "Validation failed: title is required" }),
      );
    }
    return res(
      ctx.status(200),
      ctx.json({
        data: { ...body, id, node_type: "scheme" },
      }),
    );
  }),

  // Classes endpoints
  rest.get("/api/classes", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: [
          {
            id: "class-1",
            title: "Class 1",
            node_type: "class",
            created_at: new Date().toISOString(),
          },
        ],
      }),
    );
  }),

  rest.get("/api/classes/:id", (req, res, ctx) => {
    const { id } = req.params as { id: string };
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          id,
          title: `Class ${id}`,
          node_type: "class",
          created_at: new Date().toISOString(),
        },
      }),
    );
  }),

  rest.post("/api/classes", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(201),
      ctx.json({
        data: { ...body, id: "new-class", node_type: "class" },
      }),
    );
  }),

  rest.put("/api/classes/:id", async (req, res, ctx) => {
    const { id } = req.params as { id: string };
    const body = await req.json();
    if (!body || typeof body.title !== "string" || body.title.trim() === "") {
      return res(
        ctx.status(400),
        ctx.json({ message: "Validation failed: title is required" }),
      );
    }
    return res(
      ctx.status(200),
      ctx.json({
        data: { ...body, id, node_type: "class" },
      }),
    );
  }),

  // Properties endpoints (replaces legacy predicates)
  rest.get("/api/properties", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: [
          {
            id: "prop-1",
            title: "Property 1",
            property_type: "object_property",
          },
        ],
      }),
    );
  }),

  rest.get("/api/properties/:id", (req, res, ctx) => {
    const { id } = req.params as { id: string };
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          id,
          title: `Property ${id}`,
          property_type: "object_property",
        },
      }),
    );
  }),

  rest.post("/api/properties", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(201),
      ctx.json({
        data: { ...body, id: "new-property", property_type: "object_property" },
      }),
    );
  }),

  rest.put("/api/properties/:id", async (req, res, ctx) => {
    const { id } = req.params as { id: string };
    const body = await req.json();
    if (!body || typeof body.title !== "string" || body.title.trim() === "") {
      return res(
        ctx.status(400),
        ctx.json({ message: "Validation failed: title is required" }),
      );
    }
    return res(
      ctx.status(200),
      ctx.json({
        data: { ...body, id, property_type: "object_property" },
      }),
    );
  }),

  // Relationships endpoints
  rest.get("/api/relationships", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: [
          {
            id: "rel-1",
            source_node_id: "node-1",
            target_node_id: "node-2",
            property_id: "prop-1",
          },
        ],
      }),
    );
  }),

  rest.get("/api/relationships/:id", (req, res, ctx) => {
    const { id } = req.params as { id: string };
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          id,
          source_node_id: "node-1",
          target_node_id: "node-2",
          property_id: "prop-1",
        },
      }),
    );
  }),

  rest.post("/api/relationships", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(201),
      ctx.json({
        data: { ...body, id: "new-relationship" },
      }),
    );
  }),

  rest.put("/api/relationships/:id", async (req, res, ctx) => {
    const { id } = req.params as { id: string };
    const body = await req.json();
    return res(
      ctx.status(200),
      ctx.json({
        data: { ...body, id },
      }),
    );
  }),

  // Graph endpoints
  rest.get("/api/graph", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          nodes: [],
          edges: [],
        },
      }),
    );
  }),

  rest.post("/api/graph", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          nodes: [],
          edges: [],
        },
      }),
    );
  }),

  // Datasets endpoints
  rest.get("/api/datasets", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: [],
      }),
    );
  }),

  // Schema endpoints
  rest.get("/api/schema", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: null,
      }),
    );
  }),

  // Change events endpoints
  rest.get("/api/change_events", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: [],
      }),
    );
  }),

  // RAG endpoints
  rest.post("/api/rag/extract", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          request_id: "rag-req-1",
          status: "completed",
        },
      }),
    );
  }),

  rest.get("/api/rag/metrics/:requestId", (req, res, ctx) => {
    const { requestId } = req.params as { requestId: string };
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          request_id: requestId,
          metrics: {},
        },
      }),
    );
  }),

  rest.get("/api/rag/trace/:requestId", (req, res, ctx) => {
    const { requestId } = req.params as { requestId: string };
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          request_id: requestId,
          trace: [],
        },
      }),
    );
  }),

  // RAG Experiments endpoints
  rest.get("/api/rag-experiments/paragraphs", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: [],
      }),
    );
  }),

  rest.post("/api/rag-experiments/run", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          run_id: "exp-run-1",
          status: "completed",
        },
      }),
    );
  }),

  // Pipeline configuration endpoints
  rest.get("/api/pipeline-flavors", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: [],
      }),
    );
  }),

  rest.get("/api/llm", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: null,
      }),
    );
  }),

  rest.post("/api/llm", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(201),
      ctx.json({
        data: { ...body, id: "new-llm-config" },
      }),
    );
  }),

  // LLM Traceability endpoints
  rest.get("/api/llm/health", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          status: "healthy",
        },
      }),
    );
  }),

  rest.get("/api/llm/record-selection", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: [],
      }),
    );
  }),

  rest.get("/api/llm/execution-analytics", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {},
      }),
    );
  }),

  rest.get("/api/llm/execution-history", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: [],
      }),
    );
  }),

  // NLP endpoints
  rest.post("/api/nlp_analysis", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          analysis_id: "nlp-1",
          results: {},
        },
      }),
    );
  }),

  // Reference endpoints
  rest.get("/api/reference", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: [],
      }),
    );
  }),

  rest.get("/api/reference/ref-db", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: [],
      }),
    );
  }),

  rest.get("/api/reference/ref-db/filter/statistics", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {},
      }),
    );
  }),

  rest.get("/api/reference/ref-db/nodes", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: [],
      }),
    );
  }),
];
