/**
 * An extraction proposal on its own page (#1555, #1658): its creates open the
 * review inspector, with the quotes as evidence, a near match's "Already in
 * dataset …?" choice sent as chosen_alternatives, and a relationship that waits
 * on the creates it names; the banner's near-match and low-confidence pills;
 * and bulk accepts that leave near matches (and what names them) for the reviewer.
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
import type { ChangeProposal, ChangeProposalApplyRequest } from "@/api/services/proposals";
import type { Source, SourceText } from "@/api/services/sources";
import { useToasts } from "@/components/ui/Toast";
import { ProposalDetailPage } from "../ProposalDetailPage";

const server = setupServer(...proposalHandlers, ...entityPageHandlers);

// Page 2 starts at offset 100; "French door fridge" sits at 110–128.
const PAGE_TEXT = "Thank you French door fridge comes with parts.";

const source: Source = {
  id: "src-1",
  taxonomy_id: "tax-1",
  dataset_id: "ds-1",
  kind: "pdf",
  title: "Whirlpool use and care guide",
  origin: "wrf555sdfz.pdf",
  content_type: "application/pdf",
  bytes: 1000,
  pages: 3,
  chars: 300,
  page_starts: [0, 100, 200],
  headings: [{ start: 100, title: "Parts and features", level: 1 }],
  status: "ready",
  failure: null,
  failure_detail: null,
  created_at: "2026-11-10T12:00:00Z",
  updated_at: "2026-11-10T12:00:00Z",
  removed_at: null,
};

const fridge = createProposedOperation({
  id: "op-fridge",
  seq: 1,
  op: "create",
  kind: "individual",
  target_id: null,
  ref: "fridge",
  fields: { title: "Whirlpool WRF555SDFZ", class_ids: ["class-1"] },
  evidence: [
    { source_id: "src-1", page: 2, start: 110, end: 128, quote: "French door fridge" },
    { source_id: "src-1", page: 3, start: 210, end: 220, quote: "WRF555SDFZ" },
  ],
  alternatives: [
    { kind: "existing", entity_id: "ind-1", similarity: 0.93, title: "LLM Provider Router" },
  ],
  probability: 0.94,
  scope: "additive",
});
const filter = createProposedOperation({
  id: "op-filter",
  seq: 2,
  op: "create",
  kind: "individual",
  target_id: null,
  ref: "filter",
  fields: { title: "EveryDrop Filter 1", class_ids: ["class-1"] },
  // Its offsets lie outside the page's text: the quote shows alone.
  evidence: [{ source_id: "src-1", page: 2, start: 190, end: 199, quote: "EveryDrop" }],
  probability: 0.4,
  scope: "additive",
});
const uses = createProposedOperation({
  id: "op-uses",
  seq: 3,
  op: "create",
  kind: "relationship",
  target_id: null,
  fields: { property_definition_id: "prop-1", source_id: "$fridge", target_id: "$filter" },
  probability: 0.9,
  scope: "additive",
});
const plain = createProposedOperation({
  id: "op-plain",
  seq: 4,
  op: "create",
  kind: "individual",
  target_id: null,
  ref: "light",
  fields: { title: "LED light", class_ids: ["class-1"] },
  probability: 0.9,
  scope: "additive",
});
const used = createProposedOperation({
  id: "op-used",
  seq: 5,
  op: "create",
  kind: "individual",
  target_id: null,
  ref: "maker",
  fields: { title: "Whirlpool", class_ids: ["class-1"] },
  alternatives: [
    { kind: "existing", entity_id: "ind-1", similarity: 0.97, title: "LLM Provider Router" },
  ],
  status: "applied",
  matched: true,
  result_entity_id: "ind-1",
  probability: 0.97,
  scope: "additive",
});

let proposal: ChangeProposal;
let applies: ChangeProposalApplyRequest[];

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  proposal = createChangeProposal({
    id: "proposal-1",
    taxonomy_id: "tax-1",
    dataset_id: "ds-1",
    title: "Extraction: WRF555SDFZ use and care guide",
    source: "pipeline",
    status: "open",
    operations: structuredClone([fridge, filter, uses, plain, used]),
  });
  applies = [];
  server.use(
    http.get("*/api/proposals/:id", () => HttpResponse.json(proposal)),
    http.get("*/api/taxonomies/:id/gold", () => HttpResponse.json(goldPage(proposal.operations))),
    http.get("*/api/sources/:id", () => HttpResponse.json(source)),
    http.get("*/api/sources/:id/text", ({ request }) => {
      const page = Number(new URL(request.url).searchParams.get("page"));
      const body: SourceText = {
        source_id: "src-1",
        page,
        pages: 3,
        start: source.page_starts[page - 1],
        end: source.page_starts[page - 1] + PAGE_TEXT.length,
        text: PAGE_TEXT,
      };
      return HttpResponse.json(body);
    }),
    http.post("*/api/proposals/:id/apply", async ({ request }) => {
      const body = (await request.json()) as ChangeProposalApplyRequest;
      applies.push(body);
      for (const op of proposal.operations) {
        if (body.operation_ids.includes(op.id)) Object.assign(op, { status: "applied" });
      }
      return HttpResponse.json(proposal);
    }),
  );
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function ToastProbe() {
  const { toasts } = useToasts();
  return (
    <ul>
      {toasts.map((t) => (
        <li key={t.id} data-testid={`toast-${t.type}`}>
          {t.title}
          {t.sub ? ` | ${t.sub}` : ""}
        </li>
      ))}
    </ul>
  );
}

