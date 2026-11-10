import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/api/utils/queryClient";
import * as graphHooks from "@/api/hooks/graph";
import type { GraphViewEdge, GraphViewNode } from "@/api/hooks/graph";
import { createGraphView } from "@/api/services/__tests__/fixtures/graph.fixtures";
import { GraphPage } from "../index";

const { mockToast, mockMutate } = vi.hoisted(() => ({ mockToast: vi.fn(), mockMutate: vi.fn() }));

vi.mock("@/api/hooks/graph");
vi.mock("@tinkermonkey/heimdall-ui", async () => vi.importActual("@tinkermonkey/heimdall-ui"));
vi.mock("@/components/ui/Toast", () => ({
  useToasts: () => ({ toast: mockToast }),
}));

// The dataset scope (the `dataset` URL parameter and the workspace's datasets), set per test.
const datasetScope = vi.hoisted(() => ({
  current: {
    datasets: [] as Array<{ id: string; taxonomy_id: string; title: string; identifier: string }>,
    selectedDatasetId: undefined as string | undefined,
    showSelector: false,
    setDataset: () => {},
  },
}));
vi.mock("@/hooks/useDatasetScope", () => ({ useDatasetScope: () => datasetScope.current }));

// The real canvas needs layout measurement; render nodes as plain buttons instead.
vi.mock("@/components/graph/GraphCanvas", () => ({
  GraphCanvasComponent: ({
    nodes,
    edges,
    layout,
    onNodeSelect,
    focusNodeId,
  }: {
    nodes: GraphViewNode[];
    edges: GraphViewEdge[];
    layout: string;
    onNodeSelect: (id: string) => void;
    focusNodeId?: string;
  }) => (
    <div
      data-testid="graph-canvas"
      role="region"
      aria-label="Graph visualization canvas"
      data-layout={layout}
      data-focus={focusNodeId ?? ""}
      data-edge-count={edges.length}
    >
      {nodes.map((n) => (
        <button key={n.id} type="button" onClick={() => onNodeSelect(n.id)}>
          node:{n.label}
        </button>
      ))}
    </div>
  ),
}));

function mockView(state: Partial<ReturnType<typeof graphHooks.useGraphView>>) {
  vi.mocked(graphHooks.useGraphView).mockReturnValue({
    data: undefined,
    isPending: false,
    error: null,
    refetch: vi.fn(),
    ...state,
  } as unknown as ReturnType<typeof graphHooks.useGraphView>);
}

function renderPage(props: { datasetId?: string } = {}) {
  return render(
    <QueryClientProvider client={queryClient}>
      <GraphPage {...props} />
    </QueryClientProvider>,
  );
}

const canvasNodeLabels = () =>
  within(screen.getByTestId("graph-canvas"))
    .queryAllByRole("button")
    .map((b) => b.textContent?.replace("node:", ""));

