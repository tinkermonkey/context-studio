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
import { goldPage, proposalHandlers, unamended } from "@/test/proposalFixtures";
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

/** The review list, once the proposal has loaded. */
async function list() {
  return screen.findByTestId("proposal-operations-list");
}

/** Opens Select ▾ and returns its menu. */
async function openSelect() {
  await userEvent.click(screen.getByTestId("review-bulk-select"));
  return screen.getByTestId("review-bulk-select-menu");
}

describe("Group by change kind", () => {
  it("defaults to change kind for reflection operations, with mechanical, judgment and conflicts", async () => {
    renderPage();
    expect(await list()).toHaveAttribute("data-group-by", "kind");

    for (const kind of ["remove-duplicate", "rename-predicate", "reverse"]) {
      expect(screen.getByTestId(`review-group-kind-${kind}`)).toBe(
        screen.getByRole("group", { name: `${kind} · mechanical` }),
      );
    }
    expect(
      within(screen.getByTestId("review-group-kind-reverse")).getByText("2 · p 0.50–0.95"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("review-group-kind-remove-duplicate")).getByText("1 · p 0.90"),
    ).toBeInTheDocument();

    const judgment = ["retarget", "compound"].map((kind) => {
      const section = screen.getByTestId(`review-group-kind-${kind}`);
      expect(section).toBe(screen.getByRole("group", { name: `${kind} · judgment` }));
      return section;
    });
    // a judgment row shows its change inline (alternatives are in the inspector)
    const row = within(judgment[0]).getByTestId("review-row-j-retarget");
    expect(within(row).getByTestId("operation-diff-j-retarget")).toBeInTheDocument();

    const conflicts = screen.getByTestId("review-group-conflicts");
    const card = within(conflicts).getByTestId("conflict-card-c-rename");
    expect(within(card).getByTestId("conflict-op-c-rename")).toBeInTheDocument();
    expect(within(card).getByTestId("conflict-op-c-delete")).toBeInTheDocument();
    expect(card).toHaveAttribute("role", "group");
    // conflict rows are only in the conflict card
    expect(screen.queryByTestId("review-row-c-rename")).not.toBeInTheDocument();
    expect(screen.queryByTestId("review-row-c-delete")).not.toBeInTheDocument();
    for (const section of judgment) {
      expect(within(section).queryByTestId("operation-diff-c-rename")).not.toBeInTheDocument();
    }
  });

  it("switches to the flat sequence table and back", async () => {
    renderPage();
    await list();
    const group = screen.getByRole("group", { name: "Group operations by" });

    await userEvent.click(within(group).getByText("Sequence"));
    expect(screen.queryByTestId("review-group-conflicts")).not.toBeInTheDocument();
    expect(screen.getByTestId("review-group-sequence")).toBeInTheDocument();
    expect(screen.getByTestId("proposal-operations-list")).toHaveAttribute(
      "data-group-by",
      "sequence",
    );
    // judgment and conflict rows get no checkbox there either
    expect(screen.getByTestId("operation-check-m-dup")).toBeInTheDocument();
    expect(screen.queryByTestId("operation-check-j-retarget")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operation-check-c-rename")).not.toBeInTheDocument();

    await userEvent.click(within(group).getByText("Change kind"));
    expect(screen.getByTestId("proposal-operations-list")).toHaveAttribute("data-group-by", "kind");
    expect(screen.getByTestId("review-group-conflicts")).toBeInTheDocument();
  });

  it("keeps the sequence view for operations without reflection data", async () => {
    proposal.operations = proposal.operations.map((o) => ({ ...o, reflection: null }));
    renderPage();
    expect(await list()).toHaveAttribute("data-group-by", "sequence");
    // plan kinds from the rationale still offer the change kind grouping
    expect(screen.getByTestId("proposal-group-by")).toBeInTheDocument();
  });
});

describe("Threshold over mechanical kinds", () => {
  it("selects only mechanical, non-stale, non-blocked operations at or above p", async () => {
    renderPage();
    await list();
    expect(
      screen.getByTestId("review-row-m-reverse").querySelector(".review-row__p"),
    ).toHaveTextContent("0.50");

    // default 0.60: m-dup (0.9) and m-rename (0.7); m-stale and m-blocked never; m-reverse is below
    let menu = await openSelect();
    expect(within(menu).getByTestId("proposal-threshold-value")).toHaveTextContent("0.60");
    expect(within(menu).getByTestId("review-bulk-select-threshold")).toHaveTextContent(
      "At or above p 0.60 · 2",
    );

    fireEvent.change(within(menu).getByTestId("proposal-threshold-slider"), {
      target: { value: "0.5" },
    });
    expect(within(menu).getByTestId("proposal-threshold-value")).toHaveTextContent("0.50");
    expect(within(menu).getByTestId("review-bulk-select-threshold")).toHaveTextContent(
      "At or above p 0.50 · 3",
    );
    await userEvent.click(within(menu).getByTestId("review-bulk-select-threshold"));
    expect(screen.queryByTestId("review-bulk-select-menu")).not.toBeInTheDocument();

    for (const id of ["m-dup", "m-rename", "m-reverse"]) {
      expect(screen.getByTestId(`operation-check-${id}`)).toBeChecked();
    }
    for (const id of ["m-stale", "m-blocked"]) {
      expect(screen.getByTestId(`operation-check-${id}`)).not.toBeChecked();
    }
    for (const id of ["j-retarget", "j-compound"]) {
      expect(screen.queryByTestId(`operation-check-${id}`)).not.toBeInTheDocument();
    }
    expect(screen.getByTestId("proposal-selection-count")).toHaveTextContent("3 selected");
    // the threshold stays where it was set
    menu = await openSelect();
    expect(within(menu).getByTestId("proposal-threshold-value")).toHaveTextContent("0.50");
    await userEvent.click(screen.getByTestId("review-bulk-select"));

    await userEvent.click(screen.getByTestId("proposal-selection-accept"));
    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0]).toMatchObject({
      operation_ids: ["m-dup", "m-rename", "m-reverse"],
      amended_at: unamended(["m-dup", "m-rename", "m-reverse"]),
      force_stale: [],
      edits: {},
    });
    expect(applied[0]).not.toHaveProperty("chosen_alternatives");
  });

  it("never counts judgment or conflict rows in Accept N ready", async () => {
    renderPage();
    await list();
    // m-dup, m-rename, m-reverse: the stale and blocked ones and every judgment/conflict row are left
    const menu = await openSelect();
    expect(within(menu).getByTestId("review-bulk-select-ready")).toHaveTextContent("All ready · 3");
    expect(
      within(menu).getByText(/Judgment and conflict changes are decided one by one/),
    ).toBeInTheDocument();

    await userEvent.click(within(menu).getByTestId("review-bulk-select-ready"));
    await userEvent.click(screen.getByTestId("proposal-selection-accept"));
    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0].operation_ids).toEqual(["m-dup", "m-rename", "m-reverse"]);
  });
});

