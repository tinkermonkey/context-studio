/**
 * The header's one revert control, by landing state (#1668): the in-place revert
 * while unlanded, "Propose the reversal…" once landed. A reversal and the proposal
 * it undoes link each other in their strips, and the Proposals list says when a
 * reversal is under way.
 */
import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import { doneProposal, proposalHandlers } from "@/test/proposalFixtures";
import { createTaxonomy } from "@/api/services/__tests__/fixtures/ontology.fixtures";
import type { ChangeProposal } from "@/api/services/proposals";
import { useToasts } from "@/components/ui/Toast";
import { ProposalDetailPage } from "../ProposalDetailPage";
import { ProposalsListPage } from "../ProposalsListPage";
import { pendingReversal, reversalChips, revertOffer } from "../reversalModel";

const navigate = vi.fn();
vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual("@tanstack/react-router");
  return { ...actual, useNavigate: () => navigate };
});

const server = setupServer(...proposalHandlers, ...entityPageHandlers);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  navigate.mockReset();
});
afterAll(() => server.close());

const LANDED = { commit: "abc123", landed_at: "2026-11-20T10:00:00+00:00" };
const CREATED = "2026-11-21T10:00:00+00:00";

type Link = NonNullable<ChangeProposal["links"]>[number];

/** proposal-2 (done, one change applied), landed or not, with these links. */
function proposalWith(fields: Partial<ChangeProposal>): ChangeProposal {
  return { ...structuredClone(doneProposal), ...fields };
}

function reversedBy(status: Link["status"], applied?: number, total?: number): Link {
  return {
    kind: "reversed_by",
    proposal_id: "reversal-1",
    title: "Reversal of: Sharpen a definition",
    status,
    created_at: CREATED,
    operations_applied: applied ?? null,
    operations_total: total ?? null,
  };
}

const reverses: Link = {
  kind: "reverses",
  proposal_id: "proposal-2",
  title: "Sharpen a definition",
  status: "done",
  created_at: CREATED,
};

function serve(proposal: ChangeProposal) {
  server.use(http.get(`*/api/proposals/${proposal.id}`, () => HttpResponse.json(proposal)));
}

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

function renderPage(id = "proposal-2") {
  return render(
    <>
      <ProposalDetailPage id={id} onSelectOperation={vi.fn()} />
      <ToastProbe />
    </>,
  );
}

