/**
 * Review queue usability (#1439): the inspector's section order, definition
 * overlays on reflection answers (hover and keyboard focus), selecting a
 * conflict item by clicking it, and conflict cards following the filter.
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers, taxonomy } from "@/test/entityPageHandlers";
import { goldPage, proposalHandlers } from "@/test/proposalFixtures";
import { CLASS_IDS, reflectionProposal } from "@/test/reflectionFixtures";
import { createClass } from "@/api/services/__tests__/fixtures/ontology.fixtures";
import type { ChangeProposal } from "@/api/services/proposals";
import { ProposalDetailPage } from "../ProposalDetailPage";

const server = setupServer(...proposalHandlers, ...entityPageHandlers);

const DEFINITIONS: Record<string, string> = {
  project: "A body of work with an outcome, made of tasks.",
  task: "One thing to do, done in one sitting.",
  room: "A part of a place with walls.",
};
const CLASSES = Object.entries(CLASS_IDS).map(([name, id]) =>
  createClass({ id, identifier: name, title: name, description: DEFINITIONS[name] ?? "" }),
);

let proposal: ChangeProposal;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  proposal = reflectionProposal();
  server.use(
    http.get("*/api/proposals/:id", () => HttpResponse.json(proposal)),
    http.get("*/api/taxonomies/:id/gold", () => HttpResponse.json(goldPage(proposal.operations))),
    http.get("*/api/classes", () =>
      HttpResponse.json({ items: CLASSES, total: CLASSES.length, limit: 500, offset: 0 }),
    ),
    http.get("*/api/taxonomies/:id", () =>
      HttpResponse.json({
        ...taxonomy,
        external_references: [
          {
            source: "documentation_robotics",
            identifier: "spec",
            metadata: {
              predicates: {
                holds: { description: "The source keeps the destination inside it." },
                located_in: { description: "The source sits within the destination." },
              },
            },
          },
        ],
      }),
    ),
    http.post("*/api/proposals/:id/reject", async ({ request }) => {
      const body = (await request.json()) as { operation_ids: string[] };
      for (const op of proposal.operations) {
        if (body.operation_ids.includes(op.id)) Object.assign(op, { status: "rejected" });
      }
      return HttpResponse.json(proposal);
    }),
  );
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderPage(selectedOperationId?: string, onSelectOperation = vi.fn()) {
  render(
    <ProposalDetailPage
      id="proposal-1"
      selectedOperationId={selectedOperationId}
      onSelectOperation={onSelectOperation}
    />,
  );
  return onSelectOperation;
}

function sectionTitles(): string[] {
  const inspector = screen.getByTestId("operation-inspector");
  return [...inspector.querySelectorAll(".inspector-panel__section-title")].map(
    (t) => t.firstChild?.textContent ?? "",
  );
}

describe("the inspector's section order", () => {
  it("puts Rationale after Replacement, ahead of the answers and the change", async () => {
    // m-dup is a delete naming a replacement.
    const task = { id: CLASS_IDS.task, title: "task" };
    const tool = { id: CLASS_IDS.tool, title: "tool" };
    proposal.operations[0].replacement_check = {
      replacement_id: "prop-other",
      property_id: "prop-other",
      identifier: "task_uses_tool",
      title: "uses",
      pair: "same",
      deleted_domain: task,
      deleted_range: tool,
      domain: task,
      range: tool,
      replacement_deleted: false,
      chain: [],
      cycle: false,
    };
    renderPage("m-dup");
    await screen.findByTestId("operation-inspector");
    await screen.findByTestId("operation-replacement");

    const titles = sectionTitles();
    const at = (title: string) => titles.indexOf(title);
    expect(at("Replacement")).toBeGreaterThanOrEqual(0);
    expect(at("Rationale")).toBe(at("Replacement") + 1);
    expect(at("Reflection answers")).toBe(at("Rationale") + 1);
    expect(at("Change")).toBe(at("Reflection answers") + 1);
    expect(at("Evidence pack")).toBe(at("Change") + 1);
  });

  it("puts Rationale first after the decision without a replacement", async () => {
    renderPage("j-retarget");
    await screen.findByTestId("reflection-answers");
    const titles = sectionTitles();
    expect(titles.indexOf("Rationale")).toBe(titles.indexOf("Reflection answers") - 1);
    expect(titles.indexOf("Rationale")).toBeLessThan(titles.indexOf("Change"));
  });
});

