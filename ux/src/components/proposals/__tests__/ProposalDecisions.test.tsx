/**
 * Deciding on the proposal page (#1361): accept and reject from the inspector,
 * the probability threshold, checkbox selection with the bulk bar, Apply
 * anyway for stale operations, apply results, revert (and its 409) and the
 * decisions export.
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { component, entityPageHandlers, serviceClass, taxonomy } from "@/test/entityPageHandlers";
import { openProposal, proposalHandlers } from "@/test/proposalFixtures";
import type { ChangeProposal } from "@/api/services/proposals";
import { downloadJson } from "@/lib/download";
import { ProposalDetailPage } from "../ProposalDetailPage";

vi.mock("@/lib/download", () => ({ downloadJson: vi.fn() }));

const server = setupServer(...proposalHandlers, ...entityPageHandlers);

let proposal: ChangeProposal;
let applied: Record<string, unknown>[];
let rejected: Record<string, unknown>[];
/** Operation id -> the failure reason an apply records instead of applying it. */
let failures: Record<string, string>;
let revertResponse: () => Response;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  proposal = structuredClone(openProposal);
  proposal.operations[2].result_entity_id = "prop-new";
  applied = [];
  rejected = [];
  failures = {};
  revertResponse = () => HttpResponse.json({ detail: "unset" }, { status: 500 });
  server.use(
    http.get("*/api/proposals/:id", () => HttpResponse.json(proposal)),
    http.post("*/api/proposals/:id/apply", async ({ request }) => {
      const body = (await request.json()) as { operation_ids: string[] };
      applied.push(body);
      for (const op of proposal.operations) {
        if (!body.operation_ids.includes(op.id)) continue;
        const edit = (body as { edits?: Record<string, Record<string, unknown>> }).edits?.[op.id];
        if (failures[op.id]) Object.assign(op, { status: "failed", reason: failures[op.id] });
        else Object.assign(op, { status: "applied", reason: null, stale: false });
        if (edit && op.status === "applied") {
          op.applied_fields = { ...edit, identifier: "component_uses_service" };
        }
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
    http.post("*/api/proposals/:id/revert", () => revertResponse()),
  );
});
afterEach(() => {
  server.resetHandlers();
  vi.mocked(downloadJson).mockClear();
});
afterAll(() => server.close());

/** dr_spec classes with DR references, and a taxonomy holding the predicate catalog. */
function useDrSpec() {
  const dr = (identifier: string) => [{ source: "documentation_robotics", identifier }];
  server.use(
    http.get("*/api/classes", () =>
      HttpResponse.json({
        items: [
          { ...component, external_references: dr("application.component") },
          { ...serviceClass, external_references: dr("application.service") },
        ],
        total: 2,
        limit: 500,
        offset: 0,
      }),
    ),
    http.get("*/api/taxonomies/:id", () =>
      HttpResponse.json({
        ...taxonomy,
        external_references: [
          {
            source: "documentation_robotics",
            identifier: "spec",
            metadata: { predicates: { realizes: {}, serves: {}, uses: {} } },
          },
        ],
      }),
    ),
  );
}

function renderPage(selectedOperationId?: string) {
  return render(
    <ProposalDetailPage
      id="proposal-1"
      selectedOperationId={selectedOperationId}
      onSelectOperation={vi.fn()}
    />,
  );
}

describe("deciding one operation in the inspector", () => {
  it("accepts it: applies just that operation and shows the results", async () => {
    const user = userEvent.setup();
    renderPage("op-rename");

    const decision = await screen.findByTestId("operation-decision");
    expect(within(decision).getByRole("group", { name: "Decision" })).toBeInTheDocument();
    await user.click(within(decision).getByTestId("operation-accept"));

    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0]).toEqual({ operation_ids: ["op-rename"], force_stale: [], edits: {} });
    const results = await screen.findByTestId("proposal-apply-results");
    expect(within(results).getByTestId("apply-results-ok")).toHaveTextContent("Applied 1 of 1.");
    expect(within(screen.getByTestId("apply-outcome-op-rename")).getByText("applied")).toHaveClass(
      "chip--emerald",
    );
    expect(screen.getByTestId("apply-result-op-rename")).toHaveTextContent(
      "component_serves_service",
    );
    // Decided now: the inspector has no decision controls left.
    await waitFor(() => expect(screen.queryByTestId("operation-decision")).not.toBeInTheDocument());
  });

  it("rejects it with the optional reason as the note", async () => {
    const user = userEvent.setup();
    renderPage("op-rename");

    await user.type(await screen.findByTestId("operation-reject-note"), "Duplicate of seq 3");
    await user.click(screen.getByTestId("operation-reject"));

    await waitFor(() => expect(rejected).toHaveLength(1));
    expect(rejected[0]).toEqual({ operation_ids: ["op-rename"], note: "Duplicate of seq 3" });
    expect(applied).toHaveLength(0);
  });

  it("edits a DR triple, then accepts it: the edit is sent and the result is marked edited", async () => {
    const user = userEvent.setup();
    useDrSpec();
    renderPage("op-rename");

    await user.click(await screen.findByRole("button", { name: "Edit, then accept" }));
    const predicate = await screen.findByTestId("operation-edit-predicate");
    await waitFor(() => expect(predicate).toHaveValue("serves"));
    await user.clear(predicate);
    await user.type(predicate, "uses");
    await user.click(screen.getByRole("button", { name: "Apply edited" }));

    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0]).toEqual({
      operation_ids: ["op-rename"],
      force_stale: [],
      edits: {
        "op-rename": {
          canonical_predicate: "uses",
          domain_class_id: "class-1",
          range_class_id: "class-2",
        },
      },
    });
    const outcome = await screen.findByTestId("apply-outcome-op-rename");
    expect(within(outcome).getByText("edited")).toHaveClass("chip--violet");
    expect(screen.getByTestId("apply-result-op-rename")).toHaveTextContent(
      "component_uses_service",
    );
    // The diffs (results and operations table) show the triple that applied, not the proposed one.
    await waitFor(() =>
      expect(
        screen
          .getAllByTestId("operation-diff-op-rename")
          .map((d) => d.querySelector(".op-diff__changed")?.textContent),
      ).toEqual(["uses", "uses"]),
    );
  });

  it("offers Edit, then accept only for DR relationship types", async () => {
    renderPage("op-class");
    await screen.findByTestId("operation-decision");
    expect(screen.queryByTestId("operation-edit")).not.toBeInTheDocument();
  });
});

