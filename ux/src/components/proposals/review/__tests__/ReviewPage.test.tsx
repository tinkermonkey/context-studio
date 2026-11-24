/**
 * The Review page (#1611): an extraction proposal reviewed against its whole
 * source. The source's highlights carry each element's verdict, elements are
 * grouped by layer with an Awaiting / All filter, and the inspector decides
 * the selected one (Correct, a better class, or not an element with a reason)
 * by button or key, sending the time spent on it.
 */
import { unamended } from "@/test/proposalFixtures";
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import {
  createClass,
  createConceptScheme,
  createDataset,
  createPropertyDefinition,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";
import type {
  AddIndividualRequest,
  ChangeProposal,
  ChangeProposalApplyRequest,
  ChangeProposalRejectRequest,
  ProposedOperation,
} from "@/api/services/proposals";
import type { Source, SourceText } from "@/api/services/sources";
import { useToasts } from "@/components/ui/Toast";
import { ReviewPage } from "../ReviewPage";

const TEXT =
  "Edit Check offers feedback while editing. Reference check realizes Edit Check. " +
  "Newcomers from Sub-Saharan Africa will feel safe.";

const source: Source = {
  id: "src-1",
  taxonomy_id: "tax-1",
  dataset_id: "ds-1",
  kind: "text",
  title: "Edit check",
  origin: "edit_check.md",
  content_type: "text/plain",
  bytes: TEXT.length,
  pages: null,
  chars: TEXT.length,
  page_starts: [],
  headings: [],
  status: "ready",
  failure: null,
  failure_detail: null,
  created_at: "2026-11-10T12:00:00Z",
  updated_at: "2026-11-10T12:00:00Z",
  removed_at: null,
} as unknown as Source;

const product = createConceptScheme({ id: "scheme-p", taxonomy_id: "tax-1", title: "Product" });
const motivation = createConceptScheme({
  id: "scheme-m",
  taxonomy_id: "tax-1",
  title: "Motivation",
});
// A DR-length definition: clamped to a few lines until Show more.
const STAKEHOLDER_DEFINITION =
  "A person, group or organization whose interests or concerns about the architecture " +
  "drivers, goals and requirements trace back to. Stakeholders are named by role, not by " +
  "person, and each states the concerns that make them care about the architecture and " +
  "how its outcomes are assessed.";
const feature = createClass({
  id: "cls-feature",
  concept_scheme_id: "scheme-p",
  taxonomy_id: "tax-1",
  identifier: "product.feature",
  title: "Feature",
  description: "A unit of product functionality a persona can perceive.",
  external_references: [{ source: "documentation_robotics", identifier: "product.feature" }],
});
const capability = createClass({
  id: "cls-capability",
  concept_scheme_id: "scheme-p",
  taxonomy_id: "tax-1",
  identifier: "product.softwarecapability",
  title: "Software capability",
  description: "An ability of the software platform.",
});
const derivedClass = createClass({
  id: "cls-derived",
  concept_scheme_id: "scheme-p",
  taxonomy_id: "tax-1",
  identifier: "product.featureset",
  title: "Feature set",
  derived: true,
});
const stakeholder = createClass({
  id: "cls-stakeholder",
  concept_scheme_id: "scheme-m",
  taxonomy_id: "tax-1",
  identifier: "motivation.stakeholder",
  title: "Stakeholder",
  description: STAKEHOLDER_DEFINITION,
  external_references: [{ source: "documentation_robotics", identifier: "motivation.stakeholder" }],
});
const goal = createClass({
  id: "cls-goal",
  concept_scheme_id: "scheme-m",
  taxonomy_id: "tax-1",
  identifier: "motivation_goal",
  title: "Goal",
  description: "A high-level statement of intent.",
  external_references: [{ source: "documentation_robotics", identifier: "motivation.goal" }],
});
const classes = [feature, capability, derivedClass, stakeholder, goal];
const dataset = createDataset({
  id: "ds-1",
  taxonomy_id: "tax-1",
  identifier: "bench-edit-check",
  title: "Bench edit check",
});

function passage(quote: string, from = 0) {
  const start = TEXT.indexOf(quote, from);
  return { source_id: "src-1", page: null, start, end: start + quote.length, quote };
}

function individual(
  id: string,
  title: string,
  classId: string,
  quote: string,
  overrides: Partial<ProposedOperation> = {},
): ProposedOperation {
  return createProposedOperation({
    id,
    seq: 0,
    op: "create",
    kind: "individual",
    target_id: null,
    ref: id.replace("op-", ""),
    fields: { title, class_ids: [classId] },
    evidence: [passage(quote)],
    scope: "additive",
    ...overrides,
  });
}

const edit = individual("op-edit", "Edit Check", "cls-capability", "Edit Check", {
  seq: 1,
  probability: 0.97,
});
const reference = individual("op-ref", "Reference check", "cls-feature", "Reference check", {
  seq: 2,
  probability: 0.95,
});
const region = individual(
  "op-region",
  "Sub-Saharan Africa",
  "cls-stakeholder",
  "Sub-Saharan Africa",
  {
    seq: 3,
    probability: 0.41,
  },
);
const added = individual("op-added", "Feedback", "cls-feature", "feedback", {
  seq: 4,
  status: "applied",
  added_by_reviewer: true,
  result_entity_id: "ind-77",
});
const realizes = createProposedOperation({
  id: "op-rel",
  seq: 5,
  op: "create",
  kind: "relationship",
  target_id: null,
  fields: { property_definition_id: "prop-1", source_id: "$ref", target_id: "$edit" },
  evidence: [],
  probability: 0.9,
  scope: "additive",
});

const server = setupServer(...entityPageHandlers);

let proposal: ChangeProposal;
let applies: ChangeProposalApplyRequest[];
let rejects: ChangeProposalRejectRequest[];
let failApply: string | undefined;
let additions: AddIndividualRequest[];
/** A 422 the next addition answers with. */
let refuseAddition: { code: string; message: string } | undefined;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  proposal = createChangeProposal({
    id: "proposal-1",
    taxonomy_id: "tax-1",
    dataset_id: "ds-1",
    title: "Extraction: Edit check",
    source: "pipeline",
    status: "open",
    origin: {
      pipeline_type: "individual_extraction",
      implementation_id: "single_call",
      configuration_ref: "extraction-single-call",
      configuration_version: 2,
      digest: "3f2a9c11",
    },
    operations: structuredClone([edit, reference, region, added, realizes]),
    // Extracted from src-1 into ds-1: it takes elements the reviewer adds.
    client_metadata: { source_id: "src-1" },
  });
  applies = [];
  rejects = [];
  failApply = undefined;
  additions = [];
  refuseAddition = undefined;
  const list = <T,>(items: T[]) =>
    HttpResponse.json({ items, total: items.length, limit: 500, offset: 0 });
  server.use(
    http.get("*/api/proposals/:id", () => HttpResponse.json(proposal)),
    http.get("*/api/sources/:id/text", () => {
      const body: SourceText = {
        source_id: "src-1",
        page: null,
        pages: null,
        start: 0,
        end: TEXT.length,
        text: TEXT,
      } as unknown as SourceText;
      return HttpResponse.json(body);
    }),
    http.get("*/api/sources/:id", () => HttpResponse.json(source)),
    http.get("*/api/datasets", () => HttpResponse.json([dataset])),
    // The schema's relationship types (see below): realizes and serves join feature to capability.
    http.get("*/api/properties", () => list([realizesType, servesType, drivesType])),
    http.get("*/api/schemes", () => list([product, motivation])),
    http.get("*/api/taxonomies/:id/classes", () => HttpResponse.json(classes)),
    http.get("*/api/classes", ({ request }) => {
      const url = new URL(request.url);
      const scheme = url.searchParams.get("concept_scheme_id");
      const ids = url.searchParams.getAll("ids");
      return list(
        classes.filter(
          (c) => (!scheme || c.concept_scheme_id === scheme) && (!ids.length || ids.includes(c.id)),
        ),
      );
    }),
    http.post("*/api/proposals/:id/apply", async ({ request }) => {
      const body = (await request.json()) as ChangeProposalApplyRequest;
      applies.push(body);
      for (const op of proposal.operations) {
        if (!body.operation_ids.includes(op.id)) continue;
        if (failApply) {
          Object.assign(op, { status: "failed", reason: failApply });
        } else {
          const edit = body.edits?.[op.id];
          Object.assign(op, {
            status: "applied",
            applied_fields: edit ? { ...op.fields, ...edit } : null,
          });
        }
      }
      return HttpResponse.json(proposal);
    }),
    http.post("*/api/proposals/:id/operations", async ({ request }) => {
      const body = (await request.json()) as AddIndividualRequest;
      additions.push(body);
      if (refuseAddition) {
        return HttpResponse.json(
          { detail: { message: "Invalid", errors: [{ seq: 6, ...refuseAddition }] } },
          { status: 422 },
        );
      }
      proposal.operations.push(
        createProposedOperation({
          id: "op-new",
          seq: 6,
          op: "create",
          kind: "individual",
          target_id: null,
          fields: { title: body.title, class_ids: body.class_ids },
          evidence: [{ ...body.passage, page: null }],
          status: "applied",
          added_by_reviewer: true,
          result_entity_id: "ind-new",
          scope: "additive",
        }),
      );
      return HttpResponse.json(proposal, { status: 201 });
    }),
    http.post("*/api/proposals/:id/reject", async ({ request }) => {
      const body = (await request.json()) as ChangeProposalRejectRequest;
      rejects.push(body);
      for (const op of proposal.operations) {
        if (body.operation_ids?.includes(op.id)) {
          Object.assign(op, {
            status: "rejected",
            reason: body.note ?? null,
            reason_code: body.reason_code ?? null,
          });
        }
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
          {t.action && (
            <button type="button" onClick={t.action.onAction} data-testid="toast-probe-action">
              {t.action.label}
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

const onFinish = vi.fn();

async function renderPage() {
  const user = userEvent.setup();
  render(
    <>
      <ReviewPage id="proposal-1" onFinish={onFinish} />
      <ToastProbe />
    </>,
  );
  await screen.findAllByTestId("review-mark", {}, { timeout: 10000 });
  // The layers are known once the classes and schemes load.
  await screen.findByTestId("review-group-scheme-p", {}, { timeout: 10000 });
  return user;
}

const inspectorTitle = () => screen.getByTestId("review-inspector-title");
const markFor = (opId: string) =>
  screen.getAllByTestId("review-mark").find((m) => m.dataset.spanKeys === opId)!;

describe("the review page", () => {
  it("shows the header, origin and progress", async () => {
    const user = await renderPage();
    expect(screen.getByTestId("review-page")).toHaveClass("review-page");
    const header = screen.getByTestId("review-header");
    expect(header).toHaveTextContent("PROPOSAL · SOURCE Edit check · DATASET bench-edit-check");
    expect(within(header).getByRole("heading", { level: 1 })).toHaveTextContent(
      "Review extraction: Edit check",
    );
    expect(screen.getByTestId("review-origin-line")).toHaveTextContent("Proposed by");
    expect(screen.getByTestId("proposal-origin")).toHaveTextContent("single_call v2 · 3f2a9c");
    expect(screen.getByTestId("review-progress")).toHaveAttribute(
      "aria-label",
      "Decision progress",
    );
    expect(screen.getByTestId("review-progress-decided")).toHaveTextContent("1 / 5");
    expect(screen.getByTestId("review-progress-counts")).toHaveTextContent(
      "0 correct · 0 changed · 0 rejected · 1 added",
    );
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "20");
    expect(screen.getByTestId("review-time")).toHaveTextContent(/^\d+:\d\d on this review$/);

    await user.click(screen.getByTestId("review-finish"));
    expect(onFinish).toHaveBeenCalled();
  });

  it("highlights every element's passages with its verdict, the selected one outlined", async () => {
    await renderPage();
    expect(screen.getByTestId("review-source-text")).toHaveClass("review-source__text");
    expect(screen.getByTestId("review-legend")).toHaveTextContent(
      "AwaitingCorrectClass changedNot an elementAdded by you",
    );
    const swatches = screen.getByTestId("review-legend").querySelectorAll(".review-legend__swatch");
    expect([...swatches].map((s) => s.classList[1])).toEqual([
      "review-legend__swatch--awaiting",
      "review-legend__swatch--correct",
      "review-legend__swatch--changed",
      "review-legend__swatch--rejected",
      "review-legend__swatch--added",
    ]);
    const editMark = markFor("op-edit");
    expect(editMark.tagName).toBe("MARK");
    expect(editMark).toHaveTextContent("Edit Check");
    expect(editMark).toHaveAttribute("role", "button");
    expect(editMark).toHaveClass("review-mark", "review-mark--awaiting", "review-mark--selected");
    expect(editMark).toHaveAttribute("aria-current", "true");
    expect(editMark).toHaveAttribute("aria-label", "Edit Check (Edit Check, awaiting)");
    expect(markFor("op-region")).toHaveAttribute(
      "aria-label",
      "Sub-Saharan Africa (Sub-Saharan Africa, awaiting)",
    );
    const addedMark = markFor("op-added");
    expect(addedMark).toHaveClass("review-mark--added");
    expect(addedMark).not.toHaveClass("review-mark--selected");
    expect(markFor("op-region")).toHaveClass("review-mark--awaiting");
    // The extraction review's own classes aren't used here.
    expect(editMark).not.toHaveClass("xr-span");
  });

  it("opens an element from its highlight", async () => {
    const user = await renderPage();
    expect(inspectorTitle()).toHaveTextContent("Edit Check");
    await user.click(markFor("op-region"));
    expect(inspectorTitle()).toHaveTextContent("Sub-Saharan Africa");
    expect(markFor("op-region")).toHaveClass("review-mark--selected");
    expect(screen.getByTestId("review-row-op-region")).toHaveAttribute("aria-selected", "true");
  });

  it("groups the elements by layer, then the relationships", async () => {
    await renderPage();
    const list = screen.getByRole("listbox", { name: "Elements to review" });
    const groups = within(list).getAllByRole("group");
    expect(groups.map((g) => g.getAttribute("aria-label"))).toEqual([
      "Product",
      "Motivation",
      "Relationships",
    ]);
    const productRows = within(groups[0]).getAllByRole("option");
    expect(productRows.map((r) => r.dataset.rowId)).toEqual(["op-edit", "op-ref", "op-added"]);
    const row = screen.getByTestId("review-row-op-edit");
    expect(row).toHaveClass("review-row", "review-row--selected");
    expect(row).toHaveAttribute("aria-selected", "true");
    expect(row).toHaveAttribute("aria-controls", "review-inspector");
    expect(row).toHaveTextContent("Edit Check");
    // A class without a DR reference shows as its title.
    expect(row).toHaveTextContent("Software capability");
    expect(within(row).getByTitle("Software capability")).toHaveClass("review-row__class");
    expect(row).toHaveTextContent("0.97");
    expect(row).toHaveTextContent("awaiting");
    expect(screen.getByTestId("review-row-op-added")).toHaveTextContent("added");
    await waitFor(() =>
      expect(screen.getByTestId("review-row-op-rel")).toHaveTextContent(
        "Reference check → Edit Check",
      ),
    );
    expect(screen.getByTestId("review-row-op-rel")).toHaveTextContent("realizes");
  });

  it("filters to awaiting elements, keeping the selected one", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-added"));
    await user.click(
      within(screen.getByTestId("review-filter")).getByRole("radio", { name: /Awaiting/ }),
    );
    // Decided, but selected: it stays.
    expect(screen.getByTestId("review-row-op-added")).toBeInTheDocument();
    await user.click(screen.getByTestId("review-row-op-edit"));
    expect(screen.queryByTestId("review-row-op-added")).not.toBeInTheDocument();
    await user.click(
      within(screen.getByTestId("review-filter")).getByRole("radio", { name: /All/ }),
    );
    expect(screen.getByTestId("review-row-op-added")).toBeInTheDocument();
  });

  it("shows the evidence, the class's definition and the relationships", async () => {
    await renderPage();
    expect(screen.getByTestId("review-inspector")).toHaveAttribute("role", "region");
    expect(screen.getByTestId("review-inspector-eyebrow")).toHaveTextContent("Individual · p 0.97");
    const classChip = screen.getByTestId("review-inspector-class");
    expect(classChip).toHaveTextContent("Software capability");
    // The class is prominent: a large pill, a button whose overlay explains it.
    expect(classChip).toHaveClass("review-pill", "review-pill--class", "review-pill--lg");
    expect(classChip.tagName).toBe("BUTTON");
    expect(classChip).toHaveAttribute("aria-label", "Class Software capability");
    expect(screen.getByTestId("review-inspector-status")).toHaveTextContent("awaiting");
    expect(screen.getByTestId("review-evidence")).toHaveTextContent("Edit Check");
    expect(screen.getByTestId("review-evidence")).toHaveTextContent("EVIDENCE · 1");
    expect(screen.getByTestId("review-evidence-1")).toHaveClass("review-evidence");
    expect(screen.getByTestId("review-definition")).toHaveTextContent("WHAT THE CLASS MEANS");
    expect(screen.getByTestId("review-definition")).toHaveAttribute(
      "aria-label",
      "What the class means",
    );
    expect(screen.getByTestId("review-definition")).toHaveTextContent(
      "An ability of the software platform.",
    );
    // Each relationship is a card that opens it, read as a sentence with "this" for the element:
    // Reference check realizes → this (it points in), then the other end's class.
    const card = screen.getByTestId("review-relationship-op-rel");
    await waitFor(() => expect(card).toHaveTextContent("Reference checkrealizes →thisawaiting"));
    expect(card.tagName).toBe("A");
    expect(card).toHaveClass("review-relrow");
    expect(card).toHaveAttribute("href", "?selected=op-rel");
    expect(card).toHaveAttribute("data-direction", "in");
    expect(card).toHaveTextContent("product.feature");
    const kinds = [...card.querySelectorAll("[data-pill]")].map((p) => p.getAttribute("data-pill"));
    expect(kinds).toEqual(["predicate", "class"]);
    expect(screen.getByTestId("review-relationships")).toHaveTextContent("ITS RELATIONSHIPS · 1");
  });

  it("accepts as correct with the review time, then opens the next awaiting element", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("review-correct"));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0]).toEqual({
      operation_ids: ["op-edit"],
      amended_at: unamended(["op-edit"]),
      force_stale: [],
      edits: {},
      review_ms: { "op-edit": expect.any(Number) },
    });
    expect(applies[0].review_ms!["op-edit"]).toBeGreaterThanOrEqual(0);
    await waitFor(() => expect(inspectorTitle()).toHaveTextContent("Reference check"));
    await waitFor(() => expect(markFor("op-edit")).toHaveClass("review-mark--correct"));
    expect(screen.getByTestId("review-progress-counts")).toHaveTextContent("1 correct");
  });

  it("accepts with a better class from the picker, then offers it on key 1", async () => {
    const user = await renderPage();
    const picker = within(screen.getByTestId("review-class-picker"));
    expect(picker.getByText("Search all 4 classes")).toBeInTheDocument();
    await user.type(picker.getByRole("combobox"), "product.");
    const options = await picker.findAllByRole("option");
    // The element's own class and derived classes aren't offered.
    expect(options.map((o) => o.textContent)).toEqual(["product.feature"]);
    await user.click(options[0]);
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].edits).toEqual({ "op-edit": { class_ids: ["cls-feature"] } });
    expect(applies[0].review_ms).toEqual({ "op-edit": expect.any(Number) });
    await waitFor(() => expect(markFor("op-edit")).toHaveClass("review-mark--changed"));
    expect(screen.getByTestId("review-progress-counts")).toHaveTextContent("1 changed");

    // Next: Reference check, already a product.feature, so feature isn't suggested.
    await waitFor(() => expect(inspectorTitle()).toHaveTextContent("Reference check"));
    expect(screen.queryByTestId("review-suggestion-1")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("review-row-op-region"));
    const suggestion = screen.getByTestId("review-suggestion-1");
    // A suggestion is a class tag that picks the class; its definition is its title.
    expect(suggestion).toHaveClass("review-suggestion__pick");
    expect(suggestion.parentElement).toHaveClass("review-suggestion");
    expect(suggestion).toHaveAttribute("aria-keyshortcuts", "1");
    expect(suggestion).toHaveAttribute("aria-label", "Accept as product.feature");
    expect(suggestion).toHaveTextContent("1 product.feature");
    expect(suggestion).toHaveAttribute(
      "title",
      "A unit of product functionality a persona can perceive.",
    );
    await user.keyboard("1");
    await waitFor(() => expect(applies).toHaveLength(2));
    expect(applies[1].edits).toEqual({ "op-region": { class_ids: ["cls-feature"] } });
  });

  it("lists the current class's layer-mates first in the picker", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-region"));
    const picker = within(screen.getByTestId("review-class-picker"));
    await user.type(picker.getByRole("combobox"), "o");
    const options = await picker.findAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual([
      "motivation.goal",
      "product.feature",
      "Software capability",
    ]);
  });

  it("clamps a long definition, with Show more and Show less", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-region"));
    const definition = within(screen.getByTestId("review-definition"));
    const text = definition.getByText(STAKEHOLDER_DEFINITION);
    expect(text).toHaveClass("review-definition", "review-definition--clamped");
    const toggle = screen.getByTestId("review-definition-toggle");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveAttribute("aria-controls", text.id);
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(toggle).toHaveTextContent("Show less");
    expect(text).not.toHaveClass("review-definition--clamped");
    // A short definition has nothing to show more of.
    await user.click(screen.getByTestId("review-row-op-edit"));
    expect(screen.queryByTestId("review-definition-toggle")).not.toBeInTheDocument();
  });

  it("rejects with a reason code and a note", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-region"));
    const reasons = screen.getByRole("group", { name: "Not an element, because" });
    expect(
      within(reasons)
        .getAllByRole("button")
        .map((b) => b.textContent),
    ).toEqual([
      "Not in this text",
      "Too generic",
      "Mentioned only",
      "Out of scope",
      "Duplicate",
      "Other",
    ]);
    expect(screen.getByTestId("review-reason-out_of_scope")).toHaveClass("review-reason");
    await user.type(screen.getByTestId("review-note"), "a region, not a party");
    await user.click(screen.getByTestId("review-reason-out_of_scope"));
    await waitFor(() => expect(rejects).toHaveLength(1));
    expect(rejects[0]).toEqual({
      operation_ids: ["op-region"],
      note: "a region, not a party",
      reason_code: "out_of_scope",
      review_ms: { "op-region": expect.any(Number) },
    });
    await waitFor(() => expect(markFor("op-region")).toHaveClass("review-mark--rejected"));
    // The rejected element shows its decision once reopened.
    await user.click(screen.getByTestId("review-row-op-region"));
    expect(screen.getByTestId("review-decided")).toHaveTextContent("Not an element: Out of scope.");
    expect(screen.getByTestId("review-decided-note")).toHaveTextContent("a region, not a party");
    expect(screen.queryByTestId("review-correct")).not.toBeInTheDocument();
  });

  it("opens the reason step on Not an element: prompt, highlight, focus, nothing sent", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-region"));
    // The live region is there, empty, before the prompt: screen readers announce its text.
    expect(screen.getByTestId("review-reasons-prompt")).toBeEmptyDOMElement();
    expect(screen.getByTestId("review-reasons-prompt")).toHaveAttribute("role", "status");
    expect(screen.getByTestId("review-reasons-block")).not.toHaveClass("review-block--prompt");
    await user.click(screen.getByTestId("review-not"));
    expect(screen.getByTestId("review-reasons-block")).toHaveClass("review-block--prompt");
    expect(screen.getByTestId("review-reasons-prompt")).toHaveTextContent(
      "Pick a reason to reject it.",
    );
    expect(screen.getByTestId("review-reasons-prompt")).toHaveAttribute("role", "status");
    expect(screen.getByTestId("review-reason-not_in_text")).toHaveFocus();
    // Nothing is recorded until a reason is picked.
    expect(rejects).toHaveLength(0);
    expect(applies).toHaveLength(0);
    await user.click(screen.getByTestId("review-reason-too_generic"));
    await waitFor(() => expect(rejects).toHaveLength(1));
    expect(rejects[0]).toMatchObject({ operation_ids: ["op-region"], reason_code: "too_generic" });
  });

  it("decides by key: J / K move, A accepts, X opens the reasons", async () => {
    const user = await renderPage();
    await user.keyboard("j");
    expect(inspectorTitle()).toHaveTextContent("Reference check");
    await user.keyboard("j");
    expect(inspectorTitle()).toHaveTextContent("Feedback");
    await user.keyboard("k");
    expect(inspectorTitle()).toHaveTextContent("Reference check");
    await user.keyboard("x");
    expect(screen.getByTestId("review-reason-not_in_text")).toHaveFocus();
    expect(screen.getByTestId("review-reasons-block")).toHaveClass("review-block--prompt");
    expect(screen.getByTestId("review-reasons-prompt")).toHaveTextContent(
      "Pick a reason to reject it.",
    );
    // Typing in the note is text, not a command.
    await user.click(screen.getByTestId("review-note"));
    await user.keyboard("a");
    expect(applies).toHaveLength(0);
    expect(screen.getByTestId("review-note")).toHaveValue("a");
    await user.click(screen.getByTestId("review-inspector-title"));
    await user.keyboard("a");
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].operation_ids).toEqual(["op-ref"]);
  });

  it("decides a relationship only after its ends, with no class to change", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    expect(screen.getByTestId("review-inspector-eyebrow")).toHaveTextContent(
      "Relationship · p 0.90",
    );
    expect(screen.queryByTestId("review-better-class")).not.toBeInTheDocument();
    expect(screen.queryByTestId("review-inspector-class")).not.toBeInTheDocument();
    // Its ends, Reference check (#2) and Edit Check (#1), are undecided.
    expect(screen.getByTestId("review-ends-callout")).toHaveTextContent(
      "Decide #2 and #1 first: this relationship follows their choices.",
    );
    expect(screen.getByTestId("review-correct")).toBeDisabled();
    await user.click(screen.getByTestId("review-inspector-title"));
    await user.keyboard("a");
    expect(applies).toHaveLength(0);

    // Accept both ends; the relationship can be accepted then.
    await user.click(screen.getByTestId("review-row-op-edit"));
    await user.click(screen.getByTestId("review-correct"));
    await waitFor(() => expect(applies).toHaveLength(1));
    await user.click(screen.getByTestId("review-row-op-ref"));
    await user.click(screen.getByTestId("review-correct"));
    await waitFor(() => expect(applies).toHaveLength(2));
    await user.click(screen.getByTestId("review-row-op-rel"));
    await waitFor(() => expect(screen.getByTestId("review-correct")).toBeEnabled());
    expect(screen.queryByTestId("review-ends-callout")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("review-correct"));
    await waitFor(() => expect(applies).toHaveLength(3));
    expect(applies[2].operation_ids).toEqual(["op-rel"]);
  });

  it("offers only rejecting a relationship whose end was rejected", async () => {
    proposal.operations.find((o) => o.id === "op-edit")!.status = "rejected";
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    expect(screen.getByTestId("review-ends-callout")).toHaveTextContent(
      "#1 was rejected, so this relationship can't apply as proposed. Reject it too, or give it another end.",
    );
    expect(screen.queryByTestId("review-correct")).not.toBeInTheDocument();
    expect(screen.getByTestId("review-reject-end")).toHaveAttribute("aria-keyshortcuts", "X");
    expect(screen.getByTestId("review-decide")).toHaveTextContent("X · J / K next");
    // A can't accept it, and says what to do instead.
    await user.click(screen.getByTestId("review-inspector-title"));
    await user.keyboard("a");
    expect(applies).toHaveLength(0);
    expect(await screen.findByText(/This relationship can't be accepted/)).toHaveTextContent(
      "#1 was rejected: press X to reject it too, or give it another end.",
    );
    // Any reason still rejects it.
    await user.click(screen.getByTestId("review-reason-not_in_text"));
    await waitFor(() => expect(rejects).toHaveLength(1));
    expect(rejects[0].operation_ids).toEqual(["op-rel"]);
  });

  it("rejects a relationship whose end was rejected in one click, noting why", async () => {
    proposal.operations.find((o) => o.id === "op-edit")!.status = "rejected";
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    await user.click(screen.getByTestId("review-reject-end"));
    await waitFor(() => expect(rejects).toHaveLength(1));
    expect(rejects[0]).toEqual({
      operation_ids: ["op-rel"],
      note: "An end was rejected: #1 is not an element",
      reason_code: "other",
      review_ms: { "op-rel": expect.any(Number) },
    });
    await user.click(screen.getByTestId("review-row-op-rel"));
    expect(screen.getByTestId("review-decided")).toHaveTextContent("Not a relationship: Other.");
  });

  it("rejects a relationship whose end was rejected on key X", async () => {
    proposal.operations.find((o) => o.id === "op-edit")!.status = "rejected";
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    await user.click(screen.getByTestId("review-inspector-title"));
    await user.keyboard("x");
    await waitFor(() => expect(rejects).toHaveLength(1));
    expect(rejects[0]).toMatchObject({
      operation_ids: ["op-rel"],
      note: "An end was rejected: #1 is not an element",
      reason_code: "other",
    });
  });

  it("keeps a note written before rejecting a relationship whose end was rejected", async () => {
    proposal.operations.find((o) => o.id === "op-edit")!.status = "rejected";
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    await user.type(screen.getByTestId("review-note"), "Edit Check is out");
    await user.click(screen.getByTestId("review-reject-end"));
    await waitFor(() => expect(rejects).toHaveLength(1));
    expect(rejects[0]).toMatchObject({ note: "Edit Check is out", reason_code: "other" });
  });

  it("offers on a rejected element to reject the relationships still awaiting that use it", async () => {
    proposal.operations.find((o) => o.id === "op-edit")!.status = "rejected";
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-edit"));
    expect(screen.getByTestId("review-relationships-callout")).toHaveTextContent(
      "1 relationship uses it and still awaits a decision.",
    );
    await user.click(screen.getByTestId("review-reject-relationships"));
    await waitFor(() => expect(rejects).toHaveLength(1));
    expect(rejects[0]).toEqual({
      operation_ids: ["op-rel"],
      note: "An end was rejected: #1 is not an element",
      reason_code: "other",
    });
    await waitFor(() =>
      expect(screen.queryByTestId("review-relationships-callout")).not.toBeInTheDocument(),
    );
  });

  it("offers nothing more when a rejected element's relationships are all decided", async () => {
    const user = await renderPage();
    // Sub-Saharan Africa is an end of no relationship.
    await user.click(screen.getByTestId("review-row-op-region"));
    await user.click(screen.getByTestId("review-reason-out_of_scope"));
    await waitFor(() => expect(rejects).toHaveLength(1));
    await screen.findByText("Operation rejected");
    expect(screen.queryByTestId("toast-probe-action")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("review-row-op-region"));
    expect(screen.queryByTestId("review-relationships-callout")).not.toBeInTheDocument();
  });

  it("uses an existing individual for a near match, with no class change", async () => {
    Object.assign(proposal.operations.find((o) => o.id === "op-region")!, {
      alternatives: [
        { kind: "existing", entity_id: "ind-1", similarity: 0.93, title: "LLM Provider Router" },
      ],
    });
    const user = await renderPage();
    // Pick a class for Edit Check, so it is suggested afterwards.
    const picker = within(screen.getByTestId("review-class-picker"));
    await user.type(picker.getByRole("combobox"), "product.");
    await user.click((await picker.findAllByRole("option"))[0]);
    await waitFor(() => expect(applies).toHaveLength(1));

    await user.click(screen.getByTestId("review-row-op-region"));
    // The existing individual is chosen by default: no class can be picked with it.
    expect(screen.getByTestId("operation-near-match")).toBeInTheDocument();
    expect(screen.getByTestId("review-correct")).toHaveTextContent("Correct: use existing");
    expect(screen.getByTestId("review-class-locked")).toBeInTheDocument();
    expect(screen.getByTestId("review-suggestion-1")).toBeDisabled();
    expect(within(screen.getByTestId("review-class-picker")).getByRole("combobox")).toBeDisabled();
    await user.click(screen.getByTestId("review-inspector-title"));
    await user.keyboard("1");
    expect(applies).toHaveLength(1);
    await user.keyboard("a");
    await waitFor(() => expect(applies).toHaveLength(2));
    expect(applies[1]).toMatchObject({
      operation_ids: ["op-region"],
      chosen_alternatives: { "op-region": { kind: "existing", entity_id: "ind-1" } },
      edits: {},
    });
  });

  it("creates a near match as new when chosen, with a class change", async () => {
    Object.assign(proposal.operations.find((o) => o.id === "op-edit")!, {
      alternatives: [
        { kind: "existing", entity_id: "ind-1", similarity: 0.9, title: "LLM Provider Router" },
      ],
    });
    const user = await renderPage();
    await user.click(
      within(screen.getByTestId("operation-near-match-option-new")).getByRole("radio"),
    );
    expect(screen.getByTestId("review-correct")).toHaveTextContent(/^Correct$/);
    const picker = within(screen.getByTestId("review-class-picker"));
    await user.type(picker.getByRole("combobox"), "product.");
    await user.click((await picker.findAllByRole("option"))[0]);
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].edits).toEqual({ "op-edit": { class_ids: ["cls-feature"] } });
    expect(applies[0].chosen_alternatives).toBeUndefined();
  });

  it("decides once while a key is held down", async () => {
    await renderPage();
    fireEvent.keyDown(document.body, { key: "a", repeat: true });
    fireEvent.keyDown(document.body, { key: "x", repeat: true });
    expect(screen.getByTestId("review-reason-not_in_text")).not.toHaveFocus();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(applies).toHaveLength(0);
    fireEvent.keyDown(document.body, { key: "a" });
    await waitFor(() => expect(applies).toHaveLength(1));
  });

  it("ignores review keys while a dialog is open", async () => {
    proposal.operations.find((o) => o.id === "op-edit")!.stale = true;
    const user = await renderPage();
    await user.click(screen.getByTestId("review-correct"));
    expect(await screen.findByTestId("review-force-message")).toBeInTheDocument();
    fireEvent.keyDown(document.body, { key: "j" });
    fireEvent.keyDown(screen.getByTestId("review-force-message"), { key: "k" });
    expect(inspectorTitle()).toHaveTextContent("Edit Check");
    await user.click(screen.getByRole("button", { name: "Apply anyway" }));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0]).toMatchObject({
      operation_ids: ["op-edit"],
      amended_at: unamended(["op-edit"]),
      force_stale: ["op-edit"],
    });
  });

  it("says why an apply failed and stays on the element", async () => {
    failApply = "domain_range_mismatch: target is Place, not Room";
    const user = await renderPage();
    await user.click(screen.getByTestId("review-correct"));
    await waitFor(() =>
      expect(screen.getByTestId("toast-error")).toHaveTextContent(
        "Apply failed | domain_range_mismatch: target is Place, not Room",
      ),
    );
    expect(inspectorTitle()).toHaveTextContent("Edit Check");
    await waitFor(() =>
      expect(screen.getByTestId("review-failed")).toHaveTextContent(
        "The last apply failed: domain_range_mismatch: target is Place, not Room",
      ),
    );
    expect(screen.getByTestId("review-failed")).toHaveAttribute("role", "alert");
  });

  it("shows an added element's decision read-only", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-added"));
    expect(screen.getByTestId("review-decided")).toHaveTextContent(
      "Added by you asproduct.feature",
    );
    expect(screen.getByTestId("review-decided-class")).toHaveClass(
      "review-pill",
      "review-pill--class",
    );
    // Decided: the controls wait behind Change the decision.
    expect(screen.queryByTestId("review-reasons")).not.toBeInTheDocument();
    expect(screen.getByTestId("review-change-decision")).toHaveAttribute("aria-expanded", "false");
  });

  it("says when the source can't be shown", async () => {
    server.use(
      http.get("*/api/sources/:id", () =>
        HttpResponse.json({ ...source, removed_at: "2026-11-11T00:00:00Z" }),
      ),
    );
    render(<ReviewPage id="proposal-1" onFinish={onFinish} />);
    expect(
      await screen.findByText(/The source was removed/, {}, { timeout: 10000 }),
    ).toHaveAttribute("data-testid", "review-source-unavailable");
    expect(screen.queryByTestId("review-mark")).not.toBeInTheDocument();
    // The elements can still be decided.
    expect(await screen.findByTestId("review-correct")).toBeInTheDocument();
  });
});

