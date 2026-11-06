/**
 * Tiered apply (#1411): a reflection proposal grouped by change kind.
 * Mechanical kinds accept by threshold (stale and blocked never selected),
 * judgment kinds are never bulk-selected, conflicts keep one or reject both,
 * and the inspector's reflection answers accept the plan or the reviewer's
 * picks (an edit plus the chosen alternative).
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import { goldPage, proposalHandlers } from "@/test/proposalFixtures";
import { reflectionProposal } from "@/test/reflectionFixtures";
import type { ChangeProposal } from "@/api/services/proposals";
import { ProposalDetailPage } from "../ProposalDetailPage";

const server = setupServer(...proposalHandlers, ...entityPageHandlers);

let proposal: ChangeProposal;
let applied: Record<string, unknown>[];
let rejected: { operation_ids: string[]; note: string | null }[];

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  proposal = reflectionProposal();
  applied = [];
  rejected = [];
  server.use(
    http.get("*/api/proposals/:id", () => HttpResponse.json(proposal)),
    http.get("*/api/taxonomies/:id/gold", () => HttpResponse.json(goldPage(proposal.operations))),
    http.post("*/api/proposals/:id/apply", async ({ request }) => {
      const body = (await request.json()) as { operation_ids: string[] };
      applied.push(body);
      for (const op of proposal.operations) {
        if (body.operation_ids.includes(op.id)) Object.assign(op, { status: "applied" });
      }
      return HttpResponse.json(proposal);
    }),
    http.post("*/api/proposals/:id/reject", async ({ request }) => {
      const body = (await request.json()) as { operation_ids: string[]; note: string | null };
      rejected.push(body);
      for (const op of proposal.operations) {
        if (body.operation_ids.includes(op.id)) {
          Object.assign(op, { status: "rejected", reason: body.note });
        }
      }
      return HttpResponse.json(proposal);
    }),
  );
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderPage(selectedOperationId?: string) {
  return render(
    <ProposalDetailPage
      id="proposal-1"
      selectedOperationId={selectedOperationId}
      onSelectOperation={vi.fn()}
    />,
  );
}

async function tiered() {
  return screen.findByTestId("tiered-operations");
}

