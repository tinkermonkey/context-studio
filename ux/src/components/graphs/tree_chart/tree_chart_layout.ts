import type {
  HierarchyNode,
  Dimensions,
  LayoutConfig,
  ChartData,
} from "./tree_data";
import { ChartStyles } from "./tree_chart_styles";
import {
  measureSvgTextWidth,
  extractFontPropertiesFromStyles,
  measureHtmlTextHeight,
} from "./tree_chart_utils";

// Default layout configuration
export const defaultLayoutConfig: LayoutConfig = {
  spacing: {
    vertical: 25,
    horizontal: 20,
  },
  margins: {
    top: 30,
    left: 20,
    right: 10,
    bottom: 30,
  },
};

// Function to recalculate layout with external expanded state (using Map<string, boolean>)
export type ExpandState = Map<string, boolean>;

const defaultExpandState = false;
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

// Text width measurement cache to avoid recalculating widths for the same text
// Font changes will require a complete chart redraw, so we only cache by text content
class SvgTextWidthCache {
  private cache = new Map<string, number>();
  private textOptions = extractFontPropertiesFromStyles(ChartStyles.nodeLabel);

  // Get cached width or measure and cache it using current font styles
  getTextWidth(text: string): number {
    if (this.cache.has(text)) {
      return this.cache.get(text)!;
    }

    const width = measureSvgTextWidth(text, this.textOptions);
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
const textWidthCache = new SvgTextWidthCache();

// Text height measurement cache to avoid recalculating heights for the same text
// Font changes will require a complete chart redraw, so we only cache by text content
// eslint-disable-next-line @typescript-eslint/no-unused-vars
class HtmlTextHeightCache {
  private cache = new Map<string, number>();
  private textOptions = extractFontPropertiesFromStyles(
    ChartStyles.nodeDefinition,
  );

  // Get cached height or measure and cache it using current font styles
  getTextHeight(text: string, width: number): number {
    if (this.cache.has(`${text}-${width}`)) {
      return this.cache.get(`${text}-${width}`)!;
    }

    this.cache.set(`${text}-${width}`, height);
    return height;
  }

  // Set a cached value (useful for preserving existing measurements)
  setCachedHeight(text: string, height: number): void {
    this.cache.set(text, height);
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
  maxWidth?: number,
  hoveredNodeId?: string | null,
): ChartData {
  let maxY = config.margins.top;

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
    siblingMaxTextWidth?: number,
  ): { node: HierarchyNode; bottomY: number } {
    const x =
      depth === 0
        ? config.margins.left
        : (parentX ?? config.margins.left) + config.spacing.horizontal;

    let y = startY ?? config.margins.top;

    // Get expanded state from existing tree or default to true
    const isExpanded =
      (expandState.get(node.id || node.title) ?? depth === 0)
        ? true
        : defaultExpandState;

    // Check if this node is hovered and calculate extra spacing
    const isHovered = !!(
      hoveredNodeId &&
      (node.id === hoveredNodeId || node.title === hoveredNodeId)
    );
    const extraVerticalSpacing = isHovered ? 16 : 0; // Total extra spacing for hovered node

    // If hovered, move the node down by half the extra spacing to center it in the added space
    if (isHovered) {
      y += extraVerticalSpacing / 2;
    }

    node.x = x;
    node.y = y;
    node.depth = depth;

    // Use sibling max text width if provided, otherwise calculate individual width
    node.titleWidth =
      siblingMaxTextWidth ?? textWidthCache.getTextWidth(node.title);

    node.definitionWidth = maxWidth
      ? maxWidth - (config.margins.right || 0) - node.x - (node.titleWidth || 0)
      : 0;
    node.definitionHeight = measureHtmlTextHeight(
      node.definition || "",
      node.definitionWidth,
    );
    node.expanded = isExpanded;
    node.hasChildren = node.children && node.children.length > 0;
    node.isHovered = isHovered; // Store hover state on the node

    maxY = Math.max(maxY, y);

    // Calculate the bottom Y position
    // If the node has a definition being displayed, account for its height
    // Otherwise, just use the node's Y position + spacing
    let currentBottomY: number;

    if (
      node.definition &&
      node.definitionHeight &&
      node.definitionHeight > ChartStyles.nodeLabel.height
    ) {
      // Definition is displayed and extends below the node label
      // Definition starts at nodeY - nodeLabel.height and extends downward by definitionHeight
      const definitionBottom =
        y - ChartStyles.nodeLabel.height + node.definitionHeight;
      currentBottomY =
        definitionBottom + config.spacing.vertical + extraVerticalSpacing / 2;
    } else {
      // No definition or definition doesn't extend beyond label height
      // Next element should start after the node label + spacing
      currentBottomY = y + config.spacing.vertical + extraVerticalSpacing / 2;
    }

    // Only process children if node is expanded
    if (node.children && node.children.length > 0 && isExpanded) {
      // First pass: calculate text widths for all children
      const childrenTextWidths = node.children.map((child) =>
        textWidthCache.getTextWidth(child.title),
      );

      // Calculate maximum text width among siblings
      const maxSiblingTextWidth = Math.max(...childrenTextWidths);

      // Second pass: process children with consistent text width
      node.children = node.children.map((child) => {
        const result = processNode(
          child,
          depth + 1,
          x,
          currentBottomY,
          maxSiblingTextWidth,
        );
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
  const totalHeight = result.bottomY;

  // Calculate dimensions
  const maxDepth = calculateMaxDepth(chartData.root);
  const maxX = config.margins.left + maxDepth * config.spacing.horizontal;
  const textPadding = 20;

  // Calculate natural width based on content including right margin
  const naturalWidth =
    maxX + maxTextWidth + textPadding + (config.margins.right || 0);

  // Define minimum width to ensure chart remains usable

  // Use maxWidth constraint if provided, otherwise use natural width
  let finalWidth = naturalWidth;

  if (maxWidth && maxWidth > 0) {
    // When constrained by maxWidth, just use maxWidth but ensure content fits within margins
    finalWidth = maxWidth;
  }

  const dimensions: Dimensions = {
    width: finalWidth,
    height: totalHeight + config.margins.bottom,
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
