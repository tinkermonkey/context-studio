import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
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
  useNavigatorStore.setState({ expandedIds: new Set(), mode: "schema" });
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

  it("hides counts on every row while filtering", async () => {
    const user = userEvent.setup();
    render(<EntityNavigator />);
    expect(await screen.findByText("1 scheme")).toBeInTheDocument();

    await user.type(screen.getByTestId("navigator-filter"), "service");

    await screen.findByTestId("hierarchy-node-class-2");
    expect(screen.queryByText("1 scheme")).not.toBeInTheDocument();
    expect(screen.queryByText(/\d+ class(es)?$/)).not.toBeInTheDocument();
  });
});

describe("EntityNavigator — Data mode", () => {
  it("switches mode from the header toggle and counts individuals", async () => {
    const user = userEvent.setup();
    render(<EntityNavigator expandIds={["tax-1", "scheme-1"]} />);
    const toggle = screen.getByTestId("navigator-mode");
    expect(within(toggle).getByRole("radio", { name: "Schema" })).toHaveAttribute(
      "aria-checked",
      "true",
    );

    await user.click(within(toggle).getByRole("radio", { name: "Data" }));

    expect(screen.getByText("Counts show individuals.")).toBeInTheDocument();
    // Taxonomy and scheme rows count individuals (scheme counts), classes too (class counts).
    expect(await screen.findAllByText("2 individuals")).toHaveLength(2);
    expect(await screen.findAllByText("1 individual")).toHaveLength(2);
  });

  it("keeps Data mode on pages that don't set one, and resets where they do", async () => {
    const dataRadio = () =>
      within(screen.getByTestId("navigator-mode")).getByRole("radio", { name: "Data" });
    const first = render(<EntityNavigator defaultMode="data" />);
    expect(dataRadio()).toHaveAttribute("aria-checked", "true");
    first.unmount();

    // An entity page (no defaultMode) keeps the mode the user was in.
    const second = render(<EntityNavigator />);
    expect(dataRadio()).toHaveAttribute("aria-checked", "true");
    second.unmount();

    // A schema list page switches back to Schema.
    render(<EntityNavigator defaultMode="schema" />);
    expect(dataRadio()).toHaveAttribute("aria-checked", "false");
  });

  it("opens a class to show its individuals and opens an individual's page", async () => {
    const user = userEvent.setup();
    render(<EntityNavigator defaultMode="data" expandIds={["tax-1", "scheme-1", "class-1"]} />);

    const row = await screen.findByTestId("hierarchy-node-ind-1");
    expect(row).toHaveClass("hierarchy-row--individual");
    expect(screen.getByTestId("hierarchy-node-class-1")).toHaveAttribute("aria-expanded", "true");
    expect(screen.queryByTestId("hierarchy-node-ind-2")).not.toBeInTheDocument();

    await user.click(screen.getByTestId("hierarchy-node-class-2"));
    expect(await screen.findByTestId("hierarchy-node-ind-2")).toBeInTheDocument();
  });

  it("loads individuals a page at a time and keeps the selected one visible", async () => {
    const many = Array.from({ length: 23 }, (_, i) => ({
      id: `bulk-${String(i).padStart(2, "0")}`,
      title: `Bulk ${String(i).padStart(2, "0")}`,
      class_ids: ["class-1"],
      version: 1,
      status: "draft" as const,
    }));
    server.use(
      http.get("*/api/individuals", ({ request }) => {
        const url = new URL(request.url);
        const ids = url.searchParams.getAll("ids");
        const limit = Number(url.searchParams.get("limit") ?? 100);
        const items = ids.length ? many.filter((i) => ids.includes(i.id)) : many;
        return HttpResponse.json({
          items: items.slice(0, limit),
          total: items.length,
          limit,
          offset: 0,
        });
      }),
    );
    const user = userEvent.setup();
    render(
      <EntityNavigator
        defaultMode="data"
        selectedId="bulk-20"
        expandIds={["tax-1", "scheme-1", "class-1"]}
      />,
    );

    expect(await screen.findByTestId("hierarchy-node-bulk-09")).toBeInTheDocument();
    expect(screen.queryByTestId("hierarchy-node-bulk-10")).not.toBeInTheDocument();
    // The selected individual sits past the first page but is still shown.
    expect(await screen.findByTestId("hierarchy-node-bulk-20")).toHaveClass(
      "hierarchy-row--selected",
    );
    const more = screen.getByTestId("hierarchy-more-class-1");
    expect(more).toHaveTextContent("+ 13 more in ApplicationComponent");

    await user.click(more);

    expect(await screen.findByTestId("hierarchy-node-bulk-22")).toBeInTheDocument();
    expect(screen.queryByTestId("hierarchy-more-class-1")).not.toBeInTheDocument();
  });

  it("filters individuals with server search", async () => {
    const user = userEvent.setup();
    render(<EntityNavigator defaultMode="data" />);
    await screen.findByTestId("hierarchy-node-tax-1");

    await user.type(screen.getByTestId("navigator-filter"), "router");

    expect(await screen.findByTestId("hierarchy-node-ind-1")).toBeInTheDocument();
    expect(screen.getByTestId("hierarchy-node-class-1")).toHaveAttribute("aria-expanded", "true");
    expect(screen.queryByTestId("hierarchy-node-ind-2")).not.toBeInTheDocument();
    expect(screen.queryByText(/individuals?$/)).not.toBeInTheDocument();
  });
});
