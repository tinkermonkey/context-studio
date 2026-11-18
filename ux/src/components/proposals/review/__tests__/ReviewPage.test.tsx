/**
 * The Review page (#1611): an extraction proposal reviewed against its whole
 * source. The source's highlights carry each element's verdict, elements are
 * grouped by layer with an Awaiting / All filter, and the inspector decides
 * the selected one (Correct, a better class, or not an element with a reason)
 * by button or key, sending the time spent on it.
 */
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
    http.get("*/api/schemes", () => list([product, motivation])),
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
      "0 correct · 0 class changed · 0 not elements · 1 added",
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
    expect(classChip).toHaveClass("review-class-chip");
    expect(classChip).toHaveAttribute("title", "Software capability");
    expect(screen.getByTestId("review-inspector-status")).toHaveTextContent("awaiting");
    expect(screen.getByTestId("review-evidence")).toHaveTextContent("Edit Check");
    expect(screen.getByTestId("review-definition")).toHaveTextContent(
      "What Software capability means",
    );
    expect(screen.getByTestId("review-definition")).toHaveTextContent(
      "An ability of the software platform.",
    );
    await waitFor(() =>
      expect(screen.getByTestId("review-relationship-op-rel")).toHaveTextContent(
        "Reference checkrealizesEdit Check",
      ),
    );
    expect(screen.getByTestId("review-relationships")).toHaveTextContent("Its relationships · 1");
  });

  it("accepts as correct with the review time, then opens the next awaiting element", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("review-correct"));
    await waitFor(() => expect(applies).toHaveLength(1));
    expect(applies[0]).toEqual({
      operation_ids: ["op-edit"],
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
    expect(screen.getByTestId("review-progress-counts")).toHaveTextContent("1 class changed");

    // Next: Reference check, already a product.feature, so feature isn't suggested.
    await waitFor(() => expect(inspectorTitle()).toHaveTextContent("Reference check"));
    expect(screen.queryByTestId("review-suggestion-1")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("review-row-op-region"));
    const suggestion = screen.getByTestId("review-suggestion-1");
    expect(suggestion).toHaveClass("review-alt");
    expect(suggestion).toHaveAttribute("aria-keyshortcuts", "1");
    expect(suggestion).toHaveTextContent("1 product.feature");
    expect(suggestion).toHaveTextContent("A unit of product functionality");
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

  it("decides by key: J / K move, A accepts, X focuses the reasons", async () => {
    const user = await renderPage();
    await user.keyboard("j");
    expect(inspectorTitle()).toHaveTextContent("Reference check");
    await user.keyboard("j");
    expect(inspectorTitle()).toHaveTextContent("Feedback");
    await user.keyboard("k");
    expect(inspectorTitle()).toHaveTextContent("Reference check");
    await user.keyboard("x");
    expect(screen.getByTestId("review-reason-not_in_text")).toHaveFocus();
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
      "#1 was rejected, so this relationship can't apply. Reject it.",
    );
    expect(screen.queryByTestId("review-correct")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("review-inspector-title"));
    await user.keyboard("a");
    expect(applies).toHaveLength(0);
    await user.click(screen.getByTestId("review-reason-not_in_text"));
    await waitFor(() => expect(rejects).toHaveLength(1));
    expect(rejects[0].operation_ids).toEqual(["op-rel"]);
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
    expect(applies[0]).toMatchObject({ operation_ids: ["op-edit"], force_stale: ["op-edit"] });
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
      "Added by you as product.feature.",
    );
    expect(screen.queryByTestId("review-reasons")).not.toBeInTheDocument();
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
      "Added by you as motivation.goal.",
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
    expect(inGold).toHaveTextContent("Acceptable in gold");
    expect(inGold).toHaveAttribute("aria-pressed", "true");
    expect(inGold).toBeDisabled();
    expect(inGold).toHaveClass("review-defensible--on", "review-defensible--gold");
    // The other class toggles.
    expect(screen.getByTestId("review-suggestion-2")).toHaveTextContent("2 motivation.stakeholder");
    const toggle = screen.getByTestId("review-defensible-2");
    expect(toggle).toHaveTextContent("Also defensible");
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(toggle).toHaveClass("review-defensible--on");
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
    // X goes to the note while it is empty.
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
      http.get("*/api/classes", async ({ request }) => {
        await loaded;
        const url = new URL(request.url);
        const scheme = url.searchParams.get("concept_scheme_id");
        const ids = url.searchParams.getAll("ids");
        const items = classes.filter(
          (c) => (!scheme || c.concept_scheme_id === scheme) && (!ids.length || ids.includes(c.id)),
        );
        return HttpResponse.json({ items, total: items.length, limit: 500, offset: 0 });
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