describe("Group by change kind", () => {
  it("defaults to change kind for reflection operations, with mechanical, judgment and conflicts", async () => {
    renderPage();
    await tiered();

    const table = screen.getByTestId("proposal-operations-table");
    expect(table).toHaveAttribute("data-group-by", "kind");
    const mechanical = screen.getByTestId("tiered-mechanical");
    expect(within(mechanical).getByText("Mechanical · accept by threshold")).toBeInTheDocument();
    for (const kind of ["remove-duplicate", "rename-predicate", "reverse"]) {
      expect(within(mechanical).getByTestId(`tiered-group-${kind}`)).toBeInTheDocument();
    }
    expect(
      within(screen.getByTestId("tiered-group-reverse")).getByText("2 · p 0.50–0.95"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("tiered-group-remove-duplicate")).getByText("1 · p 0.90"),
    ).toBeInTheDocument();

    const judgment = screen.getByTestId("tiered-judgment");
    expect(within(judgment).getByTestId("tiered-group-retarget")).toBeInTheDocument();
    expect(within(judgment).getByTestId("tiered-group-compound")).toBeInTheDocument();
    // a judgment row: the current triple struck through, the plan's pick and the best alternative
    const change = screen.getByTestId("judgment-change-j-retarget");
    expect(change.querySelector("s")).toHaveTextContent("task located_in room");
    expect(change).toHaveTextContent("plan project located_in room");
    expect(screen.getByTestId("judgment-alt-j-retarget")).toHaveTextContent(
      "best source task (current) · p 0.15",
    );

    const conflicts = screen.getByTestId("tiered-conflicts");
    const card = within(conflicts).getByTestId("conflict-card-c-rename");
    expect(within(card).getByTestId("conflict-op-c-rename")).toBeInTheDocument();
    expect(within(card).getByTestId("conflict-op-c-delete")).toBeInTheDocument();
    expect(card).toHaveAttribute("role", "group");
    // conflict rows are only in the conflict card
    expect(within(judgment).queryByTestId("operation-diff-c-rename")).not.toBeInTheDocument();
  });

  it("switches to the flat sequence table and back", async () => {
    renderPage();
    await tiered();
    const group = screen.getByRole("group", { name: "Group operations by" });

    await userEvent.click(within(group).getByText("Sequence"));
    expect(screen.queryByTestId("tiered-operations")).not.toBeInTheDocument();
    expect(screen.getByTestId("proposal-operations-table")).toHaveAttribute(
      "data-group-by",
      "sequence",
    );
    // judgment and conflict rows get no checkbox there either
    expect(screen.getByTestId("operation-check-m-dup")).toBeInTheDocument();
    expect(screen.queryByTestId("operation-check-j-retarget")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operation-check-c-rename")).not.toBeInTheDocument();

    await userEvent.click(within(group).getByText("Change kind"));
    expect(await tiered()).toBeInTheDocument();
  });

  it("keeps the sequence view for operations without reflection data", async () => {
    proposal.operations = proposal.operations.map((o) => ({ ...o, reflection: null }));
    renderPage();
    expect(await screen.findByTestId("proposal-operations-table")).toHaveAttribute(
      "data-group-by",
      "sequence",
    );
    // plan kinds from the rationale still offer the change kind grouping
    expect(screen.getByTestId("proposal-group-by")).toBeInTheDocument();
  });
});

describe("Threshold over mechanical kinds", () => {
  it("selects only mechanical, non-stale, non-blocked operations at or above p", async () => {
    renderPage();
    await tiered();

    // default 0.60: m-dup (0.9) and m-rename (0.7); m-stale and m-blocked never; m-reverse is below
    expect(screen.getByTestId("tiered-accept-threshold")).toHaveTextContent("Accept 2 at or above");
    expect(screen.getByTestId("operation-threshold-mark-m-dup")).toHaveAttribute("role", "img");
    expect(screen.getByTestId("operation-threshold-mark-m-rename")).toBeInTheDocument();
    for (const id of ["m-reverse", "m-stale", "m-blocked", "j-retarget", "j-compound"]) {
      expect(screen.queryByTestId(`operation-threshold-mark-${id}`)).not.toBeInTheDocument();
    }
    expect(screen.getByTestId("tiered-group-selected-rename-predicate")).toHaveTextContent(
      "1 of 2 selected",
    );
    expect(screen.getByTestId("tiered-group-selected-reverse")).toHaveTextContent(
      "0 of 2 selected",
    );
    expect(screen.getByTestId("operation-probability-m-reverse")).toHaveClass(
      "op-probability--below",
    );

    fireEvent.change(screen.getByTestId("tiered-threshold-slider"), { target: { value: "0.5" } });
    expect(screen.getByTestId("tiered-threshold-value")).toHaveTextContent("0.50");
    expect(screen.getByTestId("tiered-accept-threshold")).toHaveTextContent("Accept 3 at or above");
    expect(screen.getByTestId("tiered-group-selected-reverse")).toHaveTextContent(
      "1 of 2 selected",
    );

    await userEvent.click(screen.getByTestId("tiered-accept-threshold"));
    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0]).toMatchObject({
      operation_ids: ["m-dup", "m-rename", "m-reverse"],
      force_stale: [],
      edits: {},
    });
    expect(applied[0]).not.toHaveProperty("chosen_alternatives");
  });

  it("never counts judgment or conflict rows in Accept N ready", async () => {
    renderPage();
    await tiered();
    // m-dup, m-rename, m-reverse: the stale and blocked ones and every judgment/conflict row are left
    const accept = screen.getByTestId("proposal-accept-all");
    expect(accept).toHaveTextContent("Accept 3 ready");
    expect(accept).toHaveAttribute(
      "title",
      expect.stringContaining("Judgment and conflict changes are decided one by one"),
    );

    await userEvent.click(accept);
    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0].operation_ids).toEqual(["m-dup", "m-rename", "m-reverse"]);
  });
});

describe("Conflicts", () => {
  it("Keep seq N applies it and rejects the other with the conflict note", async () => {
    renderPage();
    await tiered();

    await userEvent.click(screen.getByTestId("conflict-keep-c-rename"));

    await waitFor(() => expect(rejected).toHaveLength(1));
    expect(applied).toHaveLength(1);
    expect(applied[0]).toMatchObject({ operation_ids: ["c-rename"], edits: {} });
    expect(rejected[0]).toEqual({ operation_ids: ["c-delete"], note: "conflict: kept seq 8" });
  });

  it("rejects nothing when the kept operation did not apply", async () => {
    server.use(
      http.post("*/api/proposals/:id/apply", async ({ request }) => {
        applied.push((await request.json()) as Record<string, unknown>);
        const op = proposal.operations.find((o) => o.id === "c-delete")!;
        Object.assign(op, { status: "failed", reason: "error: boom" });
        return HttpResponse.json(proposal);
      }),
    );
    renderPage();
    await tiered();

    await userEvent.click(screen.getByTestId("conflict-keep-c-delete"));

    await waitFor(() => expect(applied).toHaveLength(1));
    expect(rejected).toEqual([]);
  });

  it("Reject both rejects every awaiting operation of the cluster", async () => {
    renderPage();
    await tiered();

    await userEvent.click(screen.getByTestId("conflict-reject-all-c-rename"));

    await waitFor(() => expect(rejected).toHaveLength(1));
    expect(rejected[0]).toEqual({
      operation_ids: ["c-rename", "c-delete"],
      note: "conflict: rejected both",
    });
    expect(applied).toEqual([]);
  });

  it("Keep both changes nothing and leaves each to decide", async () => {
    renderPage();
    await tiered();

    await userEvent.click(screen.getByTestId("conflict-keep-all-c-rename"));

    expect(screen.getByTestId("conflict-individual-c-rename")).toHaveTextContent(
      "Decide each in the inspector.",
    );
    expect(screen.queryByTestId("conflict-keep-c-rename")).not.toBeInTheDocument();
    expect(applied).toEqual([]);
    expect(rejected).toEqual([]);
  });

  it("selects a conflict operation for the inspector", async () => {
    const onSelect = vi.fn();
    render(<ProposalDetailPage id="proposal-1" onSelectOperation={onSelect} />);
    await tiered();
    const op = screen.getByTestId("conflict-op-c-delete");
    expect(op).toHaveAttribute("aria-pressed", "false");

    await userEvent.click(op);
    expect(onSelect).toHaveBeenCalledWith("c-delete");
  });
});

