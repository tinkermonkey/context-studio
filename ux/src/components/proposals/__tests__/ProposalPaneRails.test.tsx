/**
 * Folding a left pane to a rail (#1665): [ folds the source, ] the list, one
 * rail at a time and only with a source; the rail maps the pane's items, a mark
 * opens its item, and the choice is remembered per viewer. While the list is
 * folded, J / K and A / X keep working.
 */
import { useState } from "react";
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll } from "vitest";
import { PANE_FOLD_KEY } from "../review/paneFold";
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
  ProposedOperation,
} from "@/api/services/proposals";
import type { Source, SourceText } from "@/api/services/sources";
import { ProposalDetailPage } from "../ProposalDetailPage";

const server = setupServer(...proposalHandlers, ...entityPageHandlers);

const TEXT = "The Router sends requests to the Gateway, which keeps a Cache.";

function element(
  id: string,
  seq: number,
  title: string,
  classId: string,
  probability: number,
  extra: Partial<ProposedOperation> = {},
) {
  const start = TEXT.indexOf(title);
  return createProposedOperation({
    id,
    seq,
    op: "create",
    kind: "individual",
    target_id: null,
    ref: id,
    fields: { title, class_ids: [classId] },
    evidence: [{ source_id: "src-1", page: null, start, end: start + title.length, quote: title }],
    probability,
    scope: "additive",
    ...extra,
  });
}

const router = element("op-router", 1, "Router", "class-1", 0.92);
const gateway = element("op-gateway", 2, "Gateway", "class-2", 0.81);
const cache = element("op-cache", 3, "Cache", "class-1", 0.4);
const rename = createProposedOperation({
  id: "op-rename-class",
  seq: 4,
  op: "update",
  kind: "class",
  target_id: "class-2",
  base: { title: "ApplicationService" },
  fields: { title: "Application Service" },
  amended_at: "2026-11-24T10:00:00Z",
  probability: 0.7,
});

const source = {
  id: "src-1",
  taxonomy_id: "tax-1",
  dataset_id: "ds-1",
  kind: "text",
  title: "Architecture note",
  origin: "note.md",
  content_type: "text/plain",
  bytes: TEXT.length,
  pages: null,
  chars: TEXT.length,
  page_starts: [],
  headings: [],
  status: "ready",
  failure: null,
  failure_detail: null,
} as unknown as Source;

let proposal: ChangeProposal;
let applies: ChangeProposalApplyRequest[];

