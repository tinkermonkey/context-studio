/**
 * Colour means you have something to decide: an awaiting operation's flags are
 * amber or rose, a decided one's are neutral records; the banner counts what
 * still needs a decision (failed blocked deletes included) and filters the table.
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import { goldPage, openProposal, proposalHandlers } from "@/test/proposalFixtures";
import type { ChangeProposal, ProposedOperation } from "@/api/services/proposals";
import { ProposalDetailPage } from "../ProposalDetailPage";

const server = setupServer(...proposalHandlers, ...entityPageHandlers);

let proposal: ChangeProposal;

const end = (id: string, title: string) => ({ id, title, class_ids: [], class_titles: [] });
const blockers = {
  edges: [
    {
      relationship_id: "rel-1",
      source: end("a-1", "A1"),
      target: end("b-1", "B1"),
      attributes: {},
    },
    {
      relationship_id: "rel-2",
      source: end("a-2", "A2"),
      target: end("b-2", "B2"),
      attributes: {},
    },
  ],
  replacements: [],
};

const reversedCheck = {
  replacement_id: "prop-twin",
  property_id: "prop-twin",
  identifier: "service_realizes_component",
  title: "realizes",
  pair: "reversed",
  deleted_domain: { id: "class-1", title: "Component" },
  deleted_range: { id: "class-2", title: "Service" },
  domain: { id: "class-2", title: "Service" },
  range: { id: "class-1", title: "Component" },
  replacement_deleted: false,
  chain: [],
  cycle: false,
} as unknown as ProposedOperation["replacement_check"];

function opById(id: string): ProposedOperation {
  return proposal.operations.find((o) => o.id === id)!;
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
/** Apply request bodies, and the gold requests' query strings. */
let applied: { operation_ids: string[] }[];
let goldQueries: URLSearchParams[];

