import { describe, it, expect } from "vitest";
import { createGraphView } from "@/api/services/__tests__/fixtures/graph.fixtures";
import {
  DEFAULT_LAYER_COUNT,
  LAYERED_CELL_WIDTH,
  LAYERED_MAX_COLUMNS,
  LAYER_HEADER_PREFIX,
  LAYER_PALETTE_SIZE,
  defaultLayerIds,
  defaultNodeKind,
  filterGraphView,
  isCrossLayer,
  layerColorKey,
  layeredLayout,
  neighborhood,
} from "../graphLayers";

const ids = (items: { id: string }[]) => items.map((i) => i.id).sort();

describe("graphLayers", () => {
  const view = createGraphView();

  describe("layerColorKey", () => {
    it("maps layer indexes onto the palette and wraps", () => {
      expect(layerColorKey(0)).toBe("layer-0");
      expect(layerColorKey(11)).toBe("layer-11");
      expect(layerColorKey(LAYER_PALETTE_SIZE)).toBe("layer-0");
    });

    it("returns 'default' for unknown layers", () => {
      expect(layerColorKey(-1)).toBe("default");
    });
  });

  describe("defaultLayerIds", () => {
    it("picks the first layers of the largest taxonomy that hold default-kind nodes", () => {
      // Individuals exist, and only Business and API hold any: Motivation (classes only) is skipped.
      expect(defaultLayerIds(view)).toEqual(["layer-business", "layer-api"]);
      expect(defaultLayerIds(view, 1)).toEqual(["layer-business"]);
    });

    it("counts classes as populating a layer for a schema-only view", () => {
      const schemaOnly = createGraphView({
        nodes: view.nodes.filter((n) => n.node_type === "class"),
      });
      expect(defaultLayerIds(schemaOnly)).toEqual([
        "layer-motivation",
        "layer-business",
        "layer-api",
      ]);
    });

    it("skips a leading empty layer (e.g. a spec layer with no model elements)", () => {
      const withEmpty = createGraphView({
        layers: [
          { id: "layer-product", title: "Product", identifier: "product", taxonomy_id: "tax-dr" },
          ...view.layers,
        ],
      });
      expect(defaultLayerIds(withEmpty)).toEqual(["layer-business", "layer-api"]);
    });

    it("falls back to the first layers when none hold default-kind nodes", () => {
      const empty = createGraphView({ nodes: [], edges: [] });
      expect(defaultLayerIds(empty)).toEqual(["layer-motivation", "layer-business", "layer-api"]);
    });

    it("returns an empty selection for a view without layers", () => {
      expect(defaultLayerIds(createGraphView({ layers: [] }))).toEqual([]);
    });

    it("cuts the rendered node count compared with all layers", () => {
      const manyLayers = createGraphView({
        layers: Array.from({ length: 12 }, (_, i) => ({
          id: `l${i}`,
          title: `Layer ${i}`,
          identifier: `l${i}`,
          taxonomy_id: "tax-dr",
        })),
        nodes: Array.from({ length: 120 }, (_, i) => ({
          id: `n${i}`,
          label: `Node ${i}`,
          node_type: "individual" as const,
          concept_scheme_id: `l${i % 12}`,
          taxonomy_id: "tax-dr",
          class_ids: [],
        })),
        edges: [],
      });
      const defaults = filterGraphView(manyLayers, {
        layerIds: defaultLayerIds(manyLayers),
        classIds: [],
        nodeKind: "all",
      });
      expect(defaults.nodes).toHaveLength(10 * DEFAULT_LAYER_COUNT);
    });
  });

  describe("defaultNodeKind", () => {
    it("prefers individuals when the view has any", () => {
      expect(defaultNodeKind(view)).toBe("individual");
    });

    it("falls back to classes for a schema-only view", () => {
      const schemaOnly = createGraphView({
        nodes: view.nodes.filter((n) => n.node_type === "class"),
      });
      expect(defaultNodeKind(schemaOnly)).toBe("class");
    });
  });

  describe("filterGraphView", () => {
    it("keeps nodes in the selected layers and edges between them", () => {
      const slice = filterGraphView(view, {
        layerIds: ["layer-business", "layer-api"],
        classIds: [],
        nodeKind: "all",
      });
      expect(ids(slice.nodes)).toEqual(["checkout", "op", "post-order", "svc"]);
      expect(ids(slice.edges)).toEqual([
        "checkout:instance_of:svc",
        "e-checkout-post",
        "e-svc-op",
        "post-order:instance_of:op",
      ]);
    });

    it("filters by node kind", () => {
      const slice = filterGraphView(view, {
        layerIds: ["layer-business", "layer-api"],
        classIds: [],
        nodeKind: "individual",
      });
      expect(ids(slice.nodes)).toEqual(["checkout", "post-order"]);
      expect(ids(slice.edges)).toEqual(["e-checkout-post"]);
    });

    it("restricts classes and their individuals when a class filter is set", () => {
      const slice = filterGraphView(view, {
        layerIds: ["layer-business", "layer-api"],
        classIds: ["svc"],
        nodeKind: "all",
      });
      expect(ids(slice.nodes)).toEqual(["checkout", "svc"]);
    });

    it("returns nothing when no layer is selected", () => {
      const slice = filterGraphView(view, { layerIds: [], classIds: [], nodeKind: "all" });
      expect(slice.nodes).toEqual([]);
      expect(slice.edges).toEqual([]);
    });
  });

  describe("neighborhood", () => {
    it("returns the focus node and its 1-hop neighbors across layers", () => {
      const slice = neighborhood(view, "checkout", 1);
      expect(ids(slice.nodes)).toEqual(["checkout", "post-order", "svc"]);
      expect(ids(slice.edges)).toEqual(["checkout:instance_of:svc", "e-checkout-post"]);
    });

    it("expands with depth", () => {
      const slice = neighborhood(view, "checkout", 2);
      expect(ids(slice.nodes)).toEqual(["checkout", "op", "post-order", "svc"]);
    });

    it("respects the node kind filter but always keeps the focus node", () => {
      // svc is a class: kept as the focus, but its class neighbor `op` is filtered out.
      const slice = neighborhood(view, "svc", 2, "individual");
      expect(ids(slice.nodes)).toEqual(["checkout", "post-order", "svc"]);
      const individuals = neighborhood(view, "checkout", 3, "individual");
      expect(ids(individuals.nodes)).toEqual(["checkout", "post-order"]);
    });

    it("returns an empty slice for an unknown node", () => {
      expect(neighborhood(view, "missing", 2)).toEqual({ nodes: [], edges: [] });
    });
  });

  describe("isCrossLayer", () => {
    const nodeById = new Map(view.nodes.map((n) => [n.id, n]));

    it("is true for edges between different layers", () => {
      const edge = view.edges.find((e) => e.id === "e-svc-op")!;
      expect(isCrossLayer(edge, nodeById)).toBe(true);
    });

    it("is false for edges inside one layer", () => {
      const edge = view.edges.find((e) => e.id === "e-goal-outcome")!;
      expect(isCrossLayer(edge, nodeById)).toBe(false);
    });
  });

  describe("layeredLayout", () => {
    it("places every node and one header per layer, in layer order", () => {
      const { positions, headers } = layeredLayout(view.nodes, view.layers);
      expect(positions.size).toBe(view.nodes.length);
      expect(headers.map((h) => h.layerId)).toEqual([
        "layer-motivation",
        "layer-business",
        "layer-api",
        "layer-side",
      ]);
      expect(headers.every((h) => h.id.startsWith(LAYER_HEADER_PREFIX))).toBe(true);
      // Bands stack downward.
      const ys = headers.map((h) => h.y);
      expect([...ys].sort((a, b) => a - b)).toEqual(ys);
    });

    it("keeps each node below its layer header and above the next one", () => {
      const { positions, headers } = layeredLayout(view.nodes, view.layers);
      const goal = positions.get("goal")!;
      expect(goal.y).toBeGreaterThan(headers[0].y);
      expect(goal.y).toBeLessThan(headers[1].y);
    });

    it("lists classes before individuals within a band", () => {
      const { positions } = layeredLayout(view.nodes, view.layers);
      // business band: svc (class) first column, checkout (individual) second
      expect(positions.get("svc")!.x).toBeLessThan(positions.get("checkout")!.x);
    });

    it("wraps a band after LAYERED_MAX_COLUMNS columns, centred on x = 0", () => {
      const nodes = Array.from({ length: LAYERED_MAX_COLUMNS + 1 }, (_, i) => ({
        id: `n${i}`,
        label: `Node ${String(i).padStart(2, "0")}`,
        node_type: "class" as const,
        concept_scheme_id: "layer-api",
        taxonomy_id: "tax-dr",
        class_ids: [],
      }));
      const { positions } = layeredLayout(nodes, view.layers);
      const firstRow = nodes.slice(0, LAYERED_MAX_COLUMNS).map((n) => positions.get(n.id)!);
      const xs = firstRow.map((p) => p.x);
      expect(xs[1] - xs[0]).toBe(LAYERED_CELL_WIDTH);
      expect(xs[0] + xs[xs.length - 1]).toBe(0);
      const wrapped = positions.get(`n${LAYERED_MAX_COLUMNS}`)!;
      expect(wrapped.y).toBeGreaterThan(firstRow[0].y);
    });

    it("puts nodes without a known layer into a trailing band", () => {
      const orphan = { ...view.nodes[0], id: "orphan", concept_scheme_id: null };
      const { headers } = layeredLayout([orphan, view.nodes[0]], view.layers);
      expect(headers.map((h) => h.title)).toEqual(["Motivation Layer", "No layer"]);
    });
  });
});
