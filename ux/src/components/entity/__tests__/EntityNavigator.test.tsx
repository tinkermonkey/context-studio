import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import { useNavigatorStore } from "@/stores/navigator";
import { EntityNavigator } from "../EntityNavigator";

const server = setupServer(...entityPageHandlers);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  useNavigatorStore.setState({ expandedIds: new Set() });
});
afterAll(() => server.close());

describe("EntityNavigator", () => {
  it("is a labelled navigation landmark with a filter box", async () => {
    render(<EntityNavigator />);

    const nav = screen.getByRole("navigation", { name: "Navigator" });
    expect(nav).toHaveAttribute("data-testid", "entity-navigator");
    const filter = screen.getByRole("searchbox", { name: "Filter the tree" });
    expect(filter).toHaveAttribute("data-testid", "navigator-filter");
    expect(await screen.findByTestId("hierarchy-node-tax-1")).toHaveClass("hierarchy-row");
  });

  it("opens the current node's path and keeps it open on the next page", async () => {
    const { unmount } = render(
      <EntityNavigator selectedId="class-1" expandIds={["tax-1", "scheme-1"]} />,
    );

    expect(await screen.findByTestId("hierarchy-node-class-1")).toHaveClass(
      "hierarchy-row--selected",
    );
    expect(useNavigatorStore.getState().expandedIds).toEqual(new Set(["tax-1", "scheme-1"]));
    unmount();

    // A page with no current node (e.g. a schema list page) shows the same open rows.
    render(<EntityNavigator />);
    expect(await screen.findByTestId("hierarchy-node-class-2")).toBeInTheDocument();
  });

  it("collapses a row through the shared store", async () => {
    const user = userEvent.setup();
    render(<EntityNavigator selectedId="tax-1" expandIds={["tax-1"]} />);

    await user.click(await screen.findByTestId("hierarchy-node-tax-1"));

    expect(useNavigatorStore.getState().expandedIds.has("tax-1")).toBe(false);
    expect(screen.queryByTestId("hierarchy-node-scheme-1")).not.toBeInTheDocument();
  });

  it("filters to the branches that lead to matching classes", async () => {
    const user = userEvent.setup();
    render(<EntityNavigator />);
    await screen.findByTestId("hierarchy-node-tax-1");

    await user.type(screen.getByTestId("navigator-filter"), "service");

    expect(await screen.findByTestId("hierarchy-node-class-2")).toBeInTheDocument();
    expect(screen.getByTestId("hierarchy-node-scheme-1")).toHaveAttribute("aria-expanded", "true");
    expect(screen.queryByTestId("hierarchy-node-class-1")).not.toBeInTheDocument();
  });

  it("keeps a matching scheme even when none of its classes match", async () => {
    const user = userEvent.setup();
    render(<EntityNavigator />);
    await screen.findByTestId("hierarchy-node-tax-1");

    await user.type(screen.getByTestId("navigator-filter"), "application layer");

    expect(await screen.findByTestId("hierarchy-node-scheme-1")).toBeInTheDocument();
    expect(screen.getByTestId("hierarchy-node-tax-1")).toBeInTheDocument();
  });

  it("says when nothing matches and restores the tree when cleared", async () => {
    const user = userEvent.setup();
    render(<EntityNavigator />);
    await screen.findByTestId("hierarchy-node-tax-1");
    const filter = screen.getByTestId("navigator-filter");

    await user.type(filter, "zzz");
    await waitFor(() =>
      expect(screen.getByTestId("navigator-no-matches")).toHaveTextContent(
        "Nothing matches “zzz”.",
      ),
    );

    await user.clear(filter);
    await waitFor(() =>
      expect(screen.queryByTestId("navigator-no-matches")).not.toBeInTheDocument(),
    );
    expect(screen.getByTestId("hierarchy-node-tax-1")).toBeInTheDocument();
  });
});
