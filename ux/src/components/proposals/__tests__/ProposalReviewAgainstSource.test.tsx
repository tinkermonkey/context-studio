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
});
