/**
 * The proposal page opens the Review page (#1611) from "Review against
 * source", shown only for a proposal extracted from a source.
 */
import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import { goldPage, proposalHandlers } from "@/test/proposalFixtures";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";
import type { ChangeProposal } from "@/api/services/proposals";
import { ProposalDetailPage } from "../ProposalDetailPage";

const server = setupServer(...proposalHandlers, ...entityPageHandlers);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const extracted = createProposedOperation({
  id: "op-1",
  op: "create",
  kind: "individual",
  target_id: null,
  fields: { title: "Edit Check", class_ids: ["class-1"] },
  evidence: [{ source_id: "src-1", page: null, start: 0, end: 10, quote: "Edit Check" }],
  scope: "additive",
});

function serve(proposal: ChangeProposal) {
  server.use(
    http.get("*/api/proposals/:id", () => HttpResponse.json(proposal)),
    http.get("*/api/taxonomies/:id/gold", () => HttpResponse.json(goldPage(proposal.operations))),
    http.get("*/api/sources/:id", () =>
      HttpResponse.json({ detail: "Source not found" }, { status: 404 }),
    ),
  );
}

describe("Review against source", () => {
  it("opens the review for a proposal extracted from a source", async () => {
    serve(createChangeProposal({ source: "pipeline", operations: [extracted] }));
    const onReview = vi.fn();
    render(
      <ProposalDetailPage
        id="proposal-1"
        onSelectOperation={vi.fn()}
        onReviewAgainstSource={onReview}
      />,
    );
    const button = await screen.findByTestId(
      "proposal-review-against-source",
      {},
      { timeout: 10000 },
    );
    expect(button).toHaveRole("button");
    expect(button).toHaveTextContent("Review against source");
    await userEvent.click(button);
    expect(onReview).toHaveBeenCalledTimes(1);
  });

  it("isn't offered for a schema extraction, whose class operations cite passages", async () => {
    const classOp = createProposedOperation({
      op: "create",
      kind: "class",
      target_id: null,
      fields: { identifier: "cls_room", title: "Room", concept_scheme_id: "scheme-1" },
      evidence: [{ source_id: "src-1", page: null, start: 0, end: 4, quote: "Room" }],
      scope: "additive",
    });
    serve(createChangeProposal({ source: "pipeline", operations: [classOp] }));
    render(
      <ProposalDetailPage
        id="proposal-1"
        onSelectOperation={vi.fn()}
        onReviewAgainstSource={vi.fn()}
      />,
    );
    await screen.findByTestId("proposal-summary", {}, { timeout: 10000 });
    expect(screen.queryByTestId("proposal-review-against-source")).not.toBeInTheDocument();
  });

  it("isn't offered for a proposal no source backs", async () => {
    serve(createChangeProposal());
    render(
      <ProposalDetailPage
        id="proposal-1"
        onSelectOperation={vi.fn()}
        onReviewAgainstSource={vi.fn()}
      />,
    );
    await screen.findByTestId("proposal-summary", {}, { timeout: 10000 });
    expect(screen.queryByTestId("proposal-review-against-source")).not.toBeInTheDocument();
  });

  it("decides a gold check only on the Review page", async () => {
    const origin = {
      pipeline_type: "individual_extraction",
      implementation_id: "gold_check",
      configuration_ref: "gold",
      configuration_version: 1,
      digest: "abc",
    };
    serve(
      createChangeProposal({
        source: "pipeline",
        origin,
        client_metadata: {
          origin,
          gold_check: { document: "edit_check", split: "dev", elements: {}, relationships: {} },
        },
        operations: [{ ...extracted, probability: 0.9 }],
      }),
    );
    const onReview = vi.fn();
    render(
      <ProposalDetailPage
        id="proposal-1"
        selectedOperationId="op-1"
        onSelectOperation={vi.fn()}
        onReviewAgainstSource={onReview}
      />,
    );
    const callout = await screen.findByTestId("proposal-gold-callout", {}, { timeout: 10000 });
    expect(callout).toHaveTextContent(
      "Gold checks are decided on the Review page, where tier, also-defensible and the excluded reason are recorded.",
    );
    expect(screen.queryByTestId("proposal-accept-all")).not.toBeInTheDocument();
    expect(screen.queryByTestId("proposal-reject-all")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operation-decision")).not.toBeInTheDocument();
    // Its create opens the review inspector, read-only here (#1658).
    expect(await screen.findByTestId("review-inspector")).toBeInTheDocument();
    expect(screen.queryByTestId("review-decide")).not.toBeInTheDocument();
    expect(screen.queryByTestId("review-reasons")).not.toBeInTheDocument();
    expect(screen.queryByTestId("proposal-threshold-bar")).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    await userEvent.click(screen.getByTestId("proposal-gold-review"));
    expect(onReview).toHaveBeenCalledTimes(1);
  });

  it("decides other proposals on this page as before", async () => {
    serve(createChangeProposal({ source: "pipeline", operations: [extracted] }));
    render(
      <ProposalDetailPage
        id="proposal-1"
        selectedOperationId="op-1"
        onSelectOperation={vi.fn()}
        onReviewAgainstSource={vi.fn()}
      />,
    );
    expect(
      await screen.findByTestId("proposal-accept-all", {}, { timeout: 10000 }),
    ).toBeInTheDocument();
    // Its extraction creates open the review inspector (#1658).
    expect(await screen.findByTestId("review-decide")).toBeInTheDocument();
    expect(screen.queryByTestId("proposal-gold-callout")).not.toBeInTheDocument();
  });

  it("offers comparing with another pipeline's open extraction of the same source", async () => {
    const origin = (implementation_id: string) => ({
      pipeline_type: "individual_extraction",
      implementation_id,
      configuration_ref: "c",
      configuration_version: 1,
      digest: "abcdef",
    });
    const mine = createChangeProposal({
      source: "pipeline",
      dataset_id: "ds-1",
      origin: origin("single_call"),
      client_metadata: { source_id: "src-1" },
      operations: [extracted],
    });
    const other = { ...mine, id: "proposal-2", origin: origin("find_then_type") };
    serve(mine);
    server.use(
      http.get("*/api/proposals", () =>
        HttpResponse.json({ items: [mine, other], total: 2, limit: 500, offset: 0 }),
      ),
    );
    const onCompare = vi.fn();
    render(
      <ProposalDetailPage id="proposal-1" onSelectOperation={vi.fn()} onCompare={onCompare} />,
    );
    const button = await screen.findByTestId("proposal-compare", {}, { timeout: 10000 });
    expect(button).toHaveTextContent("Compare with another pipeline");
    await userEvent.click(button);
    expect(onCompare).toHaveBeenCalledWith("proposal-2");
  });
});
