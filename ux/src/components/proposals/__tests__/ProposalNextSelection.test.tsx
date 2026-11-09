/**
 * Deciding row after row (#1458): once a decision drops the selected
 * operation out of Needs decision, the row below it is selected and the
 * inspector shows it; the new last row when it was last; nothing when the list
 * is empty. Filter changes and deep links move nothing.
 */
import { useState } from "react";
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import { goldPage, openProposal, proposalHandlers } from "@/test/proposalFixtures";
import { reflectionProposal } from "@/test/reflectionFixtures";
import type { ChangeProposal } from "@/api/services/proposals";
import { ProposalDetailPage } from "../ProposalDetailPage";

const server = setupServer(...proposalHandlers, ...entityPageHandlers);

let proposal: ChangeProposal;

function decide(ids: string[], status: "applied" | "rejected") {
  for (const op of proposal.operations) {
    if (ids.includes(op.id)) Object.assign(op, { status, stale: false });
  }
  return HttpResponse.json(proposal);
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  proposal = structuredClone(openProposal);
  server.use(
    http.get("*/api/proposals/:id", () => HttpResponse.json(proposal)),
    http.get("*/api/taxonomies/:id/gold", () => HttpResponse.json(goldPage(proposal.operations))),
    http.post("*/api/proposals/:id/apply", async ({ request }) => {
      const body = (await request.json()) as { operation_ids: string[] };
      return decide(body.operation_ids, "applied");
    }),
    http.post("*/api/proposals/:id/reject", async ({ request }) => {
      const body = (await request.json()) as { operation_ids: string[] };
      return decide(body.operation_ids, "rejected");
    }),
  );
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

/** The harness's selection as last rendered. */
let current: string | undefined;

/** The page with its selection kept in state, as the route keeps it in ?op=. */
function Harness({ initial }: { initial?: string }) {
  const [selected, setSelected] = useState(initial);
  current = selected;
  return (
    <ProposalDetailPage
      id="proposal-1"
      selectedOperationId={selected}
      onSelectOperation={setSelected}
    />
  );
}

function selected() {
  return current ?? "none";
}

/** The inspector's operation id line. */
async function inspected(id: string) {
  const inspector = await screen.findByTestId("operation-inspector");
  await waitFor(() => expect(within(inspector).getByText(id)).toBeInTheDocument());
}

function selectedRow() {
  return document.querySelector("tr.table__row--selected")?.getAttribute("data-row-key");
}

// openProposal under Needs decision: op-rename (seq 1), op-delete (seq 2, stale), op-class (seq 4).

describe("after a decision under Needs decision", () => {
  it("selects the row below the decided one and shows it in the inspector", async () => {
    render(<Harness initial="op-rename" />);
    await userEvent.click(await screen.findByTestId("operation-reject"));

    await waitFor(() => expect(selected()).toBe("op-delete"));
    await inspected("op-delete");
    expect(selectedRow()).toBe("op-delete");
    expect(screen.getByTestId("proposal-operations-table")).toHaveAttribute("data-filter", "needs");
  });

  it("selects the next row after an accept too", async () => {
    render(<Harness initial="op-rename" />);
    await userEvent.click(await screen.findByTestId("operation-accept"));

    await waitFor(() => expect(selected()).toBe("op-delete"));
    await inspected("op-delete");
  });

  it("selects the new last row when the decided row was last", async () => {
    render(<Harness initial="op-class" />);
    await userEvent.click(await screen.findByTestId("operation-reject"));

    await waitFor(() => expect(selected()).toBe("op-delete"));
    await inspected("op-delete");
    expect(selectedRow()).toBe("op-delete");
  });

  it("clears the selection when nothing is left to decide", async () => {
    proposal.operations = proposal.operations.filter((o) =>
      ["op-rename", "op-create"].includes(o.id),
    );
    // Pick Needs decision, so the filter stays there once nothing awaits.
    render(<Harness initial="op-rename" />);
    await userEvent.click(
      within(await screen.findByRole("group", { name: "Show operations" })).getByText(
        /^Needs decision/,
      ),
    );
    await userEvent.click(screen.getByTestId("operation-reject"));

    await waitFor(() => expect(selected()).toBe("none"));
    expect(screen.queryByTestId("operation-inspector")).not.toBeInTheDocument();
  });

  it("selects the next row when a bulk decision covered the selected one", async () => {
    render(<Harness initial="op-rename" />);
    await userEvent.click(await screen.findByTestId("operation-check-op-rename"));
    await userEvent.click(screen.getByTestId("operation-check-op-delete"));
    await userEvent.click(screen.getByTestId("proposal-selection-reject"));

    await waitFor(() => expect(selected()).toBe("op-class"));
    await inspected("op-class");
  });

  it("follows the change-kind grouping's order, across sections", async () => {
    proposal = reflectionProposal();
    // Mechanical: m-dup; rename-predicate m-rename, m-blocked; reverse m-reverse, m-stale.
    // Judgment: j-retarget, j-compound. Conflicts: c-rename, c-delete.
    render(<Harness initial="m-blocked" />);
    await screen.findByTestId("tiered-operations");
    await userEvent.click(await screen.findByTestId("operation-reject"));
    await waitFor(() => expect(selected()).toBe("m-reverse"));
    await inspected("m-reverse");

    // The last mechanical row moves on into the judgment section.
    await userEvent.click(document.querySelector<HTMLElement>("tr[data-row-key='m-stale']")!);
    await waitFor(() => expect(selected()).toBe("m-stale"));
    await userEvent.click(await screen.findByTestId("operation-reject"));
    await waitFor(() => expect(selected()).toBe("j-retarget"));
    await inspected("j-retarget");
  });
});

describe("moving past decided conflict members", () => {
  it("skips a conflict card's decided member for the next awaiting one", async () => {
    proposal = reflectionProposal();
    proposal.operations.find((o) => o.id === "c-rename")!.status = "rejected";
    // The last judgment row; the conflict card below lists c-rename (rejected), then c-delete.
    render(<Harness initial="j-compound" />);
    await screen.findByTestId("tiered-operations");
    await userEvent.click(await screen.findByTestId("operation-reject"));

    await waitFor(() => expect(selected()).toBe("c-delete"));
    await inspected("c-delete");
  });
});

describe("selection that stays put", () => {
  it("stays on the last decided operation when the default filter moves to All", async () => {
    proposal.operations = proposal.operations.filter((o) =>
      ["op-rename", "op-create"].includes(o.id),
    );
    render(<Harness initial="op-rename" />);
    await userEvent.click(await screen.findByTestId("operation-reject"));

    await waitFor(() =>
      expect(screen.getByTestId("proposal-operations-table")).toHaveAttribute("data-filter", "all"),
    );
    expect(selected()).toBe("op-rename");
    await inspected("op-rename");
  });

  it("doesn't move when the filter changes", async () => {
    proposal.operations[0].status = "applied";
    render(<Harness initial="op-rename" />);
    // A deep link to a decided operation opens on All.
    expect(await screen.findByTestId("proposal-operations-table")).toHaveAttribute(
      "data-filter",
      "all",
    );
    await inspected("op-rename");

    await userEvent.click(
      within(screen.getByRole("group", { name: "Show operations" })).getByText(/^Needs decision/),
    );
    expect(selected()).toBe("op-rename");
    await inspected("op-rename");
  });

  it("doesn't move after a decision under All", async () => {
    render(<Harness initial="op-rename" />);
    await userEvent.click(
      within(await screen.findByRole("group", { name: "Show operations" })).getByText(/^All/),
    );
    await userEvent.click(screen.getByTestId("operation-reject"));

    await waitFor(() => expect(screen.queryByTestId("operation-decision")).not.toBeInTheDocument());
    expect(selected()).toBe("op-rename");
  });
});
