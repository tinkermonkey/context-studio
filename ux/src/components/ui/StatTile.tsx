import type { ReactNode } from "react";

type StatColor = "cyan" | "violet" | "amber" | "emerald";

interface StatTileProps {
  label: string;
  value: ReactNode;
  color?: StatColor;
  sub?: string;
}

export function StatTile({ label, value, color = "cyan", sub }: StatTileProps) {
  return (
    <div className={`stat stat-${color}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}