function renderPage(selectedOperationId?: string) {
  return render(
    <>
      <ProposalDetailPage
        id="proposal-1"
        selectedOperationId={selectedOperationId}
        onSelectOperation={vi.fn()}
      />
      <ToastProbe />
    </>,
  );
}

describe("an extraction create opens the review inspector (#1658)", () => {
  it("opens beside the source and the list, its quotes showing their passage (#1664)", async () => {
    renderPage("op-fridge");
    const inspector = await screen.findByTestId("review-inspector", {}, { timeout: 10000 });
    expect(screen.getByTestId("proposal-review")).toContainElement(inspector);
    expect(screen.getByTestId("proposal-review")).toContainElement(
      screen.getByTestId("proposal-operations-list"),
    );
    // The proposal cites its source: the page has the source pane, beside the list.
    expect(screen.getByTestId("proposal-review")).toHaveClass("proposal-review--source");
    expect(screen.getByTestId("proposal-operations-list")).toContainElement(
      screen.getByTestId("review-source"),
    );
    expect(screen.getByTestId("review-inspector-title")).toHaveTextContent("Whirlpool WRF555SDFZ");
    expect(screen.getByTestId("review-inspector-class")).toBeInTheDocument();
    // Its quotes are buttons that show the passage in the source.
    const first = screen.getByTestId("review-evidence-1");
    expect(first.tagName).toBe("BUTTON");
    expect(first).toHaveTextContent("French door fridge");
    expect(screen.getByTestId("review-evidence-2")).toHaveTextContent("WRF555SDFZ");
    // The older inspector's sections are gone for it.
    expect(screen.queryByTestId("operation-source-passage")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operation-decision")).not.toBeInTheDocument();
    // The review keys work on this page (#1663): the inspector shows their hints.
    expect(screen.getByTestId("review-correct")).toHaveAttribute("aria-keyshortcuts", "A");
    expect(screen.getByTestId("review-not")).toHaveAttribute("aria-keyshortcuts", "X");
    expect(inspector.querySelector(".review-keys")).not.toBeNull();
  });
});

describe("a near match", () => {
  it("asks whether it is already in the dataset, opening on the existing individual", async () => {
    renderPage("op-fridge");
    const group = await screen.findByRole("group", { name: "Already in dataset default?" });
    expect(group).toHaveClass("op-near-match");
    expect(within(group).getAllByRole("radio")).toHaveLength(2);
    expect(within(group).getByRole("radio", { name: "LLM Provider Router" })).toBeChecked();
    expect(
      within(group).getByRole("radio", { name: "Create new: Whirlpool WRF555SDFZ" }),
    ).not.toBeChecked();
    expect(within(group).getByText("similarity 0.93")).toHaveClass("op-near-match__detail");
    expect(screen.getByTestId("review-correct")).toHaveTextContent("Correct: use existing");
  });

  it("applies Use existing with the chosen alternative", async () => {
    const user = userEvent.setup();
    renderPage("op-fridge");
    await user.click(await screen.findByRole("button", { name: "Correct: use existing" }));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].operation_ids).toEqual(["op-fridge"]);
    expect(applies[0].chosen_alternatives).toEqual({
      "op-fridge": { kind: "existing", entity_id: "ind-1" },
    });
  });

  it("applies Create new without a chosen alternative", async () => {
    const user = userEvent.setup();
    renderPage("op-fridge");
    await user.click(
      await screen.findByRole("radio", { name: "Create new: Whirlpool WRF555SDFZ" }),
    );
    const correct = screen.getByTestId("review-correct");
    expect(correct).toHaveTextContent(/^Correct$/);
    await user.click(correct);
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].operation_ids).toEqual(["op-fridge"]);
    expect(applies[0].chosen_alternatives).toBeUndefined();
  });

  it("is flagged in the list, and a matched one reads as using the existing individual", async () => {
    renderPage("op-used");
    expect(await screen.findByTestId("operation-near-match-chip-op-fridge")).toHaveTextContent(
      "near match",
    );
    expect(screen.getByTestId("operation-near-match-chip-op-used")).toHaveTextContent(
      "used existing",
    );
    expect(await screen.findByTestId("review-decided")).toHaveTextContent(
      "Accepted as the existing individual LLM Provider Router, instead of creating one.",
    );
  });
});

