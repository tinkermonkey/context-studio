/**
 * The review inspector learns the operations it never showed (#1660): an
 * update, a move or a delete reads as THE CHANGE (was → now, a word diff for
 * long text, what a list gains and loses), WHY (rationale, plan kind, p, scope,
 * origin) and captioned evidence; stale and failed operations offer Apply
 * anyway and Apply again with a callout; Reject offers the reason codes that fit
 * the operation; a decided one shows its record and who decided it.
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import { goldPage, proposalHandlers } from "@/test/proposalFixtures";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";
import type {
  ChangeProposal,
  ChangeProposalApplyRequest,
  ChangeProposalRejectRequest,
} from "@/api/services/proposals";
import { ProposalDetailPage } from "../ProposalDetailPage";

const server = setupServer(...proposalHandlers, ...entityPageHandlers);

const LONG_BEFORE =
  "A modular, deployable part of a system that is owned by one team and exposes its interfaces to other parts.";
const LONG_AFTER =
  "A modular, deployable part of a system that is owned by one team and exposes its services to other parts.";

const update = createProposedOperation({
  id: "op-update",
  seq: 1,
  op: "update",
  kind: "class",
  target_id: "class-1",
  base: { title: "Component", description: LONG_BEFORE },
  fields: { title: "Application Component", description: LONG_AFTER },
  rationale: "Plan kind rename. The DR spec calls it an application component.",
  probability: 0.82,
  scope: "editorial",
  evidence: [{ quote: "ApplicationComponent: a modular part", claim_id: "claim-7" }],
});
const retype = createProposedOperation({
  id: "op-retype",
  seq: 2,
  op: "update",
  kind: "individual",
  target_id: "ind-1",
  base: { title: "LLM Provider Router", class_ids: ["class-1"] },
  fields: { class_ids: ["class-2"] },
  scope: "breaking",
});
const stale = createProposedOperation({
  id: "op-stale",
  seq: 3,
  op: "update",
  kind: "class",
  target_id: "class-2",
  base: { description: "Exposed behavior" },
  fields: { description: "Behavior a component exposes" },
  stale: true,
  reason: "target_changed: description changed since proposed",
});
const failed = createProposedOperation({
  id: "op-failed",
  seq: 4,
  op: "update",
  kind: "class",
  target_id: "class-2",
  base: { title: "ApplicationService" },
  fields: { title: "Application Service" },
  status: "failed",
  reason: "conflict: the identifier is taken",
});
const removal = createProposedOperation({
  id: "op-delete",
  seq: 5,
  op: "delete",
  kind: "class",
  target_id: "class-2",
  base: { title: "ApplicationService", description: "Exposed behavior" },
  fields: undefined,
  scope: "breaking",
});
const applied = createProposedOperation({
  id: "op-applied",
  seq: 6,
  op: "update",
  kind: "class",
  target_id: "class-1",
  base: { title: "Component" },
  fields: { title: "Part" },
  status: "applied",
});
const reorder = createProposedOperation({
  id: "op-reorder",
  seq: 7,
  op: "update",
  kind: "individual",
  target_id: "ind-1",
  base: { title: "LLM Provider Router", class_ids: ["class-1", "class-2"] },
  fields: { class_ids: ["class-2", "class-1"] },
});
const move = createProposedOperation({
  id: "op-move",
  seq: 8,
  op: "move",
  kind: "class",
  target_id: "class-2",
  base: { parent_class_id: null },
  fields: { parent_class_id: "class-1" },
  rationale: "A service sits under the component that exposes it.",
});

let proposal: ChangeProposal;
let applies: ChangeProposalApplyRequest[];
let rejects: ChangeProposalRejectRequest[];

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  proposal = createChangeProposal({
    id: "proposal-1",
    taxonomy_id: "tax-1",
    title: "Align with the DR spec",
    source: "mcp",
    source_detail: "dr-cli",
    status: "open",
    operations: structuredClone([update, retype, stale, failed, removal, applied, reorder, move]),
  });
  applies = [];
  rejects = [];
  server.use(
    http.get("*/api/proposals/:id", () => HttpResponse.json(proposal)),
    http.get("*/api/taxonomies/:id/gold", () => HttpResponse.json(goldPage(proposal.operations))),
    http.post("*/api/proposals/:id/apply", async ({ request }) => {
      const body = (await request.json()) as ChangeProposalApplyRequest;
      applies.push(body);
      for (const op of proposal.operations) {
        if (body.operation_ids.includes(op.id)) Object.assign(op, { status: "applied" });
      }
      return HttpResponse.json(proposal);
    }),
    http.post("*/api/proposals/:id/reject", async ({ request }) => {
      const body = (await request.json()) as ChangeProposalRejectRequest;
      rejects.push(body);
      for (const op of proposal.operations) {
        if (body.operation_ids?.includes(op.id)) Object.assign(op, { status: "rejected" });
      }
      return HttpResponse.json(proposal);
    }),
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

