import { ReactNode } from "react";
import { StatTile as HeimdallStatTile } from "@tinkermonkey/heimdall-ui";

type StatusColor = "cyan" | "violet" | "amber" | "emerald";

type StatColor = Extract<StatusColor, "cyan" | "violet" | "amber" | "emerald">;

interface StatTileProps {
  label: string;
  value: string | number | ReactNode;
  color?: StatColor;
  sub?: string;
  className?: string;
}

export function StatTile({ label, value, color = "cyan", sub, className }: StatTileProps) {
  const isStringOrNumber = typeof value === "string" || typeof value === "number";

  if (!sub && isStringOrNumber) {
    return <HeimdallStatTile label={label} value={value} color={color} className={className} />;
  }

  return (
    <div className={["stat-tile", `stat-tile--${color}`, className].filter(Boolean).join(" ")}>
      <div className="stat-tile__label">{label}</div>
      <div className="stat-tile__value">{value}</div>
      <div className="stat-tile__meta">
        <span className="stat-tile__label-secondary">{sub}</span>
      </div>
    </div>
  );
}
