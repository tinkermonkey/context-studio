/**
 * Pure helpers for the layered graph view: layer filtering, focus
 * neighborhoods, layer colors and the layered (banded) layout.
 *
 * Layers are concept schemes. Every node (class or individual) belongs to at
 * most one layer via `concept_scheme_id`.
 */
import type { GraphView, GraphViewEdge, GraphViewNode, GraphViewLayer } from "@/api/hooks/graph";

/** Number of distinct layer colors defined in graph.css (`layer-0` … `layer-11`). */
export const LAYER_PALETTE_SIZE = 12;

/** Layers shown by default: enough to see cross-layer edges without a hairball. */
export const DEFAULT_LAYER_COUNT = 3;

/** Force layout is O(n²) per iteration in Heimdall; above this it freezes the page. */
export const FORCE_LAYOUT_MAX_NODES = 250;

export const MIN_FOCUS_DEPTH = 1;
export const MAX_FOCUS_DEPTH = 3;

export type NodeKindFilter = "all" | "class" | "individual";
export type GraphLayoutMode = "layered" | "force";

export interface GraphFilter {
  layerIds: string[];
  /** Optional class restriction; empty means every class in the selected layers. */
  classIds: string[];
  nodeKind: NodeKindFilter;
}

export interface GraphSlice {
  nodes: GraphViewNode[];
  edges: GraphViewEdge[];
}

export interface Point {
  x: number;
  y: number;
}

export interface LayerHeader {
  id: string;
  layerId: string;
  title: string;
  count: number;
  x: number;
  y: number;
}

export interface LayeredLayout {
  positions: Map<string, Point>;
  headers: LayerHeader[];
}

/** Grid geometry for the layered layout, in canvas units. */
export const LAYERED_CELL_WIDTH = 168;
export const LAYERED_ROW_HEIGHT = 42;
export const LAYERED_BAND_GAP = 64;
export const LAYERED_HEADER_OFFSET = 44;
/** Four columns keep a band inside a ~700px canvas pane at 1× zoom. */
export const LAYERED_MAX_COLUMNS = 4;

export const LAYER_HEADER_PREFIX = "layer-header:";

/** Heimdall domain key for a layer, matching `[data-domain="layer-N"]` rules in graph.css. */
export function layerColorKey(layerIndex: number): string {
  if (layerIndex < 0) return "default";
  return `layer-${layerIndex % LAYER_PALETTE_SIZE}`;
}

/** Map of layer id → index in `view.layers`, used for colors and band order. */
export function layerIndexById(layers: GraphViewLayer[]): Map<string, number> {
  return new Map(layers.map((layer, index) => [layer.id, index]));
}

/**
 * Default layer selection: the first DEFAULT_LAYER_COUNT layers of the
 * taxonomy with the most layers (for a DR model, the 12-layer `dr_spec`).
 */
export function defaultLayerIds(view: GraphView, count = DEFAULT_LAYER_COUNT): string[] {
  const layersByTaxonomy = new Map<string, GraphViewLayer[]>();
  for (const layer of view.layers) {
    const group = layersByTaxonomy.get(layer.taxonomy_id) ?? [];
    group.push(layer);
    layersByTaxonomy.set(layer.taxonomy_id, group);
  }
  let largest: GraphViewLayer[] = [];
  for (const group of layersByTaxonomy.values()) {
    if (group.length > largest.length) largest = group;
  }
  return largest.slice(0, count).map((layer) => layer.id);
}

/**
 * Default node kind: an instance graph is what users explore once one exists;
 * a schema-only ontology falls back to its classes.
 */
export function defaultNodeKind(view: GraphView): NodeKindFilter {
  return view.nodes.some((n) => n.node_type === "individual") ? "individual" : "class";
}

/** Keep only edges whose two endpoints are among `nodes`. */
export function edgesWithin(nodes: GraphViewNode[], edges: GraphViewEdge[]): GraphViewEdge[] {
  const ids = new Set(nodes.map((n) => n.id));
  return edges.filter((e) => ids.has(e.source) && ids.has(e.target));
}

function matchesKind(node: GraphViewNode, kind: NodeKindFilter): boolean {
  return kind === "all" || node.node_type === kind;
}

/** Filter the graph view by layer, optional class restriction and node kind. */
export function filterGraphView(view: GraphView, filter: GraphFilter): GraphSlice {
  const layerIds = new Set(filter.layerIds);
  const classIds = new Set(filter.classIds);
  const nodes = view.nodes.filter((node) => {
    if (!node.concept_scheme_id || !layerIds.has(node.concept_scheme_id)) return false;
    if (!matchesKind(node, filter.nodeKind)) return false;
    if (classIds.size === 0) return true;
    if (node.node_type === "class") return classIds.has(node.id);
    return (node.class_ids ?? []).some((id) => classIds.has(id));
  });
  return { nodes, edges: edgesWithin(nodes, view.edges) };
}

