/**
 * Accept with edit (#1383 UI): an update's triple edited, or a delete replaced,
 * checked as it is typed against dr_spec's classes, its predicate catalog and
 * the relationship types that exist.
 */
import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { ApiError } from "@/api/client/interceptors";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";
import {
  createClass,
  createConceptScheme,
  createPredicate,
  createPropertyDefinition,
  createTaxonomy,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { DrTripleEditor } from "../DrTripleEditor";

const DR = "documentation_robotics";
const taxonomy = createTaxonomy({ id: "tax-dr", identifier: "dr_spec" });
// dr_spec's predicate catalog, as GET /api/taxonomies/tax-dr/predicates serves it.
const predicates = ["performs", "triggers", "assigned-to", "serves"].map((identifier) =>
  createPredicate({ identifier, taxonomy_id: "tax-dr" }),
);
const drClass = (id: string, node: string) =>
  createClass({
    id,
    concept_scheme_id: "scheme-b",
    taxonomy_id: "tax-dr",
    identifier: node.replace(".", "_"),
    external_references: [{ source: DR, identifier: node }],
  });
const classes = [
  drClass("c-role", "business.businessrole"),
  drClass("c-process", "business.businessprocess"),
  drClass("c-event", "business.businessevent"),
];
const existing = createPropertyDefinition({
  id: "p-existing",
  identifier: "businessevent_triggers_businessprocess",
  canonical_predicate: "triggers",
  domain_class_id: "c-event",
  range_class_id: "c-process",
});
const current = {
  canonical_predicate: "assigned-to",
  domain_class_id: "c-role",
  range_class_id: "c-process",
};

const update = createProposedOperation({
  id: "op-u",
  seq: 16,
  op: "update",
  kind: "property",
  target_id: "p-assigned",
  fields: { canonical_predicate: "performs" },
  base: { canonical_predicate: "assigned-to" },
});
const remove = createProposedOperation({
  id: "op-d",
  seq: 4,
  op: "delete",
  kind: "property",
  target_id: "p-assigned",
  fields: {},
  base: { id: "p-assigned", ...current },
});
const proposal = createChangeProposal({ taxonomy_id: "tax-dr", operations: [update, remove] });

const list = <T,>(items: T[]) =>
  HttpResponse.json({ items, total: items.length, limit: 500, offset: 0 });

const server = setupServer(
  http.get("*/api/schemes", () =>
    list([createConceptScheme({ id: "scheme-b", taxonomy_id: "tax-dr" })]),
  ),
  http.get("*/api/classes", () => list(classes)),
  http.get("*/api/taxonomies/:id/predicates", () => HttpResponse.json(predicates)),
  http.get("*/api/properties", ({ request }) => {
    const domain = new URL(request.url).searchParams.get("domain_class_id");
    return list([existing].filter((p) => p.domain_class_id === domain));
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderEditor(operation = update, onApply = vi.fn().mockResolvedValue({})) {
  render(
    <DrTripleEditor
      operation={operation}
      proposal={proposal}
      taxonomy={taxonomy}
      current={current}
      onApply={onApply}
      onCancel={vi.fn()}
    />,
  );
  return { onApply };
}

/** The triple on one row (Current, Proposed, Your edit) of the editor. */
function tripleRow(label: string): string | null | undefined {
  return within(screen.getByTestId("operation-edit-triples")).getByText(label).nextElementSibling
    ?.textContent;
}

async function retype(input: HTMLElement, text: string) {
  const user = userEvent.setup();
  await user.clear(input);
  if (text) await user.type(input, text);
}

describe("editing an update", () => {
  it("starts from the proposed triple and applies it as proposed when unchanged", async () => {
    const user = userEvent.setup();
    const { onApply } = renderEditor();

    const source = await screen.findByTestId("operation-edit-source");
    await waitFor(() => expect(source).toHaveValue("business.businessrole"));
    expect(screen.getByTestId("operation-edit-predicate")).toHaveValue("performs");
    expect(tripleRow("Current")).toBe("business.businessrole assigned-to business.businessprocess");
    expect(tripleRow("Proposed")).toBe("business.businessrole performs business.businessprocess");
    expect(tripleRow("Your edit")).toBe("business.businessrole performs business.businessprocess");
    // No edit: DR's decision line carries no fields.
    expect(JSON.parse(screen.getByTestId("operation-edit-preview").textContent ?? "")).toEqual({
      seq: 16,
      op_id: "op-u",
      status: "applied",
      reason: null,
    });

    await user.click(screen.getByTestId("operation-edit-apply"));
    expect(onApply).toHaveBeenCalledWith(undefined);
  });

  it("checks the triple as it is typed and clears each error once fixed", async () => {
    const user = userEvent.setup();
    const { onApply } = renderEditor();
    const source = await screen.findByTestId("operation-edit-source");
    await waitFor(() => expect(source).toHaveValue("business.businessrole"));

    await retype(source, "business.typo");
    expect(screen.getByText("No class business.typo in dr_spec")).toBeInTheDocument();
    expect(source).toHaveClass("text-input--error");
    expect(source).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByTestId("operation-edit-apply")).toBeDisabled();
    expect(screen.getByTestId("operation-edit-preview")).toHaveTextContent(
      "Nothing yet: fix the edit to apply it.",
    );

    await retype(source, "business.businessevent");
    expect(screen.queryByText(/No class business\.typo/)).not.toBeInTheDocument();
    expect(source).not.toHaveClass("text-input--error");

    const predicate = screen.getByTestId("operation-edit-predicate");
    await retype(predicate, "befriends");
    expect(screen.getByText("befriends is not in the predicate catalog")).toBeInTheDocument();

    // The existing relationship type businessevent triggers businessprocess.
    await retype(predicate, "triggers");
    expect(screen.queryByText(/not in the predicate catalog/)).not.toBeInTheDocument();
    expect(await screen.findByTestId("operation-edit-triple-error")).toHaveTextContent(
      "business.businessevent.triggers.business.businessprocess already exists as businessevent_triggers_businessprocess",
    );
    expect(screen.getByTestId("operation-edit-apply")).toBeDisabled();

    await retype(screen.getByTestId("operation-edit-destination"), "business.businessrole");
    expect(screen.queryByTestId("operation-edit-triple-error")).not.toBeInTheDocument();
    expect(screen.getByTestId("operation-edit-valid")).toHaveTextContent(
      "Valid. Applies business.businessevent.triggers.business.businessrole instead of the proposed triple.",
    );
    expect(JSON.parse(screen.getByTestId("operation-edit-preview").textContent ?? "")).toEqual({
      seq: 16,
      op_id: "op-u",
      status: "applied",
      fields: {
        predicate: "triggers",
        source_spec_node_id: "business.businessevent",
        destination_spec_node_id: "business.businessrole",
      },
      reason: null,
    });

    await user.click(screen.getByTestId("operation-edit-apply"));
    expect(onApply).toHaveBeenCalledWith({
      "op-u": {
        canonical_predicate: "triggers",
        domain_class_id: "c-event",
        range_class_id: "c-role",
      },
    });
  });

  it("shows the server's refusal and clears it on the next change", async () => {
    const user = userEvent.setup();
    const onApply = vi.fn().mockResolvedValue({
      error: new ApiError("x", 422, "Edits for operations not being applied: ['op-u']"),
    });
    renderEditor(update, onApply);
    const source = await screen.findByTestId("operation-edit-source");
    await waitFor(() => expect(source).toHaveValue("business.businessrole"));

    await retype(source, "business.businessevent");
    await user.click(screen.getByTestId("operation-edit-apply"));
    expect(await screen.findByTestId("operation-edit-server-error")).toHaveTextContent(
      "Not applied: Edits for operations not being applied: ['op-u']",
    );

    await user.type(screen.getByTestId("operation-edit-predicate"), "s");
    expect(screen.queryByTestId("operation-edit-server-error")).not.toBeInTheDocument();
  });
});

describe("what blocks an edit", () => {
  it("refuses an update edited back to the target's own triple", async () => {
    renderEditor();
    const predicate = await screen.findByTestId("operation-edit-predicate");
    await waitFor(() => expect(predicate).toHaveValue("performs"));

    await retype(predicate, "assigned-to");
    expect(await screen.findByTestId("operation-edit-triple-error")).toHaveTextContent(
      "business.businessrole.assigned-to.business.businessprocess is the current triple. To keep it, reject the update.",
    );
    expect(screen.getByTestId("operation-edit-apply")).toBeDisabled();
  });

  it("waits for the already-exists lookup before Apply edited", async () => {
    let answer: () => void = () => {};
    const answered = new Promise<void>((resolve) => (answer = resolve));
    server.use(
      http.get("*/api/properties", async () => {
        await answered;
        return list([]);
      }),
    );
    renderEditor();
    const source = await screen.findByTestId("operation-edit-source");
    await waitFor(() => expect(source).toHaveValue("business.businessrole"));

    expect(screen.getByTestId("operation-edit-apply")).toBeDisabled();
    answer();
    await waitFor(() => expect(screen.getByTestId("operation-edit-apply")).toBeEnabled());
  });

  it("refuses a predicate that isn't in dr_spec's predicates", async () => {
    let asked: string | undefined;
    server.use(
      http.get("*/api/taxonomies/:id/predicates", ({ params }) => {
        asked = String(params.id);
        return HttpResponse.json(predicates);
      }),
    );
    renderEditor();
    const predicate = await screen.findByTestId("operation-edit-predicate");
    await waitFor(() => expect(predicate).toHaveValue("performs"));
    expect(asked).toBe("tax-dr");

    await retype(predicate, "befriends");
    expect(screen.getByText("befriends is not in the predicate catalog")).toBeInTheDocument();
    expect(predicate).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByTestId("operation-edit-apply")).toBeDisabled();

    await retype(predicate, "serves");
    expect(screen.queryByText(/not in the predicate catalog/)).not.toBeInTheDocument();
  });

  it("can still delete as proposed when the predicates fail to load", async () => {
    const user = userEvent.setup();
    server.use(
      http.get("*/api/taxonomies/:id/predicates", () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    );
    renderEditor(remove);

    expect(
      await screen.findByText(
        "Couldn't load the dr_spec classes and predicates to check the edit.",
      ),
    ).toBeInTheDocument();
    expect(await screen.findByTestId("operation-edit-no-catalog")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apply replacement" })).toBeDisabled();

    await user.click(screen.getByRole("radio", { name: "Delete as proposed" }));
    expect(screen.queryByTestId("operation-edit-no-catalog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Accept delete" })).toBeEnabled();
  });

  it("can't edit without the predicate catalog, but can still delete as proposed", async () => {
    const user = userEvent.setup();
    server.use(http.get("*/api/taxonomies/:id/predicates", () => HttpResponse.json([])));
    renderEditor(remove);
    await screen.findByTestId("operation-edit-source");

    expect(await screen.findByTestId("operation-edit-no-catalog")).toHaveTextContent(
      "The DR spec was imported without its predicate catalog; re-import it to edit triples.",
    );
    expect(screen.queryByTestId("operation-edit-valid")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apply replacement" })).toBeDisabled();

    await user.click(screen.getByRole("radio", { name: "Delete as proposed" }));
    expect(screen.queryByTestId("operation-edit-no-catalog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Accept delete" })).toBeEnabled();
  });
});

describe("replacing a delete", () => {
  it("sends a replacement as an edit, which applies as an update", async () => {
    const user = userEvent.setup();
    const { onApply } = renderEditor(remove);
    const source = await screen.findByTestId("operation-edit-source");
    await waitFor(() => expect(source).toHaveValue("business.businessrole"));
    expect(tripleRow("Proposed")).toBe("remove it");
    expect(screen.getByText("remove it")).toHaveClass("op-edit__removed");

    // Starting from the current triple, which a replacement has to change.
    expect(screen.getByTestId("operation-edit-triple-error")).toHaveTextContent(
      "is the current triple. To keep it, reject the delete.",
    );
    await retype(screen.getByTestId("operation-edit-predicate"), "performs");
    expect(screen.queryByTestId("operation-edit-triple-error")).not.toBeInTheDocument();
    expect(screen.getByTestId("operation-edit-valid")).toHaveTextContent("Applies as an update");

    await user.click(screen.getByRole("button", { name: "Apply replacement" }));
    expect(onApply).toHaveBeenCalledWith({
      "op-d": {
        canonical_predicate: "performs",
        domain_class_id: "c-role",
        range_class_id: "c-process",
      },
    });
  });

  it("can delete as proposed instead, with no edit", async () => {
    const user = userEvent.setup();
    const { onApply } = renderEditor(remove);
    await screen.findByTestId("operation-edit-source");

    await user.click(screen.getByRole("radio", { name: "Delete as proposed" }));
    expect(screen.queryByTestId("operation-edit-source")).not.toBeInTheDocument();
    expect(JSON.parse(screen.getByTestId("operation-edit-preview").textContent ?? "")).toEqual({
      seq: 4,
      op_id: "op-d",
      status: "applied",
      reason: null,
    });
    await user.click(screen.getByRole("button", { name: "Accept delete" }));
    expect(onApply).toHaveBeenCalledWith(undefined);
  });
});