describe("an update in the review inspector", () => {
  it("reads its change as was → now rows, long text as one word diff", async () => {
    const { container } = renderPage("op-update");
    const inspector = await screen.findByTestId("review-inspector", {}, { timeout: 10000 });
    expect(container.querySelector('[data-testid="schema-page-layout"]')).toHaveClass("split-2");
    expect(inspector).toHaveAttribute("aria-label", "Selected operation");
    expect(screen.getByTestId("review-inspector-eyebrow")).toHaveTextContent(
      "update · class · seq 1",
    );
    expect(screen.getByTestId("review-inspector-status")).toHaveTextContent("needs decision");

    const title = screen.getByTestId("review-diff-row-title");
    expect(title.querySelector(".review-diff__was")).toHaveTextContent("Component");
    expect(title.querySelector(".review-diff__now")).toHaveTextContent("Application Component");

    const words = screen.getByTestId("review-diff-text-description");
    expect([...words.querySelectorAll("del")].map((e) => e.textContent)).toEqual(["interfaces"]);
    expect([...words.querySelectorAll("ins")].map((e) => e.textContent)).toEqual(["services"]);
  });

  it("says why: the rationale, the plan kind, p, scope and who proposed it", async () => {
    renderPage("op-update");
    expect(await screen.findByTestId("review-why-rationale")).toHaveTextContent(
      "The DR spec calls it an application component.",
    );
    const chips = screen.getByTestId("review-why-chips");
    expect(chips).toHaveTextContent("rename");
    expect(chips).toHaveTextContent("p 0.82");
    expect(chips).toHaveTextContent("editorial");
    expect(chips).toHaveTextContent("mcp · dr-cli");
  });

  it("shows a sourceless proposal's evidence as quotes with captions", async () => {
    renderPage("op-update");
    const quote = await screen.findByTestId("review-quote-1");
    expect(quote.querySelector("blockquote")).toHaveTextContent(
      "ApplicationComponent: a modular part",
    );
    expect(quote.querySelector("figcaption")).toHaveTextContent("claim-7");
  });

  it("reads a type change as the classes the individual loses and gains", async () => {
    renderPage("op-retype");
    const removed = await screen.findByTestId("review-diff-removed-class_ids");
    // A DR class reads by its DR reference, as its pill does everywhere.
    await waitFor(() => expect(removed).toHaveTextContent("application.component"));
    expect(screen.getByTestId("review-diff-added-class_ids")).toHaveTextContent(
      "ApplicationService",
    );
  });

  it("reads a list whose items only moved as was → now, labelled Reordered", async () => {
    renderPage("op-reorder");
    const row = await screen.findByTestId("review-diff-row-class_ids");
    expect(within(row).getByTestId("review-diff-reordered-class_ids")).toHaveTextContent(
      "Reordered",
    );
    expect(within(row).queryByTestId("review-diff-added-class_ids")).not.toBeInTheDocument();
    expect(within(row).queryByTestId("review-diff-removed-class_ids")).not.toBeInTheDocument();
    expect(row.querySelector(".review-diff__was")).not.toBeEmptyDOMElement();
    expect(row.querySelector(".review-diff__now")).not.toBeEmptyDOMElement();
  });

  it("is accepted with Accept, and rejected with the reasons that fit an update", async () => {
    const user = userEvent.setup();
    renderPage("op-update");
    expect(await screen.findByTestId("review-correct")).toHaveTextContent(/^Accept$/);
    await user.click(screen.getByTestId("review-not"));
    expect(screen.getByTestId("review-not")).toHaveTextContent(/^Reject$/);
    const reasons = screen.getByRole("group", { name: "Reject it, because" });
    expect(
      within(reasons)
        .getAllByRole("button")
        .map((b) => b.textContent),
    ).toEqual(["Out of scope", "Wrong", "Keep as it is", "Out of date", "Other"]);
    expect(screen.getByTestId("review-reason-out_of_scope")).toHaveFocus();
    await user.click(screen.getByTestId("review-reason-keep_current"));
    await waitFor(() => expect(rejects).toHaveLength(1));
    expect(rejects[0]).toMatchObject({ operation_ids: ["op-update"], reason_code: "keep_current" });
  });

  it("accepts it", async () => {
    const user = userEvent.setup();
    renderPage("op-update");
    await user.click(await screen.findByTestId("review-correct"));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].operation_ids).toEqual(["op-update"]);
  });
});

