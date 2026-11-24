/**
 * useProposalActions sends what a review decision records (#1609, #1611): an
 * individual create's class edit and the review time with an apply, and the
 * reason code, note and review time with a reject.
 */
import { renameOperation, unamended } from "@/test/proposalFixtures";
import type { ReactNode } from "react";
import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { createTestQueryClient } from "@/test/test-utils";
import { ToastProvider } from "@/components/ui/Toast";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";
import type {
  ChangeProposalApplyRequest,
  ChangeProposalRejectRequest,
} from "@/api/services/proposals";
import { amendedAtShown, useProposalActions } from "../useProposalActions";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const proposal = createChangeProposal({
  operations: [
    createProposedOperation({
      id: "op-1",
      op: "create",
      kind: "individual",
      target_id: null,
      fields: { title: "Edit Check", class_ids: ["class-1"] },
    }),
  ],
});

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={createTestQueryClient()}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}

describe("useProposalActions", () => {
  it("applies with a class edit and the review time", async () => {
    let body: ChangeProposalApplyRequest | undefined;
    server.use(
      http.post("*/api/proposals/proposal-1/apply", async ({ request }) => {
        body = (await request.json()) as ChangeProposalApplyRequest;
        return HttpResponse.json(proposal);
      }),
    );
    const { result } = renderHook(() => useProposalActions(proposal), { wrapper });

    await act(async () => {
      await result.current.accept(["op-1"], {
        edits: { "op-1": { class_ids: ["class-2"] } },
        reviewMs: { "op-1": 3100 },
      });
    });

    expect(body).toEqual({
      operation_ids: ["op-1"],
      amended_at: unamended(["op-1"]),
      force_stale: [],
      edits: { "op-1": { class_ids: ["class-2"] } },
      review_ms: { "op-1": 3100 },
    });
  });

  it("sends gold annotations with an apply and a reject", async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post("*/api/proposals/proposal-1/apply", async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(proposal);
      }),
      http.post("*/api/proposals/proposal-1/reject", async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(proposal);
      }),
    );
    const { result } = renderHook(() => useProposalActions(proposal), { wrapper });

    await act(async () => {
      await result.current.accept(["op-1"], {
        annotations: { "op-1": { tier: "core", also_defensible: ["class-2"] } },
      });
      await result.current.rejectOperations(["op-1"], "a heading", {
        annotations: { "op-1": { tier: "supporting" } },
      });
    });

    expect(bodies).toEqual([
      {
        operation_ids: ["op-1"],
        amended_at: unamended(["op-1"]),
        force_stale: [],
        edits: {},
        annotations: { "op-1": { tier: "core", also_defensible: ["class-2"] } },
      },
      {
        operation_ids: ["op-1"],
        note: "a heading",
        annotations: { "op-1": { tier: "supporting" } },
      },
    ]);
  });

  it("leaves review_ms out of an apply without one", async () => {
    let body: ChangeProposalApplyRequest | undefined;
    server.use(
      http.post("*/api/proposals/proposal-1/apply", async ({ request }) => {
        body = (await request.json()) as ChangeProposalApplyRequest;
        return HttpResponse.json(proposal);
      }),
    );
    const { result } = renderHook(() => useProposalActions(proposal), { wrapper });

    await act(async () => {
      await result.current.accept(["op-1"]);
    });

    expect(body).toEqual({
      operation_ids: ["op-1"],
      amended_at: unamended(["op-1"]),
      force_stale: [],
      edits: {},
    });
  });

  it("rejects with a reason code, a note and the review time", async () => {
    let body: ChangeProposalRejectRequest | undefined;
    server.use(
      http.post("*/api/proposals/proposal-1/reject", async ({ request }) => {
        body = (await request.json()) as ChangeProposalRejectRequest;
        return HttpResponse.json(proposal);
      }),
    );
    const { result } = renderHook(() => useProposalActions(proposal), { wrapper });

    let rejected = false;
    await act(async () => {
      rejected = await result.current.rejectOperations(["op-1"], "  a region  ", {
        reasonCode: "out_of_scope",
        reviewMs: { "op-1": 800 },
      });
    });

    expect(rejected).toBe(true);
    expect(body).toEqual({
      operation_ids: ["op-1"],
      note: "a region",
      reason_code: "out_of_scope",
      review_ms: { "op-1": 800 },
    });
  });

  it("rejects with only a note, sending no reason code or review time", async () => {
    let body: ChangeProposalRejectRequest | undefined;
    server.use(
      http.post("*/api/proposals/proposal-1/reject", async ({ request }) => {
        body = (await request.json()) as ChangeProposalRejectRequest;
        return HttpResponse.json(proposal);
      }),
    );
    const { result } = renderHook(() => useProposalActions(proposal), { wrapper });

    await act(async () => {
      await result.current.rejectOperations(["op-1"], "duplicate of op-2");
    });

    expect(body).toEqual({ operation_ids: ["op-1"], note: "duplicate of op-2" });
  });
});

describe("amendedAtShown (#1624)", () => {
  it("sends the amended_at the page showed, null for an operation as first proposed", () => {
    const amended = { ...renameOperation, id: "op-a", amended_at: "2026-11-24T12:00:00Z" };
    expect(
      amendedAtShown([renameOperation, amended], ["op-a", renameOperation.id, "op-x"]),
    ).toEqual({ "op-a": "2026-11-24T12:00:00Z", [renameOperation.id]: null });
  });
});
