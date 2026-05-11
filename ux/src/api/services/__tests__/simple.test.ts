/**
 * Simple sanity test to verify MSW setup works
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { ontologyService } from "../ontology";

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

describe("Simple MSW Test", () => {
  it("rest should be defined", () => {
    expect(rest).toBeDefined();
    expect(typeof rest.get).toBe("function");
  });

  it("can mock a simple GET request", async () => {
    server.use(
      rest.get("*/api/taxonomies", (req, res, ctx) => {
        return res(ctx.json({ items: [], total: 0, offset: 0 }));
      }),
    );

    const result = await ontologyService.listTaxonomies();
    expect(result.items).toEqual([]);
  });
});
