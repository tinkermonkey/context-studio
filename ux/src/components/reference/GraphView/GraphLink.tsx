/**
 * GraphLink Component
 *
 * SVG-based link component for graph visualization
 */

import React from "react";
import { UnifiedSearchLink, SOURCE_METADATA } from "@/api/types/unified";

interface GraphLinkProps {
  link: UnifiedSearchLink;
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
  sourceRadius?: number;
  targetRadius?: number;
  onClick?: (link: UnifiedSearchLink) => void;
  onMouseEnter?: (link: UnifiedSearchLink) => void;
  onMouseLeave?: () => void;
  isHighlighted?: boolean;
}

export const GraphLink: React.FC<GraphLinkProps> = ({
  link,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourceRadius = 20,
  targetRadius = 20,
  onClick,
  onMouseEnter,
  onMouseLeave,
  isHighlighted = false,
}) => {
  const sourceMetadata = SOURCE_METADATA[link.source] || {
    label: link.source,
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

  const linkColor = colorMap[sourceMetadata.color] || colorMap.gray;

  // Calculate the direction vector and normalize it
  const dx = targetX - sourceX;
  const dy = targetY - sourceY;
  const length = Math.sqrt(dx * dx + dy * dy);

  if (length === 0) return null; // Avoid division by zero

  const unitX = dx / length;
  const unitY = dy / length;

  // Calculate start and end points accounting for node radii
  const startX = sourceX + unitX * sourceRadius;
  const startY = sourceY + unitY * sourceRadius;
  const endX = targetX - unitX * targetRadius;
  const endY = targetY - unitY * targetRadius;

  // Calculate midpoint for label
  const midX = (startX + endX) / 2;
  const midY = (startY + endY) / 2;

  // Use consistent thin link width regardless of weight
  const baseWidth = 1.5;
  const strokeWidth = isHighlighted ? 3 : baseWidth;
  const opacity = isHighlighted ? 1 : 0.4;

  const handleClick = () => {
    onClick?.(link);
  };

  const handleMouseEnter = () => {
    onMouseEnter?.(link);
  };

  const handleMouseLeave = () => {
    onMouseLeave?.();
  };

  return (
    <g
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={{ cursor: onClick ? 'pointer' : 'default' }}
    >
      {/* Link shadow for depth */}
      <line
        x1={startX + 1}
        y1={startY + 1}
        x2={endX + 1}
        y2={endY + 1}
        stroke="#00000015"
        strokeWidth={strokeWidth + 1}
        opacity={opacity * 0.5}
      />

      {/* Link line */}
      <line
        x1={startX}
        y1={startY}
        x2={endX}
        y2={endY}
        stroke={linkColor}
        strokeWidth={strokeWidth}
        opacity={opacity}
        strokeLinecap="round"
        className="transition-all duration-200 hover:opacity-100"
        markerEnd={isHighlighted ? "url(#arrowhead-highlighted)" : "url(#arrowhead)"}
      />

      {/* Link label (predicate) - always visible like node titles */}
      <g>
        {/* Truncate predicate similar to node titles */}
        {(() => {
          const truncatedPredicate = link.predicate.length > 12 ? `${link.predicate.substring(0, 12)}...` : link.predicate;

          return (
            <>
              {/* Label background for readability - matching node title style */}
              <rect
                x={midX - (truncatedPredicate.length * 3.5)}
                y={midY - 8}
                width={truncatedPredicate.length * 7}
                height={16}
                fill="white"
                fillOpacity={0.9}
                stroke="#E5E7EB"
                strokeWidth={1}
                rx={4}
                className="pointer-events-none"
              />
              <text
                x={midX}
                y={midY + 2}
                textAnchor="middle"
                fontSize="11"
                fill="#374151"
                className="pointer-events-none select-none font-medium"
              >
                {truncatedPredicate}
              </text>
            </>
          );
        })()}

        {/* Weight indicator - only show when highlighted */}
        {isHighlighted && link.weight && link.weight !== 1 && (
          <text
            x={midX}
            y={midY + 20}
            textAnchor="middle"
            fontSize="8"
            fill="#6B7280"
            className="pointer-events-none select-none"
          >
            {link.weight.toFixed(2)}
          </text>
        )}
      </g>
    </g>
  );
};

export default GraphLink;