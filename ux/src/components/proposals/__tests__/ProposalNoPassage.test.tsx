/**
 * Operations an extraction couldn't place in its source (#1575): a "no
 * passage" chip in the operations table and a note in the inspector; bulk
 * accepts hold them (and what names them by "$ref") back and say how many,
 * while accepting one on its own still applies it.
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
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
import { useToasts } from "@/components/ui/Toast";
import { ProposalDetailPage } from "../ProposalDetailPage";

const server = setupServer(...proposalHandlers, ...entityPageHandlers);

function individual(id: string, seq: number, title: string, noPassage: boolean) {
  return createProposedOperation({
    id,
    seq,
    op: "create",
    kind: "individual",
    target_id: null,
    ref: id.replace("op-", ""),
    fields: { title, class_ids: ["class-1"] },
    // A quote the extraction couldn't place keeps only its text.
    evidence: noPassage ? [{ quote: title.toLowerCase() }] : [],
    no_passage: noPassage,
    probability: 0.9,
    base: {},
    scope: "additive",
  });
}

const wall = individual("op-wall", 1, "Wall", false);
const pacemaker = individual("op-pacemaker", 2, "Pacemaker", true);
const anchor = individual("op-anchor", 3, "Wall anchor", true);
const near = createProposedOperation({
  id: "op-near",
  seq: 4,
  op: "create",
  kind: "relationship",
  target_id: null,
  fields: { property_definition_id: "prop-1", source_id: "$pacemaker", target_id: "$wall" },
  base: {},
  probability: 0.9,
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
    title: "Extraction: Moen INS10668B",
    source: "pipeline",
    status: "open",
    operations: structuredClone([wall, pacemaker, anchor, near]),
  });
  applies = [];
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

describe("the no passage marker", () => {
  it("flags each awaiting operation without a passage in the table, amber", async () => {
    renderPage();
    const chip = await screen.findByTestId("operation-no-passage-op-pacemaker");
    expect(chip).toHaveTextContent("no passage");
    expect(chip).toHaveClass("chip--amber");
    expect(chip).toHaveAttribute("role", "note");
    expect(chip).toHaveAttribute("aria-label", expect.stringContaining("No passage"));
    expect(screen.getByTestId("operation-no-passage-op-anchor")).toBeInTheDocument();
    expect(screen.queryByTestId("operation-no-passage-op-wall")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operation-no-passage-op-near")).not.toBeInTheDocument();
  });

  it("goes neutral once the operation is decided", async () => {
    for (const op of proposal.operations) op.status = "applied";
    proposal.status = "done";
    renderPage();
    expect(await screen.findByTestId("operation-no-passage-op-pacemaker")).toHaveClass(
      "chip--neutral",
    );
  });

  it("explains it in the inspector in place of the passage", async () => {
    renderPage("op-pacemaker");
    const note = await screen.findByTestId("operation-no-passage");
    expect(note).toHaveAttribute("role", "note");
    expect(note).toHaveClass("entity-note");
    expect(note).toHaveTextContent("couldn't place this in its source");
    expect(screen.queryByTestId("operation-source-passage")).not.toBeInTheDocument();
  });

  it("is absent from the inspector of an operation with a passage", async () => {
    renderPage("op-wall");
    expect(await screen.findByTestId("operation-inspector")).toBeInTheDocument();
    expect(screen.queryByTestId("operation-no-passage")).not.toBeInTheDocument();
  });
});

describe("bulk accept", () => {
  it("holds them and what names them out of Accept N ready, and says how many", async () => {
    const user = userEvent.setup();
    renderPage();
    const acceptAll = await screen.findByTestId("proposal-accept-all");
    expect(acceptAll).toHaveTextContent("Accept 1 ready");
    expect(acceptAll).toHaveAttribute(
      "title",
      expect.stringContaining("Operations without a passage are held back"),
    );

    await user.click(acceptAll);

    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].operation_ids).toEqual(["op-wall"]);
    expect(await screen.findByTestId("toast-success")).toHaveTextContent(
      "Applied 1 | Held back 2 operations without a passage, with 1 that names one: accept each on its own.",
    );
    expect(screen.queryByTestId("toast-error")).not.toBeInTheDocument();
  });

  it("holds a checked one back on Accept selected, and the toast says so", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByTestId("operation-check-op-pacemaker"));
    await user.click(screen.getByTestId("operation-check-op-wall"));
    expect(screen.getByTestId("proposal-selection-note")).toHaveTextContent(
      "1 without a passage: Accept selected holds it back; accept it on its own.",
    );

    await user.click(screen.getByTestId("proposal-selection-accept"));

    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].operation_ids).toEqual(["op-wall"]);
    expect(await screen.findByTestId("toast-success")).toHaveTextContent(
      "Applied 1 | Held back 1 operation without a passage: accept it on its own.",
    );
  });

  it("disables Accept selected when only held operations are checked, and says why", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByTestId("operation-check-op-anchor"));
    expect(screen.getByTestId("proposal-selection-accept")).toBeDisabled();
    expect(screen.getByTestId("proposal-selection-note")).toHaveTextContent("1 without a passage");
  });
});

describe("accepting one on its own", () => {
  it("applies an operation without a passage from the inspector", async () => {
    const user = userEvent.setup();
    renderPage("op-anchor");
    await user.click(await screen.findByTestId("operation-accept"));

    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].operation_ids).toEqual(["op-anchor"]);
  });
});
