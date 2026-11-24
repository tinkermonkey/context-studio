/**
 * One review page (#1664): proposal detail shows the source pane beside the
 * list for a proposal whose elements came from a source, and only then; gold
 * checks are decided here; the "Review against source" button and the gold
 * callout are gone.
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

describe("one review page", () => {
  it("shows the source pane beside the list for a proposal extracted from a source", async () => {
    serve(createChangeProposal({ source: "pipeline", operations: [extracted] }));
    render(<ProposalDetailPage id="proposal-1" onSelectOperation={vi.fn()} />);
    const pane = await screen.findByTestId("review-source", {}, { timeout: 10000 });
    expect(screen.getByTestId("proposal-operations-list")).toContainElement(pane);
    expect(screen.getByTestId("proposal-review")).toHaveClass("proposal-review--source");
    // The source answers 404 here: the pane says so.
    expect(await screen.findByText("The source couldn't be loaded.")).toBeInTheDocument();
    // No button crosses to another page any more.
    expect(screen.queryByTestId("proposal-review-against-source")).not.toBeInTheDocument();
  });

  it("shows no source pane for a schema extraction, whose class operations cite passages", async () => {
    const classOp = createProposedOperation({
      op: "create",
      kind: "class",
      target_id: null,
      fields: { identifier: "cls_room", title: "Room", concept_scheme_id: "scheme-1" },
      evidence: [{ source_id: "src-1", page: null, start: 0, end: 4, quote: "Room" }],
      scope: "additive",
    });
    serve(createChangeProposal({ source: "pipeline", operations: [classOp] }));
    render(<ProposalDetailPage id="proposal-1" onSelectOperation={vi.fn()} />);
    await screen.findByTestId("proposal-review", {}, { timeout: 10000 });
    expect(screen.queryByTestId("review-source")).not.toBeInTheDocument();
    expect(screen.getByTestId("proposal-review")).not.toHaveClass("proposal-review--source");
  });

  it("shows no source pane for a proposal no source backs", async () => {
    serve(createChangeProposal());
    render(<ProposalDetailPage id="proposal-1" onSelectOperation={vi.fn()} />);
    await screen.findByTestId("proposal-review", {}, { timeout: 10000 });
    expect(screen.queryByTestId("review-source")).not.toBeInTheDocument();
  });

  it("decides a gold check here, in gold mode, without bulk", async () => {
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
          gold_check: { document: "edit_check", split: "holdout", elements: {}, relationships: {} },
        },
        operations: [{ ...extracted, probability: 0.9 }],
      }),
    );
    render(
      <ProposalDetailPage id="proposal-1" selectedOperationId="op-1" onSelectOperation={vi.fn()} />,
    );
    // Decided in the inspector, in gold mode: no callout sends the reviewer elsewhere.
    expect(await screen.findByTestId("review-decide", {}, { timeout: 10000 })).toBeInTheDocument();
    expect(screen.queryByTestId("proposal-gold-callout")).not.toBeInTheDocument();
    // The status strip says which split it is from; a held-out check says why it matters.
    expect(screen.getByTestId("review-gold-split")).toHaveTextContent("holdout");
    expect(screen.getByTestId("review-gold-holdout")).toBeInTheDocument();
    // Bulk decisions never apply to a gold check.
    expect(screen.queryByTestId("review-bulk-select")).not.toBeInTheDocument();
    expect(screen.queryByTestId("proposal-selection-bar")).not.toBeInTheDocument();
    expect(screen.queryByTestId("proposal-threshold-slider")).not.toBeInTheDocument();
    expect(screen.queryByTestId(/^operation-check-/)).not.toBeInTheDocument();
  });

  it("decides other proposals on this page as before", async () => {
    serve(createChangeProposal({ source: "pipeline", operations: [extracted] }));
    render(
      <ProposalDetailPage id="proposal-1" selectedOperationId="op-1" onSelectOperation={vi.fn()} />,
    );
    expect(
      await screen.findByTestId("review-bulk-select", {}, { timeout: 10000 }),
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
