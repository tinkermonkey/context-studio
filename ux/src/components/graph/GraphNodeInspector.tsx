import { useMemo } from "react";
import { Crosshair } from "lucide-react";
import {
  Button,
  GraphInspector,
  type GraphNodeMetadata,
  type RelationshipLink,
} from "@tinkermonkey/heimdall-ui";
import type { GraphView } from "@/api/hooks/graph";
import { layerColorKey, layerIndexById } from "./graphLayers";

interface GraphNodeInspectorProps {
  view: GraphView;
  nodeId?: string;
  isFocused: boolean;
  onFocus: (nodeId: string) => void;
  /** Called when a relationship endpoint is clicked; the page re-focuses on it. */
  onNavigate: (nodeId: string) => void;
  emptyStateText: string;
}

/**
 * Inspector for the selected graph node: class, layer, taxonomy, description
 * and every relationship (predicate + other endpoint). Relationship endpoints
 * are clickable and re-focus the graph on that node.
 */
export function GraphNodeInspector({
  view,
  nodeId,
  isFocused,
  onFocus,
  onNavigate,
  emptyStateText,
}: GraphNodeInspectorProps) {
  const nodeById = useMemo(() => new Map(view.nodes.map((n) => [n.id, n])), [view.nodes]);
  const layerById = useMemo(() => new Map(view.layers.map((l) => [l.id, l])), [view.layers]);
  const layerIndex = useMemo(() => layerIndexById(view.layers), [view.layers]);
  const taxonomyById = useMemo(
    () => new Map(view.taxonomies.map((t) => [t.id, t])),
    [view.taxonomies],
  );

  const node = nodeId ? nodeById.get(nodeId) : undefined;

  const metadata: GraphNodeMetadata | null = useMemo(() => {
    if (!node) return null;
    const layer = node.concept_scheme_id ? layerById.get(node.concept_scheme_id) : undefined;
    const taxonomy = node.taxonomy_id ? taxonomyById.get(node.taxonomy_id) : undefined;
    const classTitles = (node.class_ids ?? [])
      .map((id) => nodeById.get(id)?.label ?? id)
      .join(", ");
    return {
      id: node.id,
      title: node.label,
      kind: node.node_type === "class" ? "Class" : "Individual",
      domain: layer?.title,
      description: node.description ?? undefined,
      metadata: {
        ...(node.node_type === "individual" ? { Class: classTitles || "—" } : {}),
        Layer: layer?.title ?? "—",
        Taxonomy: taxonomy?.title ?? "—",
        ...(node.identifier ? { Identifier: node.identifier } : {}),
      },
    };
  }, [node, layerById, taxonomyById, nodeById]);

  const relationships: RelationshipLink[] = useMemo(() => {
    if (!node) return [];
    const links: RelationshipLink[] = [];
    for (const edge of view.edges) {
      const direction = edge.source === node.id ? "out" : edge.target === node.id ? "in" : null;
      if (!direction) continue;
      const otherId = direction === "out" ? edge.target : edge.source;
      const other = nodeById.get(otherId);
      const otherLayer = other?.concept_scheme_id;
      links.push({
        id: edge.id,
        target: otherId,
        targetTitle: other?.label ?? otherId,
        targetDomain: otherLayer ? layerColorKey(layerIndex.get(otherLayer) ?? -1) : undefined,
        predicate: edge.predicate ?? edge.edge_type,
        direction,
      });
    }
    return links.sort((a, b) => a.predicate.localeCompare(b.predicate));
  }, [node, view.edges, nodeById, layerIndex]);

  return (
    <div
      className="graph-node-inspector"
      data-testid="node-inspector"
      role="region"
      aria-label="Selected node details"
    >
      {node && (
        <div className="graph-node-inspector__actions">
          <span
            className="graph-node-inspector__count"
            data-testid="node-inspector-relationship-count"
          >
            {relationships.length} relationship{relationships.length === 1 ? "" : "s"}
          </span>
          <Button
            variant={isFocused ? "secondary" : "primary"}
            size="sm"
            onClick={() => onFocus(node.id)}
            disabled={isFocused}
            aria-pressed={isFocused}
            data-testid="node-inspector-focus-button"
          >
            <Crosshair size={14} />
            {isFocused ? "Focused" : "Focus neighborhood"}
          </Button>
        </div>
      )}
      <GraphInspector
        node={metadata}
        relationships={relationships}
        onNodeSelect={onNavigate}
        emptyStateText={emptyStateText}
        className="graph-node-inspector__body"
      />
    </div>
  );
}
