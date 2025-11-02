import type { LayoutConfig } from "../tree_chart/tree_data";

// Geometry constants
export const curveRadius = 14;
export const leadInRadius = 10;

// Layout configuration
export const layoutConfig: LayoutConfig = {
  spacing: {
    vertical: 6,
    horizontal: 16,
  },
  expandControls: {
    width: 16,
  },
  margins: {
    top: 10,
    left: 12,
    right: 10,
    bottom: 10,
  },
};

// Spacing between title column and definition column
export const definitionSpacing = {
  controlsWidth: 16, // Width reserved for controls between title and definition
  leftMargin: 5,     // Left margin for definition text
};

// Chart styles for SVG elements
export const chartStyles = {
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
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    //display: "none",
  },
  node: {
    backgroundColor: "#FF0000",
  },
  nodeLabel: {
    height: 20,
    font: "14px sans-serif",
    color: "#333",
    backgroundColor: "transparent",
    highlightColor: "#FEF3C7",
    dominantBaseline: "middle" as const,
    padding: "2px 4px",
    margin: "0",
    lineHeight: "16px", // 14px font + 4px padding = 18px (close to 20px with box model)
  },
  nodeDefinition: {
    font: "14px sans-serif",
    color: "#333",
    backgroundColor: "transparent",
    highlightColor: "#FEF3C7",
    padding: "5px 5px",
    lineHeight: "16px",
  },
  mainNode: {
    fill: "#5B8FF9",
    stroke: "#fff",
    strokeWidth: 1,
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
