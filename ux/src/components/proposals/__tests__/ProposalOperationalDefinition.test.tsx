/**
 * A definition-enrichment proposal (#1517) in the review queue (#1523): a
 * class update's operational-definition fields read as before → after, with
 * distinguish_from entries as "Class: when" lines named by class (an unknown
 * class by its id), evidence signals as a numbered list, and the operation's
 * maintainer notes.
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

let proposal: ChangeProposal;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  proposal = structuredClone(openProposal);
  const classOp = proposal.operations.find((o) => o.id === "op-class")!;
  classOp.base = {
    distinguish_from: [{ class_id: "class-gone", when: "it was the old split" }],
    evidence_signals: ["Has a repository"],
    standard_reference: null,
  };
  classOp.fields = {
    distinguish_from: [
      { class_id: "class-gone", when: "it was the old split" },
      { class_id: "class-2", when: "it is the behaviour, not the part" },
    ],
    evidence_signals: ["Is deployed on its own", "Has a repository"],
    standard_reference: "ArchiMate 3.2 §9.2",
  };
  classOp.notes = "Checked against the 3.2 spec.\nKeep the old split for now.";
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

const linesOf = (list: HTMLElement) =>
  within(list)
    .getAllByRole("listitem")
    .map((li) => li.textContent);

describe("a class's operational definition in the review inspector (#1660)", () => {
  it("reads distinguish_from as class: when lines, by what the list gains", async () => {
    renderPage("op-class");
    const row = await screen.findByTestId("review-diff-row-distinguish_from");
    expect(within(row).getByText("distinguish from")).toHaveClass("review-diff__field");
    // The sibling reads by its label once loaded; the entry both sides keep isn't repeated.
    const added = screen.getByTestId("review-diff-added-distinguish_from");
    expect(
      await within(added).findByText("application_service: it is the behaviour, not the part"),
    ).toBeInTheDocument();
    expect(linesOf(added)).toEqual(["application_service: it is the behaviour, not the part"]);
    expect(screen.queryByTestId("review-diff-removed-distinguish_from")).not.toBeInTheDocument();
    expect(row).not.toHaveTextContent("class_id");
  });

  it("reads evidence signals by what they gain and the standard as was → now", async () => {
    renderPage("op-class");
    const added = await screen.findByTestId("review-diff-added-evidence_signals");
    expect(linesOf(added)).toEqual(["Is deployed on its own"]);
    expect(screen.queryByTestId("review-diff-removed-evidence_signals")).not.toBeInTheDocument();

    const standard = screen.getByTestId("review-diff-row-standard_reference");
    expect(within(standard).getByText("standard reference")).toBeInTheDocument();
    expect(standard.querySelector(".review-diff__was")).toHaveTextContent("—");
    expect(standard.querySelector(".review-diff__now")).toHaveTextContent("ArchiMate 3.2 §9.2");
  });

  it("shows the operation's notes under Why", async () => {
    renderPage("op-class");
    const notes = await screen.findByTestId("review-why-notes");
    expect(notes).toHaveClass("review-why");
    expect(notes.textContent).toBe("Checked against the 3.2 spec.\nKeep the old split for now.");
  });
  it("shows no notes section for an operation without notes", async () => {
    renderPage("op-rename");
    await screen.findByTestId("review-why-rationale");
    expect(screen.queryByTestId("review-why-notes")).not.toBeInTheDocument();
  });
});

describe("a class's operational definition in the operation row", () => {
  it("reads distinguish_from as class: when text, not JSON", async () => {
    renderPage("op-class");
    const cell = await screen.findByTestId("operation-diff-op-class");
    expect(
      await within(cell).findByText(/application_service: it is the behaviour/),
    ).toBeInTheDocument();
    expect(cell).toHaveTextContent("distinguish from");
    expect(cell).not.toHaveTextContent("class_id");
  });
});
