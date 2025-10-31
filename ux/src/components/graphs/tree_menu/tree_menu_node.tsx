import React, { useState } from "react";
import { ChartStyles, EdgeColors } from "./tree_menu_styles";
import {
  createNodePath,
  createMenuNodeBackgroundPath,
} from "../tree_chart/tree_chart_utils";
import type { HierarchyNode } from "../tree_chart/tree_data";
import { ChevronDown, ChevronUp } from "lucide-react";
import { defaultLayoutConfig } from "./tree_menu_layout";

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
  const labelWidth = node.textWidth ?? node.title.length * 6;

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
  const [isExpandControlHovered, setIsExpandControlHovered] = useState(false);

  return (
    <g>
      {/* Render children recursively only if expanded */}
      {isExpanded &&
        node.children.map((child, index) => {
          child.childIndex = index;
          return (
            <TreeMenuNode
              key={child.id || index}
              node={child}
              parentNode={node}
              onToggle={onToggle}
              onNodeClick={onNodeClick}
              highlightedTermId={highlightedTermId}
            />
          );
        })}

      {/* Node label */}
      <g
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        style={{ cursor: onNodeClick ? "pointer" : "default" }}
      >
        {/* Background for node */}
        <path
          className="tree-node-bg"
          d={createMenuNodeBackgroundPath(
            nodeX,
            nodeY,
            labelWidth,
            ChartStyles.nodeLabel.height,
            node.childIndex || 0,
            defaultLayoutConfig,
            ChartStyles,
          )}
          fill={isHovered ? nodeColor : "transparent"}
          fillOpacity={0.2}
          style={{ transition: "fill 0.1s ease-in-out" }}
        />

        {/* Node title */}
        <text
          className="tree-node-label"
          x={nodeX - 4}
          y={nodeY - ChartStyles.nodeLabel.height / 2}
          style={{
            ...ChartStyles.nodeLabel,
            //fontWeight: isHighlighted ? "bold" : "normal",
          }}
        >
          {node.title}
        </text>
      </g>

      {/* Branch line from parent to this node */}
      {parentNode && (
        <path
          d={createNodePath(parentX, parentY, nodeX + labelWidth + 16, nodeY)}
          style={{
            ...ChartStyles.branchLine,
            stroke: nodeColor,
          }}
        />
      )}

      {/* Expand/collapse indicator for nodes with children */}
      {hasChildren && (
        <g
          className="tree-expand-controls"
          onClick={handleClick}
          onMouseEnter={() => setIsExpandControlHovered(true)}
          onMouseLeave={() => setIsExpandControlHovered(false)}
          style={{ cursor: "pointer" }}
          transform={`translate(${nodeX + labelWidth} ${nodeY - ChartStyles.nodeLabel.height - 4})`}
        >
          <rect
            className="tree-expand-controls-bg"
            x={0}
            y={0}
            width={16}
            height={22}
            fill={isExpandControlHovered ? `#DDD` : `none`}
            stroke={`none`}
            strokeWidth={2}
          />
          <foreignObject x={0} y={3} width={16} height={16}>
            {isExpanded ? (
              <ChevronUp size={16} color={nodeColor} />
            ) : (
              <ChevronDown size={16} color={nodeColor} />
            )}
          </foreignObject>
        </g>
      )}
    </g>
  );
};

export { TreeMenuNode as TreeNode };
