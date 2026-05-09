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
    <div className="stat" data-color={color}>
      <div className="label">{label}</div>
      <div className="num">{value}</div>
      {sub && <div className="meta">{sub}</div>}
    </div>
  );
}
