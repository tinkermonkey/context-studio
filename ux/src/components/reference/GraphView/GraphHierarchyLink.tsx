/**
 * GraphHierarchyLink Component
 *
 * Renders hierarchy links in the tree layout
 */

import React from "react";
import { HierarchyLink } from "./d3TreeLayout";

interface GraphHierarchyLinkProps {
  link: HierarchyLink;
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
  onMouseEnter?: (link: HierarchyLink) => void;
  onMouseLeave?: () => void;
  isHighlighted?: boolean;
}

// Helper function to calculate intersection point with circle
const calculateCircleIntersection = (
  centerX: number,
  centerY: number,
  radius: number,
  lineStartX: number,
  lineStartY: number,
  lineEndX: number,
  lineEndY: number
): { x: number; y: number } => {
  // Calculate the direction vector from start to end
  const dx = lineEndX - lineStartX;
  const dy = lineEndY - lineStartY;
  const length = Math.sqrt(dx * dx + dy * dy);

  // Normalize the direction vector
  const unitX = dx / length;
  const unitY = dy / length;

  // Calculate the intersection point on the circle's edge
  const intersectionX = centerX - unitX * radius;
  const intersectionY = centerY - unitY * radius;

  return { x: intersectionX, y: intersectionY };
};

export const GraphHierarchyLink: React.FC<GraphHierarchyLinkProps> = ({
  link,
  sourceX,
  sourceY,
  targetX,
  targetY,
  onMouseEnter,
  onMouseLeave,
  isHighlighted = false,
}) => {
  const handleMouseEnter = () => {
    onMouseEnter?.(link);
  };

  const handleMouseLeave = () => {
    onMouseLeave?.();
  };

  // Calculate link color based on type
  const linkColor = link.type === 'subject-predicate' ? '#8B5CF6' : '#06B6D4';
  const linkWidth = isHighlighted ? 2 : 1;
  const linkOpacity = isHighlighted ? 1 : 0.6;

  // Calculate proper endpoints to show arrows outside node boundaries
  let actualSourceX = sourceX;
  let actualSourceY = sourceY;
  let actualTargetX = targetX;
  let actualTargetY = targetY;

  // For links TO predicate nodes (subject-predicate)
  if (link.type === 'subject-predicate') {
    const predicateRadius = 8 + 2; // predicate radius + stroke width
    const dataNodeRadius = 20 + 2; // data node radius + stroke width

    // Adjust source endpoint (from data node edge)
    const sourceIntersection = calculateCircleIntersection(
      sourceX, sourceY, dataNodeRadius,
      targetX, targetY, sourceX, sourceY
    );
    actualSourceX = sourceIntersection.x;
    actualSourceY = sourceIntersection.y;

    // Adjust target endpoint (to predicate node edge)
    const targetIntersection = calculateCircleIntersection(
      targetX, targetY, predicateRadius,
      sourceX, sourceY, targetX, targetY
    );
    actualTargetX = targetIntersection.x;
    actualTargetY = targetIntersection.y;
  }

  // For links FROM predicate nodes (predicate-object)
  if (link.type === 'predicate-object') {
    const predicateRadius = 8 + 2; // predicate radius + stroke width
    const dataNodeRadius = 20 + 2; // data node radius + stroke width

    // Adjust source endpoint (from predicate node edge)
    const sourceIntersection = calculateCircleIntersection(
      sourceX, sourceY, predicateRadius,
      targetX, targetY, sourceX, sourceY
    );
    actualSourceX = sourceIntersection.x;
    actualSourceY = sourceIntersection.y;

    // Adjust target endpoint (to data node edge)
    const targetIntersection = calculateCircleIntersection(
      targetX, targetY, dataNodeRadius,
      sourceX, sourceY, targetX, targetY
    );
    actualTargetX = targetIntersection.x;
    actualTargetY = targetIntersection.y;
  }

  // Choose the appropriate arrow marker
  const getArrowMarker = () => {
    if (isHighlighted) return "url(#arrowhead-highlighted)";
    return link.type === 'subject-predicate'
      ? "url(#arrowhead-subject-predicate)"
      : "url(#arrowhead-predicate-object)";
  };

  return (
    <line
      x1={actualSourceX}
      y1={actualSourceY}
      x2={actualTargetX}
      y2={actualTargetY}
      stroke={linkColor}
      strokeWidth={linkWidth}
      strokeOpacity={linkOpacity}
      markerEnd={getArrowMarker()}
      className="cursor-pointer"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    />
  );
};

export default GraphHierarchyLink;