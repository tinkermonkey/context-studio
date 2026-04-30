import { rest } from "msw";

/**
 * Centralized MSW handlers for common API endpoints used in integration tests.
 * These handlers mock the NEW back-end API endpoints (taxonomies, schemes, classes, properties).
 * All handlers use relative URLs that work with the configured baseURL from API_CONFIG.
 */

export const handlers = [
  // Taxonomies endpoints
  rest.get("/api/taxonomies", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        items: [
          {
            id: "taxonomy-1",
            title: "Taxonomy 1",
            version: 1,
            created_at: new Date().toISOString(),
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    );
  }),

  rest.get("/api/taxonomies/:id", (req, res, ctx) => {
    const { id } = req.params as { id: string };
    return res(
      ctx.status(200),
      ctx.json({
        id,
        title: `Taxonomy ${id}`,
        version: 1,
        created_at: new Date().toISOString(),
      }),
    );
  }),

  rest.post("/api/taxonomies", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(201),
      ctx.json({
        ...body,
        id: "new-taxonomy",
        version: 1,
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
        ...body,
        id,
        version: 1,
      }),
    );
  }),

  rest.delete("/api/taxonomies/:id", (req, res, ctx) => {
    return res(ctx.status(204));
  }),

  // Schemes endpoints
  rest.get("/api/schemes", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        items: [
          {
            id: "scheme-1",
            title: "Scheme 1",
            taxonomy_id: "taxonomy-1",
            version: 1,
            created_at: new Date().toISOString(),
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    );
  }),

  rest.get("/api/schemes/:id", (req, res, ctx) => {
    const { id } = req.params as { id: string };
    return res(
      ctx.status(200),
      ctx.json({
        id,
        title: `Scheme ${id}`,
        taxonomy_id: "taxonomy-1",
        version: 1,
        created_at: new Date().toISOString(),
      }),
    );
  }),

  rest.post("/api/schemes", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(201),
      ctx.json({
        ...body,
        id: "new-scheme",
        version: 1,
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
        ...body,
        id,
        version: 1,
      }),
    );
  }),

  rest.delete("/api/schemes/:id", (req, res, ctx) => {
    return res(ctx.status(204));
  }),

  // Classes endpoints
  rest.get("/api/classes", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        items: [
          {
            id: "class-1",
            title: "Class 1",
            concept_scheme_id: "scheme-1",
            taxonomy_id: "taxonomy-1",
            version: 1,
            created_at: new Date().toISOString(),
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    );
  }),

  rest.get("/api/classes/:id", (req, res, ctx) => {
    const { id } = req.params as { id: string };
    return res(
      ctx.status(200),
      ctx.json({
        id,
        title: `Class ${id}`,
        concept_scheme_id: "scheme-1",
        taxonomy_id: "taxonomy-1",
        version: 1,
        created_at: new Date().toISOString(),
      }),
    );
  }),

  rest.post("/api/classes", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(201),
      ctx.json({
        ...body,
        id: "new-class",
        version: 1,
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
        ...body,
        id,
        version: 1,
      }),
    );
  }),

  rest.delete("/api/classes/:id", (req, res, ctx) => {
    return res(ctx.status(204));
  }),

  // Properties endpoints (replaces legacy predicates)
  rest.get("/api/properties", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        items: [
          {
            id: "prop-1",
            title: "Property 1",
            identifier: "prop-1",
            version: 1,
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    );
  }),

  rest.get("/api/properties/:id", (req, res, ctx) => {
    const { id } = req.params as { id: string };
    return res(
      ctx.status(200),
      ctx.json({
        id,
        title: `Property ${id}`,
        identifier: id,
        version: 1,
      }),
    );
  }),

  rest.post("/api/properties", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(201),
      ctx.json({
        ...body,
        id: "new-property",
        version: 1,
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
        ...body,
        id,
        version: 1,
      }),
    );
  }),

  rest.delete("/api/properties/:id", (req, res, ctx) => {
    return res(ctx.status(204));
  }),

  // Relationships endpoints
  rest.get("/api/relationships", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        items: [
          {
            id: "rel-1",
            source_id: "class-1",
            target_id: "class-2",
            property_definition_id: "prop-1",
            version: 1,
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    );
  }),

  rest.get("/api/relationships/:id", (req, res, ctx) => {
    const { id } = req.params as { id: string };
    return res(
      ctx.status(200),
      ctx.json({
        id,
        source_id: "class-1",
        target_id: "class-2",
        property_definition_id: "prop-1",
        version: 1,
      }),
    );
  }),

  rest.post("/api/relationships", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(201),
      ctx.json({
        ...body,
        id: "new-relationship",
        version: 1,
      }),
    );
  }),

  rest.put("/api/relationships/:id", async (req, res, ctx) => {
    const { id } = req.params as { id: string };
    const body = await req.json();
    return res(
      ctx.status(200),
      ctx.json({
        ...body,
        id,
        version: 1,
      }),
    );
  }),

  rest.delete("/api/relationships/:id", (req, res, ctx) => {
    return res(ctx.status(204));
  }),

  // Graph endpoints
  rest.get("/api/graph", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        nodes: [],
        edges: [],
      }),
    );
  }),

  rest.post("/api/graph", async (req, res, ctx) => {
    const _body = await req.json();
    return res(
      ctx.status(200),
      ctx.json({
        nodes: [],
        edges: [],
      }),
    );
  }),

  // Datasets endpoints
  rest.get("/api/datasets", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      }),
    );
  }),

  // Schema endpoints
  rest.get("/api/schema", (req, res, ctx) => {
    return res(ctx.status(200), ctx.json(null));
  }),

  // Change events endpoints
  rest.get("/api/change_events", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      }),
    );
  }),

  // RAG endpoints
  rest.post("/api/rag/extract", async (req, res, ctx) => {
    const _body = await req.json();
    return res(
      ctx.status(200),
      ctx.json({
        request_id: "rag-req-1",
        status: "completed",
      }),
    );
  }),

  rest.get("/api/rag/metrics/:requestId", (req, res, ctx) => {
    const { requestId } = req.params as { requestId: string };
    return res(
      ctx.status(200),
      ctx.json({
        request_id: requestId,
        metrics: {},
      }),
    );
  }),

  rest.get("/api/rag/trace/:requestId", (req, res, ctx) => {
    const { requestId } = req.params as { requestId: string };
    return res(
      ctx.status(200),
      ctx.json({
        request_id: requestId,
        trace: [],
      }),
    );
  }),

  // RAG Experiments endpoints
  rest.get("/api/rag-experiments/paragraphs", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      }),
    );
  }),

  rest.post("/api/rag-experiments/run", async (req, res, ctx) => {
    const _body = await req.json();
    return res(
      ctx.status(200),
      ctx.json({
        run_id: "exp-run-1",
        status: "completed",
      }),
    );
  }),

  // Pipeline configuration endpoints
  rest.get("/api/pipeline-flavors", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      }),
    );
  }),

  rest.get("/api/llm", (req, res, ctx) => {
    return res(ctx.status(200), ctx.json(null));
  }),

  rest.post("/api/llm", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(201),
      ctx.json({
        ...body,
        id: "new-llm-config",
      }),
    );
  }),

  rest.delete("/api/llm/:id", (req, res, ctx) => {
    return res(ctx.status(204));
  }),

  // LLM Traceability endpoints
  rest.get("/api/llm/health", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: "healthy",
      }),
    );
  }),

  rest.get("/api/llm/record-selection", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      }),
    );
  }),

  rest.get("/api/llm/execution-analytics", (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({}));
  }),

  rest.get("/api/llm/execution-history", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      }),
    );
  }),

  // NLP endpoints
  rest.post("/api/nlp_analysis", async (req, res, ctx) => {
    const _body = await req.json();
    return res(
      ctx.status(200),
      ctx.json({
        analysis_id: "nlp-1",
        results: {},
      }),
    );
  }),

  // Reference endpoints
  rest.get("/api/reference", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      }),
    );
  }),

  rest.get("/api/reference/ref-db", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      }),
    );
  }),

  rest.get("/api/reference/ref-db/filter/statistics", (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({}));
  }),

  rest.get("/api/reference/ref-db/nodes", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      }),
    );
  }),
];
