import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import { createOperation, openProposal, proposalHandlers } from "@/test/proposalFixtures";
import { useBreadcrumbStore } from "@/stores/breadcrumbs";
import { ProposalDetailPage } from "../ProposalDetailPage";

const server = setupServer(...proposalHandlers, ...entityPageHandlers);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderPage(selectedOperationId?: string, onSelectOperation = vi.fn()) {
  const result = render(
    <ProposalDetailPage
      id="proposal-1"
      selectedOperationId={selectedOperationId}
      onSelectOperation={onSelectOperation}
    />,
  );
  return { ...result, onSelectOperation };
}

describe("ProposalDetailPage", () => {
  it("shows the header, status, tally and op mix", async () => {
    renderPage();

    expect(
      await screen.findByRole("heading", { name: "DR reflection plan: application layer" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("PROPOSAL · dr_spec · pipeline")).toBeInTheDocument();
    expect(screen.getByTestId("proposal-status")).toHaveClass("chip--amber");
    expect(screen.getByTestId("proposal-status")).toHaveTextContent("open");
    expect(screen.getByTestId("proposal-tally")).toHaveTextContent("3 of 4 need a decision");
    expect(screen.getByTestId("proposal-decided-counts")).toHaveTextContent(
      "1 applied · 0 rejected",
    );
    expect(screen.getByTestId("proposal-summary")).toHaveClass("proposal-summary--open");
    expect(screen.getByTestId("proposal-op-mix")).toHaveTextContent(
      "1 create · 2 update · 1 delete · 2 breaking · 1 additive · 1 editorial",
    );
    expect(useBreadcrumbStore.getState()).toMatchObject({
      pathname: "/app/proposals/proposal-1",
      crumbs: [
        { label: "Proposals", to: "/app/proposals" },
        { label: "DR reflection plan: application layer" },
      ],
    });
  });

  it("says which implementation and version produced it beside the status", async () => {
    server.use(
      http.get("*/api/proposals/:id", () =>
        HttpResponse.json({
          ...openProposal,
          origin: {
            pipeline_type: "schema_relationship_reflection",
            implementation_id: "default",
            configuration_ref: "reflection-default",
            configuration_version: 4,
            digest: "a1b2c3d4e5f6",
          },
        }),
      ),
    );
    renderPage();

    const origin = await screen.findByTestId("proposal-origin");
    expect(origin).toHaveTextContent("default v4 · a1b2c3");
    expect(origin).toHaveClass("chip--version");
    expect(origin.getAttribute("title")).toContain("configuration reflection-default version 4");
    expect(within(screen.getByTestId("proposal-summary")).getByTestId("proposal-origin")).toBe(
      origin,
    );
  });

  it("shows no origin for a proposal no run recorded one for", async () => {
    renderPage();

    await screen.findByTestId("proposal-status");
    expect(screen.queryByTestId("proposal-origin")).not.toBeInTheDocument();
  });

  it("renders each operation's change as a triple diff or field change", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("radio", { name: "All · 4" }));

    // Update: the current triple (its ends from the current property), then the new one.
    const rename = await screen.findByTestId("operation-diff-op-rename");
    expect(rename).toHaveClass("op-diff");
    expect(await within(rename).findAllByText("application_component")).toHaveLength(2);
    const changed = rename.querySelectorAll(".op-diff__changed");
    expect([...changed].map((el) => el.textContent)).toEqual(["serves"]);
    expect(within(rename).getByText("realizes")).toHaveClass("op-diff__predicate");

    // Delete: the triple struck through.
    const removal = screen.getByTestId("operation-diff-op-delete");
    expect(removal.querySelector(".op-diff__removed")).toHaveTextContent(
      "application_component realizes application_service",
    );

    // Create: the new triple.
    expect(screen.getByTestId("operation-diff-op-create")).toHaveTextContent(
      "application_service uses application_component",
    );

    // A class update: the entity, then field before → after.
    const classChange = screen.getByTestId("operation-diff-op-class");
    expect(classChange).toHaveTextContent("class application_component");
    expect(within(classChange).getByText("A deployable part")).toHaveClass("op-diff__changed");
  });

  it("shows op, plan kind, probability, decision state and stale chips", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("radio", { name: "All · 4" }));
    await screen.findByTestId("operation-diff-op-rename");

    const renameRow = screen.getByTestId("review-row-op-rename");
    expect(within(renameRow).getByTestId("review-row-op-op-rename")).toHaveTextContent(
      "seq 1 · update",
    );
    expect(renameRow.querySelector(".review-row__p")).toHaveTextContent("0.82");
    expect(within(renameRow).getByText("needs decision")).toHaveClass("chip--amber");
    expect(renameRow).toHaveAttribute("data-verdict", "needs_decision");
    expect(screen.queryByTestId("operation-stale-op-rename")).not.toBeInTheDocument();
    expect(screen.getByTestId("operation-stale-op-delete")).toHaveClass("chip--rose");
    expect(within(screen.getByTestId("review-row-op-create")).getByText("applied")).toHaveClass(
      "chip--emerald",
    );

    // The plan kind: the Change kind grouping's sections.
    await user.click(
      within(screen.getByTestId("proposal-group-by")).getByRole("radio", { name: "Change kind" }),
    );
    const renames = screen.getByTestId("review-group-kind-rename-predicate");
    expect(renames).toHaveAttribute("aria-label", "rename-predicate · mechanical");
    expect(renames).toContainElement(screen.getByTestId("review-row-op-rename"));
  });

  it("leaves out the Change kind grouping when no operation has a plan kind", async () => {
    server.use(
      http.get("*/api/proposals/:id", () =>
        HttpResponse.json({ ...openProposal, operations: [createOperation] }),
      ),
    );
    renderPage();
    await screen.findByTestId("operation-diff-op-create");
    expect(screen.queryByRole("radio", { name: "Change kind" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("review-group-kind-other")).not.toBeInTheDocument();
  });

  it("selects an operation on row click", async () => {
    const user = userEvent.setup();
    const { onSelectOperation, rerender } = renderPage();
    await user.click(await screen.findByTestId("review-row-op-rename"));
    expect(onSelectOperation).toHaveBeenLastCalledWith("op-rename");

    rerender(
      <ProposalDetailPage
        id="proposal-1"
        selectedOperationId="op-rename"
        onSelectOperation={onSelectOperation}
      />,
    );
    const row = screen.getByTestId("review-row-op-rename");
    expect(row).toHaveClass("review-row--selected");
    expect(row).toHaveAttribute("aria-selected", "true");
  });

  it("shows the selected operation in the inspector beside the list", async () => {
    renderPage("op-rename");

    const inspector = await screen.findByTestId("review-inspector");
    expect(screen.getByTestId("proposal-review")).toContainElement(inspector);
    expect(screen.getByTestId("proposal-review")).toContainElement(
      screen.getByTestId("proposal-operations-list"),
    );
    // The review inspector reads a relationship type as its triple (#1662).
    expect(screen.getByTestId("review-inspector-eyebrow")).toHaveTextContent(
      "update · property · seq 1",
    );

    const predicate = await screen.findByTestId("review-diff-row-canonical_predicate");
    // The field name, then was (struck) above now.
    expect(within(predicate).getByText("predicate")).toHaveClass("review-diff__field");
    expect(predicate.querySelector(".review-diff__was")).toHaveTextContent("realizes");
    expect(predicate.querySelector(".review-diff__now")).toHaveTextContent("serves");

    expect(screen.getByTestId("review-why-rationale")).toHaveTextContent("Rename the predicate.");
    expect(within(inspector).getByText("rename-predicate")).toHaveClass("chip--id-tag");
    expect(within(inspector).getByText("p 0.82")).toBeInTheDocument();
    expect(within(inspector).getByText("breaking")).toHaveClass("chip--rose");

    const evidence = screen.getByTestId("review-quote-1");
    expect(evidence).toHaveTextContent("realizes and serves say the same thing here.");
    expect(evidence.querySelector("figcaption")).toHaveTextContent("node:x#3");
    expect(screen.getByTestId("review-evidence")).toHaveTextContent("https://example.com/spec");
  });

  it("shows a DR type's cardinality, strength and spec evidence on a create", async () => {
    server.use(
      http.get("*/api/proposals/proposal-1", () =>
        HttpResponse.json({
          ...openProposal,
          operations: openProposal.operations.map((o) =>
            o.id === "op-create"
              ? {
                  ...o,
                  fields: {
                    ...o.fields,
                    external_references: [
                      {
                        source: "documentation_robotics",
                        identifier:
                          "business.businessservice.uses.application.applicationcomponent",
                        metadata: {
                          cardinality: "many-to-many",
                          strength: "medium",
                          evidence: ["A service config names the component.", "A second line."],
                        },
                      },
                    ],
                  },
                }
              : o,
          ),
        }),
      ),
    );
    renderPage("op-create");

    const strength = await screen.findByTestId("review-diff-row-strength");
    expect(within(strength).getByText("strength")).toHaveClass("review-diff__field");
    expect(strength.querySelector(".review-diff__now")).toHaveTextContent("medium");
    const cardinality = screen.getByTestId("review-diff-row-cardinality");
    expect(within(cardinality).getByText("many-to-many")).toBeInTheDocument();
    const evidence = screen.getByTestId("review-diff-row-evidence");
    expect(within(evidence).getByText("spec evidence")).toHaveClass("review-diff__field");
    const lines = within(evidence).getAllByRole("listitem");
    expect(lines.map((li) => li.textContent)).toEqual([
      "A service config names the component.",
      "A second line.",
    ]);
  });

  it("resolves a delete's class ids and warns when the operation is stale", async () => {
    renderPage("op-delete");

    expect(await screen.findByTestId("operation-stale-callout")).toHaveAttribute("role", "alert");
    const source = await screen.findByTestId("review-diff-row-domain_class_id");
    expect(within(source).getByText("source")).toBeInTheDocument();
    // A class reads as its pill, by its DR reference (#1662).
    expect(await within(source).findByText("application.component")).toBeInTheDocument();
    // A delete lists what it removes, and says so once (#1662).
    const predicate = screen.getByTestId("review-diff-row-canonical_predicate");
    expect(predicate).toHaveAttribute("data-op", "delete");
    expect(predicate.querySelector(".review-diff__now")).toBeNull();
    expect(screen.getByTestId("review-the-change")).toHaveTextContent("Removes");
    // Bookkeeping fields of the deleted entity are not listed.
    expect(screen.queryByTestId("review-diff-row-version")).not.toBeInTheDocument();
  });

  it("marks an update's ends unknown when its property is gone, not 'any'", async () => {
    server.use(
      http.get("*/api/properties", () =>
        HttpResponse.json({ items: [], total: 0, limit: 1, offset: 0 }),
      ),
    );
    renderPage();
    const rename = await screen.findByTestId("operation-diff-op-rename");
    expect(await within(rename).findAllByText("deleted")).toHaveLength(4);
    expect(within(rename).queryByText("any")).not.toBeInTheDocument();
  });

  it("marks unknown ends '?' when the property lookup fails", async () => {
    server.use(
      http.get("*/api/properties", () => HttpResponse.json({ detail: "boom" }, { status: 500 })),
    );
    renderPage();
    const rename = await screen.findByTestId("operation-diff-op-rename");
    expect(await within(rename).findAllByText("?")).toHaveLength(4);
  });

  it("scrolls a deep-linked operation's row into view", async () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    renderPage("op-class");
    await screen.findByTestId("review-inspector");
    expect(scrollIntoView).toHaveBeenCalledTimes(1);
    expect(scrollIntoView.mock.contexts[0]).toHaveAttribute("data-row-id", "op-class");
  });

  it("has no decision controls for an operation already decided", async () => {
    renderPage("op-create");
    const inspector = await screen.findByTestId("review-inspector");
    expect(within(inspector).queryByTestId("operation-decision")).not.toBeInTheDocument();
    expect(
      within(inspector).queryByRole("button", { name: /accept|reject|edit|apply/i }),
    ).not.toBeInTheDocument();
  });

  it("is read-only once reverted: no decisions, selection, threshold or revert", async () => {
    server.use(
      http.get("*/api/proposals/:id", () =>
        HttpResponse.json({ ...openProposal, status: "reverted" }),
      ),
    );
    renderPage("op-rename");
    const inspector = await screen.findByTestId("review-inspector");
    expect(within(inspector).queryByTestId("operation-decision")).not.toBeInTheDocument();
    expect(screen.queryByTestId("proposal-actions")).not.toBeInTheDocument();
    expect(screen.queryByTestId("review-bulk-select")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operation-check-op-rename")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /accept|reject|revert|apply/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/This proposal was reverted/)).toBeInTheDocument();
  });

  it("shows not found for an unknown proposal", async () => {
    render(<ProposalDetailPage id="missing" onSelectOperation={vi.fn()} />);
    expect(await screen.findByText("Proposal not found")).toBeInTheDocument();
  });
});