describe("definition overlays on reflection answers", () => {
  it("shows a class answer's definition on hover, and hides it on leave", async () => {
    renderPage("j-retarget");
    const option = await screen.findByTestId("reflection-option-source_for-project");
    await waitFor(() => expect(option).toHaveAttribute("data-defined", "true"));

    fireEvent.mouseEnter(option);
    const overlay = await screen.findByTestId("reflection-definition");
    expect(overlay).toHaveAttribute("role", "tooltip");
    expect(overlay).toHaveTextContent("project");
    expect(overlay).toHaveTextContent(DEFINITIONS.project);

    fireEvent.mouseLeave(option);
    expect(screen.queryByTestId("reflection-definition")).not.toBeInTheDocument();

    // A scroll that takes the answer out of view closes it (jsdom lays nothing out).
    fireEvent.mouseEnter(option);
    await screen.findByTestId("reflection-definition");
    fireEvent.scroll(document);
    await waitFor(() =>
      expect(screen.queryByTestId("reflection-definition")).not.toBeInTheDocument(),
    );
  });

  it("shows a predicate answer's curated definition, marked reversed for a reverse answer", async () => {
    renderPage("j-retarget");
    const option = await screen.findByTestId("reflection-option-predicate_for-reverse:holds");
    await waitFor(() => expect(option).toHaveAttribute("data-defined", "true"));

    fireEvent.mouseEnter(option);
    const overlay = await screen.findByTestId("reflection-definition");
    expect(overlay).toHaveTextContent("holds · reversed");
    expect(overlay).toHaveTextContent("The source keeps the destination inside it.");
  });

  it("moves along on a scroll that keeps its answer in view", async () => {
    renderPage("j-retarget");
    const option = await screen.findByTestId("reflection-option-source_for-project");
    await waitFor(() => expect(option).toHaveAttribute("data-defined", "true"));
    const inspector = screen.getByTestId("operation-inspector");
    const rect = (top: number, left: number, height: number, width: number) =>
      ({ top, left, bottom: top + height, right: left + width, height, width }) as DOMRect;
    vi.spyOn(inspector, "getBoundingClientRect").mockReturnValue(rect(0, 1000, 800, 380));
    const spy = vi.spyOn(option, "getBoundingClientRect").mockReturnValue(rect(500, 1010, 30, 360));

    fireEvent.focus(within(option).getByRole("radio"));
    const overlay = await screen.findByTestId("reflection-definition");
    // Beside the inspector: its right edge a gap short of the inspector's left.
    expect(overlay.style.left).toBe(`${1000 - 360 - 12}px`);

    spy.mockReturnValue(rect(300, 1010, 30, 360));
    fireEvent.scroll(inspector);
    await waitFor(() =>
      expect(screen.getByTestId("reflection-definition").style.top).toBe("300px"),
    );
  });

  it("opens on keyboard focus, closes on blur and on Escape", async () => {
    renderPage("j-retarget");
    const option = await screen.findByTestId("reflection-option-source_for-project");
    await waitFor(() => expect(option).toHaveAttribute("data-defined", "true"));
    const radio = within(option).getByRole("radio");

    fireEvent.focus(radio);
    expect(await screen.findByTestId("reflection-definition")).toHaveTextContent(
      DEFINITIONS.project,
    );
    // The radio is described by the definition whether or not the overlay shows.
    const describedBy = radio.getAttribute("aria-describedby")!.split(" ");
    const description = describedBy.map((id) => document.getElementById(id)?.textContent).join(" ");
    expect(description).toContain(DEFINITIONS.project);

    fireEvent.blur(radio);
    expect(screen.queryByTestId("reflection-definition")).not.toBeInTheDocument();

    fireEvent.focus(radio);
    await screen.findByTestId("reflection-definition");
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() =>
      expect(screen.queryByTestId("reflection-definition")).not.toBeInTheDocument(),
    );
  });

  it("lets a read-only answer's name take focus to open its overlay", async () => {
    proposal.operations.find((o) => o.id === "j-retarget")!.status = "applied";
    renderPage("j-retarget");
    const option = await screen.findByTestId("reflection-option-source_for-task");
    await waitFor(() => expect(option).toHaveAttribute("data-defined", "true"));
    expect(within(option).getByRole("radio")).toBeDisabled();
    const name = option.querySelector(".reflection-option__name") as HTMLElement;
    expect(name).toHaveAttribute("tabindex", "0");

    fireEvent.focus(name);
    expect(await screen.findByTestId("reflection-definition")).toHaveTextContent(DEFINITIONS.task);
  });

  it("shows no overlay for none or an undefined answer", async () => {
    renderPage("j-retarget");
    const option = await screen.findByTestId("reflection-option-source_for-project");
    await waitFor(() => expect(option).toHaveAttribute("data-defined", "true"));
    for (const id of ["reflection-option-source_for-none", "reflection-option-source_for-tool"]) {
      const other = screen.getByTestId(id);
      expect(other).not.toHaveAttribute("data-defined");
      fireEvent.mouseEnter(other);
      expect(screen.queryByTestId("reflection-definition")).not.toBeInTheDocument();
    }
  });
});

