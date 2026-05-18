import { StatTile as HeimdallStatTile, type StatColor } from "@tinkermonkey/heimdall-ui";

interface StatTileProps {
  label: string;
  value: string | number;
  color?: StatColor;
  sub?: string;
  className?: string;
}

export function StatTile({ label, value, color = "cyan", sub, className }: StatTileProps) {
  return (
    <HeimdallStatTile
      label={label}
      value={value}
      color={color}
      delta={
        sub
          ? {
              value: 0,
              label: sub,
              direction: "up" as const,
            }
          : undefined
      }
      className={className}
    />
  );
}
