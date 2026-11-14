/**
 * PipelineService: the parameter bounds it reads from the server's published schema.
 */
import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { pipelineService } from "../pipeline";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("PipelineService.getParameterBounds", () => {
  it("reads each parameter's range, also where the parameter may be null", async () => {
    server.use(
      http.get("*/openapi.json", () =>
        HttpResponse.json({
          components: {
            schemas: {
              PipelineConfigurationParameterSettings: {
                properties: {
                  // Optional: "a number in a range, or null".
                  temperature: {
                    anyOf: [{ type: "number", minimum: 0, maximum: 2 }, { type: "null" }],
                  },
                  max_tokens: {
                    anyOf: [{ type: "integer", minimum: 64, maximum: 20000 }, { type: "null" }],
                  },
                  // Always set: the range is on the property itself.
                  top_p: { type: "number", minimum: 0, maximum: 1 },
                },
              },
            },
          },
        }),
      ),
    );

    await expect(pipelineService.getParameterBounds()).resolves.toEqual({
      temperature: { minimum: 0, maximum: 2 },
      max_tokens: { minimum: 64, maximum: 20000 },
      top_p: { minimum: 0, maximum: 1 },
    });
  });

  it("states no range for a schema that has none", async () => {
    server.use(
      http.get("*/openapi.json", () => HttpResponse.json({ components: { schemas: {} } })),
    );
    await expect(pipelineService.getParameterBounds()).resolves.toEqual({});
  });
});
