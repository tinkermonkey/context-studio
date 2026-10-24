import { describe, it, expect, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { createGraphView } from "@/api/services/__tests__/fixtures/graph.fixtures";
import { GraphLayerToolbar } from "../GraphLayerToolbar";
import { FORCE_LAYOUT_MAX_NODES, type GraphFilter } from "../graphLayers";

// Use the real Heimdall FilterDropdown / SegmentedControl so ARIA roles are the shipped ones
// (vitest.setup.ts mocks the package globally).
vi.mock("@tinkermonkey/heimdall-ui", async () => vi.importActual("@tinkermonkey/heimdall-ui"));

const view = createGraphView();
const baseFilter: GraphFilter = {
  layerIds: ["layer-business", "layer-api"],
  classIds: [],
  nodeKind: "all",
};

function renderToolbar(overrides: Partial<Parameters<typeof GraphLayerToolbar>[0]> = {}) {
  const props = {
    view,
    filter: baseFilter,
    onFilterChange: vi.fn(),
    layout: "layered" as const,
    onLayoutChange: vi.fn(),
    focus: null,
    onFocusDepthChange: vi.fn(),
    onExitFocus: vi.fn(),
    visibleNodeCount: 4,
    visibleEdgeCount: 3,
    ...overrides,
  };
  render(<GraphLayerToolbar {...props} />);
  return props;
}

describe("GraphLayerToolbar", () => {
  it("renders a labelled toolbar with data-testid and visible counts", () => {
    renderToolbar();
    const toolbar = screen.getByTestId("graph-layer-toolbar");
    expect(toolbar).toHaveAttribute("role", "toolbar");
    expect(toolbar).toHaveAttribute("aria-label", "Graph filters");
    expect(toolbar).toHaveClass("graph-layer-toolbar");
    const counts = screen.getByTestId("graph-visible-counts");
    expect(counts).toHaveAttribute("role", "status");
    expect(counts).toHaveTextContent("4 nodes · 3 edges");
  });

  it("summarizes the layer selection on the trigger", () => {
    renderToolbar();
    const trigger = screen.getByTestId("graph-layer-filter");
    expect(trigger).toHaveTextContent("2 selected");
    expect(trigger).toHaveAttribute("aria-haspopup", "listbox");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("groups layers by taxonomy and emits the new selection", async () => {
    const user = userEvent.setup();
    const props = renderToolbar();
    await user.click(screen.getByTestId("graph-layer-filter"));
    const panel = screen.getByTestId("graph-layer-filter-panel");
    expect(panel).toHaveAttribute("role", "listbox");
    expect(panel).toHaveAttribute("aria-multiselectable", "true");
    expect(within(panel).getByText("DOCUMENTATION ROBOTICS")).toBeInTheDocument();
    expect(within(panel).getByText("SIDE TAXONOMY")).toBeInTheDocument();

    const motivation = within(panel).getByRole("option", { name: /Motivation Layer/ });
    expect(motivation).toHaveAttribute("aria-selected", "false");
    await user.click(motivation);
    expect(props.onFilterChange).toHaveBeenCalledWith({
      ...baseFilter,
      layerIds: expect.arrayContaining(["layer-business", "layer-api", "layer-motivation"]),
    });
  });

  it("drops class restrictions outside the new layer selection", async () => {
    const user = userEvent.setup();
    const props = renderToolbar({ filter: { ...baseFilter, classIds: ["svc", "op"] } });
    await user.click(screen.getByTestId("graph-layer-filter"));
    const panel = screen.getByTestId("graph-layer-filter-panel");
    await user.click(within(panel).getByRole("option", { name: /API Layer/ }));
    expect(props.onFilterChange).toHaveBeenCalledWith({
      ...baseFilter,
      layerIds: ["layer-business"],
      classIds: ["svc"],
    });
  });

  it("offers only classes from the selected layers in the class filter", async () => {
    const user = userEvent.setup();
    renderToolbar();
    expect(screen.getByTestId("graph-class-filter")).toHaveTextContent("All");
    await user.click(screen.getByTestId("graph-class-filter"));
    const panel = screen.getByTestId("graph-class-filter-panel");
    const options = within(panel)
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(options).toEqual(["Business Service", "Operation"]);
  });

  it("switches node kind through an accessible radio group", async () => {
    const user = userEvent.setup();
    const props = renderToolbar();
    const kind = screen.getByTestId("graph-node-kind-filter");
    expect(kind).toHaveAttribute("role", "radiogroup");
    expect(kind).toHaveAttribute("aria-label", "Node kind");
    expect(within(kind).getByRole("radio", { name: "All" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await user.click(within(kind).getByRole("radio", { name: "Individuals" }));
    expect(props.onFilterChange).toHaveBeenCalledWith({ ...baseFilter, nodeKind: "individual" });
  });

  it("switches layout and disables force layout for large graphs", async () => {
    const user = userEvent.setup();
    const props = renderToolbar();
    const layout = screen.getByTestId("graph-layout-toggle");
    expect(layout).toHaveAttribute("role", "radiogroup");
    await user.click(within(layout).getByRole("radio", { name: "Force" }));
    expect(props.onLayoutChange).toHaveBeenCalledWith("force");
  });

  it("disables the force option above the node limit", () => {
    renderToolbar({ visibleNodeCount: FORCE_LAYOUT_MAX_NODES + 1 });
    const layout = screen.getByTestId("graph-layout-toggle");
    expect(within(layout).getByRole("radio", { name: "Force" })).toBeDisabled();
  });

  describe("focus mode", () => {
    const focusProps = { focus: { nodeId: "svc", depth: 1 }, focusLabel: "Business Service" };

    it("replaces the layer filters with a focus bar", () => {
      renderToolbar(focusProps);
      const bar = screen.getByTestId("graph-focus-bar");
      expect(bar).toHaveAttribute("role", "group");
      expect(bar).toHaveAttribute("aria-label", "Focus mode");
      expect(bar).toHaveClass("graph-layer-toolbar__focus");
      expect(screen.getByTestId("graph-focus-label")).toHaveTextContent("Business Service");
      expect(screen.queryByTestId("graph-layer-filter")).not.toBeInTheDocument();
      expect(screen.queryByTestId("graph-class-filter")).not.toBeInTheDocument();
    });

    it("changes depth and exits focus", async () => {
      const user = userEvent.setup();
      const props = renderToolbar(focusProps);
      const depth = screen.getByTestId("graph-focus-depth");
      expect(depth).toHaveAttribute("role", "radiogroup");
      expect(within(depth).getByRole("radio", { name: "1 hop" })).toHaveAttribute(
        "aria-checked",
        "true",
      );
      await user.click(within(depth).getByRole("radio", { name: "3 hops" }));
      expect(props.onFocusDepthChange).toHaveBeenCalledWith(3);

      const exit = screen.getByTestId("graph-focus-exit");
      expect(exit).toHaveAttribute("aria-label", "Exit focus mode");
      await user.click(exit);
      expect(props.onExitFocus).toHaveBeenCalled();
    });
  });
});
