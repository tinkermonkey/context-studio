/**
 * Relationship-type deletes blocked by relationships still using the type
 * (#1393): the Blocked chip, the relationships in the inspector, Move / Delete
 * them too / Keep the type, bulk accept skipping them, what apply results and
 * revert say.
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import { openProposal, proposalHandlers } from "@/test/proposalFixtures";
import type { ChangeProposal, ProposedOperation } from "@/api/services/proposals";
import { ProposalDetailPage } from "../ProposalDetailPage";

const server = setupServer(...proposalHandlers, ...entityPageHandlers);

type Body = {
  operation_ids: string[];
  resolutions?: Record<
    string,
    { strategy: "move" | "delete"; replacement_property_id?: string; relationship_ids: string[] }
  >;
};

let proposal: ChangeProposal;
let applied: Body[];
let rejected: Record<string, unknown>[];
/** When set, the next resolved apply fails with this reason and leaves these blockers. */
let resolutionFails: { reason: string; blockers: typeof blockers } | null;

const end = (id: string, title: string, classTitle: string) => ({
  id,
  title,
  class_ids: [`class-${classTitle}`],
  class_titles: [classTitle],
});

const blockers = {
  edges: [
    {
      relationship_id: "rel-1",
      source: end("ev-1", "Entity Changed Event", "BusinessEvent"),
      target: end("fn-1", "Entity Enrichment", "BusinessFunction"),
      attributes: {},
    },
    {
      relationship_id: "rel-2",
      source: end("ev-2", "Sync Completed Event", "BusinessEvent"),
      target: end("fn-2", "Conflict Resolution", "BusinessFunction"),
      attributes: {},
    },
  ],
  replacements: [] as {
    property_id: string;
    identifier: string;
    title: string;
    reversed: boolean;
  }[],
  move_unavailable_reason:
    "1 type accepts BusinessEvent sources (businessevent_triggers_businessprocess), but none accepts BusinessFunction targets",
};

