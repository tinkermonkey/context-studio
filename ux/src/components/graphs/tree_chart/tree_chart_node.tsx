import React, { useState } from "react";
import { ChartStyles, EdgeColors } from "./tree_chart_styles";
import { createNodePath } from "./tree_chart_utils";
import type { HierarchyNode } from "./tree_data";
import { CircleArrowRight } from "lucide-react";

interface TreeChartNodeProps {
  node: HierarchyNode;
  parentNode?: HierarchyNode;
  onToggle?: (nodeId: string) => void;
  onNodeClick?: (node: HierarchyNode) => void;
  onNodeHover?: (nodeId: string | null) => void;
  highlightedTermId?: string;
  enableTransitions?: boolean;
}

const TreeChartNode: React.FC<TreeChartNodeProps> = ({
  node,
  parentNode,
  onToggle,
  onNodeClick,
  onNodeHover,
  highlightedTermId,
  enableTransitions = false,
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

  // Use layout-calculated hover state for size changes
  const layoutIsHovered = node.isHovered ?? false;

  // Transition style - only apply when enableTransitions is true
  const transitionStyle = enableTransitions ? "all 0.2s ease-in-out" : "none";

  return (
    <g style={{ transition: transitionStyle }}>
      {/* Render children recursively only if expanded */}
      {isExpanded &&
        node.children.map((child, index) => (
          <TreeChartNode
            key={child.id || index}
            node={child}
            parentNode={node}
            onToggle={onToggle}
            onNodeClick={onNodeClick}
            onNodeHover={onNodeHover}
            highlightedTermId={highlightedTermId}
            enableTransitions={enableTransitions}
          />
        ))}

      {/* Node label */}
      <g
        onMouseEnter={() => {
          setIsHovered(true);
          if (onNodeHover) {
            onNodeHover(node.id);
          }
        }}
        onMouseLeave={() => {
          setIsHovered(false);
          if (onNodeHover) {
            onNodeHover(null);
          }
        }}
      >
        {/* Transparent hover target rectangle - covers entire node area */}
        <rect
          className="tree-node-hover-mask"
          width={labelWidth + 25 + definitionWidth}
          height={
            Math.max(ChartStyles.nodeLabel.height + 8, definitionHeight + 8) +
            (layoutIsHovered ? 12 : -4)
          }
          fill="transparent"
          style={{
            pointerEvents: "all",
            transition: transitionStyle,
            transform: `translate(${nodeX - 16}px, ${nodeY - ChartStyles.nodeLabel.height - 4 - (layoutIsHovered ? 8 : 0)}px)`,
          }}
        />

        {/* Background rectangle for text */}
        <rect
          className="tree-node-label-bg"
          width={labelWidth + 18 + (layoutIsHovered ? 8 : 0)}
          height={ChartStyles.nodeLabel.height + (layoutIsHovered ? 4 : 0)}
          fill={
            isHighlighted
              ? ChartStyles.nodeLabel.highlightColor
              : ChartStyles.nodeLabel.backgroundColor
          }
          rx={2}
          style={{
            transition: transitionStyle,
            transform: `translate(${nodeX - 4 - (layoutIsHovered ? 2 : 0)}px, ${nodeY - ChartStyles.nodeLabel.height - (layoutIsHovered ? 2 : 0)}px)`,
          }}
        />
        <text
          className="tree-node-label"
          style={{
            ...ChartStyles.nodeLabel,
            transition: transitionStyle,
            transform: `translate(${nodeX}px, ${nodeY - ChartStyles.nodeLabel.height / 2}px)`,
            //fontWeight: isHighlighted ? "bold" : "normal",
          }}
        >
          {node.title}
        </text>

        {/* Definition using foreignObject */}
        {node.definition && (
          <foreignObject
            className="tree-node-definition-container"
            width={definitionWidth}
            height={definitionHeight}
            style={{
              transition: transitionStyle,
              transform: `translate(${nodeX + labelWidth + 15}px, ${nodeY - ChartStyles.nodeLabel.height}px)`,
            }}
          >
            <div
              className="tree-node-definition"
              style={{
                width: definitionWidth,
                height: definitionHeight,
                borderRadius: "4px",
                ...ChartStyles.nodeDefinition,
                backgroundColor: isHighlighted
                  ? ChartStyles.nodeDefinition.highlightColor
                  : ChartStyles.nodeDefinition.backgroundColor,
                transition: transitionStyle,
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
            className="tree-navigation-controls"
            onClick={handleNodeTextClick}
            style={{
              cursor: "pointer",
              transform: `translate(${nodeX + labelWidth}px, ${nodeY - 18}px)`,
              transition: transitionStyle,
            }}
          >
            <CircleArrowRight
              size={16}
              className="text-blue-500 hover:text-blue-700"
              fill={ChartStyles.controls.backgroundColor}
            />
          </g>
        )}

        {/* Branch line from parent to this node */}
        {parentNode && (
          <path
            className="tree-spine"
            d={createNodePath(parentX, parentY, nodeX + labelWidth, nodeY)}
            style={{
              ...ChartStyles.branchLine,
              stroke: nodeColor,
              transition: transitionStyle,
              pointerEvents: "none",
            }}
          />
        )}

        {/* Expand/collapse indicator for nodes with children */}
        {hasChildren && (
          <g
            className="tree-expand-controls"
            onClick={handleClick}
            style={{
              cursor: "pointer",
              transform: `translate(${nodeX - 8}px, ${nodeY}px)`,
              transition: transitionStyle,
            }}
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
    </g>
  );
};

export { TreeChartNode };
