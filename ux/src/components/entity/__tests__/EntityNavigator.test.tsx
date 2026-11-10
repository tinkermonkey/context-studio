import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import userEvent from "@testing-library/user-event";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { dataset, entityPageHandlers } from "@/test/entityPageHandlers";
import { createDataset } from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { useNavigatorStore } from "@/stores/navigator";
import { EntityNavigator, SCHEMA_LIST_MODE_LINKS } from "../EntityNavigator";

const mockNavigate = vi.hoisted(() => vi.fn());
// The URL's search params (the `dataset` parameter), set per test.
let mockSearch: { dataset?: string } = {};
vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual("@tanstack/react-router");
  return { ...actual, useNavigate: () => mockNavigate, useSearch: () => mockSearch };
});

const server = setupServer(...entityPageHandlers);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  mockNavigate.mockClear();
  mockSearch = {};
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

  it("highlights non-zero individual counts, and only in Data mode", async () => {
    const { unmount } = render(
      <EntityNavigator defaultMode="data" expandIds={["tax-1", "scheme-1"]} />,
    );

    expect((await screen.findAllByText("2 individuals"))[0].closest(".hierarchy-row")).toHaveClass(
      "hierarchy-row--has-individuals",
    );
    expect(screen.getByTestId("hierarchy-node-scheme-1")).toHaveClass(
      "hierarchy-row--scheme",
      "hierarchy-row--has-individuals",
    );
    unmount();

    render(<EntityNavigator defaultMode="schema" expandIds={["tax-1", "scheme-1"]} />);
    expect(await screen.findByTestId("hierarchy-node-scheme-1")).not.toHaveClass(
      "hierarchy-row--has-individuals",
    );
  });

  it("follows a page's mode link when the mode is switched there", async () => {
    const user = userEvent.setup();
    render(<EntityNavigator defaultMode="schema" modeLinks={SCHEMA_LIST_MODE_LINKS} />);

    await user.click(
      within(screen.getByTestId("navigator-mode")).getByRole("radio", { name: "Data" }),
    );

    expect(useNavigatorStore.getState().mode).toBe("data");
    expect(mockNavigate).toHaveBeenCalledWith({ to: "/app/data/individuals" });
  });

  it("switches mode in place on pages without mode links", async () => {
    const user = userEvent.setup();
    render(<EntityNavigator selectedId="class-1" />);

    await user.click(
      within(screen.getByTestId("navigator-mode")).getByRole("radio", { name: "Data" }),
    );

    expect(useNavigatorStore.getState().mode).toBe("data");
    expect(mockNavigate).not.toHaveBeenCalled();
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

  describe("datasets", () => {
    const second = createDataset({
      id: "ds-2",
      taxonomy_id: "tax-1",
      identifier: "second",
      title: "Second",
    });
    const twoDatasets = () =>
      server.use(http.get("*/api/datasets", () => HttpResponse.json([dataset, second])));

    it("shows no dataset selector when the taxonomy has one dataset", async () => {
      render(<EntityNavigator defaultMode="data" expandIds={["tax-1"]} />);

      expect(await screen.findByTestId("hierarchy-node-scheme-1")).toBeInTheDocument();
      expect(screen.queryByTestId("navigator-dataset-select")).not.toBeInTheDocument();
    });

    it("offers a dataset selector in Data mode once a taxonomy has two datasets", async () => {
      twoDatasets();
      const { unmount } = render(<EntityNavigator defaultMode="data" />);

      const select = await screen.findByTestId("navigator-dataset-select");
      expect(select).toHaveClass("dataset-select");
      expect(select).toHaveAccessibleName("Dataset");
      expect(within(select).getByRole("option", { name: "Second · second" })).toBeInTheDocument();
      unmount();

      render(<EntityNavigator defaultMode="schema" />);
      await screen.findByTestId("hierarchy-node-tax-1");
      expect(screen.queryByTestId("navigator-dataset-select")).not.toBeInTheDocument();
    });

    it("choosing a dataset puts it in the URL", async () => {
      twoDatasets();
      const user = userEvent.setup();
      render(<EntityNavigator defaultMode="data" />);

      const select = await screen.findByTestId("navigator-dataset-select");
      await user.selectOptions(select, "ds-2");

      expect(mockNavigate).toHaveBeenCalledWith(
        expect.objectContaining({ to: ".", replace: true }),
      );
      const { search } = mockNavigate.mock.calls[0][0];
      expect(search({ focus: "x" })).toEqual({ focus: "x", dataset: "ds-2" });
    });

    it("counts and lists only the chosen dataset's individuals", async () => {
      twoDatasets();
      mockSearch = { dataset: "ds-2" };
      const requested: URL[] = [];
      server.use(
        http.get("*/api/taxonomies/:id/scheme-counts", ({ request }) => {
          requested.push(new URL(request.url));
          return HttpResponse.json([
            {
              scheme_id: "scheme-1",
              class_count: 2,
              individual_count: 7,
              property_definition_count: 1,
            },
          ]);
        }),
        http.get("*/api/schemes/:id/class-counts", ({ request }) => {
          requested.push(new URL(request.url));
          return HttpResponse.json([]);
        }),
        http.get("*/api/individuals", ({ request }) => {
          requested.push(new URL(request.url));
          return HttpResponse.json({ items: [], total: 0, limit: 10, offset: 0 });
        }),
      );
      render(<EntityNavigator defaultMode="data" expandIds={["tax-1", "scheme-1", "class-1"]} />);

      expect(await screen.findAllByText("7 individuals")).toHaveLength(2);
      await waitFor(() => {
        const paths = requested.map((u) => u.pathname);
        expect(paths).toContain("/api/schemes/scheme-1/class-counts");
        expect(paths).toContain("/api/individuals");
      });
      for (const url of requested) {
        expect(url.searchParams.get("dataset_id")).toBe("ds-2");
      }
    });

    it("ignores a dataset the workspace does not have", async () => {
      mockSearch = { dataset: "ds-gone" };
      const requested: URL[] = [];
      server.use(
        http.get("*/api/taxonomies/:id/scheme-counts", ({ request }) => {
          requested.push(new URL(request.url));
          return HttpResponse.json([]);
        }),
      );
      render(<EntityNavigator defaultMode="data" />);

      await waitFor(() =>
        expect(requested.some((u) => !u.searchParams.has("dataset_id"))).toBe(true),
      );
    });
  });
});
