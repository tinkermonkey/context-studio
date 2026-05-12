import { GraphCanvas } from "reagraph";
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
  const getDomainColor = (nodeId: string) => {
    const hash = nodeId.charCodeAt(0) % 3;
    const colors = ["#34d399", "#fbbf24", "#818cf8"];
    return colors[hash];
  };

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
          size: Math.max(20, Math.min(50, 20 + node.centrality * 30)),
          fill: getDomainColor(node.id),
          stroke: selectedNodeId === node.id ? "#22d3ee" : "#cbd5e1",
          strokeWidth: selectedNodeId === node.id ? 3 : 1,
        }))}
        edges={edges.map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
        }))}
        onNodeClick={(node) => {
          onNodeClick?.(node.id);
        }}
      />
    </div>
  );
};
