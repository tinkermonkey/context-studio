/**
 * Unit tests for ProposalsService using MSW to mock HTTP responses.
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { ApiError } from "@/api/client/interceptors";
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

  it("lists every proposal of an implementation, page after page", async () => {
    const offsets: (string | null)[] = [];
    const all = Array.from({ length: 501 }, (_, i) => createChangeProposal({ id: `p-${i}` }));
    server.use(
      http.get("*/api/proposals", ({ request }) => {
        const query = new URL(request.url).searchParams;
        expect(query.get("implementation_id")).toBe("gold_check");
        offsets.push(query.get("offset"));
        const offset = Number(query.get("offset"));
        const limit = Number(query.get("limit"));
        return HttpResponse.json({
          items: all.slice(offset, offset + limit),
          total: all.length,
          limit,
          offset,
        });
      }),
    );

    const result = await proposalsService.listAllProposals({ implementation_id: "gold_check" });

    expect(result).toHaveLength(501);
    expect(offsets).toEqual(["0", "500"]);
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

  it("sends an individual create's class edit and the review time with an apply", async () => {
    let body: unknown;
    server.use(
      http.post("*/api/proposals/proposal-1/apply", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          createChangeProposal({
            operations: [
              createProposedOperation({
                op: "create",
                kind: "individual",
                status: "applied",
                applied_fields: { title: "Edit Check", class_ids: ["class-2"] },
              }),
            ],
          }),
        );
      }),
    );

    const result = await proposalsService.applyProposal("proposal-1", {
      operation_ids: ["op-1"],
      edits: { "op-1": { class_ids: ["class-2"] } },
      review_ms: { "op-1": 4200 },
    });

    expect(body).toEqual({
      operation_ids: ["op-1"],
      edits: { "op-1": { class_ids: ["class-2"] } },
      review_ms: { "op-1": 4200 },
    });
    expect(result.operations[0].applied_fields).toEqual({
      title: "Edit Check",
      class_ids: ["class-2"],
    });
  });

  it("sends a reject's reason code, note and review time, and reads the code back", async () => {
    let body: unknown;
    server.use(
      http.post("*/api/proposals/proposal-1/reject", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          createChangeProposal({
            operations: [
              createProposedOperation({
                status: "rejected",
                reason: "a region",
                reason_code: "out_of_scope",
              }),
            ],
          }),
        );
      }),
    );

    const result = await proposalsService.rejectProposal("proposal-1", {
      operation_ids: ["op-1"],
      note: "a region",
      reason_code: "out_of_scope",
      review_ms: { "op-1": 900 },
    });

    expect(body).toEqual({
      operation_ids: ["op-1"],
      note: "a region",
      reason_code: "out_of_scope",
      review_ms: { "op-1": 900 },
    });
    expect(result.operations[0].reason_code).toBe("out_of_scope");
  });

  it("adds an individual found in the source", async () => {
    let body: unknown;
    server.use(
      http.post("*/api/proposals/proposal-1/operations", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          createChangeProposal({
            operations: [
              createProposedOperation({
                id: "op-9",
                op: "create",
                kind: "individual",
                status: "applied",
                added_by_reviewer: true,
              }),
            ],
          }),
          { status: 201 },
        );
      }),
    );
    const data = {
      title: "TextMatch",
      class_ids: ["class-1"],
      passage: { source_id: "src-1", start: 10, end: 19, quote: "TextMatch" },
      review_ms: 4000,
    };

    const result = await proposalsService.addIndividual("proposal-1", data);

    expect(body).toEqual(data);
    expect(result.operations[0]).toMatchObject({ added_by_reviewer: true, status: "applied" });
  });

  it("keeps an addition's validation errors on the ApiError", async () => {
    const errors = [{ seq: 6, code: "duplicate_title", message: "An individual titled 'X'…" }];
    server.use(
      http.post("*/api/proposals/proposal-1/operations", () =>
        HttpResponse.json({ detail: { message: "Invalid", errors } }, { status: 422 }),
      ),
    );

    const error = await proposalsService
      .addIndividual("proposal-1", {
        title: "X",
        class_ids: ["class-1"],
        passage: { source_id: "src-1", start: 0, end: 1, quote: "X" },
      })
      .catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 422, detail: "Invalid", body: { errors } });
  });

  it("keeps a refused revert's blockers on the ApiError", async () => {
    const blocking = [{ kind: "individual", dependent_id: "ind-1", referenced_id: "class-9" }];
    server.use(
      http.post("*/api/proposals/proposal-1/revert", () =>
        HttpResponse.json({ detail: { message: "Can't be reverted", blocking } }, { status: 409 }),
      ),
    );

    const error = await proposalsService.revertProposal("proposal-1").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 409,
      detail: "Can't be reverted",
      body: { message: "Can't be reverted", blocking },
    });
  });

  it("gets a proposal's DR decisions", async () => {
    const decisions = [
      { seq: 1, op_id: "op-1", status: "applied", reason: null, result_entity_id: "p-1" },
    ];
    server.use(
      http.get("*/api/proposals/proposal-1/decisions", () => HttpResponse.json(decisions)),
    );
    expect(await proposalsService.getDecisions("proposal-1")).toEqual(decisions);
  });

  it("reads and replaces a taxonomy's approval policy", async () => {
    const policy = {
      taxonomy_id: "tax-1",
      auto_apply: [{ op: "create" as const, kind: "individual" as const, class: "house_activity" }],
      min_probability: 0.5,
    };
    let body: unknown;
    server.use(
      http.get("*/api/taxonomies/tax-1/approval-policy", () =>
        HttpResponse.json({ taxonomy_id: "tax-1", auto_apply: [], min_probability: 0 }),
      ),
      http.put("*/api/taxonomies/tax-1/approval-policy", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(policy);
      }),
    );

    const empty = await proposalsService.getApprovalPolicy("tax-1");
    const saved = await proposalsService.setApprovalPolicy("tax-1", {
      auto_apply: policy.auto_apply,
      min_probability: 0.5,
    });

    expect(empty.auto_apply).toEqual([]);
    expect(body).toEqual({ auto_apply: policy.auto_apply, min_probability: 0.5 });
    expect(saved).toEqual(policy);
  });
});
