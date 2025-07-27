import type {
  HierarchyNode,
  Dimensions,
  LayoutConfig,
  ChartData,
} from "./tree_data";
import { measureTextWidth, getTextOptionsFromStyles } from "./tree_chart_utils";

// Default layout configuration
export const defaultLayoutConfig: LayoutConfig = {
  spacing: {
    vertical: 40,
    horizontal: 40,
    nodeHeight: 20,
  },
  margins: {
    top: 30,
    left: 50,
  },
};

// Function to recalculate layout with external expanded state (using Map<string, boolean>)
export type ExpandState = Map<string, boolean>;

const defaultExpandState = false
export function toggleExpandState(
  expandState: ExpandState,
  nodeId: string,
): ExpandState {
  const newState = new Map(expandState);
  if (newState.has(nodeId)) {
    newState.set(nodeId, !newState.get(nodeId));
  } else {
    newState.set(nodeId, !defaultExpandState);
  }
  return newState;
}

// Text measurement cache to avoid recalculating widths for the same text
// Font changes will require a complete chart redraw, so we only cache by text content
class TextMeasurementCache {
  private cache = new Map<string, number>();
  private textOptions = getTextOptionsFromStyles();

  // Get cached width or measure and cache it using current font styles
  getTextWidth(text: string): number {
    if (this.cache.has(text)) {
      return this.cache.get(text)!;
    }

    const width = measureTextWidth(text, this.textOptions);
    this.cache.set(text, width);
    return width;
  }

  // Set a cached value (useful for preserving existing measurements)
  setCachedWidth(text: string, width: number): void {
    this.cache.set(text, width);
  }

  // Clear the cache (useful for testing or font changes)
  clear(): void {
    this.cache.clear();
  }

  // Get cache size for debugging
  size(): number {
    return this.cache.size;
  }
}

// Global cache instance
const textWidthCache = new TextMeasurementCache();

// Helper function to calculate maximum depth of the tree
export function calculateMaxDepth(
  node: HierarchyNode,
  currentDepth = 0,
): number {
  if (!node.children || node.children.length === 0) {
    return currentDepth;
  }

  return Math.max(
    ...node.children.map((child) => calculateMaxDepth(child, currentDepth + 1)),
  );
}

// Function to toggle node expansion and recalculate layout with optimized text width preservation
export function toggleNodeExpansion(
  expandState: ExpandState,
  nodeId: string,
  nodeExpanded: boolean,
) {
  expandState.set(nodeId, nodeExpanded);
}

// Helper function to calculate layout while preserving expanded states and text widths
export function calculateLayout(
  chartData: ChartData,
  expandState: ExpandState,
  config: LayoutConfig = defaultLayoutConfig,
  existingTextWidths?: Map<string, number>,
): ChartData {
  let maxY = config.margins.top;

  console.log("Calculating layout with expand state:", expandState);

  // Pre-populate cache with existing text widths to avoid remeasurement
  if (existingTextWidths) {
    existingTextWidths.forEach((width, text) => {
      // Pre-populate the cache with existing measurements
      textWidthCache.setCachedWidth(text, width);
    });
  }

  // Calculate max text width using cached measurements
  function collectLabels(node: HierarchyNode, labels: string[] = []): string[] {
    labels.push(node.title);
    if (node.children) {
      node.children.forEach((child) => collectLabels(child, labels));
    }
    return labels;
  }

  const allLabels = collectLabels(chartData.root);
  const maxTextWidth = Math.max(
    ...allLabels.map((label) => textWidthCache.getTextWidth(label)),
  );

  // Recursive function to process nodes and assign coordinates
  function processNode(
    node: HierarchyNode,
    depth: number,
    parentX?: number,
    startY?: number,
  ): { node: HierarchyNode; bottomY: number } {
    const x =
      depth === 0
        ? config.margins.left
        : (parentX ?? config.margins.left) + config.spacing.horizontal;

    const y = startY ?? config.margins.top;

    // Get expanded state from existing tree or default to true
    const isExpanded = expandState.get(node.id || node.title) ?? depth === 0 ? true : defaultExpandState;

    node.x = x;
    node.y = y;
    node.depth = depth;
    node.textWidth = textWidthCache.getTextWidth(node.title);
    node.expanded = isExpanded;
    node.hasChildren = node.children && node.children.length > 0;

    maxY = Math.max(maxY, y);
    let currentBottomY = y + config.spacing.vertical;

    // Only process children if node is expanded
    if (node.children && node.children.length > 0 && isExpanded) {
      node.children = node.children.map((child) => {
        const result = processNode(child, depth + 1, x, currentBottomY);
        currentBottomY = result.bottomY;
        return result.node;
      });
    }

    return {
      node: node,
      bottomY: currentBottomY,
    };
  }

  const result = processNode(chartData.root, 0);
  const root = result.node;

  // Calculate dimensions
  const maxDepth = calculateMaxDepth(chartData.root);
  const maxX = config.margins.left + maxDepth * config.spacing.horizontal;
  const textPadding = 20;
  const dimensions: Dimensions = {
    width: maxX + maxTextWidth + textPadding,
    height: maxY + config.spacing.vertical,
  };

  return {
    root,
    dimensions,
  };
}

// Utility functions for cache management
export function clearTextWidthCache(): void {
  textWidthCache.clear();
}

export function getTextWidthCacheSize(): number {
  return textWidthCache.size();
}

// Direct access to cached text width measurement (useful for external components)
export function getCachedTextWidth(text: string): number {
  return textWidthCache.getTextWidth(text);
}