function blocked(): ProposedOperation {
  return proposal.operations.find((o) => o.id === "op-delete")!;
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  proposal = structuredClone(openProposal);
  // The fixture's delete is stale; here it is fresh but in use.
  Object.assign(blocked(), { stale: false, probability: 0.9, blockers: structuredClone(blockers) });
  applied = [];
  rejected = [];
  resolutionFails = null;
  server.use(
    http.get("*/api/proposals/:id", () => HttpResponse.json(proposal)),
    http.post("*/api/proposals/:id/apply", async ({ request }) => {
      const body = (await request.json()) as Body;
      applied.push(body);
      for (const op of proposal.operations) {
        if (!body.operation_ids.includes(op.id)) continue;
        const resolution = body.resolutions?.[op.id];
        if (resolution && resolutionFails) {
          Object.assign(op, {
            status: "failed",
            reason: resolutionFails.reason,
            blockers: resolutionFails.blockers,
          });
          resolutionFails = null;
          continue;
        }
        if (op.blockers && !resolution) {
          Object.assign(op, {
            status: "failed",
            reason: "error: PropertyDefinition 'prop-1' is in use by 2 relationship(s)",
          });
          continue;
        }
        Object.assign(op, { status: "applied", reason: null, stale: false });
        if (resolution && op.blockers) {
          op.resolution = {
            strategy: resolution.strategy,
            reversed: false,
            replacement_property_id: resolution.replacement_property_id ?? null,
            replacement_identifier: resolution.replacement_property_id ? "relates_to" : null,
            edges: op.blockers.edges.map((e) => ({
              relationship_id: e.relationship_id,
              source_id: e.source.id,
              target_id: e.target.id,
              source_title: e.source.title,
              target_title: e.target.title,
              moved_to_id: resolution.replacement_property_id ? `${e.relationship_id}-moved` : null,
            })),
          };
          op.blockers = null;
        }
      }
      return HttpResponse.json(proposal);
    }),
    http.post("*/api/proposals/:id/reject", async ({ request }) => {
      const body = (await request.json()) as { operation_ids: string[]; note: string | null };
      rejected.push(body);
      for (const op of proposal.operations) {
        if (body.operation_ids.includes(op.id)) {
          Object.assign(op, { status: "rejected", reason: body.note, blockers: null });
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

describe("a blocked relationship-type delete", () => {
  it("is marked Blocked in the operation list; other operations are not", async () => {
    renderPage();

    const chip = await screen.findByTestId("operation-blocked-op-delete");
    expect(chip).toHaveTextContent("Blocked: in use by 2");
    expect(chip).toHaveClass("chip--amber");
    expect(screen.queryByTestId("operation-blocked-op-rename")).not.toBeInTheDocument();
  });

  it("lists the relationships using the type, with each end's classes, before apply", async () => {
    renderPage("op-delete");

    const resolver = await screen.findByTestId("operation-in-use");
    expect(within(resolver).getByTestId("operation-in-use-callout")).toHaveTextContent(
      "Blocked: 2 relationships still use this type",
    );
    const edges = within(resolver).getByRole("list", { name: "Relationships using this type" });
    expect(within(edges).getAllByRole("listitem")).toHaveLength(2);
    expect(within(resolver).getByTestId("operation-blocker-edge-rel-1")).toHaveTextContent(
      "Entity Changed Event (BusinessEvent)→Entity Enrichment (BusinessFunction)",
    );
    // No plain Accept: it would fail as in use.
    expect(screen.queryByTestId("operation-accept")).not.toBeInTheDocument();
    expect(screen.getByTestId("operation-reject")).toHaveTextContent("Keep the type (reject)");
  });

  it("offers no Move when no type fits, says why, and deletes them too on request", async () => {
    const user = userEvent.setup();
    renderPage("op-delete");

    const resolver = await screen.findByTestId("operation-in-use");
    expect(within(resolver).getByRole("radio", { name: "Move them" })).toBeDisabled();
    expect(within(resolver).getByTestId("operation-move-unavailable")).toHaveTextContent(
      "Move isn't available: 1 type accepts BusinessEvent sources (businessevent_triggers_businessprocess), but none accepts BusinessFunction targets.",
    );
    expect(
      within(resolver).queryByTestId("operation-resolution-replacement"),
    ).not.toBeInTheDocument();

    const apply = within(resolver).getByTestId("operation-resolution-apply");
    expect(apply).toHaveTextContent("Apply: delete 2 relationships and the type");
    await user.click(apply);

    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0]).toEqual({
      operation_ids: ["op-delete"],
      force_stale: [],
      edits: {},
      resolutions: { "op-delete": { strategy: "delete", relationship_ids: ["rel-1", "rel-2"] } },
    });
    const results = await screen.findByTestId("proposal-apply-results");
    expect(within(results).getByTestId("apply-result-op-delete")).toHaveTextContent(
      "deleted 2 relationships and the type",
    );
    const listed = within(results).getByRole("list", { name: "Relationships deleted" });
    expect(listed).toHaveTextContent("Entity Changed Event → Entity Enrichment");
    expect(within(results).getByTestId("apply-results-ok")).toHaveTextContent(
      "puts the relationships it moved or deleted back on their type",
    );
  });

  it("moves them to a type that fits every one, the button naming it", async () => {
    blocked().blockers!.replacements = [
      {
        property_id: "prop-relates",
        identifier: "relates_to",
        title: "relates to",
        reversed: false,
      },
    ];
    blocked().blockers!.move_unavailable_reason = null;
    const user = userEvent.setup();
    renderPage("op-delete");

    const resolver = await screen.findByTestId("operation-in-use");
    expect(within(resolver).getByRole("radio", { name: "Move them" })).toBeChecked();
    expect(within(resolver).getByTestId("operation-resolution-replacement")).toBeInTheDocument();
    expect(within(resolver).queryByTestId("operation-move-unavailable")).not.toBeInTheDocument();
    expect(within(resolver).getByTestId("operation-blocker-edge-rel-2")).toHaveTextContent(
      "fits relates_to",
    );
    await user.click(within(resolver).getByTestId("operation-resolution-apply"));

    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0].resolutions).toEqual({
      "op-delete": {
        strategy: "move",
        replacement_property_id: "prop-relates",
        relationship_ids: ["rel-1", "rel-2"],
      },
    });
    expect(await screen.findByTestId("apply-result-op-delete")).toHaveTextContent(
      "moved 2 relationships to relates_to, removed the type",
    );
  });

  it("the move button names its scope", async () => {
    blocked().blockers!.replacements = [
      {
        property_id: "prop-relates",
        identifier: "relates_to",
        title: "relates to",
        reversed: false,
      },
    ];
    renderPage("op-delete");

    expect(await screen.findByTestId("operation-resolution-apply")).toHaveTextContent(
      "Apply: move 2 relationships to relates_to and delete the type",
    );
  });

  it("keeps the type by rejecting, with the reason", async () => {
    const user = userEvent.setup();
    renderPage("op-delete");

    await user.type(await screen.findByTestId("operation-reject-note"), "Both events need it");
    await user.click(screen.getByTestId("operation-reject"));

    await waitFor(() => expect(rejected).toHaveLength(1));
    expect(rejected[0]).toEqual({ operation_ids: ["op-delete"], note: "Both events need it" });
    expect(applied).toHaveLength(0);
  });
});

describe("a failed resolution", () => {
  it("a plain in-use failure shows only the Blocked callout, not a repeat of it", async () => {
    Object.assign(blocked(), {
      status: "failed",
      reason: "error: PropertyDefinition 'prop-1' is in use by 2 relationship(s)",
    });
    renderPage("op-delete");

    expect(await screen.findByTestId("operation-in-use-callout")).toBeInTheDocument();
    expect(screen.queryByTestId("operation-resolution-failed")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operation-failed-callout")).not.toBeInTheDocument();
  });

  it("shows why it failed, and falls back to Delete when its type no longer fits", async () => {
    blocked().blockers!.replacements = [
      {
        property_id: "prop-relates",
        identifier: "relates_to",
        title: "relates to",
        reversed: false,
      },
    ];
    blocked().blockers!.move_unavailable_reason = null;
    resolutionFails = {
      reason: "unresolvable: 2 of 2 relationship(s) don't fit relates_to",
      blockers: structuredClone(blockers),
    };
    const user = userEvent.setup();
    renderPage("op-delete");

    expect(screen.queryByTestId("operation-resolution-failed")).not.toBeInTheDocument();
    await user.click(await screen.findByTestId("operation-resolution-apply"));

    const failure = await screen.findByTestId("operation-resolution-failed");
    expect(failure).toHaveTextContent(
      "The last apply failed: unresolvable: 2 of 2 relationship(s) don't fit relates_to",
    );
    // relates_to is no longer offered: Move falls back to Delete them too.
    const resolver = screen.getByTestId("operation-in-use");
    await waitFor(() =>
      expect(within(resolver).getByRole("radio", { name: "Move them" })).toBeDisabled(),
    );
    expect(within(resolver).getByRole("radio", { name: "Delete them too" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(within(resolver).getByTestId("operation-resolution-apply")).toHaveTextContent(
      "Apply: delete 2 relationships and the type",
    );
  });
});

describe("bulk decisions skip blocked deletes", () => {
  it("a delete whose relationships the proposal deletes too is not blocked", async () => {
    blocked().blockers = null;
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByTestId("proposal-accept-all"));

    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0].operation_ids).toEqual(["op-rename", "op-delete", "op-class"]);
    expect(screen.queryByTestId("operation-blocked-op-delete")).not.toBeInTheDocument();
  });

  it("Accept all awaiting leaves the blocked delete and says so", async () => {
    const user = userEvent.setup();
    renderPage();

    const acceptAll = await screen.findByTestId("proposal-accept-all");
    expect(acceptAll).toHaveAttribute(
      "title",
      "Blocked deletes are left for a resolution in the inspector",
    );
    await user.click(acceptAll);

    await waitFor(() => expect(applied).toHaveLength(1));
    expect(applied[0].operation_ids).toEqual(["op-rename", "op-class"]);
    expect(blocked().status).toBe("pending");
  });

  it("the selection bar says Accept selected skips it", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByTestId("operation-check-op-delete"));

    expect(screen.getByTestId("proposal-selection-note")).toHaveTextContent(
      "1 blocked (in use): Accept selected skips it; resolve it in the inspector.",
    );
    expect(screen.getByTestId("proposal-selection-accept")).toBeDisabled();
  });

  it("the threshold never selects it", async () => {
    renderPage();

    // op-rename (0.819) and op-class (0.9) qualify; the blocked delete (0.9) does not.
    expect(await screen.findByTestId("proposal-threshold-count")).toHaveTextContent(
      "2 of 3 awaiting at or above",
    );
  });
});

describe("revert after a resolved delete", () => {
  it("says it restores the relationships with the type", async () => {
    Object.assign(blocked(), {
      status: "applied",
      blockers: null,
      resolution: {
        strategy: "delete",
        replacement_property_id: null,
        replacement_identifier: null,
        edges: blockers.edges.map((e) => ({
          relationship_id: e.relationship_id,
          source_id: e.source.id,
          target_id: e.target.id,
          source_title: e.source.title,
          target_title: e.target.title,
        })),
      },
    });
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByTestId("proposal-revert"));

    expect(await screen.findByTestId("proposal-revert-message")).toHaveTextContent(
      "1 deleted restored, the 2 relationships moved or deleted with a type restored on it",
    );
  });
});
