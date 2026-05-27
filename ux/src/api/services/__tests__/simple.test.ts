/**
 * Simple sanity test to verify MSW setup works
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { http, HttpResponse } from "msw";
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
  it("http should be defined", () => {
    expect(http).toBeDefined();
    expect(typeof http.get).toBe("function");
  });

  it("can mock a simple GET request", async () => {
    server.use(
      http.get("*/api/taxonomies", () => {
        return HttpResponse.json({ items: [], total: 0, offset: 0 });
      }),
    );

    const result = await ontologyService.listTaxonomies();
    expect(result.items).toEqual([]);
  });
});
