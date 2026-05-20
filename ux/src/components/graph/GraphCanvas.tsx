import { GraphCanvas } from "@tinkermonkey/heimdall-ui";
import type { GraphNode, GraphEdge } from "@/api/hooks/graph";
import "@/design-system/graph.css";

interface GraphCanvasComponentProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (nodeId: string) => void;
  selectedNodeId?: string;
}

export const GraphCanvasComponent = ({
  nodes,
  edges,
  onNodeClick,
  selectedNodeId,
}: GraphCanvasComponentProps) => {
  return (
    <div
      data-testid="graph-canvas"
      className="graph-canvas"
      role="region"
      aria-label="Graph visualization canvas"
    >
      <GraphCanvas
        nodes={nodes.map((node) => ({
          id: node.id,
          label: node.label,
          kind: node.kind,
          domainColor: node.domainColor,
        }))}
        edges={edges.map((edge) => ({
          id: edge.id,
          sourceId: edge.source,
          targetId: edge.target,
        }))}
        selectedNodeId={selectedNodeId}
        onNodeSelect={onNodeClick}
        layout="manual"
      />
    </div>
  );
};
