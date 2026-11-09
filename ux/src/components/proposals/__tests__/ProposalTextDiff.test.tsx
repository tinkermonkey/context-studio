/**
 * Text changes as a diff (#1454): a changed long text field (a definition) in
 * the inspector shows as Heimdall's line diff, marking the sentence that
 * changed; short values such as a rename stay inline.
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import { goldPage, openProposal, proposalHandlers } from "@/test/proposalFixtures";
import type { ChangeProposal } from "@/api/services/proposals";
import { ProposalDetailPage } from "../ProposalDetailPage";

const server = setupServer(...proposalHandlers, ...entityPageHandlers);

const BEFORE =
  "A modular, deployable part of a system. It exposes interfaces to other components. It is owned by one team.";
const AFTER =
  "A modular, deployable part of a system. It exposes services and interfaces to other components. It is owned by one team.";

let proposal: ChangeProposal;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  proposal = structuredClone(openProposal);
  const classOp = proposal.operations.find((o) => o.id === "op-class")!;
  classOp.base = { description: BEFORE };
  classOp.fields = { description: AFTER };
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

function rowsOf(diff: HTMLElement, type: string): string {
  return [...diff.querySelectorAll(`.side-by-side-diff__row--${type}`)]
    .map((r) => r.textContent)
    .join(" ");
}

describe("a changed definition in the inspector", () => {
  it("shows as a diff marking the sentence that changed", async () => {
    renderPage("op-class");
    const row = await screen.findByTestId("operation-change-row-description");
    const diff = within(row).getByTestId("operation-text-diff-description");
    expect(diff).toHaveClass("side-by-side-diff");
    expect(diff).toHaveAttribute("aria-label", "description: what changed");

    expect(rowsOf(diff, "removed")).toBe("It exposes interfaces to other components.");
    expect(rowsOf(diff, "added")).toBe("It exposes services and interfaces to other components.");
    // The unchanged sentences around it read as context, not as changes.
    expect(rowsOf(diff, "context")).toContain("It is owned by one team.");
    expect(rowsOf(diff, "removed")).not.toContain("owned by one team");
    // No plain before / after values for the field.
    expect(row.querySelector(".op-change__before--changed")).toBeNull();
  });

  it("keeps a whitespace-only change inline: a diff would mark nothing", async () => {
    const classOp = proposal.operations.find((o) => o.id === "op-class")!;
    classOp.base = { description: `${BEFORE}\n` };
    classOp.fields = { description: BEFORE };
    renderPage("op-class");
    const row = await screen.findByTestId("operation-change-row-description");
    expect(within(row).queryByTestId("operation-text-diff-description")).not.toBeInTheDocument();
    expect(row.querySelector(".op-change__after--changed")).toHaveTextContent(BEFORE);
  });

  it("keeps a short value change inline", async () => {
    renderPage("op-rename");
    const row = await screen.findByTestId("operation-change-row-identifier");
    expect(within(row).queryByTestId("operation-text-diff-identifier")).not.toBeInTheDocument();
    expect(row.querySelector(".op-change__before--changed")).toHaveTextContent(
      "component_realizes_service",
    );
    expect(row.querySelector(".op-change__after--changed")).toHaveTextContent(
      "component_serves_service",
    );
  });

  it("shows a long text a create sets as a plain value", async () => {
    const create = proposal.operations.find((o) => o.id === "op-create")!;
    create.fields = { ...create.fields, description: AFTER };
    renderPage("op-create");
    const row = await screen.findByTestId("operation-change-row-description");
    expect(within(row).queryByTestId("operation-text-diff-description")).not.toBeInTheDocument();
    expect(row).toHaveTextContent(AFTER);
  });
});
