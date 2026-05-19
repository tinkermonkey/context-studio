import type { CSSProperties } from "react";

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  style?: CSSProperties;
  className?: string;
}

export function Skeleton({ width, height = "1em", style, className }: SkeletonProps) {
  return (
    <div
      className={className}
      style={{
        width,
        height,
        background: "rgb(var(--canvas-border))",
        borderRadius: "var(--radius-md)",
        animation: "skeleton-shimmer 1.4s ease infinite",
        ...style,
      }}
    />
  );
}
