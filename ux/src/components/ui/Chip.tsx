import type { HTMLAttributes, ReactNode } from "react";
import { Chip as HeimdallChip } from "@tinkermonkey/heimdall-ui";

type StatusColor = "emerald" | "amber" | "rose" | "cyan" | "violet" | "neutral";

export type ChipColor = "cyan" | "amber" | "violet" | "emerald" | "rose" | "gray";

interface ChipProps extends HTMLAttributes<HTMLSpanElement> {
  color?: ChipColor;
  children: ReactNode;
  className?: string;
}

export function Chip({ color, children, className = "", ...rest }: ChipProps) {
  const variantMap: Record<ChipColor, StatusColor> = {
    cyan: "cyan",
    amber: "amber",
    violet: "violet",
    emerald: "emerald",
    rose: "rose",
    gray: "neutral",
  };

  const variant = color ? variantMap[color] : "neutral";

  return (
    <HeimdallChip variant={variant} className={className} {...rest}>
      {children}
    </HeimdallChip>
  );
}
