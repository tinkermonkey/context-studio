import type { HTMLAttributes, ReactNode } from "react";

type ChipColor = "cyan" | "amber" | "violet" | "emerald" | "rose" | "gray";

interface ChipProps extends HTMLAttributes<HTMLSpanElement> {
  color?: ChipColor;
  children: ReactNode;
  className?: string;
}

export function Chip({ color, children, className = "", ...rest }: ChipProps) {
  const classes = ["chip", color, className].filter(Boolean).join(" ");
  return (
    <span className={classes} {...rest}>
      {color && <span className="dot" />}
      {children}
    </span>
  );
}