describe("the revert control", () => {
  it("offers the in-place revert while the proposal is unlanded", async () => {
    serve(proposalWith({ landed: null }));
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByTestId("proposal-revert"));

    expect(screen.queryByTestId("proposal-propose-reversal")).not.toBeInTheDocument();
    expect(screen.getByTestId("revert-proposal-dialog")).toBeInTheDocument();
    expect(screen.getByTestId("proposal-revert-message")).toHaveTextContent(
      "Undoes the 1 operation this proposal applied",
    );
  });

  it("proposes the reversal of a landed proposal and opens it", async () => {
    serve(proposalWith({ landed: LANDED }));
    const posted: string[] = [];
    server.use(
      http.post("*/api/proposals/:id/reversal", ({ params }) => {
        posted.push(String(params.id));
        return HttpResponse.json(
          proposalWith({ id: "reversal-1", status: "open", links: [reverses] }),
          { status: 201 },
        );
      }),
    );
    const user = userEvent.setup();
    renderPage();

    const control = await screen.findByTestId("proposal-propose-reversal");
    expect(control).toHaveTextContent("Propose the reversal…");
    expect(screen.queryByTestId("proposal-revert")).not.toBeInTheDocument();
    await user.click(control);

    const dialog = screen.getByTestId("propose-reversal-dialog");
    expect(dialog).toHaveTextContent("can't be undone here");
    expect(dialog).toHaveTextContent("reviewed, applied and landed like any proposal");
    expect(screen.getByTestId("propose-reversal-contents")).toHaveTextContent(
      "undo the change it applied, unless it is already undone",
    );
    await user.click(screen.getByRole("button", { name: "Propose the reversal" }));

    expect(await screen.findByTestId("toast-success")).toHaveTextContent("Reversal proposed");
    expect(posted).toEqual(["proposal-2"]);
    expect(navigate).toHaveBeenCalledWith({
      to: "/app/proposals/$proposalId",
      params: { proposalId: "reversal-1" },
    });
    expect(screen.queryByTestId("propose-reversal-dialog")).not.toBeInTheDocument();
  });

  it("says why a reversal was refused, and shows the reversal opened elsewhere", async () => {
    // Someone else proposed the reversal after this page loaded: the server refuses this one.
    let current = proposalWith({ landed: LANDED });
    server.use(
      http.get("*/api/proposals/proposal-2", () => HttpResponse.json(current)),
      http.post("*/api/proposals/:id/reversal", () => {
        current = { ...current, links: [reversedBy("open")] };
        return HttpResponse.json(
          { detail: "Change proposal proposal-2 already has an open reversal, reversal-1" },
          { status: 409 },
        );
      }),
    );
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByTestId("proposal-propose-reversal"));
    await user.click(screen.getByRole("button", { name: "Propose the reversal" }));

    expect(await screen.findByTestId("toast-error")).toHaveTextContent(
      "Couldn't propose the reversal | Change proposal proposal-2 already has an open reversal",
    );
    const strip = await screen.findByTestId("proposal-reversal-reversed_by");
    expect(within(strip).getByText("reversal open")).toBeInTheDocument();
    expect(screen.queryByTestId("proposal-propose-reversal")).not.toBeInTheDocument();
    expect(navigate).not.toHaveBeenCalled();
  });

  it("is hidden while a reversal is open, and the strip links to it", async () => {
    serve(proposalWith({ landed: LANDED, links: [reversedBy("open")] }));
    renderPage();

    const strip = await screen.findByTestId("proposal-reversal-reversed_by");
    expect(within(strip).getByText("reversal open")).toHaveClass("chip--amber");
    expect(within(strip).getByRole("link")).toHaveAttribute("href", "/app/proposals/reversal-1");
    expect(screen.queryByTestId("proposal-propose-reversal")).not.toBeInTheDocument();
    expect(screen.queryByTestId("proposal-revert")).not.toBeInTheDocument();
  });

  it("shows a reversed proposal's reversal and how many changes it undid", async () => {
    serve(proposalWith({ status: "reversed", landed: LANDED, links: [reversedBy("done", 1, 2)] }));
    renderPage();

    const strip = await screen.findByTestId("proposal-reversal-reversed_by");
    expect(screen.getByTestId("proposal-status")).toHaveTextContent("reversed");
    expect(within(strip).getByText("reversed by")).toBeInTheDocument();
    expect(within(strip).getByRole("link")).toHaveTextContent("Reversal of: Sharpen a definition");
    expect(screen.getByTestId("proposal-reversal-count")).toHaveTextContent(
      "1 of 2 changes reversed",
    );
    expect(screen.queryByTestId("proposal-propose-reversal")).not.toBeInTheDocument();
  });

  it("offers an unlanded reversal's in-place revert, never its reversal", async () => {
    serve(proposalWith({ id: "reversal-1", title: "Reversal", landed: null, links: [reverses] }));
    renderPage("reversal-1");

    expect(await screen.findByTestId("proposal-revert")).toHaveTextContent("Revert proposal");
    expect(screen.getByTestId("proposal-reversal-reverses")).toBeInTheDocument();
    expect(screen.queryByTestId("proposal-propose-reversal")).not.toBeInTheDocument();
  });

  it("links a landed reversal back to the original, and never offers to reverse it", async () => {
    serve(proposalWith({ id: "reversal-1", title: "Reversal", landed: LANDED, links: [reverses] }));
    renderPage("reversal-1");

    const strip = await screen.findByTestId("proposal-reversal-reverses");
    expect(within(strip).getByText("reverses")).toHaveClass("chip--cyan");
    expect(within(strip).getByRole("link")).toHaveAttribute("href", "/app/proposals/proposal-2");
    expect(screen.queryByTestId("proposal-propose-reversal")).not.toBeInTheDocument();
    expect(screen.queryByTestId("proposal-revert")).not.toBeInTheDocument();
  });
});