describe("Graph Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    datasetScope.current = {
      datasets: [],
      selectedDatasetId: undefined,
      showSelector: false,
      setDataset: () => {},
    };
    vi.mocked(graphHooks.useBuildGraph).mockReturnValue({
      mutate: mockMutate,
      isPending: false,
    } as unknown as ReturnType<typeof graphHooks.useBuildGraph>);
    vi.mocked(graphHooks.useGraphMetrics).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof graphHooks.useGraphMetrics>);
  });

  it("renders the page container and header", () => {
    mockView({ data: createGraphView() });
    renderPage();
    expect(screen.getByTestId("graph-page")).toHaveClass("graph-page");
    expect(screen.getByText("Graph Visualization")).toBeInTheDocument();
  });

  it("renders the skeleton shell while loading", () => {
    mockView({ isPending: true });
    renderPage();
    expect(screen.getByTestId("graph-shell")).toBeInTheDocument();
    expect(screen.queryByTestId("graph-layer-toolbar")).not.toBeInTheDocument();
  });

  it("renders the empty state when the ontology has no nodes", () => {
    mockView({ data: createGraphView({ nodes: [], edges: [] }) });
    renderPage();
    expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    expect(screen.queryByTestId("graph-canvas")).not.toBeInTheDocument();
  });

  it("renders the error banner when the view fails to load", () => {
    mockView({ error: new Error("boom") } as never);
    renderPage();
    expect(screen.getByText("Failed to load graph")).toBeInTheDocument();
    expect(screen.queryByTestId("graph-canvas")).not.toBeInTheDocument();
  });

  it("defaults to the first populated DR layers and individuals when individuals exist", () => {
    mockView({ data: createGraphView() });
    renderPage();
    // Motivation holds only classes, so the individual default skips it.
    expect(screen.getByTestId("graph-layer-filter")).toHaveTextContent("2 selected");
    expect(
      within(screen.getByTestId("graph-node-kind-filter")).getByRole("radio", {
        name: "Individuals",
      }),
    ).toHaveAttribute("aria-checked", "true");
    expect(canvasNodeLabels().sort()).toEqual(["Checkout", "POST /orders"]);
    expect(screen.getByTestId("graph-canvas")).toHaveAttribute("data-layout", "organic");
  });

  it("shows classes by default for a schema-only ontology", () => {
    const view = createGraphView();
    mockView({
      data: createGraphView({
        nodes: view.nodes.filter((n) => n.node_type === "class"),
      }),
    });
    renderPage();
    expect(canvasNodeLabels().sort()).toEqual(["Business Service", "Goal", "Operation", "Outcome"]);
  });

  it("selecting a node opens the node inspector tab with its details", async () => {
    const user = userEvent.setup();
    mockView({ data: createGraphView() });
    renderPage();
    await user.click(screen.getByRole("tab", { name: "Metrics" }));
    await user.click(screen.getByRole("button", { name: "node:Checkout" }));
    const inspector = screen.getByTestId("node-inspector");
    expect(within(inspector).getByText("Checkout service")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Node Inspector" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("focus mode shows the neighborhood across layers and exits back to the filter", async () => {
    const user = userEvent.setup();
    mockView({ data: createGraphView() });
    renderPage();
    await user.click(screen.getByRole("radio", { name: "All" }));
    await user.click(screen.getByRole("button", { name: "node:Business Service" }));
    await user.click(screen.getByTestId("node-inspector-focus-button"));

    expect(screen.getByTestId("graph-focus-label")).toHaveTextContent("Business Service");
    expect(screen.getByTestId("graph-canvas")).toHaveAttribute("data-focus", "svc");
    expect(canvasNodeLabels().sort()).toEqual(["Business Service", "Checkout", "Operation"]);

    await user.click(
      within(screen.getByTestId("graph-focus-depth")).getByRole("radio", { name: "2 hops" }),
    );
    expect(canvasNodeLabels()).toContain("POST /orders");

    await user.click(screen.getByTestId("graph-focus-exit"));
    expect(screen.queryByTestId("graph-focus-bar")).not.toBeInTheDocument();
    expect(screen.getByTestId("graph-layer-filter")).toBeInTheDocument();
  });

  it("clicking a relationship endpoint in the inspector re-focuses on it", async () => {
    const user = userEvent.setup();
    mockView({ data: createGraphView() });
    renderPage();
    await user.click(screen.getByRole("button", { name: "node:Checkout" }));
    const inspector = screen.getByTestId("node-inspector");
    await user.click(within(inspector).getByRole("button", { name: /POST \/orders/ }));
    expect(screen.getByTestId("graph-focus-label")).toHaveTextContent("POST /orders");
    expect(screen.getByTestId("graph-canvas")).toHaveAttribute("data-focus", "post-order");
  });

  it("rebuild button triggers a graph build", async () => {
    const user = userEvent.setup();
    mockView({ data: createGraphView() });
    renderPage();
    await user.click(screen.getByTestId("build-graph-button"));
    expect(mockMutate).toHaveBeenCalled();
  });

  describe("datasets", () => {
    const datasets = [
      { id: "ds-1", taxonomy_id: "tax-1", title: "Context Studio", identifier: "context-studio" },
      { id: "ds-2", taxonomy_id: "tax-1", title: "Sample", identifier: "sample" },
    ];

    it("shows no dataset selector while each taxonomy has one dataset", () => {
      mockView({ data: createGraphView() });
      renderPage();
      expect(screen.queryByTestId("graph-dataset-select")).not.toBeInTheDocument();
    });

    it("offers the selector in the header once a taxonomy has two datasets", () => {
      datasetScope.current = { ...datasetScope.current, datasets, showSelector: true };
      mockView({ data: createGraphView() });
      renderPage();

      const select = screen.getByTestId("graph-dataset-select");
      expect(select).toHaveClass("dataset-select");
      expect(within(select).getByRole("button", { name: "Dataset" })).toHaveAttribute(
        "aria-haspopup",
        "listbox",
      );
    });

    it("loads, rebuilds and measures the graph of the chosen dataset", async () => {
      const user = userEvent.setup();
      mockView({ data: createGraphView() });
      renderPage({ datasetId: "ds-2" });

      expect(graphHooks.useGraphView).toHaveBeenCalledWith("ds-2");
      expect(graphHooks.useBuildGraph).toHaveBeenCalledWith("ds-2");

      await user.click(screen.getByRole("tab", { name: "Metrics" }));
      expect(graphHooks.useGraphMetrics).toHaveBeenCalledWith(undefined, "ds-2");
    });

    it("runs SPARQL over the chosen dataset", async () => {
      const user = userEvent.setup();
      vi.mocked(graphHooks.useSparqlQuery).mockReturnValue({
        mutate: vi.fn(),
        isPending: false,
        isSuccess: false,
        error: null,
        data: undefined,
      } as unknown as ReturnType<typeof graphHooks.useSparqlQuery>);
      mockView({ data: createGraphView() });
      renderPage({ datasetId: "ds-2" });

      await user.click(screen.getByRole("tab", { name: "SPARQL Query" }));

      expect(screen.getByTestId("sparql-editor")).toBeInTheDocument();
      expect(graphHooks.useSparqlQuery).toHaveBeenCalledWith("ds-2");
    });

    it("shows all data when no dataset is chosen", () => {
      mockView({ data: createGraphView() });
      renderPage();
      expect(graphHooks.useGraphView).toHaveBeenCalledWith(undefined);
    });
  });
});