describe("stale and failed operations", () => {
  it("offers Apply anyway for a stale one, says why, and leads its reasons with Out of date", async () => {
    const user = userEvent.setup();
    renderPage("op-stale");
    expect(await screen.findByTestId("review-stale-callout")).toHaveTextContent(
      "description changed since it was proposed. Apply anyway keeps the proposed values over those changes.",
    );
    expect(screen.getByTestId("review-correct")).toHaveTextContent("Apply anyway");
    await user.click(screen.getByTestId("review-not"));
    expect(screen.getByTestId("review-reason-outdated")).toHaveFocus();
  });

  it("applies a stale one with force_stale once Apply anyway is confirmed", async () => {
    const user = userEvent.setup();
    renderPage("op-stale");
    await user.click(await screen.findByTestId("review-correct"));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByTestId("proposal-force-message")).toHaveTextContent(
      "description changed since it was proposed.",
    );
    // Nothing is sent before the confirmation.
    expect(applies).toHaveLength(0);
    await user.click(within(dialog).getByRole("button", { name: "Apply anyway" }));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0]).toMatchObject({ operation_ids: ["op-stale"], force_stale: ["op-stale"] });
  });

  it("offers Apply again for a failed one, with the failure", async () => {
    renderPage("op-failed");
    expect(await screen.findByTestId("review-failed")).toHaveTextContent(
      "The last apply failed: conflict: the identifier is taken",
    );
    expect(screen.getByTestId("review-correct")).toHaveTextContent("Apply again");
  });

  it("applies a failed one again on Apply again, with no force", async () => {
    const user = userEvent.setup();
    renderPage("op-failed");
    await user.click(await screen.findByTestId("review-correct"));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0]).toMatchObject({ operation_ids: ["op-failed"], force_stale: [] });
  });
});

describe("a class move", () => {
  it("reads as the parent it had and the one it moves under, and is accepted", async () => {
    const user = userEvent.setup();
    renderPage("op-move");
    const row = await screen.findByTestId("review-diff-row-parent_class_id");
    await waitFor(() =>
      expect(row.querySelector(".review-diff__now")).toHaveTextContent("application.component"),
    );
    expect(screen.getByTestId("review-why-rationale")).toHaveTextContent(
      "A service sits under the component that exposes it.",
    );
    expect(screen.getByTestId("review-correct")).toHaveTextContent(/^Accept$/);
    await user.click(screen.getByTestId("review-correct"));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0]).toMatchObject({ operation_ids: ["op-move"], force_stale: [] });
  });
});

describe("a delete", () => {
  it("lists what it removes", async () => {
    renderPage("op-delete");
    const row = await screen.findByTestId("review-diff-row-description");
    expect(row).toHaveAttribute("data-op", "delete");
    expect(row.querySelector(".review-diff__was")).toHaveTextContent("Exposed behavior");
    expect(row.querySelector(".review-diff__now")).toBeNull();
    expect(screen.getByTestId("review-the-change")).toHaveTextContent("Removes ApplicationService");
  });
});

describe("a decided operation", () => {
  it("shows its record and who decided it, with no decision to change", async () => {
    renderPage("op-applied");
    expect(await screen.findByTestId("review-decided")).toHaveAttribute("data-state", "applied");
    expect(screen.getByTestId("review-inspector-status")).toHaveTextContent("applied");
    expect(await screen.findByTestId("review-decided-by")).toHaveTextContent("by you");
    expect(screen.getByTestId("review-change-note")).toHaveTextContent(
      "Nothing left to decide. Revert the proposal to undo it.",
    );
    // Only an individual or relationship create can be reopened.
    expect(screen.queryByTestId("review-change-decision")).not.toBeInTheDocument();
    expect(screen.queryByTestId("review-decide")).not.toBeInTheDocument();
  });
});