describe("the Proposals list", () => {
  /** The list with proposal-2, with these links, and proposal-1, with none. */
  function renderList(links: Link[]) {
    const plain = proposalWith({ id: "proposal-1", title: "Another", links: [] });
    server.use(
      http.get("*/api/taxonomies", () =>
        HttpResponse.json({
          items: [createTaxonomy({ id: "tax-2", identifier: "house" })],
          total: 1,
          limit: 500,
          offset: 0,
        }),
      ),
      http.get("*/api/proposals", () =>
        HttpResponse.json({
          items: [proposalWith({ landed: LANDED, links }), plain],
          total: 2,
          limit: 500,
          offset: 0,
        }),
      ),
    );
    render(<ProposalsListPage status="all" onFiltersChange={vi.fn()} />);
  }

  it("says a reversal is open on the proposal it undoes", async () => {
    renderList([reversedBy("open")]);

    const chip = await screen.findByTestId("proposals-list-reversal-proposal-2");
    expect(chip).toHaveTextContent("reversal open");
    expect(chip).toHaveClass("chip--amber");
    expect(screen.queryByTestId("proposals-list-reversal-proposal-1")).not.toBeInTheDocument();
  });

  it("says a decided reversal is not landed yet", async () => {
    renderList([reversedBy("done", 1, 1)]);

    expect(await screen.findByTestId("proposals-list-reversal-proposal-2")).toHaveTextContent(
      "reversal not landed",
    );
  });

  it("shows no chip for a withdrawn reversal", async () => {
    renderList([reversedBy("withdrawn")]);

    await screen.findByTestId("proposal-link-proposal-2");
    expect(screen.queryByTestId("proposals-list-reversal-proposal-2")).not.toBeInTheDocument();
  });
});

describe("reversalModel", () => {
  const landed = proposalWith({ landed: LANDED });

  it("offers by landing state, and nothing when nothing applied", () => {
    expect(revertOffer(proposalWith({ landed: null }))).toBe("revert");
    expect(revertOffer(landed)).toBe("reversal");
    const nothingApplied = proposalWith({
      landed: LANDED,
      operations: doneProposal.operations.map((o) => ({ ...o, status: "rejected" as const })),
    });
    expect(revertOffer(nothingApplied)).toBeUndefined();
    expect(revertOffer({ ...landed, status: "reversed" })).toBeUndefined();
  });

  it("keeps a decided but unlanded reversal under way", () => {
    const decided = { ...landed, links: [reversedBy("done", 1, 1)] };
    expect(pendingReversal(decided)?.proposal_id).toBe("reversal-1");
    expect(revertOffer(decided)).toBeUndefined();
    expect(reversalChips(decided).map((c) => c.label)).toEqual(["reversal not landed"]);
  });

  it("lets a reversal whose changes were all rejected be proposed again", () => {
    const rejected = { ...landed, links: [reversedBy("done", 0, 2)] };
    expect(pendingReversal(rejected)).toBeUndefined();
    expect(revertOffer(rejected)).toBe("reversal");
    expect(reversalChips(rejected)).toMatchObject([
      { label: "reversal rejected", variant: "neutral" },
    ]);
  });

  it("offers a reversal only its in-place revert, while unlanded", () => {
    const reversal = proposalWith({ id: "reversal-1", links: [reverses] });
    expect(revertOffer({ ...reversal, landed: null })).toBe("revert");
    expect(revertOffer({ ...reversal, landed: LANDED })).toBeUndefined();
  });

  it("lets a withdrawn reversal be proposed again", () => {
    const withdrawn = { ...landed, links: [reversedBy("withdrawn")] };
    expect(pendingReversal(withdrawn)).toBeUndefined();
    expect(revertOffer(withdrawn)).toBe("reversal");
    expect(reversalChips(withdrawn).map((c) => c.label)).toEqual(["reversal withdrawn"]);
  });
});