describe("a relationship create's ends", () => {
  it("names both ends, which are this proposal's creates", async () => {
    renderPage("op-uses");
    expect(await screen.findByTestId("review-end-source")).toHaveTextContent(
      "Whirlpool WRF555SDFZ",
    );
    expect(screen.getByTestId("review-end-target")).toHaveTextContent("EveryDrop Filter 1");
  });

  it("can't be accepted until the creates it names are decided; a reason still rejects it", async () => {
    const user = userEvent.setup();
    const rejects: unknown[] = [];
    server.use(
      http.post("*/api/proposals/:id/reject", async ({ request }) => {
        rejects.push(await request.json());
        return HttpResponse.json(proposal);
      }),
    );
    renderPage("op-uses");
    expect(await screen.findByTestId("review-ends-callout")).toHaveTextContent(
      "Decide #1 and #2 first: this relationship follows their choices.",
    );
    expect(screen.getByTestId("review-correct")).toBeDisabled();
    await user.click(screen.getByTestId("review-reason-not_in_text"));
    await waitFor(() => expect(rejects).toHaveLength(1));
    expect(rejects[0]).toMatchObject({ operation_ids: ["op-uses"], reason_code: "not_in_text" });
    expect(applies).toHaveLength(0);
  });

  it("can be accepted once the creates it names applied", async () => {
    for (const op of proposal.operations) {
      if (op.id === "op-fridge" || op.id === "op-filter") Object.assign(op, { status: "applied" });
    }
    renderPage("op-uses");
    await waitFor(() => expect(screen.getByTestId("review-correct")).toBeEnabled());
    expect(screen.queryByTestId("review-ends-callout")).not.toBeInTheDocument();
  });

  it("says to reject it when a create it names was rejected", async () => {
    for (const op of proposal.operations) {
      if (op.id === "op-fridge") Object.assign(op, { status: "applied" });
      if (op.id === "op-filter") Object.assign(op, { status: "rejected" });
    }
    renderPage("op-uses");
    expect(await screen.findByTestId("review-ends-callout")).toHaveTextContent(
      "#2 was rejected, so this relationship can't apply as proposed.",
    );
    expect(screen.queryByTestId("review-correct")).not.toBeInTheDocument();
    expect(screen.getByTestId("review-reject-end")).toBeEnabled();
  });
});

describe("the decision banner and bulk accepts", () => {
  it("counts near matches and low-confidence operations as their own pills", async () => {
    renderPage();
    expect(await screen.findByTestId("proposal-pill-near-match")).toHaveTextContent("1 near match");
    expect(screen.getByTestId("proposal-pill-low-confidence")).toHaveTextContent(
      "1 low confidence",
    );
    expect(screen.getByTestId("proposal-pill-to-decide")).toHaveTextContent(
      "2 to accept or reject",
    );
  });

  it("leaves near matches and what names them out of All ready, and says so", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("review-group-scheme-1");
    await user.click(screen.getByTestId("review-bulk-select"));
    const menu = screen.getByTestId("review-bulk-select-menu");
    const ready = within(menu).getByTestId("review-bulk-select-ready");
    expect(ready).toHaveTextContent("All ready · 2");
    // The menu says what All ready leaves out, and how many.
    expect(within(menu).getByTestId("review-bulk-select-note")).toHaveTextContent(
      "1 near match is left for you to decide, with 1 operation that names one.",
    );
    await user.click(ready);
    expect(screen.getByTestId("operation-check-op-fridge")).not.toBeChecked();
    expect(screen.getByTestId("operation-check-op-uses")).not.toBeChecked();
    await user.click(screen.getByTestId("proposal-selection-accept"));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].operation_ids.sort()).toEqual(["op-filter", "op-plain"]);
    expect(applies[0].chosen_alternatives).toBeUndefined();
  });

  it("leaves them out of the threshold's pick", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByTestId("review-bulk-select"));
    // At 0.60: op-plain only. op-fridge (0.94) and op-uses (0.90) wait on the near match.
    expect(screen.getByTestId("review-bulk-select-threshold")).toHaveTextContent(
      "At or above p 0.60 · 1",
    );
  });

  it("skips a checked near match on Accept selected, and the toast says it was left", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("review-group-scheme-1");
    await user.click(screen.getByTestId("operation-check-op-fridge"));
    await user.click(screen.getByTestId("operation-check-op-plain"));
    expect(screen.getByTestId("proposal-selection-note")).toHaveTextContent(
      "1 near match is left for you to decide.",
    );
    await user.click(screen.getByTestId("proposal-selection-accept"));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].operation_ids).toEqual(["op-plain"]);
    expect(await screen.findByTestId("toast-success")).toHaveTextContent(
      "Applied 1 | 1 near match is left for you to decide.",
    );
  });
});