beforeEach(() => {
  proposal = structuredClone(openProposal);
  applied = [];
  goldQueries = [];
  server.use(
    http.get("*/api/proposals/:id", () => HttpResponse.json(proposal)),
    http.get("*/api/taxonomies/:id/gold", ({ request }) => {
      goldQueries.push(new URL(request.url).searchParams);
      return HttpResponse.json(goldPage(proposal.operations));
    }),
    http.post("*/api/proposals/:id/apply", async ({ request }) => {
      const body = (await request.json()) as { operation_ids: string[] };
      applied.push(body);
      for (const o of proposal.operations) {
        if (body.operation_ids.includes(o.id))
          Object.assign(o, { status: "applied", stale: false });
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

/** Every operation decided: the delete applied with its relationships moved to a reversed pair. */
function decideAll() {
  Object.assign(opById("op-delete"), {
    status: "applied",
    stale: true,
    replacement_check: reversedCheck,
    resolution: {
      strategy: "move",
      replacement_property_id: "prop-twin",
      replacement_identifier: "service_realizes_component",
      reversed: true,
      edges: [
        { relationship_id: "rel-1", source_id: "a-1", target_id: "b-1" },
        { relationship_id: "rel-2", source_id: "a-2", target_id: "b-2" },
      ],
    },
  });
  opById("op-rename").status = "rejected";
  Object.assign(opById("op-class"), {
    status: "applied",
    applied_fields: { description: "A deployable unit" },
  });
}

/** The 0-pending case: blocked delete and class update failed, rename still pending. */
function failSome() {
  Object.assign(opById("op-delete"), {
    status: "failed",
    stale: false,
    blockers,
    reason: "prop-1 is in use by 2 relationships",
  });
  Object.assign(opById("op-class"), { status: "failed", reason: "boom" });
}

describe("a proposal with everything decided", () => {
  it("says all are decided, tints the banner emerald and opens on All", async () => {
    decideAll();
    renderPage();

    const tally = await screen.findByTestId("proposal-tally");
    expect(tally).toHaveTextContent("All 4 decided");
    expect(screen.getByTestId("proposal-decided-counts")).toHaveTextContent(
      "3 applied · 1 rejected",
    );
    const summary = screen.getByTestId("proposal-summary");
    expect(summary).toHaveClass("proposal-summary", "proposal-summary--done");
    expect(summary).not.toHaveClass("proposal-summary--open");
    expect(screen.queryByTestId("proposal-progress-pills")).not.toBeInTheDocument();
    expect(within(summary).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
    expect(screen.queryByTestId("proposal-accept-all")).not.toBeInTheDocument();

    expect(screen.getByRole("radio", { name: "All · 4" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByTestId("proposal-operations-table")).toHaveAttribute("data-filter", "all");
  });

  it("shows each decision state and turns its flags neutral", async () => {
    decideAll();
    renderPage();

    const status = await screen.findByTestId("operation-status-op-delete");
    expect(status).toHaveAttribute("data-status", "applied");
    expect(status).toHaveAttribute("data-state", "applied");
    expect(screen.getByTestId("operation-state-op-delete")).toHaveTextContent("applied");
    expect(screen.getByTestId("operation-state-op-delete")).toHaveClass("chip--emerald");
    expect(screen.getByTestId("operation-stale-op-delete")).toHaveClass("chip--neutral");
    const pair = screen.getByTestId("operation-replacement-chip-op-delete");
    expect(within(pair).getByText("reversed pair")).toHaveClass("chip--neutral");
    expect(screen.queryByTestId("operation-blocked-op-delete")).not.toBeInTheDocument();
    const resolvedChip = screen.getByTestId("operation-resolved-op-delete");
    expect(resolvedChip).toHaveTextContent("moved 2 relationships");
    expect(resolvedChip).toHaveClass("chip--neutral");

    expect(screen.getByTestId("operation-state-op-class")).toHaveTextContent("applied with edits");
    expect(screen.getByTestId("operation-state-op-class")).toHaveClass("chip--emerald");
    expect(screen.queryByText("edited")).not.toBeInTheDocument();
    expect(screen.getByTestId("operation-state-op-rename")).toHaveTextContent("rejected");
    expect(screen.getByTestId("operation-state-op-rename")).toHaveClass("chip--neutral");

    const cell = screen.getByTestId("operation-diff-op-delete").closest(".op-change-cell");
    expect(cell).toHaveClass("op-change-cell--decided");
    expect(screen.queryByTestId("operation-check-op-delete")).not.toBeInTheDocument();
  });

  it("records the decision in the inspector: who, when, what it did", async () => {
    decideAll();
    const { container } = renderPage("op-delete");

    const decided = await screen.findByTestId("operation-decided");
    expect(container.querySelector('[data-testid="schema-page-layout"]')).toBeInTheDocument();
    expect(decided).toHaveAttribute("data-state", "applied");
    expect(within(decided).getByTestId("operation-decided-state")).toHaveClass("chip--emerald");
    expect(await within(decided).findByTestId("operation-decided-by")).toHaveTextContent(
      /^by you · Nov \d+, \d\d:\d\d$/,
    );
    expect(within(decided).getByTestId("operation-decided-record")).toHaveTextContent(
      "The replacement linked the pair reversed; 2 relationships moved to service_realizes_component with their ends swapped.",
    );
    expect(decided).toHaveTextContent("Nothing left to decide. Revert the proposal to undo it.");
    expect(screen.queryByTestId("operation-accept")).not.toBeInTheDocument();
    // Who and when come from the taxonomy's gold, filtered to this proposal.
    expect(goldQueries.at(-1)?.get("proposal_id")).toBe("proposal-1");
    // One state chip: the Decision section's, not repeated under Change.
    const inspector = screen.getByTestId("operation-inspector");
    expect(within(inspector).getAllByText("applied", { exact: true })).toHaveLength(1);

    const replacement = screen.getByTestId("operation-replacement");
    expect(within(replacement).getByText("reversed pair")).toHaveClass("chip--neutral");
    expect(within(replacement).getByTestId("operation-replacement-callout")).toHaveClass(
      "op-decided__note",
    );
    // A long replacement id ellipses inside the panel, with the full id as its title.
    const id = within(replacement).getByTestId("operation-replacement-id");
    expect(id).toHaveClass("chip", "op-replacement__id");
    expect(id).toHaveAttribute("title", "service_realizes_component");
    expect(id.querySelector(".op-replacement__id-text")).toHaveTextContent(
      "service_realizes_component",
    );
  });

  it("turns decided rows' op chips neutral", async () => {
    decideAll();
    renderPage();

    expect(await screen.findByTestId("operation-op-op-delete")).toHaveClass("chip--neutral");
    expect(screen.getByTestId("operation-op-op-class")).toHaveClass("chip--neutral");
  });

  it("reads a reverted proposal's applied operations as reverted, without who or when", async () => {
    decideAll();
    proposal.status = "reverted";
    renderPage("op-delete");

    const decided = await screen.findByTestId("operation-decided");
    expect(decided).toHaveAttribute("data-state", "reverted");
    expect(within(decided).getByTestId("operation-decided-state")).toHaveClass("chip--neutral");
    expect(within(decided).getByTestId("operation-decided-state")).toHaveTextContent("reverted");
    expect(decided).toHaveTextContent("The proposal was reverted, so this is undone.");
    expect(screen.getByTestId("operation-state-op-delete")).toHaveTextContent("reverted");
    expect(screen.getByTestId("operation-state-op-delete")).toHaveClass("chip--neutral");
    expect(screen.getByTestId("operation-state-op-rename")).toHaveTextContent("rejected");
    expect(within(decided).queryByTestId("operation-decided-by")).not.toBeInTheDocument();
    expect(goldQueries).toHaveLength(0);
    expect(screen.getByTestId("proposal-summary")).toHaveAttribute("class", "proposal-summary");
  });

  it("a rejected operation has nothing to revert", async () => {
    decideAll();
    renderPage("op-rename");

    const decided = await screen.findByTestId("operation-decided");
    expect(decided).toHaveAttribute("data-state", "rejected");
    expect(decided).toHaveTextContent("Nothing left to decide.");
    expect(decided).not.toHaveTextContent("Revert the proposal");
  });
});

describe("a proposal with decisions outstanding", () => {
  it("counts failed blocked deletes as needing a decision, with a pill each", async () => {
    failSome();
    renderPage();

    expect(await screen.findByTestId("proposal-tally")).toHaveTextContent("3 of 4 need a decision");
    expect(screen.getByTestId("proposal-summary")).toHaveClass("proposal-summary--open");
    const pills = screen.getByTestId("proposal-progress-pills");
    expect(pills).toHaveAttribute("role", "group");
    expect(
      within(screen.getByTestId("proposal-pill-to-decide")).getByText("1 to accept or reject"),
    ).toHaveClass("chip--amber");
    expect(
      within(screen.getByTestId("proposal-pill-need-choice")).getByText("1 need an in-use choice"),
    ).toHaveClass("chip--amber");
    expect(
      within(screen.getByTestId("proposal-pill-failed")).getByText("1 failed: retry or reject"),
    ).toHaveClass("chip--rose");
    expect(screen.queryByTestId("proposal-pill-stale")).not.toBeInTheDocument();
    expect(within(screen.getByTestId("proposal-summary")).getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "25",
    );
    // The rename and the failed class update are ready; the blocked delete waits for a choice.
    expect(screen.getByTestId("proposal-accept-all")).toHaveTextContent("Accept 2 ready");
  });

  it("marks the blocked delete as needing a choice, in amber", async () => {
    failSome();
    renderPage();

    const state = await screen.findByTestId("operation-state-op-delete");
    expect(state).toHaveTextContent("needs a choice");
    expect(state).toHaveClass("chip--amber");
    expect(screen.getByTestId("operation-status-op-delete")).toHaveAttribute(
      "data-status",
      "failed",
    );
    const inUse = screen.getByTestId("operation-blocked-op-delete");
    expect(inUse).toHaveTextContent("2 in use: move or drop");
    expect(inUse).toHaveClass("chip--amber");
    expect(screen.getByTestId("operation-state-op-class")).toHaveTextContent("failed");
    expect(screen.getByTestId("operation-state-op-class")).toHaveClass("chip--rose");
    expect(screen.getByTestId("operation-state-op-rename")).toHaveTextContent("needs decision");
    const cell = screen.getByTestId("operation-diff-op-rename").closest(".op-change-cell");
    expect(cell).not.toHaveClass("op-change-cell--decided");
  });

  it("opens on Needs decision, with checkboxes on awaiting rows only", async () => {
    failSome();
    const user = userEvent.setup();
    renderPage();

    const needs = await screen.findByRole("radio", { name: "Needs decision · 3" });
    expect(needs).toHaveAttribute("aria-checked", "true");
    expect(screen.queryByTestId("operation-diff-op-create")).not.toBeInTheDocument();
    expect(screen.getByTestId("operation-check-op-rename")).toBeInTheDocument();
    expect(screen.getByTestId("operation-check-op-delete")).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "Decided · 1" }));
    expect(screen.getByTestId("operation-diff-op-create")).toBeInTheDocument();
    expect(screen.queryByTestId("operation-diff-op-rename")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operation-check-op-create")).not.toBeInTheDocument();
  });

  it("a pill filters the table to what needs a decision", async () => {
    failSome();
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("radio", { name: "All · 4" }));
    expect(screen.getByTestId("operation-diff-op-create")).toBeInTheDocument();
    const pill = screen.getByTestId("proposal-pill-failed");
    expect(pill.tagName).toBe("BUTTON");
    expect(pill).toHaveAttribute("type", "button");
    expect(pill).toHaveAttribute("aria-controls", "proposal-operations");
    expect(pill).toHaveAccessibleName(
      "1 failed: retry or reject: show the operations that need a decision",
    );
    await user.click(pill);
    expect(screen.getByRole("radio", { name: "Needs decision · 3" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.queryByTestId("operation-diff-op-create")).not.toBeInTheDocument();
  });

  it("keeps the inspector when the selected row is filtered out", async () => {
    failSome();
    const user = userEvent.setup();
    const { container } = renderPage("op-rename");

    expect(await screen.findByTestId("operation-decision")).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Decided · 1" }));
    expect(screen.queryByTestId("operation-diff-op-rename")).not.toBeInTheDocument();
    expect(screen.getByTestId("operation-inspector")).toBeInTheDocument();
    expect(screen.getByTestId("operation-decision")).toBeInTheDocument();
    expect(container.querySelector('[data-testid="schema-page-layout"]')).toBeInTheDocument();
  });

  it("a deep link to a decided operation opens on All, so its row shows", async () => {
    failSome();
    renderPage("op-create");

    expect(await screen.findByTestId("operation-diff-op-create")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "All · 4" })).toHaveAttribute("aria-checked", "true");
    await waitFor(() =>
      expect(screen.getByTestId("operation-decided")).toHaveAttribute("data-state", "applied"),
    );
  });
});

describe("deciding from the banner and the table", () => {
  it("Accept N ready sends exactly the N ready operations", async () => {
    failSome();
    const user = userEvent.setup();
    renderPage();

    const accept = await screen.findByTestId("proposal-accept-all");
    expect(accept).toHaveTextContent("Accept 2 ready");
    await user.click(accept);
    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0].operation_ids).toHaveLength(2);
    expect([...applied[0].operation_ids].sort()).toEqual(["op-class", "op-rename"]);
  });

  it("deciding a deep-linked operation keeps the Needs decision filter", async () => {
    failSome();
    const user = userEvent.setup();
    renderPage("op-rename");

    const needs = await screen.findByRole("radio", { name: "Needs decision · 3" });
    expect(needs).toHaveAttribute("aria-checked", "true");
    await user.click(await screen.findByTestId("operation-accept"));
    await waitFor(() => expect(applied).toHaveLength(1));
    await waitFor(() =>
      expect(screen.getByRole("radio", { name: "Needs decision · 2" })).toHaveAttribute(
        "aria-checked",
        "true",
      ),
    );
    const table = screen.getByTestId("proposal-operations-table");
    expect(table).toHaveAttribute("data-filter", "needs");
    // The decided row left the table (the apply results above it still show its diff).
    expect(within(table).queryByTestId("operation-diff-op-rename")).not.toBeInTheDocument();
    expect(within(table).getByTestId("operation-diff-op-class")).toBeInTheDocument();
  });

  it("a filter that hides checked rows unchecks them", async () => {
    failSome();
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByTestId("operation-check-op-rename"));
    expect(screen.getByTestId("proposal-selection-count")).toHaveTextContent("1 selected");
    await user.click(screen.getByRole("radio", { name: "Decided · 1" }));
    expect(screen.queryByTestId("proposal-selection-bar")).not.toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Needs decision · 3" }));
    expect(screen.getByTestId("operation-check-op-rename")).not.toBeChecked();
    expect(screen.queryByTestId("proposal-selection-bar")).not.toBeInTheDocument();
  });

  it("reverting drops the cached who and when", async () => {
    decideAll();
    const user = userEvent.setup();
    server.use(
      http.post("*/api/proposals/:id/revert", () => {
        proposal.status = "reverted";
        return HttpResponse.json({ events_reverted: 3, proposal });
      }),
    );
    renderPage("op-delete");

    expect(await screen.findByTestId("operation-decided-by")).toBeInTheDocument();
    await user.click(screen.getByTestId("proposal-revert"));
    await user.click(screen.getByRole("button", { name: "Revert proposal" }));
    await waitFor(() =>
      expect(screen.getByTestId("operation-decided")).toHaveAttribute("data-state", "reverted"),
    );
    expect(screen.queryByTestId("operation-decided-by")).not.toBeInTheDocument();
  });
});