describe("a failed edit", () => {
  const replacement = {
    canonical_predicate: "uses",
    domain_class_id: "class-1",
    range_class_id: "class-2",
  };

  async function replaceDelete(user: ReturnType<typeof userEvent.setup>) {
    await user.click(await screen.findByRole("button", { name: "Replace instead" }));
    const predicate = await screen.findByTestId("operation-edit-predicate");
    await waitFor(() => expect(predicate).toHaveValue("realizes"));
    await user.clear(predicate);
    await user.type(predicate, "uses");
    await waitFor(() => expect(screen.getByTestId("operation-edit-apply")).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Apply replacement" }));
  }

  it("retries with the edit, never quietly as the proposed delete", async () => {
    const user = userEvent.setup();
    useDrSpec();
    proposal.operations[1].stale = false;
    failures = { "op-delete": "invalid_edit: seq 9 also produces it" };
    renderPage("op-delete");

    await replaceDelete(user);
    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0]).toEqual({
      operation_ids: ["op-delete"],
      force_stale: [],
      edits: { "op-delete": replacement },
    });
    // Its failure is the edit's: the generic button says it applies the proposal.
    expect(await screen.findByTestId("apply-retry-op-delete")).toHaveTextContent("Retry edit");
    expect(screen.getByTestId("apply-as-proposed-op-delete")).toHaveTextContent(
      "Apply as proposed",
    );

    failures = {};
    await user.click(screen.getByTestId("apply-retry-op-delete"));
    await waitFor(() => expect(applied).toHaveLength(2));
    expect(applied[1]).not.toEqual({ operation_ids: ["op-delete"], force_stale: [], edits: {} });
    expect(applied[1]).toEqual({
      operation_ids: ["op-delete"],
      force_stale: [],
      edits: { "op-delete": replacement },
    });
  });

  it("after a reload offers Apply as proposed, not a plain retry", async () => {
    Object.assign(proposal.operations[1], {
      status: "failed",
      stale: false,
      reason: "invalid_edit: predicate 'x' is not in the DR predicate catalog",
    });
    renderPage("op-delete");
    expect(await screen.findByTestId("operation-accept")).toHaveTextContent("Apply as proposed");
  });

  it("keeps the edit through Apply anyway; a cancel shows no old reason, a 422 reaches the editor", async () => {
    const user = userEvent.setup();
    useDrSpec();
    Object.assign(proposal.operations[1], {
      status: "failed",
      reason: "invalid_edit: an older refusal",
    });
    renderPage("op-delete");

    await replaceDelete(user);
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", { name: "Cancel" }),
    );
    expect(applied).toHaveLength(0);
    expect(screen.queryByTestId("operation-edit-server-error")).not.toBeInTheDocument();

    server.use(
      http.post("*/api/proposals/:id/apply", async ({ request }) => {
        applied.push((await request.json()) as Record<string, unknown>);
        return HttpResponse.json(
          { detail: "Edits for operations not being applied" },
          { status: 422 },
        );
      }),
    );
    await user.click(screen.getByRole("button", { name: "Apply replacement" }));
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", { name: "Apply anyway" }),
    );
    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0]).toEqual({
      operation_ids: ["op-delete"],
      force_stale: ["op-delete"],
      edits: { "op-delete": replacement },
    });
    expect(await screen.findByTestId("operation-edit-server-error")).toHaveTextContent(
      "Not applied: Edits for operations not being applied",
    );
  });
});

