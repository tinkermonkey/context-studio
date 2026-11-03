import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createOperation,
  deleteOperation,
  openProposal,
  proposalHandlers,
  renameOperation,
} from "@/test/proposalFixtures";
import { createTaxonomy } from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { ProposalsListPage } from "../ProposalsListPage";

const navigate = vi.fn();
vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual("@tanstack/react-router");
  return { ...actual, useNavigate: () => navigate };
});

const server = setupServer(
  ...proposalHandlers,
  http.get("*/api/taxonomies", () =>
    HttpResponse.json({
      items: [
        createTaxonomy({ id: "tax-1", identifier: "dr_spec" }),
        createTaxonomy({ id: "tax-2", identifier: "house" }),
      ],
      total: 2,
      limit: 500,
      offset: 0,
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  navigate.mockReset();
});
afterAll(() => server.close());

describe("ProposalsListPage", () => {
  it("lists open proposals with taxonomy, source, status, pending, scope and age", async () => {
    render(<ProposalsListPage status="open" onFiltersChange={vi.fn()} />);

    const link = await screen.findByTestId("proposal-link-proposal-1");
    expect(link).toHaveTextContent("DR reflection plan: application layer");
    expect(link).toHaveAttribute("href", "/app/proposals/proposal-1");
    expect(link).toHaveClass("entity-link");
    expect(screen.queryByTestId("proposal-link-proposal-2")).not.toBeInTheDocument();

    const row = link.closest("tr") as HTMLElement;
    expect(within(row).getByText("documentation_robotics proposal-export.ts")).toHaveClass(
      "proposal-cell__detail",
    );
    expect(await within(row).findByText("dr_spec")).toBeInTheDocument();
    expect(within(row).getByText("pipeline")).toHaveClass("chip--violet");
    expect(within(row).getByText("open")).toHaveClass("chip--amber");
    expect(within(row).getByText("breaking")).toHaveClass("chip--rose");
    expect(within(row).getByText("6d")).toHaveClass("proposal-age");

    const pending = screen.getByTestId("proposal-pending-proposal-1");
    expect(pending).toHaveTextContent("3 of 4 · 1 applied");
    expect(within(pending).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "25");

    expect(screen.getByTestId("proposals-count")).toHaveTextContent("1 of 1 proposals");
    expect(screen.getByTestId("proposals-table")).toHaveClass("schema-table-wrap");
  });

  it("counts failed operations as still awaiting a decision", async () => {
    server.use(
      http.get("*/api/proposals", () =>
        HttpResponse.json({
          items: [
            {
              ...openProposal,
              operations: [
                renameOperation,
                { ...deleteOperation, status: "failed", reason: "target_not_found: gone" },
                createOperation,
              ],
            },
          ],
          total: 1,
          limit: 500,
          offset: 0,
        }),
      ),
    );
    render(<ProposalsListPage status="open" onFiltersChange={vi.fn()} />);

    const pending = await screen.findByTestId("proposal-pending-proposal-1");
    expect(pending).toHaveTextContent("2 of 3 · 1 applied · 1 failed");
    expect(within(pending).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "33");
  });

  it("opens a proposal when its row is clicked", async () => {
    const user = userEvent.setup();
    render(<ProposalsListPage status="open" onFiltersChange={vi.fn()} />);

    const link = await screen.findByTestId("proposal-link-proposal-1");
    await user.click(within(link.closest("tr") as HTMLElement).getByText("6d"));
    expect(navigate).toHaveBeenCalledWith({
      to: "/app/proposals/$proposalId",
      params: { proposalId: "proposal-1" },
    });
  });

  it("reports filter changes for status and taxonomy", async () => {
    const onFiltersChange = vi.fn();
    const user = userEvent.setup();
    render(<ProposalsListPage status="all" onFiltersChange={onFiltersChange} />);
    await screen.findByTestId("proposal-link-proposal-2");

    const status = screen.getByTestId("proposals-status-filter");
    expect(status).toHaveAttribute("aria-label", "Status");
    expect(within(status).getByRole("radio", { name: "All" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await user.click(within(status).getByRole("radio", { name: "Done" }));
    expect(onFiltersChange).toHaveBeenLastCalledWith({ status: "done", taxonomyId: undefined });

    const taxonomy = screen.getByTestId("proposals-taxonomy-filter");
    await user.click(await within(taxonomy).findByRole("radio", { name: "house" }));
    expect(onFiltersChange).toHaveBeenLastCalledWith({ status: "all", taxonomyId: "tax-2" });
  });

  it("filters by taxonomy in the browser and says when nothing matches", async () => {
    const { rerender } = render(
      <ProposalsListPage status="all" taxonomyId="tax-2" onFiltersChange={vi.fn()} />,
    );
    expect(await screen.findByTestId("proposal-link-proposal-2")).toBeInTheDocument();
    expect(screen.queryByTestId("proposal-link-proposal-1")).not.toBeInTheDocument();
    expect(screen.getByTestId("proposals-count")).toHaveTextContent("1 of 2 proposals");

    rerender(<ProposalsListPage status="reverted" onFiltersChange={vi.fn()} />);
    expect(await screen.findByText("No proposals match these filters.")).toBeInTheDocument();
  });

  it("shows an error banner when the list fails", async () => {
    server.use(
      http.get("*/api/proposals", () => HttpResponse.json({ detail: "boom" }, { status: 500 })),
    );
    render(<ProposalsListPage status="open" onFiltersChange={vi.fn()} />);
    expect(await screen.findByText("Failed to load proposals")).toBeInTheDocument();
  });
});