/**
 * Nodes within `depth` hops of `focusId` (edges treated as undirected), plus
 * the edges among them. Ignores the layer filter so cross-layer neighbors
 * show up.
 *
 * Computed client-side on purpose rather than via GET /graph/nodes/{id}/subgraph:
 * the backend's in-memory graph has no schema (domain → range) edges, so its
 * neighborhoods would not match what this view draws.
 */
export function neighborhood(
  view: GraphView,
  focusId: string,
  depth: number,
  nodeKind: NodeKindFilter = "all",
): GraphSlice {
  const nodeById = new Map(view.nodes.map((n) => [n.id, n]));
  if (!nodeById.has(focusId)) return { nodes: [], edges: [] };

  const adjacency = new Map<string, string[]>();
  for (const edge of view.edges) {
    const source = nodeById.get(edge.source);
    const target = nodeById.get(edge.target);
    if (!source || !target) continue;
    if (!matchesKind(source, nodeKind) && source.id !== focusId) continue;
    if (!matchesKind(target, nodeKind) && target.id !== focusId) continue;
    for (const [from, to] of [
      [edge.source, edge.target],
      [edge.target, edge.source],
    ]) {
      const list = adjacency.get(from);
      if (list) list.push(to);
      else adjacency.set(from, [to]);
    }
  }

  const visited = new Set<string>([focusId]);
  let frontier = [focusId];
  for (let hop = 0; hop < depth && frontier.length > 0; hop++) {
    const next: string[] = [];
    for (const id of frontier) {
      for (const neighbor of adjacency.get(id) ?? []) {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          next.push(neighbor);
        }
      }
    }
    frontier = next;
  }

  const nodes = view.nodes.filter((n) => visited.has(n.id));
  return { nodes, edges: edgesWithin(nodes, view.edges) };
}

/** True when an edge connects nodes in two different layers. */
export function isCrossLayer(edge: GraphViewEdge, nodeById: Map<string, GraphViewNode>): boolean {
  const source = nodeById.get(edge.source)?.concept_scheme_id;
  const target = nodeById.get(edge.target)?.concept_scheme_id;
  return Boolean(source && target && source !== target);
}

function byLabel(a: GraphViewNode, b: GraphViewNode): number {
  return a.label.localeCompare(b.label);
}

/**
 * Layered layout: one horizontal band per layer (in `layers` order), classes
 * first then individuals, laid out in a centred grid. Every node gets a
 * position, so the canvas can run in manual layout mode. Nodes without a
 * known layer go into a trailing band.
 */
export function layeredLayout(nodes: GraphViewNode[], layers: GraphViewLayer[]): LayeredLayout {
  const indexById = layerIndexById(layers);
  const groups = new Map<string, GraphViewNode[]>();
  for (const node of nodes) {
    const key =
      node.concept_scheme_id && indexById.has(node.concept_scheme_id) ? node.concept_scheme_id : "";
    groups.set(key, [...(groups.get(key) ?? []), node]);
  }

  const orderedKeys = [...groups.keys()].sort((a, b) => {
    const ia = a === "" ? Number.MAX_SAFE_INTEGER : (indexById.get(a) ?? 0);
    const ib = b === "" ? Number.MAX_SAFE_INTEGER : (indexById.get(b) ?? 0);
    return ia - ib;
  });

  const positions = new Map<string, Point>();
  const headers: LayerHeader[] = [];
  let top = 0;
  for (const key of orderedKeys) {
    const members = groups.get(key) ?? [];
    const classes = members.filter((n) => n.node_type === "class").sort(byLabel);
    const individuals = members.filter((n) => n.node_type !== "class").sort(byLabel);
    const ordered = [...classes, ...individuals];
    const columns = Math.min(ordered.length, LAYERED_MAX_COLUMNS);
    const rows = Math.ceil(ordered.length / columns);
    const layer = key ? layers[indexById.get(key) ?? 0] : undefined;

    headers.push({
      id: `${LAYER_HEADER_PREFIX}${key || "none"}`,
      layerId: key,
      title: layer?.title ?? "No layer",
      count: ordered.length,
      x: 0,
      y: top,
    });

    ordered.forEach((node, index) => {
      const column = index % columns;
      const row = Math.floor(index / columns);
      positions.set(node.id, {
        x: (column - (columns - 1) / 2) * LAYERED_CELL_WIDTH,
        y: top + LAYERED_HEADER_OFFSET + row * LAYERED_ROW_HEIGHT,
      });
    });

    top += LAYERED_HEADER_OFFSET + rows * LAYERED_ROW_HEIGHT + LAYERED_BAND_GAP;
  }

  return { positions, headers };
}