describe("stale operations", () => {
  beforeEach(() => {
    Object.assign(proposal.operations[1], {
      status: "failed",
      reason: "target_changed: description changed since proposed",
    });
  });

  it("needs Apply anyway, confirmed with what changed, then applies with force_stale", async () => {
    const user = userEvent.setup();
    renderPage("op-delete");

    expect(await screen.findByTestId("operation-stale-callout")).toHaveTextContent(
      "description changed since it was proposed. Applying it needs Apply anyway",
    );
    await user.click(screen.getByTestId("operation-accept"));
    expect(screen.getByTestId("operation-accept")).toHaveTextContent("Apply anyway");

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByTestId("proposal-force-message")).toHaveTextContent(
      "seq 2 Remove application_component realizes application_service: description changed since it was proposed.",
    );
    expect(applied).toHaveLength(0);
    await user.click(within(dialog).getByRole("button", { name: "Apply anyway" }));

    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0]).toEqual({
      operation_ids: ["op-delete"],
      force_stale: ["op-delete"],
      edits: {},
    });
  });

  it("applies nothing when the confirmation is cancelled", async () => {
    const user = userEvent.setup();
    renderPage("op-delete");
    await user.click(await screen.findByTestId("operation-accept"));
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", { name: "Cancel" }),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(applied).toHaveLength(0);
  });
});

describe("the probability threshold", () => {
  it("defaults to 0.60, mutes lower probabilities and selects the awaiting ones at or above", async () => {
    const user = userEvent.setup();
    renderPage();

    const bar = await screen.findByTestId("proposal-threshold-bar");
    expect(within(bar).getByTestId("proposal-threshold-value")).toHaveTextContent("0.60");
    // op-rename 0.82 and op-class 0.90; op-delete is stale (and 0.41).
    expect(within(bar).getByTestId("proposal-threshold-count")).toHaveTextContent(
      "2 of 3 awaiting at or above",
    );
    expect(screen.getByTestId("operation-probability-op-delete")).toHaveClass(
      "op-probability--below",
    );
    expect(screen.getByTestId("operation-probability-op-rename")).not.toHaveClass(
      "op-probability--below",
    );

    await user.click(within(bar).getByRole("button", { name: "Select 2" }));
    expect(screen.getByTestId("operation-check-op-rename")).toBeChecked();
    expect(screen.getByTestId("operation-check-op-class")).toBeChecked();
    expect(screen.getByTestId("operation-check-op-delete")).not.toBeChecked();
    expect(screen.getByTestId("proposal-selection-count")).toHaveTextContent("2 selected");
    // Selecting never applies.
    expect(applied).toHaveLength(0);
  });

  it("never selects a stale operation, however low the threshold", async () => {
    const user = userEvent.setup();
    renderPage();
    const slider = (await screen.findByTestId("proposal-threshold-slider")) as HTMLInputElement;
    // Range inputs take their value from a change event, not typing.
    fireEvent.change(slider, { target: { value: "0" } });
    expect(await screen.findByTestId("proposal-threshold-value")).toHaveTextContent("0.00");
    await user.click(screen.getByRole("button", { name: "Select 2" }));
    expect(screen.getByTestId("operation-check-op-delete")).not.toBeChecked();
    expect(screen.getByTestId("operation-probability-op-delete")).not.toHaveClass(
      "op-probability--below",
    );
  });

  it("is hidden when no operation has a probability", async () => {
    proposal.operations = proposal.operations.map((o) => ({ ...o, probability: null }));
    renderPage();
    await screen.findByTestId("operation-diff-op-rename");
    expect(screen.queryByTestId("proposal-threshold-bar")).not.toBeInTheDocument();
  });
});

