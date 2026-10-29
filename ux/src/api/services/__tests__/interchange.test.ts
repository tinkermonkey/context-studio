/**
 * Unit tests for InterchangeService using MSW to mock HTTP responses.
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { ApiError } from "@/api/client/interceptors";
import { interchangeService } from "../interchange";

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const bundle = {
  format: "context-studio-bundle",
  version: 0,
  source: "house",
  taxonomy: { identifier: "house", title: "House" },
  classes: [],
};

describe("InterchangeService", () => {
  it("fetches a taxonomy's bundle", async () => {
    let taxonomyId: string | undefined;
    server.use(
      http.get("*/api/v1/interchange/bundles/:id", ({ params }) => {
        taxonomyId = params.id as string;
        return HttpResponse.json(bundle);
      }),
    );

    const result = await interchangeService.exportBundle("tax-1");

    expect(taxonomyId).toBe("tax-1");
    expect(result).toEqual(bundle);
  });

  it("rejects with the server's detail when the export is refused", async () => {
    server.use(
      http.get("*/api/v1/interchange/bundles/:id", () =>
        HttpResponse.json({ detail: "these have no stored identifier" }, { status: 409 }),
      ),
    );

    const error = await interchangeService.exportBundle("tax-1").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, detail: "these have no stored identifier" });
  });
});
