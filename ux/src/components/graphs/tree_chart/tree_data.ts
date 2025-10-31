// Layout configuration
interface LayoutConfig {
  spacing: {
    vertical: number;
    horizontal: number;
  };
  margins: {
    top: number;
    left: number;
    right: number;
    bottom: number;
  };
}

// Chart data types
interface HierarchyNode {
  id: string;
  title: string;
  definition?: string;
  type?: "dataset" | "layer" | "domain" | "term";
  x?: number;
  y?: number;
  depth: number;
  children: HierarchyNode[];
  textWidth?: number; // Measured width of the text label
  definitionHeight?: number; // Height of the definition box
  definitionWidth?: number; // Width of the definition box
  expanded?: boolean; // Whether the node is currently expanded
  hasChildren?: boolean; // Whether the node has children in the original data
  isHovered?: boolean; // Whether the node is currently being hovered
  childIndex?: number; // Index of the child among its siblings
}

interface Dimensions {
  width: number;
  height: number;
}

export interface ChartData {
  root: HierarchyNode;
  dimensions: Dimensions;
}

// Export types and data for use in other components
export type { HierarchyNode, Dimensions, LayoutConfig };
