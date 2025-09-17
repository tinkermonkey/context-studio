/**
 * GraphPredicateNode Component
 *
 * Renders predicate nodes in the tree layout
 */

import React from "react";
import { HierarchyNode } from "./d3TreeLayout";

interface GraphPredicateNodeProps {
  node: HierarchyNode;
  x: number;
  y: number;
  radius?: number;
  onMouseEnter?: (node: HierarchyNode) => void;
  onMouseLeave?: () => void;
  isHighlighted?: boolean;
}

export const GraphPredicateNode: React.FC<GraphPredicateNodeProps> = ({
  node,
  x,
  y,
  radius = 8,
  onMouseEnter,
  onMouseLeave,
  isHighlighted = false,
}) => {
  if (node.type !== 'predicate') {
    return null;
  }

  const handleMouseEnter = () => {
    onMouseEnter?.(node);
  };

  const handleMouseLeave = () => {
    onMouseLeave?.();
  };

  return (
    <g>
      {/* Predicate node circle */}
      <circle
        cx={x}
        cy={y}
        r={radius}
        fill="#6366F1"
        stroke={isHighlighted ? "#4F46E5" : "#4338CA"}
        strokeWidth={isHighlighted ? 2 : 1}
        opacity={0.8}
        className="cursor-pointer"
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      />

      {/* Predicate label */}
      <text
        x={x}
        y={y + radius + 12}
        textAnchor="middle"
        fontSize="10"
        fill="#4338CA"
        className="pointer-events-none select-none font-medium"
      >
        {node.predicate}
      </text>
    </g>
  );
};

export default GraphPredicateNode;