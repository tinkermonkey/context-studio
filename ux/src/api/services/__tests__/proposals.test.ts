/**
 * Unit tests for ProposalsService using MSW to mock HTTP responses.
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { proposalsService, type ChangeProposalCreateRequest } from "../proposals";
import { createChangeProposal, createProposedOperation } from "./fixtures/proposals.fixtures";

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

describe("ProposalsService", () => {
  it("lists proposals with filters as query parameters", async () => {
    const proposal = createChangeProposal();
    let query: URLSearchParams | undefined;
    server.use(
      http.get("*/api/proposals", ({ request }) => {
        query = new URL(request.url).searchParams;
        return HttpResponse.json({ items: [proposal], total: 1, limit: 10, offset: 0 });
      }),
    );

    const result = await proposalsService.listProposals({
      taxonomy_id: "tax-1",
      status: "open",
      source: "mcp",
      limit: 10,
    });

    expect(result.items).toEqual([proposal]);
    expect(query?.get("taxonomy_id")).toBe("tax-1");
    expect(query?.get("status")).toBe("open");
    expect(query?.get("source")).toBe("mcp");
    expect(query?.get("limit")).toBe("10");
  });

  it("gets one proposal with stale flags", async () => {
    const proposal = createChangeProposal({
      operations: [createProposedOperation({ stale: true })],
    });
    server.use(http.get("*/api/proposals/proposal-1", () => HttpResponse.json(proposal)));

    const result = await proposalsService.getProposal("proposal-1");

    expect(result.operations[0].stale).toBe(true);
  });

  it("creates a proposal", async () => {
    let body: unknown;
    server.use(
      http.post("*/api/proposals", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(createChangeProposal(), { status: 201 });
      }),
    );
    const request: ChangeProposalCreateRequest = {
      taxonomy_id: "tax-1",
      title: "Clearer rooms",
      source: "mcp",
      operations: [
        {
          seq: 1,
          op: "update",
          kind: "class",
          target_id: "class-1",
          fields: { description: "Any room" },
        },
      ],
    };

    const result = await proposalsService.createProposal(request);

    expect(body).toEqual(request);
    expect(result.id).toBe("proposal-1");
  });

  it("surfaces a 422 validation error", async () => {
    server.use(
      http.post("*/api/proposals", () =>
        HttpResponse.json(
          {
            detail: {
              message: "Invalid change proposal (1 errors)",
              errors: [{ seq: 1, code: "target_not_found", message: "No class class-1" }],
            },
          },
          { status: 422 },
        ),
      ),
    );

    await expect(
      proposalsService.createProposal({
        taxonomy_id: "tax-1",
        title: "x",
        source: "user",
        operations: [],
      }),
    ).rejects.toBeTruthy();
  });

  it("applies, rejects and reverts", async () => {
    const bodies: Record<string, unknown> = {};
    const applied = createChangeProposal({
      status: "done",
      operations: [createProposedOperation({ status: "applied" })],
    });
    server.use(
      http.post("*/api/proposals/proposal-1/apply", async ({ request }) => {
        bodies.apply = await request.json();
        return HttpResponse.json(applied);
      }),
      http.post("*/api/proposals/proposal-1/reject", async ({ request }) => {
        bodies.reject = await request.json();
        return HttpResponse.json(createChangeProposal());
      }),
      http.post("*/api/proposals/proposal-1/revert", () =>
        HttpResponse.json({
          events_reverted: 1,
          classes_deleted: 0,
          individuals_deleted: 0,
          relationships_deleted: 0,
          properties_deleted: 0,
          taxonomies_deleted: 0,
          concept_schemes_deleted: 0,
          entities_restored: 1,
          proposal: createChangeProposal({ status: "reverted" }),
        }),
      ),
    );

    const apply = await proposalsService.applyProposal("proposal-1", {
      operation_ids: ["op-1"],
      force_stale: ["op-1"],
    });
    const reject = await proposalsService.rejectProposal("proposal-1", { note: "no" });
    const revert = await proposalsService.revertProposal("proposal-1");

    expect(apply.status).toBe("done");
    expect(bodies.apply).toEqual({ operation_ids: ["op-1"], force_stale: ["op-1"] });
    expect(reject.status).toBe("open");
    expect(bodies.reject).toEqual({ note: "no" });
    expect(revert.proposal.status).toBe("reverted");
  });
});
