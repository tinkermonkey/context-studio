import { StatTile as HeimdallStatTile, type StatColor } from "@tinkermonkey/heimdall-ui";

interface StatTileProps {
  label: string;
  value: string | number;
  color?: StatColor;
  sub?: string;
  className?: string;
}

export function StatTile({ label, value, color = "cyan", sub, className }: StatTileProps) {
  if (!sub) {
    return (
      <HeimdallStatTile
        label={label}
        value={value}
        color={color}
        className={className}
      />
    );
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
