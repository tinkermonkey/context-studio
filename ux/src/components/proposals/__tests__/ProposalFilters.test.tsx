/**
 * The operation filters (#1460): a rejected operation lists as decided, in the
 * flat table and the change-kind grouping, and the op and scope filters narrow
 * whichever primary filter is chosen, with counts, unchecking rows they hide.
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
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

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  proposal = structuredClone(openProposal);
  server.use(
    http.get("*/api/proposals/:id", () => HttpResponse.json(proposal)),
    http.get("*/api/taxonomies/:id/gold", () => HttpResponse.json(goldPage(proposal.operations))),
    http.post("*/api/proposals/:id/reject", async ({ request }) => {
      const body = (await request.json()) as { operation_ids: string[]; note: string | null };
      for (const op of proposal.operations) {
        if (body.operation_ids.includes(op.id)) {
          Object.assign(op, { status: "rejected", reason: body.note });
        }
      }
      return HttpResponse.json(proposal);
    }),
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

function table() {
  return screen.getByTestId("proposal-operations-table");
}

/** The row keys the table shows, in order (flat table or every grouped table and card). */
function shownIds(): string[] {
  const rows = [...table().querySelectorAll("tr[data-row-key]")].map(
    (r) => r.getAttribute("data-row-key")!,
  );
  const cards = [...table().querySelectorAll("[data-testid^='conflict-op-']")].map((e) =>
    e.getAttribute("data-testid")!.slice("conflict-op-".length),
  );
  return [...rows, ...cards];
}

async function pick(groupName: string, label: RegExp) {
  const group = screen.getByRole("group", { name: groupName });
  await userEvent.click(within(group).getByRole("radio", { name: label }));
}

const primary = (label: RegExp) => pick("Show operations", label);
const byOp = (label: RegExp) => pick("Show operations by op", label);
const byScope = (label: RegExp) => pick("Show operations by scope", label);

function options(groupName: string): string[] {
  const group = screen.getByRole("group", { name: groupName });
  return within(group)
    .getAllByRole("radio")
    .map((r) => r.textContent ?? "");
}

describe("a rejected operation lists as decided", () => {
  it("shows under Decided and All in the flat table", async () => {
    const user = userEvent.setup();
    renderPage("op-rename");

    await user.click(await screen.findByTestId("operation-reject"));
    await waitFor(() =>
      expect(within(table()).queryByTestId("operation-diff-op-rename")).not.toBeInTheDocument(),
    );
    expect(table()).toHaveAttribute("data-filter", "needs");

    await primary(/^Decided · 2$/);
    expect(shownIds()).toEqual(["op-rename", "op-create"]);
    expect(within(table()).getByTestId("operation-diff-op-rename")).toBeInTheDocument();

    await primary(/^All · 4$/);
    expect(shownIds()).toEqual(["op-rename", "op-delete", "op-create", "op-class"]);
  });

  it("shows under Decided and All in the change-kind grouping, conflict members included", async () => {
    proposal = reflectionProposal();
    const user = userEvent.setup();
    renderPage("m-dup");
    await screen.findByTestId("tiered-operations");

    await user.click(await screen.findByTestId("operation-reject"));
    await waitFor(() => expect(shownIds()).not.toContain("m-dup"));

    await primary(/^Decided/);
    expect(shownIds()).toEqual(["m-dup"]);
    await primary(/^All/);
    expect(shownIds()).toContain("m-dup");
    expect(shownIds()).toHaveLength(proposal.operations.length);

    // A rejected conflict member lists as decided too, in its card.
    await user.click(screen.getByTestId("conflict-reject-all-c-rename"));
    await waitFor(() =>
      expect(
        within(screen.getByTestId("conflict-op-c-rename")).getByText("rejected"),
      ).toBeVisible(),
    );
    await primary(/^Decided/);
    expect(shownIds()).toEqual(expect.arrayContaining(["m-dup", "c-rename", "c-delete"]));
    await primary(/^All/);
    expect(shownIds()).toHaveLength(proposal.operations.length);
  });
});

