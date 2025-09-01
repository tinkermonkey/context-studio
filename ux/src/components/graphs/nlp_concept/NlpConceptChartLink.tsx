import React from "react";

interface Coordinate {
  x: number;
  y: number;
}

interface NlpConceptChartLinkProps {
  startPoint: Coordinate;
  label: string;
  endPoints: Coordinate[];
  /** If true, the initial segment from startPoint to the branch point will prefer a vertical orientation */
  startVertical?: boolean;
  strokeWidth?: number;
  strokeColor?: string;
  fontSize?: string;
  fontFamily?: string;
}

export const NlpConceptChartLink: React.FC<NlpConceptChartLinkProps> = ({
  startPoint,
  label,
  endPoints,
  startVertical = false,
  strokeWidth = 1.25,
  strokeColor = "#000",
  fontSize = "12px",
  fontFamily = "sans-serif",
}) => {
  if (endPoints.length === 0) {
    return null;
  }

  // Calculate the branch point
  const calculateBranchPoint = (): Coordinate => {
    if (endPoints.length === 1) {
      // For single endpoint, position branch point for smooth horizontal entry
      return {
        x: endPoints[0].x - 80,
        y: endPoints[0].y,
      };
    }

    // Position branch point further left for smoother curves
    const endX = Math.min(...endPoints.map((p) => p.x));

    return {
      x: endX - 80,
      y: endPoints[0].y,
    };
  };

  // Create smooth S-curve from start to branch point
  const createSmoothCurve = (
    from: Coordinate,
    to: Coordinate,
    forceHorizontal: boolean = false,
    preferVertical: boolean = false,
  ): string => {
    const deltaX = to.x - from.x;
    const deltaY = to.y - from.y;

    // Determine whether the curve should be treated as 'horizontal' or 'vertical'.
    // preferVertical forces a vertical-style control point layout unless forceHorizontal is true.
    const isHorizontal =
      forceHorizontal || (!preferVertical && Math.abs(deltaX) > Math.abs(deltaY));

    // Create control points for smooth curve
    let controlPoint1X, controlPoint1Y, controlPoint2X, controlPoint2Y;

    if (isHorizontal) {
      controlPoint1X = from.x + deltaX * 0.5;
      controlPoint1Y = from.y;
      controlPoint2X = to.x - deltaX * 0.5;
      controlPoint2Y = to.y;
    } else {
      controlPoint1X = from.x;
      controlPoint1Y = from.y + deltaY * 0.6;
      controlPoint2X = to.x - deltaX * 1;
      controlPoint2Y = to.y;
    }

    return `M ${from.x} ${from.y} 
            C ${controlPoint1X} ${controlPoint1Y}, ${controlPoint2X} ${controlPoint2Y}, ${to.x} ${to.y}`;
  };

  const branchPoint = calculateBranchPoint();

  // Calculate label position - align horizontally with the first (topmost) endpoint
  const firstEndpoint = endPoints.reduce(
    (min, point) => (point.y < min.y ? point : min),
    endPoints[0],
  );

  const labelPosition: Coordinate = {
    x: branchPoint.x,
    y: firstEndpoint.y - 8, // Position above the first endpoint line
  };

  return (
    <g>
      {/* Main smooth curve from start to branch point */}
      <path
    d={createSmoothCurve(startPoint, branchPoint, false, startVertical)}
        stroke={strokeColor}
        strokeWidth={strokeWidth}
        fill="none"
      />

      {/* Individual smooth curves from branch point to each endpoint with horizontal final segments */}
      {endPoints.map((endPoint, index) => {
        // Create a smooth curve to a point just before the endpoint, then a horizontal line
        const preEndPoint = { x: endPoint.x - 10, y: endPoint.y };
  const branchToPreEnd = createSmoothCurve(branchPoint, preEndPoint, true, false);
        const horizontalSegment = `M ${preEndPoint.x} ${preEndPoint.y} L ${endPoint.x} ${endPoint.y}`;

        return (
          <g key={`branch-line-${index}`}>
            {/* Curved segment from branch point to near the endpoint */}
            <path
              d={branchToPreEnd}
              stroke={strokeColor}
              strokeWidth={strokeWidth}
              fill="none"
            />
            {/* Final horizontal segment into the endpoint */}
            <path
              d={horizontalSegment}
              stroke={strokeColor}
              strokeWidth={strokeWidth}
              fill="none"
              markerEnd="url(#arrowhead)"
            />
          </g>
        );
      })}

      {/* Label positioned horizontally aligned with first endpoint */}
      <text
        x={labelPosition.x}
        y={labelPosition.y}
        textAnchor="middle"
        fontSize={fontSize}
        fontFamily={fontFamily}
        fill={strokeColor}
      >
        {label}
      </text>
    </g>
  );
};