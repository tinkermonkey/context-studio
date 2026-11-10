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

describe("a class's operational definition in the inspector", () => {
  it("reads distinguish_from as class: when lines, before then after", async () => {
    renderPage("op-class");
    const row = await screen.findByTestId("operation-change-row-distinguish_from");
    expect(within(row).getByText("distinguish from")).toHaveClass("op-change__field");

    const before = row.querySelector(".op-change__before--changed") as HTMLElement;
    const after = row.querySelector(".op-change__after--changed") as HTMLElement;
    // The unknown class reads by its id; the sibling by its label once loaded.
    expect(linesOf(before)).toEqual(["class-gone: it was the old split"]);
    expect(
      await within(after).findByText("application_service: it is the behaviour, not the part"),
    ).toBeInTheDocument();
    expect(linesOf(after)).toEqual([
      "class-gone: it was the old split",
      "application_service: it is the behaviour, not the part",
    ]);
    expect(row).not.toHaveTextContent("class_id");
  });

  it("reads evidence signals as a numbered list and the standard as text", async () => {
    renderPage("op-class");
    const signals = await screen.findByTestId("operation-change-row-evidence_signals");
    const after = within(signals)
      .getAllByTestId("operation-change-lines-evidence_signals")
      .find((l) => l.closest(".op-change__after--changed"))!;
    expect(after.tagName).toBe("OL");
    expect(after).toHaveClass("op-change__lines", "op-change__lines--ordered");
    expect(linesOf(after)).toEqual(["Is deployed on its own", "Has a repository"]);

    const standard = screen.getByTestId("operation-change-row-standard_reference");
    expect(within(standard).getByText("standard reference")).toBeInTheDocument();
    expect(standard.querySelector(".op-change__before--changed")).toHaveTextContent("—");
    expect(standard.querySelector(".op-change__after--changed")).toHaveTextContent(
      "ArchiMate 3.2 §9.2",
    );
  });

  it("shows the operation's notes", async () => {
    renderPage("op-class");
    const notes = await screen.findByTestId("operation-notes");
    expect(notes).toHaveClass("op-inspector__notes");
    expect(notes.textContent).toBe("Checked against the 3.2 spec.\nKeep the old split for now.");
  });

  it("shows no notes section for an operation without notes", async () => {
    renderPage("op-rename");
    await screen.findByTestId("operation-rationale");
    expect(screen.queryByTestId("operation-notes")).not.toBeInTheDocument();
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
