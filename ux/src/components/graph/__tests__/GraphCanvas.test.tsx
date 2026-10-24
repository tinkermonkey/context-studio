import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import type { GraphNodeData, GraphEdgeData } from "@tinkermonkey/heimdall-ui";
import { createGraphView } from "@/api/services/__tests__/fixtures/graph.fixtures";
import { GraphCanvasComponent, truncateLabel } from "../GraphCanvas";
import { LAYER_HEADER_PREFIX } from "../graphLayers";

interface CapturedProps {
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  layout: string;
  selectedNodeId?: string;
  renderNode: (node: GraphNodeData, selected: boolean) => React.ReactNode;
}

const { captured } = vi.hoisted(() => ({ captured: { props: null as unknown } }));

// Replace the canvas (it needs layout measurement) with a stub that renders
// every node through the component's renderNode, keeping the real GraphNode.
vi.mock("@tinkermonkey/heimdall-ui", async () => {
  const actual = await vi.importActual<typeof import("@tinkermonkey/heimdall-ui")>(
    "@tinkermonkey/heimdall-ui",
  );
  return {
    ...actual,
    GraphCanvas: (props: CapturedProps) => {
      captured.props = props;
      return (
        <div className="heimdall-graph-canvas-stub">
          {props.nodes.map((node) => (
            <div key={node.id}>{props.renderNode(node, node.id === props.selectedNodeId)}</div>
          ))}
        </div>
      );
    },
  };
});

const lastProps = () => captured.props as CapturedProps;

describe("GraphCanvasComponent", () => {
  const view = createGraphView();
  const businessAndApi = view.nodes.filter(
    (n) => n.concept_scheme_id === "layer-business" || n.concept_scheme_id === "layer-api",
  );
  const businessAndApiIds = new Set(businessAndApi.map((n) => n.id));
  const edges = view.edges.filter(
    (e) => businessAndApiIds.has(e.source) && businessAndApiIds.has(e.target),
  );

  beforeEach(() => {
    captured.props = null;
  });

  const renderCanvas = (overrides: Partial<Parameters<typeof GraphCanvasComponent>[0]> = {}) =>
    render(
      <GraphCanvasComponent
        nodes={businessAndApi}
        edges={edges}
        layers={view.layers}
        layout="layered"
        onNodeSelect={vi.fn()}
        {...overrides}
      />,
    );

  it("renders the canvas region with data-testid and ARIA label", () => {
    renderCanvas();
    const canvas = screen.getByTestId("graph-canvas");
    expect(canvas).toHaveAttribute("role", "region");
    expect(canvas).toHaveAttribute("aria-label", "Graph visualization canvas");
    expect(canvas).toHaveClass("graph-canvas", "graph-canvas-shell");
    expect(canvas).toHaveAttribute("data-layout", "layered");
  });

  it("pins every node and adds one layer header per band in layered mode", () => {
    renderCanvas();
    const props = lastProps();
    expect(props.layout).toBe("manual");
    expect(props.nodes.every((n) => typeof n.x === "number" && typeof n.y === "number")).toBe(true);
    const headers = props.nodes.filter((n) => n.id.startsWith(LAYER_HEADER_PREFIX));
    expect(headers.map((h) => h.label)).toEqual(["Business Layer", "API Layer"]);
    expect(screen.getByTestId("graph-layer-header-layer-business")).toHaveClass(
      "graph-layer-header",
    );
  });

  it("uses Heimdall force layout without pinned coordinates or headers in force mode", () => {
    renderCanvas({ layout: "force" });
    const props = lastProps();
    expect(props.layout).toBe("force");
    expect(props.nodes.some((n) => n.x !== undefined)).toBe(false);
    expect(props.nodes.some((n) => n.id.startsWith(LAYER_HEADER_PREFIX))).toBe(false);
    expect(screen.getByTestId("graph-canvas")).toHaveAttribute("data-layout", "force");
  });

  it("colors nodes by layer index and badges classes vs individuals", () => {
    renderCanvas();
    const byId = new Map(lastProps().nodes.map((n) => [n.id, n]));
    // layer-business is index 1, layer-api index 2 in view.layers
    expect(byId.get("svc")?.domainColor).toBe("layer-1");
    expect(byId.get("op")?.domainColor).toBe("layer-2");
    expect(byId.get("svc")?.kind).toBe("C");
    expect(byId.get("checkout")?.kind).toBe("I");
  });

  it("renders individuals and classes with distinct CSS classes and button roles", () => {
    renderCanvas({ focusNodeId: "svc" });
    const individual = screen.getByRole("button", { name: "Checkout (individual)" });
    expect(individual).toHaveClass("graph-node", "graph-node--individual");
    expect(individual).toHaveAttribute("data-domain", "layer-1");
    const focused = screen.getByRole("button", { name: "Business Service (class)" });
    expect(focused).toHaveClass("graph-node--class", "graph-node--focus");
    expect(focused).toHaveAttribute("aria-pressed", "false");
  });

  it("marks the selected node as pressed", () => {
    renderCanvas({ selectedNodeId: "checkout" });
    expect(screen.getByRole("button", { name: "Checkout (individual)" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("draws cross-layer edges hot and same-layer edges default", () => {
    renderCanvas();
    const variants = new Map(lastProps().edges.map((e) => [e.id, e.variant]));
    expect(variants.get("e-svc-op")).toBe("hot");
    expect(variants.get("e-checkout-post")).toBe("hot");
    expect(variants.get("checkout:instance_of:svc")).toBe("default");
  });

  it("labels only edges incident to the selected node, truncating long predicates", () => {
    renderCanvas({ selectedNodeId: "svc" });
    const labels = new Map(lastProps().edges.map((e) => [e.id, e.label]));
    expect(labels.get("e-svc-op")).toBe(
      truncateLabel("business.service realized-by api.operation"),
    );
    expect(labels.get("e-svc-op")?.endsWith("…")).toBe(true);
    expect(labels.get("checkout:instance_of:svc")).toBe("instance of");
    expect(labels.get("e-checkout-post")).toBeUndefined();
  });

  it("renders a legend with the visible layers and the cross-layer edge count", () => {
    renderCanvas();
    const legend = screen.getByTestId("graph-layer-legend");
    expect(legend).toHaveAttribute("role", "group");
    expect(legend).toHaveClass("graph-legend-bar");
    const layers = screen.getAllByTestId("graph-legend-layer");
    expect(layers.map((l) => l.textContent)).toEqual(["Business Layer2", "API Layer2"]);
    expect(screen.getByTestId("graph-legend-cross-layer-count")).toHaveTextContent("2");
  });

  it("shows an empty status instead of the canvas when no nodes match", () => {
    const { container } = renderCanvas({ nodes: [], edges: [], emptyText: "Nothing here" });
    const empty = screen.getByTestId("graph-canvas-empty");
    expect(empty).toHaveAttribute("role", "status");
    expect(empty).toHaveClass("graph-canvas__empty");
    expect(empty).toHaveTextContent("Nothing here");
    expect(container.querySelector(".heimdall-graph-canvas-stub")).not.toBeInTheDocument();
    expect(captured.props).toBeNull();
  });
});

describe("truncateLabel", () => {
  it("keeps short labels and drops empty ones", () => {
    expect(truncateLabel("causes")).toBe("causes");
    expect(truncateLabel(null)).toBeUndefined();
    expect(truncateLabel("")).toBeUndefined();
  });
});