describe("conflict cards", () => {
  it("select an item when it is clicked anywhere, as a row click does", async () => {
    const onSelect = renderPage();
    const item = await screen.findByTestId("conflict-op-c-delete");

    await userEvent.click(item.querySelector(".conflict-op__rationale")!);
    expect(onSelect).toHaveBeenLastCalledWith("c-delete");

    // The seq button is still the keyboard control, and selects once, not twice.
    onSelect.mockClear();
    await userEvent.click(within(item).getByTestId("conflict-select-c-delete"));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenLastCalledWith("c-delete");
  });

  it("deselect the selected item when it is clicked again", async () => {
    const onSelect = renderPage("c-rename");
    const item = await screen.findByTestId("conflict-op-c-rename");
    expect(item).toHaveClass("conflict-op--selected");
    await userEvent.click(item.querySelector(".conflict-op__rationale")!);
    expect(onSelect).toHaveBeenLastCalledWith(undefined);
  });

  it("follow Needs decision: decided items drop out, then the card once all are decided", async () => {
    proposal.operations.find((o) => o.id === "c-rename")!.status = "applied";
    renderPage();
    const card = await screen.findByTestId("conflict-card-c-rename");
    expect(screen.getByTestId("proposal-operations-table")).toHaveAttribute("data-filter", "needs");
    // One member applied, the other still awaiting: the card stays, with the awaiting one.
    expect(within(card).queryByTestId("conflict-op-c-rename")).not.toBeInTheDocument();
    expect(within(card).getByTestId("conflict-op-c-delete")).toBeInTheDocument();
    expect(within(card).getByTestId("conflict-kept-c-rename")).toHaveTextContent(
      "Seq 8 is applied.",
    );

    await userEvent.click(within(card).getByTestId("conflict-reject-rest-c-rename"));
    await waitFor(() =>
      expect(screen.queryByTestId("conflict-card-c-rename")).not.toBeInTheDocument(),
    );

    await userEvent.click(
      within(screen.getByRole("group", { name: "Show operations" })).getByText(/^Decided/),
    );
    const decided = await screen.findByTestId("conflict-card-c-rename");
    expect(within(decided).getByTestId("conflict-op-c-rename")).toBeInTheDocument();
    expect(within(decided).getByTestId("conflict-op-c-delete")).toBeInTheDocument();
  });

  it("offer no actions under Decided for members they hide", async () => {
    proposal.operations.find((o) => o.id === "c-rename")!.status = "applied";
    renderPage();
    await screen.findByTestId("conflict-card-c-rename");
    await userEvent.click(
      within(screen.getByRole("group", { name: "Show operations" })).getByText(/^Decided/),
    );
    const card = screen.getByTestId("conflict-card-c-rename");
    expect(within(card).getByTestId("conflict-op-c-rename")).toBeInTheDocument();
    expect(within(card).queryByTestId("conflict-op-c-delete")).not.toBeInTheDocument();
    // c-delete still awaits, but the card doesn't show it, so it can't reject it from here.
    expect(within(card).queryByTestId("conflict-reject-rest-c-rename")).not.toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: /Keep|Reject/ })).not.toBeInTheDocument();
  });

  it("show every member under All", async () => {
    proposal.operations.find((o) => o.id === "c-rename")!.status = "applied";
    renderPage();
    await screen.findByTestId("conflict-card-c-rename");
    await userEvent.click(
      within(screen.getByRole("group", { name: "Show operations" })).getByText(/^All/),
    );
    const card = screen.getByTestId("conflict-card-c-rename");
    expect(within(card).getByTestId("conflict-op-c-rename")).toBeInTheDocument();
    expect(within(card).getByTestId("conflict-op-c-delete")).toBeInTheDocument();
  });
});