function extraction(extra: Partial<ChangeProposal> = {}): ChangeProposal {
  return createChangeProposal({
    id: "proposal-1",
    taxonomy_id: "tax-1",
    dataset_id: "ds-1",
    title: "Extraction of the architecture note",
    source: "pipeline",
    status: "open",
    origin: {
      pipeline_type: "individual_extraction",
      implementation_id: "single_call",
      configuration_ref: "c",
      configuration_version: 1,
      digest: "abcdef",
    },
    client_metadata: { source_id: "src-1" },
    operations: structuredClone([router, gateway, cache, rename]),
    ...extra,
  });
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  proposal = extraction();
  applies = [];
  server.use(
    http.get("*/api/proposals/:id", () => HttpResponse.json(proposal)),
    http.get("*/api/taxonomies/:id/gold", () => HttpResponse.json(goldPage(proposal.operations))),
    http.get("*/api/sources/:id/text", () =>
      HttpResponse.json({
        source_id: "src-1",
        page: null,
        pages: null,
        start: 0,
        end: TEXT.length,
        text: TEXT,
      } as unknown as SourceText),
    ),
    http.get("*/api/sources/:id", () => HttpResponse.json(source)),
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
afterEach(() => {
  server.resetHandlers();
  window.localStorage.removeItem(PANE_FOLD_KEY);
});
afterAll(() => server.close());

let current: string | undefined;

/** The route's part: the selection, as ?selected= holds it. */
function Harness({ initial }: { initial?: string }) {
  const [selected, setSelected] = useState<string | undefined>(initial);
  current = selected;
  return (
    <ProposalDetailPage
      id="proposal-1"
      selectedOperationId={selected}
      onSelectOperation={setSelected}
    />
  );
}

async function openPage(initial?: string) {
  const user = userEvent.setup();
  render(<Harness initial={initial} />);
  await screen.findByTestId("proposal-operations", {}, { timeout: 10000 });
  // Rows move into their layer once the classes and schemes load.
  await screen.findByTestId("review-group-scheme-1", {}, { timeout: 10000 });
  return user;
}

describe("folding a pane to a rail", () => {
  it("folds the source with [ and back, the rail mapping its highlights", async () => {
    const user = await openPage("op-router");
    await screen.findByTestId("review-source-text");
    expect(screen.getByTestId("review-fold-source")).toHaveAttribute("aria-keyshortcuts", "[");
    await user.keyboard("[[");
    const rail = screen.getByTestId("review-source-rail");
    expect(screen.queryByTestId("review-source")).not.toBeInTheDocument();
    expect(screen.getByTestId("proposal-operations-list")).toHaveAttribute("data-fold", "source");
    // Its marks: one per highlight, named by verdict and quote.
    const map = within(rail).getByRole("toolbar", { name: "Highlights in the source" });
    expect(
      within(map)
        .getAllByRole("button")
        .map((b) => b.getAttribute("aria-label")),
    ).toEqual(["Awaiting: Router", "Awaiting: Gateway", "Awaiting: Cache"]);
    expect(window.localStorage.getItem(PANE_FOLD_KEY)).toBe("source");
    await user.keyboard("[[");
    expect(screen.queryByTestId("review-source-rail")).not.toBeInTheDocument();
    expect(screen.getByTestId("review-source")).toBeInTheDocument();
    expect(window.localStorage.getItem(PANE_FOLD_KEY)).toBeNull();
  });

  it("folds the list with ], one rail at a time, the rail placing the selection", async () => {
    const user = await openPage("op-gateway");
    await screen.findByTestId("review-source-text");
    await user.click(screen.getByTestId("review-fold-list"));
    const rail = screen.getByTestId("review-list-rail");
    expect(screen.getByTestId("proposal-operations")).not.toBeVisible();
    // Rows in list order; the selection is the 2nd of 4.
    expect(rail).toHaveTextContent("2 / 4");
    expect(
      within(within(rail).getByRole("toolbar", { name: "Operations in the list" }))
        .getAllByRole("button")
        .map((b) => b.getAttribute("aria-label")),
    ).toEqual([
      "awaiting: Router",
      "awaiting: Gateway",
      "awaiting: Cache",
      "needs decision: ApplicationService",
    ]);
    // Folding the source unfolds the list: one rail at a time.
    await user.keyboard("[[");
    expect(screen.getByTestId("review-source-rail")).toBeInTheDocument();
    expect(screen.queryByTestId("review-list-rail")).not.toBeInTheDocument();
    expect(screen.getByTestId("proposal-operations")).toBeVisible();
  });

  it("opens an item from its mark, expanding the pane", async () => {
    const user = await openPage("op-router");
    await screen.findByTestId("review-source-text");
    await user.keyboard("]");
    const rail = screen.getByTestId("review-list-rail");
    await user.click(within(rail).getByRole("button", { name: "awaiting: Cache" }));
    expect(current).toBe("op-cache");
    expect(screen.queryByTestId("review-list-rail")).not.toBeInTheDocument();
    expect(screen.getByTestId("review-row-op-cache")).toHaveAttribute("aria-selected", "true");
  });

  it("shows a mark's pill card on hover", async () => {
    const user = await openPage("op-router");
    await screen.findByTestId("review-source-text");
    await user.keyboard("[[");
    await user.hover(
      within(screen.getByTestId("review-source-rail")).getByRole("button", {
        name: "Awaiting: Gateway",
      }),
    );
    expect(await screen.findByTestId("review-rail-card")).toHaveTextContent("Gateway");
  });

  it("keeps J / K and A / X working while the list is folded", async () => {
    const user = await openPage("op-router");
    await screen.findByTestId("review-source-text");
    await user.keyboard("]");
    await user.keyboard("j");
    expect(current).toBe("op-gateway");
    expect(screen.getByTestId("review-list-rail")).toHaveTextContent("2 / 4");
    await user.keyboard("x");
    await waitFor(() =>
      expect(screen.getByTestId("review-reasons-prompt")).not.toBeEmptyDOMElement(),
    );
    await user.keyboard("a");
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].operation_ids).toEqual(["op-gateway"]);
  });

  it("unfolds the source for Show in source", async () => {
    const user = await openPage("op-router");
    await screen.findByTestId("review-source-text");
    await user.keyboard("[[");
    await user.click(screen.getByTestId("review-evidence-1"));
    expect(screen.queryByTestId("review-source-rail")).not.toBeInTheDocument();
    expect(screen.getByTestId("review-source-text")).toBeInTheDocument();
  });

  it("remembers the fold for the viewer", async () => {
    window.localStorage.setItem(PANE_FOLD_KEY, "list");
    await openPage("op-router");
    expect(await screen.findByTestId("review-list-rail")).toBeInTheDocument();
  });

  it("doesn't fold without a source: the list is the only way through", async () => {
    window.localStorage.setItem(PANE_FOLD_KEY, "list");
    proposal = extraction({ client_metadata: {}, operations: structuredClone([rename]) });
    const user = userEvent.setup();
    render(<Harness initial="op-rename-class" />);
    await screen.findByTestId("review-row-op-rename-class", {}, { timeout: 10000 });
    expect(screen.queryByTestId("review-list-rail")).not.toBeInTheDocument();
    expect(screen.queryByTestId("review-fold-list")).not.toBeInTheDocument();
    await user.keyboard("]");
    expect(screen.queryByTestId("review-list-rail")).not.toBeInTheDocument();
  });
});
