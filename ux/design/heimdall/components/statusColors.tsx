type StatusColor = "emerald" | "amber" | "rose" | "cyan" | "violet" | "neutral";

const statusColorMap: Record<StatusColor, string> = {
  emerald: "rgb(16 185 129)",
  amber: "rgb(245 158 11)",
  rose: "rgb(244 63 94)",
  cyan: "rgb(34 211 238)",
  violet: "rgb(139 92 246)",
  neutral: "rgb(var(--canvas-fg-2))",
};

interface ChartSeries {
  name: string;
  data: number[];
  color?: StatusColor;
}

interface LineChartSeries extends ChartSeries {
  filled?: boolean;
}

interface BarChartSeries extends ChartSeries {}

// --- Babel-standalone: expose runtime values to window ---
window.statusColorMap = statusColorMap;
