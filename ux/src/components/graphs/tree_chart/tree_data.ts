// Layout configuration
interface LayoutConfig {
  spacing: {
    vertical: number;
    horizontal: number;
  };
  expandControls?: {
    width: number;
  };
  margins: {
    top: number;
    left: number;
    right: number;
    bottom: number;
  };
}

// Chart node data structure
interface HierarchyNode {
  id: string;
  title: string;
  definition?: string;
  type?: "dataset" | "layer" | "domain" | "term";
  x: number; // X position in the chart of the top-left corner of the node block
  y: number; // Y position in the chart of the top-left corner of the node block
  width: number; // Total width of the node block
  height: number; // Total height of the node block
  depth: number; // Hierarchy depth (0 for root)
  children: HierarchyNode[];
  titleWidth?: number; // Measured width of the text label
  titleHeight?: number; // Measured height of the text label (for wrapped text)
  definitionHeight?: number; // Height of the definition box
  definitionWidth?: number; // Width of the definition box
  expanded?: boolean; // Whether the node is currently expanded
  hasChildren?: boolean; // Whether the node has children in the original data
  isHovered?: boolean; // Whether the node is currently being hovered
  childIndex?: number; // Index of the child among its siblings
}

// Abstract dimensions of the chart
interface Dimensions {
  width: number;
  height: number;
}

// Chart data structure
export interface ChartData {
  root: HierarchyNode;
  dimensions: Dimensions;
}

// Export types and data for use in other components
export type { HierarchyNode, Dimensions, LayoutConfig };
