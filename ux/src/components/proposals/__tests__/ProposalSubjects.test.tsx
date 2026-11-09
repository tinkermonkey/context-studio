/**
 * Operations read by name, not id (#1459): an attribute with its owning class
 * ("ApplicationComponent · Status"), an individual or taxonomy update by its
 * title, and a relationship as its triple, in the change cell and the
 * inspector title. The id stays as the inspector's secondary line.
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

const attributeUpdate = createProposedOperation({
  id: "op-attr",
  seq: 1,
  op: "update",
  kind: "attribute",
  target_id: "attr-1",
  // An update's base holds only the fields it touches: no title, no class.
  base: { description: "Open or done." },
  fields: { description: "Open, in progress or done." },
  scope: "editorial",
  status: "pending",
});
const attributeCreate = createProposedOperation({
  id: "op-attr-new",
  seq: 2,
  op: "create",
  kind: "attribute",
  target_id: null,
  fields: { class_id: "class-2", identifier: "service_owner", title: "Owner" },
  scope: "additive",
  status: "pending",
});
const individualUpdate = createProposedOperation({
  id: "op-ind",
  seq: 3,
  op: "update",
  kind: "individual",
  target_id: "ind-1",
  base: { description: "Routes LLM calls." },
  fields: { description: "Routes LLM calls to the configured provider." },
  scope: "editorial",
  status: "pending",
});
const taxonomyUpdate = createProposedOperation({
  id: "op-tax",
  seq: 4,
  op: "update",
  kind: "taxonomy",
  target_id: "tax-1",
  base: { description: "DR." },
  fields: { description: "The Documentation Robotics spec." },
  scope: "editorial",
  status: "pending",
});
const gatewayCreate = createProposedOperation({
  id: "op-gateway",
  seq: 5,
  op: "create",
  kind: "individual",
  target_id: null,
  ref: "gateway",
  fields: { class_ids: ["class-2"], title: "Gateway" },
  scope: "additive",
  status: "pending",
});
const relationshipCreate = createProposedOperation({
  id: "op-rel",
  seq: 6,
  op: "create",
  kind: "relationship",
  target_id: null,
  fields: { property_definition_id: "prop-1", source_id: "ind-1", target_id: "$gateway" },
  scope: "additive",
  status: "pending",
});

const attributeRename = createProposedOperation({
  id: "op-attr-rename",
  seq: 7,
  op: "update",
  kind: "attribute",
  target_id: "attr-1",
  // A rename's base has the title but not the class.
  base: { title: "Status" },
  fields: { title: "State" },
  scope: "editorial",
  status: "pending",
});
const relationshipUpdate = createProposedOperation({
  id: "op-rel-update",
  seq: 8,
  op: "update",
  kind: "relationship",
  target_id: "rel-1",
  // An attributes-only update names no ends.
  base: { attributes: { weight: 1 } },
  fields: { attributes: { weight: 2 } },
  scope: "editorial",
  status: "pending",
});
const schemeUpdate = createProposedOperation({
  id: "op-scheme",
  seq: 9,
  op: "update",
  kind: "scheme",
  target_id: "scheme-1",
  base: { description: "Old." },
  fields: { description: "New." },
  scope: "editorial",
  status: "pending",
});

let proposal: ChangeProposal;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  proposal = createChangeProposal({
    id: "proposal-1",
    taxonomy_id: "tax-1",
    title: "Name things",
    status: "open",
    operations: [
      attributeUpdate,
      attributeCreate,
      individualUpdate,
      taxonomyUpdate,
      gatewayCreate,
      relationshipCreate,
      attributeRename,
      relationshipUpdate,
      schemeUpdate,
    ],
  });
  server.use(
    http.get("*/api/proposals/:id", () => HttpResponse.json(proposal)),
    http.get("*/api/taxonomies/:id/gold", () => HttpResponse.json(goldPage(proposal.operations))),
  );
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderPage(selectedOperationId?: string) {
  return render(
    <ProposalDetailPage
      id="proposal-1"
      selectedOperationId={selectedOperationId}
      onSelectOperation={vi.fn()}
    />,
  );
}

