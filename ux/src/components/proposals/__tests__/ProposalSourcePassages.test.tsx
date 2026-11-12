/**
 * Reviewing an extraction proposal beside its passages (#1555): the source
 * passage with its quote highlighted in the page's text (or alone when it
 * can't be placed), a near match's "Already in dataset …?" choice sent as
 * chosen_alternatives, which ends of a relationship are new, the banner's
 * near-match and low-confidence pills, and bulk accepts that leave near
 * matches (and what names them) for the reviewer.
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

describe("the source passage", () => {
  it("highlights the quote in its page's text, with the page, section and source", async () => {
    renderPage("op-fridge");
    const mark = await screen.findByTestId("operation-source-passage-mark", {}, { timeout: 10000 });
    expect(mark.tagName).toBe("MARK");
    expect(mark).toHaveClass("op-passage__mark");
    expect(mark).toHaveTextContent("French door fridge");
    const text = screen.getByTestId("operation-source-passage-text");
    expect(text).toHaveClass("op-passage__text");
    expect(text).toHaveAttribute("data-placed", "true");
    expect(text).toHaveTextContent("Thank you French door fridge comes with parts.");
    await waitFor(() =>
      expect(screen.getByTestId("operation-source-passage-location")).toHaveTextContent(
        "p. 2 · Parts and features",
      ),
    );
    // Sources have no page of their own: the title links to its taxonomy's Sources
    // page, in a new tab so an unsent decision and reason here aren't lost.
    const title = screen.getByTestId("operation-source-title");
    expect(title).toHaveTextContent("Whirlpool use and care guide");
    expect(title).toHaveClass("op-passage__source");
    expect(title).toHaveClass("entity-link");
    const link = within(screen.getByTestId("operation-source-passage")).getByRole("link", {
      name: "Whirlpool use and care guide (opens in a new tab)",
    });
    expect(link).toBe(title);
    expect(link).toHaveAttribute("href", "/app/data/sources?taxonomy=tax-1");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(within(link).getByText("(opens in a new tab)")).toHaveClass("sr-only");
    expect(screen.getByTestId("operation-source-passage-more")).toHaveTextContent("Also on p. 3");
    // The passages aren't repeated as plain evidence.
    expect(screen.queryByTestId("operation-evidence")).not.toBeInTheDocument();
  });

  it("shows a quote it can't place alone, without a highlight", async () => {
    renderPage("op-filter");
    const text = await screen.findByTestId("operation-source-passage-text");
    await waitFor(() =>
      expect(screen.getByTestId("operation-source-passage-location")).toHaveTextContent(
        "Parts and features",
      ),
    );
    expect(text).toHaveAttribute("data-placed", "false");
    expect(text).toHaveTextContent("EveryDrop");
    expect(screen.queryByTestId("operation-source-passage-mark")).not.toBeInTheDocument();
  });

  it("shows the quote alone when the source is removed", async () => {
    server.use(
      http.get("*/api/sources/:id", () =>
        HttpResponse.json({ ...source, removed_at: "2026-11-11T00:00:00Z" }),
      ),
    );
    renderPage("op-fridge");
    await waitFor(() =>
      expect(screen.getByTestId("operation-source-passage-more")).toHaveTextContent(
        "The source was removed.",
      ),
    );
    expect(screen.getByTestId("operation-source-passage-text")).toHaveAttribute(
      "data-placed",
      "false",
    );
    expect(screen.queryByTestId("operation-source-passage-mark")).not.toBeInTheDocument();
    // A removed source isn't on the Sources page, so its title stays text.
    expect(screen.getByTestId("operation-source-title").tagName).toBe("SPAN");
    expect(
      within(screen.getByTestId("operation-source-passage")).queryByRole("link"),
    ).not.toBeInTheDocument();
  });
});