describe("review time", () => {
  const START = new Date("2026-11-17T10:00:00Z").getTime();
  afterEach(() => vi.useRealTimers());

  it("shows the active time on this review", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(START);
    await renderPage();
    vi.setSystemTime(START + 65_000);
    await waitFor(
      () => expect(screen.getByTestId("review-time")).toHaveTextContent("1:05 on this review"),
      { timeout: 3000 },
    );
  });

  it("sends the active time on the element, leaving out an idle gap", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(START);
    const user = await renderPage();
    vi.setSystemTime(START + 4_000);
    fireEvent.pointerMove(window);
    // Away for three minutes: not counted.
    vi.setSystemTime(START + 4_000 + 180_000);
    fireEvent.pointerMove(window);
    vi.setSystemTime(START + 4_000 + 180_000 + 2_500);
    await user.click(screen.getByTestId("review-correct"));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].review_ms).toEqual({ "op-edit": 6_500 });
  });
});

/** Select `quote` (its first occurrence) in the source text, as a reader's drag would. */
function selectText(quote: string, from = 0, text = TEXT) {
  const container = screen.getByTestId("review-source-text");
  const start = text.indexOf(quote, from);
  const end = start + quote.length;
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const range = document.createRange();
  let offset = 0;
  while (walker.nextNode()) {
    const node = walker.currentNode as Text;
    const length = node.data.length;
    if (start >= offset && start <= offset + length) range.setStart(node, start - offset);
    if (end >= offset && end <= offset + length) {
      range.setEnd(node, end - offset);
      break;
    }
    offset += length;
  }
  const selection = window.getSelection()!;
  selection.removeAllRanges();
  selection.addRange(range);
  return { start, end };
}