describe("Conflicts", () => {
  it("Keep seq N applies it and rejects the other with the conflict note", async () => {
    renderPage();
    await list();

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
    await list();

    await userEvent.click(screen.getByTestId("conflict-keep-c-delete"));

    await waitFor(() => expect(applied).toHaveLength(1));
    expect(rejected).toEqual([]);
  });

  it("Reject both rejects every awaiting operation of the cluster", async () => {
    renderPage();
    await list();

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
    await list();

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
    await list();
    const op = screen.getByTestId("conflict-select-c-delete");
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
    expect(screen.getByRole("group", { name: "Best source" })).toBe(source); // a fieldset
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
    expect(applied[0]).toEqual({
      operation_ids: ["j-retarget"],
      amended_at: unamended(["j-retarget"]),
      force_stale: [],
      edits: {},
    });
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
      amended_at: unamended(["j-retarget"]),
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

describe("Conflicts: dependents, bulk and a kept operation", () => {
  it("never rejects a delete that only names the kept operation's type as its replacement", async () => {
    proposal.operations.push({
      ...proposal.operations[0],
      id: "x-dependent",
      seq: 10,
      target_id: "prop-x",
      proposed_replacement_id: "prop-c-rename",
      reflection: null,
      rationale: "Remove it. Plan kind remove-duplicate, p 0.90.",
    });
    renderPage();
    await list();
    const card = screen.getByTestId("conflict-card-c-rename");
    expect(within(card).queryByTestId("conflict-op-x-dependent")).not.toBeInTheDocument();

    await userEvent.click(screen.getByTestId("conflict-keep-c-rename"));

    await waitFor(() => expect(rejected).toHaveLength(1));
    expect(rejected[0].operation_ids).toEqual(["c-delete"]);
  });

  it("leaves a mechanical change shown in a conflict card out of every bulk decision", async () => {
    const linked = structuredClone(proposal.operations.find((o) => o.id === "m-rename")!);
    Object.assign(linked, {
      id: "m-linked",
      seq: 10,
      target_id: "prop-m-linked",
      probability: 0.99,
    });
    linked.reflection = {
      ...linked.reflection!,
      current: { source: "task", predicate: "employs", target: "tool" },
      replacement: "task uses tool",
    };
    proposal.operations.push(linked);
    renderPage();
    await list();

    expect(
      within(screen.getByTestId("conflict-card-c-rename")).getByTestId("conflict-op-m-linked"),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("review-row-m-linked")).not.toBeInTheDocument();
    const menu = await openSelect();
    expect(within(menu).getByTestId("review-bulk-select-threshold")).toHaveTextContent(
      "At or above p 0.60 · 2",
    );
    expect(within(menu).getByTestId("review-bulk-select-ready")).toHaveTextContent("All ready · 3");
    expect(within(menu).getByTestId("review-bulk-select-awaiting")).toHaveTextContent(
      "All awaiting · 5",
    );
    await userEvent.click(screen.getByTestId("review-bulk-select"));

    await userEvent.click(
      within(screen.getByRole("group", { name: "Group operations by" })).getByText("Sequence"),
    );
    expect(screen.getByTestId("operation-check-m-rename")).toBeInTheDocument();
    expect(screen.queryByTestId("operation-check-m-linked")).not.toBeInTheDocument();
  });

  it("once a member is applied, the rest can only be rejected as kept against it", async () => {
    proposal.operations.find((o) => o.id === "c-rename")!.status = "applied";
    renderPage();
    await list();
    const card = screen.getByTestId("conflict-card-c-rename");

    expect(within(card).getByTestId("conflict-kept-c-rename")).toHaveTextContent(
      "Seq 8 is applied.",
    );
    expect(within(card).queryByTestId("conflict-keep-c-delete")).not.toBeInTheDocument();
    expect(within(card).queryByTestId("conflict-keep-all-c-rename")).not.toBeInTheDocument();

    await userEvent.click(within(card).getByTestId("conflict-reject-rest-c-rename"));
    await waitFor(() => expect(rejected).toHaveLength(1));
    expect(rejected[0]).toEqual({ operation_ids: ["c-delete"], note: "conflict: kept seq 8" });
  });

  it("shows the kept state when the reject after a keep fails", async () => {
    server.use(
      http.post("*/api/proposals/:id/reject", () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    );
    renderPage();
    await list();

    await userEvent.click(screen.getByTestId("conflict-keep-c-rename"));

    expect(await screen.findByTestId("conflict-kept-c-rename")).toBeInTheDocument();
    expect(screen.getByTestId("conflict-reject-rest-c-rename")).toHaveTextContent(
      "Reject the rest (conflict: kept seq 8)",
    );
    expect(screen.queryByTestId("conflict-keep-c-delete")).not.toBeInTheDocument();
  });
});

describe("Picks on a type relationships use", () => {
  const edges = (n: number) => ({
    edges: Array.from({ length: n }, (_, i) => ({
      relationship_id: `rel-${i}`,
      source: { id: `a-${i}`, title: `A${i}`, class_ids: [], class_titles: [] },
      target: { id: `b-${i}`, title: `B${i}`, class_ids: [], class_titles: [] },
      attributes: {},
    })),
    replacements: [],
  });
  const op = (id: string) => proposal.operations.find((o) => o.id === id)!;
  const addOption = (id: string, question: string, option: string, classId: string | null) =>
    op(id)
      .reflection!.questions.find((q) => q.question === question)!
      .options.push({ option, probability: 0.04, class_id: classId, current: false, plan: false });
  const pick = async (question: string, option: string) =>
    userEvent.click(
      within(await screen.findByTestId(`reflection-option-${question}-${option}`)).getByRole(
        "radio",
      ),
    );

  it("a blocked operation whose picks retarget it resolves with the edit and the alternative", async () => {
    addOption("m-blocked", "target_for", "room", "class-room");
    renderPage("m-blocked");
    await pick("target_for", "room");

    expect(screen.queryByTestId("operation-accept")).not.toBeInTheDocument();
    expect(screen.getByTestId("operation-in-use-callout")).toHaveTextContent(
      "Your picks retarget this type to project contains room",
    );
    await userEvent.click(screen.getByTestId("operation-resolution-apply"));

    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0]).toMatchObject({
      operation_ids: ["m-blocked"],
      edits: {
        "m-blocked": {
          canonical_predicate: "contains",
          domain_class_id: "class-project",
          range_class_id: "class-room",
        },
      },
      chosen_alternatives: { "m-blocked": { target_for: "room", triple: "project contains room" } },
      resolutions: { "m-blocked": { strategy: "delete", relationship_ids: ["rel-1"] } },
    });
  });

  it("a blocked operation whose picks only rename it applies as an edit, without a resolution", async () => {
    addOption("m-blocked", "predicate_for", "includes", null);
    renderPage("m-blocked");
    await pick("predicate_for", "includes");

    expect(screen.queryByTestId("operation-in-use")).not.toBeInTheDocument();
    const accept = screen.getByTestId("operation-accept");
    expect(accept).toHaveTextContent("Accept with my picks");
    await userEvent.click(accept);

    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0]).toMatchObject({
      operation_ids: ["m-blocked"],
      edits: { "m-blocked": { canonical_predicate: "includes" } },
      chosen_alternatives: { "m-blocked": { predicate_for: "includes" } },
    });
    expect(applied[0]).not.toHaveProperty("resolutions");
  });

  it("a rename in use whose picks retarget it offers the resolver over its usage", async () => {
    op("m-rename").type_usage = edges(2);
    addOption("m-rename", "source_for", "task", "class-task");
    renderPage("m-rename");
    expect(await screen.findByTestId("operation-accept")).toHaveTextContent("Accept plan");

    await pick("source_for", "task");

    expect(screen.queryByTestId("operation-accept")).not.toBeInTheDocument();
    expect(screen.getByTestId("operation-in-use-callout")).toHaveTextContent(
      "2 relationships still use it",
    );
    await userEvent.click(screen.getByTestId("operation-resolution-apply"));
    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0]).toMatchObject({
      edits: { "m-rename": { domain_class_id: "class-task" } },
      resolutions: { "m-rename": { strategy: "delete", relationship_ids: ["rel-0", "rel-1"] } },
    });
  });

  it("after a pick edit fails, other picks can be accepted again", async () => {
    addOption("j-retarget", "source_for", "room", "class-room");
    server.use(
      http.post("*/api/proposals/:id/apply", async ({ request }) => {
        applied.push((await request.json()) as Record<string, unknown>);
        Object.assign(op("j-retarget"), { status: "failed", reason: "invalid_edit: exists" });
        return HttpResponse.json(proposal);
      }),
    );
    renderPage("j-retarget");
    await pick("source_for", "tool");
    await userEvent.click(screen.getByTestId("operation-accept"));
    // the same picks again would be refused again: nothing to accept until they change
    await waitFor(() => expect(screen.getByTestId("operation-accept")).toBeDisabled());
    expect(screen.getByTestId("operation-picks-callout")).toHaveTextContent("was refused");

    await pick("source_for", "room");
    const accept = screen.getByTestId("operation-accept");
    expect(accept).toHaveTextContent("Accept with my picks");
    await userEvent.click(accept);
    await waitFor(() => expect(applied).toHaveLength(2));
    expect(applied[1]).toMatchObject({
      edits: { "j-retarget": { domain_class_id: "class-room" } },
      chosen_alternatives: { "j-retarget": { source_for: "room" } },
    });
  });

  it("picks that can't be written as an edit disable accept instead of accepting the plan", async () => {
    const reflection = op("j-retarget").reflection!;
    for (const q of reflection.questions) for (const o of q.options) o.class_id = null;
    renderPage("j-retarget");
    // a reverse needs class ids: not pickable
    const reverse = await screen.findByTestId("reflection-option-predicate_for-reverse:holds");
    expect(within(reverse).getByRole("radio")).toBeDisabled();
    expect(screen.getByTestId("operation-accept")).toHaveTextContent("Accept plan");
  });

  it("a predicate-only pick without class ids applies as a rename edit", async () => {
    const reflection = op("m-rename").reflection!;
    for (const q of reflection.questions) for (const o of q.options) o.class_id = null;
    addOption("m-rename", "predicate_for", "keeps", null);
    renderPage("m-rename");
    await pick("predicate_for", "keeps");
    await userEvent.click(screen.getByTestId("operation-accept"));

    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0]).toMatchObject({
      edits: { "m-rename": { canonical_predicate: "keeps" } },
      chosen_alternatives: { "m-rename": { predicate_for: "keeps" } },
    });
  });
});

