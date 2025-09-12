import { rest } from "msw";

// Centralized MSW handlers for common API endpoints used in integration tests.
// Extend these as tests require more endpoints and edge cases.
export const handlers = [
  // Generic PUT matcher for domains; validate minimal required fields and return normalized domain
  rest.put(new RegExp(".*/api/domains/.+"), async (req, res, ctx) => {
    const body = await req.json();
    // extract id from url
    const pathname = req.url.pathname || "";
    const parts = pathname.split("/").filter(Boolean);
    const id = parts.length ? parts[parts.length - 1] : "unknown";

    // Minimal validation for tests: require a title
    if (!body || typeof body.title !== "string" || body.title.trim() === "") {
      return res(
        ctx.status(400),
        ctx.json({ message: "Validation failed: title is required" }),
      );
    }

    // Normalize layer_id if missing for test flexibility
    const layer_id = body.layer_id || "00000000-0000-0000-0000-000000000000";

    const response = {
      data: {
        id,
        title: String(body.title),
        definition: body.definition || null,
        layer_id,
        created_at: body.created_at || new Date().toISOString(),
        description: body.description || null,
      },
    };

    return res(ctx.status(200), ctx.json(response));
  }),

  // Domains list & single
  rest.get("/api/domains", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ data: [{ id: "domain-1", title: "Domain 1" }] }),
    );
  }),
  rest.get("http://localhost:8000/api/domains", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ data: [{ id: "domain-1", title: "Domain 1" }] }),
    );
  }),
  rest.get("http://localhost:8000/api/domains/", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ data: [{ id: "domain-1", title: "Domain 1" }] }),
    );
  }),
  rest.get("/api/domains/:id", (req, res, ctx) => {
    const { id } = req.params as { id: string };
    return res(
      ctx.status(200),
      ctx.json({ data: { id, title: `Domain ${id}` } }),
    );
  }),
  rest.get("http://localhost:8000/api/domains/:id", (req, res, ctx) => {
    const { id } = req.params as { id: string };
    return res(
      ctx.status(200),
      ctx.json({ data: { id, title: `Domain ${id}` } }),
    );
  }),
  rest.post("/api/domains", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(201),
      ctx.json({ data: { ...body, id: "new-domain" } }),
    );
  }),
  rest.post("http://localhost:8000/api/domains", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(201),
      ctx.json({ data: { ...body, id: "new-domain" } }),
    );
  }),
  rest.put("/api/domains/:id", async (req, res, ctx) => {
    const { id } = req.params as { id: string };
    const body = await req.json();
    // Accept numeric or uuid layer ids for test flexibility
    const layer_id = body.layer_id || "00000000-0000-0000-0000-000000000000";
    return res(ctx.status(200), ctx.json({ data: { ...body, id, layer_id } }));
  }),
  rest.put("/api/domains/:id/", async (req, res, ctx) => {
    const { id } = req.params as { id: string };
    const body = await req.json();
    const layer_id = body.layer_id || "00000000-0000-0000-0000-000000000000";
    return res(ctx.status(200), ctx.json({ data: { ...body, id, layer_id } }));
  }),
  rest.put("http://localhost:8000/api/domains/:id", async (req, res, ctx) => {
    const { id } = req.params as { id: string };
    const body = await req.json();
    return res(ctx.status(200), ctx.json({ data: { ...body, id } }));
  }),
  rest.put("http://localhost:8000/api/domains/:id/", async (req, res, ctx) => {
    const { id } = req.params as { id: string };
    const body = await req.json();
    return res(ctx.status(200), ctx.json({ data: { ...body, id } }));
  }),

  // Layers list
  rest.get("/api/layers", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ data: [{ id: "layer-1", title: "Layer 1" }] }),
    );
  }),
  rest.get("http://localhost:8000/api/layers", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ data: [{ id: "layer-1", title: "Layer 1" }] }),
    );
  }),
  rest.get("http://localhost:8000/api/layers/", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ data: [{ id: "layer-1", title: "Layer 1" }] }),
    );
  }),
  rest.get("/api/layers/:id", (req, res, ctx) => {
    const { id } = req.params as { id: string };
    return res(
      ctx.status(200),
      ctx.json({ data: { id, title: `Layer ${id}` } }),
    );
  }),
  rest.get("http://localhost:8000/api/layers/:id", (req, res, ctx) => {
    const { id } = req.params as { id: string };
    return res(
      ctx.status(200),
      ctx.json({ data: { id, title: `Layer ${id}` } }),
    );
  }),

  // Terms list & create
  rest.get("/api/terms", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ data: [{ id: "term-1", title: "Term 1" }] }),
    );
  }),
  rest.get("http://localhost:8000/api/terms", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ data: [{ id: "term-1", title: "Term 1" }] }),
    );
  }),
  rest.get("http://localhost:8000/api/terms/", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ data: [{ id: "term-1", title: "Term 1" }] }),
    );
  }),
  rest.post("/api/terms", async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(201),
      ctx.json({ data: { ...body, id: "new-term" } }),
    );
  }),

  // Predicates
  rest.get("/api/predicates", (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: [] }));
  }),
  rest.get("http://localhost:8000/api/predicates", (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: [] }));
  }),
  rest.get("http://localhost:8000/api/predicates/", (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: [] }));
  }),

  // Relationships
  rest.get("/api/relationships", (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: [] }));
  }),
];
