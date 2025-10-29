// Menu styles for compressed navigation display
export const MenuStyles = {
  menuContainer: {
    fontFamily: "Arial, sans-serif",
    margin: "0",
    backgroundColor: "transparent",
  },
  controls: {
    backgroundColor: "#fff",
  },
  branchLine: {
    fill: "none",
    stroke: "#cbd5e1",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
  },
  nodeLabel: {
    height: 16,
    font: "12px sans-serif",
    color: "#475569",
    backgroundColor: "transparent",
    highlightColor: "#FEF3C7",
    dominantBaseline: "middle" as const,
    hoverColor: "#1e40af",
  },
} as const;

// Compressed line colors for menu
export const MenuEdgeColors = [
  "#94a3b8", // slate
  "#cbd5e1", // lighter slate
  "#64748b", // darker slate
  "#475569", // even darker slate
];
