import React, { useEffect, useState } from "react";
import {
  chartStyles,
  EdgeColors,
  layoutConfig,
  definitionSpacing,
} from "./config";
import { createNodeSpinePath, createMenuNodeBackgroundPath } from "./geometry";
import type { HierarchyNode } from "../tree_chart/tree_data";
import { ChevronDown, ChevronUp } from "lucide-react";

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
  const parentHeight = parentNode?.height ?? 0;

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

  const handleExpandToggleClick = () => {
    if (hasChildren && onToggle) {
      onToggle(node.id);
    }
  };

  const handleNodeClick = () => {
    if (onNodeClick) {
      onNodeClick(node);
    }
  };

  const [isHovered, setIsHovered] = useState(false);
  const [isExpandControlHovered, setIsExpandControlHovered] = useState(false);
  const [isDefinitionDisplayed, setIsDefinitionDisplayed] = useState(
    !!(node.definition && node.definitionWidth && node.definitionWidth > 0),
  );

  useEffect(() => {
    setIsDefinitionDisplayed(
      !!(node.definition && node.definitionWidth && node.definitionWidth > 0),
    );
  }, [node.definition, node.definitionWidth]);

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

      {/* Background for node */}
      <g
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        style={{ cursor: onNodeClick ? "pointer" : "default" }}
        onClick={handleNodeClick}
      >
        {/*}
        <circle
          cx={nodeX}
          cy={nodeY}
          r={2}
          fill={isHighlighted ? "#ff5900" : nodeColor}
        />
        */}

        <rect
          className="tree-node-bg"
          x={nodeX}
          y={nodeY}
          width={node.width}
          height={node.height}
          fill={"transparent"}
          fillOpacity={0.2}
          style={{ transition: "fill 0.1s ease-in-out" }}
        />

        <path
          className="tree-node-bg"
          d={createMenuNodeBackgroundPath(
            nodeX,
            nodeY,
            (isDefinitionDisplayed ? node.width : node.titleWidth) || 0,
            node.height || 0,
            node.childIndex,
          )}
          fill={nodeColor}
          fillOpacity={
            isHovered || isHighlighted ? 0.5 : isDefinitionDisplayed ? 0 : 0.1
          }
          style={{ transition: "fill 0.1s ease-in-out" }}
        />

        {/* Node title using foreignObject for text wrapping */}
        <foreignObject
          x={nodeX}
          y={nodeY + node.height - (node.titleHeight || 0)}
          width={node.titleWidth}
          height={node.titleHeight}
        >
          <div
            className="tree-node-label"
            style={{
              font: chartStyles.nodeLabel.font,
              color: chartStyles.nodeLabel.color,
              padding: chartStyles.nodeLabel.padding,
              margin: chartStyles.nodeLabel.margin,
              lineHeight: chartStyles.nodeLabel.lineHeight,
              width: `${node.titleWidth}px`,
              maxWidth: `${node.titleWidth}px`,
              wordWrap: "break-word",
              overflowWrap: "break-word",
              hyphens: "auto",
              boxSizing: "border-box",
              backgroundColor: chartStyles.nodeLabel.backgroundColor,
            }}
          >
            {node.title}
          </div>
        </foreignObject>

        {/* Node definition using foreignObject for text wrapping */}
        {isDefinitionDisplayed && (
          <foreignObject
            className="tree-node-definition-container"
            x={
              nodeX +
              (node.titleWidth || 0) +
              definitionSpacing.controlsWidth +
              (layoutConfig.expandControls?.width || 0) +
              definitionSpacing.leftMargin
            }
            y={nodeY + node.height - (node.definitionHeight || 0)}
            width={node.definitionWidth}
            height={node.definitionHeight || 0}
          >
            <div
              className="tree-node-definition"
              style={{
                width: node.definitionWidth,
                height: node.definitionHeight,
                borderRadius: "4px",
                font: chartStyles.nodeDefinition.font,
                color: chartStyles.nodeDefinition.color,
                padding: chartStyles.nodeDefinition.padding,
                lineHeight: chartStyles.nodeDefinition.lineHeight,
                backgroundColor: chartStyles.nodeDefinition.backgroundColor,
                wordWrap: "break-word",
                overflowWrap: "break-word",
                hyphens: "auto",
                boxSizing: "border-box",
              }}
            >
              {node.definition}
            </div>
          </foreignObject>
        )}
      </g>

      {/* Expand/collapse indicator for nodes with children */}
      {hasChildren && (
        <g
          className="tree-expand-controls"
          onClick={handleExpandToggleClick}
          onMouseEnter={() => setIsExpandControlHovered(true)}
          onMouseLeave={() => setIsExpandControlHovered(false)}
          style={{ cursor: "pointer" }}
          transform={`translate(${nodeX + (node.titleWidth || 0)} ${nodeY})`}
        >
          <rect
            className="tree-expand-controls-bg"
            x={0}
            y={chartStyles.branchLine.strokeWidth / 2}
            width={layoutConfig.expandControls?.width || 0}
            height={node.height - chartStyles.branchLine.strokeWidth || 0}
            fill={isExpandControlHovered ? `#DDD` : `transparent`}
            stroke={`none`}
            style={{ transition: "fill 0.2s ease-in-out" }}
          />
          {/** Expand/Collapse Icon, the y adjustment is purely for the icon centering and should be static */}
          <foreignObject
            x={0}
            y={Math.max(
              (node.height - (layoutConfig.expandControls?.width || 0)) / 2,
              2,
            )}
            width={layoutConfig.expandControls?.width || 0}
            height={layoutConfig.expandControls?.width}
          >
            {isExpanded ? (
              <ChevronUp
                size={layoutConfig.expandControls?.width || 16}
                color={nodeColor}
              />
            ) : (
              <ChevronDown
                size={layoutConfig.expandControls?.width || 16}
                color={nodeColor}
              />
            )}
          </foreignObject>
        </g>
      )}

      {/* Branch line from parent to this node */}
      {parentNode && (
        <path
          d={createNodeSpinePath(
            parentX,
            parentY,
            parentHeight,
            nodeX,
            nodeY,
            (node.titleWidth || 0) + (layoutConfig.expandControls?.width || 0),
            node.height || 0,
          )}
          style={{
            ...chartStyles.branchLine,
            stroke: nodeColor,
          }}
        />
      )}
    </g>
  );
};

export { TreeMenuNode as TreeNode };
