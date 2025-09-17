/**
 * GraphNode Component
 *
 * SVG-based node component for graph visualization
 */

import React from "react";
import { UnifiedNode, SOURCE_METADATA } from "@/api/types/unified";

interface GraphNodeProps {
  node: UnifiedNode;
  x: number;
  y: number;
  radius?: number;
  onClick?: (node: UnifiedNode) => void;
  onMouseEnter?: (node: UnifiedNode) => void;
  onMouseLeave?: () => void;
  isHighlighted?: boolean;
}

export const GraphNode: React.FC<GraphNodeProps> = ({
  node,
  x,
  y,
  radius = 20,
  onClick,
  onMouseEnter,
  onMouseLeave,
  isHighlighted = false,
}) => {
  const sourceMetadata = SOURCE_METADATA[node.source] || {
    label: node.source,
    color: "gray",
    description: "",
  };

  // Map flowbite colors to actual hex colors for SVG
  const colorMap: Record<string, string> = {
    blue: "#3B82F6",
    orange: "#F97316",
    purple: "#8B5CF6",
    red: "#EF4444",
    gray: "#6B7280",
  };

  const nodeColor = colorMap[sourceMetadata.color] || colorMap.gray;
  const strokeColor = isHighlighted ? "#1F2937" : nodeColor;
  const strokeWidth = isHighlighted ? 3 : 2;

  const handleClick = () => {
    onClick?.(node);
  };

  const handleMouseEnter = () => {
    onMouseEnter?.(node);
  };

  const handleMouseLeave = () => {
    onMouseLeave?.();
  };

  // Truncate long titles reasonably
  const truncatedTitle = node.title.length > 15 ? `${node.title.substring(0, 15)}...` : node.title;

  return (
    <g
      transform={`translate(${x}, ${y})`}
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={{
        cursor: onClick ? 'pointer' : 'default',
        transition: 'transform 0.1s ease-out'
      }}
    >
      {/* Node shadow for depth */}
      <circle
        r={radius}
        cx={2}
        cy={2}
        fill="#00000015"
        opacity={0.3}
      />

      {/* Node circle */}
      <circle
        r={radius}
        fill={nodeColor}
        stroke={strokeColor}
        strokeWidth={strokeWidth}
        opacity={0.9}
        className="transition-all duration-200 hover:opacity-100 hover:stroke-width-4"
      />

      {/* Node label - always visible */}
      <g>
        {/* Label background for readability */}
        <rect
          x={-truncatedTitle.length * 3.5}
          y={radius + 8}
          width={truncatedTitle.length * 7}
          height={16}
          fill="white"
          fillOpacity={0.9}
          stroke="#E5E7EB"
          strokeWidth={1}
          rx={4}
          className="pointer-events-none"
        />
        <text
          y={radius + 18}
          textAnchor="middle"
          fontSize="11"
          fill="#374151"
          className="pointer-events-none select-none font-medium"
        >
          {truncatedTitle}
        </text>
      </g>

      {/* Confidence score indicator */}
      {node.confidence_score && node.confidence_score < 1 && (
        <text
          y={-radius - 8}
          textAnchor="middle"
          fontSize="10"
          fill="#6B7280"
          className="pointer-events-none select-none"
        >
          {Math.round(node.confidence_score * 100)}%
        </text>
      )}
    </g>
  );
};

export default GraphNode;