/**
 * Accept N ready while it runs and after: a busy banner, no second apply from
 * a double click, a toast that says what applied and what still needs a
 * decision (never as a failure), and a timed-out apply that refetches.
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import { openProposal, proposalHandlers } from "@/test/proposalFixtures";
import { ApiError } from "@/api/client/interceptors";
import { proposalsService, type ChangeProposal } from "@/api/services/proposals";
import { useToasts } from "@/components/ui/Toast";
import { ProposalDetailPage } from "../ProposalDetailPage";
import { bulkSummary } from "../useProposalActions";

const server = setupServer(...proposalHandlers, ...entityPageHandlers);

let proposal: ChangeProposal;
let applies: string[][];
let gets: number;
/** While set, applies wait for it to resolve. */
let hold: Promise<void> | null;

const blockers = {
  edges: [
    {
      relationship_id: "rel-1",
      source: {
        id: "ev-1",
        title: "Entity Changed Event",
        class_ids: ["c-1"],
        class_titles: ["BusinessEvent"],
      },
      target: {
        id: "fn-1",
        title: "Entity Enrichment",
        class_ids: ["c-2"],
        class_titles: ["BusinessFunction"],
      },
      attributes: {},
    },
  ],
  replacements: [],
  move_unavailable_reason: null,
};

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  proposal = structuredClone(openProposal);
  // The fixture's delete is stale; here it is fresh but in use, so it needs a decision.
  Object.assign(proposal.operations.find((o) => o.id === "op-delete")!, {
    stale: false,
    blockers: structuredClone(blockers),
  });
  applies = [];
  gets = 0;
  hold = null;
  server.use(
    http.get("*/api/proposals/:id", () => {
      gets += 1;
      return HttpResponse.json(proposal);
    }),
    http.post("*/api/proposals/:id/apply", async ({ request }) => {
      const body = (await request.json()) as { operation_ids: string[] };
      applies.push(body.operation_ids);
      if (hold) await hold;
      for (const op of proposal.operations) {
        if (body.operation_ids.includes(op.id)) Object.assign(op, { status: "applied" });
      }
      return HttpResponse.json(proposal);
    }),
  );
});
afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
});
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

function renderPage() {
  return render(
    <>
      <ProposalDetailPage id="proposal-1" onSelectOperation={vi.fn()} />
      <ToastProbe />
    </>,
  );
}

describe("Accept N ready while the apply runs", () => {
  it("shows a busy banner, disables the bulk buttons, and sends one apply for a double click", async () => {
    let release!: () => void;
    hold = new Promise((resolve) => (release = resolve));
    const user = userEvent.setup();
    renderPage();

    const accept = await screen.findByTestId("proposal-accept-all");
    expect(accept).toHaveTextContent("Accept 2 ready");
    await user.dblClick(accept);

    const busy = await screen.findByTestId("proposal-busy");
    expect(busy).toHaveAttribute("role", "status");
    expect(busy).toHaveTextContent("Applying 2 operations…");
    expect(screen.getByTestId("proposal-summary")).toHaveAttribute("aria-busy", "true");
    expect(accept).toHaveAttribute("aria-busy", "true");
    expect(accept).toBeDisabled();
    expect(screen.getByTestId("proposal-reject-all")).toBeDisabled();
    // Nothing is reported before the apply returns.
    expect(screen.queryByTestId("toast-info")).not.toBeInTheDocument();

    release();
    await waitFor(() => expect(screen.queryByTestId("proposal-busy")).not.toBeInTheDocument());
    expect(applies).toEqual([["op-rename", "op-class"]]);
    expect(screen.getByTestId("proposal-summary")).not.toHaveAttribute("aria-busy");
  });
});

describe("Accept N ready afterwards", () => {
  it("says what applied and what still needs a decision, never as an error", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByTestId("proposal-accept-all"));

    expect(await screen.findByTestId("toast-success")).toHaveTextContent(
      "Applied 2 | 1 still needs a decision (in use: choose move or drop in the inspector).",
    );
    expect(screen.queryByTestId("toast-error")).not.toBeInTheDocument();
    expect(screen.queryByText(/skipped/)).not.toBeInTheDocument();
  });

  it("says the apply is still running on a timeout, and refetches the proposal", async () => {
    vi.spyOn(proposalsService, "applyProposal").mockRejectedValue(
      new ApiError(
        "timeout of 300000ms exceeded",
        0,
        "timeout of 300000ms exceeded",
        undefined,
        "ECONNABORTED",
      ),
    );
    const user = userEvent.setup();
    renderPage();
    const accept = await screen.findByTestId("proposal-accept-all");
    const before = gets;
    await user.click(accept);

    expect(await screen.findByTestId("toast-warning")).toHaveTextContent(
      "Apply is taking longer than expected | The page stopped waiting after 5 minutes; the server may still be applying.",
    );
    expect(screen.queryByTestId("toast-error")).not.toBeInTheDocument();
    expect(screen.queryByTestId("toast-success")).not.toBeInTheDocument();
    await waitFor(() => expect(gets).toBeGreaterThan(before));
    expect(screen.getByTestId("proposal-accept-all")).toBeEnabled();
  });

  it("reports any other apply failure as an error", async () => {
    vi.spyOn(proposalsService, "applyProposal").mockRejectedValue(
      new ApiError("boom", 500, "Internal error"),
    );
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByTestId("proposal-accept-all"));

    expect(await screen.findByTestId("toast-error")).toHaveTextContent(
      "Apply failed | Internal error",
    );
  });
});

describe("bulkSummary", () => {
  const after = (statuses: Record<string, string>) =>
    ({
      ...openProposal,
      operations: openProposal.operations.map((o) => ({
        ...o,
        status: statuses[o.id] ?? o.status,
      })),
    }) as ChangeProposal;

  it("counts what applied and failed among the sent operations only", () => {
    expect(
      bulkSummary(
        ["op-rename", "op-class"],
        3,
        0,
        after({ "op-rename": "applied", "op-class": "failed" }),
      ),
    ).toEqual([
      "info",
      "Applied 1; 1 failed (see the results)",
      "3 still need a decision (in use: choose move or drop in the inspector).",
    ]);
  });

  it("names stale operations left for Apply anyway", () => {
    expect(bulkSummary(["op-rename"], 0, 2, after({ "op-rename": "applied" }))).toEqual([
      "success",
      "Applied 1",
      "2 stale operations left for Apply anyway.",
    ]);
  });

  it("says nothing applied when every operation was skipped", () => {
    expect(bulkSummary([], 1, 0, undefined)).toEqual([
      "info",
      "Nothing applied",
      "1 still needs a decision (in use: choose move or drop in the inspector).",
    ]);
  });
});