describe("adding an element from selected text", () => {
  const popover = () =>
    screen.queryByRole("dialog", { name: "Selected text · not in the proposal" });

  it("opens the add form on a selection, and closes it with Escape or Cancel", async () => {
    const user = await renderPage();
    expect(screen.getByTestId("review-source-hint")).toHaveTextContent(
      "Select any text to add an element the pipeline missed. Click a highlight to open it.",
    );
    expect(screen.queryByTestId("review-add-unavailable")).not.toBeInTheDocument();
    selectText("feel safe");
    fireEvent.mouseUp(screen.getByTestId("review-source-selectable"));
    const dialog = popover()!;
    expect(dialog).toHaveAttribute("data-testid", "review-add-popover");
    expect(dialog).toHaveClass("review-add");
    expect(within(dialog).getByTestId("review-add-quote")).toHaveTextContent("feel safe");
    const title = within(dialog).getByLabelText(/Title/);
    expect(title).toHaveValue("feel safe");
    expect(title).toHaveFocus();
    expect(within(dialog).getByRole("combobox")).toHaveAccessibleName("Search the classes");
    await user.keyboard("{Escape}");
    expect(popover()).not.toBeInTheDocument();

    selectText("feel safe");
    fireEvent.mouseUp(screen.getByTestId("review-source-selectable"));
    await user.click(screen.getByTestId("review-add-cancel"));
    expect(popover()).not.toBeInTheDocument();
  });

  it("opens on a selection made from the keyboard", async () => {
    await renderPage();
    selectText("Newcomers");
    fireEvent.keyUp(document, { key: "ArrowRight", shiftKey: true });
    expect(popover()).toBeInTheDocument();
    expect(screen.getByTestId("review-add-title")).toHaveValue("Newcomers");
  });

  it("ignores a click that selects nothing", async () => {
    const user = await renderPage();
    window.getSelection()!.removeAllRanges();
    await user.click(screen.getByTestId("review-source-selectable"));
    expect(popover()).not.toBeInTheDocument();
  });

  it("asks for a title and a class, clearing each error as it is fixed", async () => {
    const user = await renderPage();
    selectText("feel safe");
    fireEvent.mouseUp(screen.getByTestId("review-source-selectable"));
    await user.clear(screen.getByTestId("review-add-title"));
    await user.click(screen.getByTestId("review-add-submit"));
    expect(screen.getByText("Give the element a title.")).toBeInTheDocument();
    expect(screen.getByTestId("review-add-title")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Choose its class.")).toBeInTheDocument();
    await user.type(screen.getByTestId("review-add-title"), "S");
    expect(screen.queryByText("Give the element a title.")).not.toBeInTheDocument();
    const picker = within(screen.getByTestId("review-add-class-picker"));
    await user.type(picker.getByRole("combobox"), "goal");
    await user.click(await picker.findByRole("option", { name: "motivation.goal" }));
    expect(screen.queryByText("Choose its class.")).not.toBeInTheDocument();
    expect(additions).toHaveLength(0);
  });

  it("adds the selection as an element, shown as added and opened in the inspector", async () => {
    const user = await renderPage();
    const { start, end } = selectText("feel safe");
    fireEvent.mouseUp(screen.getByTestId("review-source-selectable"));
    await user.clear(screen.getByTestId("review-add-title"));
    await user.type(screen.getByTestId("review-add-title"), "Feeling safe");
    const picker = within(screen.getByTestId("review-add-class-picker"));
    await user.type(picker.getByRole("combobox"), "goal");
    await user.click(await picker.findByRole("option", { name: "motivation.goal" }));
    expect(screen.getByTestId("review-add-class-chosen")).toHaveTextContent("motivation.goal");
    await user.click(screen.getByTestId("review-add-submit"));

    await waitFor(() => expect(additions).toHaveLength(1));
    expect(additions[0]).toEqual({
      title: "Feeling safe",
      class_ids: ["cls-goal"],
      passage: { source_id: "src-1", start, end, quote: "feel safe" },
      review_ms: expect.any(Number),
    });
    await waitFor(() => expect(popover()).not.toBeInTheDocument());
    expect(screen.getByTestId("toast-success")).toHaveTextContent(
      "Added Feeling safe | As motivation.goal",
    );
    await waitFor(() => expect(inspectorTitle()).toHaveTextContent("Feeling safe"));
    expect(markFor("op-new")).toHaveClass("review-mark--added", "review-mark--selected");
    expect(screen.getByTestId("review-row-op-new")).toHaveTextContent("added");
    expect(screen.getByTestId("review-progress-counts")).toHaveTextContent("2 added");
    expect(screen.getByTestId("review-decided")).toHaveTextContent(
      "Added by you asmotivation.goal",
    );
  });

  it("starts with the class picked most recently", async () => {
    const user = await renderPage();
    const picker = within(screen.getByTestId("review-class-picker"));
    await user.type(picker.getByRole("combobox"), "product.");
    await user.click((await picker.findAllByRole("option"))[0]);
    await waitFor(() => expect(applies).toHaveLength(1));
    selectText("feel safe");
    fireEvent.mouseUp(screen.getByTestId("review-source-selectable"));
    expect(screen.getByTestId("review-add-class-chosen")).toHaveTextContent("product.feature");
    await user.click(screen.getByTestId("review-add-submit"));
    await waitFor(() => expect(additions).toHaveLength(1));
    expect(additions[0].class_ids).toEqual(["cls-feature"]);
  });

  it("shows a refusal in the form, cleared on change", async () => {
    refuseAddition = { code: "duplicate_title", message: "An individual titled 'feel safe' …" };
    const user = await renderPage();
    selectText("feel safe");
    fireEvent.mouseUp(screen.getByTestId("review-source-selectable"));
    const picker = within(screen.getByTestId("review-add-class-picker"));
    await user.type(picker.getByRole("combobox"), "product.");
    await user.click((await picker.findAllByRole("option"))[0]);
    await user.click(screen.getByTestId("review-add-submit"));
    const error = await screen.findByTestId("review-add-error");
    expect(error).toHaveAttribute("role", "alert");
    expect(error).toHaveTextContent("feel safe already exists in this dataset as product.feature.");
    expect(popover()).toBeInTheDocument();
    expect(screen.queryByTestId("toast-error")).not.toBeInTheDocument();
    await user.type(screen.getByTestId("review-add-title"), "!");
    expect(screen.queryByTestId("review-add-error")).not.toBeInTheDocument();
  });

  it("isn't offered when the proposal doesn't record its source", async () => {
    proposal.client_metadata = {};
    await renderPage();
    expect(screen.getByTestId("review-source-hint")).toHaveTextContent(
      /^Click a highlight to open it\.$/,
    );
    expect(screen.getByTestId("review-add-unavailable")).toHaveTextContent(
      "No element can be added here: the proposal doesn't record the source",
    );
    selectText("feel safe");
    fireEvent.mouseUp(screen.getByTestId("review-source-selectable"));
    expect(popover()).not.toBeInTheDocument();
  });

  it("isn't offered on a reverted proposal", async () => {
    proposal.status = "reverted";
    await renderPage();
    expect(screen.getByTestId("review-add-unavailable")).toHaveTextContent(
      "the proposal was reverted.",
    );
    selectText("feel safe");
    fireEvent.mouseUp(screen.getByTestId("review-source-selectable"));
    expect(popover()).not.toBeInTheDocument();
  });

  it("sends code-point offsets after an emoji, and a selection over lines as a one-line title", async () => {
    const emojiText = `😀 ${TEXT}\nMore notes here.`;
    server.use(
      http.get("*/api/sources/:id/text", () =>
        HttpResponse.json({
          source_id: "src-1",
          page: null,
          pages: null,
          start: 0,
          end: [...emojiText].length,
          text: emojiText,
        }),
      ),
    );
    // The stored passages count the emoji as one code point (and its space as one).
    for (const op of proposal.operations) {
      op.evidence = (op.evidence ?? []).map((e) => ({
        ...e,
        start: (e.start as number) + 2,
        end: (e.end as number) + 2,
      }));
    }
    const user = await renderPage();
    // Placed in the browser's units: one more than the code points.
    expect(markFor("op-region")).toHaveTextContent("Sub-Saharan Africa");
    const { start, end } = selectText("safe.\nMore", 0, emojiText);
    fireEvent.mouseUp(screen.getByTestId("review-source-selectable"));
    expect(screen.getByTestId("review-add-title")).toHaveValue("safe. More");
    const picker = within(screen.getByTestId("review-add-class-picker"));
    await user.type(picker.getByRole("combobox"), "goal");
    await user.click(await picker.findByRole("option", { name: "motivation.goal" }));
    await user.click(screen.getByTestId("review-add-submit"));
    await waitFor(() => expect(additions).toHaveLength(1));
    // The emoji is two UTF-16 units but one code point: the server's offsets are one less.
    expect(additions[0].passage).toEqual({
      source_id: "src-1",
      start: start - 1,
      end: end - 1,
      quote: "safe.\nMore",
    });
    expect(additions[0].title).toBe("safe. More");
  });

  it("keeps review keys off while the form is open, and Escape closes it from anywhere", async () => {
    const user = await renderPage();
    selectText("feel safe");
    fireEvent.mouseUp(screen.getByTestId("review-source-selectable"));
    expect(popover()).toBeInTheDocument();
    (document.activeElement as HTMLElement).blur();
    expect(document.activeElement).toBe(document.body);
    await user.keyboard("a");
    await user.keyboard("j");
    expect(applies).toHaveLength(0);
    expect(inspectorTitle()).toHaveTextContent("Edit Check");
    await user.keyboard("{Escape}");
    expect(popover()).not.toBeInTheDocument();
    // Focus comes back to the source text.
    expect(screen.getByTestId("review-source-selectable")).toHaveFocus();
    expect(screen.getByTestId("review-source-selectable")).toHaveAttribute("tabindex", "-1");
  });

  it("returns focus to the source text after Cancel and after adding", async () => {
    const user = await renderPage();
    selectText("feel safe");
    fireEvent.mouseUp(screen.getByTestId("review-source-selectable"));
    await user.click(screen.getByTestId("review-add-cancel"));
    expect(screen.getByTestId("review-source-selectable")).toHaveFocus();

    selectText("feel safe");
    fireEvent.mouseUp(screen.getByTestId("review-source-selectable"));
    const picker = within(screen.getByTestId("review-add-class-picker"));
    await user.type(picker.getByRole("combobox"), "goal");
    await user.click(await picker.findByRole("option", { name: "motivation.goal" }));
    await user.click(screen.getByTestId("review-add-submit"));
    await waitFor(() => expect(popover()).not.toBeInTheDocument());
    expect(screen.getByTestId("review-source-selectable")).toHaveFocus();
  });

  it("closes on a press outside the form, but not on one in the source text", async () => {
    await renderPage();
    selectText("feel safe");
    fireEvent.mouseUp(screen.getByTestId("review-source-selectable"));
    fireEvent.mouseDown(screen.getByTestId("review-add-title"));
    fireEvent.mouseDown(screen.getByTestId("review-source-text"));
    expect(popover()).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByTestId("review-progress"));
    expect(popover()).not.toBeInTheDocument();
  });

  it("stays open when a press inside it removes its own target (picking from the class list)", async () => {
    await renderPage();
    selectText("feel safe");
    fireEvent.mouseDown(screen.getByTestId("review-source-selectable"));
    fireEvent.mouseUp(screen.getByTestId("review-source-selectable"));
    // An option that is gone from the page once pressed, as a picked option is.
    const option = document.createElement("div");
    screen.getByTestId("review-add-popover").append(option);
    option.addEventListener("mousedown", () => option.remove());
    fireEvent.mouseDown(option);
    expect(popover()).toBeInTheDocument();
  });

  it("opens from Shift only for a selection in the source text, made outside fields", async () => {
    const user = await renderPage();
    // A selection outside the source text.
    const header = screen.getByTestId("review-header");
    const range = document.createRange();
    range.selectNodeContents(header);
    window.getSelection()!.removeAllRanges();
    window.getSelection()!.addRange(range);
    fireEvent.keyUp(document, { key: "Shift", shiftKey: true });
    expect(popover()).not.toBeInTheDocument();
    // Shift typed into the note, even with source text selected.
    await user.click(screen.getByTestId("review-note"));
    selectText("feel safe");
    fireEvent.keyUp(screen.getByTestId("review-note"), { key: "Shift", shiftKey: true });
    expect(popover()).not.toBeInTheDocument();
    // In the source text: it opens; a further Shift while it is open changes nothing.
    fireEvent.keyUp(document, { key: "ArrowRight", shiftKey: true });
    expect(screen.getByTestId("review-add-title")).toHaveValue("feel safe");
    selectText("Newcomers");
    fireEvent.keyUp(document, { key: "Shift", shiftKey: true });
    expect(screen.getByTestId("review-add-title")).toHaveValue("feel safe");
  });

  it("sends the active time from opening the form to adding", async () => {
    const START = new Date("2026-11-17T10:00:00Z").getTime();
    vi.useFakeTimers({ toFake: ["Date"] });
    try {
      vi.setSystemTime(START);
      const user = await renderPage();
      selectText("feel safe");
      fireEvent.mouseUp(screen.getByTestId("review-source-selectable"));
      const picker = within(screen.getByTestId("review-add-class-picker"));
      await user.type(picker.getByRole("combobox"), "goal");
      await user.click(await picker.findByRole("option", { name: "motivation.goal" }));
      vi.setSystemTime(START + 3_000);
      fireEvent.pointerMove(window);
      vi.setSystemTime(START + 5_000);
      await user.click(screen.getByTestId("review-add-submit"));
      await waitFor(() => expect(additions).toHaveLength(1));
      expect(additions[0].review_ms).toBe(5_000);
    } finally {
      vi.useRealTimers();
    }
  });
});

