import { useCallback, useMemo } from "react";
import {
  GraphCanvas,
  GraphNode,
  type GraphNodeData,
  type GraphEdgeData,
} from "@tinkermonkey/heimdall-ui";
import type { GraphViewEdge, GraphViewLayer, GraphViewNode } from "@/api/hooks/graph";
import {
  isCrossLayer,
  layerColorKey,
  layerIndexById,
  layeredLayout,
  type GraphLayoutMode,
  type LayerHeader,
} from "./graphLayers";
import "@/design-system/graph.css";

interface GraphCanvasComponentProps {
  nodes: GraphViewNode[];
  edges: GraphViewEdge[];
  layers: GraphViewLayer[];
  layout: GraphLayoutMode;
  selectedNodeId?: string;
  focusNodeId?: string;
  onNodeSelect?: (nodeId: string) => void;
  emptyText?: string;
}

const KIND_BADGE: Record<GraphViewNode["node_type"], string> = {
  class: "C",
  individual: "I",
};

/** Edge labels sit on the canvas; long predicates (e.g. DR's "a.b verb c.d") would bury the nodes. */
const MAX_EDGE_LABEL_LENGTH = 28;

export function truncateLabel(label: string | null | undefined): string | undefined {
  if (!label) return undefined;
  return label.length > MAX_EDGE_LABEL_LENGTH
    ? `${label.slice(0, MAX_EDGE_LABEL_LENGTH - 1)}…`
    : label;
}

/**
 * Layer-aware graph canvas. Nodes are colored by layer (concept scheme), carry
 * a C/I badge for class vs individual, and cross-layer edges are drawn "hot".
 * In layered mode every node is pinned into its layer's band; in force mode
 * Heimdall's force layout positions them.
 */