describe("Review round 2", () => {
  const edges = (n: number) => ({
    edges: Array.from({ length: n }, (_, i) => ({
      relationship_id: `rel-${i}`,
      source: { id: `a-${i}`, title: `A${i}`, class_ids: [], class_titles: [] },
      target: { id: `b-${i}`, title: `B${i}`, class_ids: [], class_titles: [] },
      attributes: {},
    })),
    replacements: [],
  });
  const op = (id: string) => proposal.operations.find((o) => o.id === id)!;
  const addOption = (id: string, question: string, option: string, classId: string | null) =>
    op(id)
      .reflection!.questions.find((q) => q.question === question)!
      .options.push({ option, probability: 0.04, class_id: classId, current: false, plan: false });
  const pick = async (question: string, option: string) =>
    userEvent.click(
      within(await screen.findByTestId(`reflection-option-${question}-${option}`)).getByRole(
        "radio",
      ),
    );
  /** The next apply fails the operation with `reason`. */
  const failNextApply = (id: string, reason: string) =>
    server.use(
      http.post(
        "*/api/proposals/:id/apply",
        async ({ request }) => {
          applied.push((await request.json()) as Record<string, unknown>);
          Object.assign(op(id), { status: "failed", reason });
          return HttpResponse.json(proposal);
        },
        { once: true },
      ),
    );

  it.each([
    ["a blocked operation", "m-blocked", "target_for", "room", "class-room"],
    ["a rename in use (type_usage)", "m-rename", "source_for", "task", "class-task"],
  ])(
    "%s: a failed resolution keeps the picks and the retarget resolver",
    async (_label, id, question, option, classId) => {
      if (id === "m-rename") op(id).type_usage = edges(2);
      addOption(id, question, option, classId);
      failNextApply(id, "unresolvable: a relationship doesn't fit");
      renderPage(id);
      await pick(question, option);
      await userEvent.click(screen.getByTestId("operation-resolution-apply"));
      await waitFor(() => expect(applied).toHaveLength(1));

      // still the retarget with the same picks: never the plan, never a delete as proposed
      expect(await screen.findByTestId("operation-resolution-failed")).toHaveTextContent(
        "unresolvable: a relationship doesn't fit",
      );
      expect(screen.getByTestId("operation-in-use-callout")).toHaveTextContent(
        "Your picks retarget this type",
      );
      expect(screen.queryByTestId("operation-accept")).not.toBeInTheDocument();

      await userEvent.click(screen.getByTestId("operation-resolution-apply"));
      await waitFor(() => expect(applied).toHaveLength(2));
      expect(applied[1]).toMatchObject({
        edits: applied[0].edits as object,
        chosen_alternatives: applied[0].chosen_alternatives as object,
        resolutions: { [id]: { strategy: "delete" } },
      });
    },
  );

  it("a refused edit of a blocked operation's picks never falls back to the delete", async () => {
    addOption("m-blocked", "predicate_for", "includes", null);
    failNextApply("m-blocked", "invalid_edit: project includes task already exists");
    renderPage("m-blocked");
    await pick("predicate_for", "includes");
    await userEvent.click(screen.getByTestId("operation-accept"));
    await waitFor(() => expect(applied).toHaveLength(1));

    expect(await screen.findByTestId("operation-picks-callout")).toHaveTextContent(
      "The edit your picks make (project includes task) was refused",
    );
    expect(screen.queryByTestId("operation-in-use")).not.toBeInTheDocument();
    const accept = screen.getByTestId("operation-accept");
    expect(accept).toHaveTextContent("Accept with my picks");
    expect(accept).toBeDisabled();
  });

  it("picks that keep the current triple leave no resolver to apply", async () => {
    renderPage("m-blocked");
    await pick("predicate_for", "has");

    expect(screen.getByTestId("operation-picks-callout")).toHaveTextContent(
      "Your picks keep the current triple",
    );
    expect(screen.queryByTestId("operation-resolution-apply")).not.toBeInTheDocument();
    expect(screen.getByTestId("operation-accept")).toBeDisabled();
  });

  it("Keep seq N rejects only what contradicts N, not a chained member", async () => {
    const third = structuredClone(op("c-delete"));
    Object.assign(third, { id: "c-third", seq: 10, target_id: "prop-c-third" });
    third.reflection = {
      ...third.reflection!,
      current: { source: "task", predicate: "wields", target: "tool" },
      replacement: "task grips tool",
    };
    proposal.operations.push(third);
    renderPage();
    await list();
    expect(
      within(screen.getByTestId("conflict-card-c-rename")).getByTestId("conflict-op-c-third"),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByTestId("conflict-keep-c-rename"));

    await waitFor(() => expect(rejected).toHaveLength(1));
    expect(rejected[0]).toEqual({ operation_ids: ["c-delete"], note: "conflict: kept seq 8" });
    // c-third contradicted only c-delete: left to decide
    expect(await screen.findByTestId("conflict-individual-c-rename")).toHaveTextContent(
      "Seq 8 is applied; nothing left contradicts it.",
    );
    expect(op("c-third").status).toBe("pending");
  });

  it("without the current triple only the plan's answers can be picked", async () => {
    op("j-retarget").reflection!.current = null;
    renderPage("j-retarget");
    const answers = await screen.findByTestId("reflection-answers");
    const radios = within(answers).getAllByRole("radio");
    expect(radios.filter((r) => !(r as HTMLInputElement).disabled)).toHaveLength(3);
    expect(screen.getByTestId("operation-accept")).toHaveTextContent("Accept plan");
  });
});