/** Make the proposal a gold check of edit_check (or the holdout). */
function makeGoldCheck(split: "dev" | "holdout" = "dev") {
  const origin = {
    pipeline_type: "individual_extraction",
    implementation_id: "gold_check",
    configuration_ref: "gold",
    configuration_version: 1,
    digest: "abc123def456",
  };
  proposal.origin = origin;
  proposal.client_metadata = {
    source_id: "src-1",
    origin,
    gold_check: {
      document: split === "dev" ? "edit_check" : "wikimedia_enterprise",
      split,
      elements: {
        edit: {
          key: "edit",
          tier: "core",
          acceptable_classes: ["product.feature"],
          aliases: ["EditCheck"],
        },
        ref: { key: "ref", tier: "supporting", acceptable_classes: [], aliases: [] },
        region: {
          key: "region",
          tier: "core",
          acceptable_classes: ["motivation.goal"],
          aliases: [],
        },
      },
      relationships: {
        "5": { source: "ref", predicate: "realizes", target: "edit", tier: "supporting" },
      },
    },
  };
}

describe("gold mode", () => {
  const tier = () => screen.getByTestId("review-tier");

  it("says what a tier means: a hint under the control, the scorer's rule on the label", async () => {
    makeGoldCheck();
    const user = await renderPage();
    expect(screen.getByTestId("review-tier-hint")).toHaveTextContent(
      "Core: the text names it and says what it is or does. Supporting: only mentioned in passing. Missing a core one also costs core recall.",
    );
    const label = screen.getByTestId("review-tier-label");
    expect(label.tagName).toBe("BUTTON");
    expect(label).toHaveClass("review-hint-label");
    expect(tier().querySelector('[aria-labelledby="review-tier-label"]')).not.toBeNull();
    await user.hover(label);
    const overlay = await screen.findByTestId("review-hint-overlay");
    expect(overlay).toHaveAttribute("role", "tooltip");
    expect(label).toHaveAttribute("aria-describedby", overlay.id);
    expect(overlay).toHaveTextContent("A core miss also lowers core recall");
    // A relationship's tier is recorded, not scored: it says so.
    await user.click(screen.getByTestId("review-row-op-rel"));
    expect(screen.getByTestId("review-tier-hint")).toHaveTextContent(
      "Recorded in the gold file only. Relationship scores count every gold relationship alike",
    );
  });

  it("says it is a gold check, with its split", async () => {
    makeGoldCheck();
    await renderPage();
    expect(
      within(screen.getByTestId("review-header")).getByRole("heading", { level: 1 }),
    ).toHaveTextContent("Gold check: edit_check");
    const split = screen.getByTestId("review-gold-split");
    expect(split).toHaveTextContent("dev");
    expect(split).toHaveClass("chip--cyan");
    expect(screen.queryByTestId("review-gold-holdout")).not.toBeInTheDocument();
  });

  it("notes the holdout rule on a holdout check", async () => {
    makeGoldCheck("holdout");
    await renderPage();
    expect(screen.getByTestId("review-gold-split")).toHaveClass("chip--violet");
    expect(screen.getByTestId("review-gold-holdout")).toHaveTextContent(
      "Holdout: check it like the others; its element-level errors are never shown where pipelines are tuned.",
    );
  });

  it("shows the aliases and tier, offers the acceptable classes, and sends what is noted", async () => {
    makeGoldCheck();
    const user = await renderPage();
    expect(screen.getByTestId("review-gold-aliases")).toHaveTextContent("Also called EditCheck");
    expect(within(tier()).getByRole("radio", { name: "Core" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    // A class picked earlier (here for Reference check) is offered after gold's acceptable ones.
    await user.click(screen.getByTestId("review-row-op-ref"));
    const picker = within(screen.getByTestId("review-class-picker"));
    await user.type(picker.getByRole("combobox"), "stake");
    await user.click(await picker.findByRole("option", { name: "motivation.stakeholder" }));
    await waitFor(() => expect(applies).toHaveLength(1));
    await user.click(screen.getByTestId("review-row-op-edit"));

    // The gold's acceptable class: first, shown as acceptable in gold, not a toggle.
    expect(screen.getByTestId("review-suggestion-1")).toHaveTextContent("1 product.feature");
    const inGold = screen.getByTestId("review-defensible-1");
    expect(inGold).toHaveTextContent("in gold");
    expect(inGold).toHaveAttribute("aria-label", "product.feature is acceptable in gold");
    expect(inGold).toHaveAttribute("aria-pressed", "true");
    expect(inGold).toBeDisabled();
    expect(inGold).toHaveClass(
      "review-suggestion__defensible--on",
      "review-suggestion__defensible--gold",
    );
    // The other class toggles.
    expect(screen.getByTestId("review-suggestion-2")).toHaveTextContent("2 motivation.stakeholder");
    const toggle = screen.getByTestId("review-defensible-2");
    expect(toggle).toHaveTextContent("defensible");
    expect(toggle).toHaveAttribute("aria-label", "motivation.stakeholder is also defensible");
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(toggle).toHaveClass("review-suggestion__defensible--on");
    await user.click(screen.getByTestId("review-correct"));
    await waitFor(() => expect(applies).toHaveLength(2));
    expect(applies[1].annotations).toEqual({ "op-edit": { also_defensible: ["cls-stakeholder"] } });
  });

  it("sends a flipped tier, and nothing when nothing is noted", async () => {
    makeGoldCheck();
    const user = await renderPage();
    await user.click(within(tier()).getByRole("radio", { name: "Supporting" }));
    await user.click(screen.getByTestId("review-correct"));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].annotations).toEqual({ "op-edit": { tier: "supporting" } });
    // Next: Reference check, nothing noted.
    await waitFor(() => expect(inspectorTitle()).toHaveTextContent("Reference check"));
    expect(within(tier()).getByRole("radio", { name: "Supporting" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await user.click(screen.getByTestId("review-correct"));
    await waitFor(() => expect(applies).toHaveLength(2));
    expect(applies[1].annotations).toBeUndefined();
  });

  it("keeps the replaced class as also defensible when asked", async () => {
    makeGoldCheck();
    const user = await renderPage();
    const keep = within(screen.getByTestId("review-keep-old")).getByRole("checkbox", {
      name: "Keep Software capability as also defensible",
    });
    expect(keep).not.toBeChecked();
    await user.click(keep);
    await user.click(screen.getByTestId("review-suggestion-1"));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].edits).toEqual({ "op-edit": { class_ids: ["cls-feature"] } });
    expect(applies[0].annotations).toEqual({ "op-edit": { also_defensible: ["cls-capability"] } });
  });

  it("needs a note to reject, the message clearing once there is one", async () => {
    makeGoldCheck();
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-region"));
    expect(screen.getByTestId("review-reason-out_of_scope")).toBeDisabled();
    expect(screen.getByTestId("review-note-required")).toHaveTextContent(
      "Write why it is not an element to reject it",
    );
    expect(screen.getByTestId("review-note")).toHaveAttribute(
      "aria-describedby",
      "review-note-required",
    );
    // Not an element goes to the note while it is empty, and says why.
    await user.click(screen.getByTestId("review-not"));
    expect(screen.getByTestId("review-note")).toHaveFocus();
    expect(screen.getByTestId("review-reasons-block")).toHaveClass("review-block--prompt");
    expect(screen.getByTestId("review-reasons-prompt")).toHaveTextContent(
      "Write why in the note, then pick a reason to reject it.",
    );
    expect(rejects).toHaveLength(0);
    // X does the same.
    await user.click(screen.getByTestId("review-inspector-title"));
    await user.keyboard("x");
    expect(screen.getByTestId("review-note")).toHaveFocus();
    await user.type(screen.getByTestId("review-note"), "A region, not a party");
    expect(screen.queryByTestId("review-note-required")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Write why it is not an element to reject it/),
    ).not.toBeInTheDocument();
    await user.click(screen.getByTestId("review-reason-out_of_scope"));
    await waitFor(() => expect(rejects).toHaveLength(1));
    expect(rejects[0]).toMatchObject({
      operation_ids: ["op-region"],
      note: "A region, not a party",
      reason_code: "out_of_scope",
    });
  });

  it("gives a relationship its gold tier", async () => {
    makeGoldCheck();
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    expect(within(tier()).getByRole("radio", { name: "Supporting" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("asks an added element's tier, supporting to start with", async () => {
    makeGoldCheck();
    const user = await renderPage();
    selectText("feel safe");
    fireEvent.mouseUp(screen.getByTestId("review-source-selectable"));
    const addTier = screen.getByTestId("review-add-tier");
    expect(within(addTier).getByRole("radio", { name: "Supporting" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await user.click(within(addTier).getByRole("radio", { name: "Core" }));
    const picker = within(screen.getByTestId("review-add-class-picker"));
    await user.type(picker.getByRole("combobox"), "goal");
    await user.click(await picker.findByRole("option", { name: "motivation.goal" }));
    await user.click(screen.getByTestId("review-add-submit"));
    await waitFor(() => expect(additions).toHaveLength(1));
    expect(additions[0].annotation).toEqual({ tier: "core" });
  });

  it("needs no note to reject a relationship", async () => {
    makeGoldCheck();
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    expect(screen.getByTestId("review-reason-not_in_text")).toBeEnabled();
    expect(screen.queryByTestId("review-note-required")).not.toBeInTheDocument();
    expect(screen.getByText("Note, optional · kept with the decision")).toBeInTheDocument();
  });

  // #1641: an individual rejected, the relationships using it must stay decidable.
  it("rejects an individual, then its relationship from the inspector by key", async () => {
    makeGoldCheck();
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-edit"));
    await user.type(screen.getByTestId("review-note"), "a product, not a capability");
    await user.click(screen.getByTestId("review-reason-too_generic"));
    await waitFor(() => expect(rejects).toHaveLength(1));

    await user.click(screen.getByTestId("review-row-op-rel"));
    await waitFor(() => expect(screen.getByTestId("review-reject-end")).toBeEnabled());
    await user.click(screen.getByTestId("review-inspector-title"));
    await user.keyboard("x");
    await waitFor(() => expect(rejects).toHaveLength(2));
    expect(rejects[1]).toEqual({
      operation_ids: ["op-rel"],
      note: "An end was rejected: #1 is not an element",
      reason_code: "other",
      review_ms: { "op-rel": expect.any(Number) },
    });
    await waitFor(() =>
      expect(screen.getByTestId("review-row-op-rel")).toHaveTextContent("not a relationship"),
    );
  });

  it("offers to reject the relationships using an individual once it is rejected", async () => {
    makeGoldCheck();
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-edit"));
    await user.type(screen.getByTestId("review-note"), "a product, not a capability");
    await user.click(screen.getByTestId("review-reason-too_generic"));
    await waitFor(() => expect(rejects).toHaveLength(1));
    const offer = await screen.findByText(/1 relationship uses Edit Check: reject it too\?/);
    expect(offer).toHaveTextContent('#5 would be rejected as "an end was rejected".');
    await user.click(within(offer).getByTestId("toast-probe-action"));
    await waitFor(() => expect(rejects).toHaveLength(2));
    expect(rejects[1]).toEqual({
      operation_ids: ["op-rel"],
      note: "An end was rejected: #1 is not an element",
      reason_code: "other",
    });
    // Clicked again once they are decided, it sends nothing more.
    await waitFor(() =>
      expect(screen.getByTestId("review-row-op-rel")).toHaveTextContent("not a relationship"),
    );
    await user.click(within(offer).getByTestId("toast-probe-action"));
    expect(rejects).toHaveLength(2);
  });

  it("numbers and keys only the first three suggestions", async () => {
    makeGoldCheck();
    const driver = createClass({
      id: "cls-driver",
      concept_scheme_id: "scheme-m",
      taxonomy_id: "tax-1",
      identifier: "motivation_driver",
      title: "Driver",
      external_references: [{ source: "documentation_robotics", identifier: "motivation.driver" }],
    });
    const all = [...classes, driver];
    server.use(
      http.get("*/api/taxonomies/:id/classes", () => HttpResponse.json(all)),
      http.get("*/api/classes", ({ request }) => {
        const url = new URL(request.url);
        const scheme = url.searchParams.get("concept_scheme_id");
        const ids = url.searchParams.getAll("ids");
        const items = all.filter(
          (c) => (!scheme || c.concept_scheme_id === scheme) && (!ids.length || ids.includes(c.id)),
        );
        return HttpResponse.json({ items, total: items.length, limit: 500, offset: 0 });
      }),
    );
    const elements = (
      proposal.client_metadata!.gold_check as {
        elements: Record<string, { acceptable_classes: string[] }>;
      }
    ).elements;
    elements.region.acceptable_classes = [
      "product.feature",
      "motivation.goal",
      "motivation.driver",
      "product.softwarecapability",
    ];
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-region"));
    expect(screen.getByTestId("review-suggestion-3")).toHaveAttribute("aria-keyshortcuts", "3");
    expect(screen.getByTestId("review-suggestion-3")).toHaveTextContent(/^3 motivation\.driver/);
    const fourth = screen.getByTestId("review-suggestion-4");
    expect(fourth).not.toHaveAttribute("aria-keyshortcuts");
    expect(fourth).toHaveTextContent(/^Software capability/);
  });

  it("hides keeping the old class while a near match uses the existing individual", async () => {
    makeGoldCheck();
    Object.assign(proposal.operations.find((o) => o.id === "op-edit")!, {
      alternatives: [
        { kind: "existing", entity_id: "ind-1", similarity: 0.9, title: "LLM Provider Router" },
      ],
    });
    const user = await renderPage();
    expect(screen.queryByTestId("review-keep-old")).not.toBeInTheDocument();
    await user.click(
      within(screen.getByTestId("operation-near-match-option-new")).getByRole("radio"),
    );
    expect(screen.getByTestId("review-keep-old")).toBeInTheDocument();
  });

  it("changes nothing for a normal proposal", async () => {
    const user = await renderPage();
    expect(screen.queryByTestId("review-tier")).not.toBeInTheDocument();
    expect(screen.queryByTestId("review-gold-split")).not.toBeInTheDocument();
    expect(screen.queryByTestId("review-defensible-1")).not.toBeInTheDocument();
    expect(screen.queryByTestId("review-keep-old")).not.toBeInTheDocument();
    expect(screen.getByTestId("review-reason-out_of_scope")).toBeEnabled();
    expect(screen.queryByTestId("review-note-required")).not.toBeInTheDocument();
    selectText("feel safe");
    fireEvent.mouseUp(screen.getByTestId("review-source-selectable"));
    expect(screen.queryByTestId("review-add-tier")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("review-add-cancel"));
  });
});

describe("while the classes load", () => {
  it("shows placeholders, not class ids, and groups by layer once loaded", async () => {
    let release: () => void = () => {};
    const loaded = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get("*/api/taxonomies/:id/classes", async () => {
        await loaded;
        return HttpResponse.json(classes);
      }),
    );
    render(<ReviewPage id="proposal-1" onFinish={onFinish} />);
    const group = await screen.findByTestId("review-group-loading", {}, { timeout: 10000 });
    expect(group).toHaveAttribute("aria-label", "Loading layers…");
    expect(screen.getByTestId("review-row-op-edit")).toHaveTextContent("…");
    expect(screen.getByTestId("review-row-op-edit")).not.toHaveTextContent("cls-capability");
    expect(screen.getByTestId("review-inspector-class")).toHaveTextContent("…");
    expect(screen.getByTestId("review-definition-loading")).toHaveTextContent("Loading…");
    expect(screen.getByTestId("review-definition")).not.toHaveTextContent("cls-capability");
    const picker = within(screen.getByTestId("review-class-picker"));
    expect(picker.getByText("Loading classes…")).toBeInTheDocument();
    expect(picker.getByRole("combobox")).toBeDisabled();
    expect(screen.queryByTestId("review-group-other")).not.toBeInTheDocument();

    release();
    expect(
      await screen.findByTestId("review-group-scheme-p", {}, { timeout: 10000 }),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("review-group-loading")).not.toBeInTheDocument();
    expect(screen.getByTestId("review-inspector-class")).toHaveTextContent("Software capability");
    expect(screen.queryByTestId("review-definition-loading")).not.toBeInTheDocument();
  });
});

// ==================== The usability pass: redecide, links, pills, relationships ====================

const realizesType = createPropertyDefinition({
  id: "prop-1",
  identifier: "feature_realizes_capability",
  title: "product.feature realizes product.softwarecapability",
  description: "A feature makes a software capability available.",
  canonical_predicate: "realizes",
  domain_class_id: "cls-feature",
  range_class_id: "cls-capability",
});
const servesType = createPropertyDefinition({
  id: "prop-2",
  identifier: "feature_serves_capability",
  title: "product.feature serves product.softwarecapability",
  description: "A feature serves a capability.",
  canonical_predicate: "serves",
  domain_class_id: "cls-feature",
  range_class_id: "cls-capability",
});
const drivesType = createPropertyDefinition({
  id: "prop-3",
  identifier: "stakeholder_drives_goal",
  title: "motivation.stakeholder drives motivation.goal",
  canonical_predicate: "drives",
  domain_class_id: "cls-stakeholder",
  range_class_id: "cls-goal",
});

let reopens: string[][];

/** The schema's relationship types, and a reopen that puts operations back to pending. */
function useSchemaAndReopen() {
  reopens = [];
  server.use(
    http.get("*/api/properties", () =>
      HttpResponse.json({
        items: [realizesType, servesType, drivesType],
        total: 3,
        limit: 5000,
        offset: 0,
      }),
    ),
    http.post("*/api/proposals/:id/reopen", async ({ request }) => {
      const body = (await request.json()) as { operation_ids: string[] };
      reopens.push(body.operation_ids);
      for (const op of proposal.operations) {
        if (!body.operation_ids.includes(op.id)) continue;
        Object.assign(op, {
          status: "pending",
          reason: null,
          reason_code: null,
          applied_fields: null,
          result_entity_id: null,
        });
      }
      return HttpResponse.json(proposal);
    }),
  );
}

function decideOp(id: string, changes: Partial<ProposedOperation>) {
  Object.assign(proposal.operations.find((o) => o.id === id)!, changes);
}

describe("changing a decision while the review is open", () => {
  beforeEach(useSchemaAndReopen);

  it("rejects an accepted element instead: reopens it, then rejects it, and stays on it", async () => {
    decideOp("op-edit", { status: "applied", result_entity_id: "res-edit" });
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-edit"));
    expect(screen.getByTestId("review-inspector-status")).toHaveTextContent("correct");
    expect(screen.queryByTestId("review-reasons")).not.toBeInTheDocument();

    const change = screen.getByTestId("review-change-decision");
    expect(change).toHaveAttribute("aria-controls", "review-change");
    await user.click(change);
    expect(change).toHaveAttribute("aria-expanded", "true");
    // Already correct: Correct has nothing to change.
    expect(screen.getByTestId("review-correct")).toBeDisabled();
    await user.click(screen.getByTestId("review-reason-too_generic"));

    await waitFor(() => expect(rejects).toHaveLength(1));
    expect(reopens).toEqual([["op-edit"]]);
    expect(rejects[0].operation_ids).toEqual(["op-edit"]);
    expect(rejects[0].reason_code).toBe("too_generic");
    await waitFor(() =>
      expect(screen.getByTestId("review-inspector-status")).toHaveTextContent("not an element"),
    );
    expect(inspectorTitle()).toHaveTextContent("Edit Check");
    // A new decision closes the change controls.
    expect(screen.queryByTestId("review-reasons")).not.toBeInTheDocument();
  });

  it("accepts a rejected element instead, with another class", async () => {
    decideOp("op-region", { status: "rejected", reason_code: "out_of_scope" });
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-region"));
    await user.click(screen.getByTestId("review-change-decision"));
    const picker = within(screen.getByTestId("review-class-picker"));
    await user.type(picker.getByRole("combobox"), "motivation.goal");
    await user.click((await picker.findAllByRole("option"))[0]);

    await waitFor(() => expect(applies).toHaveLength(1));
    expect(reopens).toEqual([["op-region"]]);
    expect(applies[0].edits).toEqual({ "op-region": { class_ids: ["cls-goal"] } });
    await waitFor(() =>
      expect(screen.getByTestId("review-inspector-status")).toHaveTextContent("class changed"),
    );
  });

  it("decides nothing when the reopen is refused", async () => {
    decideOp("op-region", { status: "rejected", reason_code: "out_of_scope" });
    server.use(
      http.post("*/api/proposals/:id/reopen", () =>
        HttpResponse.json({ detail: "refused" }, { status: 409 }),
      ),
    );
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-region"));
    await user.click(screen.getByTestId("review-change-decision"));
    await user.click(screen.getByTestId("review-correct"));
    await waitFor(() => expect(screen.getByTestId("review-correct")).toBeEnabled());
    expect(applies).toHaveLength(0);
    expect(screen.getByTestId("review-inspector-status")).toHaveTextContent("not an element");
  });
});

describe("recent classes", () => {
  it("keeps the classes picked, each with a remove control", async () => {
    const user = await renderPage();
    const pick = async (query: string) => {
      const picker = within(screen.getByTestId("review-class-picker"));
      await user.type(picker.getByRole("combobox"), query);
      await user.click((await picker.findAllByRole("option"))[0]);
    };
    await pick("product.feature");
    await waitFor(() => expect(applies).toHaveLength(1));
    await user.click(screen.getByTestId("review-row-op-region"));
    const suggestion = screen.getByTestId("review-suggestion-1");
    expect(suggestion).toHaveTextContent("1 product.feature");
    const remove = screen.getByTestId("review-suggestion-1-remove");
    expect(remove).toHaveClass("review-forget");
    expect(remove).toHaveAttribute("aria-label", "Remove product.feature from recent classes");
    await user.click(remove);
    expect(screen.queryByTestId("review-suggestion-1")).not.toBeInTheDocument();
  });
});

describe("selection in the URL", () => {
  it("selects through the route: rows are links, and a modified click is left to the browser", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <ReviewPage
        id="proposal-1"
        onFinish={onFinish}
        selectedId="op-region"
        onSelect={onSelect}
        hrefOf={(opId) => `/review?selected=${opId}`}
      />,
    );
    await screen.findByTestId("review-group-scheme-p", {}, { timeout: 10000 });
    // The URL's selection opens in the inspector.
    expect(inspectorTitle()).toHaveTextContent("Sub-Saharan Africa");
    const row = screen.getByTestId("review-row-op-ref");
    expect(row.tagName).toBe("A");
    expect(row).toHaveAttribute("role", "option");
    expect(row).toHaveAttribute("href", "/review?selected=op-ref");
    await user.click(row);
    expect(onSelect).toHaveBeenCalledWith("op-ref");
    onSelect.mockClear();
    fireEvent.click(row, { ctrlKey: true });
    expect(onSelect).not.toHaveBeenCalled();
    // Selecting what is selected adds no history entry.
    await user.click(screen.getByTestId("review-row-op-region"));
    expect(onSelect).not.toHaveBeenCalled();
    // A highlight in the source selects through the route too.
    await user.click(markFor("op-edit"));
    expect(onSelect).toHaveBeenCalledWith("op-edit");
  });

  it("falls back to the first awaiting element when the URL names none of the proposal's", async () => {
    render(
      <ReviewPage
        id="proposal-1"
        onFinish={onFinish}
        selectedId="op-gone"
        onSelect={vi.fn()}
        hrefOf={(opId) => `?selected=${opId}`}
      />,
    );
    await screen.findByTestId("review-group-scheme-p", {}, { timeout: 10000 });
    expect(inspectorTitle()).toHaveTextContent("Edit Check");
  });
});

describe("pills with hover overlays", () => {
  beforeEach(useSchemaAndReopen);

  it("explains a class on hover: its definition and the relationships the schema allows", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-ref"));
    const pill = screen.getByTestId("review-inspector-class");
    await waitFor(() => expect(pill).toHaveTextContent("product.feature"));
    await user.hover(pill);
    const overlay = await screen.findByTestId("review-pill-overlay");
    expect(overlay).toHaveAttribute("role", "tooltip");
    expect(overlay).toHaveClass("definition-overlay");
    expect(pill).toHaveAttribute("aria-describedby", overlay.id);
    expect(overlay).toHaveTextContent("A unit of product functionality");
    expect(overlay).toHaveClass("definition-overlay--interactive");
    expect(overlay).toHaveTextContent("ALLOWED FROM IT");
    expect(overlay).toHaveTextContent("realizes → Software capability");
    expect(overlay).toHaveTextContent("serves → Software capability");
    expect(overlay).toHaveTextContent("ALLOWED INTO IT");
    expect(within(overlay).getByRole("link", { name: "Open the class" })).toHaveAttribute(
      "href",
      "/app/schema/classes/cls-feature",
    );
    // The pointer can move into the card (its link): it lingers, then closes.
    await user.unhover(pill);
    await waitFor(() =>
      expect(screen.queryByTestId("review-pill-overlay")).not.toBeInTheDocument(),
    );
  });

  it("keeps a decided element's class a pill", async () => {
    decideOp("op-edit", {
      status: "applied",
      result_entity_id: "res-edit",
      applied_fields: { title: "Edit Check", class_ids: ["cls-feature"] },
    });
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-edit"));
    expect(screen.getByTestId("review-decided-class")).toHaveClass("review-pill--class");
    await user.hover(screen.getByTestId("review-decided-class"));
    expect(await screen.findByTestId("review-pill-overlay")).toHaveTextContent(
      "A unit of product functionality",
    );
  });
});

describe("the relationship inspector", () => {
  beforeEach(() => {
    useSchemaAndReopen();
    decideOp("op-edit", { status: "applied", result_entity_id: "res-edit" });
    decideOp("op-ref", { status: "applied", result_entity_id: "res-ref" });
    decideOp("op-rel", { evidence: [passage("Reference check realizes Edit Check")] });
  });

  it("shows both ends with their classes and decisions, and the predicate's meaning", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    expect(screen.getByTestId("review-inspector")).toHaveAttribute(
      "aria-label",
      "Selected relationship",
    );
    // The title is the relationship as a sentence, its predicate a pill.
    const title = screen.getByTestId("review-inspector-title");
    expect(title.tagName).toBe("H2");
    expect(title).toHaveClass("review-head__sentence");
    expect(title).toHaveAttribute("aria-label", "Reference check realizes Edit Check");
    expect(screen.getByTestId("review-title-predicate")).toHaveClass("review-pill--predicate");
    // Then the relationship, top to bottom: FROM, the predicate between, TO.
    const block = screen.getByTestId("review-relationship-block");
    expect(block).toHaveAttribute("aria-label", "The relationship");
    const order = [...block.querySelectorAll("[data-pill]")].map((p) =>
      p.getAttribute("data-pill"),
    );
    expect(order).toEqual(["individual", "class", "predicate", "individual", "class"]);
    const predicatePill = screen.getByTestId("review-predicate-pill");
    expect(predicatePill).toHaveClass("review-pill--predicate", "review-pill--lg");
    expect(predicatePill).toHaveTextContent("realizes");
    expect(screen.getByTestId("review-ends-fit")).toHaveTextContent("both ends fit the schema");
    // An individual is bold text with a dot, not a pill; a class a violet tag with a diamond.
    expect(screen.getByTestId("review-end-source-individual")).toHaveClass(
      "review-pill--individual",
    );
    expect(
      screen.getByTestId("review-end-source-individual").querySelector(".review-ind__dot"),
    ).not.toBeNull();
    const sourceClass = screen.getByTestId("review-end-source-class");
    expect(sourceClass).toHaveClass("review-pill--class");
    expect(sourceClass.querySelector(".review-pill__icon svg")).not.toBeNull();
    expect(screen.getByTestId("review-end-source-individual")).toHaveTextContent("Reference check");
    expect(screen.getByTestId("review-end-source-individual")).toHaveAttribute(
      "href",
      "?selected=op-ref",
    );
    expect(screen.getByTestId("review-end-source-class")).toHaveTextContent("product.feature");
    expect(screen.getByTestId("review-end-source-status")).toHaveTextContent("correct");
    expect(screen.getByTestId("review-end-target-individual")).toHaveTextContent("Edit Check");
    await waitFor(() =>
      expect(screen.getByTestId("review-predicate-definition")).toHaveTextContent(
        "A feature makes a software capability available.",
      ),
    );
    // The allowed classes are in the predicate's hover.
    await user.hover(screen.getByTestId("review-predicate-pill"));
    expect(await screen.findByTestId("review-pill-overlay")).toHaveTextContent(
      "From product.feature to Software capability",
    );
  });

  it("shows its evidence in the source: highlighted while open, flashed when clicked", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    const mark = await waitFor(() => {
      const found = screen
        .getAllByTestId("review-mark")
        .find((m) => m.dataset.spanKeys?.split(" ").includes("op-rel"));
      expect(found).toBeDefined();
      return found!;
    });
    expect(mark).toHaveAttribute("aria-current", "true");
    await user.click(screen.getByTestId("review-evidence-1"));
    const start = String(TEXT.indexOf("Reference check realizes Edit Check"));
    const shown = screen
      .getAllByTestId("review-mark")
      .find((m) => m.getAttribute("data-start") === start)!;
    expect(shown).toHaveClass("review-mark--flash");
  });

  it("accepts it with a better predicate the schema allows between its ends' classes", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    expect(screen.getByTestId("review-accept-edited")).toBeDisabled();
    const change = screen.getByTestId("review-change-predicate");
    expect(change).toHaveAttribute("aria-expanded", "false");
    await user.click(change);
    expect(change).toHaveTextContent("Cancel");
    expect(screen.getByTestId("review-better-predicate")).toHaveClass("review-fix--open");
    const option = await screen.findByTestId("review-predicate-option-1");
    expect(option).toHaveTextContent("serves →");
    // drives (stakeholder → goal) doesn't fit these ends.
    expect(screen.queryByTestId("review-predicate-option-2")).not.toBeInTheDocument();
    await user.click(option);
    expect(screen.getByTestId("review-draft-predicate")).toHaveTextContent("serves");
    expect(screen.getByTestId("review-better-predicate")).toHaveClass("review-fix--changed");
    await user.click(screen.getByTestId("review-accept-edited"));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].edits).toEqual({ "op-rel": { property_definition_id: "prop-2" } });
    // A first decision moves on; the row says how it was decided.
    await waitFor(() =>
      expect(screen.getByTestId("review-row-op-rel")).toHaveTextContent("edited"),
    );
    expect(screen.getByTestId("review-row-op-rel")).toHaveTextContent("serves");
  });

  it("warns when its ends no longer fit its type, and offers no Correct", async () => {
    // Reference check was accepted as a goal: realizes runs from features only.
    decideOp("op-ref", {
      applied_fields: { title: "Reference check", class_ids: ["cls-goal"] },
    });
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    // In place of the green tick: the pill turns red and says which end is wrong.
    const warning = await screen.findByTestId("review-ends-misfit");
    expect(warning).toHaveAttribute("role", "alert");
    expect(warning).toHaveTextContent("source is motivation.goal; realizes needs product.feature");
    expect(screen.getByTestId("review-predicate-pill")).toHaveClass("review-pill--misfit");
    expect(screen.queryByTestId("review-ends-fit")).not.toBeInTheDocument();
    expect(screen.getByTestId("review-correct")).toBeDisabled();
  });

  it("accepts it with a better source of a class its type allows", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    // Or correct it: three rows of one shape, each with Change.
    const editor = screen.getByTestId("review-relationship-editor");
    expect(editor).toHaveTextContent("OR CORRECT IT");
    for (const row of ["predicate", "source", "target"]) {
      expect(screen.getByTestId(`review-better-${row}`)).toHaveClass("review-fix");
    }
    // No other predicate fits feature → capability but serves: its Change is enabled.
    await user.click(screen.getByTestId("review-change-source"));
    const panel = screen.getByRole("group", { name: "Source" });
    expect(screen.getByTestId("review-change-source")).toHaveAttribute("aria-expanded", "true");
    // Feedback (added, a feature) fits; Reference check is the current source.
    expect(
      within(panel).getByText("2 product.feature individuals, in this proposal or the dataset"),
    ).toBeInTheDocument();
    await user.type(within(panel).getByRole("textbox"), "Feed");
    const results = within(panel).getAllByTestId("review-end-option-source");
    expect(results).toHaveLength(1);
    expect(results[0]).toHaveTextContent("Feedbackproduct.feature");
    await user.click(results[0]);
    expect(screen.getByTestId("review-draft-source")).toHaveTextContent("Feedback");
    await user.click(screen.getByTestId("review-accept-edited"));
    await waitFor(() => expect(applies).toHaveLength(1));
    // An element of this proposal is named by its ref, as the proposed ends are (#1673).
    expect(applies[0].edits).toEqual({ "op-rel": { source_id: "$added" } });
  });
});

