import { GraphCanvas, type GraphNodeData, type GraphEdgeData } from "@tinkermonkey/heimdall-ui";
import { useEffect, useMemo } from "react";
import type { GraphNode, GraphEdge } from "@/api/hooks/graph";
import "@/design-system/graph.css";
import { useToasts } from "@/components/ui/Toast";

interface GraphCanvasComponentProps {
  nodes: GraphNode[];
  edges: Array<{ id: string; source: string; target: string }>;
  onNodeSelect?: (nodeId: string) => void;
  selectedNodeId?: string;
}

export const validateEdgeEndpoints = (
  nodes: GraphNode[],
  edges: GraphEdge[],
): { valid: boolean; errors: string[] } => {
  const errors: string[] = [];
  const nodeIds = new Set(nodes.map((n) => n.id));

  edges.forEach((edge) => {
    if (!nodeIds.has(edge.source)) {
      errors.push(`Edge ${edge.id}: source node "${edge.source}" not found in nodes array`);
    }
    if (!nodeIds.has(edge.target)) {
      errors.push(`Edge ${edge.id}: target node "${edge.target}" not found in nodes array`);
    }
  });

  return {
    valid: errors.length === 0,
    errors,
  };
};

export const GraphCanvasComponent = ({
  nodes,
  edges,
  onNodeSelect,
  selectedNodeId,
}: GraphCanvasComponentProps) => {
  const { toast } = useToasts();
  const validation = useMemo(() => validateEdgeEndpoints(nodes, edges), [nodes, edges]);

  useEffect(() => {
    if (!validation.valid) {
      validation.errors.forEach((error) => {
        toast("error", "Graph validation error", error);
      });
      console.error("Graph validation errors:", validation.errors);
    }
  }, [validation, toast]);

  if (!validation.valid) {
    return (
      <div
        data-testid="graph-canvas"
        className="graph-canvas"
        role="region"
        aria-label="Graph visualization canvas"
      >
        <div className="graph-canvas__error">
          <p>Graph data validation failed. Check console for details.</p>
        </div>
      </div>
    );
  }

  const heimdallNodes: GraphNodeData[] = nodes.map((node) => ({
    id: node.id,
    label: node.label,
    kind: node.kind,
    domainColor: node.domainColor,
  }));

  const heimdallEdges: GraphEdgeData[] = edges.map((edge) => ({
    id: edge.id,
    sourceId: edge.source,
    targetId: edge.target,
  }));

  return (
    <div
      data-testid="graph-canvas"
      className="graph-canvas"
      role="region"
      aria-label="Graph visualization canvas"
    >
      <GraphCanvas
        nodes={heimdallNodes}
        edges={heimdallEdges}
        layout="force"
        selectedNodeId={selectedNodeId}
        onNodeSelect={onNodeSelect}
        style={{ width: "100%", height: "100%" }}
      />
    </div>
  );
};
