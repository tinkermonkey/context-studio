/**
 * The inspector's Change section reads the entities an operation names by id
 * (#1450): an individual's classes and a class's scheme by title, a
 * relationship's ends and type by name, and a "$ref" to an earlier create as
 * "#seq title (new in this proposal)". The raw id stays in the tooltip.
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
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

const classCreate = createProposedOperation({
  id: "op-class",
  seq: 1,
  op: "create",
  kind: "class",
  target_id: null,
  ref: "c1",
  fields: { title: "Heat Pump", concept_scheme_id: "scheme-1" },
  scope: "additive",
  status: "pending",
});
const individualCreate = createProposedOperation({
  id: "op-ind",
  seq: 2,
  op: "create",
  kind: "individual",
  target_id: null,
  ref: "t2",
  fields: { title: "Basement heat pump", class_ids: ["class-2", "$c1"] },
  scope: "additive",
  status: "pending",
});
const relationshipCreate = createProposedOperation({
  id: "op-rel",
  seq: 3,
  op: "create",
  kind: "relationship",
  target_id: null,
  fields: { property_definition_id: "prop-1", source_id: "ind-1", target_id: "$t2" },
  scope: "additive",
  status: "pending",
});

let proposal: ChangeProposal;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  proposal = createChangeProposal({
    id: "proposal-1",
    taxonomy_id: "tax-1",
    title: "Extraction: heat pump manual",
    status: "open",
    operations: [classCreate, individualCreate, relationshipCreate],
  });
  server.use(
    http.get("*/api/proposals/:id", () => HttpResponse.json(proposal)),
    http.get("*/api/taxonomies/:id/gold", () => HttpResponse.json(goldPage(proposal.operations))),
  );
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderPage(selectedOperationId: string) {
  return render(
    <ProposalDetailPage
      id="proposal-1"
      selectedOperationId={selectedOperationId}
      onSelectOperation={vi.fn()}
    />,
  );
}

function refsOf(field: string) {
  return within(screen.getByTestId(`operation-change-refs-${field}`));
}

describe("the inspector's Change section names what an operation refers to", () => {
  it("reads an individual's classes by name, a $ref class as new in this proposal", async () => {
    renderPage("op-ind");
    const row = await screen.findByTestId("operation-change-row-class_ids");
    await waitFor(() => expect(row).toHaveTextContent("application_service"));
    expect(row).not.toHaveTextContent('["class-2"');
    expect(row).not.toHaveTextContent("$c1");

    const existing = refsOf("class_ids").getByText("application_service");
    expect(existing).toHaveClass("op-ref");
    expect(existing).not.toHaveClass("op-ref--new");
    // The raw id stays in the tooltip.
    expect(existing).toHaveAttribute("title", "class-2");

    const created = refsOf("class_ids").getByText("#1 Heat Pump (new in this proposal)");
    expect(created).toHaveClass("op-ref", "op-ref--new");
    expect(created).toHaveAttribute("title", "$c1");
  });

  it("reads a class's scheme by its title", async () => {
    renderPage("op-class");
    const row = await screen.findByTestId("operation-change-row-concept_scheme_id");
    await waitFor(() => expect(row).toHaveTextContent("Application Layer"));
    expect(row).not.toHaveTextContent("scheme-1");
    expect(refsOf("concept_scheme_id").getByText("Application Layer")).toHaveAttribute(
      "title",
      "scheme-1",
    );
  });

  it("reads a relationship's ends and type by name, a $ref end by its create", async () => {
    renderPage("op-rel");
    const source = await screen.findByTestId("operation-change-row-source_id");
    await waitFor(() => expect(source).toHaveTextContent("LLM Provider Router"));
    expect(source).not.toHaveTextContent("ind-1");
    expect(refsOf("source_id").getByText("LLM Provider Router")).toHaveAttribute("title", "ind-1");

    const target = screen.getByTestId("operation-change-row-target_id");
    expect(target).toHaveTextContent("#2 Basement heat pump (new in this proposal)");
    expect(target).not.toHaveTextContent("$t2");
    expect(
      refsOf("target_id").getByText("#2 Basement heat pump (new in this proposal)"),
    ).toHaveAttribute("title", "$t2");

    const type = screen.getByTestId("operation-change-row-property_definition_id");
    await waitFor(() => expect(type).toHaveTextContent("realizes"));
    expect(type).not.toHaveTextContent("prop-1");
  });

  it("keeps an id it can't resolve, so nothing reads blank", async () => {
    proposal = createChangeProposal({
      id: "proposal-1",
      taxonomy_id: "tax-1",
      status: "open",
      operations: [
        createProposedOperation({
          id: "op-ghost",
          seq: 1,
          op: "create",
          kind: "relationship",
          target_id: null,
          fields: { property_definition_id: "prop-1", source_id: "ind-1", target_id: "$gone" },
          scope: "additive",
          status: "pending",
        }),
      ],
    });
    renderPage("op-ghost");
    const target = await screen.findByTestId("operation-change-row-target_id");
    expect(refsOf("target_id").getByText("$gone")).toHaveAttribute("title", "$gone");
    expect(target).not.toHaveTextContent("new in this proposal");
  });
});