describe("a relationship's ends on a fresh extraction (#1673)", () => {
  const enablesType = createPropertyDefinition({
    id: "prop-4",
    identifier: "capability_enables_feature",
    title: "product.softwarecapability enables product.feature",
    canonical_predicate: "enables",
    domain_class_id: "cls-capability",
    range_class_id: "cls-feature",
  });

  beforeEach(() => {
    useSchemaAndReopen();
    // Nothing applied yet, and an empty dataset: the elements to come are the only candidates.
    decideOp("op-added", { status: "pending", result_entity_id: null });
    server.use(
      http.get("*/api/individuals", () =>
        HttpResponse.json({ items: [], total: 0, limit: 500, offset: 0 }),
      ),
    );
  });

  it("finds this proposal's pending elements, and won't accept until the one picked applies", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    await user.click(screen.getByTestId("review-change-source"));
    const panel = screen.getByRole("group", { name: "Source" });
    // Reference check (the current source) and Feedback, both awaiting, both features.
    expect(
      within(panel).getByText("2 product.feature individuals, in this proposal or the dataset"),
    ).toBeInTheDocument();
    const [feedback] = within(panel).getAllByTestId("review-end-option-source");
    expect(feedback).toHaveTextContent("Feedback");
    expect(feedback).toHaveTextContent("in this proposal, awaiting");
    await user.click(feedback);
    expect(screen.getByTestId("review-draft-source")).toHaveTextContent("Feedback");
    expect(screen.getByTestId("review-editor-pending")).toHaveTextContent(
      "Decide #4 Feedback first: this end follows its choice.",
    );
    expect(screen.getByTestId("review-accept-edited")).toBeDisabled();
    expect(applies).toHaveLength(0);
  });

  it("says why the list is empty: nothing of the class the type needs, or nothing by that text", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    await user.click(screen.getByTestId("review-change-target"));
    // Edit Check is the only capability, and it is the target already.
    expect(screen.getByTestId("review-end-empty-target")).toHaveTextContent(
      "No Software capability individual is in this proposal or the dataset.",
    );
    await user.click(screen.getByTestId("review-change-target"));
    await user.click(screen.getByTestId("review-change-source"));
    await user.type(screen.getByTestId("review-end-search-source"), "zzz");
    expect(screen.getByTestId("review-end-empty-source")).toHaveTextContent(
      "No product.feature individual matches “zzz”.",
    );
  });

  it("reverses the ends, and says when no predicate allows the reversed direction", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    const reverse = screen.getByTestId("review-reverse");
    expect(reverse).toHaveAttribute("aria-pressed", "false");
    await user.click(reverse);
    expect(reverse).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("review-draft-source")).toHaveTextContent("Edit Check");
    expect(screen.getByTestId("review-draft-target")).toHaveTextContent("Reference check");
    expect(screen.getByTestId("review-editor-misfit")).toHaveTextContent(
      "No predicate is allowed from Software capability to product.feature.",
    );
    expect(screen.getByTestId("review-accept-edited")).toBeDisabled();
    // Reversed again, it is the relationship as proposed: nothing to accept as an edit.
    await user.click(reverse);
    expect(screen.getByTestId("review-draft-source")).toHaveTextContent("Reference check");
    expect(screen.queryByTestId("review-editor-misfit")).not.toBeInTheDocument();
    expect(screen.getByTestId("review-accept-edited")).toBeDisabled();
  });

  it("offers the predicates the reversed direction allows, and accepts it by the ends' refs", async () => {
    server.use(
      http.get("*/api/properties", () =>
        HttpResponse.json({
          items: [realizesType, servesType, drivesType, enablesType],
          total: 4,
          limit: 5000,
          offset: 0,
        }),
      ),
    );
    decideOp("op-edit", { status: "applied", result_entity_id: "res-edit" });
    decideOp("op-ref", { status: "applied", result_entity_id: "res-ref" });
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    await user.click(screen.getByTestId("review-reverse"));
    expect(screen.getByTestId("review-editor-misfit")).toHaveTextContent(
      "realizes isn't allowed from Software capability to product.feature. Pick one of the 1 that are, above.",
    );
    // The predicate row opens on the ones that are.
    const options = within(screen.getByRole("group", { name: "Predicate" })).getAllByTestId(
      /^review-predicate-option-/,
    );
    expect(options).toHaveLength(1);
    expect(options[0]).toHaveTextContent("enables");
    await user.click(options[0]);
    expect(screen.queryByTestId("review-editor-misfit")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("review-accept-edited"));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].edits).toEqual({
      "op-rel": { property_definition_id: "prop-4", source_id: "$edit", target_id: "$ref" },
    });
  });

  it("offers the individual a rejected duplicate points at, and a near match once", async () => {
    // Feedback was rejected as a duplicate of the dataset's own Feedback loop; Reference
    // check applied as its near match Reference checking.
    decideOp("op-added", {
      status: "rejected",
      reason_code: "duplicate",
      result_entity_id: "ind-loop",
    });
    decideOp("op-ref", { status: "applied", matched: true, result_entity_id: "ind-checking" });
    server.use(
      http.get("*/api/individuals", () =>
        HttpResponse.json({
          items: [
            { id: "ind-loop", title: "Feedback loop", class_ids: ["cls-feature"] },
            { id: "ind-checking", title: "Reference checking", class_ids: ["cls-feature"] },
          ],
          total: 2,
          limit: 500,
          offset: 0,
        }),
      ),
    );
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    await user.click(screen.getByTestId("review-change-source"));
    const options = within(screen.getByRole("group", { name: "Source" })).getAllByTestId(
      "review-end-option-source",
    );
    const titles = options.map((o) => o.textContent ?? "");
    expect(titles.some((t) => t.includes("Feedback loop"))).toBe(true);
    // The near match is the current source, offered by its ref only: not again from the dataset.
    expect(titles.some((t) => t.includes("Reference checking"))).toBe(false);
    expect(titles.some((t) => t.startsWith("Feedback") && t.includes("in this proposal"))).toBe(
      false,
    );
  });

  it("says a rejected end was rejected after Reverse, not that it waits for a decision", async () => {
    decideOp("op-ref", { status: "rejected", reason_code: "not_in_text" });
    decideOp("op-edit", { status: "applied", result_entity_id: "res-edit" });
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    await user.click(screen.getByTestId("review-reverse"));
    expect(screen.getByTestId("review-editor-rejected-end")).toHaveTextContent(
      "#2 Reference check was rejected: pick another end.",
    );
    expect(screen.queryByTestId("review-editor-pending")).not.toBeInTheDocument();
    expect(screen.getByTestId("review-accept-edited")).toBeDisabled();
  });

  it("accepts with a pending element's ref once it applied, resolved by the server", async () => {
    decideOp("op-added", { status: "applied", result_entity_id: "ind-77" });
    decideOp("op-edit", { status: "applied", result_entity_id: "res-edit" });
    const user = await renderPage();
    await user.click(screen.getByTestId("review-row-op-rel"));
    await user.click(screen.getByTestId("review-change-source"));
    const [feedback] = within(screen.getByRole("group", { name: "Source" })).getAllByTestId(
      "review-end-option-source",
    );
    expect(feedback).toHaveTextContent("in this proposal");
    expect(feedback).not.toHaveTextContent("awaiting");
    await user.click(feedback);
    expect(screen.queryByTestId("review-editor-pending")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("review-accept-edited"));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0].edits).toEqual({ "op-rel": { source_id: "$added" } });
  });
});