describe("Reflection answers in the inspector", () => {
  it("shows the ranked answers marked current and plan, and the evidence pack", async () => {
    renderPage("j-retarget");
    const answers = await screen.findByTestId("reflection-answers");

    const source = within(answers).getByTestId("reflection-question-source_for");
    expect(within(source).getByRole("radiogroup")).toBeInTheDocument();
    const project = within(source).getByTestId("reflection-option-source_for-project");
    expect(within(project).getByRole("radio")).toBeChecked();
    expect(within(project).getByText("plan")).toBeInTheDocument();
    expect(within(project).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "75");
    expect(project).toHaveClass("reflection-option--chosen");
    const task = within(source).getByTestId("reflection-option-source_for-task");
    expect(within(task).getByText("current")).toBeInTheDocument();
    // 'none' can't be picked
    expect(
      within(within(source).getByTestId("reflection-option-source_for-none")).getByRole("radio"),
    ).toBeDisabled();

    const pack = screen.getByTestId("reflection-evidence-pack");
    expect(pack).toHaveTextContent("Tasks are filed in projects.");
    expect(screen.getByTestId("operation-accept")).toHaveTextContent("Accept plan");
  });

  it("Accept plan applies the operation as proposed", async () => {
    renderPage("j-retarget");
    await userEvent.click(await screen.findByTestId("operation-accept"));

    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0]).toEqual({ operation_ids: ["j-retarget"], force_stale: [], edits: {} });
  });

  it("an alternative pick accepts with an edit and the chosen alternative", async () => {
    renderPage("j-retarget");
    const tool = await screen.findByTestId("reflection-option-source_for-tool");
    await userEvent.click(within(tool).getByRole("radio"));

    const accept = screen.getByTestId("operation-accept");
    expect(accept).toHaveTextContent("Accept with my picks");
    expect(screen.getByTestId("operation-picks-callout")).toHaveTextContent(
      "Your picks make tool located_in room instead of the plan's project located_in room.",
    );

    await userEvent.click(accept);
    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0]).toEqual({
      operation_ids: ["j-retarget"],
      force_stale: [],
      edits: {
        "j-retarget": {
          canonical_predicate: "located_in",
          domain_class_id: "class-tool",
          range_class_id: "class-room",
        },
      },
      chosen_alternatives: {
        "j-retarget": {
          source_for: "tool",
          target_for: "room",
          predicate_for: "located_in",
          triple: "tool located_in room",
          plan: "project located_in room",
        },
      },
    });
  });

  it("a reverse pick swaps the ends of the edit", async () => {
    renderPage("j-retarget");
    const reverse = await screen.findByTestId("reflection-option-predicate_for-reverse:holds");
    await userEvent.click(within(reverse).getByRole("radio"));
    await userEvent.click(screen.getByTestId("operation-accept"));

    await waitFor(() => expect(applied).toHaveLength(1));
    expect((applied[0].edits as Record<string, unknown>)["j-retarget"]).toEqual({
      canonical_predicate: "holds",
      domain_class_id: "class-room",
      range_class_id: "class-project",
    });
  });

  it("picks that make the current triple can't be accepted", async () => {
    renderPage("j-retarget");
    const task = await screen.findByTestId("reflection-option-source_for-task");
    await userEvent.click(within(task).getByRole("radio"));

    expect(screen.getByTestId("operation-accept")).toBeDisabled();
    expect(screen.getByTestId("operation-picks-callout")).toHaveTextContent(
      "Your picks keep the current triple task located_in room. To keep it, reject the operation.",
    );
  });

  it("picking the plan's answer again is a plain accept", async () => {
    renderPage("j-retarget");
    const tool = await screen.findByTestId("reflection-option-source_for-tool");
    await userEvent.click(within(tool).getByRole("radio"));
    const project = screen.getByTestId("reflection-option-source_for-project");
    await userEvent.click(within(project).getByRole("radio"));

    const accept = screen.getByTestId("operation-accept");
    expect(accept).toHaveTextContent("Accept plan");
    expect(screen.queryByTestId("operation-picks-callout")).not.toBeInTheDocument();
    await userEvent.click(accept);
    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0]).not.toHaveProperty("chosen_alternatives");
  });

  it("a decided operation's answers are read-only", async () => {
    proposal.operations.find((o) => o.id === "j-retarget")!.status = "applied";
    renderPage("j-retarget");
    const answers = await screen.findByTestId("reflection-answers");
    for (const radio of within(answers).getAllByRole("radio")) expect(radio).toBeDisabled();
  });
});
