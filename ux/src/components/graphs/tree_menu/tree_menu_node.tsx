import React, { useState } from "react";
import { MenuStyles, MenuEdgeColors } from "./tree_menu_styles";
import { createNodePath } from "../hierarchy/tree_chart_utils";
import type { HierarchyNode } from "../hierarchy/tree_data";
import { CircleArrowRight, ChevronRight, ChevronDown } from "lucide-react";

interface TreeMenuNodeProps {
  node: HierarchyNode;
  parentNode?: HierarchyNode;
  onToggle?: (nodeId: string) => void;
  onNodeClick?: (node: HierarchyNode) => void;
  highlightedTermId?: string;
}

const TreeMenuNode: React.FC<TreeMenuNodeProps> = ({
  node,
  parentNode,
  onToggle,
  onNodeClick,
  highlightedTermId,
}) => {
  const nodeX = node.x ?? 0;
  const nodeY = node.y ?? 0;
  const parentX = parentNode?.x ?? 0;
  const parentY = parentNode?.y ?? 0;

  // Use the measured text width from the node, with fallback
  const labelWidth = node.textWidth ?? node.title.length * 5;

  // Check if node has children based on original data
  const hasChildren =
    node.hasChildren ?? (node.children && node.children.length > 0);

  // Use the external expanded state
  const isExpanded = node.expanded ?? true;

  // Get color based on node depth
  const nodeDepth = node.depth ?? 0;
  const colorIndex = Math.max(0, nodeDepth - 1) % MenuEdgeColors.length;
  const nodeColor = MenuEdgeColors[colorIndex];

  // Check if this node should be highlighted
  const isHighlighted = highlightedTermId && node.id === highlightedTermId;

  const handleExpandClick = () => {
    if (hasChildren && onToggle) {
      onToggle(node.id);
    }
  };

  const handleNodeTextClick = () => {
    if (onNodeClick) {
      onNodeClick(node);
    }
  };

  const [isHovered, setIsHovered] = useState(false);

  return (
    <g>
      {/* Render children recursively only if expanded */}
      {isExpanded &&
        node.children.map((child, index) => (
          <TreeMenuNode
            key={child.id || index}
            node={child}
            parentNode={node}
            onToggle={onToggle}
            onNodeClick={onNodeClick}
            highlightedTermId={highlightedTermId}
          />
        ))}

      {/* Node label with expand/collapse icon */}
      <g
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        onClick={handleNodeTextClick}
        style={{ cursor: onNodeClick ? "pointer" : "default" }}
      >
        {/* Background rectangle for text */}
        <rect
          x={nodeX - 2}
          y={nodeY - MenuStyles.nodeLabel.height}
          width={labelWidth + 20}
          height={MenuStyles.nodeLabel.height}
          fill={
            isHighlighted
              ? MenuStyles.nodeLabel.highlightColor
              : MenuStyles.nodeLabel.backgroundColor
          }
          rx={2}
        />

        {/* Expand/collapse chevron icon for nodes with children */}
        {hasChildren && (
          <g
            onClick={(e) => {
              e.stopPropagation();
              handleExpandClick();
            }}
            style={{ cursor: "pointer" }}
            transform={`translate(${nodeX}, ${nodeY - 14})`}
          >
            {isExpanded ? (
              <ChevronDown size={12} className="text-slate-600" />
            ) : (
              <ChevronRight size={12} className="text-slate-600" />
            )}
          </g>
        )}

        {/* Node text */}
        <text
          x={nodeX + (hasChildren ? 14 : 2)}
          y={nodeY - MenuStyles.nodeLabel.height / 2}
          style={{
            ...MenuStyles.nodeLabel,
            fill: isHovered ? MenuStyles.nodeLabel.hoverColor : MenuStyles.nodeLabel.color,
            fontWeight: isHighlighted ? "600" : "normal",
          }}
        >
          {node.title}
        </text>

        {/* CircleArrowRight icon - shown on hover when click handler is provided */}
        {onNodeClick && isHovered && (
          <g
            onClick={handleNodeTextClick}
            style={{ cursor: "pointer" }}
            transform={`translate(${nodeX + labelWidth + (hasChildren ? 14 : 2)}, ${nodeY - 14})`}
          >
            <CircleArrowRight
              size={12}
              className="text-blue-500 hover:text-blue-700"
              fill={MenuStyles.controls.backgroundColor}
            />
          </g>
        )}
      </g>

      {/* Branch line from parent to this node */}
      {parentNode && (
        <path
          d={createNodePath(
            parentX + (parentNode.hasChildren ? 14 : 2),
            parentY,
            nodeX + (hasChildren ? 14 : 2),
            nodeY
          )}
          style={{
            ...MenuStyles.branchLine,
            stroke: nodeColor,
          }}
        />
      )}
    </g>
  );
};

export { TreeMenuNode };
