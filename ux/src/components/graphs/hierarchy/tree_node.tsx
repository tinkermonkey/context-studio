import React, { useState } from "react";
import { ChartStyles, EdgeColors } from "./tree_styles";
import { createNodePath } from "./tree_chart_utils";
import type { HierarchyNode } from "./tree_data";
import { CircleArrowRight } from "lucide-react";

interface TreeNodeProps {
  node: HierarchyNode;
  parentNode?: HierarchyNode;
  onToggle?: (nodeId: string) => void;
  onNodeClick?: (node: HierarchyNode) => void;
  highlightedTermId?: string;
}

const TreeNode: React.FC<TreeNodeProps> = ({
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
  const labelWidth = node.textWidth ?? node.title.length * 6;

  // Definition dimensions
  const definitionWidth = node.definitionWidth ?? 0;
  const definitionHeight =
    node.definitionHeight ?? ChartStyles.nodeLabel.height;

  // Check if node has children based on original data (not current children array)
  const hasChildren =
    node.hasChildren ?? (node.children && node.children.length > 0);

  // Use the external expanded state instead of node.expanded
  const isExpanded = node.expanded ?? true;

  // Get color based on node depth (depth 1 uses index 0, depth 2 uses index 1, etc.)
  const nodeDepth = node.depth ?? 0;
  const colorIndex = Math.max(0, nodeDepth - 1) % EdgeColors.length;
  const nodeColor = EdgeColors[colorIndex];

  // Check if this node should be highlighted
  const isHighlighted = highlightedTermId && node.id === highlightedTermId;

  const handleClick = () => {
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
          <TreeNode
            key={child.id || index}
            node={child}
            parentNode={node}
            onToggle={onToggle}
            onNodeClick={onNodeClick}
            highlightedTermId={highlightedTermId}
          />
        ))}

      {/* Node label */}
      <g
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {/* Background rectangle for text */}
        <rect
          x={nodeX - 2}
          y={nodeY - ChartStyles.nodeLabel.height}
          width={labelWidth + 18}
          height={ChartStyles.nodeLabel.height}
          fill={
            isHighlighted
              ? ChartStyles.nodeLabel.highlightColor
              : ChartStyles.nodeLabel.backgroundColor
          }
          rx={2}
        />
        <text
          x={nodeX}
          y={nodeY - ChartStyles.nodeLabel.height / 2}
          style={{
            ...ChartStyles.nodeLabel,
            //fontWeight: isHighlighted ? "bold" : "normal",
          }}
        >
          {node.title}
        </text>

        {/* Definition using foreignObject */}
        {node.definition && (
          <foreignObject
            x={nodeX + labelWidth + 15}
            y={nodeY - ChartStyles.nodeLabel.height}
            width={definitionWidth}
            height={definitionHeight}
          >
            <div
              style={{
                width: definitionWidth,
                height: definitionHeight,
                borderRadius: "4px",
                ...ChartStyles.nodeDefinition,
                backgroundColor: isHighlighted
                  ? ChartStyles.nodeDefinition.highlightColor
                  : ChartStyles.nodeDefinition.backgroundColor,
                //fontWeight: isHighlighted ? "bold" : "normal",
              }}
            >
              {node.definition}
            </div>
          </foreignObject>
        )}

        {/* CircleArrowRight icon - shown on hover when click handler is provided */}
        {onNodeClick && isHovered && (
          <g
            onClick={handleNodeTextClick}
            style={{ cursor: "pointer" }}
            transform={`translate(${nodeX + labelWidth}, ${nodeY - 18})`}
          >
            <CircleArrowRight
              size={16}
              className="text-blue-500 hover:text-blue-700"
              fill={ChartStyles.controls.backgroundColor}
            />
          </g>
        )}
      </g>

      {/* Branch line from parent to this node */}
      {parentNode && (
        <path
          d={createNodePath(parentX, parentY, nodeX + labelWidth, nodeY)}
          style={{
            ...ChartStyles.branchLine,
            stroke: nodeColor,
          }}
        />
      )}

      {/* Expand/collapse indicator for nodes with children */}
      {hasChildren && (
        <g
          onClick={handleClick}
          style={{ cursor: "pointer" }}
          transform={`translate(${nodeX - 10}, ${nodeY})`}
        >
          <circle
            cx={0}
            cy={0}
            r={7}
            fill={ChartStyles.controls.backgroundColor}
            stroke={nodeColor}
            strokeWidth={2}
          />
          <text
            x={0}
            y={3.5}
            textAnchor="middle"
            fontSize="10"
            fill={isExpanded ? "#e74c3c" : "#27ae60"}
            fontWeight="bold"
          >
            {isExpanded ? "−" : "+"}
          </text>
        </g>
      )}
    </g>
  );
};

export { TreeNode };
