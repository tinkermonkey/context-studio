// Chart styles for SVG elements
export const ChartStyles = {
  chartContainer: {
    fontFamily: "Arial, sans-serif",
    margin: "0",
    backgroundColor: "transparent",
  },
  controls: {
    backgroundColor: "#fff",
  },
  branchLine: {
    fill: "none",
    stroke: "#f39c12",
    strokeWidth: 3,
    strokeLinecap: "round" as const,
  },
  nodeLabel: {
    height: 20,
    font: "14px sans-serif",
    color: "#333",
    backgroundColor: "transparent",
    highlightColor: "#FEF3C7",
    dominantBaseline: "middle" as const,
  },
  nodeDefinition: {
    font: "14px sans-serif",
    color: "#333",
    backgroundColor: "transparent",
    highlightColor: "#FEF3C7",
    padding: "5px 5px",
  },
  mainNode: {
    fill: "#4a90e2",
    stroke: "#fff",
    strokeWidth: 2,
    rx: 3,
  },
} as const;

// Line Colors
export const EdgeColors = [
  "#5B8FF9", // blue
  "#F6BD16", // yellow
  "#5AD8A6", // green
  "#945FB9", // purple
  "#E86452", // red
  "#6DC8EC", // cyan
  "#FF99C3", // pink
  "#1E9493", // teal
  "#FF9845", // orange
  "#5D7092", // gray
];