async function inspectorTitle() {
  const inspector = await screen.findByTestId("operation-inspector");
  return inspector.querySelector(".inspector-panel__title")!;
}

describe("an attribute update", () => {
  it("reads by its class and name in the change cell", async () => {
    renderPage();
    const cell = await screen.findByTestId("operation-diff-op-attr");
    await waitFor(() => expect(cell).toHaveTextContent("attribute ApplicationComponent · Status"));
    expect(cell).not.toHaveTextContent("attr-1");
  });

  it("reads by its class and name in the inspector title, with the id below", async () => {
    renderPage("op-attr");
    const title = await inspectorTitle();
    await waitFor(() => expect(title).toHaveTextContent("ApplicationComponent · Status"));
    expect(title).not.toHaveTextContent("attr-1");
    const inspector = screen.getByTestId("operation-inspector");
    expect(within(inspector).getByText("op-attr")).toHaveClass("inspector-panel__id");
  });
});

describe("other kinds named by id", () => {
  it("names an attribute create with its owning class", async () => {
    renderPage();
    const cell = await screen.findByTestId("operation-diff-op-attr-new");
    await waitFor(() => expect(cell).toHaveTextContent("attribute ApplicationService · Owner"));
  });

  it("shows an attribute's class by label in the inspector's change list", async () => {
    renderPage("op-attr-new");
    const row = await screen.findByTestId("operation-change-row-class_id");
    await waitFor(() => expect(row).not.toHaveTextContent("class-2"));
    expect(row).toHaveTextContent("application_service");
  });

  it("names an individual update by its title", async () => {
    renderPage("op-ind");
    const cell = await screen.findByTestId("operation-diff-op-ind");
    await waitFor(() => expect(cell).toHaveTextContent("individual LLM Provider Router"));
    expect(cell).not.toHaveTextContent("ind-1");
    await waitFor(async () =>
      expect(await inspectorTitle()).toHaveTextContent("LLM Provider Router"),
    );
  });

  it("names a taxonomy update by its title", async () => {
    renderPage();
    const cell = await screen.findByTestId("operation-diff-op-tax");
    await waitFor(() => expect(cell).toHaveTextContent("taxonomy Documentation Robotics"));
    expect(cell).not.toHaveTextContent("tax-1");
  });

  it("reads a relationship create as its triple, a $ref end by its create's title", async () => {
    renderPage("op-rel");
    const cell = await screen.findByTestId("operation-diff-op-rel");
    await waitFor(() =>
      expect(cell).toHaveTextContent("relationship LLM Provider Router realizes Gateway"),
    );
    await waitFor(async () =>
      expect(await inspectorTitle()).toHaveTextContent("LLM Provider Router realizes Gateway"),
    );
  });

  it("names an attribute rename with its owning class, looked up as its base has none", async () => {
    renderPage();
    const cell = await screen.findByTestId("operation-diff-op-attr-rename");
    await waitFor(() => expect(cell).toHaveTextContent("attribute ApplicationComponent · Status"));
  });

  it("reads a relationship update by its looked-up triple", async () => {
    renderPage();
    const cell = await screen.findByTestId("operation-diff-op-rel-update");
    await waitFor(() =>
      expect(cell).toHaveTextContent("relationship LLM Provider Router realizes Pipeline API"),
    );
    expect(cell).not.toHaveTextContent("rel-1");
  });

  it("names a scheme update by its title", async () => {
    renderPage();
    const cell = await screen.findByTestId("operation-diff-op-scheme");
    await waitFor(() => expect(cell).toHaveTextContent("scheme Application Layer"));
    expect(cell).not.toHaveTextContent("scheme-1");
  });
});
