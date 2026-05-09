import type { ReactNode } from "react";

type ChipColor = "cyan" | "amber" | "violet" | "emerald" | "rose" | "gray";

interface ChipProps {
  color?: ChipColor;
  children: ReactNode;
  className?: string;
}

export function Chip({ color, children, className = "" }: ChipProps) {
  const classes = ["chip", color, className].filter(Boolean).join(" ");
  return <span className={classes}>{children}</span>;
}