describe("op and scope filters", () => {
  // openProposal: op-rename update/breaking, op-delete delete/breaking,
  // op-create create/additive (applied), op-class update/editorial.

  it("count what each choice would show under the primary filter", async () => {
    renderPage();
    await screen.findByTestId("proposal-op-filter");

    expect(table()).toHaveAttribute("data-filter", "needs");
    expect(options("Show operations by op")).toEqual([
      "Any op",
      "create · 0",
      "update · 2",
      "delete · 1",
    ]);
    expect(options("Show operations by scope")).toEqual([
      "Any scope",
      "breaking · 2",
      "additive · 0",
      "editorial · 1",
    ]);

    await primary(/^Decided/);
    expect(options("Show operations by op")).toEqual([
      "Any op",
      "create · 1",
      "update · 0",
      "delete · 0",
    ]);
    expect(options("Show operations by scope")).toEqual([
      "Any scope",
      "breaking · 0",
      "additive · 1",
      "editorial · 0",
    ]);

    await primary(/^All/);
    expect(options("Show operations by op")).toEqual([
      "Any op",
      "create · 1",
      "update · 2",
      "delete · 1",
    ]);
    expect(options("Show operations by scope")).toEqual([
      "Any scope",
      "breaking · 2",
      "additive · 1",
      "editorial · 1",
    ]);
  });

  it("narrows Needs decision by op, then by scope, and counts each by the other", async () => {
    renderPage();
    await screen.findByTestId("proposal-op-filter");

    await byOp(/^update/);
    expect(shownIds()).toEqual(["op-rename", "op-class"]);
    expect(options("Show operations by scope")).toEqual([
      "Any scope",
      "breaking · 1",
      "additive · 0",
      "editorial · 1",
    ]);

    await byScope(/^editorial/);
    expect(shownIds()).toEqual(["op-class"]);
    expect(options("Show operations by op")).toEqual([
      "Any op",
      "create · 0",
      "update · 1",
      "delete · 0",
    ]);

    await byOp(/^delete/);
    expect(shownIds()).toEqual([]);
    expect(screen.getByText("No operations match these filters.")).toBeInTheDocument();

    await byOp(/^Any op/);
    await byScope(/^Any scope/);
    expect(shownIds()).toEqual(["op-rename", "op-delete", "op-class"]);
  });

  it("narrows Decided by op and scope", async () => {
    renderPage();
    await screen.findByTestId("proposal-op-filter");
    await primary(/^Decided/);

    await byOp(/^create/);
    expect(shownIds()).toEqual(["op-create"]);
    await byScope(/^additive/);
    expect(shownIds()).toEqual(["op-create"]);
    await byScope(/^breaking/);
    expect(shownIds()).toEqual([]);
  });

  it("narrows All by op and scope", async () => {
    renderPage();
    await screen.findByTestId("proposal-op-filter");
    await primary(/^All/);

    await byScope(/^breaking/);
    expect(shownIds()).toEqual(["op-rename", "op-delete"]);
    await byOp(/^delete/);
    expect(shownIds()).toEqual(["op-delete"]);
    await byScope(/^Any scope/);
    await byOp(/^update/);
    expect(shownIds()).toEqual(["op-rename", "op-class"]);
  });

  it("keep narrowing when the primary filter changes", async () => {
    renderPage();
    await screen.findByTestId("proposal-op-filter");

    await byScope(/^breaking/);
    expect(shownIds()).toEqual(["op-rename", "op-delete"]);
    await primary(/^Decided/);
    expect(shownIds()).toEqual([]);
    await primary(/^All/);
    expect(shownIds()).toEqual(["op-rename", "op-delete"]);
  });

  it("narrow the change-kind grouping too", async () => {
    proposal = reflectionProposal();
    renderPage();
    await screen.findByTestId("tiered-operations");
    const deletes = proposal.operations
      .filter((o) => o.op === "delete" && !o.id.startsWith("c-"))
      .map((o) => o.id);

    await byOp(/^delete/);
    const rows = [...table().querySelectorAll("tr[data-row-key]")].map((r) =>
      r.getAttribute("data-row-key"),
    );
    expect(rows.sort()).toEqual([...deletes].sort());
    // A conflict card shows all its members while the filter shows any of them (c-delete).
    expect(screen.getByTestId("conflict-card-c-rename")).toBeInTheDocument();

    await byOp(/^update/);
    expect(screen.getByTestId("conflict-card-c-rename")).toBeInTheDocument();
    expect(table().querySelector("tr[data-row-key='m-dup']")).toBeNull();
  });

  it("uncheck the rows they hide", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByTestId("operation-check-op-rename"));
    await user.click(screen.getByTestId("operation-check-op-class"));
    expect(screen.getByTestId("operation-check-op-rename")).toBeChecked();

    await byScope(/^editorial/);
    expect(screen.queryByTestId("operation-check-op-rename")).not.toBeInTheDocument();
    expect(screen.getByTestId("operation-check-op-class")).toBeChecked();

    await byScope(/^Any scope/);
    expect(screen.getByTestId("operation-check-op-rename")).not.toBeChecked();
    expect(screen.getByTestId("operation-check-op-class")).toBeChecked();
  });

  it("are left out when the proposal has a single op and scope", async () => {
    proposal.operations = proposal.operations.filter((o) => o.id === "op-rename");
    renderPage();
    await screen.findByTestId("operation-diff-op-rename");
    expect(screen.queryByTestId("proposal-op-filter")).not.toBeInTheDocument();
    expect(screen.queryByTestId("proposal-scope-filter")).not.toBeInTheDocument();
  });
});