describe("a near match", () => {
  it("asks whether it is already in the dataset, opening on the existing individual", async () => {
    renderPage("op-fridge");
    const group = await screen.findByRole("group", { name: "Already in dataset default?" });
    expect(group).toHaveClass("op-near-match");
    expect(group).toHaveAttribute("data-testid", "operation-near-match");
    const radios = within(group).getAllByRole("radio");
    expect(radios).toHaveLength(2);
    expect(within(group).getByRole("radio", { name: "LLM Provider Router" })).toBeChecked();
    expect(
      within(group).getByRole("radio", { name: "Create new: Whirlpool WRF555SDFZ" }),
    ).not.toBeChecked();
    expect(within(group).getByText("similarity 0.93")).toHaveClass("op-near-match__detail");
    expect(screen.getByTestId("operation-near-match-option-ind-1")).toHaveClass(
      "op-near-match__option--chosen",
    );
    expect(screen.getByTestId("operation-accept")).toHaveTextContent("Use existing");
  });

  it("applies Use existing with the chosen alternative", async () => {
    const user = userEvent.setup();
    renderPage("op-fridge");
    await user.click(await screen.findByRole("button", { name: "Use existing" }));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].operation_ids).toEqual(["op-fridge"]);
    expect(applies[0].chosen_alternatives).toEqual({
      "op-fridge": { kind: "existing", entity_id: "ind-1" },
    });
  });

  it("applies Accept new without a chosen alternative", async () => {
    const user = userEvent.setup();
    renderPage("op-fridge");
    await user.click(
      await screen.findByRole("radio", { name: "Create new: Whirlpool WRF555SDFZ" }),
    );
    const accept = screen.getByTestId("operation-accept");
    expect(accept).toHaveTextContent("Accept new");
    await user.click(accept);
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].operation_ids).toEqual(["op-fridge"]);
    expect(applies[0].chosen_alternatives).toBeUndefined();
  });

  it("is flagged in the table, and a matched one reads as using the existing individual", async () => {
    renderPage("op-used");
    expect(await screen.findByTestId("operation-near-match-chip-op-fridge")).toHaveTextContent(
      "near match",
    );
    expect(screen.getByTestId("operation-near-match-chip-op-used")).toHaveTextContent(
      "used existing",
    );
    expect(await screen.findByTestId("operation-decided-record")).toHaveTextContent(
      "Used the existing individual LLM Provider Router instead of creating one.",
    );
  });
});

describe("a relationship create's ends", () => {
  it("says which end follows a near match and which is new in the proposal", async () => {
    renderPage("op-uses");
    expect(await screen.findByTestId("operation-relationship-ends-note")).toHaveTextContent(
      "Source is #1, a near match: it follows the choice made there; target is new in this proposal (#2).",
    );
    expect(screen.getByTestId("operation-relationship-end-source")).toHaveAttribute(
      "data-kind",
      "near",
    );
    expect(screen.getByTestId("operation-relationship-end-target")).toHaveAttribute(
      "data-kind",
      "new",
    );
  });

  it("can't be accepted until the creates it names are decided; Reject still works", async () => {
    const user = userEvent.setup();
    renderPage("op-uses");
    const callout = await screen.findByTestId("operation-ends-callout");
    expect(callout).toHaveTextContent(
      "Decide #1 and #2 first: this relationship follows their choices.",
    );
    expect(screen.getByTestId("operation-accept")).toBeDisabled();
    const reject = screen.getByTestId("operation-reject");
    expect(reject).toBeEnabled();
    server.use(http.post("*/api/proposals/:id/reject", () => HttpResponse.json(proposal)));
    await user.click(reject);
    expect(applies).toHaveLength(0);
  });

  it("can be accepted once the creates it names applied", async () => {
    for (const op of proposal.operations) {
      if (op.id === "op-fridge" || op.id === "op-filter") Object.assign(op, { status: "applied" });
    }
    renderPage("op-uses");
    await waitFor(() => expect(screen.getByTestId("operation-accept")).toBeEnabled());
    expect(screen.queryByTestId("operation-ends-callout")).not.toBeInTheDocument();
  });

  it("says to reject it when a create it names was rejected", async () => {
    for (const op of proposal.operations) {
      if (op.id === "op-fridge") Object.assign(op, { status: "applied" });
      if (op.id === "op-filter") Object.assign(op, { status: "rejected" });
    }
    renderPage("op-uses");
    expect(await screen.findByTestId("operation-ends-callout")).toHaveTextContent(
      "#2 was rejected, so this relationship can't apply. Reject it.",
    );
    expect(screen.getByTestId("operation-accept")).toBeDisabled();
    expect(screen.getByTestId("operation-reject")).toBeEnabled();
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

  it("leaves near matches and what names them out of Accept N ready, and says so", async () => {
    const user = userEvent.setup();
    renderPage();
    const acceptAll = await screen.findByTestId("proposal-accept-all");
    expect(acceptAll).toHaveTextContent("Accept 2 ready");
    expect(acceptAll).toHaveAttribute(
      "title",
      expect.stringContaining("1 near match is left for you to decide, with 1 operation"),
    );
    await user.click(acceptAll);
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].operation_ids.sort()).toEqual(["op-filter", "op-plain"]);
    expect(applies[0].chosen_alternatives).toBeUndefined();
  });

  it("leaves them out of the threshold's Select N", async () => {
    renderPage();
    // At 0.60: op-plain only. op-fridge (0.94) and op-uses (0.90) wait on the near match.
    expect(await screen.findByTestId("proposal-threshold-select")).toHaveTextContent("Select 1");
  });

  it("skips a checked near match on Accept selected, and the toast says it was left", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByTestId("operation-check-op-fridge"));
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