describe("comparing with another pipeline", () => {
  it("offers it in the header when another pipeline extracted the source", async () => {
    const origin = (implementation_id: string) => ({
      pipeline_type: "individual_extraction",
      implementation_id,
      configuration_ref: "c",
      configuration_version: 1,
      digest: "abcdef",
    });
    proposal.origin = origin("single_call");
    const other = { ...proposal, id: "proposal-2", origin: origin("find_then_type") };
    server.use(
      http.get("*/api/proposals", () =>
        HttpResponse.json({ items: [proposal, other], total: 2, limit: 500, offset: 0 }),
      ),
    );
    const onCompare = vi.fn();
    const user = userEvent.setup();
    render(<ReviewPage id="proposal-1" onFinish={onFinish} onCompare={onCompare} />);
    const button = await screen.findByTestId("review-compare", {}, { timeout: 10000 });
    expect(within(screen.getByTestId("review-header")).getByTestId("review-compare")).toBe(button);
    await user.click(button);
    expect(onCompare).toHaveBeenCalledWith("proposal-2");
  });

  it("isn't offered without another pipeline's extraction", async () => {
    server.use(
      http.get("*/api/proposals", () =>
        HttpResponse.json({ items: [proposal], total: 1, limit: 500, offset: 0 }),
      ),
    );
    await renderPage();
    expect(screen.queryByTestId("review-compare")).not.toBeInTheDocument();
  });
});
