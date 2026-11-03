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
    expect(screen.getByTestId("proposal-tally")).toHaveTextContent(
      "3 pending · 1 applied · 0 rejected · 0 failed",
    );
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

  it("renders each operation's change as a triple diff or field change", async () => {
    renderPage();

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

  it("shows op, plan kind, probability, status and stale chips", async () => {
    renderPage();
    await screen.findByTestId("operation-diff-op-rename");

    const table = screen.getByTestId("proposal-operations-table");
    expect(within(table).getByText("Plan kind")).toBeInTheDocument();
    const renameRow = screen.getByTestId("operation-diff-op-rename").closest("tr") as HTMLElement;
    expect(within(renameRow).getByText("update")).toHaveClass("chip--cyan");
    expect(within(renameRow).getByText("rename-predicate")).toHaveClass("op-plan-kind");
    expect(within(renameRow).getByText("0.82")).toHaveClass("op-probability");
    expect(
      within(screen.getByTestId("operation-status-op-rename")).getByText("pending"),
    ).toHaveClass("chip--amber");
    expect(screen.queryByTestId("operation-stale-op-rename")).not.toBeInTheDocument();
    expect(screen.getByTestId("operation-stale-op-delete")).toHaveClass("chip--rose");
    expect(
      within(screen.getByTestId("operation-status-op-create")).getByText("applied"),
    ).toHaveClass("chip--emerald");
  });

  it("leaves out the plan kind column when no operation has one", async () => {
    server.use(
      http.get("*/api/proposals/:id", () =>
        HttpResponse.json({ ...openProposal, operations: [createOperation] }),
      ),
    );
    renderPage();
    await screen.findByTestId("operation-diff-op-create");
    expect(screen.queryByText("Plan kind")).not.toBeInTheDocument();
  });

  it("selects an operation on row click, and clears it on a second click", async () => {
    const user = userEvent.setup();
    const { onSelectOperation, rerender } = renderPage();
    await user.click(await screen.findByTestId("operation-diff-op-rename"));
    expect(onSelectOperation).toHaveBeenLastCalledWith("op-rename");

    rerender(
      <ProposalDetailPage
        id="proposal-1"
        selectedOperationId="op-rename"
        onSelectOperation={onSelectOperation}
      />,
    );
    const row = screen.getByTestId("operation-diff-op-rename").closest("tr") as HTMLElement;
    expect(row).toHaveClass("table__row--selected");
    await user.click(row);
    expect(onSelectOperation).toHaveBeenLastCalledWith(undefined);
  });

  it("shows the selected operation in the inspector beside the table", async () => {
    const { container } = renderPage("op-rename");

    const inspector = await screen.findByTestId("operation-inspector");
    expect(container.querySelector('[data-testid="schema-page-layout"]')).toBeInTheDocument();
    expect(screen.getByTestId("schema-inspector-container")).toContainElement(inspector);
    expect(
      within(inspector).getByText("OPERATION · seq 1 · update · property"),
    ).toBeInTheDocument();

    const predicate = await screen.findByTestId("operation-change-row-canonical_predicate");
    // Stacked: the field name, then before (struck) above after (highlighted).
    expect(within(predicate).getByText("predicate")).toHaveClass("op-change__field");
    expect(within(predicate).getByText("realizes")).toHaveClass("op-change__before--changed");
    expect(within(predicate).getByText("serves")).toHaveClass("op-change__after--changed");
    expect(within(predicate).getByText("serves")).toHaveClass("op-change__value--id");

    expect(screen.getByTestId("operation-rationale")).toHaveTextContent("Rename the predicate.");
    expect(within(inspector).getByText("rename-predicate")).toHaveClass("chip--id-tag");
    expect(within(inspector).getByText("p 0.82")).toBeInTheDocument();
    expect(within(inspector).getByText("breaking")).toHaveClass("chip--rose");

    const evidence = screen.getByTestId("operation-evidence");
    expect(
      within(evidence).getByText("realizes and serves say the same thing here."),
    ).toBeInTheDocument();
    expect(within(evidence).getByText("node:x#3")).toHaveClass("op-evidence__caption");
    expect(within(evidence).getByText("https://example.com/spec")).toBeInTheDocument();
  });

  it("resolves a delete's class ids and warns when the operation is stale", async () => {
    renderPage("op-delete");

    expect(await screen.findByTestId("operation-stale-callout")).toHaveAttribute("role", "alert");
    const source = await screen.findByTestId("operation-change-row-domain_class_id");
    expect(within(source).getByText("source")).toBeInTheDocument();
    expect(await within(source).findByText("application_component")).toBeInTheDocument();
    // "removed" is said once, on the first row.
    const predicate = screen.getByTestId("operation-change-row-canonical_predicate");
    expect(within(predicate).getByText("removed")).toHaveClass("op-change__removed");
    expect(within(source).queryByText("removed")).not.toBeInTheDocument();
    // Bookkeeping fields of the deleted entity are not listed.
    expect(screen.queryByTestId("operation-change-row-version")).not.toBeInTheDocument();
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
    await screen.findByTestId("operation-inspector");
    expect(scrollIntoView).toHaveBeenCalledTimes(1);
    expect(scrollIntoView.mock.contexts[0]).toHaveAttribute("data-row-key", "op-class");
  });

  it("has no decision controls for an operation already decided", async () => {
    renderPage("op-create");
    const inspector = await screen.findByTestId("operation-inspector");
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
    const inspector = await screen.findByTestId("operation-inspector");
    expect(within(inspector).queryByTestId("operation-decision")).not.toBeInTheDocument();
    expect(screen.queryByTestId("proposal-actions")).not.toBeInTheDocument();
    expect(screen.queryByTestId("proposal-threshold-bar")).not.toBeInTheDocument();
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
