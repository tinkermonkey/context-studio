import { chartStyles, layoutConfig, curveRadius, leadInRadius } from "./config";

/**
 * Calculate the tangent point between two circles given the center of circle 1, the radius of both circles and the x offset of circle 2
 * @param c1x Center x of circle 1
 * @param c1y Center y of circle 1
 * @param r1 Radius of circle 1
 * @param dx The horizontal distance from circle 1 center to circle 2 center (positive means circle 2 is to the right)
 * @param r2 Radius of circle 2
 * @returns The tangent point on circle 1, or null if no tangent is possible
 */
export function calculateTangentPointBetweenCircles(
  c1x: number,
  c1y: number,
  r1: number,
  dx: number,
  r2: number,
): { x: number; y: number } | null {
  if (Math.abs(dx) >= Math.max(r1, r2)) {
    // No tangent possible
    return null;
  }

  const alpha = Math.asin(dx / (r1 + r2));

  return { x: c1x + r1 * Math.sin(alpha), y: c1y + r1 * Math.cos(alpha) };
}

/**
 * Calculate how far past the perimeter of an arc a line from the center intersects
 * @param radius Arc radius
 * @param distanceFromCenter Distance from the center of the arc
 * @returns Distance to intersection point, or null if no intersection
 */
export function calculateIntersectionToArc(
  radius: number,
  distanceFromCenter: number,
): number | null {
  if (distanceFromCenter > radius) {
    // No intersection
    return null;
  }

  const alpha = Math.asin(distanceFromCenter / radius);

  const d = radius - radius * Math.cos(alpha);
  return d;
}

/**
 * Create an SVG path string for a tree node connection
 * @param parentX - X position of the parent node
 * @param parentY - Y position of the parent node
 * @param parentHeight - Height of the parent node (for proper connection point)
 * @param nodeX - X position of the target node
 * @param nodeY - Y position of the target node
 * @param nodeWidth - Width of the target node
 * @param nodeHeight - Height of the target node (for proper connection point)
 * @returns SVG path string
 */
export const createNodeSpinePath = (
  parentX: number,
  parentY: number,
  parentHeight: number,
  nodeX: number,
  nodeY: number,
  nodeWidth: number,
  nodeHeight: number,
): string => {
  const halfStroke = chartStyles.branchLine.strokeWidth / 2;
  let startX = parentX - leadInRadius;
  let startY = parentY + parentHeight;
  const endX = nodeX + nodeWidth;
  const endY = nodeY + nodeHeight;

  // If this is the first level of nodes, adjust the lead-in start point
  if (parentY <= layoutConfig.margins.top) {
    startX = parentX;
    return `M ${startX} ${startY}
          L ${parentX} ${endY - curveRadius}
          Q ${parentX} ${endY} ${parentX + curveRadius} ${endY}
          L ${endX} ${endY}`;
  }

  // Calculate the starting point as tangent to the parent node's curve
  const c1 = {
    x: parentX,
    y: parentY + parentHeight - curveRadius,
  };
  const startTangent = calculateTangentPointBetweenCircles(
    c1.x,
    c1.y,
    curveRadius + halfStroke,
    -leadInRadius,
    leadInRadius + halfStroke,
  );
  if (startTangent) {
    startX = startTangent.x;
    startY = startTangent.y;
  }

  return `M ${startX} ${startY}
          A ${leadInRadius} ${leadInRadius} 0 0 1 ${parentX} ${parentY + parentHeight + leadInRadius}
          L ${parentX} ${endY - curveRadius}
          Q ${parentX} ${endY} ${parentX + curveRadius} ${endY}
          L ${endX} ${endY}`;
};

/**
 * Create the svg path for the menu node background
 * @param x
 * @param y
 * @param labelWidth
 * @param labelHeight
 * @returns
 */
export const createMenuNodeBackgroundPath = (
  nodeX: number,
  nodeY: number,
  nodeWidth: number,
  nodeHeight: number,
  childIndex: number = 0,
): string => {
  const strokeWidth = chartStyles.branchLine.strokeWidth;
  const halfStroke = chartStyles.branchLine.strokeWidth / 2;
  const topLeft = {
    x: nodeX - curveRadius - halfStroke,
    y: nodeY - 0 + halfStroke,
  };
  const bottomRight = {
    x: nodeX + nodeWidth,
    y: nodeY + nodeHeight - halfStroke,
  };

  if (childIndex === 0) {
    // Calculate the starting point as tangent to the parent node's curve
    const dx =
      calculateIntersectionToArc(
        leadInRadius + strokeWidth,
        leadInRadius - halfStroke,
      ) || 0;
    return `M ${topLeft.x - dx} ${topLeft.y}
          L ${bottomRight.x} ${topLeft.y}
          L ${bottomRight.x} ${bottomRight.y}
          L ${topLeft.x + curveRadius + halfStroke} ${bottomRight.y}
          Q ${topLeft.x - halfStroke} ${bottomRight.y + halfStroke} ${topLeft.x} ${bottomRight.y - curveRadius}
          L ${topLeft.x} ${topLeft.y + leadInRadius}
          A ${leadInRadius + halfStroke} ${leadInRadius + halfStroke} 0 0 0 ${topLeft.x - dx} ${topLeft.y}
          Z`;
  }

  // Calculate the starting point as tangent to the parent node's curve
  const dy =
    calculateIntersectionToArc(
      curveRadius + strokeWidth,
      curveRadius - halfStroke,
    ) || 0;

  return `M ${topLeft.x + curveRadius - halfStroke} ${topLeft.y}
          L ${bottomRight.x} ${topLeft.y}
          L ${bottomRight.x} ${bottomRight.y}
          L ${topLeft.x + curveRadius + halfStroke} ${bottomRight.y}
          Q ${topLeft.x - halfStroke} ${bottomRight.y + halfStroke} ${topLeft.x} ${bottomRight.y - curveRadius}
          L ${topLeft.x} ${topLeft.y - dy}
          A ${curveRadius + halfStroke} ${curveRadius + halfStroke} 0 0 0 ${topLeft.x + curveRadius - halfStroke} ${topLeft.y}
          Z`;
};
