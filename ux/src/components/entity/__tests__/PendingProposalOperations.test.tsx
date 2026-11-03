import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { setupServer } from "msw/node";
import { QUERY_KEYS } from "@/api/config";
import { createTestQueryClient, render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import { proposalHandlers } from "@/test/proposalFixtures";
import { ClassPage } from "@/routes/app/schema/classes_.$id";
import { PendingProposalOperations } from "../PendingProposalOperations";

const navigate = vi.fn();
vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual("@tanstack/react-router");
  return { ...actual, useNavigate: () => navigate };
});

const OPEN = { status: "open", limit: 500 };
const server = setupServer(...proposalHandlers, ...entityPageHandlers);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  navigate.mockReset();
});
afterAll(() => server.close());

function linkIds() {
  return screen
    .getAllByTestId(/^pending-operation-link-/)
    .map((a) => a.getAttribute("data-testid")?.replace("pending-operation-link-", ""));
}

describe("PendingProposalOperations", () => {
  it("lists a class's pending operations, including a property update that keeps its ends", async () => {
    render(<PendingProposalOperations kind="class" entityId="class-1" />);

    const callout = await screen.findByTestId("pending-operations-callout");
    // The rename's base has no ends; the current prop-1 (domain class-1) supplies them.
    expect(
      await screen.findByText("3 pending operations in 1 proposal would change this class."),
    ).toBeInTheDocument();
    expect(callout).toHaveAttribute("role", "note");
    expect(linkIds()).toEqual(["op-rename", "op-delete", "op-class"]);
  });

  it("links each operation to its proposal page with the operation selected", async () => {
    const user = userEvent.setup();
    render(<PendingProposalOperations kind="property" entityId="prop-1" />);

    const link = await screen.findByTestId("pending-operation-link-op-rename");
    expect(link).toHaveAttribute("href", "/app/proposals/proposal-1?op=op-rename");
    expect(link).toHaveClass("entity-link");
    expect(linkIds()).toEqual(["op-rename", "op-delete"]);
    const row = link.closest("tr") as HTMLElement;
    expect(within(row).getByText(/seq 1 · update/)).toHaveClass("pending-ops__where");
    expect(within(row).getByText("0.82")).toHaveClass("op-probability");

    await user.click(link);
    expect(navigate).toHaveBeenCalledWith({
      to: "/app/proposals/$proposalId",
      params: { proposalId: "proposal-1" },
      search: { op: "op-rename" },
    });
  });

  it("lists every pending operation of a proposal about the taxonomy", async () => {
    render(<PendingProposalOperations kind="taxonomy" entityId="tax-1" />);
    expect(
      await screen.findByText("3 pending operations in 1 proposal would change this taxonomy."),
    ).toBeInTheDocument();
    // The applied create is not pending.
    expect(screen.queryByTestId("pending-operation-link-op-create")).not.toBeInTheDocument();
  });

  it("renders nothing when no pending operation touches the entity", async () => {
    const queryClient = createTestQueryClient();
    render(<PendingProposalOperations kind="class" entityId="class-9" />, { queryClient });
    // Let the open-proposals query load before asserting absence.
    await waitFor(() =>
      expect(queryClient.getQueryState(QUERY_KEYS.changeProposals(OPEN))?.status).toBe("success"),
    );
    expect(screen.queryByTestId("pending-operations")).not.toBeInTheDocument();
  });

  it("appears on the class page", async () => {
    render(<ClassPage id="class-1" />);
    expect(await screen.findByTestId("pending-operations")).toBeInTheDocument();
    expect(await screen.findByTestId("pending-operation-link-op-class")).toBeInTheDocument();
  });
});