describe("selection and the bulk bar", () => {
  it("accepts the checked operations, leaving stale ones for Apply anyway", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByTestId("operation-check-op-rename"));
    await user.click(screen.getByTestId("operation-check-op-delete"));
    const bar = screen.getByTestId("proposal-selection-bar");
    expect(within(bar).getByTestId("proposal-selection-count")).toHaveTextContent("2 selected");
    expect(bar).toHaveTextContent("1 stale: Accept selected leaves it for Apply anyway");
    // Decided operations can't be checked.
    expect(screen.getByTestId("operation-check-op-create")).toBeDisabled();

    await user.click(within(bar).getByTestId("proposal-selection-accept"));
    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0]).toEqual({ operation_ids: ["op-rename"], force_stale: [], edits: {} });
    await waitFor(() =>
      expect(screen.queryByTestId("proposal-selection-bar")).not.toBeInTheDocument(),
    );
  });

  it("rejects the checked operations, and Clear unchecks them", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByTestId("operation-check-op-rename"));
    await user.click(screen.getByTestId("proposal-selection-clear"));
    expect(screen.queryByTestId("proposal-selection-bar")).not.toBeInTheDocument();
    expect(screen.getByTestId("operation-check-op-rename")).not.toBeChecked();

    await user.click(screen.getByTestId("operation-check-op-rename"));
    await user.click(screen.getByTestId("operation-check-op-class"));
    await user.click(screen.getByTestId("proposal-selection-reject"));
    await waitFor(() => expect(rejected).toHaveLength(1));
    expect(rejected[0]).toEqual({ operation_ids: ["op-rename", "op-class"], note: null });
  });
});

describe("accept all and the results", () => {
  it("applies every fresh awaiting operation; a failure is warned about and retryable", async () => {
    const user = userEvent.setup();
    failures = { "op-class": "target_changed: description changed since proposed" };
    renderPage();

    await user.click(await screen.findByTestId("proposal-accept-all"));
    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0]).toEqual({
      operation_ids: ["op-rename", "op-class"],
      force_stale: [],
      edits: {},
    });

    const results = await screen.findByTestId("proposal-apply-results");
    expect(within(results).getByTestId("apply-results-warning")).toHaveTextContent(
      "Applied 1 of 2. Seq 4 failed and stays failed: retry, or reject.",
    );
    const tiles = within(results).getByTestId("apply-results-tally");
    const tile = (color: string) =>
      tiles.querySelector(`.stat-tile--${color} .stat-tile__value`)?.textContent;
    // The proposal's tally: op-create was already applied.
    expect([tile("emerald"), tile("rose"), tile("amber"), tile("neutral")]).toEqual([
      "2",
      "1",
      "1",
      "0",
    ]);
    expect(screen.getByTestId("apply-result-op-class")).toHaveTextContent(
      "target_changed: description changed since proposed",
    );

    failures = {};
    await user.click(screen.getByTestId("apply-retry-op-class"));
    await waitFor(() => expect(applied).toHaveLength(2));
    expect(applied[1]).toEqual({ operation_ids: ["op-class"], force_stale: [], edits: {} });
    // The retry joins the batch's outcomes instead of replacing them.
    expect(await screen.findByTestId("apply-results-ok")).toHaveTextContent("Applied 2 of 2.");
    expect(screen.getByTestId("apply-result-op-rename")).toHaveTextContent(
      "component_serves_service",
    );
  });

  it("confirms Reject all awaiting before rejecting every pending and failed operation", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByTestId("proposal-reject-all"));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("A rejected operation can't be applied later.");
    await user.click(within(dialog).getByRole("button", { name: "Reject 3" }));
    await waitFor(() => expect(rejected).toHaveLength(1));
    expect(rejected[0]).toEqual({
      operation_ids: ["op-rename", "op-delete", "op-class"],
      note: null,
    });
  });
});