export const GraphCanvasComponent = ({
  nodes,
  edges,
  layers,
  layout,
  selectedNodeId,
  focusNodeId,
  onNodeSelect,
  emptyText = "No nodes match the current filters.",
}: GraphCanvasComponentProps) => {
  const indexById = useMemo(() => layerIndexById(layers), [layers]);
  const nodeById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const colorFor = useCallback(
    (layerId: string | null | undefined) =>
      layerColorKey(layerId ? (indexById.get(layerId) ?? -1) : -1),
    [indexById],
  );

  const layered = useMemo(
    () => (layout === "layered" ? layeredLayout(nodes, layers) : null),
    [layout, nodes, layers],
  );

  const headerById = useMemo(
    () => new Map<string, LayerHeader>((layered?.headers ?? []).map((h) => [h.id, h])),
    [layered],
  );

  const heimdallNodes: GraphNodeData[] = useMemo(() => {
    const result: GraphNodeData[] = nodes.map((node) => {
      const position = layered?.positions.get(node.id);
      return {
        id: node.id,
        label: node.label,
        kind: KIND_BADGE[node.node_type],
        domainColor: colorFor(node.concept_scheme_id),
        ...(position ? { x: position.x, y: position.y } : {}),
      };
    });
    for (const header of layered?.headers ?? []) {
      result.push({
        id: header.id,
        label: header.title,
        domainColor: colorFor(header.layerId),
        x: header.x,
        y: header.y,
      });
    }
    return result;
  }, [nodes, layered, colorFor]);

  const heimdallEdges: GraphEdgeData[] = useMemo(
    () =>
      edges.map((edge) => {
        const incident =
          selectedNodeId !== undefined &&
          (edge.source === selectedNodeId || edge.target === selectedNodeId);
        return {
          id: edge.id,
          sourceId: edge.source,
          targetId: edge.target,
          label: incident ? truncateLabel(edge.predicate) : undefined,
          variant: isCrossLayer(edge, nodeById) ? "hot" : "default",
        };
      }),
    [edges, nodeById, selectedNodeId],
  );

  const renderNode = useCallback(
    (data: GraphNodeData, selected: boolean) => {
      const header = headerById.get(data.id);
      if (header) {
        return (
          <div
            className="graph-layer-header"
            data-domain={data.domainColor}
            data-testid={`graph-layer-header-${header.layerId || "none"}`}
            data-no-drag
          >
            <span className="graph-layer-header__swatch" aria-hidden="true" />
            <span className="graph-layer-header__title">{header.title}</span>
            <span className="graph-layer-header__count">{header.count}</span>
          </div>
        );
      }
      const node = nodeById.get(data.id);
      const classNames = [
        node ? `graph-node--${node.node_type}` : "",
        data.id === focusNodeId ? "graph-node--focus" : "",
      ]
        .filter(Boolean)
        .join(" ");
      return (
        <GraphNode
          id={data.id}
          label={data.label}
          kind={data.kind}
          domainColor={data.domainColor}
          selected={selected}
          onSelect={onNodeSelect}
          className={classNames}
          aria-label={node ? `${node.label} (${node.node_type})` : data.label}
        />
      );
    },
    [headerById, nodeById, focusNodeId, onNodeSelect],
  );

  // Heimdall fits the viewport only on first render; remount when the node set changes.
  const canvasKey = useMemo(() => `${layout}|${nodes.map((n) => n.id).join(",")}`, [layout, nodes]);

  const legendLayers = useMemo(() => {
    const counts = new Map<string, number>();
    for (const node of nodes) {
      if (node.concept_scheme_id) {
        counts.set(node.concept_scheme_id, (counts.get(node.concept_scheme_id) ?? 0) + 1);
      }
    }
    return layers
      .filter((layer) => counts.has(layer.id))
      .map((layer) => ({ layer, count: counts.get(layer.id) ?? 0 }));
  }, [nodes, layers]);

  const crossLayerCount = heimdallEdges.filter((e) => e.variant === "hot").length;

  return (
    <div
      data-testid="graph-canvas"
      className="graph-canvas graph-canvas-shell"
      data-layout={layout}
      role="region"
      aria-label="Graph visualization canvas"
    >
      {nodes.length === 0 ? (
        <div className="graph-canvas__empty" data-testid="graph-canvas-empty" role="status">
          {emptyText}
        </div>
      ) : (
        <>
          <div
            className="graph-legend-bar"
            data-testid="graph-layer-legend"
            role="group"
            aria-label="Graph legend"
          >
            {legendLayers.map(({ layer, count }) => (
              <span
                className="graph-legend-bar__item"
                key={layer.id}
                data-testid="graph-legend-layer"
              >
                <span
                  className="graph-legend-bar__dot"
                  data-domain={colorFor(layer.id)}
                  aria-hidden="true"
                />
                {layer.title}
                <span className="graph-legend-bar__count">{count}</span>
              </span>
            ))}
            <span className="graph-legend-bar__divider" aria-hidden="true" />
            <span className="graph-legend-bar__item">
              <span
                className="graph-legend-bar__line graph-legend-bar__line--hot"
                aria-hidden="true"
              />
              Cross-layer
              <span
                className="graph-legend-bar__count"
                data-testid="graph-legend-cross-layer-count"
              >
                {crossLayerCount}
              </span>
            </span>
            <span className="graph-legend-bar__item">
              <span className="graph-legend-bar__line" aria-hidden="true" />
              Within layer
              <span className="graph-legend-bar__count">
                {heimdallEdges.length - crossLayerCount}
              </span>
            </span>
            <span className="graph-legend-bar__divider" aria-hidden="true" />
            <span className="graph-legend-bar__item">
              <span className="graph-legend-bar__pill" aria-hidden="true">
                C
              </span>
              Class
            </span>
            <span className="graph-legend-bar__item">
              <span
                className="graph-legend-bar__pill graph-legend-bar__pill--individual"
                aria-hidden="true"
              >
                I
              </span>
              Individual
            </span>
          </div>
          <GraphCanvas
            key={canvasKey}
            nodes={heimdallNodes}
            edges={heimdallEdges}
            layout={layout === "layered" ? "manual" : "force"}
            selectedNodeId={selectedNodeId}
            onNodeSelect={onNodeSelect}
            renderNode={renderNode}
            className="graph-canvas__surface"
          />
        </>
      )}
    </div>
  );
};
