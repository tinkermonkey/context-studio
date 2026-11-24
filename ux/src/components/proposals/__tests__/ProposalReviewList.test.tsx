/**
 * The review list on proposal detail (#1663): grouped by layer for an
 * extraction, with Select ▾ and the bulk bar on every proposal decided here
 * (extractions included) but a gold check; keys J / K, A and X; "amended" on an
 * operation its proposer changed, and a superseded proposal linked to the one
 * that replaces it (#1624).
 */
import { useState } from "react";
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
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
afterEach(() => server.resetHandlers());
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

const menuItem = (name: string) => screen.getByTestId(`review-bulk-select-${name}`);

describe("the review list", () => {
  it("groups an extraction by layer, the other changes by what they change", async () => {
    await openPage();
    const layer = await screen.findByTestId("review-group-scheme-1");
    await waitFor(() => expect(layer).toHaveAccessibleName("Application Layer"));
    expect(
      within(layer)
        .getAllByRole("option")
        .map((row) => row.getAttribute("data-row-id")),
    ).toEqual(["op-router", "op-gateway", "op-cache"]);
    const classes = screen.getByTestId("review-group-kind-class");
    expect(classes).toHaveAccessibleName("Classes");
    // A change row reads by its seq, op and what it changes, inline.
    expect(screen.getByTestId("review-row-op-op-rename-class")).toHaveTextContent("seq 4 · update");
    expect(within(classes).getByTestId("operation-diff-op-rename-class")).toBeInTheDocument();
    expect(screen.getByTestId("proposal-operations-list")).toHaveAttribute(
      "data-group-by",
      "layer",
    );
    // What the progress pills control: the list itself, not the source beside it.
    const list = document.getElementById("proposal-operations");
    expect(list).toBe(screen.getByTestId("proposal-operations"));
    expect(list).not.toContainElement(screen.getByTestId("review-source"));
  });

  it("marks an operation its proposer amended (#1624)", async () => {
    await openPage();
    expect(await screen.findByTestId("review-row-amended-op-rename-class")).toHaveTextContent(
      "amended",
    );
    expect(screen.queryByTestId("review-row-amended-op-router")).not.toBeInTheDocument();
  });

  it("reads an operation its proposer withdrew as withdrawn, under All only, uncounted", async () => {
    proposal.operations[2].status = "withdrawn";
    const user = await openPage();
    await screen.findByTestId("review-row-op-router");
    expect(screen.queryByTestId("review-row-op-cache")).not.toBeInTheDocument();
    // Not part of the review (#1624): not counted, and not listed as decided.
    expect(screen.getByTestId("proposal-tally")).toHaveTextContent("3 of 3 need a decision");
    await user.click(screen.getByRole("radio", { name: /^Decided/ }));
    expect(screen.queryByTestId("review-row-op-cache")).not.toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: /^All/ }));
    const row = await screen.findByTestId("review-row-op-cache");
    expect(row).toHaveAttribute("data-verdict", "withdrawn");
    expect(within(row).getByText("withdrawn")).toBeInTheDocument();
    expect(within(row).queryByRole("checkbox")).not.toBeInTheDocument();
    // Its inspector says so, with no decision to change: it was never decided.
    await user.click(row);
    expect(screen.getByTestId("review-inspector-status")).toHaveTextContent("withdrawn");
    expect(screen.getByTestId("review-decided")).toHaveTextContent("Withdrawn by its proposer");
    expect(screen.queryByTestId("review-change-decision")).not.toBeInTheDocument();
  });

  it("reads a withdrawn change as withdrawn, not rejected", async () => {
    proposal.operations[3].status = "withdrawn";
    const user = await openPage();
    await user.click(screen.getByRole("radio", { name: /^All/ }));
    const row = await screen.findByTestId("review-row-op-rename-class");
    expect(row).toHaveAttribute("data-verdict", "withdrawn");
    expect(within(row).getByText("withdrawn")).toBeInTheDocument();
  });

  it("opens on the first row awaiting a decision, and another on its row's link", async () => {
    const user = await openPage();
    // Nothing in the URL: the first awaiting row is open, without a history entry (#1664).
    await waitFor(() =>
      expect(screen.getByTestId("review-row-op-router")).toHaveAttribute("aria-selected", "true"),
    );
    expect(current).toBeUndefined();
    expect(screen.queryByTestId("proposal-inspector-empty")).not.toBeInTheDocument();
    const row = await screen.findByTestId("review-row-op-gateway");
    expect(row).toHaveAttribute("href", "/app/proposals/proposal-1?selected=op-gateway");
    await user.click(row);
    expect(current).toBe("op-gateway");
    expect(row).toHaveAttribute("aria-selected", "true");
    expect(
      within(screen.getByTestId("proposal-review")).getByTestId("review-inspector"),
    ).toBeVisible();
  });
});