describe("revert", () => {
  it("says what it undoes before reverting", async () => {
    const user = userEvent.setup();
    revertResponse = () => {
      proposal.status = "reverted";
      return HttpResponse.json({ events_reverted: 1, proposal });
    };
    renderPage();

    await user.click(await screen.findByTestId("proposal-revert"));
    expect(await screen.findByTestId("proposal-revert-message")).toHaveTextContent(
      "Undoes the 1 operation this proposal applied, in one transaction: 1 created removed. The 3 operations still awaiting a decision are rejected.",
    );
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Revert proposal" }),
    );

    // Reverted: read-only.
    await waitFor(() =>
      expect(screen.getByTestId("proposal-status")).toHaveTextContent("reverted"),
    );
    expect(screen.queryByTestId("proposal-actions")).not.toBeInTheDocument();
    expect(screen.queryByTestId("proposal-threshold-bar")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operation-check-op-rename")).not.toBeInTheDocument();
  });

  it("explains a refused (409) revert: nothing changed, what blocks it, what to do first", async () => {
    const user = userEvent.setup();
    revertResponse = () =>
      HttpResponse.json(
        {
          detail: {
            message:
              "Batch run proposal-1 can't be reverted: 1 entities outside it depend on entities it created",
            blocking: [{ kind: "individual", dependent_id: "ind-9", referenced_id: "prop-new" }],
          },
        },
        { status: 409 },
      );
    renderPage();

    await user.click(await screen.findByTestId("proposal-revert"));
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", { name: "Revert proposal" }),
    );

    const conflict = await screen.findByTestId("revert-conflict");
    expect(within(conflict).getByTestId("revert-conflict-message")).toHaveTextContent(
      "Can't revert DR reflection plan: application layer. 1 entity made after it depends on what it created. Nothing was changed.",
    );
    const blockers = within(conflict).getByTestId("revert-conflict-blockers");
    expect(within(blockers).getByRole("link", { name: "ind-9" })).toHaveAttribute(
      "href",
      "/app/data/individuals/ind-9",
    );
    expect(blockers).toHaveTextContent("individual ind-9");
    expect(blockers).toHaveTextContent("service_uses_component prop-new");
    expect(conflict).toHaveTextContent("Remove or retype those first");
    // Still open: nothing was reverted.
    expect(screen.getByTestId("proposal-status")).toHaveTextContent("open");

    await user.click(within(conflict).getByTestId("revert-conflict-dismiss"));
    expect(screen.queryByTestId("revert-conflict")).not.toBeInTheDocument();
  });
});

describe("export decisions", () => {
  it("downloads the decisions file for a dr_spec proposal", async () => {
    const user = userEvent.setup();
    const decisions = [{ seq: 1, op_id: "op-rename", status: "pending", reason: null }];
    server.use(http.get("*/api/proposals/:id/decisions", () => HttpResponse.json(decisions)));
    renderPage();

    await user.click(await screen.findByTestId("proposal-export-decisions"));
    await waitFor(() =>
      expect(downloadJson).toHaveBeenCalledWith("dr-decisions-proposal.json", decisions),
    );
  });

  it("is not offered outside dr_spec", async () => {
    server.use(
      http.get("*/api/taxonomies/:id", () =>
        HttpResponse.json({ ...taxonomy, identifier: "house" }),
      ),
    );
    renderPage();
    await screen.findByTestId("proposal-accept-all");
    await waitFor(() =>
      expect(screen.getByTestId("proposal-page")).toHaveTextContent("PROPOSAL · house"),
    );
    expect(screen.queryByTestId("proposal-export-decisions")).not.toBeInTheDocument();
  });
});