describe("bulk decisions", () => {
  it("are offered on an extraction proposal: Select ▾ checks all ready, the bar accepts them", async () => {
    const user = await openPage();
    const select = await screen.findByTestId("review-bulk-select");
    // A disclosure: its panel is a group of choices, not a menu (it holds a slider).
    expect(select).toHaveAttribute("aria-expanded", "false");
    await user.click(select);
    expect(select).toHaveAttribute("aria-expanded", "true");
    const panel = screen.getByRole("group", { name: "Select operations" });
    expect(select).toHaveAttribute("aria-controls", panel.id);
    expect(menuItem("ready")).toHaveTextContent("All ready · 4");
    await user.click(menuItem("ready"));
    // The menu closes; the rows are checked and the bar counts them.
    expect(screen.queryByTestId("review-bulk-select-menu")).not.toBeInTheDocument();
    for (const id of ["op-router", "op-gateway", "op-cache", "op-rename-class"]) {
      expect(screen.getByTestId(`operation-check-${id}`)).toBeChecked();
    }
    expect(screen.getByTestId("proposal-selection-count")).toHaveTextContent("4 selected");
    await user.click(screen.getByTestId("proposal-selection-accept"));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].operation_ids).toEqual([
      "op-router",
      "op-gateway",
      "op-cache",
      "op-rename-class",
    ]);
  });

  it("checks the ready rows at or above the threshold, and the slider moves it", async () => {
    const user = await openPage();
    await user.click(await screen.findByTestId("review-bulk-select"));
    expect(screen.getByTestId("proposal-threshold-value")).toHaveTextContent("0.60");
    expect(menuItem("threshold")).toHaveTextContent("At or above p 0.60 · 3");
    fireEvent.change(screen.getByTestId("proposal-threshold-slider"), {
      target: { value: "0.85" },
    });
    expect(menuItem("threshold")).toHaveTextContent("At or above p 0.85 · 1");
    await user.click(menuItem("threshold"));
    expect(screen.getByTestId("operation-check-op-router")).toBeChecked();
    expect(screen.getByTestId("operation-check-op-gateway")).not.toBeChecked();
    expect(screen.getByTestId("proposal-selection-count")).toHaveTextContent("1 selected");
  });

  it("clears with None, and closes on Esc with focus back on Select", async () => {
    const user = await openPage();
    await user.click(await screen.findByTestId("review-bulk-select"));
    await user.click(menuItem("awaiting"));
    expect(screen.getByTestId("proposal-selection-count")).toHaveTextContent("4 selected");
    await user.click(screen.getByTestId("review-bulk-select"));
    await user.click(menuItem("none"));
    expect(screen.queryByTestId("proposal-selection-bar")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("review-bulk-select"));
    await user.keyboard("{Escape}");
    expect(screen.queryByTestId("review-bulk-select-menu")).not.toBeInTheDocument();
    expect(screen.getByTestId("review-bulk-select")).toHaveFocus();
  });

  it("are hidden on a gold check: no Select, no checkboxes, no bulk bar", async () => {
    proposal = extraction({
      origin: {
        pipeline_type: "individual_extraction",
        implementation_id: "gold_check",
        configuration_ref: "c",
        configuration_version: 1,
        digest: "abcdef",
      },
      client_metadata: { source_id: "src-1", gold_check: { document: "doc", elements: {} } },
    });
    await openPage();
    await screen.findByTestId("review-row-op-router");
    expect(screen.queryByTestId("review-bulk-select")).not.toBeInTheDocument();
    expect(screen.queryByTestId(/^operation-check-/)).not.toBeInTheDocument();
    expect(screen.queryByTestId("proposal-selection-bar")).not.toBeInTheDocument();
  });
});

describe("keys", () => {
  it("J and K move the selection down and up the list, also after a click on a checkbox", async () => {
    const user = await openPage("op-router");
    await screen.findByTestId("review-inspector");
    // A checkbox takes no letters: the keys still move the selection.
    await user.click(screen.getByTestId("operation-check-op-cache"));
    expect(screen.getByTestId("operation-check-op-cache")).toHaveFocus();
    await user.keyboard("j");
    expect(current).toBe("op-gateway");
    await user.keyboard("j");
    expect(current).toBe("op-cache");
    await user.keyboard("k");
    expect(current).toBe("op-gateway");
  });

  it("A accepts the selected operation; X opens its reason step", async () => {
    const user = await openPage("op-gateway");
    await screen.findByTestId("review-inspector");
    await user.keyboard("x");
    await waitFor(() =>
      expect(screen.getByTestId("review-reasons-prompt")).not.toBeEmptyDOMElement(),
    );
    await user.keyboard("a");
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].operation_ids).toEqual(["op-gateway"]);
  });
});

describe("review timing on every proposal (#1664)", () => {
  it("times a change plan without a source too, and sends the time with its decision", async () => {
    proposal = extraction({
      source: "mcp",
      origin: null,
      client_metadata: {},
      operations: structuredClone([rename]),
    });
    const user = userEvent.setup();
    render(<Harness initial="op-rename-class" />);
    await screen.findByTestId("review-inspector", {}, { timeout: 10000 });
    expect(screen.queryByTestId("review-source")).not.toBeInTheDocument();
    expect(screen.getByTestId("review-time")).toHaveTextContent(/on this review$/);
    await user.click(screen.getByTestId("review-correct"));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].review_ms).toEqual({ "op-rename-class": expect.any(Number) });
  });
});

describe("a superseded proposal (#1624)", () => {
  it("links the proposal that replaces it, and takes no decisions", async () => {
    proposal = extraction({
      status: "withdrawn",
      links: [
        {
          kind: "superseded_by",
          proposal_id: "proposal-9",
          title: "Newer extraction",
          status: "open",
          created_at: "2026-11-24T11:00:00Z",
        },
      ],
    });
    await openPage("op-router");
    const link = await screen.findByTestId("proposal-supersede-superseded_by");
    expect(link).toHaveTextContent("superseded by");
    expect(within(link).getByRole("link", { name: "Newer extraction" })).toHaveAttribute(
      "href",
      "/app/proposals/proposal-9",
    );
    await screen.findByTestId("review-inspector");
    expect(screen.queryByTestId("review-correct")).not.toBeInTheDocument();
    expect(screen.queryByTestId("review-bulk-select")).not.toBeInTheDocument();
  });
});
